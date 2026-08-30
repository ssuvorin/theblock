"""Derive warm paths from the stored graph instead of from hand-written fixtures.

A path is written only when the graph proves all three of its parts: the person works at the
hiring organization, the owner has a relationship edge to them, and a non-deleted interaction
supplies citable private evidence. Anything weaker stays "no warm path found", and a path that
has stopped being true — the contact changed employer — is deleted rather than left to rot.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    InteractionEvent,
    InteractionParticipant,
    Opportunity,
    OpportunityPersonPath,
    Organization,
    Person,
    Relationship,
    utcnow,
)
from app.services.relationship_graph import RECENCY_HORIZON_DAYS

DIRECT_PATH = "direct"
INTRODUCTION_PATH = "introduction"
ACTIVE_STATUS = "active"
REAL_IMPORT = "real_import"
STRENGTH_WEIGHT = 0.5
RECENCY_WEIGHT = 0.35
ACTIVE_WEIGHT = 0.15

_PathKey = tuple[str, str, str]


@dataclass(frozen=True, slots=True)
class _Evidence:
    """The single interaction a derived path cites, always the most recent one."""

    interaction_id: str
    occurred_at: datetime
    source: str


@dataclass(frozen=True, slots=True)
class _Candidate:
    """One person who satisfies every warm-path precondition, with the proof attached."""

    person: Person
    relationship: Relationship
    organization_name: str
    evidence: _Evidence


@dataclass(frozen=True, slots=True)
class _Plan:
    """What one path row should say once written."""

    opportunity: Opportunity
    candidate: _Candidate
    path_type: str
    score: float


class WarmPathDeriver:
    """Rewrites the warm paths of a set of opportunities from the graph as it stands now."""

    def __init__(self, session: Session, owner_id: str, demo_mode: bool) -> None:
        self._session = session
        self._owner_id = owner_id
        self._demo_mode = demo_mode

    def derive(self, opportunities: Sequence[Opportunity]) -> int:
        """Write, update and prune paths for these opportunities; return the rows written.

        Three SELECTs regardless of how many opportunities arrive: the employed contacts the
        owner has an edge to, their latest interactions, and the paths already stored. The
        matching happens in Python so a page of 20 opportunities stays a constant query count.
        """

        targets = [item for item in opportunities if item.owner_id == self._owner_id]
        if not targets:
            return 0
        organization_ids = {item.organization_id for item in targets if item.organization_id}
        candidates = self._candidates(organization_ids)
        stored = self._stored_paths([item.id for item in targets])
        planned = self._planned(targets, candidates)
        self._prune(stored, planned)
        return self._write(stored, planned)

    def _candidates(self, organization_ids: set[str]) -> dict[str, list[_Candidate]]:
        """Group qualifying contacts by the organization they currently work for."""

        if not organization_ids:
            return {}
        employed = self._employed(organization_ids)
        evidence = self._latest_evidence([person.id for person, _, _ in employed])
        grouped: dict[str, list[_Candidate]] = {}
        for person, relationship, organization_name in employed:
            cited = evidence.get(person.id)
            if cited is None or person.current_org_id is None:
                continue
            grouped.setdefault(person.current_org_id, []).append(
                _Candidate(person, relationship, organization_name, cited)
            )
        return grouped

    def _employed(self, organization_ids: set[str]) -> list[tuple[Person, Relationship, str]]:
        """People at a hiring organization the owner actually has a relationship with."""

        statement = (
            select(Person, Relationship, Organization.name)
            .join(Relationship, Relationship.person_b_id == Person.id)
            .join(Organization, Organization.id == Person.current_org_id)
            .where(
                Person.owner_id == self._owner_id,
                Relationship.owner_id == self._owner_id,
                Person.current_org_id.in_(sorted(organization_ids)),
            )
            .order_by(Relationship.strength_score.desc(), Person.id)
        )
        if self._demo_mode:
            statement = statement.where(Person.data_origin != REAL_IMPORT)
        strongest: dict[str, tuple[Person, Relationship, str]] = {}
        for person, relationship, organization_name in self._session.execute(statement).all():
            strongest.setdefault(person.id, (person, relationship, organization_name))
        return list(strongest.values())

    def _latest_evidence(self, person_ids: Sequence[str]) -> dict[str, _Evidence]:
        """The newest non-deleted interaction per person, which is what the card cites."""

        if not person_ids:
            return {}
        statement = (
            select(
                InteractionParticipant.person_id,
                InteractionEvent.id,
                InteractionEvent.occurred_at,
                InteractionEvent.source,
            )
            .join(InteractionEvent, InteractionEvent.id == InteractionParticipant.interaction_id)
            .where(
                InteractionEvent.owner_id == self._owner_id,
                InteractionParticipant.person_id.in_(list(person_ids)),
                InteractionEvent.is_deleted.is_(False),
            )
            .order_by(InteractionEvent.occurred_at.desc(), InteractionEvent.id)
        )
        if self._demo_mode:
            statement = statement.where(InteractionEvent.data_origin != REAL_IMPORT)
        latest: dict[str, _Evidence] = {}
        for person_id, interaction_id, occurred_at, source in self._session.execute(statement):
            latest.setdefault(person_id, _Evidence(interaction_id, _aware(occurred_at), source))
        return latest

    def _stored_paths(
        self, opportunity_ids: Sequence[str]
    ) -> dict[_PathKey, OpportunityPersonPath]:
        rows = self._session.scalars(
            select(OpportunityPersonPath).where(
                OpportunityPersonPath.owner_id == self._owner_id,
                OpportunityPersonPath.opportunity_id.in_(list(opportunity_ids)),
            )
        )
        return {(row.opportunity_id, row.person_id, row.path_type): row for row in rows}

    def _planned(
        self,
        opportunities: Sequence[Opportunity],
        candidates: dict[str, list[_Candidate]],
    ) -> dict[_PathKey, _Plan]:
        now = utcnow()
        planned: dict[_PathKey, _Plan] = {}
        for opportunity in opportunities:
            for candidate in candidates.get(opportunity.organization_id or "", []):
                path_type = _path_type(candidate.relationship)
                planned[(opportunity.id, candidate.person.id, path_type)] = _Plan(
                    opportunity=opportunity,
                    candidate=candidate,
                    path_type=path_type,
                    score=_path_score(candidate, now),
                )
        return planned

    def _prune(
        self,
        stored: dict[_PathKey, OpportunityPersonPath],
        planned: dict[_PathKey, _Plan],
    ) -> None:
        """Delete unsupported paths first, so a replacement key is free before inserting."""

        stale = [row for key, row in stored.items() if key not in planned]
        for row in stale:
            self._session.delete(row)
        if stale:
            self._session.flush()

    def _write(
        self,
        stored: dict[_PathKey, OpportunityPersonPath],
        planned: dict[_PathKey, _Plan],
    ) -> int:
        """Update in place where a row already exists, so re-deriving never duplicates."""

        for key, plan in planned.items():
            row = stored.get(key)
            if row is None:
                row = OpportunityPersonPath(
                    owner_id=self._owner_id,
                    opportunity_id=plan.opportunity.id,
                    person_id=plan.candidate.person.id,
                    path_type=plan.path_type,
                )
                self._session.add(row)
            _apply_plan(row, plan)
        self._session.flush()
        return len(planned)


def _path_type(relationship: Relationship) -> str:
    """Working at the hiring company is direct unless the edge itself came from an intro."""

    return INTRODUCTION_PATH if relationship.introduced_by else DIRECT_PATH


def _path_score(candidate: _Candidate, now: datetime) -> float:
    """Blend edge strength, evidence recency and whether the edge is still active.

    The recency term reuses the shape ``relationship_graph`` scores edges with, so a path
    score and the relationship score behind it decay at the same rate.
    """

    strength = min(1.0, max(0.0, candidate.relationship.strength_score))
    recency = _recency(candidate.evidence.occurred_at, now)
    active = 1.0 if candidate.relationship.status == ACTIVE_STATUS else 0.0
    return round(
        strength * STRENGTH_WEIGHT + recency * RECENCY_WEIGHT + active * ACTIVE_WEIGHT,
        3,
    )


def _recency(occurred_at: datetime, now: datetime) -> float:
    age_days = max(0.0, (now - occurred_at).total_seconds() / 86400)
    return max(0.0, 1.0 - age_days / RECENCY_HORIZON_DAYS)


def _apply_plan(row: OpportunityPersonPath, plan: _Plan) -> None:
    candidate = plan.candidate
    row.relationship_id = candidate.relationship.id
    row.private_evidence_id = candidate.evidence.interaction_id
    row.path_score = plan.score
    row.rationale = _rationale(candidate)
    row.suggested_action = _suggested_action(plan)


def _rationale(candidate: _Candidate) -> str:
    """State the employer, the title and the cited date, all read from the database."""

    role = candidate.person.current_title or "an unrecorded role"
    return (
        f"{candidate.person.display_name} holds {role} at {candidate.organization_name}, "
        f"and your most recent {candidate.evidence.source} exchange with them is dated "
        f"{_day(candidate.evidence.occurred_at)}."
    )


def _suggested_action(plan: _Plan) -> str:
    candidate = plan.candidate
    name = candidate.person.display_name
    role = plan.opportunity.role_title or "the open role"
    if plan.path_type == INTRODUCTION_PATH:
        return (
            f"Ask the contact who introduced you to {name} to re-open that thread, then "
            f"request an introduction inside {candidate.organization_name} for {role}."
        )
    return (
        f"Message {name} directly, citing your {candidate.evidence.source} exchange from "
        f"{_day(candidate.evidence.occurred_at)}, and ask who owns {role}."
    )


def _day(value: datetime) -> str:
    return value.date().isoformat()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
