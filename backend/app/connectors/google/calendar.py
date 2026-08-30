"""Calendar read-only sync: bounded initial window, then syncToken deltas.

Attendees are the point. A meeting is the densest relationship evidence Google exposes, so
each event becomes one interaction with every attendee as a participant, and cancellations
arrive as tombstones rather than silently disappearing from the graph.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from app.connectors.base import CursorInvalidated, NormalizedParticipant, NormalizedRecord
from app.connectors.google.api import CALENDAR_ROOT, GoogleApi, GoogleApiError
from app.domain.identity.normalize import IdentityKind
from app.models import utcnow

SOURCE = "google_calendar"
SURFACE = "calendar"
PAGE_SIZE = 250
CURSOR_DEAD_STATUS = 410
EVENTS_URL = f"{CALENDAR_ROOT}/calendars/primary/events"


class CalendarSurface:
    """Page primary-calendar events into normalized meeting records."""

    source = SOURCE
    surface = SURFACE

    def __init__(self, api: GoogleApi, account: str, lookback_days: int, page_limit: int) -> None:
        self._api = api
        self._account = account.casefold()
        self._lookback_days = lookback_days
        self._page_limit = page_limit

    def initial(self) -> Iterator[tuple[tuple[NormalizedRecord, ...], str]]:
        """timeMin is only legal without a syncToken, which is why the modes differ here."""

        time_min = (utcnow() - timedelta(days=self._lookback_days)).isoformat()
        params = {
            "timeMin": time_min,
            "singleEvents": "true",
            "maxResults": PAGE_SIZE,
            "showDeleted": "true",
        }
        yield from self._walk(params)

    def delta(self, sync_token: str) -> Iterator[tuple[tuple[NormalizedRecord, ...], str]]:
        params = {
            "syncToken": sync_token,
            "singleEvents": "true",
            "maxResults": PAGE_SIZE,
            "showDeleted": "true",
        }
        yield from self._walk(params, dead_cursor=True)

    def _walk(
        self,
        params: dict,
        *,
        dead_cursor: bool = False,
    ) -> Iterator[tuple[tuple[NormalizedRecord, ...], str]]:
        token: str | None = None
        carried = str(params.get("syncToken") or "")
        for _ in range(self._page_limit):
            query = dict(params)
            if token:
                query["pageToken"] = token
            page = self._page(query, dead_cursor=dead_cursor)
            # nextSyncToken only appears on the final page; earlier pages keep the old cursor.
            carried = str(page.get("nextSyncToken") or carried)
            yield self._normalize_page(page), carried
            token = page.get("nextPageToken")
            if not token:
                return

    def _page(self, query: dict, *, dead_cursor: bool) -> dict:
        try:
            return self._api.get(EVENTS_URL, query)
        except GoogleApiError as error:
            if dead_cursor and error.status_code == CURSOR_DEAD_STATUS:
                raise CursorInvalidated(
                    "Calendar sync token expired; a bounded resync is required",
                    SURFACE,
                ) from error
            raise

    def _normalize_page(self, page: dict) -> tuple[NormalizedRecord, ...]:
        records = []
        for event in page.get("items") or []:
            record = self._normalize(event)
            if record is not None:
                records.append(record)
        return tuple(records)

    def _normalize(self, event: dict) -> NormalizedRecord | None:
        event_id = str(event.get("id") or "")
        occurred_at = _event_time(event)
        if not event_id or occurred_at is None:
            return None
        organizer = _address(event.get("organizer") or {})
        return NormalizedRecord(
            external_id=event_id,
            type="meeting",
            source=SOURCE,
            occurred_at=occurred_at,
            direction="outgoing" if organizer == self._account else "incoming",
            subject=str(event.get("summary") or "") or None,
            body_text=str(event.get("description") or "") or None,
            participants=tuple(_participants(event)),
            metadata={
                "status": event.get("status"),
                "start": (event.get("start") or {}).get("dateTime")
                or (event.get("start") or {}).get("date"),
                "end": (event.get("end") or {}).get("dateTime")
                or (event.get("end") or {}).get("date"),
                "timezone": (event.get("start") or {}).get("timeZone"),
                "location": event.get("location"),
                "html_link": event.get("htmlLink"),
                "recurring_event_id": event.get("recurringEventId"),
                "account": self._account,
            },
            raw_ref=f"google_calendar://{self._account}/{event_id}",
            is_deleted=str(event.get("status") or "") == "cancelled",
        )


def _participants(event: dict) -> Iterator[NormalizedParticipant]:
    organizer = event.get("organizer") or {}
    if _address(organizer):
        yield _participant(organizer, "organizer")
    for attendee in event.get("attendees") or []:
        if attendee.get("resource"):
            continue  # Meeting rooms are equipment, not contacts.
        if _address(attendee) and _address(attendee) != _address(organizer):
            yield _participant(attendee, "attendee")


def _participant(entry: dict, role: str) -> NormalizedParticipant:
    address = _address(entry)
    return NormalizedParticipant(
        source_address=address,
        role=role,
        display_name=str(entry.get("displayName") or "") or None,
        identity_hint={IdentityKind.EMAIL.value: address} if address else {},
    )


def _address(entry: dict) -> str:
    return str(entry.get("email") or "").casefold()


def _event_time(event: dict) -> datetime | None:
    start = event.get("start") or {}
    raw = start.get("dateTime") or start.get("date")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
