"""Turn normalized connector records into the canonical PostgreSQL graph.

Adapters produce provider-shaped records; this is the single place that decides what a
person is. Identity resolution stays deterministic and precision-first: a participant only
becomes a person when it carries an identity the matcher is allowed to auto-link on, so a
shared careers@ inbox never turns into a contact and never absorbs unrelated threads.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.base import NormalizedParticipant, NormalizedRecord
from app.domain.identity.normalize import (
    IdentityKind,
    IdentityNormalizationError,
    NormalizedIdentity,
    is_role_email,
    normalize_identity,
)
from app.models import (
    InteractionEvent,
    InteractionParticipant,
    Owner,
    Person,
    PersonIdentity,
    SourceConnection,
    utcnow,
)

DATA_ORIGIN = "live_connector"
DEFAULT_LOCATOR = "body:0"
LINKABLE_KINDS = (IdentityKind.EMAIL, IdentityKind.PHONE, IdentityKind.LINKEDIN_URL)


@dataclass
class GraphDelta:
    """What one batch changed, reported to the owner as sync progress."""

    processed: int = 0
    skipped: int = 0
    people_created: int = 0
    identities_created: int = 0
    interactions_created: int = 0
    interactions_updated: int = 0
    participants_created: int = 0
    participants_unresolved: int = 0
    shared_addresses_skipped: int = 0
    touched_person_ids: set[str] = field(default_factory=set)
    interaction_ids: list[str] = field(default_factory=list)

    def merge(self, other: GraphDelta) -> None:
        self.processed += other.processed
        self.skipped += other.skipped
        self.people_created += other.people_created
        self.identities_created += other.identities_created
        self.interactions_created += other.interactions_created
        self.interactions_updated += other.interactions_updated
        self.participants_created += other.participants_created
        self.participants_unresolved += other.participants_unresolved
        self.shared_addresses_skipped += other.shared_addresses_skipped
        self.touched_person_ids |= other.touched_person_ids
        self.interaction_ids.extend(other.interaction_ids)

    def counters(self) -> dict[str, int]:
        return {
            "people_created": self.people_created,
            "identities_created": self.identities_created,
            "interactions_created": self.interactions_created,
            "interactions_updated": self.interactions_updated,
            "participants_created": self.participants_created,
            "participants_unresolved": self.participants_unresolved,
            "shared_addresses_skipped": self.shared_addresses_skipped,
        }


class ConnectorGraphWriter:
    """Write one connection's records as people, interactions and participants."""

    def __init__(self, session: Session, owner: Owner, connection: SourceConnection) -> None:
        self._session = session
        self._owner = owner
        self._connection = connection
        self._identities = self._identity_index()
        self._self_person_id = self._ensure_self_person()

    @property
    def self_person_id(self) -> str:
        return self._self_person_id

    def write(self, records: Sequence[NormalizedRecord]) -> GraphDelta:
        delta = GraphDelta()
        for record in records:
            self._write_record(record, delta)
        self._session.flush()
        return delta

    def attach_owner_identity(self, kind: IdentityKind | str, raw_value: str) -> None:
        """Bind the authorized account to the owner so their own messages resolve to self."""

        try:
            identity = normalize_identity(kind, raw_value, source=self._connection.source)
        except IdentityNormalizationError:
            return
        self._add_identity(self._self_person_id, identity, is_verified=True, is_primary=False)
        self._session.flush()

    def _write_record(self, record: NormalizedRecord, delta: GraphDelta) -> None:
        existing = self._existing_interaction(record)
        if existing is None:
            event = self._create_interaction(record)
            delta.interactions_created += 1
        else:
            event = existing
            if not self._apply_update(event, record):
                delta.skipped += 1
                return
            delta.interactions_updated += 1
        delta.processed += 1
        delta.interaction_ids.append(event.id)
        self._write_participants(event, record, delta, replace=existing is not None)

    def _existing_interaction(self, record: NormalizedRecord) -> InteractionEvent | None:
        return self._session.scalar(
            select(InteractionEvent).where(
                InteractionEvent.owner_id == self._owner.id,
                InteractionEvent.source == record.source,
                InteractionEvent.external_id == record.external_id,
            )
        )

    def _create_interaction(self, record: NormalizedRecord) -> InteractionEvent:
        event = InteractionEvent(
            owner_id=self._owner.id,
            source_connection_id=self._connection.id,
            external_id=record.external_id,
            type=record.type,
            source=record.source,
            direction=record.direction,
            occurred_at=record.occurred_at,
            subject=record.subject,
            body_text=record.body_text,
            metadata_json=_metadata(record),
            raw_ref=record.raw_ref or None,
            content_version=record.content_version,
            is_deleted=record.is_deleted,
            data_origin=DATA_ORIGIN,
        )
        self._session.add(event)
        self._session.flush()
        return event

    def _apply_update(self, event: InteractionEvent, record: NormalizedRecord) -> bool:
        """Replay is a no-op unless the provider actually changed the record.

        Comparing content rather than trusting the cursor is what makes a resync idempotent:
        a bounded re-import of ninety days of mail rewrites nothing it has already stored.
        """

        unchanged = (
            event.subject == record.subject
            and event.body_text == record.body_text
            and event.occurred_at == record.occurred_at
            and event.is_deleted == record.is_deleted
            and event.metadata_json == _metadata(record)
        )
        if unchanged:
            return False
        event.subject = record.subject
        event.body_text = record.body_text
        event.occurred_at = record.occurred_at
        event.direction = record.direction
        event.metadata_json = _metadata(record)
        event.is_deleted = record.is_deleted
        event.source_connection_id = self._connection.id
        event.content_version = max(event.content_version + 1, record.content_version)
        return True

    def _write_participants(
        self,
        event: InteractionEvent,
        record: NormalizedRecord,
        delta: GraphDelta,
        *,
        replace: bool,
    ) -> None:
        if replace:
            self._clear_participants(event.id)
        seen: set[tuple[str, str]] = set()
        for participant in record.participants:
            address = participant.source_address or participant.display_name or "unknown"
            key = (address, participant.role)
            if key in seen:
                continue
            seen.add(key)
            person_id = self._resolve_person(participant, record.source, delta)
            self._session.add(
                InteractionParticipant(
                    owner_id=self._owner.id,
                    interaction_id=event.id,
                    person_id=person_id,
                    source_address=address,
                    role=participant.role,
                )
            )
            delta.participants_created += 1
            if person_id is None:
                delta.participants_unresolved += 1
            elif person_id != self._self_person_id:
                delta.touched_person_ids.add(person_id)

    def _clear_participants(self, interaction_id: str) -> None:
        rows = self._session.scalars(
            select(InteractionParticipant).where(
                InteractionParticipant.owner_id == self._owner.id,
                InteractionParticipant.interaction_id == interaction_id,
            )
        )
        for row in rows:
            self._session.delete(row)
        self._session.flush()

    def _resolve_person(
        self,
        participant: NormalizedParticipant,
        source: str,
        delta: GraphDelta,
    ) -> str | None:
        candidates = _identity_candidates(participant, source)
        for identity in candidates:
            existing = self._identities.get((identity.kind.value, identity.normalized_value))
            if existing is not None:
                return existing.person_id
        linkable = [item for item in candidates if _is_linkable(item)]
        if not linkable:
            if candidates:
                delta.shared_addresses_skipped += 1
            return None
        person = self._create_person(participant)
        delta.people_created += 1
        for identity in linkable:
            self._add_identity(person.id, identity, is_verified=True, is_primary=False)
            delta.identities_created += 1
        return person.id

    def _create_person(self, participant: NormalizedParticipant) -> Person:
        display = participant.display_name or _display_from(participant.source_address)
        person = Person(
            owner_id=self._owner.id,
            display_name=display,
            data_origin=DATA_ORIGIN,
        )
        self._session.add(person)
        self._session.flush()
        return person

    def _add_identity(
        self,
        person_id: str,
        identity: NormalizedIdentity,
        *,
        is_verified: bool,
        is_primary: bool,
    ) -> None:
        key = (identity.kind.value, identity.normalized_value)
        if key in self._identities:
            return
        row = PersonIdentity(
            owner_id=self._owner.id,
            person_id=person_id,
            kind=key[0],
            raw_value=identity.raw_value,
            normalized_value=key[1],
            source=identity.source,
            is_verified=is_verified,
            is_primary=is_primary,
        )
        self._session.add(row)
        self._identities[key] = row

    def _identity_index(self) -> dict[tuple[str, str], PersonIdentity]:
        rows = self._session.scalars(
            select(PersonIdentity).where(PersonIdentity.owner_id == self._owner.id)
        )
        return {(row.kind, row.normalized_value): row for row in rows}

    def _ensure_self_person(self) -> str:
        """A connector must not be the reason the owner has no node in their own graph."""

        if self._owner.self_person_id:
            existing = self._session.get(Person, self._owner.self_person_id)
            if existing is not None:
                return existing.id
        person = Person(
            owner_id=self._owner.id,
            display_name=self._owner.display_name,
            data_origin=DATA_ORIGIN,
        )
        self._session.add(person)
        self._session.flush()
        self._owner.self_person_id = person.id
        self._owner.updated_at = utcnow()
        return person.id


def _metadata(record: NormalizedRecord) -> dict:
    return {"citation_locator": DEFAULT_LOCATOR, **record.metadata}


def _identity_candidates(
    participant: NormalizedParticipant,
    source: str,
) -> list[NormalizedIdentity]:
    """Normalize every identity hint the adapter supplied, silently dropping junk."""

    raw: list[tuple[IdentityKind | str, str]] = [
        (kind, value) for kind, value in participant.identity_hint.items() if value
    ]
    if not raw and "@" in participant.source_address:
        raw.append((IdentityKind.EMAIL, participant.source_address))
    normalized: list[NormalizedIdentity] = []
    for kind, value in raw:
        try:
            normalized.append(normalize_identity(kind, value, source=source))
        except (IdentityNormalizationError, ValueError):
            continue
    return normalized


def _is_linkable(identity: NormalizedIdentity) -> bool:
    """Only evidence the deterministic matcher trusts may create a person on its own."""

    if identity.kind not in LINKABLE_KINDS:
        return False
    if identity.kind is IdentityKind.EMAIL:
        return not is_role_email(identity.normalized_value)
    return True


def _display_from(address: str) -> str:
    local = address.split("@", 1)[0]
    cleaned = local.replace(".", " ").replace("_", " ").replace("-", " ").strip()
    return cleaned.title() if cleaned else address
