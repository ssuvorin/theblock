from __future__ import annotations

from app.models import (
    InteractionEvent,
    Opportunity,
    OpportunityPersonPath,
    Organization,
    Owner,
    Person,
    PersonIdentity,
    Relationship,
)
from app.services.demo_reset import DemoSeedReset
from app.services.demo_seed import (
    SEEDED_OPPORTUNITY_KEYS,
    SEEDED_ORG_KEYS,
    SEEDED_PERSON_KEYS,
    seeded_ids,
)
from fastapi.testclient import TestClient
from sqlalchemy import func, select


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_seeder_ids_match_the_declared_key_lists(client: TestClient) -> None:
    """The reset recomputes ids, so a seeder that adds a key without declaring it must fail."""

    with client.app.state.database.session_factory() as session:
        people = set(session.scalars(select(Person.id)))
        organizations = set(session.scalars(select(Organization.id)))
        opportunities = set(session.scalars(select(Opportunity.id)))

    assert people == set(seeded_ids("person", SEEDED_PERSON_KEYS))
    assert organizations == set(seeded_ids("org", SEEDED_ORG_KEYS))
    assert opportunities == set(seeded_ids("opportunity", SEEDED_OPPORTUNITY_KEYS))


def test_reset_removes_the_seeded_graph_but_keeps_the_owner(client: TestClient) -> None:
    with client.app.state.database.session_factory() as session:
        owner = session.scalar(select(Owner))
        assert _count(session, Person) > 0
        assert _count(session, OpportunityPersonPath) > 0

        report = DemoSeedReset(session, owner).run()
        session.commit()

        assert report.removed_anything
        assert report.people_removed == len(SEEDED_PERSON_KEYS)
        assert report.paths_removed > 0
        assert _count(session, Person) == 0
        assert _count(session, Relationship) == 0
        assert _count(session, InteractionEvent) == 0
        assert _count(session, OpportunityPersonPath) == 0
        assert _count(session, PersonIdentity) == 0
        assert _count(session, Organization) == 0
        assert session.scalar(select(Owner)) is not None


def test_reset_releases_the_seeded_self_person(client: TestClient) -> None:
    """A stale self person would leave the owner pointing at a deleted row."""

    with client.app.state.database.session_factory() as session:
        owner = session.scalar(select(Owner))
        assert owner.self_person_id in seeded_ids("person", SEEDED_PERSON_KEYS)

        DemoSeedReset(session, owner).run()
        session.commit()

        assert owner.self_person_id is None


def test_reset_is_idempotent_and_cheap_when_there_is_no_seed(client: TestClient) -> None:
    with client.app.state.database.session_factory() as session:
        owner = session.scalar(select(Owner))
        DemoSeedReset(session, owner).run()
        session.commit()

        second = DemoSeedReset(session, owner).run()

        assert second.removed_anything is False
        assert second.people_removed == 0


def test_reset_keeps_imported_rows(client: TestClient) -> None:
    """Only deterministic seeded ids may be deleted; real imports must survive."""

    with client.app.state.database.session_factory() as session:
        owner = session.scalar(select(Owner))
        session.add(
            Person(
                id="imported-person",
                owner_id=owner.id,
                display_name="Imported Contact",
                data_origin="synthetic",
            )
        )
        session.commit()

        DemoSeedReset(session, owner).run()
        session.commit()

        remaining = list(session.scalars(select(Person.id)))
        assert remaining == ["imported-person"]
