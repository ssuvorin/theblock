"""Create one Google Calendar event with a Meet link, on explicit owner action.

This is the only place in the codebase that writes to a third-party account, so the rules are
narrow on purpose:

* It runs from an owner-initiated request. Nothing schedules on a timer, on a draft, or as a
  side effect of a sync.
* One event per call, with a freshly generated ``requestId``. Reusing conference data across
  events would expose one meeting's Meet link to another meeting's guests.
* Guests are addresses the owner supplied. The connector never derives an invite list from the
  graph on its own.

Collabute cannot be told about the event: its MCP surface exposes no tool that registers a
meeting or adds a notetaker, so a created meeting reaches Collabute only once Collabute's own
calendar integration works. The API response says so rather than implying a handoff happened.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

from app.config import Settings
from app.connectors.base import (
    ConnectorNotConfigured,
    CredentialStore,
    RateLimited,
    ReauthRequired,
    SourceUnavailable,
)
from app.connectors.google.api import CALENDAR_ROOT
from app.connectors.google.oauth import CALENDAR_WRITE_SCOPE, GoogleOAuth

EVENTS_URL = f"{CALENDAR_ROOT}/calendars/primary/events"
CONFERENCE_TYPE = "hangoutsMeet"
MEET_HOST = "meet.google.com"


class SchedulingDisabled(ConnectorNotConfigured):
    """Scheduling is off, or the stored grant predates the calendar write scope."""


@dataclass(frozen=True, slots=True)
class MeetingRequest:
    title: str
    starts_at: datetime
    duration_minutes: int
    guest_emails: tuple[str, ...]
    description: str | None = None
    timezone: str = "UTC"
    notify_guests: bool = True


@dataclass(frozen=True, slots=True)
class ScheduledMeeting:
    """What Google actually created, including whether the Meet link is ready yet."""

    event_id: str
    html_link: str
    meet_url: str | None
    conference_status: str
    starts_at: str
    ends_at: str
    guests: tuple[str, ...]
    invites_sent: bool

    def as_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "html_link": self.html_link,
            "meet_url": self.meet_url,
            "conference_status": self.conference_status,
            "starts_at": self.starts_at,
            "ends_at": self.ends_at,
            "guests": list(self.guests),
            "invites_sent": self.invites_sent,
        }


class MeetingScheduler:
    """Insert a calendar event that carries a generated Google Meet conference."""

    def __init__(self, settings: Settings, credentials: CredentialStore) -> None:
        self._settings = settings
        self._credentials = credentials
        self._oauth = GoogleOAuth(settings)

    def schedule(self, request: MeetingRequest) -> ScheduledMeeting:
        self._assert_allowed()
        ends_at = request.starts_at + timedelta(minutes=request.duration_minutes)
        body = _event_body(request, ends_at)
        payload = self._insert(body, request.notify_guests)
        conference = payload.get("conferenceData") or {}
        return ScheduledMeeting(
            event_id=str(payload.get("id") or ""),
            html_link=str(payload.get("htmlLink") or ""),
            meet_url=_meet_url(payload, conference),
            conference_status=_conference_status(conference),
            starts_at=_slot(payload.get("start"), request.starts_at),
            ends_at=_slot(payload.get("end"), ends_at),
            guests=request.guest_emails,
            invites_sent=request.notify_guests and bool(request.guest_emails),
        )

    def _assert_allowed(self) -> None:
        """Refuse before calling Google if the grant cannot possibly carry the write scope."""

        if not self._settings.google_meeting_scheduling:
            raise SchedulingDisabled(
                "meeting scheduling is disabled; set GOOGLE_MEETING_SCHEDULING=true to enable it"
            )
        granted = str(self._credentials.get().get("scope") or "").split()
        if granted and CALENDAR_WRITE_SCOPE not in granted:
            raise SchedulingDisabled(
                "the stored Google grant predates the calendar write scope; "
                "reconnect Google to consent to creating events"
            )

    def _insert(self, body: dict, notify_guests: bool) -> dict:
        params = {
            # Version 1 is what makes createRequest produce a conference at all.
            "conferenceDataVersion": "1",
            "sendUpdates": "all" if notify_guests else "none",
        }
        response = self._post(params, body, self._token())
        if response.status_code == 401:
            response = self._post(params, body, self._refresh())
        return self._decode(response)

    def _post(self, params: dict, body: dict, token: str) -> httpx.Response:
        try:
            with httpx.Client(timeout=self._settings.connector_timeout_seconds) as client:
                return client.post(
                    EVENTS_URL,
                    params=params,
                    json=body,
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.HTTPError as error:
            raise SourceUnavailable(f"Google calendar insert failed: {error}") from error

    def _decode(self, response: httpx.Response) -> dict:
        if response.status_code in {401, 403} and _is_scope_failure(response):
            raise SchedulingDisabled(
                "Google refused the calendar write; reconnect Google to grant calendar.events"
            )
        if response.status_code == 401:
            raise ReauthRequired("Google rejected the refreshed access token")
        if response.status_code == 429:
            raise RateLimited("Google asked us to slow down")
        if response.status_code >= 400:
            raise SourceUnavailable(
                f"Google calendar insert returned {response.status_code}: {response.text[:200]}"
            )
        try:
            return response.json()
        except ValueError as error:
            raise SourceUnavailable("Google calendar insert response was not JSON") from error

    def _token(self) -> str:
        token = str(self._credentials.get().get("access_token") or "")
        return token or self._refresh()

    def _refresh(self) -> str:
        current = self._credentials.get()
        refresh_token = str(current.get("refresh_token") or "")
        if not refresh_token:
            raise ReauthRequired("no Google refresh token is stored for this connection")
        refreshed = self._oauth.refresh(refresh_token)
        self._credentials.update(refreshed)
        return refreshed["access_token"]


def _event_body(request: MeetingRequest, ends_at: datetime) -> dict:
    body: dict = {
        "summary": request.title,
        "start": {"dateTime": request.starts_at.isoformat(), "timeZone": request.timezone},
        "end": {"dateTime": ends_at.isoformat(), "timeZone": request.timezone},
        "attendees": [{"email": email} for email in request.guest_emails],
        "conferenceData": {
            "createRequest": {
                # Unique per event: a shared conference leaks one meeting into another.
                "requestId": uuid.uuid4().hex,
                "conferenceSolutionKey": {"type": CONFERENCE_TYPE},
            }
        },
    }
    if request.description:
        body["description"] = request.description
    return body


def _conference_status(conference: dict) -> str:
    """Google creates conferences asynchronously, so ``pending`` is a normal answer."""

    status = (conference.get("createRequest") or {}).get("status") or {}
    return str(
        status.get("statusCode") or ("success" if conference.get("entryPoints") else "pending")
    )


def _meet_url(payload: dict, conference: dict) -> str | None:
    for entry in conference.get("entryPoints") or []:
        uri = str(entry.get("uri") or "")
        if entry.get("entryPointType") == "video" and uri:
            return uri
    hangout = str(payload.get("hangoutLink") or "")
    return hangout if MEET_HOST in hangout else None


def _slot(slot: object, fallback: datetime) -> str:
    if isinstance(slot, dict):
        value = slot.get("dateTime") or slot.get("date")
        if isinstance(value, str) and value:
            return value
    return fallback.isoformat()


def _is_scope_failure(response: httpx.Response) -> bool:
    try:
        body = response.json()
    except ValueError:
        return False
    error = body.get("error")
    text = str(error) if not isinstance(error, dict) else str(error.get("message") or error)
    return "insufficient" in text.casefold() or "scope" in text.casefold()
