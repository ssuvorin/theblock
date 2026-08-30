"""Delete one source's contribution without deleting people another source still supports.

FR-13.3 is the whole shape of this file: removing Gmail must remove Gmail's interactions,
identities and reminders, but a person who is also in the LinkedIn archive stays. So people
are only removed when nothing is left that evidences them, and the semantic index is told to
drop the chunks through the same durable outbox that created them — never by assuming the
vector store is reachable at the moment the owner presses delete.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    FollowUp,
    InteractionEvent,
    InteractionParticipant,
    Owner,
    Person,
    PersonIdentity,
    Relationship,
    SourceConnection,
)
from app.repositories.semantic_outbox import SemanticOutboxRepository


@dataclass(frozen=True, slots=True)
class DeletionResult:
    interactions: int
    participants: int
    identities: int
    people: int
    follow_ups: int
    chunks_queued: int


def delete_connection_data(
    session: Session,
    owner: Owner,
    connection: SourceConnection,
    embedding_version: str = "v1",
) -> int:
    """Remove this connection's data and return how many interactions went away."""

    return detail(session, owner, connection, embedding_version).interactions


def detail(
    session: Session,
    owner: Owner,
    connection: SourceConnection,
    embedding_version: str = "v1",
) -> DeletionResult:
    sources = _sources(connection)
    interactions = _interactions(session, owner.id, connection.id, sources)
    outbox = SemanticOutboxRepository(session, owner.id)
    for interaction in interactions:
        outbox.enqueue_tombstone(interaction.id, embedding_version)
    touched = _participant_people(session, owner.id, [item.id for item in interactions])
    participants = _drop_participants(session, owner.id, [item.id for item in interactions])
    for interaction in interactions:
        session.delete(interaction)
    session.flush()
    identities = _drop_identities(session, owner.id, sources)
    follow_ups = _drop_follow_ups(session, owner.id, sources)
    people = _drop_orphan_people(session, owner, touched)
    session.flush()
    return DeletionResult(
        interactions=len(interactions),
        participants=participants,
        identities=identities,
        people=people,
        follow_ups=follow_ups,
        chunks_queued=len(interactions),
    )


def _sources(connection: SourceConnection) -> tuple[str, ...]:
    """A Google connection owns two interaction sources; fall back to the source name."""

    declared = (connection.capabilities or {}).get("surfaces")
    surfaces = tuple(str(item) for item in declared or () if item)
    return surfaces or (connection.source,)


def _interactions(
    session: Session,
    owner_id: str,
    connection_id: str,
    sources: tuple[str, ...],
) -> list[InteractionEvent]:
    """Match on the connection first, and on source for rows imported before it existed."""

    return list(
        session.scalars(
            select(InteractionEvent).where(
                InteractionEvent.owner_id == owner_id,
                (InteractionEvent.source_connection_id == connection_id)
                | InteractionEvent.source.in_(list(sources)),
            )
        )
    )


def _participant_people(session: Session, owner_id: str, interaction_ids: list[str]) -> set[str]:
    if not interaction_ids:
        return set()
    rows = session.scalars(
        select(InteractionParticipant.person_id).where(
            InteractionParticipant.owner_id == owner_id,
            InteractionParticipant.interaction_id.in_(interaction_ids),
            InteractionParticipant.person_id.is_not(None),
        )
    )
    return {row for row in rows if row}


def _drop_participants(session: Session, owner_id: str, interaction_ids: list[str]) -> int:
    if not interaction_ids:
        return 0
    rows = list(
        session.scalars(
            select(InteractionParticipant).where(
                InteractionParticipant.owner_id == owner_id,
                InteractionParticipant.interaction_id.in_(interaction_ids),
            )
        )
    )
    for row in rows:
        session.delete(row)
    session.flush()
    return len(rows)


def _drop_identities(session: Session, owner_id: str, sources: tuple[str, ...]) -> int:
    rows = list(
        session.scalars(
            select(PersonIdentity).where(
                PersonIdentity.owner_id == owner_id,
                PersonIdentity.source.in_(list(sources)),
            )
        )
    )
    for row in rows:
        session.delete(row)
    session.flush()
    return len(rows)


def _drop_follow_ups(session: Session, owner_id: str, sources: tuple[str, ...]) -> int:
    rows = list(
        session.scalars(
            select(FollowUp).where(
                FollowUp.owner_id == owner_id,
                FollowUp.source.in_(list(sources)),
            )
        )
    )
    for row in rows:
        session.delete(row)
    session.flush()
    return len(rows)


def _drop_orphan_people(session: Session, owner: Owner, candidates: set[str]) -> int:
    """Remove only people with no remaining interaction and no remaining identity."""

    removed = 0
    for person_id in candidates:
        if person_id == owner.self_person_id or _still_supported(session, owner.id, person_id):
            continue
        _drop_edges(session, owner.id, person_id)
        person = session.get(Person, person_id)
        if person is not None:
            session.delete(person)
            removed += 1
    session.flush()
    return removed


def _still_supported(session: Session, owner_id: str, person_id: str) -> bool:
    has_interaction = session.scalar(
        select(InteractionParticipant.id)
        .where(
            InteractionParticipant.owner_id == owner_id,
            InteractionParticipant.person_id == person_id,
        )
        .limit(1)
    )
    if has_interaction:
        return True
    has_identity = session.scalar(
        select(PersonIdentity.id)
        .where(PersonIdentity.owner_id == owner_id, PersonIdentity.person_id == person_id)
        .limit(1)
    )
    return bool(has_identity)


def _drop_edges(session: Session, owner_id: str, person_id: str) -> None:
    rows = session.scalars(
        select(Relationship).where(
            Relationship.owner_id == owner_id,
            (Relationship.person_a_id == person_id) | (Relationship.person_b_id == person_id),
        )
    )
    for row in rows:
        session.delete(row)
    session.flush()
