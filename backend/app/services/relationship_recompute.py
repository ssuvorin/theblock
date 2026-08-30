"""Recompute relationship edges from everything already stored, not from one batch.

A connector sync that scored edges only from its own page would overwrite what the archive
import and the other connectors established. Deriving strength from the persisted
interactions instead means each sync makes the edge more accurate rather than narrower, and
it is the only way ``channel_diversity`` can mean what it says.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import InteractionEvent, InteractionParticipant
from app.services.relationship_graph import MAX_EVIDENCE, EdgeUpserter, ReciprocityStats

_PERSON_BATCH = 200
OUTGOING = "outgoing"


@dataclass
class _Tally:
    outgoing: int = 0
    incoming: int = 0
    first_at: datetime | None = None
    last_at: datetime | None = None
    sources: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class RecomputeResult:
    created: int
    updated: int
    skipped: int


def recompute_edges(
    session: Session,
    owner_id: str,
    self_person_id: str,
    person_ids: Iterable[str],
) -> RecomputeResult:
    """Rewrite owner-to-contact edges for the people a sync touched."""

    contacts = [item for item in dict.fromkeys(person_ids) if item and item != self_person_id]
    if not contacts:
        return RecomputeResult(0, 0, 0)
    upserter = EdgeUpserter(session, owner_id, self_person_id)
    created = 0
    updated = 0
    skipped = 0
    for batch in _batched(contacts):
        tallies = _tally(session, owner_id, batch)
        evidence = _evidence(session, owner_id, batch)
        for person_id in batch:
            tally = tallies.get(person_id)
            stats = _stats(tally) if tally else None
            if stats is None:
                skipped += 1
                continue
            if upserter.upsert(
                person_id,
                stats,
                evidence.get(person_id, []),
                channel_count=len(tally.sources),
            ):
                created += 1
            else:
                updated += 1
    session.flush()
    return RecomputeResult(created, updated, skipped)


def _stats(tally: _Tally) -> ReciprocityStats | None:
    """A person with no dated interaction has nothing defensible to score."""

    last = tally.last_at
    if last is None:
        return None
    return ReciprocityStats(
        outgoing=tally.outgoing,
        incoming=tally.incoming,
        first_at=tally.first_at or last,
        last_at=last,
        evidence=(),
    )


def _tally(session: Session, owner_id: str, person_ids: Sequence[str]) -> dict[str, _Tally]:
    rows = session.execute(
        select(
            InteractionParticipant.person_id,
            InteractionEvent.direction,
            InteractionEvent.source,
            func.count(InteractionEvent.id),
            func.min(InteractionEvent.occurred_at),
            func.max(InteractionEvent.occurred_at),
        )
        .join(InteractionEvent, InteractionEvent.id == InteractionParticipant.interaction_id)
        .where(
            InteractionParticipant.owner_id == owner_id,
            InteractionParticipant.person_id.in_(list(person_ids)),
            InteractionEvent.is_deleted.is_(False),
        )
        .group_by(
            InteractionParticipant.person_id,
            InteractionEvent.direction,
            InteractionEvent.source,
        )
    ).all()
    tallies: dict[str, _Tally] = {}
    for person_id, direction, source, count, first_at, last_at in rows:
        tally = tallies.setdefault(person_id, _Tally())
        if direction == OUTGOING:
            tally.outgoing += count
        else:
            tally.incoming += count
        tally.sources.add(source)
        tally.first_at = _earliest(tally.first_at, _aware(first_at))
        tally.last_at = _latest(tally.last_at, _aware(last_at))
    return tallies


def _evidence(
    session: Session,
    owner_id: str,
    person_ids: Sequence[str],
) -> dict[str, list[dict[str, str]]]:
    """Cite the most recent interactions per person so a warm path is checkable."""

    rows = session.execute(
        select(
            InteractionParticipant.person_id,
            InteractionEvent.id,
            InteractionEvent.source,
            InteractionEvent.occurred_at,
        )
        .join(InteractionEvent, InteractionEvent.id == InteractionParticipant.interaction_id)
        .where(
            InteractionParticipant.owner_id == owner_id,
            InteractionParticipant.person_id.in_(list(person_ids)),
            InteractionEvent.is_deleted.is_(False),
        )
        .order_by(InteractionEvent.occurred_at.desc(), InteractionEvent.id)
    ).all()
    cited: dict[str, list[dict[str, str]]] = {}
    for person_id, interaction_id, source, _ in rows:
        bucket = cited.setdefault(person_id, [])
        if len(bucket) < MAX_EVIDENCE:
            bucket.append({"interaction_id": interaction_id, "source": source})
    return cited


def _batched(values: Sequence[str]) -> list[list[str]]:
    return [
        list(values[start : start + _PERSON_BATCH])
        for start in range(0, len(values), _PERSON_BATCH)
    ]


def _earliest(current: datetime | None, candidate: datetime | None) -> datetime | None:
    if candidate is None:
        return current
    return candidate if current is None else min(current, candidate)


def _latest(current: datetime | None, candidate: datetime | None) -> datetime | None:
    if candidate is None:
        return current
    return candidate if current is None else max(current, candidate)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
