"""Deterministic boundary-aware text chunking for semantic indexing."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass

DEFAULT_MAX_CHARS = 2_000
_PARAGRAPH_BOUNDARY = re.compile(r"\n[ \t]*\n+")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class TextChunk:
    chunk_key: str
    interaction_id: str
    content_version: int
    ordinal: int
    text: str
    text_hash: str


def make_chunk_key(interaction_id: str, content_version: int, ordinal: int) -> str:
    """Return ``sha256(interaction_id:content_version:ordinal)``."""

    material = f"{interaction_id}:{content_version}:{ordinal}".encode()
    return hashlib.sha256(material).hexdigest()


def chunk_text(text: str | None, max_chars: int = DEFAULT_MAX_CHARS) -> tuple[str, ...]:
    """Split one message at paragraph, then sentence/word boundaries.

    Adjacent short paragraphs may share a chunk, but their blank-line boundary is
    retained. Empty content always yields no chunks.
    """

    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    normalized = _normalize_newlines(text or "").strip()
    if not normalized:
        return ()
    pieces: list[str] = []
    for paragraph in _PARAGRAPH_BOUNDARY.split(normalized):
        clean = paragraph.strip()
        if not clean:
            continue
        pieces.extend(_split_oversized(clean, max_chars))
    return tuple(_pack_pieces(pieces, max_chars))


def chunk_interaction(
    interaction_id: str,
    content_version: int,
    body_text: str | None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> tuple[TextChunk, ...]:
    """Build keyed chunks for one interaction; never crosses message boundaries."""

    texts = chunk_text(body_text, max_chars)
    return tuple(
        _make_chunk(interaction_id, content_version, ordinal, text)
        for ordinal, text in enumerate(texts)
    )


def _make_chunk(
    interaction_id: str,
    content_version: int,
    ordinal: int,
    text: str,
) -> TextChunk:
    return TextChunk(
        chunk_key=make_chunk_key(interaction_id, content_version, ordinal),
        interaction_id=interaction_id,
        content_version=content_version,
        ordinal=ordinal,
        text=text,
        text_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _split_oversized(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    sentences = [part.strip() for part in _SENTENCE_BOUNDARY.split(text) if part.strip()]
    if len(sentences) == 1:
        return _split_words(text, max_chars)
    result: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                result.append(current)
                current = ""
            result.extend(_split_words(sentence, max_chars))
        elif not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= max_chars:
            current = f"{current} {sentence}"
        else:
            result.append(current)
            current = sentence
    if current:
        result.append(current)
    return result


def _split_words(text: str, max_chars: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    result: list[str] = []
    current = ""
    for word in words:
        while len(word) > max_chars:
            if current:
                result.append(current)
                current = ""
            result.append(word[:max_chars])
            word = word[max_chars:]
        if not word:
            continue
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= max_chars:
            current = f"{current} {word}"
        else:
            result.append(current)
            current = word
    if current:
        result.append(current)
    return result


def _pack_pieces(pieces: Iterable[str], max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        separator = "\n\n" if current else ""
        if current and len(current) + len(separator) + len(piece) > max_chars:
            chunks.append(current)
            current = piece
        else:
            current = f"{current}{separator}{piece}"
    if current:
        chunks.append(current)
    return chunks
