from __future__ import annotations

from pathlib import Path

import pytest
from app.config import Settings
from app.connectors.linkedin_export.importer import load_linkedin_export
from app.database import Database
from app.models import (
    InteractionEvent,
    InteractionParticipant,
    Owner,
    Person,
    PersonIdentity,
    Relationship,
)
from app.schema import upgrade_to_head
from app.services.graph_writer import ArchiveGraphWriter
from app.services.relationship_graph import collect_reciprocity
from sqlalchemy import func, select
from sqlalchemy.orm import Session

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_export"
OWNER_URL = "https://www.linkedin.com/in/maya-haddad-product"


@pytest.fixture
def session(settings: Settings) -> Session:
    database = Database(Settings(**{**settings.model_dump(), "seed_demo_data": False}))
    upgrade_to_head(database.engine)
    with database.session_factory() as active:
        active.add(Owner(id="owner-1", display_name="Maya Haddad", email="maya@example.test"))
        active.commit()
        yield active


@pytest.fixture
def plan():
    return load_linkedin_export(FIXTURE, data_origin="synthetic", demo_mode=True)


def _write(session: Session, plan) -> object:
    owner = session.scalar(select(Owner))
    report = ArchiveGraphWriter(session, owner).write(plan)
    session.commit()
    return report


def test_import_creates_people_identities_and_interactions(session: Session, plan) -> None:
    report = _write(session, plan)

    assert report.people_created == len(plan.people)
    assert report.interactions_created == len(plan.messages)
    assert report.data_origin == "synthetic"
    assert session.scalar(select(func.count()).select_from(Person)) == len(plan.people)
    linkedin_identities = session.scalars(
        select(PersonIdentity).where(PersonIdentity.kind == "linkedin_url")
    ).all()
    assert len(linkedin_identities) == len(plan.people)
    assert all(item.is_verified for item in linkedin_identities)


def test_owner_self_person_is_linked_and_titled_from_profile(session: Session, plan) -> None:
    report = _write(session, plan)

    owner = session.scalar(select(Owner))
    assert owner.self_person_id == report.self_person_id
    self_person = session.get(Person, report.self_person_id)
    assert self_person.display_name == "Maya Haddad"
    assert self_person.current_title == plan.owner_profile.headline
    owner_emails = session.scalars(
        select(PersonIdentity).where(
            PersonIdentity.person_id == self_person.id,
            PersonIdentity.kind == "email",
        )
    ).all()
    assert [item.normalized_value for item in owner_emails] == ["maya.haddad@example.test"]


def test_every_interaction_has_participants_resolved_to_people(session: Session, plan) -> None:
    _write(session, plan)

    total_events = session.scalar(select(func.count()).select_from(InteractionEvent))
    orphan_events = session.scalar(
        select(func.count())
        .select_from(InteractionEvent)
        .where(
            ~select(InteractionParticipant.id)
            .where(InteractionParticipant.interaction_id == InteractionEvent.id)
            .exists()
        )
    )
    unresolved = session.scalar(
        select(func.count())
        .select_from(InteractionParticipant)
        .where(InteractionParticipant.person_id.is_(None))
    )
    assert total_events == len(plan.messages)
    assert orphan_events == 0
    assert unresolved == 0


def test_relationships_follow_message_reciprocity(session: Session, plan) -> None:
    report = _write(session, plan)

    stats = collect_reciprocity(plan.messages, OWNER_URL)
    edges = session.scalars(select(Relationship)).all()
    assert report.relationships_created == len(edges)
    assert len(edges) == len(stats)

    self_person_id = report.self_person_id
    assert all(edge.person_a_id == self_person_id for edge in edges)
    assert all(edge.person_b_id != self_person_id for edge in edges)
    for edge in edges:
        assert 0.0 <= edge.strength_score <= 1.0
        assert edge.total_interactions > 0
        assert edge.status in {"active", "dormant", "cold"}
        assert set(edge.strength_components) == {
            "recency",
            "frequency",
            "reciprocity",
            "channel_diversity",
        }


def test_relationship_evidence_points_at_stored_interactions(session: Session, plan) -> None:
    _write(session, plan)

    stored_ids = set(session.scalars(select(InteractionEvent.id)).all())
    edges = session.scalars(select(Relationship)).all()
    cited = [item for edge in edges for item in edge.evidence]
    assert cited
    assert all(item["interaction_id"] in stored_ids for item in cited)
    assert all(item["source"] == "linkedin" for item in cited)


def test_one_directional_thread_stays_cold() -> None:
    plan = load_linkedin_export(FIXTURE, data_origin="synthetic", demo_mode=True)
    stats = collect_reciprocity(plan.messages, OWNER_URL)
    assert stats, "fixture must produce counterparts"
    for counterpart in stats.values():
        if not counterpart.is_reciprocal:
            assert counterpart.outgoing == 0 or counterpart.incoming == 0


def test_reimport_is_idempotent(session: Session, plan) -> None:
    first = _write(session, plan)
    second = _write(session, plan)

    assert second.people_created == 0
    assert second.interactions_created == 0
    assert second.people_matched == first.people_created
    assert second.interactions_existing == len(plan.messages)
    assert second.relationships_created == 0
    assert second.relationships_updated == first.relationships_created
    assert session.scalar(select(func.count()).select_from(Person)) == len(plan.people)
    assert session.scalar(select(func.count()).select_from(InteractionEvent)) == len(plan.messages)
    assert session.scalar(select(func.count()).select_from(Relationship)) == len(
        collect_reciprocity(plan.messages, OWNER_URL)
    )
