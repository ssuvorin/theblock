"""SQL that decides which organization row a company name or domain refers to.

Two write paths create organizations and they used to be unable to join: an archive import
knows only the company name printed in a connection list, while market search knows a name
and a domain. Both now funnel through :meth:`OrganizationRepository.resolve`, so a contact's
employer and an opportunity's hiring company land on the same row, which is the join a warm
path depends on.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Organization, utcnow


class OrganizationRepository:
    """Owner-scoped, reconciling lookup for organizations, keyed on domain then name."""

    def __init__(self, session: Session, owner_id: str) -> None:
        self._session = session
        self._owner_id = owner_id

    def resolve(self, name: str | None, domain: str | None) -> Organization | None:
        """Return the one organization this name and domain describe, creating it if new.

        A domain identifies an organization exactly, because ``(owner_id, domain)`` is unique,
        so it is matched first. A name alone matches case-insensitively whatever row already
        carries that name. Returns ``None`` only when neither a name nor a domain is known,
        which is how a market result that names no company stays unresolved.
        """

        clean_name = (name or "").strip()
        clean_domain = (domain or "").strip().casefold()
        if clean_domain:
            return self._with_domain(clean_name, clean_domain)
        if clean_name:
            return self._by_name(clean_name) or self._create(clean_name, None)
        return None

    def _with_domain(self, name: str, domain: str) -> Organization:
        """Match the domain, otherwise let a domain-less row of the same name adopt it."""

        existing = self._by_domain(domain)
        if existing is not None:
            return existing
        adoptable = self._by_name(name, domainless_only=True) if name else None
        if adoptable is None:
            return self._create(name or domain, domain)
        adoptable.domain = domain
        adoptable.updated_at = utcnow()
        self._session.flush()
        return adoptable

    def _by_domain(self, domain: str) -> Organization | None:
        return self._session.scalar(
            select(Organization)
            .where(
                Organization.owner_id == self._owner_id,
                func.lower(Organization.domain) == domain,
            )
            .order_by(Organization.created_at)
        )

    def _by_name(self, name: str, domainless_only: bool = False) -> Organization | None:
        statement = select(Organization).where(
            Organization.owner_id == self._owner_id,
            func.lower(Organization.name) == name.casefold(),
        )
        if domainless_only:
            statement = statement.where(Organization.domain.is_(None))
        return self._session.scalar(statement.order_by(Organization.created_at))

    def _create(self, name: str, domain: str | None) -> Organization:
        organization = Organization(owner_id=self._owner_id, name=name, domain=domain)
        self._session.add(organization)
        self._session.flush()
        return organization
