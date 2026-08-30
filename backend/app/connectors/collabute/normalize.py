"""Turn Collabute tool results into normalized meeting records, tolerantly.

The tool *names* are pinned by a captured fixture, but the *item* shapes inside
``meeting.list_recent`` are not: the workspace was empty when the fixture was taken, so no
real meeting payload has ever been observed. Every field here is therefore read through an
alias list and every absence is allowed. A meeting with only an id and a time still imports;
it just carries less evidence, which is the honest outcome.

Results arrive either as ``structuredContent`` or as ``content[]`` text blocks that may hold
JSON, so both are unwrapped before any field is read.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.connectors.base import NormalizedParticipant, NormalizedRecord
from app.domain.identity.normalize import IdentityKind

SOURCE = "collabute"
ID_KEYS = ("id", "meetingId", "meeting_id", "uuid", "externalId")
TITLE_KEYS = ("title", "name", "subject", "summaryTitle")
TIME_KEYS = (
    "startTime",
    "start_time",
    "startedAt",
    "scheduledAt",
    "occurredAt",
    "date",
    "createdAt",
)
SUMMARY_KEYS = ("summary", "notes", "overview", "description", "abstract")
PARTICIPANT_KEYS = ("participants", "attendees", "members", "speakers")
DECISION_KEYS = ("decisions", "keyDecisions", "key_decisions")
ACTION_KEYS = ("actionItems", "action_items", "tasks", "todos", "followUps", "follow_ups")
EMAIL_KEYS = ("email", "emailAddress", "mail")
NAME_KEYS = ("name", "displayName", "fullName", "speaker", "label")
TEXT_KEYS = ("text", "title", "description", "content", "task", "summary")
OWNER_KEYS = ("owner", "assignee", "assignedTo", "responsible", "ownerName")
STATUS_KEYS = ("status", "state")


@dataclass(frozen=True, slots=True)
class ActionItem:
    """One action item plus the stable key that keeps re-syncs from duplicating it."""

    text: str
    owner: str | None
    source_key: str


def unwrap(result: dict) -> Any:
    """Return the payload a tool actually carried, whichever transport shape it used."""

    structured = result.get("structuredContent")
    if isinstance(structured, dict | list):
        return structured
    for block in result.get("content") or []:
        if not isinstance(block, dict) or block.get("type") != "text":
            continue
        text = block.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        try:
            return json.loads(text)
        except ValueError:
            return {"text": text}
    return {}


def meeting_items(payload: Any) -> list[dict]:
    """Find the meeting list inside an envelope whose key name is not guaranteed."""

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "meetings", "results", "data", "records"):
        candidate = payload.get(key)
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return [payload] if _first(payload, ID_KEYS) else []


def meeting_id(raw: dict) -> str:
    return _first(raw, ID_KEYS) or ""


def normalize_meeting(raw: dict) -> NormalizedRecord | None:
    """Build one interaction from a meeting, or nothing if it has no usable identity."""

    external_id = meeting_id(raw)
    occurred_at = _timestamp(raw)
    if not external_id or occurred_at is None:
        return None
    actions = list(action_items(raw, external_id))
    return NormalizedRecord(
        external_id=external_id,
        type="meeting",
        source=SOURCE,
        occurred_at=occurred_at,
        direction=None,
        subject=_first(raw, TITLE_KEYS) or None,
        body_text=_body(raw),
        participants=tuple(participants(raw)),
        metadata={
            "status": _first(raw, STATUS_KEYS),
            "decisions": _strings(raw, DECISION_KEYS),
            "action_items": [
                {"text": item.text, "owner": item.owner, "source_key": item.source_key}
                for item in actions
            ],
            "provider": SOURCE,
        },
        raw_ref=f"collabute://meeting/{external_id}",
    )


def participants(raw: dict) -> Iterator[NormalizedParticipant]:
    """Emit one participant per attendee, keeping unresolvable names as plain addresses."""

    seen: set[str] = set()
    for entry in _participant_entries(raw):
        email = _first(entry, EMAIL_KEYS) if isinstance(entry, dict) else None
        name = _first(entry, NAME_KEYS) if isinstance(entry, dict) else str(entry).strip()
        address = (email or name or "").casefold()
        if not address or address in seen:
            continue
        seen.add(address)
        yield NormalizedParticipant(
            source_address=address,
            role="attendee",
            display_name=name or None,
            identity_hint={IdentityKind.EMAIL.value: email} if email else {},
        )


def action_items(raw: dict, external_id: str) -> Iterator[ActionItem]:
    """Yield action items with a stable key: the provider's id, else a content hash.

    The hash is what makes two consecutive syncs produce one follow-up rather than two when
    Collabute supplies no identifier of its own.
    """

    for entry in _collect(raw, ACTION_KEYS):
        if isinstance(entry, str):
            text, owner, stable = entry.strip(), None, None
        elif isinstance(entry, dict):
            text = _first(entry, TEXT_KEYS) or ""
            owner = _owner_name(entry)
            stable = _first(entry, ID_KEYS)
        else:
            continue
        if not text:
            continue
        yield ActionItem(text=text, owner=owner, source_key=stable or _hash(external_id, text))


def _owner_name(entry: dict) -> str | None:
    for key in OWNER_KEYS:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = _first(value, (*NAME_KEYS, *EMAIL_KEYS))
            if nested:
                return nested
    return None


def _participant_entries(raw: dict) -> list:
    entries = _collect(raw, PARTICIPANT_KEYS)
    return [item for item in entries if isinstance(item, dict | str)]


def _collect(raw: dict, keys: tuple[str, ...]) -> list:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, list):
            return value
    return []


def _strings(raw: dict, keys: tuple[str, ...]) -> list[str]:
    collected = []
    for entry in _collect(raw, keys):
        if isinstance(entry, str) and entry.strip():
            collected.append(entry.strip())
        elif isinstance(entry, dict):
            text = _first(entry, TEXT_KEYS)
            if text:
                collected.append(text)
    return collected


def _body(raw: dict) -> str | None:
    """Compose the searchable body from summary and decisions, since both are evidence."""

    parts = [_first(raw, SUMMARY_KEYS) or ""]
    decisions = _strings(raw, DECISION_KEYS)
    if decisions:
        parts.append("Decisions:\n" + "\n".join(f"- {item}" for item in decisions))
    text = "\n\n".join(part for part in parts if part).strip()
    return text or None


def _timestamp(raw: dict) -> datetime | None:
    for key in TIME_KEYS:
        value = raw.get(key)
        parsed = _parse_time(value)
        if parsed is not None:
            return parsed
    return None


def _parse_time(value: object) -> datetime | None:
    if isinstance(value, int | float) and value > 0:
        seconds = value / 1000 if value > 1e11 else value
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _first(raw: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int | float) and not isinstance(value, bool):
            return str(value)
    return None


def _hash(external_id: str, text: str) -> str:
    normalized = " ".join(text.split()).casefold()
    digest = hashlib.sha256(f"{external_id}\n{normalized}".encode()).hexdigest()
    return f"sha256:{digest[:32]}"
