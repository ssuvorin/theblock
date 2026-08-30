"""CSV parsing primitives for LinkedIn data-export archives.

Real exports are messier than the Basic sample suggests: ``Connections.csv`` opens with a
free-text ``Notes:`` preamble before its header, job files live under a ``Jobs/``
subdirectory, ``Sent At`` timestamps use more than one format, and ``messages.csv`` carries
unsent drafts alongside real messages. Every quirk here was observed in an actual archive.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator, Mapping
from datetime import UTC, date, datetime
from pathlib import Path

CSV_FIELD_SIZE_LIMIT = 16 * 1024 * 1024
MESSAGE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S UTC"
INVITATION_DATE_FORMATS = (
    "%m/%d/%y, %I:%M %p",
    "%Y-%m-%d %H:%M:%S UTC",
    "%Y-%m-%d %H:%M:%S",
    "%d %b %Y",
)
CONNECTIONS_HEADER_MARKER = "First Name"
KNOWN_FILES = (
    "messages.csv",
    "Invitations.csv",
    "Profile.csv",
    "Positions.csv",
    "Connections.csv",
    "Company Follows.csv",
    "Skills.csv",
    "Email Addresses.csv",
    "PhoneNumbers.csv",
    "Job Seeker Preferences.csv",
)
_DRAFT_FLAGS = ("IS MESSAGE DRAFT", "IS CONVERSATION DRAFT")
_TRUTHY = frozenset({"true", "yes", "1"})


class LinkedInArchiveError(ValueError):
    """Raised for an invalid or unreadable LinkedIn export artifact."""


def raise_csv_field_limit(limit: int = CSV_FIELD_SIZE_LIMIT) -> int:
    """Raise the process CSV limit and return the effective value."""

    if limit <= 0:
        raise ValueError("CSV field limit must be positive")
    csv.field_size_limit(limit)
    return csv.field_size_limit()


def read_csv_rows(
    path: str | Path,
    *,
    header_marker: str | None = None,
) -> tuple[dict[str, str], ...]:
    """Parse records with stdlib CSV, including quoted embedded newlines.

    ``header_marker`` names a column that must appear in the header, which lets callers skip
    a free-text preamble instead of misreading it as data.
    """

    csv_path = Path(path)
    raise_csv_field_limit()
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            header = _locate_header(reader, csv_path, header_marker)
            return tuple(_row_dicts(reader, header, csv_path))
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


def parse_connections(path: str | Path) -> tuple[dict[str, str], ...]:
    """Read ``Connections.csv`` past the privacy notice LinkedIn prepends to it."""

    rows = read_csv_rows(path, header_marker=CONNECTIONS_HEADER_MARKER)
    _require_headers(rows, path, ("First Name", "Last Name", "URL"))
    return rows


def is_draft(row: Mapping[str, str]) -> bool:
    """A drafted message was never sent, so it is not interaction evidence."""

    return any(field(row, flag).strip().casefold() in _TRUTHY for flag in _DRAFT_FLAGS)


def parse_message_date(value: str) -> datetime:
    """Parse the UTC timestamp format used only by ``messages.csv``."""

    try:
        parsed = datetime.strptime(value.strip(), MESSAGE_DATE_FORMAT)
    except ValueError as error:
        raise LinkedInArchiveError("invalid messages.csv DATE") from error
    return parsed.replace(tzinfo=UTC)


def parse_invitation_date(value: str) -> date:
    """Parse an invitation timestamp as date-only because its zone is unknown.

    LinkedIn has shipped several ``Sent At`` formats, so accept each observed one rather than
    failing the whole import on a format the archive is entitled to use.
    """

    text = value.strip()
    for pattern in INVITATION_DATE_FORMATS:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise LinkedInArchiveError("invalid Invitations.csv Sent At")


def archive_file(path: str | Path, filename: str) -> Path | None:
    """Locate a known file case-insensitively, including inside export subdirectories."""

    archive = Path(path)
    if not archive.is_dir():
        raise LinkedInArchiveError("archive path must be a directory")
    expected = filename.casefold()
    for candidate in sorted(archive.iterdir()):
        if candidate.is_file() and candidate.name.casefold() == expected:
            return candidate
    nested = sorted(
        item for item in archive.rglob("*") if item.is_file() and item.name.casefold() == expected
    )
    return nested[0] if nested else None


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


def _locate_header(
    reader: Iterator[list[str]],
    path: Path,
    header_marker: str | None,
) -> tuple[str, ...]:
    """Return the first non-empty row that qualifies as the header."""

    wanted = header_marker.casefold() if header_marker else None
    for values in reader:
        header = tuple(_clean_key(value) for value in values)
        if not any(header):
            continue
        if wanted is None or any(name.casefold() == wanted for name in header):
            return header
    if wanted is None:
        raise LinkedInArchiveError(f"{path.name} has no CSV header")
    raise LinkedInArchiveError(f"{path.name} has no {header_marker} header row")


def _row_dicts(
    reader: Iterator[list[str]],
    header: tuple[str, ...],
    path: Path,
) -> Iterator[dict[str, str]]:
    for row_number, values in enumerate(reader, start=2):
        if len(values) > len(header):
            raise LinkedInArchiveError(f"{path.name} row {row_number} has more values than headers")
        row = {
            name: values[index] if index < len(values) else "" for index, name in enumerate(header)
        }
        if any(value != "" for value in row.values()):
            yield row


def _clean_key(value: str) -> str:
    return value.strip().lstrip("\ufeff")


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
