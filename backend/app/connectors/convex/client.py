"""Convex HTTP adapter for the derived semantic chunk store.

Convex answers function calls with HTTP 200 even when the function itself failed, so every
response body is inspected for ``status`` before its value is trusted. Deploy keys are read
from settings at call time and never echoed into errors.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.domain.semantic import ChunkPayload, SemanticHit, owner_scope

UPSERT_FUNCTION = "chunks:upsertBatch"
TOMBSTONE_FUNCTION = "chunks:tombstoneInteraction"
SEARCH_FUNCTION = "chunks:search"


class ConvexError(RuntimeError):
    """Raised when Convex is unconfigured, unreachable, or returns a function error."""


class ConvexSemanticStore:
    """Owner-scoped vector store satisfying ``SemanticStorePort``."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self._settings = settings
        self._transport = transport

    @property
    def available(self) -> bool:
        url = (self._settings.convex_url or "").strip()
        secret = self._settings.convex_deploy_key
        key = secret.get_secret_value().strip() if secret is not None else ""
        return bool(url and key)

    def upsert(self, chunks: list[ChunkPayload]) -> int:
        """Write chunks in deployment-sized batches; returns how many rows changed."""

        if not chunks:
            return 0
        for chunk in chunks:
            self._validate_chunk(chunk)
        size = max(1, self._settings.convex_upsert_batch_size)
        changed = 0
        for start in range(0, len(chunks), size):
            batch = chunks[start : start + size]
            value = self._call(
                "mutation",
                UPSERT_FUNCTION,
                {"chunks": [chunk.as_payload() for chunk in batch]},
            )
            changed += _as_int(value)
        return changed

    def tombstone(self, owner_id: str, interaction_id: str) -> int:
        value = self._call(
            "mutation",
            TOMBSTONE_FUNCTION,
            {"owner_id": owner_id, "interaction_id": interaction_id},
        )
        return _as_int(value)

    def search(
        self,
        vector: tuple[float, ...],
        owner_id: str,
        embedding_version: str,
        sources: list[str] | None = None,
        limit: int = 32,
    ) -> list[SemanticHit]:
        self._validate_vector(vector)
        args: dict[str, Any] = {
            "vector": list(vector),
            "owner_id": owner_id,
            "embedding_version": embedding_version,
            "limit": limit,
        }
        if sources:
            args["sources"] = list(sources)
        return self._as_hits(self._call("action", SEARCH_FUNCTION, args))

    def _validate_chunk(self, chunk: ChunkPayload) -> None:
        expected = owner_scope(chunk.owner_id, chunk.embedding_version)
        if chunk.owner_scope != expected:
            raise ConvexError("owner_scope does not match owner and embedding version")
        self._validate_vector(chunk.embedding)

    def _validate_vector(self, vector: tuple[float, ...]) -> None:
        expected = self._settings.embedding_dimensions
        if len(vector) != expected:
            raise ConvexError(f"embedding has {len(vector)} dimensions, expected {expected}")

    def _credentials(self) -> tuple[str, str]:
        url = (self._settings.convex_url or "").strip().rstrip("/")
        secret = self._settings.convex_deploy_key
        key = secret.get_secret_value().strip() if secret is not None else ""
        if not url:
            raise ConvexError("Convex deployment URL is not configured")
        if not key:
            raise ConvexError("Convex deploy key is not configured")
        return url, key

    def _call(self, endpoint: str, function: str, args: dict[str, Any]) -> Any:
        url, key = self._credentials()
        with httpx.Client(
            timeout=self._settings.semantic_timeout_seconds,
            transport=self._transport,
        ) as client:
            response = client.post(
                f"{url}/api/{endpoint}",
                headers={"Authorization": f"Convex {key}"},
                json={"path": function, "args": args, "format": "json"},
            )
        return _unwrap(response, function)

    @staticmethod
    def _as_hits(value: Any) -> list[SemanticHit]:
        if not isinstance(value, list):
            return []
        return [_as_hit(item) for item in value if isinstance(item, dict)]


class NullSemanticStore:
    """Honest stand-in used when Convex is not configured.

    Writes fail loudly so the import path can record the failure, while search degrades to
    no evidence instead of pretending the index is empty for a configured deployment.
    """

    available = False

    def upsert(self, chunks: list[ChunkPayload]) -> int:
        del chunks
        raise ConvexError("Convex semantic store is not configured")

    def tombstone(self, owner_id: str, interaction_id: str) -> int:
        del owner_id, interaction_id
        raise ConvexError("Convex semantic store is not configured")

    def search(
        self,
        vector: tuple[float, ...],
        owner_id: str,
        embedding_version: str,
        sources: list[str] | None = None,
        limit: int = 32,
    ) -> list[SemanticHit]:
        del vector, owner_id, embedding_version, sources, limit
        return []


def _unwrap(response: httpx.Response, function: str) -> Any:
    if response.status_code >= 400:
        raise ConvexError(f"Convex {function} failed with HTTP status {response.status_code}")
    try:
        body = response.json()
    except ValueError:
        raise ConvexError(f"Convex {function} returned a non-JSON response") from None
    if not isinstance(body, dict):
        raise ConvexError(f"Convex {function} returned a malformed response")
    if body.get("status") != "success":
        message = body.get("errorMessage") or "unknown Convex function error"
        raise ConvexError(f"Convex {function} failed: {message}")
    return body.get("value")


def _as_hit(document: dict[str, Any]) -> SemanticHit:
    raw_people = document.get("person_ids")
    people = tuple(str(person) for person in raw_people) if isinstance(raw_people, list) else ()
    return SemanticHit(
        chunk_key=str(document.get("chunk_key") or ""),
        interaction_id=str(document.get("interaction_id") or ""),
        person_ids=people,
        source=str(document.get("source") or "unknown"),
        occurred_at=_as_int(document.get("occurred_at")),
        text=str(document.get("text") or ""),
        citation_locator=str(document.get("citation_locator") or ""),
        score=_as_float(document.get("score")),
    )


def _as_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0
    return int(value)


def _as_float(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return float(value)
