"""Deleting a source must not delete people another source still supports (FR-13.3)."""

from __future__ import annotations

import base64
import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from app.config import Settings
from app.models import (
    Base,
    FollowUp,
    InteractionEvent,
    InteractionParticipant,
    Owner,
    Person,
    PersonIdentity,
    SemanticIndexOutbox,
    SourceConnection,
)
from app.services.source_deletion import detail
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

OCCURRED_AT = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


def _settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        auth_secret="s" * 40,
        owner_password="p" * 12,
        encryption_key=base64.urlsafe_b64encode(os.urandom(32)).decode(),
    )


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as active:
        active.add(Owner(id="owner-1", display_name="Owner", email="owner@example.test"))
        active.flush()
        yield active


def _interaction(
    session: Session,
    source: str,
    external_id: str,
    connection_id: str | None,
) -> str:
    event = InteractionEvent(
        owner_id="owner-1",
        source_connection_id=connection_id,
        external_id=external_id,
        type="email",
        source=source,
        occurred_at=OCCURRED_AT,
        body_text="body",
        metadata_json={},
        data_origin="live_connector",
    )
    session.add(event)
    session.flush()
    return event.id


def _person(session: Session, name: str, kind: str, value: str, source: str) -> str:
    person = Person(owner_id="owner-1", display_name=name, data_origin="live_connector")
    session.add(person)
    session.flush()
    session.add(
        PersonIdentity(
            owner_id="owner-1",
            person_id=person.id,
            kind=kind,
            raw_value=value,
            normalized_value=value,
            source=source,
        )
    )
    session.flush()
    return person.id


@pytest.fixture
def connection(session: Session) -> SourceConnection:
    row = SourceConnection(
        owner_id="owner-1",
        source="google",
        external_account_id="owner@example.test",
        status="connected",
        capabilities={"surfaces": ["gmail", "google_calendar"]},
    )
    session.add(row)
    session.flush()
    return row


def test_only_this_connection_s_interactions_are_removed(
    session: Session,
    connection: SourceConnection,
) -> None:
    _interaction(session, "gmail", "g1", connection.id)
    _interaction(session, "google_calendar", "c1", connection.id)
    kept = _interaction(session, "linkedin", "l1", None)

    result = detail(session, session.get(Owner, "owner-1"), connection)

    assert result.interactions == 2
    remaining = list(session.scalars(select(InteractionEvent.id)))
    assert remaining == [kept]


def test_a_person_evidenced_by_another_source_survives(
    session: Session,
    connection: SourceConnection,
) -> None:
    shared = _person(session, "Priya Nair", "linkedin_url", "https://li/priya", "linkedin_export")
    gmail_only = _person(session, "Tom Reed", "email", "tom@x.test", "gmail")
    event = _interaction(session, "gmail", "g1", connection.id)
    other = _interaction(session, "linkedin", "l1", None)
    rows = (
        (shared, event, "priya@rain.test"),
        (shared, other, "priya@rain.test"),
        (gmail_only, event, "tom@x.test"),
    )
    for person_id, interaction_id, address in rows:
        session.add(
            InteractionParticipant(
                owner_id="owner-1",
                interaction_id=interaction_id,
                person_id=person_id,
                source_address=address,
                role="sender",
            )
        )
    session.flush()

    detail(session, session.get(Owner, "owner-1"), connection)

    survivors = {person.display_name for person in session.scalars(select(Person))}
    assert "Priya Nair" in survivors, "a LinkedIn-backed person must outlive a Gmail disconnect"
    assert "Tom Reed" not in survivors, "a person with no remaining evidence is removed"


def test_identities_and_reminders_from_this_source_are_removed(
    session: Session,
    connection: SourceConnection,
) -> None:
    person_id = _person(session, "Tom Reed", "email", "tom@x.test", "gmail")
    session.add(
        FollowUp(
            owner_id="owner-1",
            person_id=person_id,
            reason="Send the spec",
            source="gmail",
            source_key="k1",
        )
    )
    session.flush()

    result = detail(session, session.get(Owner, "owner-1"), connection)

    assert result.identities == 1
    assert result.follow_ups == 1
    assert list(session.scalars(select(PersonIdentity))) == []
    assert list(session.scalars(select(FollowUp))) == []


def test_semantic_chunks_are_queued_for_removal_rather_than_assumed_gone(
    session: Session,
    connection: SourceConnection,
) -> None:
    """The vector store may be unreachable, so removal goes through the durable outbox."""

    _interaction(session, "gmail", "g1", connection.id)

    result = detail(session, session.get(Owner, "owner-1"), connection)

    queued = list(session.scalars(select(SemanticIndexOutbox)))
    assert result.chunks_queued == 1
    assert [row.op for row in queued] == ["tombstone"]


def test_the_owner_s_own_person_is_never_deleted(
    session: Session,
    connection: SourceConnection,
) -> None:
    owner = session.get(Owner, "owner-1")
    owner.self_person_id = _person(session, "Owner", "email", "owner@example.test", "gmail")
    event = _interaction(session, "gmail", "g1", connection.id)
    session.add(
        InteractionParticipant(
            owner_id="owner-1",
            interaction_id=event,
            person_id=owner.self_person_id,
            source_address="owner@example.test",
            role="sender",
        )
    )
    session.flush()

    detail(session, owner, connection)

    assert session.get(Person, owner.self_person_id) is not None
