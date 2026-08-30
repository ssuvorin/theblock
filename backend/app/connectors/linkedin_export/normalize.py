"""Normalize LinkedIn export rows into immutable ingestion records."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

from ...domain.identity.normalize import canonicalize_linkedin_url
from .parse import field, parse_invitation_date, parse_message_date

LINKEDIN_SOURCE = "linkedin_export"
_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:[a-z0-9-]+\.)*linkedin\.com/[a-z0-9_~%+./@:-]+",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class NormalizedParticipant:
    display_name: str
    source_address: str
    profile_url: str | None
    role: str


@dataclass(frozen=True, slots=True)
class NormalizedMessage:
    external_id: str
    conversation_external_id: str
    conversation_type: str
    occurred_at: datetime
    direction: str | None
    subject: str | None
    body_text: str
    folder: str | None
    attachments: str | None
    sender: NormalizedParticipant
    recipients: tuple[NormalizedParticipant, ...]
    data_origin: str

    @property
    def is_chunkable(self) -> bool:
        return bool(self.body_text.strip())


@dataclass(frozen=True, slots=True)
class IdentityHint:
    kind: str
    raw_value: str
    normalized_value: str
    source: str
    evidence: str


@dataclass(frozen=True, slots=True)
class NormalizedInvitation:
    sent_on: date
    direction: str
    from_name: str
    to_name: str
    message: str | None
    identity_hints: tuple[IdentityHint, ...]
    data_origin: str


@dataclass(frozen=True, slots=True)
class NormalizedOwnerProfile:
    display_name: str
    profile_url: str | None
    headline: str | None
    data_origin: str


def deterministic_external_id(
    conversation_id: str,
    message_date: str | datetime,
    sender_url: str,
    content: str | None,
) -> str:
    """Hash conversation, date, sender URL, and a content hash deterministically."""

    date_value = (
        message_date.isoformat() if isinstance(message_date, datetime) else message_date.strip()
    )
    canonical_sender = canonicalize_linkedin_url(sender_url) if sender_url.strip() else ""
    content_hash = hashlib.sha256((content or "").encode("utf-8")).hexdigest()
    material = "\x1f".join((conversation_id.strip(), date_value, canonical_sender, content_hash))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def normalize_message(
    row: Mapping[str, str],
    *,
    owner_profile_url: str | None,
    data_origin: str,
) -> NormalizedMessage:
    conversation_id = field(row, "CONVERSATION ID").strip()
    raw_date = field(row, "DATE")
    content = field(row, "CONTENT")
    sender_name = field(row, "FROM").strip()
    raw_sender_url = field(row, "SENDER PROFILE URL").strip()
    sender_url = _canonical_optional_url(raw_sender_url)
    recipient_names = _split_names(field(row, "TO"))
    raw_recipient_urls = _extract_urls(field(row, "RECIPIENT PROFILE URLS"))
    recipient_urls = tuple(_canonical_optional_url(value) for value in raw_recipient_urls)
    recipients = _recipient_participants(recipient_names, raw_recipient_urls, recipient_urls)
    direction = _direction(sender_url, owner_profile_url, recipient_urls)
    return NormalizedMessage(
        external_id=deterministic_external_id(
            conversation_id,
            raw_date,
            raw_sender_url,
            content,
        ),
        conversation_external_id=conversation_id,
        conversation_type="linkedin_thread",
        occurred_at=parse_message_date(raw_date),
        direction=direction,
        subject=field(row, "SUBJECT").strip() or None,
        body_text=content,
        folder=field(row, "FOLDER").strip() or None,
        attachments=field(row, "ATTACHMENTS").strip() or None,
        sender=NormalizedParticipant(sender_name, sender_name, sender_url, "sender"),
        recipients=recipients,
        data_origin=data_origin,
    )


def normalize_invitation(
    row: Mapping[str, str],
    *,
    data_origin: str,
) -> NormalizedInvitation:
    raw_urls = (
        field(row, "inviterProfileUrl", "INVITER PROFILE URL").strip(),
        field(row, "inviteeProfileUrl", "INVITEE PROFILE URL").strip(),
    )
    hints = tuple(_identity_hint(url, "invitation") for url in raw_urls if url)
    direction = field(row, "Direction", "DIRECTION").strip().upper()
    return NormalizedInvitation(
        sent_on=parse_invitation_date(field(row, "Sent At", "SENT AT", "DATE")),
        direction=direction,
        from_name=field(row, "From", "FROM").strip(),
        to_name=field(row, "To", "TO").strip(),
        message=field(row, "Message", "MESSAGE").strip() or None,
        identity_hints=hints,
        data_origin=data_origin,
    )


def normalize_owner_profile(
    row: Mapping[str, str],
    *,
    data_origin: str,
    resolved_profile_url: str | None = None,
) -> NormalizedOwnerProfile:
    """Build the owner profile, preferring an externally resolved URL.

    ``Profile.csv`` usually has no URL column at all, so the caller resolves the owner URL
    from message and invitation evidence and passes it in here.
    """

    first_name = field(row, "First Name", "FIRST NAME").strip()
    last_name = field(row, "Last Name", "LAST NAME").strip()
    display_name = " ".join(part for part in (first_name, last_name) if part)
    raw_profile_url = field(
        row,
        "Profile URL",
        "LinkedIn Profile URL",
        "Public Profile URL",
    ).strip()
    profile_url = _canonical_optional_url(resolved_profile_url or raw_profile_url)
    return NormalizedOwnerProfile(
        display_name=display_name,
        profile_url=profile_url,
        headline=field(row, "Headline", "HEADLINE").strip() or None,
        data_origin=data_origin,
    )


def message_identity_hints(message: NormalizedMessage) -> tuple[IdentityHint, ...]:
    participants = (message.sender, *message.recipients)
    return tuple(
        _identity_hint(participant.profile_url, "message")
        for participant in participants
        if participant.profile_url
    )


def _identity_hint(raw_url: str, evidence: str) -> IdentityHint:
    return IdentityHint(
        kind="linkedin_url",
        raw_value=raw_url,
        normalized_value=canonicalize_linkedin_url(raw_url),
        source=LINKEDIN_SOURCE,
        evidence=evidence,
    )


def _direction(
    sender_url: str | None,
    owner_url: str | None,
    recipient_urls: tuple[str | None, ...] = (),
) -> str | None:
    """Classify a message relative to the owner.

    LinkedIn omits the sender URL for restricted or deleted accounts. The owner appearing
    among the recipients still proves the message was received, so direction survives.
    """

    if not owner_url:
        return None
    if sender_url:
        return "outgoing" if sender_url == owner_url else "incoming"
    return "incoming" if owner_url in recipient_urls else None


def _extract_urls(value: str) -> tuple[str, ...]:
    matches = tuple(match.group(0).rstrip(".,") for match in _URL_PATTERN.finditer(value))
    if matches:
        return matches
    return tuple(part.strip() for part in re.split(r"[;,]", value) if part.strip())


def _split_names(value: str) -> tuple[str, ...]:
    if ";" in value:
        return tuple(part.strip() for part in value.split(";") if part.strip())
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _recipient_participants(
    names: tuple[str, ...],
    raw_urls: tuple[str, ...],
    urls: tuple[str | None, ...],
) -> tuple[NormalizedParticipant, ...]:
    count = max(len(names), len(urls))
    recipients: list[NormalizedParticipant] = []
    for index in range(count):
        name = names[index] if index < len(names) else ""
        url = urls[index] if index < len(urls) else None
        raw_url = raw_urls[index] if index < len(raw_urls) else ""
        recipients.append(NormalizedParticipant(name, name or raw_url, url, "recipient"))
    return tuple(recipients)


def _canonical_optional_url(value: str | None) -> str | None:
    return canonicalize_linkedin_url(value) if value else None
