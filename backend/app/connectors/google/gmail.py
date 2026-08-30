"""Gmail read-only sync: bounded initial import, then historyId deltas.

Two rules shape this file. The initial import is bounded by a lookback window and the
cursor is snapshotted *before* it starts, so nothing that arrives mid-import can slip
between the two phases. And an expired history cursor is a bounded resync, never an
unbounded mailbox download — Google's 404 is caught and translated, not retried.
"""

from __future__ import annotations

import base64
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from email.utils import getaddresses, parsedate_to_datetime

from app.connectors.base import CursorInvalidated, NormalizedParticipant, NormalizedRecord
from app.connectors.google.api import GMAIL_ROOT, GoogleApi, GoogleApiError
from app.domain.identity.normalize import IdentityKind
from app.models import utcnow

SOURCE = "gmail"
SURFACE = "gmail"
PAGE_SIZE = 100
BODY_LIMIT = 20_000
CURSOR_DEAD_STATUS = 404
ROLE_HEADERS = (("To", "recipient"), ("Cc", "cc"), ("Bcc", "bcc"))


class GmailSurface:
    """Page Gmail into normalized records without deciding what a person is."""

    source = SOURCE
    surface = SURFACE

    def __init__(self, api: GoogleApi, account: str, lookback_days: int, page_limit: int) -> None:
        self._api = api
        self._account = account.casefold()
        self._lookback_days = lookback_days
        self._page_limit = page_limit

    def snapshot_cursor(self) -> str:
        """Record where deltas will resume before the initial import reads anything."""

        profile = self._api.get(f"{GMAIL_ROOT}/profile")
        return str(profile.get("historyId") or "")

    def initial(self) -> Iterator[tuple[tuple[NormalizedRecord, ...], str]]:
        history_id = self.snapshot_cursor()
        after = int((utcnow() - timedelta(days=self._lookback_days)).timestamp())
        params = {"q": f"after:{after}", "maxResults": PAGE_SIZE}
        for page in self._pages(f"{GMAIL_ROOT}/messages", params):
            ids = [str(item.get("id")) for item in page.get("messages") or [] if item.get("id")]
            yield self._hydrate(ids), history_id

    def delta(self, history_id: str) -> Iterator[tuple[tuple[NormalizedRecord, ...], str]]:
        params = {
            "startHistoryId": history_id,
            "historyTypes": "messageAdded",
            "maxResults": PAGE_SIZE,
        }
        latest = history_id
        for page in self._pages(f"{GMAIL_ROOT}/history", params, dead_cursor=True):
            latest = str(page.get("historyId") or latest)
            yield self._hydrate(_added_message_ids(page)), latest

    def _pages(
        self,
        url: str,
        params: dict,
        *,
        dead_cursor: bool = False,
    ) -> Iterator[dict]:
        """Walk pageToken links up to a hard page budget so one sync cannot run forever."""

        token: str | None = None
        for _ in range(self._page_limit):
            query = dict(params)
            if token:
                query["pageToken"] = token
            try:
                page = self._api.get(url, query)
            except GoogleApiError as error:
                if dead_cursor and error.status_code == CURSOR_DEAD_STATUS:
                    raise CursorInvalidated(
                        "Gmail history cursor expired; a bounded resync is required",
                        SURFACE,
                    ) from error
                raise
            yield page
            token = page.get("nextPageToken")
            if not token:
                return

    def _hydrate(self, message_ids: list[str]) -> tuple[NormalizedRecord, ...]:
        records = []
        for message_id in message_ids:
            try:
                payload = self._api.get(f"{GMAIL_ROOT}/messages/{message_id}", {"format": "full"})
            except GoogleApiError as error:
                # A message deleted between listing and fetching is not a sync failure.
                if error.status_code in {403, 404}:
                    continue
                raise
            record = self._normalize(payload)
            if record is not None:
                records.append(record)
        return tuple(records)

    def _normalize(self, payload: dict) -> NormalizedRecord | None:
        message_id = str(payload.get("id") or "")
        if not message_id:
            return None
        headers = _headers(payload.get("payload") or {})
        participants = tuple(_participants(headers))
        sender = _first_address(headers.get("from", ""))
        return NormalizedRecord(
            external_id=message_id,
            type="email",
            source=SOURCE,
            occurred_at=_occurred_at(payload, headers),
            direction="outgoing" if sender == self._account else "incoming",
            subject=headers.get("subject") or None,
            body_text=_body_text(payload.get("payload") or {}),
            participants=participants,
            metadata={
                "thread_id": payload.get("threadId"),
                "labels": payload.get("labelIds") or [],
                "attachments": _attachment_names(payload.get("payload") or {}),
                "account": self._account,
            },
            raw_ref=f"gmail://{self._account}/{message_id}",
        )


def _headers(part: dict) -> dict[str, str]:
    """Lowercase header names once; Gmail's casing is not guaranteed."""

    return {
        str(item.get("name", "")).casefold(): str(item.get("value", ""))
        for item in part.get("headers") or []
    }


def _participants(headers: dict[str, str]) -> Iterator[NormalizedParticipant]:
    for name, address in getaddresses([headers.get("from", "")]):
        yield _participant(name, address, "sender")
    for header, role in ROLE_HEADERS:
        for name, address in getaddresses([headers.get(header.casefold(), "")]):
            yield _participant(name, address, role)


def _participant(name: str, address: str, role: str) -> NormalizedParticipant:
    return NormalizedParticipant(
        source_address=address.casefold(),
        role=role,
        display_name=name.strip() or None,
        identity_hint={IdentityKind.EMAIL.value: address} if address else {},
    )


def _first_address(value: str) -> str:
    addresses = [address for _, address in getaddresses([value]) if address]
    return addresses[0].casefold() if addresses else ""


def _occurred_at(payload: dict, headers: dict[str, str]) -> datetime:
    """Prefer Gmail's internalDate: the Date header is attacker-supplied and often wrong."""

    internal = payload.get("internalDate")
    if internal:
        try:
            return datetime.fromtimestamp(int(internal) / 1000, tz=UTC)
        except (TypeError, ValueError):
            pass
    raw_date = headers.get("date")
    if raw_date:
        try:
            parsed = parsedate_to_datetime(raw_date)
        except (TypeError, ValueError):
            parsed = None
        if parsed is not None:
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return utcnow()


def _body_text(part: dict) -> str | None:
    text = _walk_for_text(part)
    if text is None:
        return None
    collapsed = text.replace("\r\n", "\n").strip()
    return collapsed[:BODY_LIMIT] or None


def _walk_for_text(part: dict) -> str | None:
    if part.get("mimeType") == "text/plain":
        decoded = _decode(part.get("body") or {})
        if decoded:
            return decoded
    for child in part.get("parts") or []:
        found = _walk_for_text(child)
        if found:
            return found
    if not part.get("parts") and part.get("mimeType", "").startswith("text/"):
        return _decode(part.get("body") or {})
    return None


def _decode(body: dict) -> str | None:
    data = body.get("data")
    if not isinstance(data, str) or not data:
        return None
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return None


def _attachment_names(part: dict) -> list[str]:
    """Attachment names only. P0 never downloads attachment content."""

    names = []
    for child in part.get("parts") or []:
        if child.get("filename"):
            names.append(str(child["filename"]))
        names.extend(_attachment_names(child))
    return names


def _added_message_ids(page: dict) -> list[str]:
    ids: list[str] = []
    for entry in page.get("history") or []:
        for added in entry.get("messagesAdded") or []:
            message = added.get("message") or {}
            if message.get("id"):
                ids.append(str(message["id"]))
    return list(dict.fromkeys(ids))
