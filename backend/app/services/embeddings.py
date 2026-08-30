"""OpenRouter embedding adapter for the derived semantic index.

The provider is OpenAI-compatible, so responses may arrive out of order. Vectors are
reordered by ``index`` and their width validated before any caller can persist them.
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx

from app.config import Settings


class EmbeddingError(RuntimeError):
    """Raised when embeddings are unavailable, malformed, or the wrong width."""


class OpenRouterEmbeddings:
    """Batching embedding client satisfying ``EmbeddingPort``."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self._settings = settings
        self._transport = transport

    @property
    def model(self) -> str:
        return self._settings.embedding_model

    def embed(self, texts: list[str]) -> list[tuple[float, ...]]:
        """Return one validated vector per input, in the original input order."""

        if not texts:
            return []
        key = self._api_key()
        vectors: list[tuple[float, ...]] = []
        with httpx.Client(
            timeout=self._settings.semantic_timeout_seconds,
            transport=self._transport,
        ) as client:
            for batch in self._batches(texts):
                vectors.extend(self._embed_batch(client, key, batch))
        return vectors

    def _api_key(self) -> str:
        secret = self._settings.openrouter_api_key
        key = secret.get_secret_value().strip() if secret is not None else ""
        if not key:
            raise EmbeddingError("OpenRouter API key is not configured")
        return key

    def _batches(self, texts: list[str]) -> Iterator[list[str]]:
        size = max(1, self._settings.embedding_batch_size)
        for start in range(0, len(texts), size):
            yield texts[start : start + size]

    def _embed_batch(
        self,
        client: httpx.Client,
        key: str,
        batch: list[str],
    ) -> list[tuple[float, ...]]:
        response = client.post(
            f"{self._settings.openrouter_base_url.rstrip('/')}/embeddings",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": self._settings.embedding_model, "input": batch},
        )
        if response.status_code >= 400:
            raise EmbeddingError(
                f"OpenRouter embeddings request failed with HTTP status {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError:
            raise EmbeddingError("OpenRouter returned a non-JSON embeddings response") from None
        return self._ordered_vectors(body, len(batch))

    def _ordered_vectors(self, body: object, expected: int) -> list[tuple[float, ...]]:
        if not isinstance(body, dict):
            raise EmbeddingError("OpenRouter returned a malformed embeddings response")
        data = body.get("data")
        if not isinstance(data, list):
            raise EmbeddingError("OpenRouter embeddings response has no data list")
        by_index: dict[int, tuple[float, ...]] = {}
        for item in data:
            index, vector = self._read_entry(item)
            by_index[index] = vector
        if len(by_index) != expected or any(index not in by_index for index in range(expected)):
            raise EmbeddingError(
                f"OpenRouter returned {len(by_index)} usable embeddings for {expected} inputs"
            )
        return [by_index[index] for index in range(expected)]

    def _read_entry(self, item: object) -> tuple[int, tuple[float, ...]]:
        if not isinstance(item, dict):
            raise EmbeddingError("OpenRouter embedding entry is not an object")
        index = item.get("index")
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise EmbeddingError("OpenRouter embedding entry has no usable index")
        return index, self._read_vector(item.get("embedding"))

    def _read_vector(self, raw: object) -> tuple[float, ...]:
        expected = self._settings.embedding_dimensions
        if not isinstance(raw, list):
            raise EmbeddingError("OpenRouter embedding entry has no vector")
        if len(raw) != expected:
            raise EmbeddingError(
                f"OpenRouter returned a {len(raw)}-dimension vector, expected {expected}"
            )
        try:
            return tuple(float(value) for value in raw)
        except (TypeError, ValueError):
            raise EmbeddingError(
                "OpenRouter embedding vector contains a non-numeric value"
            ) from None


class NullEmbeddings:
    """Placeholder used when no embedding provider is configured.

    Construction always succeeds so the query and import paths can be assembled, but any
    attempt to embed fails loudly instead of silently returning unusable vectors.
    """

    available = False

    def __init__(self, model: str = "unconfigured") -> None:
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def embed(self, texts: list[str]) -> list[tuple[float, ...]]:
        del texts
        raise EmbeddingError("No embedding provider is configured")
