"""Generate a deterministic Basic_LinkedInDataExport-style demo archive."""

from __future__ import annotations

import argparse
import csv
import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_SEED = 20260830
DEFAULT_MESSAGE_COUNT = 480
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


@dataclass(frozen=True, slots=True)
class SyntheticPerson:
    name: str
    role: str
    slug: str

    @property
    def linkedin_url(self) -> str:
        return f"https://www.linkedin.com/in/{self.slug}"


OWNER = SyntheticPerson(
    "Alex Ivanov", "marketing business, crypto side project", "alex-ivanov-demo"
)
CONTACTS = (
    SyntheticPerson("Marta", "VP Product, crypto infrastructure, Dubai", "marta-product-demo"),
    SyntheticPerson("Sergey Lapin", "CTO in an AI tech startup, Dubai", "sergey-lapin-demo"),
    SyntheticPerson("John", "Investor, digital assets, UAE", "john-investor-demo"),
    SyntheticPerson("Daniel Ruiz", "Ops lead, Palm Logistics, Dubai", "daniel-ruiz-demo"),
    SyntheticPerson("Nadia", "Growth lead, fintech", "nadia-growth-demo"),
    SyntheticPerson("Omar", "Product designer, Dubai", "omar-design-demo"),
    SyntheticPerson("Lena", "Founder, climate software", "lena-founder-demo"),
    SyntheticPerson("Tom", "Engineering manager, payments", "tom-engineering-demo"),
    SyntheticPerson("Ruth", "Recruiter, emerging technology", "ruth-recruiter-demo"),
)

_DATE_RANGES = {
    "Marta": (datetime(2025, 10, 20, 9), datetime(2025, 12, 30, 16)),
    "Sergey Lapin": (datetime(2026, 8, 2, 10), datetime(2026, 8, 29, 18)),
    "John": (datetime(2026, 3, 4, 8), datetime(2026, 8, 28, 15)),
    "Daniel Ruiz": (datetime(2026, 5, 5, 11), datetime(2026, 8, 24, 14)),
    "Nadia": (datetime(2026, 1, 8, 9), datetime(2026, 6, 18, 13)),
    "Omar": (datetime(2026, 2, 12, 12), datetime(2026, 7, 21, 17)),
    "Lena": (datetime(2025, 11, 3, 14), datetime(2026, 5, 16, 11)),
    "Tom": (datetime(2026, 1, 19, 8), datetime(2026, 6, 30, 16)),
    "Ruth": (datetime(2025, 12, 7, 10), datetime(2026, 7, 9, 9)),
}
_SHORT_MESSAGES = (
    "Quick follow-up on the Dubai product conversation. Are you free next week?",
    "Thanks, this is useful context. I will review it and send a concise update.",
    "The crypto infrastructure angle makes sense. Let us compare notes on Thursday.",
    "Good point about the UAE market. The product team should validate that assumption.",
    "I can make an introduction after the roadmap review. Does Tuesday afternoon work?",
    "That hiring signal sounds relevant. Please send the role scope when it is ready.",
    "Agreed. A short call is enough, then we can decide whether to involve the team.",
    "The launch plan is moving. I have one question about positioning and distribution.",
    "Let us keep this practical: market, role, location, and the right warm introduction.",
    "Appreciate the update. Dubai remains the priority and product leadership is the fit.",
    "Makes sense. I will share the notes after I speak with the digital assets team.",
    "Yes, please send it over. I can review the product brief before the weekend.",
)
_CONTEXT_MESSAGES = {
    "Marta": (
        "It was great meeting at TOKEN2049. Alex introduced us after the product panel.",
        "The Dubai crypto infrastructure team is shaping a VP Product hiring plan.",
        "Eight months since our last contact already. I would value a quick reconnection.",
    ),
    "Sergey Lapin": (
        "Great meeting at the AI meetup in Dubai. The technical discussion was useful.",
        "The mutual NDA is signed for three years; we can continue product scoping.",
        "We are discussing UAE expansion and hiring for the AI product team.",
    ),
    "John": (
        "Several digital assets portfolio companies are hiring product talent in Dubai.",
        "Happy to make a warm introduction. We have a strong relationship to work from.",
    ),
    "Daniel Ruiz": (
        "Following up from our WhatsApp chat about operations at Palm Logistics.",
        "I sent the Palm Logistics role details to your Gmail so the context stays handy.",
        "Palm Logistics posted the Dubai marketing lead role six days ago.",
    ),
}


def generate_archive(
    output_dir: str | Path,
    *,
    seed: int = DEFAULT_SEED,
    message_count: int = DEFAULT_MESSAGE_COUNT,
) -> dict[str, int]:
    """Write the archive and return aggregate row counts."""

    if message_count < len(CONTACTS):
        raise ValueError("message_count must cover every synthetic contact")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    messages = _message_rows(rng, message_count)
    invitations = _invitation_rows(rng)
    datasets: tuple[tuple[str, Sequence[str], Iterable[Sequence[str]]], ...] = (
        ("messages.csv", MESSAGE_HEADERS, messages),
        ("Invitations.csv", INVITATION_HEADERS, invitations),
        ("Profile.csv", _PROFILE_HEADERS, _profile_rows()),
        ("Positions.csv", _POSITION_HEADERS, _position_rows()),
        ("Company Follows.csv", _COMPANY_HEADERS, _company_rows()),
        ("Skills.csv", _SKILL_HEADERS, _skill_rows()),
        ("Email Addresses.csv", _EMAIL_HEADERS, _email_rows()),
        ("PhoneNumbers.csv", _PHONE_HEADERS, _phone_rows()),
    )
    counts: dict[str, int] = {}
    for filename, headers, rows in datasets:
        materialized = tuple(rows)
        _write_csv(output / filename, headers, materialized)
        counts[filename] = len(materialized)
    connections = output / "Connections.csv"
    if connections.exists():
        connections.unlink()
    return counts


def _message_rows(rng: random.Random, message_count: int) -> tuple[tuple[str, ...], ...]:
    per_contact = _distribute(message_count, len(CONTACTS))
    rows: list[tuple[datetime, tuple[str, ...]]] = []
    global_index = 0
    for contact_index, (contact, count) in enumerate(zip(CONTACTS, per_contact, strict=True)):
        for occurrence in range(count):
            occurred_at = _interpolated_date(contact.name, occurrence, count)
            content = _message_content(rng, contact, contact_index, occurrence, count, global_index)
            outgoing = rng.random() < 0.58
            sender, recipient = (OWNER, contact) if outgoing else (contact, OWNER)
            folder = "ARCHIVE" if global_index % 13 == 0 else "INBOX"
            if global_index % 41 == 0:
                folder = ""
            subject = "Dubai product follow-up" if global_index % 37 == 0 else ""
            attachment = "product-brief.pdf" if global_index % 113 == 0 else ""
            values = (
                f"synthetic-thread-{contact_index + 1:02d}",
                f"{OWNER.name} and {contact.name}",
                sender.name,
                sender.linkedin_url,
                recipient.name,
                recipient.linkedin_url,
                occurred_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                subject,
                content,
                folder,
                attachment,
            )
            rows.append((occurred_at, values))
            global_index += 1
    rows.sort(key=lambda item: (item[0], item[1][0], item[1][2]))
    return tuple(values for _, values in rows)


def _message_content(
    rng: random.Random,
    contact: SyntheticPerson,
    contact_index: int,
    occurrence: int,
    count: int,
    global_index: int,
) -> str:
    contextual = _CONTEXT_MESSAGES.get(contact.name, ())
    if occurrence < len(contextual):
        return contextual[occurrence]
    if contact.name == "Marta" and occurrence == count - 1:
        return _CONTEXT_MESSAGES["Marta"][-1]
    if contact.name == "Daniel Ruiz" and occurrence == count - 1:
        return "Following up on WhatsApp: Palm Logistics posted the role six days ago."
    if (contact_index, occurrence) in {(0, 15), (1, 20), (2, 25)}:
        return _long_message(contact)
    if global_index % 11 == 3:
        return ""
    first = rng.choice(_SHORT_MESSAGES)
    if global_index % 17 == 0:
        second = rng.choice(_SHORT_MESSAGES)
        return f"{first}\n\n{second}"
    return first


def _long_message(contact: SyntheticPerson) -> str:
    paragraph = (
        f"Notes for {contact.name}: the Dubai product opportunity needs a clear role scope, "
        "evidence from the hiring team, and a warm path that respects the relationship. "
        "We should separate verified openings from general expansion signals, review the "
        "crypto and digital assets context, and record each decision with provenance."
    )
    sections = [f"Section {index + 1}. {paragraph}" for index in range(12)]
    content = "\n\n".join(sections)
    filler = " The next step is a focused conversation with the product owner."
    while len(content) < 3_300:
        content += filler
    return content[:3_480]


def _invitation_rows(rng: random.Random) -> tuple[tuple[str, ...], ...]:
    rows: list[tuple[str, ...]] = []
    invitees = CONTACTS + tuple(
        SyntheticPerson(f"Invitee {index:02d}", "extended network", f"invitee-{index:02d}-demo")
        for index in range(1, 52)
    )
    for index, person in enumerate(invitees):
        incoming = index >= len(invitees) - 5
        sender, recipient = (person, OWNER) if incoming else (OWNER, person)
        sent_at = datetime(2025, 9, 1, 9) + timedelta(days=index * 4, hours=index % 7)
        message = "Good to connect after the Dubai product event." if index == 7 else ""
        rows.append(
            (
                sender.name,
                recipient.name,
                sent_at.strftime("%m/%d/%y, %I:%M %p"),
                message,
                "INCOMING" if incoming else "OUTGOING",
                sender.linkedin_url,
                recipient.linkedin_url,
            )
        )
    rng.shuffle(rows)
    return tuple(rows)


def _distribute(total: int, groups: int) -> tuple[int, ...]:
    quotient, remainder = divmod(total, groups)
    return tuple(quotient + (index < remainder) for index in range(groups))


def _interpolated_date(name: str, occurrence: int, count: int) -> datetime:
    start, finish = _DATE_RANGES[name]
    if count == 1:
        return finish
    ratio = occurrence / (count - 1)
    return start + (finish - start) * ratio


def _write_csv(path: Path, headers: Sequence[str], rows: Iterable[Sequence[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)


_PROFILE_HEADERS = (
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
    "Profile URL",
)
_POSITION_HEADERS = (
    "Company Name",
    "Title",
    "Description",
    "Location",
    "Started On",
    "Finished On",
)
_COMPANY_HEADERS = ("Organization", "Followed On")
_SKILL_HEADERS = ("Name",)
_EMAIL_HEADERS = ("Email Address", "Confirmed", "Primary", "Updated On")
_PHONE_HEADERS = ("Extension", "Number", "Type")


def _profile_rows() -> tuple[tuple[str, ...], ...]:
    return (
        (
            "Alex",
            "Ivanov",
            "",
            "Dubai, UAE",
            "",
            OWNER.role,
            "Building a marketing business and a crypto side project.",
            "Marketing and Advertising",
            "",
            "Dubai",
            "",
            "https://alex-ivanov.example",
            "",
            OWNER.linkedin_url,
        ),
    )


def _position_rows() -> tuple[tuple[str, ...], ...]:
    return (
        ("Ivanov Marketing", "Founder", "Marketing business", "Dubai", "Jan 2022", ""),
        ("Crypto Side Project", "Co-founder", "Product and go-to-market", "Dubai", "Mar 2025", ""),
    )


def _company_rows() -> tuple[tuple[str, ...], ...]:
    return tuple(
        (company, f"{month:02d}/15/25")
        for month, company in enumerate(
            ("Palm Logistics", "Dubai Future Foundation", "Company X", "Company Z"),
            start=1,
        )
    )


def _skill_rows() -> tuple[tuple[str, ...], ...]:
    return tuple(
        (skill,)
        for skill in ("Product Marketing", "Crypto", "Go-to-Market", "Partnerships", "Strategy")
    )


def _email_rows() -> tuple[tuple[str, ...], ...]:
    return (("alex.ivanov@example.test", "Yes", "Yes", "08/01/26"),)


def _phone_rows() -> tuple[tuple[str, ...], ...]:
    return (("", "+971 50 555 0101", "Mobile"),)


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
