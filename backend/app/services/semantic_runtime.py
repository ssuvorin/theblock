"""Compose the semantic index from configuration, degrading honestly when unconfigured.

This is the only place that decides whether a real vector store is available, so no caller
has to re-derive that from settings and none can accidentally claim a capability the
deployment does not have.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import Settings, has_semantic_index
from app.connectors.convex.client import ConvexSemanticStore, NullSemanticStore
from app.domain.semantic import EmbeddingPort, SemanticStorePort
from app.repositories.semantic_outbox import SemanticOutboxRepository
from app.services.embeddings import NullEmbeddings, OpenRouterEmbeddings
from app.services.semantic_index import SemanticIndexer


@dataclass(frozen=True, slots=True)
class SemanticRuntime:
    """An indexer plus the honest answer to whether it can actually reach a provider."""

    indexer: SemanticIndexer
    outbox: SemanticOutboxRepository
    configured: bool

    @property
    def status(self) -> str:
        return "ready" if self.configured else "not_configured"


def build_adapters(settings: Settings) -> tuple[EmbeddingPort, SemanticStorePort, bool]:
    if has_semantic_index(settings):
        return OpenRouterEmbeddings(settings), ConvexSemanticStore(settings), True
    return NullEmbeddings(), NullSemanticStore(), False


def build_runtime(session: Session, owner_id: str, settings: Settings) -> SemanticRuntime:
    embeddings, store, configured = build_adapters(settings)
    return SemanticRuntime(
        indexer=SemanticIndexer(session, owner_id, embeddings, store, settings),
        outbox=SemanticOutboxRepository(session, owner_id),
        configured=configured,
    )


def index_snapshot(session: Session, owner_id: str, settings: Settings) -> dict[str, object]:
    """Report queue depth for the dependency read-out without contacting any provider."""

    runtime = build_runtime(session, owner_id, settings)
    return {
        "provider": "convex" if runtime.configured else "not_configured",
        "status": runtime.status,
        "embedding_model": settings.embedding_model if runtime.configured else None,
        "embedding_version": settings.embedding_version,
        "queue": runtime.outbox.status_counts(),
        "pending": runtime.outbox.pending_count(),
        "chunks": runtime.outbox.chunks_indexed(),
    }
