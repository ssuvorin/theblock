"""Derive advisory relationship edges from archive message reciprocity.

A Basic LinkedIn export has no connection list, so the only defensible evidence of a
relationship is who actually exchanged messages. One-directional threads stay cold.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.linkedin_export.normalize import NormalizedMessage
from app.models import InteractionEvent, Person, Relationship, utcnow

ACTIVE_HORIZON_DAYS = 180
RECENCY_HORIZON_DAYS = 365
FREQUENCY_SATURATION = 20
MAX_EVIDENCE = 3


@dataclass(frozen=True, slots=True)
class ReciprocityStats:
    outgoing: int
    incoming: int
    first_at: datetime
    last_at: datetime
    evidence: tuple[str, ...]

    @property
    def total(self) -> int:
        return self.outgoing + self.incoming

    @property
    def is_reciprocal(self) -> bool:
        return self.outgoing > 0 and self.incoming > 0


class _Accumulator:
    def __init__(self) -> None:
        self.outgoing = 0
        self.incoming = 0
        self.first_at: datetime | None = None
        self.last_at: datetime | None = None
        self.evidence: list[str] = []

    def observe(self, message: NormalizedMessage, outgoing: bool) -> None:
        if outgoing:
            self.outgoing += 1
        else:
            self.incoming += 1
        occurred = _aware(message.occurred_at)
        if self.first_at is None or occurred < self.first_at:
            self.first_at = occurred
        if self.last_at is None or occurred > self.last_at:
            self.last_at = occurred
        if len(self.evidence) < MAX_EVIDENCE and message.is_chunkable:
            self.evidence.append(message.external_id)

    def freeze(self) -> ReciprocityStats:
        anchor = self.last_at or utcnow()
        return ReciprocityStats(
            outgoing=self.outgoing,
            incoming=self.incoming,
            first_at=self.first_at or anchor,
            last_at=anchor,
            evidence=tuple(self.evidence),
        )


def collect_reciprocity(
    messages: Iterable[NormalizedMessage],
    owner_url: str | None,
) -> dict[str, ReciprocityStats]:
    """Count messages per counterpart profile URL, split by direction."""

    accumulators: dict[str, _Accumulator] = {}

    def accumulator(url: str) -> _Accumulator:
        return accumulators.setdefault(url, _Accumulator())

    for message in messages:
        sender_url = message.sender.profile_url
        if owner_url is not None and sender_url == owner_url:
            for recipient in message.recipients:
                if recipient.profile_url and recipient.profile_url != owner_url:
                    accumulator(recipient.profile_url).observe(message, outgoing=True)
        elif sender_url and sender_url != owner_url:
            accumulator(sender_url).observe(message, outgoing=False)
    return {url: item.freeze() for url, item in accumulators.items()}


def strength_components(
    stats: ReciprocityStats,
    now: datetime | None = None,
    *,
    channel_count: int = 1,
) -> dict[str, float]:
    """Return advisory sub-scores; every component is explainable to the owner.

    ``channel_count`` is the number of distinct sources the relationship is evidenced in, so
    someone reached by both mail and messages scores above someone reached by one of them.
    """

    reference = now or utcnow()
    age_days = max(0.0, (reference - stats.last_at).total_seconds() / 86400)
    return {
        "recency": round(max(0.0, 1.0 - age_days / RECENCY_HORIZON_DAYS), 3),
        "frequency": round(min(1.0, stats.total / FREQUENCY_SATURATION), 3),
        "reciprocity": 1.0 if stats.is_reciprocal else 0.3,
        "channel_diversity": round(min(1.0, max(1, channel_count) * 0.25), 3),
    }


def strength_score(components: dict[str, float]) -> float:
    return round(
        components["recency"] * 0.35
        + components["frequency"] * 0.25
        + components["reciprocity"] * 0.3
        + components["channel_diversity"] * 0.1,
        3,
    )


def relationship_status(stats: ReciprocityStats, now: datetime | None = None) -> str:
    reference = now or utcnow()
    age_days = (reference - stats.last_at).total_seconds() / 86400
    if not stats.is_reciprocal:
        return "cold"
    return "active" if age_days <= ACTIVE_HORIZON_DAYS else "dormant"


class EdgeUpserter:
    """Create or update owner-to-contact edges, keyed by contact person id.

    Every caller scores and labels an edge the same way here, so an edge written from an
    archive import and one written from a live connector stay directly comparable.
    """

    def __init__(self, session: Session, owner_id: str, self_person_id: str) -> None:
        self._session = session
        self._owner_id = owner_id
        self._self_person_id = self_person_id
        self._existing = self._load_edges()

    def upsert(
        self,
        contact_id: str,
        stats: ReciprocityStats,
        evidence: list[dict[str, str]],
        *,
        channel_count: int = 1,
    ) -> bool:
        """Write one edge and report whether it had to be created."""

        edge = self._existing.get(contact_id)
        created = edge is None
        if edge is None:
            edge = Relationship(
                owner_id=self._owner_id,
                person_a_id=self._self_person_id,
                person_b_id=contact_id,
                type="contact",
            )
            self._session.add(edge)
            self._existing[contact_id] = edge
        components = strength_components(stats, channel_count=channel_count)
        edge.strength_components = components
        edge.strength_score = strength_score(components)
        edge.status = relationship_status(stats)
        edge.last_interaction_at = stats.last_at
        edge.total_interactions = stats.total
        edge.evidence = evidence
        edge.updated_at = utcnow()
        return created

    def _load_edges(self) -> dict[str, Relationship]:
        rows = self._session.scalars(
            select(Relationship).where(
                Relationship.owner_id == self._owner_id,
                Relationship.person_a_id == self._self_person_id,
            )
        )
        return {row.person_b_id: row for row in rows}


class RelationshipDeriver:
    """Upsert one owner-to-contact edge per archive counterpart with cited evidence."""

    def __init__(self, session: Session, owner_id: str, self_person: Person) -> None:
        self._session = session
        self._self_person = self_person
        self._upserter = EdgeUpserter(session, owner_id, self_person.id)

    def apply(
        self,
        stats_by_url: dict[str, ReciprocityStats],
        contacts: dict[str, Person],
        interaction_ids: dict[str, str],
    ) -> tuple[int, int]:
        created = 0
        updated = 0
        for url, stats in stats_by_url.items():
            contact = contacts.get(url)
            if contact is None or contact.id == self._self_person.id:
                continue
            if self._upserter.upsert(contact.id, stats, _archive_evidence(stats, interaction_ids)):
                created += 1
            else:
                updated += 1
        self._session.flush()
        return created, updated


def _archive_evidence(
    stats: ReciprocityStats,
    interaction_ids: dict[str, str],
) -> list[dict[str, str]]:
    return [
        {"interaction_id": interaction_ids[key], "source": "linkedin"}
        for key in stats.evidence
        if key in interaction_ids
    ]


def interaction_id_index(session: Session, owner_id: str) -> dict[str, str]:
    """Map archive external ids to stored interaction ids for evidence citations."""

    rows = session.execute(
        select(InteractionEvent.external_id, InteractionEvent.id).where(
            InteractionEvent.owner_id == owner_id,
            InteractionEvent.source == "linkedin",
        )
    ).all()
    return {external_id: identifier for external_id, identifier in rows}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
