"""Derive the Signals screen from the graph that is already stored.

Every row written here cites a record the owner can open: a relationship edge, a warm path, or
one interaction. Nothing is invented, so a database without evidence produces no signals rather
than a plausible-looking reminder. Each rule owns its ``source`` and a stable ``source_key``, so
``UNIQUE (owner_id, source, source_key)`` makes re-deriving an update instead of a duplicate.
Rows the owner completed, skipped, or wrote by hand are history: they are read to stay out of the
way and never rewritten.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    FollowUp,
    InteractionEvent,
    InteractionParticipant,
    Opportunity,
    OpportunityPersonPath,
    Organization,
    Owner,
    Person,
    Relationship,
    utcnow,
)

COOLING_SOURCE = "cooling_relationship"
WARM_PATH_SOURCE = "warm_path"
UNANSWERED_SOURCE = "unanswered_message"
DORMANT_SOURCE = "dormant_contact"
DERIVED_SOURCES = (COOLING_SOURCE, WARM_PATH_SOURCE, UNANSWERED_SOURCE, DORMANT_SOURCE)
COOLING_MIN_STRENGTH = 0.7
COOLING_QUIET_DAYS = 90
COOLING_PRIORITY_SCALE = 10
WARM_PATH_DUE_DAYS = 3
WARM_PATH_PRIORITY = 12
WARM_PATH_SCORE_SCALE = 8
UNANSWERED_QUIET_DAYS = 14
UNANSWERED_PRIORITY = 5
DORMANT_STATUSES = ("dormant", "cold")
DORMANT_MIN_INTERACTIONS = 4
DORMANT_ANNIVERSARY_DAYS = 365
DORMANT_PRIORITY = 1
MAX_SIGNALS = 20
PENDING = "pending"
INCOMING = "incoming"
REAL_IMPORT = "real_import"

_Key = tuple[str, str]


@dataclass(frozen=True, slots=True)
class _Signal:
    """One follow-up a rule asks for, already carrying its evidence-derived wording."""

    person_id: str
    source: str
    source_key: str
    reason: str
    due_date: date
    priority: int

    @property
    def key(self) -> _Key:
        return (self.source, self.source_key)


class FollowUpDeriver:
    """Turns stored relationships, warm paths and interactions into the owner's follow-ups."""

    def __init__(self, session: Session, owner_id: str, demo_mode: bool) -> None:
        self._session = session
        self._owner_id = owner_id
        self._demo_mode = demo_mode

    def derive(self) -> int:
        """Write this owner's derived signals and report how many rows landed.

        Five SELECTs whatever the graph size: the owner, the relationship edges either rule
        cares about, the open warm paths, the newest interaction per contact, and the derived
        rows already stored. Matching happens in Python, so hundreds of people cost the same
        as ten.
        """

        owner = self._session.get(Owner, self._owner_id)
        if owner is None:
            return 0
        planned = self._planned(owner, utcnow())
        stored = self._stored()
        self._prune(stored, planned)
        return self._write(owner, stored, planned)

    def _planned(self, owner: Owner, now: datetime) -> dict[_Key, _Signal]:
        """Collect every rule's signals, drop key collisions, then keep the loudest ones."""

        found = [
            *self._relationship_signals(now),
            *self._warm_path_signals(),
            *self._unanswered_signals(owner, now),
        ]
        indexed: dict[_Key, _Signal] = {}
        for signal in found:
            indexed.setdefault(signal.key, signal)
        return _capped(indexed)

    def _relationship_signals(self, now: datetime) -> list[_Signal]:
        """Cooling strong edges and dormant reciprocal ones, read in a single pass."""

        signals: list[_Signal] = []
        for relationship, person in self._relationship_rows(now):
            if _is_cooling(relationship, now):
                signals.append(_cooling_signal(relationship, person, now))
            if _is_dormant(relationship):
                signals.append(_dormant_signal(relationship, person))
        return signals

    def _relationship_rows(self, now: datetime) -> list[tuple[Relationship, Person]]:
        statement = (
            select(Relationship, Person)
            .select_from(Relationship)
            .join(Person, Person.id == Relationship.person_b_id)
            .where(
                Relationship.owner_id == self._owner_id,
                Person.owner_id == self._owner_id,
                Relationship.last_interaction_at.is_not(None),
                or_(_cooling_clause(now), _dormant_clause()),
            )
            .order_by(Relationship.strength_score.desc(), Person.id)
        )
        if self._demo_mode:
            statement = statement.where(Person.data_origin != REAL_IMPORT)
        return list(self._session.execute(statement).all())

    def _warm_path_signals(self) -> list[_Signal]:
        """Warm paths into opportunities the owner has neither saved nor dismissed."""

        statement = (
            select(OpportunityPersonPath, Opportunity, Person, Organization.name)
            .select_from(OpportunityPersonPath)
            .join(Opportunity, Opportunity.id == OpportunityPersonPath.opportunity_id)
            .join(Person, Person.id == OpportunityPersonPath.person_id)
            .outerjoin(Organization, Organization.id == Opportunity.organization_id)
            .where(
                OpportunityPersonPath.owner_id == self._owner_id,
                Opportunity.saved_at.is_(None),
                Opportunity.dismissed_at.is_(None),
            )
            .order_by(OpportunityPersonPath.path_score.desc(), Person.id)
        )
        if self._demo_mode:
            statement = statement.where(Person.data_origin != REAL_IMPORT)
        return [
            _warm_path_signal(path, opportunity, person, company)
            for path, opportunity, person, company in self._session.execute(statement)
        ]

    def _unanswered_signals(self, owner: Owner, now: datetime) -> list[_Signal]:
        """Contacts whose own message is still the newest one on the thread."""

        newest = (
            select(
                InteractionParticipant.person_id.label("person_id"),
                func.max(InteractionEvent.occurred_at).label("occurred_at"),
            )
            .select_from(InteractionParticipant)
            .join(InteractionEvent, InteractionEvent.id == InteractionParticipant.interaction_id)
            .where(*self._interaction_conditions(owner))
            .group_by(InteractionParticipant.person_id)
            .subquery()
        )
        statement = (
            select(Person, InteractionEvent)
            .select_from(InteractionEvent)
            .join(
                InteractionParticipant,
                InteractionParticipant.interaction_id == InteractionEvent.id,
            )
            .join(Person, Person.id == InteractionParticipant.person_id)
            .join(
                newest,
                and_(
                    newest.c.person_id == InteractionParticipant.person_id,
                    newest.c.occurred_at == InteractionEvent.occurred_at,
                ),
            )
            .where(
                *self._interaction_conditions(owner),
                Person.owner_id == self._owner_id,
                InteractionEvent.direction == INCOMING,
                InteractionEvent.occurred_at < now - timedelta(days=UNANSWERED_QUIET_DAYS),
            )
            .order_by(InteractionEvent.occurred_at.desc(), InteractionEvent.id)
        )
        if self._demo_mode:
            statement = statement.where(Person.data_origin != REAL_IMPORT)
        return self._newest_incoming(statement, now)

    def _newest_incoming(self, statement, now: datetime) -> list[_Signal]:
        """One signal per contact even when two interactions share a timestamp."""

        seen: dict[str, _Signal] = {}
        for person, event in self._session.execute(statement):
            seen.setdefault(person.id, _unanswered_signal(person, event, now))
        return list(seen.values())

    def _interaction_conditions(self, owner: Owner) -> list:
        conditions = [
            InteractionEvent.owner_id == self._owner_id,
            InteractionEvent.is_deleted.is_(False),
            InteractionParticipant.person_id.is_not(None),
        ]
        if owner.self_person_id:
            conditions.append(InteractionParticipant.person_id != owner.self_person_id)
        if self._demo_mode:
            conditions.append(InteractionEvent.data_origin != REAL_IMPORT)
        return conditions

    def _stored(self) -> dict[_Key, FollowUp]:
        """Load derived rows without the demo filter, so a hidden row still holds its key."""

        rows = self._session.scalars(
            select(FollowUp).where(
                FollowUp.owner_id == self._owner_id,
                FollowUp.source.in_(DERIVED_SOURCES),
                FollowUp.source_key.is_not(None),
            )
        )
        return {(row.source, row.source_key): row for row in rows}

    def _prune(self, stored: dict[_Key, FollowUp], planned: dict[_Key, _Signal]) -> None:
        """Delete pending rows the graph stopped justifying; settled ones stay as history."""

        stale = [
            row
            for key, row in stored.items()
            if key not in planned and row.status == PENDING and row.source in DERIVED_SOURCES
        ]
        for row in stale:
            self._session.delete(row)
        if stale:
            self._session.flush()

    def _write(
        self,
        owner: Owner,
        stored: dict[_Key, FollowUp],
        planned: dict[_Key, _Signal],
    ) -> int:
        """Update in place where the key exists, so a dismissed signal stays dismissed."""

        written = 0
        for key, signal in planned.items():
            row = stored.get(key)
            if row is not None and row.status != PENDING:
                continue
            if row is None:
                row = FollowUp(
                    owner_id=self._owner_id,
                    source=signal.source,
                    source_key=signal.source_key,
                )
                self._session.add(row)
            _apply(row, signal, owner.timezone)
            written += 1
        self._session.flush()
        return written


def _cooling_clause(now: datetime):
    return and_(
        Relationship.strength_score >= COOLING_MIN_STRENGTH,
        Relationship.last_interaction_at < now - timedelta(days=COOLING_QUIET_DAYS),
    )


def _dormant_clause():
    return and_(
        Relationship.status.in_(DORMANT_STATUSES),
        Relationship.total_interactions >= DORMANT_MIN_INTERACTIONS,
    )


def _is_cooling(relationship: Relationship, now: datetime) -> bool:
    if relationship.strength_score < COOLING_MIN_STRENGTH:
        return False
    return _quiet_days(relationship, now) > COOLING_QUIET_DAYS


def _is_dormant(relationship: Relationship) -> bool:
    return (
        relationship.status in DORMANT_STATUSES
        and relationship.total_interactions >= DORMANT_MIN_INTERACTIONS
    )


def _cooling_signal(relationship: Relationship, person: Person, now: datetime) -> _Signal:
    quiet = _quiet_days(relationship, now)
    last = _aware(relationship.last_interaction_at)
    return _Signal(
        person_id=person.id,
        source=COOLING_SOURCE,
        source_key=person.id,
        reason=_cooling_reason(relationship, person, quiet, last),
        due_date=last.date() + timedelta(days=COOLING_QUIET_DAYS),
        priority=max(1, round(relationship.strength_score * COOLING_PRIORITY_SCALE)),
    )


def _cooling_reason(
    relationship: Relationship,
    person: Person,
    quiet: int,
    last: datetime,
) -> str:
    """Name the contact, the score that makes them strong, and the date it went quiet."""

    role = person.current_title or "an unrecorded role"
    return (
        f"{person.display_name} scores {relationship.strength_score:.2f} as a relationship, "
        f"holds {role}, and your last recorded exchange was {quiet} days ago on {_day(last)}. "
        f"Reach out before that context goes cold."
    )


def _warm_path_signal(
    path: OpportunityPersonPath,
    opportunity: Opportunity,
    person: Person,
    company: str | None,
) -> _Signal:
    checked = _aware(opportunity.checked_at)
    return _Signal(
        person_id=person.id,
        source=WARM_PATH_SOURCE,
        source_key=f"{opportunity.id}:{person.id}",
        reason=_warm_path_reason(path, opportunity, person, company),
        due_date=checked.date() + timedelta(days=WARM_PATH_DUE_DAYS),
        priority=WARM_PATH_PRIORITY + round(path.path_score * WARM_PATH_SCORE_SCALE),
    )


def _warm_path_reason(
    path: OpportunityPersonPath,
    opportunity: Opportunity,
    person: Person,
    company: str | None,
) -> str:
    """Name the contact, their title and the hiring company, because that is the ask."""

    role = person.current_title or "an unrecorded role"
    employer = company or opportunity.source_domain
    opening = opportunity.role_title or "an unnamed opening"
    return (
        f"{person.display_name} holds {role} at {employer} and is your {path.path_type} path "
        f"into {opening} there, which you have neither saved nor dismissed. "
        f"Ask {person.display_name} who owns that role."
    )


def _unanswered_signal(person: Person, event: InteractionEvent, now: datetime) -> _Signal:
    occurred = _aware(event.occurred_at)
    silent = max(0, int((now - occurred).total_seconds() // 86400))
    return _Signal(
        person_id=person.id,
        source=UNANSWERED_SOURCE,
        source_key=person.id,
        reason=_unanswered_reason(person, event, silent, occurred),
        due_date=occurred.date() + timedelta(days=UNANSWERED_QUIET_DAYS),
        priority=UNANSWERED_PRIORITY,
    )


def _unanswered_reason(
    person: Person,
    event: InteractionEvent,
    silent: int,
    occurred: datetime,
) -> str:
    """Cite the channel, the date and the subject line only, never the message body."""

    subject = f", subject “{event.subject}”" if event.subject else ""
    return (
        f"{person.display_name} sent the last {event.source} message on {_day(occurred)}"
        f"{subject}, and it has waited {silent} days for your reply."
    )


def _dormant_signal(relationship: Relationship, person: Person) -> _Signal:
    last = _aware(relationship.last_interaction_at)
    return _Signal(
        person_id=person.id,
        source=DORMANT_SOURCE,
        source_key=person.id,
        reason=_dormant_reason(relationship, person, last),
        due_date=last.date() + timedelta(days=DORMANT_ANNIVERSARY_DAYS),
        priority=DORMANT_PRIORITY,
    )


def _dormant_reason(relationship: Relationship, person: Person, last: datetime) -> str:
    """Say why a cold edge is still worth something: the traffic it already carried."""

    return (
        f"{person.display_name} reads as {relationship.status} now, yet the two of you "
        f"exchanged {relationship.total_interactions} recorded interactions, the last on "
        f"{_day(last)}. A short check-in keeps that door open."
    )


def _capped(signals: dict[_Key, _Signal]) -> dict[_Key, _Signal]:
    """Keep the loudest ``MAX_SIGNALS``, because an unreadable screen is an empty screen."""

    ranked = sorted(
        signals.items(),
        key=lambda item: (-item[1].priority, item[1].due_date, item[0]),
    )
    return dict(ranked[:MAX_SIGNALS])


def _apply(row: FollowUp, signal: _Signal, timezone: str) -> None:
    row.person_id = signal.person_id
    row.reason = signal.reason
    row.due_date = signal.due_date
    row.due_timezone = timezone
    row.priority = signal.priority
    row.status = PENDING
    row.updated_at = utcnow()


def _quiet_days(relationship: Relationship, now: datetime) -> int:
    last = _aware(relationship.last_interaction_at)
    return max(0, int((now - last).total_seconds() // 86400))


def _day(value: datetime) -> str:
    return value.date().isoformat()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
