"""Resolve which profile URL belongs to the archive owner.

``Profile.csv`` names the owner but carries no profile URL, while ``messages.csv`` keys
every participant by URL. Direction and reciprocity therefore depend on deriving the
owner URL from corroborating evidence instead of trusting a column LinkedIn omits.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .parse import field

DOMINANT_SENDER_SHARE = 0.25


@dataclass(frozen=True, slots=True)
class OwnerResolution:
    profile_url: str | None
    method: str
    confidence: str
    corroborated_by: tuple[str, ...]

    @property
    def resolved(self) -> bool:
        return self.profile_url is not None


def owner_display_name(profile_row: Mapping[str, str] | None) -> str:
    if not profile_row:
        return ""
    first = field(profile_row, "First Name", "FIRST NAME").strip()
    last = field(profile_row, "Last Name", "LAST NAME").strip()
    return " ".join(part for part in (first, last) if part)


def declared_profile_url(profile_row: Mapping[str, str] | None) -> str | None:
    """Read a profile URL only when the export actually provides one."""

    if not profile_row:
        return None
    value = field(
        profile_row,
        "Profile URL",
        "LinkedIn Profile URL",
        "Public Profile URL",
    ).strip()
    return value or None


def invitation_owner_url(invitation_rows: Sequence[Mapping[str, str]]) -> str | None:
    """An owner is the inviter of every outgoing invitation, so one URL must dominate."""

    urls = {
        field(row, "inviterProfileUrl", "INVITER PROFILE URL").strip()
        for row in invitation_rows
        if field(row, "Direction", "DIRECTION").strip().upper() == "OUTGOING"
    }
    urls.discard("")
    return next(iter(urls)) if len(urls) == 1 else None


def named_sender_url(
    message_rows: Sequence[Mapping[str, str]],
    display_name: str,
) -> str | None:
    """Match the Profile.csv name against message senders to recover the owner URL."""

    if not display_name:
        return None
    target = _normalized(display_name)
    urls = {
        field(row, "SENDER PROFILE URL").strip()
        for row in message_rows
        if _normalized(field(row, "FROM")) == target
    }
    urls.discard("")
    return next(iter(urls)) if len(urls) == 1 else None


def dominant_sender_url(message_rows: Sequence[Mapping[str, str]]) -> str | None:
    """Fall back to the most prolific sender when it clearly outweighs the rest."""

    counts = Counter(
        url for url in (field(row, "SENDER PROFILE URL").strip() for row in message_rows) if url
    )
    if not counts:
        return None
    (url, hits), *_ = counts.most_common(1)
    total = sum(counts.values())
    return url if total and hits / total >= DOMINANT_SENDER_SHARE else None


def resolve_owner_url(
    profile_row: Mapping[str, str] | None,
    message_rows: Sequence[Mapping[str, str]],
    invitation_rows: Sequence[Mapping[str, str]],
) -> OwnerResolution:
    """Prefer declared, then invitation, then named-sender, then dominant-sender evidence."""

    declared = declared_profile_url(profile_row)
    from_invitations = invitation_owner_url(invitation_rows)
    from_name = named_sender_url(message_rows, owner_display_name(profile_row))
    candidates = {
        "profile_url": declared,
        "invitations": from_invitations,
        "profile_name": from_name,
    }
    for method in ("profile_url", "invitations", "profile_name"):
        chosen = candidates[method]
        if chosen is None:
            continue
        agreeing = tuple(
            name for name, value in candidates.items() if name != method and value == chosen
        )
        confidence = "high" if agreeing else "medium"
        return OwnerResolution(chosen, method, confidence, agreeing)
    dominant = dominant_sender_url(message_rows)
    if dominant is not None:
        return OwnerResolution(dominant, "dominant_sender", "low", ())
    return OwnerResolution(None, "unresolved", "none", ())


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()
