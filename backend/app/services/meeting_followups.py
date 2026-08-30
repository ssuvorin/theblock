"""Turn imported meeting action items into follow-ups, once per action item.

Deduplication is the whole job. Two consecutive syncs of the same meeting must leave exactly
one follow-up per action item, which is why the connector already computed a stable
``source_key`` — the provider's own id when it has one, otherwise a hash of the meeting id
and the normalized text. ``UNIQUE (owner_id, source, source_key)`` then makes the write
idempotent no matter how often the meeting is re-read.

An action item whose owner cannot be resolved to a real contact is counted, not invented: a
reminder attached to a guessed person is worse than no reminder.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.base import NormalizedRecord
from app.models import FollowUp, InteractionEvent, InteractionParticipant, Owner, Person

DEFAULT_PRIORITY = 1


@dataclass
class FollowUpReport:
    created: int = 0
    existing: int = 0
    unassigned: int = 0

    def counters(self) -> dict[str, int]:
        return {
            "followups_created": self.created,
            "followups_existing": self.existing,
            "action_items_unassigned": self.unassigned,
        }


def create_meeting_followups(
    session: Session,
    owner: Owner,
    records: Sequence[NormalizedRecord],
) -> FollowUpReport:
    """Create one follow-up per resolvable action item across the given records."""

    report = FollowUpReport()
    for record in records:
        items = _action_items(record)
        if items:
            _apply(session, owner, record, items, report)
    session.flush()
    return report


def _apply(
    session: Session,
    owner: Owner,
    record: NormalizedRecord,
    items: list[dict],
    report: FollowUpReport,
) -> None:
    event = _interaction(session, owner.id, record)
    if event is None:
        report.unassigned += len(items)
        return
    people = _participant_people(session, owner, event.id)
    existing = _existing_keys(session, owner.id, record.source)
    for item in items:
        key = str(item.get("source_key") or "")
        person_id = _match(str(item.get("owner") or ""), people)
        if not key or person_id is None:
            report.unassigned += 1
            continue
        if key in existing:
            report.existing += 1
            continue
        session.add(
            FollowUp(
                owner_id=owner.id,
                person_id=person_id,
                reason=_reason(record, item),
                source=record.source,
                source_key=key,
                priority=DEFAULT_PRIORITY,
                status="pending",
                due_timezone=owner.timezone,
            )
        )
        existing.add(key)
        report.created += 1


def _action_items(record: NormalizedRecord) -> list[dict]:
    items = record.metadata.get("action_items")
    return [item for item in items or [] if isinstance(item, dict)]


def _interaction(
    session: Session,
    owner_id: str,
    record: NormalizedRecord,
) -> InteractionEvent | None:
    return session.scalar(
        select(InteractionEvent).where(
            InteractionEvent.owner_id == owner_id,
            InteractionEvent.source == record.source,
            InteractionEvent.external_id == record.external_id,
        )
    )


def _participant_people(session: Session, owner: Owner, interaction_id: str) -> dict[str, str]:
    """Index this meeting's resolved attendees by address and by display name."""

    rows = session.execute(
        select(InteractionParticipant.source_address, Person.id, Person.display_name)
        .join(Person, Person.id == InteractionParticipant.person_id)
        .where(
            InteractionParticipant.owner_id == owner.id,
            InteractionParticipant.interaction_id == interaction_id,
            InteractionParticipant.person_id.is_not(None),
            InteractionParticipant.person_id != owner.self_person_id,
        )
    ).all()
    index: dict[str, str] = {}
    for address, person_id, display_name in rows:
        index[address.casefold()] = person_id
        if display_name:
            index[display_name.casefold()] = person_id
    return index


def _match(owner_name: str, people: dict[str, str]) -> str | None:
    """Exact address or exact name only. A partial name match would guess."""

    candidate = owner_name.strip().casefold()
    if not candidate:
        return None
    return people.get(candidate)


def _existing_keys(session: Session, owner_id: str, source: str) -> set[str]:
    return set(
        session.scalars(
            select(FollowUp.source_key).where(
                FollowUp.owner_id == owner_id,
                FollowUp.source == source,
                FollowUp.source_key.is_not(None),
            )
        )
    )


def _reason(record: NormalizedRecord, item: dict) -> str:
    text = str(item.get("text") or "").strip()
    subject = (record.subject or "meeting").strip()
    stamp = record.occurred_at.date().isoformat()
    return f"{text} — agreed in “{subject}” on {stamp}"
