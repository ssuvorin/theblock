from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from app.config import Settings
from app.database import Database
from app.models import (
    Base,
    FollowUp,
    InteractionEvent,
    InteractionParticipant,
    Opportunity,
    OpportunityPersonPath,
    Organization,
    Owner,
    Person,
    Relationship,
)
from app.services.followup_rules import (
    COOLING_SOURCE,
    DORMANT_SOURCE,
    MAX_SIGNALS,
    UNANSWERED_SOURCE,
    WARM_PATH_SOURCE,
    FollowUpDeriver,
)
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

OWNER_ID = "owner-signals"
SELF_ID = "person-self"
TIMEZONE = "Asia/Dubai"
NOW = datetime.now(UTC)


@pytest.fixture
def session(settings: Settings) -> Iterator[Session]:
    database = Database(settings)
    Base.metadata.create_all(database.engine)
    with database.session_factory() as active:
        active.add(
            Owner(
                id=OWNER_ID,
                display_name="Alex Ivanov",
                email="alex@example.test",
                timezone=TIMEZONE,
                self_person_id=SELF_ID,
            )
        )
        active.add(Person(id=SELF_ID, owner_id=OWNER_ID, display_name="Alex Ivanov"))
        active.commit()
        yield active


def add_person(
    session: Session,
    person_id: str,
    display_name: str,
    *,
    title: str | None = "VP Product",
    org_id: str | None = None,
    data_origin: str = "synthetic",
) -> Person:
    person = Person(
        id=person_id,
        owner_id=OWNER_ID,
        display_name=display_name,
        current_title=title,
        current_org_id=org_id,
        data_origin=data_origin,
    )
    session.add(person)
    session.commit()
    return person


def add_relationship(
    session: Session,
    person_id: str,
    *,
    strength: float,
    days_ago: int,
    status: str = "active",
    total: int = 18,
) -> Relationship:
    relationship = Relationship(
        id=f"rel-{person_id}",
        owner_id=OWNER_ID,
        person_a_id=SELF_ID,
        person_b_id=person_id,
        strength_score=strength,
        status=status,
        last_interaction_at=NOW - timedelta(days=days_ago),
        total_interactions=total,
    )
    session.add(relationship)
    session.commit()
    return relationship


def add_interaction(
    session: Session,
    interaction_id: str,
    person_id: str,
    *,
    days_ago: int,
    direction: str = "incoming",
    subject: str | None = "TOKEN2049 follow-up",
    data_origin: str = "synthetic",
) -> InteractionEvent:
    event = InteractionEvent(
        id=interaction_id,
        owner_id=OWNER_ID,
        external_id=f"ext-{interaction_id}",
        type="message",
        source="linkedin",
        direction=direction,
        occurred_at=NOW - timedelta(days=days_ago),
        subject=subject,
        body_text="Salary numbers that must never reach a follow-up reason.",
        data_origin=data_origin,
    )
    session.add(event)
    for index, participant in enumerate((person_id, SELF_ID)):
        session.add(
            InteractionParticipant(
                id=f"part-{interaction_id}-{index}",
                owner_id=OWNER_ID,
                interaction_id=interaction_id,
                person_id=participant,
                source_address=f"{participant}@example.test",
                role="sender" if index == 0 else "recipient",
            )
        )
    session.commit()
    return event


def add_warm_path(
    session: Session,
    person_id: str,
    *,
    key: str = "binance",
    score: float = 0.9,
    saved: bool = False,
    dismissed: bool = False,
) -> Opportunity:
    session.add(
        Organization(id=f"org-{key}", owner_id=OWNER_ID, name="Binance", domain=f"{key}.com")
    )
    opportunity = Opportunity(
        id=f"opp-{key}",
        owner_id=OWNER_ID,
        organization_id=f"org-{key}",
        canonical_url=f"https://{key}.com/careers/product-manager",
        source_domain=f"{key}.com",
        role_title="Product Manager",
        location="Dubai, UAE",
        verification_status="verified_open_role",
        checked_at=NOW - timedelta(days=1),
        saved_at=NOW if saved else None,
        dismissed_at=NOW if dismissed else None,
        provider="synthetic_demo",
    )
    session.add(opportunity)
    session.flush()
    session.add(
        OpportunityPersonPath(
            id=f"path-{key}-{person_id}",
            owner_id=OWNER_ID,
            opportunity_id=opportunity.id,
            person_id=person_id,
            relationship_id=None,
            path_type="direct",
            path_score=score,
            rationale="Derived from the stored graph.",
            suggested_action="Ask who owns the role.",
        )
    )
    session.commit()
    return opportunity


def deriver(session: Session, demo_mode: bool = True) -> FollowUpDeriver:
    return FollowUpDeriver(session, OWNER_ID, demo_mode)


def follow_ups(session: Session) -> list[FollowUp]:
    return list(
        session.scalars(
            select(FollowUp).where(FollowUp.owner_id == OWNER_ID).order_by(FollowUp.source_key)
        )
    )


def sources(session: Session) -> set[str]:
    return {row.source for row in follow_ups(session)}


def test_cooling_relationship_fires_for_a_strong_but_quiet_edge(session: Session) -> None:
    add_person(session, "person-marta", "Marta", title="VP Product, Binance")
    add_relationship(session, "person-marta", strength=0.9, days_ago=200)

    assert deriver(session).derive() == 1

    row = follow_ups(session)[0]
    assert row.source == COOLING_SOURCE
    assert row.source_key == "person-marta"
    assert row.priority == 9
    assert row.status == "pending"
    assert row.due_timezone == TIMEZONE
    assert row.due_date == (NOW - timedelta(days=200)).date() + timedelta(days=90)
    assert "Marta" in row.reason
    assert "0.90" in row.reason
    assert "200 days ago" in row.reason


def test_cooling_relationship_stays_quiet_when_recent_or_weak(session: Session) -> None:
    add_person(session, "person-recent", "Recent Contact")
    add_relationship(session, "person-recent", strength=0.95, days_ago=30)
    add_person(session, "person-weak", "Weak Contact")
    add_relationship(session, "person-weak", strength=0.4, days_ago=400)

    assert deriver(session).derive() == 0
    assert follow_ups(session) == []


def test_warm_path_fires_for_an_untouched_opportunity(session: Session) -> None:
    add_person(session, "person-john", "John", title="Investor, digital assets")
    add_warm_path(session, "person-john", score=0.9)

    assert deriver(session).derive() == 1

    row = follow_ups(session)[0]
    assert row.source == WARM_PATH_SOURCE
    assert row.source_key == "opp-binance:person-john"
    assert row.priority == 19
    assert "John" in row.reason
    assert "Investor, digital assets" in row.reason
    assert "Binance" in row.reason
    assert "Product Manager" in row.reason
    assert row.due_date == (NOW - timedelta(days=1)).date() + timedelta(days=3)


def test_warm_path_stays_quiet_for_saved_or_dismissed_opportunities(session: Session) -> None:
    add_person(session, "person-saved", "Saved Contact")
    add_warm_path(session, "person-saved", key="rain", saved=True)
    add_person(session, "person-gone", "Dismissed Contact")
    add_warm_path(session, "person-gone", key="okx", dismissed=True)

    assert deriver(session).derive() == 0
    assert follow_ups(session) == []


def test_unanswered_message_fires_when_they_wrote_last(session: Session) -> None:
    add_person(session, "person-sergey", "Sergey Lapin", title="CTO")
    add_interaction(session, "int-sergey", "person-sergey", days_ago=40)

    assert deriver(session).derive() == 1

    row = follow_ups(session)[0]
    assert row.source == UNANSWERED_SOURCE
    assert row.source_key == "person-sergey"
    assert "Sergey Lapin" in row.reason
    assert "TOKEN2049 follow-up" in row.reason
    assert "linkedin" in row.reason
    assert "Salary" not in row.reason
    assert row.due_date == (NOW - timedelta(days=40)).date() + timedelta(days=14)


def test_unanswered_message_stays_quiet_when_answered_or_fresh(session: Session) -> None:
    add_person(session, "person-answered", "Answered Contact")
    add_interaction(session, "int-in", "person-answered", days_ago=40)
    add_interaction(session, "int-out", "person-answered", days_ago=20, direction="outgoing")
    add_person(session, "person-fresh", "Fresh Contact")
    add_interaction(session, "int-fresh", "person-fresh", days_ago=3)

    assert deriver(session).derive() == 0
    assert follow_ups(session) == []


def test_dormant_contact_fires_only_with_real_reciprocal_history(session: Session) -> None:
    add_person(session, "person-nadia", "Nadia", title="Growth advisor")
    add_relationship(session, "person-nadia", strength=0.2, days_ago=500, status="cold", total=11)
    add_person(session, "person-thin", "Thin Contact")
    add_relationship(session, "person-thin", strength=0.2, days_ago=500, status="cold", total=2)

    assert deriver(session).derive() == 1

    row = follow_ups(session)[0]
    assert row.source == DORMANT_SOURCE
    assert row.source_key == "person-nadia"
    assert row.priority == 1
    assert "Nadia" in row.reason
    assert "11 recorded interactions" in row.reason
    assert row.due_date == (NOW - timedelta(days=500)).date() + timedelta(days=365)


def test_deriving_twice_updates_the_same_rows(session: Session) -> None:
    add_person(session, "person-marta", "Marta")
    add_relationship(session, "person-marta", strength=0.9, days_ago=200)
    add_person(session, "person-john", "John")
    add_warm_path(session, "person-john")
    add_interaction(session, "int-john", "person-john", days_ago=40)
    add_person(session, "person-nadia", "Nadia")
    add_relationship(session, "person-nadia", strength=0.2, days_ago=500, status="cold", total=11)

    first = deriver(session).derive()
    ids = {row.id for row in follow_ups(session)}
    second = deriver(session).derive()

    assert first == 4
    assert second == 4
    assert sources(session) == {
        COOLING_SOURCE,
        WARM_PATH_SOURCE,
        UNANSWERED_SOURCE,
        DORMANT_SOURCE,
    }
    assert {row.id for row in follow_ups(session)} == ids
    assert len(follow_ups(session)) == 4


def test_a_completed_signal_is_never_recreated(session: Session) -> None:
    add_person(session, "person-marta", "Marta")
    add_relationship(session, "person-marta", strength=0.9, days_ago=200)
    deriver(session).derive()
    done = follow_ups(session)[0]
    done.status = "done"
    done.reason = "Handled offline"
    session.commit()

    assert deriver(session).derive() == 0

    rows = follow_ups(session)
    assert len(rows) == 1
    assert rows[0].status == "done"
    assert rows[0].reason == "Handled offline"


def test_manual_follow_ups_are_left_untouched(session: Session) -> None:
    add_person(session, "person-marta", "Marta")
    add_relationship(session, "person-marta", strength=0.9, days_ago=200)
    session.add(
        FollowUp(
            id="manual-1",
            owner_id=OWNER_ID,
            person_id="person-marta",
            reason="My own note",
            due_date=None,
            due_timezone=None,
            source="manual",
            source_key="person-marta",
            priority=3,
            status="pending",
        )
    )
    session.commit()

    assert deriver(session).derive() == 1

    manual = session.get(FollowUp, "manual-1")
    assert manual.reason == "My own note"
    assert manual.priority == 3
    assert manual.due_date is None
    assert manual.source_key == "person-marta"
    assert len(follow_ups(session)) == 2


def test_output_is_capped_to_the_highest_priority_signals(session: Session) -> None:
    for index in range(MAX_SIGNALS + 6):
        person_id = f"person-warm-{index:02d}"
        add_person(session, person_id, f"Warm Contact {index}")
        add_warm_path(session, person_id, key=f"opp{index:02d}", score=0.9)
    for index in range(5):
        person_id = f"person-cold-{index:02d}"
        add_person(session, person_id, f"Cold Contact {index}")
        add_relationship(session, person_id, strength=0.2, days_ago=500, status="dormant", total=11)

    assert deriver(session).derive() == MAX_SIGNALS

    rows = follow_ups(session)
    assert len(rows) == MAX_SIGNALS
    assert {row.source for row in rows} == {WARM_PATH_SOURCE}
    assert {row.priority for row in rows} == {19}


def test_demo_mode_ignores_imported_people(session: Session) -> None:
    add_person(session, "person-real", "Imported Contact", data_origin="real_import")
    add_relationship(session, "person-real", strength=0.9, days_ago=200)

    assert deriver(session, demo_mode=True).derive() == 0
    assert deriver(session, demo_mode=False).derive() == 1


def test_signals_screen_derives_when_the_owner_has_no_follow_ups(
    client: TestClient, auth: dict[str, str]
) -> None:
    for item in client.get("/api/followups", headers=auth).json()["follow_ups"]:
        assert client.delete(f"/api/followups/{item['id']}", headers=auth).status_code == 200

    listed = client.get("/api/followups?status=pending&sort=due_date", headers=auth)
    rows = listed.json()["follow_ups"]

    assert listed.status_code == 200
    assert rows
    for row in rows:
        assert row["person"]["display_name"]
        assert row["reason"]
        assert isinstance(row["priority"], int)
        assert row["source"] in {
            COOLING_SOURCE,
            WARM_PATH_SOURCE,
            UNANSWERED_SOURCE,
            DORMANT_SOURCE,
        }


def test_derive_endpoint_reports_the_resulting_status_counts(
    client: TestClient, auth: dict[str, str]
) -> None:
    response = client.post("/api/followups/derive", headers=auth)
    body = response.json()

    assert response.status_code == 200
    assert body["derived"] > 0
    assert body["status_counts"]["pending"] >= body["derived"]
    assert client.post("/api/followups/derive", headers=auth).json()["derived"] == body["derived"]
