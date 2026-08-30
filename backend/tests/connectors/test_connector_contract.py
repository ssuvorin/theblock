"""Run the shared connector contract against every registered adapter.

Google and Collabute are exercised through stubbed HTTP so the suite needs no OAuth secrets
and no network; the fake connector proves the same suite is satisfiable by a source the core
has never heard of, which is the SC-7 claim.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest
from app.config import Settings
from app.connectors.base import SyncBatch, SyncMode
from app.connectors.collabute.connector import CollabuteConnector
from app.connectors.google.connector import GoogleConnector
from app.connectors.registry import ConnectorRegistry

from .contract import (
    ConnectorCase,
    DictCredentials,
    FakeConnector,
    assert_auth_challenge,
    assert_idempotent_replay,
    assert_protocol,
    assert_records_are_normalized,
)

GMAIL_LIST = {"messages": [{"id": "m1"}]}
GMAIL_MESSAGE = {
    "id": "m1",
    "threadId": "t1",
    "internalDate": "1780000000000",
    "labelIds": ["INBOX"],
    "payload": {
        "mimeType": "text/plain",
        "headers": [
            {"name": "From", "value": "Priya Nair <priya@rain.test>"},
            {"name": "To", "value": "owner@example.test"},
            {"name": "Subject", "value": "Product role"},
        ],
        "body": {"data": "V2UgYXJlIGhpcmluZyBhIHByb2R1Y3QgbWFuYWdlci4="},
    },
}
CALENDAR_PAGE = {
    "items": [
        {
            "id": "e1",
            "summary": "Intro call",
            "status": "confirmed",
            "start": {"dateTime": "2026-08-20T09:00:00Z"},
            "end": {"dateTime": "2026-08-20T09:30:00Z"},
            "organizer": {"email": "owner@example.test"},
            "attendees": [{"email": "priya@rain.test", "displayName": "Priya Nair"}],
        }
    ],
    "nextSyncToken": "sync-2",
}
COLLABUTE_MEETING = {
    "id": "cb-1",
    "title": "Roadmap review",
    "startTime": "2026-08-25T14:00:00Z",
    "summary": "Agreed to prioritise the payments milestone.",
    "participants": [{"email": "priya@rain.test", "name": "Priya Nair"}],
    "decisions": ["Ship payments first"],
    "actionItems": [{"text": "Send the spec", "owner": "Priya Nair", "id": "act-1"}],
}


def google_settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        auth_secret="s" * 40,
        owner_password="p" * 12,
        encryption_key="k" * 43 + "=",
        google_client_id="client",
        google_client_secret="secret",
    )


def collabute_settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        auth_secret="s" * 40,
        owner_password="p" * 12,
        encryption_key="k" * 43 + "=",
    )


def _google_transport(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/profile"):
        return httpx.Response(200, json={"emailAddress": "owner@example.test", "historyId": "42"})
    if path.endswith("/messages"):
        return httpx.Response(200, json=GMAIL_LIST)
    if "/messages/" in path:
        return httpx.Response(200, json=GMAIL_MESSAGE)
    if path.endswith("/events"):
        return httpx.Response(200, json=CALENDAR_PAGE)
    return httpx.Response(404, json={"error": {"message": "unmapped"}})


def _collabute_transport(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content or b"{}")
    method = body.get("method")
    if method == "initialize":
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": body["id"], "result": {"protocolVersion": "2025-06-18"}},
            headers={"Mcp-Session-Id": "sess-1"},
        )
    if method == "notifications/initialized":
        return httpx.Response(202)
    if method == "tools/list":
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {
                    "tools": [
                        {"name": "system.ping"},
                        {"name": "meeting.list_recent"},
                        {"name": "meeting.get"},
                    ]
                },
            },
        )
    if method == "tools/call":
        return _collabute_tool(body)
    return httpx.Response(404)


def _collabute_tool(body: dict) -> httpx.Response:
    name = body["params"]["name"]
    payloads = {
        "system.ping": {"ok": True, "organizationId": "org_1"},
        "meeting.list_recent": {"count": 1, "items": [COLLABUTE_MEETING]},
        "meeting.get": COLLABUTE_MEETING,
    }
    return httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": body["id"],
            "result": {"content": [{"type": "text", "text": json.dumps(payloads[name])}]},
        },
    )


@pytest.fixture
def stub_google(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, _google_transport)


@pytest.fixture
def stub_collabute(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, _collabute_transport)


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    original = httpx.Client

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return original(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)


CASES = {
    "fake": ConnectorCase(
        name="fake",
        build=FakeConnector,
        credentials=lambda: DictCredentials({"access_token": "t", "refresh_token": "r"}),
    ),
    "google": ConnectorCase(
        name="google",
        build=lambda: GoogleConnector(google_settings()),
        credentials=lambda: DictCredentials(
            {
                "access_token": "t",
                "refresh_token": "r",
                "account": "owner@example.test",
                "expires_at": "2099-01-01T00:00:00+00:00",
            }
        ),
    ),
    "collabute": ConnectorCase(
        name="collabute",
        build=lambda: CollabuteConnector(collabute_settings()),
        credentials=lambda: DictCredentials(
            {
                "access_token": "t",
                "refresh_token": "r",
                "client_id": "c",
                "expires_at": "2099-01-01T00:00:00+00:00",
            }
        ),
    ),
}


def _drain(case: ConnectorCase, mode: SyncMode = SyncMode.INITIAL) -> list[SyncBatch]:
    connector = case.build()
    return list(connector.fetch(mode, {}, case.credentials()))


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_connector_satisfies_the_protocol(name: str) -> None:
    assert_protocol(CASES[name].build())


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_connector_binds_state_into_its_auth_challenge(name: str) -> None:
    case = CASES[name]
    if name == "collabute":
        pytest.skip("Collabute needs a live registration endpoint to build an authorize URL")
    assert_auth_challenge(case.build(), expect_redirect=case.expect_redirect)


def test_fake_connector_produces_normalized_records() -> None:
    assert_records_are_normalized(_drain(CASES["fake"]))


def test_google_produces_normalized_records(stub_google: None) -> None:
    del stub_google
    batches = _drain(CASES["google"])
    assert_records_are_normalized(batches)
    sources = {record.source for batch in batches for record in batch.records}
    assert sources == {"gmail", "google_calendar"}


def test_collabute_produces_normalized_records(stub_collabute: None) -> None:
    del stub_collabute
    batches = _drain(CASES["collabute"])
    assert_records_are_normalized(batches)
    record = batches[0].records[0]
    assert record.source == "collabute"
    assert record.metadata["decisions"] == ["Ship payments first"]
    assert record.metadata["action_items"][0]["source_key"] == "act-1"


def test_google_replay_is_idempotent(stub_google: None) -> None:
    del stub_google
    assert_idempotent_replay(_drain(CASES["google"]), _drain(CASES["google"]))


def test_collabute_replay_is_idempotent(stub_collabute: None) -> None:
    del stub_collabute
    assert_idempotent_replay(_drain(CASES["collabute"]), _drain(CASES["collabute"]))


def test_registry_needs_one_line_per_source() -> None:
    """SC-7: the registry is the only place that knows the set of sources."""

    registry = ConnectorRegistry(google_settings())
    assert {item["source"] for item in registry.catalog()} == {"google", "collabute", "whatsapp"}
    assert registry.availability("google")[0] == "available"
    assert registry.availability("whatsapp")[0] == "unsupported"


def test_google_scopes_stay_read_only_until_scheduling_is_enabled() -> None:
    read_only = GoogleConnector(google_settings()).capabilities
    assert read_only["write_access"] is False
    assert all("readonly" in scope for scope in read_only["scopes"])
    with_write = GoogleConnector(
        google_settings().model_copy(update={"google_meeting_scheduling": True})
    ).capabilities
    assert with_write["write_access"] is True
    assert "https://www.googleapis.com/auth/calendar.events" in with_write["scopes"]


def test_collabute_never_declares_write_access(stub_collabute: None) -> None:
    """Collabute's MCP surface has no meeting-create tool, so the adapter must not claim one."""

    del stub_collabute
    assert CollabuteConnector(collabute_settings()).capabilities["write_access"] is False


def _batches_for_dead_cursor() -> Iterator[SyncBatch]:
    connector = FakeConnector(dead_cursor=True)
    return connector.fetch(SyncMode.DELTA, {"fake": {"cursor": "1"}}, DictCredentials({}))
