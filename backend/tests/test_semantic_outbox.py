from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from app.config import Settings
from app.database import Database
from app.models import Base, InteractionEvent, Owner, SemanticIndexOutbox
from app.repositories.semantic_outbox import (
    MAX_ERROR_CHARS,
    SemanticOutboxRepository,
    SemanticSourceRepository,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

OWNER_ID = "owner-outbox"
VERSION = "v1"


@pytest.fixture
def session(settings: Settings) -> Iterator[Session]:
    database = Database(
        Settings(**{**settings.model_dump(), "database_url": "sqlite://", "seed_demo_data": False})
    )
    Base.metadata.create_all(database.engine)
    with database.session_factory() as active:
        active.add(Owner(id=OWNER_ID, display_name="Alex Ivanov", email="alex@example.test"))
        active.commit()
        yield active


def add_interaction(
    session: Session,
    interaction_id: str,
    *,
    minute: int = 0,
    source: str = "linkedin",
    is_deleted: bool = False,
) -> InteractionEvent:
    interaction = InteractionEvent(
        id=interaction_id,
        owner_id=OWNER_ID,
        external_id=f"ext-{interaction_id}",
        type="message",
        source=source,
        direction="incoming",
        occurred_at=datetime(2024, 3, 1, 12, minute, tzinfo=UTC),
        body_text="hello there",
        metadata_json={},
        is_deleted=is_deleted,
        data_origin="synthetic",
    )
    session.add(interaction)
    session.commit()
    return interaction


def rows(session: Session) -> list[SemanticIndexOutbox]:
    return list(
        session.scalars(select(SemanticIndexOutbox).order_by(SemanticIndexOutbox.created_at))
    )


def test_enqueue_upsert_is_idempotent_across_reimports(session: Session) -> None:
    add_interaction(session, "int-1")
    add_interaction(session, "int-2", minute=1)
    repository = SemanticOutboxRepository(session, OWNER_ID)

    created = repository.enqueue_upsert(["int-1", "int-2", "int-1"], VERSION)
    again = repository.enqueue_upsert(["int-1", "int-2"], VERSION)
    session.commit()

    assert created == 2
    assert again == 0
    assert [row.interaction_id for row in rows(session)] == ["int-1", "int-2"]
    assert {row.status for row in rows(session)} == {"pending"}
    assert {row.op for row in rows(session)} == {"upsert"}


def test_reenqueue_resets_a_done_row_to_pending(session: Session) -> None:
    add_interaction(session, "int-1")
    repository = SemanticOutboxRepository(session, OWNER_ID)
    repository.enqueue_upsert(["int-1"], VERSION)
    claimed = repository.claim(10)
    repository.mark_done(claimed[0], 3)
    session.commit()

    reset = repository.enqueue_upsert(["int-1"], VERSION)
    session.commit()

    row = rows(session)[0]
    assert reset == 1
    assert len(rows(session)) == 1
    assert row.status == "pending"
    assert row.chunks_written is None
    assert row.processed_at is None


def test_reenqueue_resets_a_failed_row_and_keeps_the_attempt_count(session: Session) -> None:
    add_interaction(session, "int-1")
    repository = SemanticOutboxRepository(session, OWNER_ID)
    repository.enqueue_upsert(["int-1"], VERSION)
    claimed = repository.claim(10)
    repository.mark_failed(claimed[0], "convex refused the mutation")
    session.commit()

    assert repository.enqueue_upsert(["int-1"], VERSION) == 1
    row = rows(session)[0]
    assert row.status == "pending"
    assert row.attempts == 1
    assert row.last_error is None


def test_tombstone_row_coexists_with_the_upsert_row(session: Session) -> None:
    add_interaction(session, "int-1")
    repository = SemanticOutboxRepository(session, OWNER_ID)

    repository.enqueue_upsert(["int-1"], VERSION)
    repository.enqueue_tombstone("int-1", VERSION)
    repository.enqueue_tombstone("int-1", VERSION)
    session.commit()

    assert sorted(row.op for row in rows(session)) == ["tombstone", "upsert"]


def test_claim_takes_pending_rows_oldest_first_and_marks_them_processing(
    session: Session,
) -> None:
    for index in range(3):
        add_interaction(session, f"int-{index}", minute=index)
    repository = SemanticOutboxRepository(session, OWNER_ID)
    repository.enqueue_upsert(["int-0", "int-1", "int-2"], VERSION)
    session.commit()

    first = repository.claim(2)
    session.commit()

    assert [row.interaction_id for row in first] == ["int-0", "int-1"]
    assert {row.status for row in first} == {"processing"}
    assert repository.pending_count() == 1

    second = repository.claim(2)
    assert [row.interaction_id for row in second] == ["int-2"]
    assert repository.claim(2) == []


def test_claim_rejects_non_positive_limits(session: Session) -> None:
    add_interaction(session, "int-1")
    repository = SemanticOutboxRepository(session, OWNER_ID)
    repository.enqueue_upsert(["int-1"], VERSION)

    assert repository.claim(0) == []
    assert repository.pending_count() == 1


def test_mark_failed_truncates_the_error_and_counts_attempts(session: Session) -> None:
    add_interaction(session, "int-1")
    repository = SemanticOutboxRepository(session, OWNER_ID)
    repository.enqueue_upsert(["int-1"], VERSION)
    row = repository.claim(1)[0]

    repository.mark_failed(row, "boom " * 400)
    session.commit()

    assert row.status == "failed"
    assert row.attempts == 1
    assert len(row.last_error) == MAX_ERROR_CHARS
    assert row.processed_at is not None


def test_status_counts_group_every_row_of_the_owner(session: Session) -> None:
    for index in range(3):
        add_interaction(session, f"int-{index}", minute=index)
    repository = SemanticOutboxRepository(session, OWNER_ID)
    repository.enqueue_upsert(["int-0", "int-1", "int-2"], VERSION)
    claimed = repository.claim(2)
    repository.mark_done(claimed[0], 2)
    repository.mark_failed(claimed[1], "store unavailable")
    session.commit()

    assert repository.status_counts() == {"pending": 1, "done": 1, "failed": 1}
    assert repository.pending_count() == 1


def test_enqueue_ignores_an_empty_id_list(session: Session) -> None:
    repository = SemanticOutboxRepository(session, OWNER_ID)

    assert repository.enqueue_upsert([], VERSION) == 0
    assert rows(session) == []


def test_a_different_embedding_version_gets_its_own_row(session: Session) -> None:
    add_interaction(session, "int-1")
    repository = SemanticOutboxRepository(session, OWNER_ID)

    repository.enqueue_upsert(["int-1"], VERSION)
    repository.enqueue_upsert(["int-1"], "v2")
    session.commit()

    assert sorted(row.embedding_version for row in rows(session)) == ["v1", "v2"]


def test_source_repository_lists_live_interactions_only(session: Session) -> None:
    add_interaction(session, "int-1")
    add_interaction(session, "int-2", minute=1, source="email")
    add_interaction(session, "int-3", minute=2, is_deleted=True)
    source = SemanticSourceRepository(session, OWNER_ID)

    assert source.interaction_ids() == ["int-1", "int-2"]
    assert source.interaction_ids(["email"]) == ["int-2"]
    assert set(source.interactions_by_id(["int-1", "int-missing"])) == {"int-1"}
