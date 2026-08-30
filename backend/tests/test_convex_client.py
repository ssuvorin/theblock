from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from app.config import Settings
from app.connectors.convex.client import (
    ConvexError,
    ConvexSemanticStore,
    NullSemanticStore,
)
from app.domain.semantic import ChunkPayload, owner_scope

DEPLOY_KEY = "convex-deploy-key-must-never-leak"
CONVEX_URL = "https://example-deployment.convex.cloud"
DIMENSIONS = 8
OWNER_ID = "owner-1"
VERSION = "v1"


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "auth_secret": "a" * 40,
        "owner_password": "p" * 16,
        "convex_url": CONVEX_URL,
        "convex_deploy_key": DEPLOY_KEY,
        "embedding_dimensions": DIMENSIONS,
        "embedding_version": VERSION,
        "convex_upsert_batch_size": 50,
        "semantic_timeout_seconds": 5.0,
    }
    values.update(overrides)
    return Settings(**values)


def make_chunk(ordinal: int, owner_id: str = OWNER_ID, scope: str | None = None) -> ChunkPayload:
    return ChunkPayload(
        chunk_key=f"chunk-{ordinal}",
        owner_id=owner_id,
        owner_scope=scope if scope is not None else owner_scope(owner_id, VERSION),
        interaction_id="interaction-1",
        person_ids=("person-1",),
        source="linkedin_message",
        occurred_at=1_700_000_000_000,
        ordinal=ordinal,
        text=f"chunk body {ordinal}",
        text_hash=f"hash-{ordinal}",
        citation_locator=f"interaction-1#{ordinal}",
        embedding_model="openai/text-embedding-3-small",
        embedding_version=VERSION,
        embedding=tuple(float(ordinal) for _ in range(DIMENSIONS)),
    )


def recording_transport(
    calls: list[dict[str, Any]],
    value: Any = None,
    value_factory: Any = None,
) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(
            {
                "url": str(request.url),
                "authorization": request.headers.get("Authorization"),
                "payload": payload,
            }
        )
        resolved = value_factory(payload) if value_factory is not None else value
        return httpx.Response(200, json={"status": "success", "value": resolved})

    return httpx.MockTransport(handle)


def exploding_transport() -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected HTTP call to {request.url}")

    return httpx.MockTransport(handle)


def test_upsert_splits_into_batches_of_fifty_and_sums_counts() -> None:
    calls: list[dict[str, Any]] = []
    store = ConvexSemanticStore(
        make_settings(),
        transport=recording_transport(
            calls, value_factory=lambda payload: len(payload["args"]["chunks"])
        ),
    )
    chunks = [make_chunk(index) for index in range(120)]

    changed = store.upsert(chunks)

    assert changed == 120
    assert [len(call["payload"]["args"]["chunks"]) for call in calls] == [50, 50, 20]
    assert all(call["url"] == f"{CONVEX_URL}/api/mutation" for call in calls)
    assert all(call["payload"]["path"] == "chunks:upsertBatch" for call in calls)
    assert all(call["payload"]["format"] == "json" for call in calls)
    assert all(call["authorization"] == f"Convex {DEPLOY_KEY}" for call in calls)


def test_upsert_payload_carries_required_owner_scope_format() -> None:
    calls: list[dict[str, Any]] = []
    store = ConvexSemanticStore(make_settings(), transport=recording_transport(calls, value=1))

    store.upsert([make_chunk(0)])

    sent = calls[0]["payload"]["args"]["chunks"][0]
    assert sent["owner_scope"] == f"{OWNER_ID}:{VERSION}:active"
    assert sent["embedding"] == [0.0] * DIMENSIONS
    assert sent["person_ids"] == ["person-1"]


def test_upsert_rejects_mismatched_owner_scope_before_any_http_call() -> None:
    store = ConvexSemanticStore(make_settings(), transport=exploding_transport())

    with pytest.raises(ConvexError) as error:
        store.upsert([make_chunk(0, scope="owner-1:v1:deleted")])

    assert "owner_scope" in str(error.value)


def test_upsert_rejects_wrong_dimension_embedding_before_any_http_call() -> None:
    store = ConvexSemanticStore(
        make_settings(embedding_dimensions=16), transport=exploding_transport()
    )

    with pytest.raises(ConvexError) as error:
        store.upsert([make_chunk(0)])

    assert "dimensions" in str(error.value)


def test_empty_upsert_performs_no_http_call() -> None:
    store = ConvexSemanticStore(make_settings(), transport=exploding_transport())

    assert store.upsert([]) == 0


def test_convex_function_error_with_http_200_raises_without_deploy_key() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "status": "error",
                "errorMessage": "embedding must have 1536 dimensions",
                "errorData": None,
            },
        )

    store = ConvexSemanticStore(make_settings(), transport=httpx.MockTransport(handle))

    with pytest.raises(ConvexError) as error:
        store.upsert([make_chunk(0)])

    message = str(error.value)
    assert "embedding must have 1536 dimensions" in message
    assert "chunks:upsertBatch" in message
    assert DEPLOY_KEY not in message


def test_http_status_error_raises_without_deploy_key() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(500, text="internal error")

    store = ConvexSemanticStore(make_settings(), transport=httpx.MockTransport(handle))

    with pytest.raises(ConvexError) as error:
        store.tombstone(OWNER_ID, "interaction-1")

    assert "500" in str(error.value)
    assert DEPLOY_KEY not in str(error.value)


def test_tombstone_calls_mutation_and_returns_count() -> None:
    calls: list[dict[str, Any]] = []
    store = ConvexSemanticStore(make_settings(), transport=recording_transport(calls, value=3))

    assert store.tombstone(OWNER_ID, "interaction-9") == 3
    assert calls[0]["url"] == f"{CONVEX_URL}/api/mutation"
    assert calls[0]["payload"]["path"] == "chunks:tombstoneInteraction"
    assert calls[0]["payload"]["args"] == {
        "owner_id": OWNER_ID,
        "interaction_id": "interaction-9",
    }


def test_search_uses_action_endpoint_and_maps_documents_to_hits() -> None:
    calls: list[dict[str, Any]] = []
    documents = [
        {
            "_id": "doc-1",
            "chunk_key": "chunk-1",
            "interaction_id": "interaction-1",
            "person_ids": ["person-1", "person-2"],
            "source": "linkedin_message",
            "occurred_at": 1_700_000_000_000,
            "text": "They asked about the product role.",
            "citation_locator": "interaction-1#0",
            "score": 0.87,
        },
        {"chunk_key": "chunk-2"},
    ]
    store = ConvexSemanticStore(
        make_settings(), transport=recording_transport(calls, value=documents)
    )
    vector = tuple(0.25 for _ in range(DIMENSIONS))

    hits = store.search(vector, OWNER_ID, VERSION, sources=["linkedin_message"], limit=5)

    assert calls[0]["url"] == f"{CONVEX_URL}/api/action"
    assert calls[0]["payload"]["path"] == "chunks:search"
    assert calls[0]["payload"]["args"] == {
        "vector": [0.25] * DIMENSIONS,
        "owner_id": OWNER_ID,
        "embedding_version": VERSION,
        "limit": 5,
        "sources": ["linkedin_message"],
    }
    assert len(hits) == 2
    assert hits[0].chunk_key == "chunk-1"
    assert hits[0].person_ids == ("person-1", "person-2")
    assert hits[0].occurred_at == 1_700_000_000_000
    assert hits[0].text == "They asked about the product role."
    assert hits[0].citation_locator == "interaction-1#0"
    assert hits[0].score == pytest.approx(0.87)
    assert hits[1].score == 0.0
    assert hits[1].occurred_at == 0
    assert hits[1].person_ids == ()


def test_search_omits_sources_when_not_filtered_and_tolerates_non_list_value() -> None:
    calls: list[dict[str, Any]] = []
    store = ConvexSemanticStore(make_settings(), transport=recording_transport(calls, value=None))
    vector = tuple(0.5 for _ in range(DIMENSIONS))

    assert store.search(vector, OWNER_ID, VERSION) == []
    assert "sources" not in calls[0]["payload"]["args"]
    assert calls[0]["payload"]["args"]["limit"] == 32


def test_missing_url_raises_before_any_http_call() -> None:
    store = ConvexSemanticStore(make_settings(convex_url="  "), transport=exploding_transport())

    with pytest.raises(ConvexError) as error:
        store.tombstone(OWNER_ID, "interaction-1")

    assert "URL" in str(error.value)
    assert store.available is False


def test_missing_deploy_key_raises_before_any_http_call() -> None:
    store = ConvexSemanticStore(
        make_settings(convex_deploy_key=None), transport=exploding_transport()
    )

    with pytest.raises(ConvexError) as error:
        store.upsert([make_chunk(0)])

    assert "deploy key" in str(error.value)
    assert store.available is False


def test_configured_store_reports_available() -> None:
    assert ConvexSemanticStore(make_settings()).available is True


def test_null_store_degrades_honestly() -> None:
    store = NullSemanticStore()

    assert store.available is False
    assert store.search(tuple(0.0 for _ in range(DIMENSIONS)), OWNER_ID, VERSION) == []
    with pytest.raises(ConvexError):
        store.upsert([make_chunk(0)])
    with pytest.raises(ConvexError):
        store.tombstone(OWNER_ID, "interaction-1")
