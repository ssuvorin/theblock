from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from app.config import Settings
from app.services.embeddings import EmbeddingError, NullEmbeddings, OpenRouterEmbeddings

API_KEY = "sk-or-test-embedding-key"
DIMENSIONS = 8


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "auth_secret": "a" * 40,
        "owner_password": "p" * 16,
        "openrouter_api_key": API_KEY,
        "openrouter_base_url": "https://openrouter.test/api/v1",
        "embedding_model": "openai/text-embedding-3-small",
        "embedding_dimensions": DIMENSIONS,
        "embedding_batch_size": 2,
        "semantic_timeout_seconds": 5.0,
    }
    values.update(overrides)
    return Settings(**values)


def vector_for(text: str) -> list[float]:
    return [float(len(text))] * DIMENSIONS


def recording_transport(
    calls: list[dict[str, Any]],
    reverse: bool = False,
    dimensions: int = DIMENSIONS,
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
        data = [
            {"index": index, "embedding": [float(len(text))] * dimensions}
            for index, text in enumerate(payload["input"])
        ]
        if reverse:
            data.reverse()
        return httpx.Response(200, json={"data": data})

    return httpx.MockTransport(handle)


def exploding_transport() -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected HTTP call to {request.url}")

    return httpx.MockTransport(handle)


def test_batches_split_at_configured_size_and_preserve_order() -> None:
    calls: list[dict[str, Any]] = []
    client = OpenRouterEmbeddings(make_settings(), transport=recording_transport(calls))
    texts = ["a", "bb", "ccc", "dddd", "eeeee"]

    vectors = client.embed(texts)

    assert [call["payload"]["input"] for call in calls] == [
        ["a", "bb"],
        ["ccc", "dddd"],
        ["eeeee"],
    ]
    assert vectors == [tuple(vector_for(text)) for text in texts]
    assert all(len(vector) == DIMENSIONS for vector in vectors)


def test_request_targets_embeddings_endpoint_with_model_and_key() -> None:
    calls: list[dict[str, Any]] = []
    client = OpenRouterEmbeddings(make_settings(), transport=recording_transport(calls))

    client.embed(["only"])

    assert client.model == "openai/text-embedding-3-small"
    assert calls[0]["url"] == "https://openrouter.test/api/v1/embeddings"
    assert calls[0]["authorization"] == f"Bearer {API_KEY}"
    assert calls[0]["payload"]["model"] == "openai/text-embedding-3-small"


def test_out_of_order_indexes_are_reordered_to_input_order() -> None:
    calls: list[dict[str, Any]] = []
    settings = make_settings(embedding_batch_size=8)
    client = OpenRouterEmbeddings(settings, transport=recording_transport(calls, reverse=True))
    texts = ["a", "bb", "ccc", "dddd"]

    vectors = client.embed(texts)

    assert len(calls) == 1
    assert calls[0]["payload"]["input"] == texts
    assert vectors == [tuple(vector_for(text)) for text in texts]


def test_wrong_dimension_vector_raises_without_poisoning_the_index() -> None:
    calls: list[dict[str, Any]] = []
    transport = recording_transport(calls, dimensions=DIMENSIONS - 1)
    client = OpenRouterEmbeddings(make_settings(), transport=transport)

    with pytest.raises(EmbeddingError) as error:
        client.embed(["a"])

    assert "dimension" in str(error.value)
    assert API_KEY not in str(error.value)


def test_missing_index_or_malformed_entry_raises() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"data": [{"embedding": [0.0] * DIMENSIONS}]})

    client = OpenRouterEmbeddings(make_settings(), transport=httpx.MockTransport(handle))

    with pytest.raises(EmbeddingError):
        client.embed(["a"])


def test_short_data_list_raises() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.5] * DIMENSIONS}]})

    settings = make_settings(embedding_batch_size=4)
    client = OpenRouterEmbeddings(settings, transport=httpx.MockTransport(handle))

    with pytest.raises(EmbeddingError):
        client.embed(["a", "bb"])


def test_empty_input_performs_no_http_call() -> None:
    client = OpenRouterEmbeddings(make_settings(), transport=exploding_transport())

    assert client.embed([]) == []


def test_missing_key_raises_before_any_http_call() -> None:
    client = OpenRouterEmbeddings(
        make_settings(openrouter_api_key=None), transport=exploding_transport()
    )

    with pytest.raises(EmbeddingError) as error:
        client.embed(["secret business context"])

    assert "not configured" in str(error.value)
    assert "secret business context" not in str(error.value)


def test_blank_key_raises_before_any_http_call() -> None:
    client = OpenRouterEmbeddings(
        make_settings(openrouter_api_key="   "), transport=exploding_transport()
    )

    with pytest.raises(EmbeddingError):
        client.embed(["a"])


def test_http_error_never_leaks_key_or_input_text() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(401, json={"error": {"message": "no auth"}})

    client = OpenRouterEmbeddings(make_settings(), transport=httpx.MockTransport(handle))

    with pytest.raises(EmbeddingError) as error:
        client.embed(["confidential message body"])

    message = str(error.value)
    assert "401" in message
    assert API_KEY not in message
    assert "confidential message body" not in message


def test_null_embeddings_construct_but_refuse_to_embed() -> None:
    client = NullEmbeddings()

    assert client.model == "unconfigured"
    with pytest.raises(EmbeddingError):
        client.embed(["a"])
