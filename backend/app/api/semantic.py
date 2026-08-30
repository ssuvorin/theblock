from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentOwner, DbSession, RuntimeSettings
from app.services.semantic_index import SemanticIndexError
from app.services.semantic_runtime import build_runtime, index_snapshot

router = APIRouter(prefix="/api/index", tags=["semantic index"])


@router.get("")
def index_status(owner: CurrentOwner, db: DbSession, settings: RuntimeSettings) -> dict:
    """Queue depth and provider state; never contacts Convex or OpenRouter."""

    return index_snapshot(db, owner.id, settings)


@router.post("/drain")
def drain_index(
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    """Embed and upload pending chunks. Retryable: the outbox keeps unfinished work."""

    runtime = build_runtime(db, owner.id, settings)
    if not runtime.configured:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Semantic index is not configured; set CONVEX_URL, "
                "CONVEX_DEPLOY_KEY and OPENROUTER_API_KEY"
            ),
        )
    result = runtime.indexer.drain(limit=limit)
    return {
        "chunks_written": result.chunks_written,
        "interactions_indexed": result.interactions_indexed,
        "failures": list(result.failures),
        "queue": runtime.outbox.status_counts(),
        "pending": runtime.outbox.pending_count(),
    }


@router.post("/reindex")
def reindex_owner(owner: CurrentOwner, db: DbSession, settings: RuntimeSettings) -> dict:
    """Enqueue every stored interaction at the active embedding version."""

    runtime = build_runtime(db, owner.id, settings)
    enqueued = runtime.indexer.enqueue_owner_interactions()
    return {
        "enqueued": enqueued,
        "embedding_version": settings.embedding_version,
        "provider": runtime.status,
        "pending": runtime.outbox.pending_count(),
    }


@router.get("/search")
def search_index(
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
    q: str = Query(min_length=2, max_length=1000),
    limit: int = Query(default=16, ge=1, le=64),
) -> dict:
    """Owner-scoped semantic retrieval used to inspect what the index actually holds."""

    runtime = build_runtime(db, owner.id, settings)
    if not runtime.configured:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Semantic index is not configured",
        )
    try:
        hits = runtime.indexer.search(q, limit=limit)
    except SemanticIndexError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    return {
        "hits": [
            {
                "interaction_id": hit.interaction_id,
                "person_ids": list(hit.person_ids),
                "source": hit.source,
                "occurred_at": hit.occurred_at,
                "snippet": hit.text[:240],
                "citation_locator": hit.citation_locator,
                "score": hit.score,
            }
            for hit in hits
        ],
        "total": len(hits),
    }
