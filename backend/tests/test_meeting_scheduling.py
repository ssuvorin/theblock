"""Scheduling is the only outbound side effect, so its guard rails are asserted directly.

Two claims are load-bearing for the demo: the write scope is not requested unless scheduling is
switched on, and the response never implies Collabute was told about the meeting — because its
MCP surface has no tool that could be told.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest
from app.config import Settings
from app.connectors.google.oauth import CALENDAR_WRITE_SCOPE
from app.connectors.google.scheduling import (
    MeetingRequest,
    MeetingScheduler,
    SchedulingDisabled,
)

from connectors.contract import DictCredentials

STARTS_AT = datetime(2026, 9, 3, 14, 0, tzinfo=UTC)
EVENT = {
    "id": "evt-1",
    "htmlLink": "https://calendar.google.com/event?eid=evt-1",
    "hangoutLink": "https://meet.google.com/abc-defg-hij",
    "start": {"dateTime": "2026-09-03T14:00:00Z"},
    "end": {"dateTime": "2026-09-03T14:30:00Z"},
    "conferenceData": {
        "createRequest": {"status": {"statusCode": "success"}},
        "entryPoints": [{"entryPointType": "video", "uri": "https://meet.google.com/abc-defg-hij"}],
    },
}


def _settings(*, scheduling: bool) -> Settings:
    return Settings(
        database_url="sqlite://",
        auth_secret="s" * 40,
        owner_password="p" * 12,
        encryption_key="k" * 43 + "=",
        google_client_id="client",
        google_client_secret="secret",
        google_meeting_scheduling=scheduling,
    )


def _credentials(scope: str) -> DictCredentials:
    return DictCredentials(
        {
            "access_token": "token",
            "refresh_token": "refresh",
            "scope": scope,
            "expires_at": "2099-01-01T00:00:00+00:00",
        }
    )


def _request() -> MeetingRequest:
    return MeetingRequest(
        title="Intro call",
        starts_at=STARTS_AT,
        duration_minutes=30,
        guest_emails=("priya@rain.test",),
        description="Talk about the product role",
    )


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=EVENT)

    original = httpx.Client

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return original(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)
    return seen


def test_scheduling_is_refused_while_it_is_switched_off() -> None:
    scheduler = MeetingScheduler(_settings(scheduling=False), _credentials(CALENDAR_WRITE_SCOPE))

    with pytest.raises(SchedulingDisabled, match="GOOGLE_MEETING_SCHEDULING"):
        scheduler.schedule(_request())


def test_a_grant_without_the_write_scope_is_refused_before_calling_google() -> None:
    read_only = "https://www.googleapis.com/auth/gmail.readonly"
    scheduler = MeetingScheduler(_settings(scheduling=True), _credentials(read_only))

    with pytest.raises(SchedulingDisabled, match="reconnect Google"):
        scheduler.schedule(_request())


def test_a_meet_link_is_requested_with_a_unique_conference_request(
    captured: list[httpx.Request],
) -> None:
    scheduler = MeetingScheduler(_settings(scheduling=True), _credentials(CALENDAR_WRITE_SCOPE))

    first = scheduler.schedule(_request())
    second = scheduler.schedule(_request())

    assert first.meet_url == "https://meet.google.com/abc-defg-hij"
    assert first.conference_status == "success"
    bodies = [json.loads(request.content) for request in captured]
    request_ids = {body["conferenceData"]["createRequest"]["requestId"] for body in bodies}
    assert len(request_ids) == 2, "each event needs its own conference, never a shared one"
    assert bodies[0]["conferenceData"]["createRequest"]["conferenceSolutionKey"] == {
        "type": "hangoutsMeet"
    }
    assert second.event_id == "evt-1"


def test_conference_data_version_one_is_sent_or_google_ignores_the_request(
    captured: list[httpx.Request],
) -> None:
    MeetingScheduler(_settings(scheduling=True), _credentials(CALENDAR_WRITE_SCOPE)).schedule(
        _request()
    )

    assert captured[0].url.params["conferenceDataVersion"] == "1"


def test_guests_are_invited_only_when_the_owner_asked(captured: list[httpx.Request]) -> None:
    scheduler = MeetingScheduler(_settings(scheduling=True), _credentials(CALENDAR_WRITE_SCOPE))

    loud = scheduler.schedule(_request())
    quiet = scheduler.schedule(
        MeetingRequest(
            title="Quiet hold",
            starts_at=STARTS_AT,
            duration_minutes=30,
            guest_emails=("priya@rain.test",),
            notify_guests=False,
        )
    )

    assert captured[0].url.params["sendUpdates"] == "all"
    assert loud.invites_sent is True
    assert captured[1].url.params["sendUpdates"] == "none"
    assert quiet.invites_sent is False


def test_a_pending_conference_is_reported_as_pending_not_as_a_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Google creates conferences asynchronously; a missing link must not be invented."""

    pending = {
        "id": "evt-2",
        "htmlLink": "https://calendar.google.com/event?eid=evt-2",
        "conferenceData": {"createRequest": {"status": {"statusCode": "pending"}}},
    }
    original = httpx.Client

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        handler = httpx.MockTransport(lambda request: httpx.Response(200, json=pending))
        return original(*args, transport=handler, **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)

    scheduled = MeetingScheduler(
        _settings(scheduling=True), _credentials(CALENDAR_WRITE_SCOPE)
    ).schedule(_request())

    assert scheduled.meet_url is None
    assert scheduled.conference_status == "pending"


def test_an_insufficient_scope_error_asks_for_reconsent(monkeypatch: pytest.MonkeyPatch) -> None:
    original = httpx.Client

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        handler = httpx.MockTransport(
            lambda request: httpx.Response(
                403,
                json={"error": {"message": "Request had insufficient authentication scopes."}},
            )
        )
        return original(*args, transport=handler, **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)

    with pytest.raises(SchedulingDisabled, match="reconnect Google"):
        MeetingScheduler(_settings(scheduling=True), _credentials(CALENDAR_WRITE_SCOPE)).schedule(
            _request()
        )
