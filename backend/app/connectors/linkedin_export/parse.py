"""CSV parsing primitives for ``Basic_LinkedInDataExport`` archives."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path

CSV_FIELD_SIZE_LIMIT = 16 * 1024 * 1024
MESSAGE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S UTC"
INVITATION_DATE_FORMAT = "%m/%d/%y, %I:%M %p"
KNOWN_FILES = (
    "messages.csv",
    "Invitations.csv",
    "Profile.csv",
    "Positions.csv",
    "Company Follows.csv",
    "Skills.csv",
    "Email Addresses.csv",
    "PhoneNumbers.csv",
)


class LinkedInArchiveError(ValueError):
    """Raised for an invalid or unreadable LinkedIn export artifact."""


def raise_csv_field_limit(limit: int = CSV_FIELD_SIZE_LIMIT) -> int:
    """Raise the process CSV limit and return the effective value."""

    if limit <= 0:
        raise ValueError("CSV field limit must be positive")
    csv.field_size_limit(limit)
    return csv.field_size_limit()


def read_csv_rows(path: str | Path) -> tuple[dict[str, str], ...]:
    """Parse records with stdlib CSV, including quoted embedded newlines."""

    csv_path = Path(path)
    raise_csv_field_limit()
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None:
                raise LinkedInArchiveError(f"{csv_path.name} has no CSV header")
            rows: list[dict[str, str]] = []
            for row_number, row in enumerate(reader, start=2):
                if None in row:
                    raise LinkedInArchiveError(
                        f"{csv_path.name} row {row_number} has more values than headers"
                    )
                normalized = {
                    (key or "").strip().lstrip("\ufeff"): value if value is not None else ""
                    for key, value in row.items()
                }
                if any(value != "" for value in normalized.values()):
                    rows.append(normalized)
            return tuple(rows)
    except (OSError, csv.Error) as error:
        raise LinkedInArchiveError(f"could not parse {csv_path.name}: {error}") from error


def parse_messages(path: str | Path) -> tuple[dict[str, str], ...]:
    rows = read_csv_rows(path)
    _require_headers(rows, path, ("CONVERSATION ID", "DATE", "CONTENT"))
    return rows


def parse_invitations(path: str | Path) -> tuple[dict[str, str], ...]:
    rows = read_csv_rows(path)
    _require_any_header(rows, path, ("Sent At", "SENT AT", "DATE"))
    return rows


def parse_message_date(value: str) -> datetime:
    """Parse the UTC timestamp format used only by ``messages.csv``."""

    try:
        parsed = datetime.strptime(value.strip(), MESSAGE_DATE_FORMAT)
    except ValueError as error:
        raise LinkedInArchiveError("invalid messages.csv DATE") from error
    return parsed.replace(tzinfo=UTC)


def parse_invitation_date(value: str) -> date:
    """Parse an invitation timestamp as date-only because its zone is unknown."""

    try:
        return datetime.strptime(value.strip(), INVITATION_DATE_FORMAT).date()
    except ValueError as error:
        raise LinkedInArchiveError("invalid Invitations.csv Sent At") from error


def archive_file(path: str | Path, filename: str) -> Path | None:
    """Locate a known file case-insensitively without assuming all exports contain it."""

    archive = Path(path)
    if not archive.is_dir():
        raise LinkedInArchiveError("archive path must be a directory")
    expected = filename.casefold()
    for candidate in archive.iterdir():
        if candidate.is_file() and candidate.name.casefold() == expected:
            return candidate
    return None


def field(row: Mapping[str, str], *names: str, default: str = "") -> str:
    """Read a field using exact then case-insensitive archive header aliases."""

    for name in names:
        if name in row:
            return row[name]
    folded = {key.strip().casefold(): value for key, value in row.items()}
    for name in names:
        if name.casefold() in folded:
            return folded[name.casefold()]
    return default


def _require_headers(
    rows: tuple[dict[str, str], ...],
    path: str | Path,
    required: tuple[str, ...],
) -> None:
    if not rows:
        return
    folded = {header.casefold() for header in rows[0]}
    missing = [header for header in required if header.casefold() not in folded]
    if missing:
        joined = ", ".join(missing)
        raise LinkedInArchiveError(f"{Path(path).name} is missing headers: {joined}")


def _require_any_header(
    rows: tuple[dict[str, str], ...],
    path: str | Path,
    alternatives: tuple[str, ...],
) -> None:
    if not rows:
        return
    folded = {header.casefold() for header in rows[0]}
    if not any(header.casefold() in folded for header in alternatives):
        raise LinkedInArchiveError(f"{Path(path).name} has no invitation date header")
