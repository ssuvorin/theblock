from __future__ import annotations

import csv
import statistics
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from app.connectors.linkedin_export.parse import (
    LinkedInArchiveError,
    archive_file,
    is_draft,
    parse_connections,
    parse_invitation_date,
    parse_invitations,
    parse_message_date,
    parse_messages,
    read_csv_rows,
)
from scripts.generate_synthetic_archive import DEFAULT_SEED, generate_archive

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_export"
TOP_LEVEL_FILES = {
    "messages.csv",
    "Invitations.csv",
    "Profile.csv",
    "Positions.csv",
    "Connections.csv",
    "Company Follows.csv",
    "Skills.csv",
    "Email Addresses.csv",
    "PhoneNumbers.csv",
}
GENERATED_FILES = TOP_LEVEL_FILES | {"Jobs/Job Seeker Preferences.csv"}


def test_fixture_is_messy_full_export_shape() -> None:
    rows = parse_messages(FIXTURE / "messages.csv")
    assert len(rows) == 480
    assert {path.name for path in FIXTURE.iterdir()} == TOP_LEVEL_FILES | {"Jobs"}
    assert any("\n" in row["CONTENT"] for row in rows)
    assert any(not row["CONTENT"] for row in rows)
    assert {row["FOLDER"] for row in rows} == {"INBOX", "ARCHIVE"}
    lengths = [len(row["CONTENT"]) for row in rows if row["CONTENT"]]
    assert 50 <= statistics.median(lengths) <= 100
    assert sum(length > 1_000 for length in lengths) >= 5


def test_profile_has_no_profile_url_column() -> None:
    """LinkedIn never exports the owner's own URL, so the importer must infer it."""

    profile = read_csv_rows(FIXTURE / "Profile.csv")[0]
    assert "Profile URL" not in profile
    assert not any("url" in key.casefold() for key in profile if key != "Websites")


def test_connections_preamble_is_skipped() -> None:
    rows = parse_connections(FIXTURE / "Connections.csv")
    assert rows
    assert set(rows[0]) >= {"First Name", "Last Name", "URL", "Company", "Position"}
    assert all(row["URL"].startswith("https://www.linkedin.com/in/") for row in rows)
    assert not any(row["First Name"].startswith("Notes") for row in rows)


def test_connections_without_the_preamble_marker_would_misparse() -> None:
    """Reading Connections.csv as an ordinary CSV is exactly the bug this guards against."""

    with pytest.raises(LinkedInArchiveError):
        read_csv_rows(FIXTURE / "Connections.csv")


def test_job_preferences_are_found_inside_the_jobs_subdirectory() -> None:
    located = archive_file(FIXTURE, "Job Seeker Preferences.csv")
    assert located is not None
    assert located.parent.name == "Jobs"


def test_drafts_are_recognized_from_either_flag() -> None:
    assert is_draft({"IS MESSAGE DRAFT": "Yes", "IS CONVERSATION DRAFT": "No"})
    assert is_draft({"IS MESSAGE DRAFT": "No", "IS CONVERSATION DRAFT": "Yes"})
    assert not is_draft({"IS MESSAGE DRAFT": "No", "IS CONVERSATION DRAFT": "No"})
    assert any(is_draft(row) for row in parse_messages(FIXTURE / "messages.csv"))


def test_embedded_newlines_are_one_csv_record() -> None:
    rows = parse_messages(FIXTURE / "messages.csv")
    multiline = next(row for row in rows if "\n\n" in row["CONTENT"])
    assert "Dubai" in multiline["CONTENT"] or "product" in multiline["CONTENT"]
    assert multiline["CONVERSATION ID"].startswith("2-")


def test_per_file_date_formats_are_explicit() -> None:
    message_time = parse_message_date("2026-08-30 07:37:53 UTC")
    invitation_day = parse_invitation_date("08/30/26, 07:37 AM")
    assert message_time == datetime(2026, 8, 30, 7, 37, 53, tzinfo=UTC)
    assert invitation_day == date(2026, 8, 30)
    assert not isinstance(invitation_day, datetime)


def test_invitation_dates_accept_every_observed_format() -> None:
    """A single hard-coded format fails the whole import on a valid archive."""

    assert parse_invitation_date("2026-08-30 07:37:53 UTC") == date(2026, 8, 30)
    assert parse_invitation_date("08/30/26, 07:37 AM") == date(2026, 8, 30)
    assert parse_invitation_date("30 Aug 2026") == date(2026, 8, 30)
    with pytest.raises(LinkedInArchiveError):
        parse_invitation_date("Synthetic demo value 1")
    invitation = parse_invitations(FIXTURE / "Invitations.csv")[0]
    assert parse_invitation_date(invitation["Sent At"]).year in {2024, 2025, 2026}


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
    assert set(first_counts) == GENERATED_FILES
    for filename in GENERATED_FILES:
        assert (first / filename).read_bytes() == (second / filename).read_bytes()


def test_canonical_cast_and_daniel_context_are_present() -> None:
    rows = parse_messages(FIXTURE / "messages.csv")
    names = {row["FROM"] for row in rows} | {row["TO"] for row in rows}
    assert names >= {
        "Maya Haddad",
        "Marta Oliveira",
        "Sergey Lapin",
        "John Whitfield",
        "Daniel Ruiz",
        "Nadia Karim",
        "Omar Faris",
        "Lena Brandt",
        "Tom Nkemdirim",
        "Ruth Alvarez",
    }
    daniel_text = " ".join(
        row["CONTENT"] for row in rows if "Daniel Ruiz" in {row["FROM"], row["TO"]}
    ).casefold()
    assert "whatsapp" in daniel_text
    assert "gmail" in daniel_text
    assert "telegram" not in daniel_text


def test_owner_appears_in_every_message() -> None:
    """Direction and reciprocity are undefined unless the owner is a party to each message."""

    owner = "Maya Haddad"
    rows = parse_messages(FIXTURE / "messages.csv")
    assert all(owner in {row["FROM"], row["TO"]} for row in rows)
