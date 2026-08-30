"""Contracts for the derived semantic index.

PostgreSQL stays canonical. These ports let the import path enqueue work and the query path
retrieve evidence without either depending on a concrete vector store or embedding vendor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ChunkPayload:
    """One embedded chunk, shaped exactly as the Convex ``semanticChunks`` table expects."""

    chunk_key: str
    owner_id: str
    owner_scope: str
    interaction_id: str
    person_ids: tuple[str, ...]
    source: str
    occurred_at: int
    ordinal: int
    text: str
    text_hash: str
    citation_locator: str
    embedding_model: str
    embedding_version: str
    embedding: tuple[float, ...]

    def as_payload(self) -> dict[str, object]:
        return {
            "chunk_key": self.chunk_key,
            "owner_id": self.owner_id,
            "owner_scope": self.owner_scope,
            "interaction_id": self.interaction_id,
            "person_ids": list(self.person_ids),
            "source": self.source,
            "occurred_at": self.occurred_at,
            "ordinal": self.ordinal,
            "text": self.text,
            "text_hash": self.text_hash,
            "citation_locator": self.citation_locator,
            "embedding_model": self.embedding_model,
            "embedding_version": self.embedding_version,
            "embedding": list(self.embedding),
        }


@dataclass(frozen=True, slots=True)
class SemanticHit:
    chunk_key: str
    interaction_id: str
    person_ids: tuple[str, ...]
    source: str
    occurred_at: int
    text: str
    citation_locator: str
    score: float


@dataclass(frozen=True, slots=True)
class IndexResult:
    chunks_written: int
    interactions_indexed: int
    failures: tuple[str, ...] = field(default_factory=tuple)


class EmbeddingPort(Protocol):
    def embed(self, texts: list[str]) -> list[tuple[float, ...]]:
        """Return one vector per input, in the same order."""

    @property
    def model(self) -> str:
        """Identifier persisted alongside every chunk for reindex bookkeeping."""


class SemanticStorePort(Protocol):
    def upsert(self, chunks: list[ChunkPayload]) -> int:
        """Idempotently write chunks; returns how many rows actually changed."""

    def tombstone(self, owner_id: str, interaction_id: str) -> int:
        """Deactivate every chunk for one interaction; returns how many were affected."""

    def search(
        self,
        vector: tuple[float, ...],
        owner_id: str,
        embedding_version: str,
        sources: list[str] | None = None,
        limit: int = 32,
    ) -> list[SemanticHit]:
        """Owner-scoped vector search over active chunks only."""


def owner_scope(owner_id: str, embedding_version: str) -> str:
    """Composite filter value the Convex vector index is partitioned by."""

    return f"{owner_id}:{embedding_version}:active"
