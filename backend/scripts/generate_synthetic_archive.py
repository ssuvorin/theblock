"""Generate a deterministic LinkedIn data-export archive for tests and demos.

This reproduces the quirks of a real export rather than an idealized one, because the
importer is only trustworthy if its fixtures can actually occur:

* ``Profile.csv`` has no profile-URL column, so the owner URL must be inferred.
* ``Connections.csv`` opens with a free-text privacy notice before its header.
* ``messages.csv`` carries unsent drafts, empty bodies, and embedded newlines.
* Job preferences live in a ``Jobs/`` subdirectory.
* Every message includes the owner as sender or recipient, so direction is derivable.
"""

from __future__ import annotations

import argparse
import csv
import random
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from pathlib import Path

try:  # Root invocation: python -m backend.scripts.generate_synthetic_archive
    from backend.scripts.synthetic_archive_data import (
        CONNECTIONS_PREAMBLE,
        CONTACTS,
        CONTEXT_MESSAGES,
        FOLLOWED_COMPANIES,
        JOB_PREFERENCE_HEADERS,
        JOB_PREFERENCE_ROW,
        OWNER_EMAIL,
        OWNER_FIRST_NAME,
        OWNER_HEADLINE,
        OWNER_LAST_NAME,
        OWNER_LOCATION,
        OWNER_PHONE,
        OWNER_SLUG,
        OWNER_SUMMARY,
        POSITIONS,
        SHORT_MESSAGES,
        SILENT_COMPANIES,
        SILENT_CONNECTION_NAMES,
        SILENT_POSITIONS,
        SKILLS,
        Contact,
    )
except ModuleNotFoundError as error:  # Backend invocation: python -m scripts.generate_...
    if error.name != "backend":
        raise
    from scripts.synthetic_archive_data import (  # type: ignore[assignment]
        CONNECTIONS_PREAMBLE,
        CONTACTS,
        CONTEXT_MESSAGES,
        FOLLOWED_COMPANIES,
        JOB_PREFERENCE_HEADERS,
        JOB_PREFERENCE_ROW,
        OWNER_EMAIL,
        OWNER_FIRST_NAME,
        OWNER_HEADLINE,
        OWNER_LAST_NAME,
        OWNER_LOCATION,
        OWNER_PHONE,
        OWNER_SLUG,
        OWNER_SUMMARY,
        POSITIONS,
        SHORT_MESSAGES,
        SILENT_COMPANIES,
        SILENT_CONNECTION_NAMES,
        SILENT_POSITIONS,
        SKILLS,
        Contact,
    )

DEFAULT_SEED = 20260830
DEFAULT_MESSAGE_COUNT = 480
MESSAGES_PER_THREAD = 3
MIN_THREAD_LENGTH = 2
MAX_THREAD_LENGTH = 12
OWNER_NAME = f"{OWNER_FIRST_NAME} {OWNER_LAST_NAME}"
OWNER_URL = f"https://www.linkedin.com/in/{OWNER_SLUG}"
FIRST_MESSAGE_AT = datetime(2025, 1, 6, 9, 15)
MESSAGE_HEADERS = (
    "CONVERSATION ID",
    "CONVERSATION TITLE",
    "FROM",
    "SENDER PROFILE URL",
    "TO",
    "RECIPIENT PROFILE URLS",
    "DATE",
    "SUBJECT",
    "CONTENT",
    "FOLDER",
    "ATTACHMENTS",
    "IS MESSAGE DRAFT",
    "IS CONVERSATION DRAFT",
)
INVITATION_HEADERS = (
    "From",
    "To",
    "Sent At",
    "Message",
    "Direction",
    "inviterProfileUrl",
    "inviteeProfileUrl",
)
CONNECTION_HEADERS = (
    "First Name",
    "Last Name",
    "URL",
    "Email Address",
    "Company",
    "Position",
    "Connected On",
)
PROFILE_HEADERS = (
    "First Name",
    "Last Name",
    "Maiden Name",
    "Address",
    "Birth Date",
    "Headline",
    "Summary",
    "Industry",
    "Zip Code",
    "Geo Location",
    "Twitter Handles",
    "Websites",
    "Instant Messengers",
)
POSITION_HEADERS = ("Company Name", "Title", "Description", "Location", "Started On", "Finished On")
COMPANY_HEADERS = ("Organization", "Followed On")
SKILL_HEADERS = ("Name",)
EMAIL_HEADERS = ("Email Address", "Confirmed", "Primary", "Updated On")
PHONE_HEADERS = ("Extension", "Number", "Type")


def generate_archive(
    output_dir: str | Path,
    *,
    seed: int = DEFAULT_SEED,
    message_count: int = DEFAULT_MESSAGE_COUNT,
) -> dict[str, int]:
    """Write the archive and return aggregate row counts per file."""

    if message_count < len(CONTACTS) * MIN_THREAD_LENGTH:
        raise ValueError("message_count must cover at least two messages per contact")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    counts = {
        "messages.csv": _write(
            output / "messages.csv", MESSAGE_HEADERS, _messages(rng, message_count)
        ),
        "Invitations.csv": _write(
            output / "Invitations.csv", INVITATION_HEADERS, _invitations(rng)
        ),
        "Profile.csv": _write(output / "Profile.csv", PROFILE_HEADERS, _profile()),
        "Positions.csv": _write(output / "Positions.csv", POSITION_HEADERS, POSITIONS),
        "Company Follows.csv": _write(
            output / "Company Follows.csv", COMPANY_HEADERS, _company_follows()
        ),
        "Skills.csv": _write(output / "Skills.csv", SKILL_HEADERS, ((skill,) for skill in SKILLS)),
        "Email Addresses.csv": _write(output / "Email Addresses.csv", EMAIL_HEADERS, _emails()),
        "PhoneNumbers.csv": _write(output / "PhoneNumbers.csv", PHONE_HEADERS, _phones()),
        "Connections.csv": _write(
            output / "Connections.csv",
            CONNECTION_HEADERS,
            _connections(rng),
            preamble=CONNECTIONS_PREAMBLE,
        ),
    }
    jobs = output / "Jobs"
    jobs.mkdir(exist_ok=True)
    counts["Jobs/Job Seeker Preferences.csv"] = _write(
        jobs / "Job Seeker Preferences.csv",
        JOB_PREFERENCE_HEADERS,
        (JOB_PREFERENCE_ROW,),
    )
    return counts


def _messages(rng: random.Random, message_count: int) -> tuple[tuple[str, ...], ...]:
    """Build threaded conversations whose lengths sum to ``message_count``."""

    threads = _thread_plan(rng, message_count)
    rows: list[tuple[datetime, tuple[str, ...]]] = []
    clock = FIRST_MESSAGE_AT
    for index, (contact, length) in enumerate(threads):
        conversation_id = f"2-{7000000 + index}"
        title = f"Product and crypto discussion with {contact.name}"
        clock += timedelta(days=rng.randint(3, 21), hours=rng.randint(0, 9))
        moment = clock
        for position in range(length):
            moment += timedelta(days=rng.randint(0, 4), hours=rng.randint(1, 20))
            outgoing = position % 2 == 1 if rng.random() < 0.75 else rng.random() < 0.5
            rows.append(
                (
                    moment,
                    _message_row(rng, contact, conversation_id, title, moment, position, outgoing),
                )
            )
    rows.sort(key=lambda item: (item[0], item[1][0]))
    return tuple(values for _, values in rows)


def _thread_plan(rng: random.Random, message_count: int) -> list[tuple[Contact, int]]:
    """Assign a message count to every thread, keeping the total exact.

    Real archives average roughly three messages per conversation, so the thread count is
    derived from the message budget instead of being fixed per contact.
    """

    thread_count = max(len(CONTACTS), message_count // MESSAGES_PER_THREAD)
    weights = [contact.threads for contact in CONTACTS]
    extras = rng.choices(CONTACTS, weights=weights, k=thread_count - len(CONTACTS))
    threads = list(CONTACTS) + extras
    # Each contact's first thread is long enough to hold its whole narrative opener.
    lengths = [
        max(MIN_THREAD_LENGTH, len(CONTEXT_MESSAGES.get(contact.slug, ())))
        if index < len(CONTACTS)
        else MIN_THREAD_LENGTH
        for index, contact in enumerate(threads)
    ]
    remaining = message_count - sum(lengths)
    if remaining < 0:
        raise ValueError("message_count is too small for the required thread count")
    if remaining > len(threads) * (MAX_THREAD_LENGTH - MIN_THREAD_LENGTH):
        raise ValueError("message_count exceeds what the thread plan can hold")
    while remaining > 0:
        index = rng.randrange(len(threads))
        if lengths[index] >= MAX_THREAD_LENGTH:
            continue
        lengths[index] += 1
        remaining -= 1
    return list(zip(threads, lengths, strict=True))


def _message_row(
    rng: random.Random,
    contact: Contact,
    conversation_id: str,
    title: str,
    moment: datetime,
    position: int,
    outgoing: bool,
) -> tuple[str, ...]:
    sender_name, sender_url = (
        (OWNER_NAME, OWNER_URL) if outgoing else (contact.name, contact.linkedin_url)
    )
    to_name, to_url = (contact.name, contact.linkedin_url) if outgoing else (OWNER_NAME, OWNER_URL)
    draft = outgoing and rng.random() < 0.02
    return (
        conversation_id,
        title,
        sender_name,
        sender_url,
        to_name,
        to_url,
        moment.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "Dubai product follow-up" if position == 0 and rng.random() < 0.2 else "",
        _content(rng, contact, position),
        "ARCHIVE" if rng.random() < 0.08 else "INBOX",
        "product-brief.pdf" if rng.random() < 0.01 else "",
        "Yes" if draft else "No",
        "No",
    )


def _content(rng: random.Random, contact: Contact, position: int) -> str:
    """Reproduce the real body-length spread, including empty and multi-paragraph bodies."""

    narrative = CONTEXT_MESSAGES.get(contact.slug, ())
    if position < len(narrative):
        return narrative[position]
    draw = rng.random()
    if draw < 0.10:
        return ""
    if draw < 0.14:
        return _long_content(contact)
    first = rng.choice(SHORT_MESSAGES)
    if draw < 0.45:
        return f"{first}\n\n{rng.choice(SHORT_MESSAGES)}"
    return first


def _long_content(contact: Contact) -> str:
    paragraph = (
        f"Notes for {contact.name}: the Dubai product opportunity needs a clear role scope, "
        "evidence from the hiring team, and a warm path that respects the relationship. "
        "We should separate verified openings from general expansion signals and record "
        "each decision with provenance."
    )
    return "\n\n".join(f"Section {index + 1}. {paragraph}" for index in range(6))


def _invitations(rng: random.Random) -> tuple[tuple[str, ...], ...]:
    """The owner is the sole inviter on every outgoing row, which identifies the owner URL."""

    rows: list[tuple[str, ...]] = []
    invitees = [(contact.name, contact.linkedin_url) for contact in CONTACTS]
    invitees += [
        (f"{first} {last}", _silent_url(first, last, index))
        for index, (first, last) in enumerate(SILENT_CONNECTION_NAMES)
    ]
    sent_at = datetime(2024, 9, 1, 9)
    for index, (name, url) in enumerate(invitees):
        incoming = index % 5 == 4
        sent_at += timedelta(days=rng.randint(2, 11), minutes=rng.randint(0, 59))
        message = "Good to connect after the Dubai product event." if index == 3 else ""
        rows.append(
            (
                name if incoming else OWNER_NAME,
                OWNER_NAME if incoming else name,
                sent_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                message,
                "INCOMING" if incoming else "OUTGOING",
                url if incoming else OWNER_URL,
                OWNER_URL if incoming else url,
            )
        )
    rng.shuffle(rows)
    return tuple(rows)


def _connections(rng: random.Random) -> tuple[tuple[str, ...], ...]:
    """Every messaging contact plus connections the owner never wrote to."""

    connected = datetime(2021, 3, 4)
    rows: list[tuple[str, ...]] = []
    for contact in CONTACTS:
        connected += timedelta(days=rng.randint(9, 60))
        rows.append(
            (
                contact.first_name,
                contact.last_name,
                contact.linkedin_url,
                f"{contact.slug}@example.test" if rng.random() < 0.4 else "",
                contact.company,
                contact.position,
                connected.strftime("%d %b %Y"),
            )
        )
    for index, (first, last) in enumerate(SILENT_CONNECTION_NAMES):
        connected += timedelta(days=rng.randint(4, 40))
        rows.append(
            (
                first,
                last,
                _silent_url(first, last, index),
                "",
                SILENT_COMPANIES[index % len(SILENT_COMPANIES)],
                SILENT_POSITIONS[index % len(SILENT_POSITIONS)],
                connected.strftime("%d %b %Y"),
            )
        )
    return tuple(rows)


def _silent_url(first: str, last: str, index: int) -> str:
    slug = f"{first}-{last}".casefold().replace(" ", "-")
    return f"https://www.linkedin.com/in/{slug}-{index + 1:05d}"


def _profile() -> tuple[tuple[str, ...], ...]:
    return (
        (
            OWNER_FIRST_NAME,
            OWNER_LAST_NAME,
            "",
            OWNER_LOCATION,
            "Aug 18, 1996",
            OWNER_HEADLINE,
            OWNER_SUMMARY,
            "Financial Services",
            "00000",
            OWNER_LOCATION,
            "",
            "[PERSONAL:https://maya-product.example]",
            "",
        ),
    )


def _company_follows() -> tuple[tuple[str, ...], ...]:
    return tuple(
        (company, f"{index + 1:02d}/15/25") for index, company in enumerate(FOLLOWED_COMPANIES)
    )


def _emails() -> tuple[tuple[str, ...], ...]:
    return ((OWNER_EMAIL, "Yes", "Yes", "2026-08-01 09:00:00 UTC"),)


def _phones() -> tuple[tuple[str, ...], ...]:
    return (("", OWNER_PHONE, "MOBILE"),)


def _write(
    path: Path,
    headers: Sequence[str],
    rows: Iterable[Sequence[str]],
    *,
    preamble: Sequence[Sequence[str]] = (),
) -> int:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerows(preamble)
        writer.writerow(headers)
        written = 0
        for row in rows:
            writer.writerow(row)
            written += 1
    return written


def _default_output() -> Path:
    return Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "synthetic_export"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=_default_output())
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--messages", type=int, default=DEFAULT_MESSAGE_COUNT)
    args = parser.parse_args(argv)
    counts = generate_archive(args.output, seed=args.seed, message_count=args.messages)
    print(f"generated_files={len(counts)} messages={counts['messages.csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
