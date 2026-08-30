from __future__ import annotations

import csv
import statistics
from datetime import UTC, date, datetime
from pathlib import Path

from app.connectors.linkedin_export.parse import (
    parse_invitation_date,
    parse_invitations,
    parse_message_date,
    parse_messages,
)
from scripts.generate_synthetic_archive import DEFAULT_SEED, generate_archive

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_export"
EXPECTED_FILES = {
    "messages.csv",
    "Invitations.csv",
    "Profile.csv",
    "Positions.csv",
    "Company Follows.csv",
    "Skills.csv",
    "Email Addresses.csv",
    "PhoneNumbers.csv",
}


def test_fixture_is_messy_basic_export_shape() -> None:
    rows = parse_messages(FIXTURE / "messages.csv")
    assert len(rows) == 480
    assert set(path.name for path in FIXTURE.iterdir()) == EXPECTED_FILES
    assert any("\n" in row["CONTENT"] for row in rows)
    assert any(not row["CONTENT"] for row in rows)
    assert {row["FOLDER"] for row in rows} >= {"INBOX", "ARCHIVE", ""}
    lengths = [len(row["CONTENT"]) for row in rows if row["CONTENT"]]
    assert 50 <= statistics.median(lengths) <= 100
    assert 2 <= sum(length > 3_000 for length in lengths) <= 5


def test_embedded_newlines_are_one_csv_record() -> None:
    rows = parse_messages(FIXTURE / "messages.csv")
    multiline = next(row for row in rows if "\n\n" in row["CONTENT"])
    assert "Dubai" in multiline["CONTENT"] or "product" in multiline["CONTENT"]
    assert multiline["CONVERSATION ID"].startswith("synthetic-thread-")


def test_per_file_date_formats_are_explicit() -> None:
    message_time = parse_message_date("2026-08-30 07:37:53 UTC")
    invitation_day = parse_invitation_date("08/30/26, 07:37 AM")
    assert message_time == datetime(2026, 8, 30, 7, 37, 53, tzinfo=UTC)
    assert invitation_day == date(2026, 8, 30)
    assert not isinstance(invitation_day, datetime)
    invitation = parse_invitations(FIXTURE / "Invitations.csv")[0]
    assert parse_invitation_date(invitation["Sent At"]).year in {2025, 2026}


def test_csv_field_limit_accepts_large_quoted_content(tmp_path: Path) -> None:
    path = tmp_path / "messages.csv"
    content = "large-field-" * 20_000 + "\nembedded newline"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("CONVERSATION ID", "DATE", "CONTENT"))
        writer.writerow(("large", "2026-08-30 07:37:53 UTC", content))
    rows = parse_messages(path)
    assert len(rows) == 1
    assert rows[0]["CONTENT"] == content


def test_fixed_seed_generation_is_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_counts = generate_archive(first, seed=DEFAULT_SEED)
    second_counts = generate_archive(second, seed=DEFAULT_SEED)
    assert first_counts == second_counts
    assert set(first_counts) == EXPECTED_FILES
    for filename in EXPECTED_FILES:
        assert (first / filename).read_bytes() == (second / filename).read_bytes()


def test_canonical_cast_and_daniel_context_are_present() -> None:
    rows = parse_messages(FIXTURE / "messages.csv")
    names = {row["FROM"] for row in rows} | {row["TO"] for row in rows}
    assert names >= {
        "Alex Ivanov",
        "Marta",
        "Sergey Lapin",
        "John",
        "Daniel Ruiz",
        "Nadia",
        "Omar",
        "Lena",
        "Tom",
        "Ruth",
    }
    daniel_text = " ".join(
        row["CONTENT"] for row in rows if "Daniel Ruiz" in {row["FROM"], row["TO"]}
    ).casefold()
    assert "whatsapp" in daniel_text
    assert "gmail" in daniel_text
    assert "telegram" not in daniel_text
