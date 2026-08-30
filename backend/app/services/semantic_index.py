"""Drain the semantic outbox into the derived vector index.

The loop is at-least-once: rows are claimed, reconciled with the store, then settled. A
single bad interaction fails its own row and the rest of the claim still lands, and empty
messages never reach the embedding provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.semantic import (
    ChunkPayload,
    EmbeddingPort,
    IndexResult,
    SemanticHit,
    SemanticStorePort,
    owner_scope,
)
from app.models import InteractionEvent, SemanticIndexOutbox
from app.repositories.semantic_outbox import (
    OP_TOMBSTONE,
    SemanticOutboxRepository,
    SemanticSourceRepository,
    truncate_error,
)
from app.services.chunking import TextChunk, chunk_interaction

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
DEFAULT_CITATION_LOCATOR = "body"


class SemanticIndexError(RuntimeError):
    """Raised when the semantic index cannot serve a request."""


def epoch_millis(moment: datetime) -> int:
    """Convert a datetime to epoch milliseconds; a naive value is treated as UTC."""

    aware = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
    delta = aware - _EPOCH
    return delta.days * 86_400_000 + delta.seconds * 1_000 + delta.microseconds // 1_000


@dataclass(frozen=True, slots=True)
class _PendingUpsert:
    row: SemanticIndexOutbox
    interaction: InteractionEvent
    chunks: tuple[TextChunk, ...]
    person_ids: tuple[str, ...]


class SemanticIndexer:
    """Compose the outbox, the chunker, an embedding provider, and a vector store."""

    def __init__(
        self,
        session: Session,
        owner_id: str,
        embeddings: EmbeddingPort,
        store: SemanticStorePort,
        settings: Settings,
    ) -> None:
        self._owner_id = owner_id
        self._embeddings = embeddings
        self._store = store
        self._settings = settings
        self._outbox = SemanticOutboxRepository(session, owner_id)
        self._source = SemanticSourceRepository(session, owner_id)

    @property
    def embedding_version(self) -> str:
        return self._settings.embedding_version

    def enqueue_owner_interactions(self, sources: list[str] | None = None) -> int:
        """Queue every non-deleted interaction of this owner for a full reindex."""

        ids = self._source.interaction_ids(sources)
        return self._outbox.enqueue_upsert(ids, self.embedding_version)

    def drain(self, limit: int = 50) -> IndexResult:
        """Claim up to ``limit`` outbox rows and reconcile them with the store.

        ``interactions_indexed`` counts every row settled as done, tombstones included;
        ``chunks_written`` counts the chunks handed to the store; ``failures`` holds one
        ``"{interaction_id}: {reason}"`` entry per row left failed.
        """

        rows = self._outbox.claim(limit)
        if not rows:
            return IndexResult(chunks_written=0, interactions_indexed=0)
        interactions = self._source.interactions_by_id(
            [row.interaction_id for row in rows if row.op != OP_TOMBSTONE]
        )
        person_ids = self._source.person_ids_by_interaction(list(interactions))
        failures: list[str] = []
        settled = 0
        pending: list[_PendingUpsert] = []
        for row in rows:
            interaction = interactions.get(row.interaction_id)
            if row.op == OP_TOMBSTONE or interaction is None or interaction.is_deleted:
                settled += int(self._tombstone(row, failures))
                continue
            chunks = chunk_interaction(
                interaction.id, interaction.content_version, interaction.body_text
            )
            if not chunks:
                self._outbox.mark_done(row, 0)
                settled += 1
                continue
            pending.append(
                _PendingUpsert(row, interaction, chunks, person_ids.get(interaction.id, ()))
            )
        written, indexed, upsert_failures = self._flush(pending)
        return IndexResult(
            chunks_written=written,
            interactions_indexed=settled + indexed,
            failures=tuple(failures + upsert_failures),
        )

    def search(
        self,
        query_text: str,
        sources: list[str] | None = None,
        limit: int = 32,
    ) -> list[SemanticHit]:
        """Embed ``query_text`` and return owner-scoped hits over active chunks.

        A blank query returns ``[]`` without calling the provider. Failure is never
        disguised as "no evidence": if embedding or the store raises, this raises
        :class:`SemanticIndexError` (chained to the cause) so the caller can degrade
        deliberately instead of showing an empty, unlabelled result set.
        """

        text = (query_text or "").strip()
        if not text:
            return []
        try:
            vectors = self._embeddings.embed([text])
            if not vectors:
                raise SemanticIndexError("embedding provider returned no query vector")
            return self._store.search(
                vectors[0],
                self._owner_id,
                self.embedding_version,
                sources,
                limit,
            )
        except SemanticIndexError:
            raise
        except Exception as error:
            raise SemanticIndexError(f"semantic search unavailable: {error}") from error

    def _tombstone(self, row: SemanticIndexOutbox, failures: list[str]) -> bool:
        try:
            self._store.tombstone(self._owner_id, row.interaction_id)
        except Exception as error:
            self._fail(row, error, failures)
            return False
        self._outbox.mark_done(row, 0)
        return True

    def _fail(self, row: SemanticIndexOutbox, error: Exception, failures: list[str]) -> None:
        message = truncate_error(str(error) or error.__class__.__name__)
        self._outbox.mark_failed(row, message)
        failures.append(f"{row.interaction_id}: {message}")

    def _flush(self, pending: list[_PendingUpsert]) -> tuple[int, int, list[str]]:
        failures: list[str] = []
        if not pending:
            return 0, 0, failures
        texts = [chunk.text for unit in pending for chunk in unit.chunks]
        try:
            vectors = self._embed(texts)
        except Exception as error:
            for unit in pending:
                self._fail(unit.row, error, failures)
            return 0, 0, failures
        batches = self._build(pending, vectors)
        written, indexed = self._write(batches, failures)
        return written, indexed, failures

    def _embed(self, texts: list[str]) -> list[tuple[float, ...]]:
        vectors = list(self._embeddings.embed(texts))
        if len(vectors) != len(texts):
            raise SemanticIndexError(
                f"embedding provider returned {len(vectors)} vectors for {len(texts)} chunks"
            )
        return vectors

    def _build(
        self, pending: list[_PendingUpsert], vectors: list[tuple[float, ...]]
    ) -> list[tuple[SemanticIndexOutbox, list[ChunkPayload]]]:
        batches: list[tuple[SemanticIndexOutbox, list[ChunkPayload]]] = []
        cursor = 0
        for unit in pending:
            window = vectors[cursor : cursor + len(unit.chunks)]
            cursor += len(unit.chunks)
            payloads = [
                self._payload(unit, chunk, vector)
                for chunk, vector in zip(unit.chunks, window, strict=True)
            ]
            batches.append((unit.row, payloads))
        return batches

    def _payload(
        self, unit: _PendingUpsert, chunk: TextChunk, vector: tuple[float, ...]
    ) -> ChunkPayload:
        interaction = unit.interaction
        metadata = interaction.metadata_json or {}
        locator = metadata.get("citation_locator") or DEFAULT_CITATION_LOCATOR
        return ChunkPayload(
            chunk_key=chunk.chunk_key,
            owner_id=self._owner_id,
            owner_scope=owner_scope(self._owner_id, self.embedding_version),
            interaction_id=interaction.id,
            person_ids=unit.person_ids,
            source=interaction.source,
            occurred_at=epoch_millis(interaction.occurred_at),
            ordinal=chunk.ordinal,
            text=chunk.text,
            text_hash=chunk.text_hash,
            citation_locator=str(locator),
            embedding_model=self._embeddings.model,
            embedding_version=self.embedding_version,
            embedding=tuple(vector),
        )

    def _write(
        self,
        batches: list[tuple[SemanticIndexOutbox, list[ChunkPayload]]],
        failures: list[str],
    ) -> tuple[int, int]:
        """Write the whole claim in one call, isolating the culprit only when it fails."""

        chunks = [payload for _, payloads in batches for payload in payloads]
        try:
            self._store.upsert(chunks)
        except Exception:
            return self._write_individually(batches, failures)
        for row, payloads in batches:
            self._outbox.mark_done(row, len(payloads))
        return len(chunks), len(batches)

    def _write_individually(
        self,
        batches: list[tuple[SemanticIndexOutbox, list[ChunkPayload]]],
        failures: list[str],
    ) -> tuple[int, int]:
        written = 0
        indexed = 0
        for row, payloads in batches:
            try:
                self._store.upsert(payloads)
            except Exception as error:
                self._fail(row, error, failures)
                continue
            self._outbox.mark_done(row, len(payloads))
            written += len(payloads)
            indexed += 1
        return written, indexed
