from __future__ import annotations

import hashlib

from app.services.chunking import chunk_interaction, chunk_text, make_chunk_key


def test_chunk_key_is_exact_and_stable() -> None:
    expected = hashlib.sha256(b"interaction-7:3:2").hexdigest()
    assert make_chunk_key("interaction-7", 3, 2) == expected
    assert make_chunk_key("interaction-7", 3, 2) == expected
    assert make_chunk_key("interaction-7", 4, 2) != expected


def test_short_message_is_one_chunk_and_empty_is_skipped() -> None:
    text = "A realistic short message is kept whole."
    chunks = chunk_interaction("interaction-1", 1, text)
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].ordinal == 0
    assert chunk_interaction("interaction-2", 1, "  \n\n  ") == ()


def test_long_text_splits_at_paragraph_and_sentence_boundaries() -> None:
    text = (
        "First paragraph has one complete thought. It has a second complete thought.\n\n"
        "Second paragraph stays visibly separated from the first paragraph.\n\n"
        "Third paragraph finishes the message with useful context."
    )
    chunks = chunk_text(text, max_chars=90)
    assert len(chunks) >= 3
    assert all(len(chunk) <= 90 for chunk in chunks)
    assert all(not chunk.startswith(" ") and not chunk.endswith(" ") for chunk in chunks)
    assert "First paragraph has one complete thought." in chunks[0]
    assert any("Second paragraph" in chunk for chunk in chunks)


def test_rechunking_same_version_is_byte_stable() -> None:
    text = "Paragraph one.\n\n" + ("A bounded repeated sentence. " * 100)
    first = chunk_interaction("stable-id", 7, text, max_chars=180)
    second = chunk_interaction("stable-id", 7, text, max_chars=180)
    assert first == second
    assert len({chunk.chunk_key for chunk in first}) == len(first)
    assert all(
        chunk.text_hash == hashlib.sha256(chunk.text.encode()).hexdigest() for chunk in first
    )
