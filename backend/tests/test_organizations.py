"""The reconciling organization resolver is what makes a warm path joinable at all.

An archive import writes ``Organization(name=...)`` with no domain, because a connection list
only prints a company name. Market search knows a name and a domain. Before these rows were
reconciled, "Rain" from the connection list and rain.com from market search were two ids, so
``person.current_org_id`` could never equal ``opportunity.organization_id``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from app.config import Settings
from app.database import Database
from app.domain.ports import PublicSearchResult
from app.models import Base, Organization, Owner, Person
from app.repositories.opportunities import OpportunityRepository
from app.repositories.organizations import OrganizationRepository
from sqlalchemy import select
from sqlalchemy.orm import Session

OWNER_ID = "owner-organizations"
CHECKED_AT = datetime(2025, 3, 1, 9, 0, tzinfo=UTC)
DISCLOSURE = ""


@pytest.fixture
def graph_settings(settings: Settings) -> Settings:
    return Settings(
        **{**settings.model_dump(), "database_url": "sqlite://", "seed_demo_data": False}
    )


@pytest.fixture
def session(graph_settings: Settings) -> Iterator[Session]:
    database = Database(graph_settings)
    Base.metadata.create_all(database.engine)
    with database.session_factory() as active:
        active.add(Owner(id=OWNER_ID, display_name="Alex Ivanov", email="alex@example.test"))
        active.commit()
        yield active


def repository(session: Session) -> OrganizationRepository:
    return OrganizationRepository(session, OWNER_ID)


def stored(session: Session) -> list[Organization]:
    return list(session.scalars(select(Organization).order_by(Organization.created_at)))


def connection_list_row(session: Session, name: str) -> Organization:
    """Write exactly what the archive import writes: a name only, no domain."""

    organization = Organization(owner_id=OWNER_ID, name=name)
    session.add(organization)
    session.flush()
    return organization


def market_result(name: str | None, domain: str | None) -> PublicSearchResult:
    return PublicSearchResult(
        url="https://jobs.ashbyhq.com/rain/senior-product-manager-uae",
        title="Senior Product Manager — UAE",
        source_domain="jobs.ashbyhq.com",
        excerpt="Rain is hiring a Senior Product Manager in the UAE.",
        role_title="Senior Product Manager",
        organization_name=name,
        organization_domain=domain,
        location="UAE",
        verification_status="verified_open_role",
        evidence_type="vacancy",
        checked_at=CHECKED_AT,
    )


def test_domainless_row_is_adopted_and_gains_its_domain_without_changing_id(
    session: Session,
) -> None:
    from_connections = connection_list_row(session, "Rain")
    original_id = from_connections.id

    resolved = repository(session).resolve("Rain", "rain.com")

    assert resolved is not None
    assert resolved.id == original_id
    assert resolved.domain == "rain.com"
    assert len(stored(session)) == 1


def test_adoption_matches_the_name_case_insensitively(session: Session) -> None:
    from_connections = connection_list_row(session, "rain")

    resolved = repository(session).resolve("Rain", "RAIN.com")

    assert resolved.id == from_connections.id
    assert resolved.domain == "rain.com"
    assert len(stored(session)) == 1


def test_resolve_never_creates_two_rows_for_the_same_domain(session: Session) -> None:
    repo = repository(session)

    first = repo.resolve("Rain", "rain.com")
    second = repo.resolve("Rain", "rain.com")
    renamed = repo.resolve("Rain Financial", "rain.com")

    assert first.id == second.id == renamed.id
    assert [row.domain for row in stored(session)] == ["rain.com"]


def test_a_name_only_result_matches_any_existing_row_with_that_name(session: Session) -> None:
    repo = repository(session)
    with_domain = repo.resolve("Binance", "binance.com")

    matched = repo.resolve("binance", None)

    assert matched.id == with_domain.id
    assert len(stored(session)) == 1


def test_a_new_name_without_a_domain_is_created_domainless(session: Session) -> None:
    created = repository(session).resolve("Palm Logistics", None)

    assert created.domain is None
    assert created.name == "Palm Logistics"
    assert len(stored(session)) == 1


def test_two_different_domainless_names_stay_two_rows(session: Session) -> None:
    repo = repository(session)

    repo.resolve("Palm Logistics", None)
    repo.resolve("Crescent Digital Ventures", None)

    assert {row.name for row in stored(session)} == {"Palm Logistics", "Crescent Digital Ventures"}


def test_resolve_returns_none_when_no_company_is_named(session: Session) -> None:
    repo = repository(session)

    assert repo.resolve(None, None) is None
    assert repo.resolve("   ", "") is None
    assert stored(session) == []


def test_market_result_reuses_the_connection_list_row_so_the_person_can_join(
    session: Session,
) -> None:
    """The join that was broken: employer id and hiring organization id must be equal."""

    from_connections = connection_list_row(session, "Rain")
    person = Person(
        owner_id=OWNER_ID,
        display_name="Dana Lee",
        current_title="Head of Product",
        current_org_id=from_connections.id,
        data_origin="synthetic",
    )
    session.add(person)
    session.flush()

    opportunity = OpportunityRepository(session, OWNER_ID, demo_mode=True).upsert_result(
        market_result("Rain", "rain.com"), "synthetic_demo", DISCLOSURE
    )

    assert opportunity.organization_id == person.current_org_id
    assert from_connections.domain == "rain.com"
    assert len(stored(session)) == 1


def test_market_result_without_a_company_leaves_the_opportunity_unresolved(
    session: Session,
) -> None:
    opportunity = OpportunityRepository(session, OWNER_ID, demo_mode=True).upsert_result(
        market_result(None, None), "synthetic_demo", DISCLOSURE
    )

    assert opportunity.organization_id is None
    assert stored(session) == []
