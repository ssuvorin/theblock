from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime

import pytest
from app.config import Settings
from app.database import Database
from app.domain.semantic import ChunkPayload, SemanticHit
from app.models import (
    Base,
    InteractionEvent,
    InteractionParticipant,
    Owner,
    Person,
    SemanticIndexOutbox,
)
from app.repositories.semantic_outbox import MAX_ERROR_CHARS, SemanticOutboxRepository
from app.services.chunking import chunk_interaction
from app.services.semantic_index import SemanticIndexer, SemanticIndexError, epoch_millis
from sqlalchemy import select
from sqlalchemy.orm import Session

OWNER_ID = "owner-index"
PERSON_ID = "person-dana"
OTHER_PERSON_ID = "person-sam"
SHORT_BODY = "Thanks for the intro, let us talk next week."
LONG_BODY = ("alpha " * 500).strip() + "\n\n" + ("beta " * 500).strip()
OCCURRED_AT = datetime(2024, 3, 1, 12, 30, tzinfo=UTC)


class FakeEmbeddings:
    """Deterministic offline stand-in for :class:`app.domain.semantic.EmbeddingPort`."""

    def __init__(self, dimensions: int, error: str | None = None) -> None:
        self.calls: list[list[str]] = []
        self._dimensions = dimensions
        self._error = error

    @property
    def model(self) -> str:
        return "fake/embedding-1"

    def embed(self, texts: list[str]) -> list[tuple[float, ...]]:
        self.calls.append(list(texts))
        if self._error:
            raise RuntimeError(self._error)
        return [(float(len(text)),) * self._dimensions for text in texts]


class FakeStore:
    """Records every write so the tests can assert batching without any network."""

    def __init__(
        self,
        failing: set[str] | None = None,
        error: str = "convex rejected the batch",
        hits: Sequence[SemanticHit] = (),
        search_error: str | None = None,
    ) -> None:
        self.upserts: list[list[ChunkPayload]] = []
        self.tombstones: list[tuple[str, str]] = []
        self.searches: list[tuple] = []
        self._failing = failing or set()
        self._error = error
        self._hits = list(hits)
        self._search_error = search_error

    @property
    def written(self) -> list[ChunkPayload]:
        return [payload for batch in self.upserts for payload in batch]

    def upsert(self, chunks: list[ChunkPayload]) -> int:
        if any(chunk.interaction_id in self._failing for chunk in chunks):
            raise RuntimeError(self._error)
        self.upserts.append(list(chunks))
        return len(chunks)

    def tombstone(self, owner_id: str, interaction_id: str) -> int:
        self.tombstones.append((owner_id, interaction_id))
        return 1

    def search(
        self,
        vector: tuple[float, ...],
        owner_id: str,
        embedding_version: str,
        sources: list[str] | None = None,
        limit: int = 32,
    ) -> list[SemanticHit]:
        self.searches.append((vector, owner_id, embedding_version, sources, limit))
        if self._search_error:
            raise RuntimeError(self._search_error)
        return list(self._hits)


@pytest.fixture
def index_settings(settings: Settings) -> Settings:
    return Settings(
        **{**settings.model_dump(), "database_url": "sqlite://", "seed_demo_data": False}
    )


@pytest.fixture
def session(index_settings: Settings) -> Iterator[Session]:
    database = Database(index_settings)
    Base.metadata.create_all(database.engine)
    with database.session_factory() as active:
        active.add(Owner(id=OWNER_ID, display_name="Alex Ivanov", email="alex@example.test"))
        active.add(Person(id=PERSON_ID, owner_id=OWNER_ID, display_name="Dana Lee"))
        active.add(Person(id=OTHER_PERSON_ID, owner_id=OWNER_ID, display_name="Sam Cole"))
        active.commit()
        yield active


def add_interaction(
    session: Session,
    interaction_id: str,
    body_text: str | None = SHORT_BODY,
    *,
    minute: int = 30,
    source: str = "linkedin",
    is_deleted: bool = False,
    metadata: dict | None = None,
    person_ids: Sequence[str | None] = (PERSON_ID,),
) -> InteractionEvent:
    interaction = InteractionEvent(
        id=interaction_id,
        owner_id=OWNER_ID,
        external_id=f"ext-{interaction_id}",
        type="message",
        source=source,
        direction="incoming",
        occurred_at=datetime(2024, 3, 1, 12, minute, tzinfo=UTC),
        subject=None,
        body_text=body_text,
        metadata_json=metadata or {},
        content_version=1,
        is_deleted=is_deleted,
        data_origin="synthetic",
    )
    session.add(interaction)
    for index, person_id in enumerate(person_ids):
        session.add(
            InteractionParticipant(
                owner_id=OWNER_ID,
                interaction_id=interaction_id,
                person_id=person_id,
                source_address=f"addr-{index}@example.test",
                role="sender" if index == 0 else f"recipient-{index}",
            )
        )
    session.commit()
    return interaction


def make_indexer(
    session: Session,
    settings: Settings,
    embeddings: FakeEmbeddings,
    store: FakeStore,
) -> SemanticIndexer:
    return SemanticIndexer(session, OWNER_ID, embeddings, store, settings)


def outbox_rows(session: Session) -> list[SemanticIndexOutbox]:
    return list(
        session.scalars(select(SemanticIndexOutbox).order_by(SemanticIndexOutbox.created_at))
    )


def expected_chunks(interaction_id: str, body_text: str) -> int:
    return len(chunk_interaction(interaction_id, 1, body_text))


def test_drain_writes_chunks_and_marks_rows_done(
    session: Session, index_settings: Settings
) -> None:
    add_interaction(session, "int-short", SHORT_BODY)
    add_interaction(session, "int-long", LONG_BODY, minute=31)
    embeddings = FakeEmbeddings(index_settings.embedding_dimensions)
    store = FakeStore()
    indexer = make_indexer(session, index_settings, embeddings, store)
    indexer.enqueue_owner_interactions()

    result = indexer.drain()
    session.commit()

    short_count = expected_chunks("int-short", SHORT_BODY)
    long_count = expected_chunks("int-long", LONG_BODY)
    assert long_count > 1
    assert result.interactions_indexed == 2
    assert result.chunks_written == short_count + long_count
    assert result.failures == ()
    assert {row.interaction_id: row.chunks_written for row in outbox_rows(session)} == {
        "int-short": short_count,
        "int-long": long_count,
    }
    assert {row.status for row in outbox_rows(session)} == {"done"}
    assert all(row.processed_at is not None for row in outbox_rows(session))
    assert len(store.written) == short_count + long_count


def test_empty_body_is_marked_done_without_any_embedding_call(
    session: Session, index_settings: Settings
) -> None:
    add_interaction(session, "int-empty", "   \n\n  ")
    add_interaction(session, "int-none", None, minute=31)
    embeddings = FakeEmbeddings(index_settings.embedding_dimensions)
    store = FakeStore()
    indexer = make_indexer(session, index_settings, embeddings, store)
    indexer.enqueue_owner_interactions()

    result = indexer.drain()
    session.commit()

    assert embeddings.calls == []
    assert store.upserts == []
    assert result.chunks_written == 0
    assert result.interactions_indexed == 2
    assert [row.status for row in outbox_rows(session)] == ["done", "done"]
    assert [row.chunks_written for row in outbox_rows(session)] == [0, 0]


def test_deleted_interaction_is_tombstoned_instead_of_indexed(
    session: Session, index_settings: Settings
) -> None:
    add_interaction(session, "int-gone", LONG_BODY)
    embeddings = FakeEmbeddings(index_settings.embedding_dimensions)
    store = FakeStore()
    indexer = make_indexer(session, index_settings, embeddings, store)
    SemanticOutboxRepository(session, OWNER_ID).enqueue_upsert(
        ["int-gone"], index_settings.embedding_version
    )
    interaction = session.get(InteractionEvent, "int-gone")
    interaction.is_deleted = True
    session.commit()

    result = indexer.drain()
    session.commit()

    assert store.tombstones == [(OWNER_ID, "int-gone")]
    assert store.upserts == []
    assert embeddings.calls == []
    assert result.chunks_written == 0
    assert result.interactions_indexed == 1
    assert outbox_rows(session)[0].status == "done"


def test_missing_interaction_is_tombstoned_and_settled(
    session: Session, index_settings: Settings
) -> None:
    add_interaction(session, "int-vanished", SHORT_BODY)
    store = FakeStore()
    embeddings = FakeEmbeddings(index_settings.embedding_dimensions)
    indexer = make_indexer(session, index_settings, embeddings, store)
    indexer.enqueue_owner_interactions()
    session.delete(session.get(InteractionEvent, "int-vanished"))
    session.commit()

    result = indexer.drain()
    session.commit()

    assert store.tombstones == [(OWNER_ID, "int-vanished")]
    assert result.interactions_indexed == 1
    assert outbox_rows(session)[0].status == "done"


def test_explicit_tombstone_row_calls_the_store_and_settles(
    session: Session, index_settings: Settings
) -> None:
    add_interaction(session, "int-1", SHORT_BODY)
    store = FakeStore()
    embeddings = FakeEmbeddings(index_settings.embedding_dimensions)
    indexer = make_indexer(session, index_settings, embeddings, store)
    SemanticOutboxRepository(session, OWNER_ID).enqueue_tombstone(
        "int-1", index_settings.embedding_version
    )
    session.commit()

    result = indexer.drain()
    session.commit()

    assert store.tombstones == [(OWNER_ID, "int-1")]
    assert embeddings.calls == []
    assert result.interactions_indexed == 1
    assert outbox_rows(session)[0].chunks_written == 0


def test_failing_store_fails_one_row_and_the_drain_keeps_going(
    session: Session, index_settings: Settings
) -> None:
    add_interaction(session, "int-ok", SHORT_BODY)
    add_interaction(session, "int-bad", LONG_BODY, minute=31)
    add_interaction(session, "int-also-ok", SHORT_BODY, minute=32)
    embeddings = FakeEmbeddings(index_settings.embedding_dimensions)
    store = FakeStore(failing={"int-bad"}, error="convex rejected the batch " * 40)
    indexer = make_indexer(session, index_settings, embeddings, store)
    indexer.enqueue_owner_interactions()

    result = indexer.drain()
    session.commit()

    by_id = {row.interaction_id: row for row in outbox_rows(session)}
    assert by_id["int-bad"].status == "failed"
    assert by_id["int-bad"].attempts == 1
    assert len(by_id["int-bad"].last_error) == MAX_ERROR_CHARS
    assert by_id["int-ok"].status == "done"
    assert by_id["int-also-ok"].status == "done"
    assert result.interactions_indexed == 2
    assert result.failures == (f"int-bad: {by_id['int-bad'].last_error[:MAX_ERROR_CHARS]}",)
    assert {payload.interaction_id for payload in store.written} == {"int-ok", "int-also-ok"}


def test_embedding_failure_fails_the_claim_without_writing(
    session: Session, index_settings: Settings
) -> None:
    add_interaction(session, "int-1", SHORT_BODY)
    embeddings = FakeEmbeddings(index_settings.embedding_dimensions, error="provider is down")
    store = FakeStore()
    indexer = make_indexer(session, index_settings, embeddings, store)
    indexer.enqueue_owner_interactions()

    result = indexer.drain()
    session.commit()

    row = outbox_rows(session)[0]
    assert store.upserts == []
    assert row.status == "failed"
    assert row.attempts == 1
    assert row.last_error == "provider is down"
    assert result.chunks_written == 0
    assert result.interactions_indexed == 0
    assert result.failures == ("int-1: provider is down",)


def test_draining_twice_claims_nothing_the_second_time(
    session: Session, index_settings: Settings
) -> None:
    add_interaction(session, "int-1", SHORT_BODY)
    add_interaction(session, "int-2", SHORT_BODY, minute=31)
    embeddings = FakeEmbeddings(index_settings.embedding_dimensions)
    store = FakeStore()
    indexer = make_indexer(session, index_settings, embeddings, store)
    indexer.enqueue_owner_interactions()

    first = indexer.drain()
    second = indexer.drain()
    session.commit()

    assert first.interactions_indexed == 2
    assert second.interactions_indexed == 0
    assert second.chunks_written == 0
    assert second.failures == ()
    assert len(embeddings.calls) == 1
    assert len(store.upserts) == 1


def test_embeddings_are_batched_into_one_call_per_claim(
    session: Session, index_settings: Settings
) -> None:
    for index in range(5):
        add_interaction(session, f"int-{index}", LONG_BODY, minute=30 + index)
    embeddings = FakeEmbeddings(index_settings.embedding_dimensions)
    store = FakeStore()
    indexer = make_indexer(session, index_settings, embeddings, store)
    indexer.enqueue_owner_interactions()

    result = indexer.drain(limit=50)
    session.commit()

    total = 5 * expected_chunks("int-0", LONG_BODY)
    assert len(embeddings.calls) == 1
    assert len(embeddings.calls[0]) == total
    assert len(store.upserts) == 1
    assert result.chunks_written == total


def test_chunk_payload_carries_owner_scope_and_epoch_millis(
    session: Session, index_settings: Settings
) -> None:
    add_interaction(
        session,
        "int-1",
        SHORT_BODY,
        metadata={"citation_locator": "message#7"},
        person_ids=(PERSON_ID, PERSON_ID, None, OTHER_PERSON_ID),
    )
    embeddings = FakeEmbeddings(index_settings.embedding_dimensions)
    store = FakeStore()
    indexer = make_indexer(session, index_settings, embeddings, store)
    indexer.enqueue_owner_interactions()

    indexer.drain()
    session.commit()

    payload = store.written[0]
    chunk = chunk_interaction("int-1", 1, SHORT_BODY)[0]
    assert payload.owner_scope == f"{OWNER_ID}:{index_settings.embedding_version}:active"
    assert payload.occurred_at == int(OCCURRED_AT.timestamp() * 1000)
    assert isinstance(payload.occurred_at, int)
    assert payload.person_ids == (PERSON_ID, OTHER_PERSON_ID)
    assert payload.source == "linkedin"
    assert payload.citation_locator == "message#7"
    assert payload.embedding_model == "fake/embedding-1"
    assert payload.embedding_version == index_settings.embedding_version
    assert payload.chunk_key == chunk.chunk_key
    assert payload.text == chunk.text
    assert payload.text_hash == chunk.text_hash
    assert payload.ordinal == 0
    assert len(payload.embedding) == index_settings.embedding_dimensions
    assert payload.as_payload()["owner_scope"] == payload.owner_scope


def test_citation_locator_defaults_to_body(session: Session, index_settings: Settings) -> None:
    add_interaction(session, "int-1", SHORT_BODY, metadata={})
    embeddings = FakeEmbeddings(index_settings.embedding_dimensions)
    store = FakeStore()
    indexer = make_indexer(session, index_settings, embeddings, store)
    indexer.enqueue_owner_interactions()

    indexer.drain()

    assert store.written[0].citation_locator == "body"


def test_epoch_millis_treats_a_naive_datetime_as_utc() -> None:
    naive = datetime(2024, 3, 1, 12, 30)

    assert epoch_millis(naive) == epoch_millis(OCCURRED_AT)
    assert epoch_millis(datetime(1970, 1, 1, 0, 0, 0, 250_000, tzinfo=UTC)) == 250


def test_enqueue_owner_interactions_skips_deleted_and_honours_sources(
    session: Session, index_settings: Settings
) -> None:
    add_interaction(session, "int-linkedin", SHORT_BODY)
    add_interaction(session, "int-email", SHORT_BODY, minute=31, source="email")
    add_interaction(session, "int-deleted", SHORT_BODY, minute=32, is_deleted=True)
    embeddings = FakeEmbeddings(index_settings.embedding_dimensions)
    indexer = make_indexer(session, index_settings, embeddings, FakeStore())

    enqueued = indexer.enqueue_owner_interactions(["linkedin"])
    session.commit()

    assert enqueued == 1
    assert [row.interaction_id for row in outbox_rows(session)] == ["int-linkedin"]
    assert indexer.enqueue_owner_interactions() == 1
    assert {row.interaction_id for row in outbox_rows(session)} == {"int-linkedin", "int-email"}


def test_search_embeds_the_query_and_delegates_to_the_store(
    session: Session, index_settings: Settings
) -> None:
    hit = SemanticHit(
        chunk_key="key-1",
        interaction_id="int-1",
        person_ids=(PERSON_ID,),
        source="linkedin",
        occurred_at=epoch_millis(OCCURRED_AT),
        text=SHORT_BODY,
        citation_locator="body",
        score=0.82,
    )
    embeddings = FakeEmbeddings(index_settings.embedding_dimensions)
    store = FakeStore(hits=[hit])
    indexer = make_indexer(session, index_settings, embeddings, store)

    hits = indexer.search("who can introduce me?", sources=["linkedin"], limit=5)

    assert hits == [hit]
    assert embeddings.calls == [["who can introduce me?"]]
    vector, owner_id, version, sources, limit = store.searches[0]
    assert len(vector) == index_settings.embedding_dimensions
    assert owner_id == OWNER_ID
    assert version == index_settings.embedding_version
    assert sources == ["linkedin"]
    assert limit == 5


def test_blank_search_query_never_touches_the_provider(
    session: Session, index_settings: Settings
) -> None:
    embeddings = FakeEmbeddings(index_settings.embedding_dimensions)
    store = FakeStore()
    indexer = make_indexer(session, index_settings, embeddings, store)

    assert indexer.search("   ") == []
    assert embeddings.calls == []
    assert store.searches == []


def test_search_raises_instead_of_faking_zero_hits(
    session: Session, index_settings: Settings
) -> None:
    broken_embeddings = FakeEmbeddings(index_settings.embedding_dimensions, error="provider down")
    with pytest.raises(SemanticIndexError):
        make_indexer(session, index_settings, broken_embeddings, FakeStore()).search("intro")

    broken_store = FakeStore(search_error="convex vector index missing")
    embeddings = FakeEmbeddings(index_settings.embedding_dimensions)
    with pytest.raises(SemanticIndexError) as error:
        make_indexer(session, index_settings, embeddings, broken_store).search("intro")

    assert "convex vector index missing" in str(error.value)
