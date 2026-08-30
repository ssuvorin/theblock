from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.domain.ports import PublicSearchResult
from app.models import (
    InteractionEvent,
    Opportunity,
    OpportunityEvidence,
    OpportunityPersonPath,
    Organization,
    Person,
    Relationship,
    utcnow,
)
from app.repositories.organizations import OrganizationRepository


class OpportunityRepository:
    def __init__(self, session: Session, owner_id: str, demo_mode: bool) -> None:
        self._session = session
        self._owner_id = owner_id
        self._demo_mode = demo_mode
        self._organizations = OrganizationRepository(session, owner_id)

    def list(
        self,
        verification_status: str | None = None,
        saved: bool | None = None,
        organization_id: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Opportunity], int]:
        conditions = [Opportunity.owner_id == self._owner_id]
        if verification_status:
            conditions.append(Opportunity.verification_status == verification_status)
        if saved is True:
            conditions.append(Opportunity.saved_at.is_not(None))
        elif saved is False:
            conditions.append(Opportunity.saved_at.is_(None))
        if organization_id:
            conditions.append(Opportunity.organization_id == organization_id)
        total = (
            self._session.scalar(select(func.count()).select_from(Opportunity).where(*conditions))
            or 0
        )
        statement = (
            select(Opportunity)
            .where(*conditions)
            .order_by(Opportunity.checked_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return list(self._session.scalars(statement)), total

    def query_candidates(self) -> list[Opportunity]:
        return list(
            self._session.scalars(
                select(Opportunity)
                .where(
                    Opportunity.owner_id == self._owner_id,
                    Opportunity.dismissed_at.is_(None),
                    Opportunity.verification_status != "stale",
                )
                .order_by(Opportunity.checked_at.desc())
            )
        )

    def get(self, opportunity_id: str) -> Opportunity | None:
        return self._session.scalar(
            select(Opportunity).where(
                Opportunity.id == opportunity_id,
                Opportunity.owner_id == self._owner_id,
            )
        )

    def organization(self, organization_id: str | None) -> Organization | None:
        if not organization_id:
            return None
        return self._session.scalar(
            select(Organization).where(
                Organization.id == organization_id,
                Organization.owner_id == self._owner_id,
            )
        )

    def evidence(self, opportunity_id: str) -> list[OpportunityEvidence]:
        return list(
            self._session.scalars(
                select(OpportunityEvidence)
                .where(
                    OpportunityEvidence.owner_id == self._owner_id,
                    OpportunityEvidence.opportunity_id == opportunity_id,
                )
                .order_by(OpportunityEvidence.checked_at.desc())
            )
        )

    def paths(self, opportunity_id: str) -> list[tuple]:
        statement = self._paths_statement().where(
            OpportunityPersonPath.opportunity_id == opportunity_id
        )
        return list(self._session.execute(statement).all())

    def paths_by_opportunity(self, opportunity_ids: Sequence[str]) -> dict[str, list[tuple]]:
        """Load warm-path rows for many opportunities in one query, grouped by opportunity."""

        ids = list(opportunity_ids)
        if not ids:
            return {}
        statement = self._paths_statement().where(OpportunityPersonPath.opportunity_id.in_(ids))
        grouped: dict[str, list[tuple]] = {}
        for row in self._session.execute(statement).all():
            grouped.setdefault(row[0].opportunity_id, []).append(row)
        return grouped

    def _paths_statement(self) -> Select:
        statement = (
            select(OpportunityPersonPath, Person, Relationship, InteractionEvent)
            .join(Person, Person.id == OpportunityPersonPath.person_id)
            .join(Relationship, Relationship.id == OpportunityPersonPath.relationship_id)
            .join(
                InteractionEvent, InteractionEvent.id == OpportunityPersonPath.private_evidence_id
            )
            .where(
                OpportunityPersonPath.owner_id == self._owner_id,
                InteractionEvent.is_deleted.is_(False),
            )
            .order_by(OpportunityPersonPath.path_score.desc())
        )
        if self._demo_mode:
            statement = statement.where(
                Person.data_origin != "real_import",
                InteractionEvent.data_origin != "real_import",
            )
        return statement

    def patch(
        self, opportunity: Opportunity, *, saved: bool | None, dismissed: bool | None
    ) -> None:
        now = utcnow()
        if saved is not None:
            opportunity.saved_at = now if saved else None
        if dismissed is not None:
            opportunity.dismissed_at = now if dismissed else None
        opportunity.updated_at = now
        self._session.flush()

    def upsert_result(
        self, result: PublicSearchResult, provider: str, disclosure: str
    ) -> Opportunity:
        opportunity = self._by_url(result.url)
        organization = self._resolve_organization(result)
        if opportunity is None:
            opportunity = Opportunity(
                owner_id=self._owner_id,
                canonical_url=result.url,
                source_domain=result.source_domain,
                provider=provider,
                checked_at=result.checked_at,
            )
            self._session.add(opportunity)
        self._apply_result(opportunity, organization, result, disclosure)
        self._session.flush()
        self._upsert_evidence(opportunity, result)
        return opportunity

    def _by_url(self, url: str) -> Opportunity | None:
        return self._session.scalar(
            select(Opportunity).where(
                Opportunity.owner_id == self._owner_id,
                Opportunity.canonical_url == url,
            )
        )

    def _resolve_organization(self, result: PublicSearchResult) -> Organization | None:
        """Reuse the row a connection list already created for this company, domain and all."""

        return self._organizations.resolve(result.organization_name, result.organization_domain)

    @staticmethod
    def _apply_result(
        opportunity: Opportunity,
        organization: Organization | None,
        result: PublicSearchResult,
        disclosure: str,
    ) -> None:
        opportunity.organization_id = organization.id if organization else None
        opportunity.role_title = result.role_title
        opportunity.location = result.location
        opportunity.summary = result.excerpt
        opportunity.verification_status = result.verification_status
        opportunity.checked_at = result.checked_at
        opportunity.provider_disclosure = disclosure
        opportunity.updated_at = utcnow()

    def _upsert_evidence(
        self,
        opportunity: Opportunity,
        result: PublicSearchResult,
    ) -> None:
        content_hash = hashlib.sha256(result.excerpt.encode()).hexdigest()
        exists = self._session.scalar(
            select(OpportunityEvidence.id).where(
                OpportunityEvidence.opportunity_id == opportunity.id,
                OpportunityEvidence.url == result.url,
                OpportunityEvidence.content_hash == content_hash,
            )
        )
        if exists:
            return
        self._session.add(
            OpportunityEvidence(
                owner_id=self._owner_id,
                opportunity_id=opportunity.id,
                url=result.url,
                title=result.title,
                excerpt=result.excerpt,
                source_domain=result.source_domain,
                content_hash=content_hash,
                evidence_type=result.evidence_type,
                checked_at=result.checked_at,
                verification_details=result.verification_details,
            )
        )

    def recently_checked(self, since: datetime) -> list[Opportunity]:
        return list(
            self._session.scalars(
                select(Opportunity).where(
                    Opportunity.owner_id == self._owner_id,
                    Opportunity.checked_at >= since,
                )
            )
        )
