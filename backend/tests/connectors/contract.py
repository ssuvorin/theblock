"""The shared contract every source adapter must satisfy, parameterized per connector.

This exists so that adding a source cannot quietly weaken the guarantees the sync service
depends on. A fake connector is registered against the same suite as the real ones, which is
what evidences SC-7: the core needs no change to accept a new source, because the suite the
new source passes is the core's only expectation of it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import pytest
from app.connectors.base import (
    AuthChallenge,
    AuthGrant,
    CredentialStore,
    CursorInvalidated,
    NormalizedParticipant,
    NormalizedRecord,
    ReauthRequired,
    SourceConnector,
    SyncBatch,
    SyncMode,
)

REQUIRED_RECORD_FIELDS = (
    "external_id",
    "type",
    "source",
    "occurred_at",
    "participants",
    "raw_ref",
)


@dataclass
class DictCredentials:
    """An in-memory CredentialStore that records whether a rotation was persisted."""

    credentials: dict
    updates: int = 0

    def get(self) -> dict:
        return dict(self.credentials)

    def update(self, credentials: dict) -> None:
        self.credentials.update(credentials)
        self.updates += 1


@dataclass
class ConnectorCase:
    """One connector plus the seams a test needs to drive it without a live provider."""

    name: str
    build: Callable[[], SourceConnector]
    credentials: Callable[[], DictCredentials]
    expect_redirect: bool = True
    delta_cursor: dict | None = None


class FakeConnector:
    """A minimal connector used to prove the contract is satisfiable without provider code."""

    source_type = "fake"

    def __init__(self, *, dead_cursor: bool = False, reauth: bool = False) -> None:
        self._dead_cursor = dead_cursor
        self._reauth = reauth
        self.modes: list[SyncMode] = []

    @property
    def capabilities(self) -> dict:
        return {"surfaces": ["fake"], "scopes": ["fake.readonly"], "write_access": False}

    def initiate_auth(self, redirect_uri: str, state: str) -> AuthChallenge:
        return AuthChallenge(
            redirect_url=f"{redirect_uri}?state={state}",
            pending_secrets={"verifier": "v"},
        )

    def complete_auth(self, code: str, redirect_uri: str, pending: dict) -> AuthGrant:
        del redirect_uri
        return AuthGrant(
            external_account_id="fake@example.test",
            scopes=("fake.readonly",),
            capabilities=self.capabilities,
            credentials={"access_token": code, "verifier": pending.get("verifier", "")},
        )

    def fetch(
        self,
        mode: SyncMode,
        cursor: dict,
        credentials: CredentialStore,
    ) -> Iterator[SyncBatch]:
        self.modes.append(mode)
        if self._reauth:
            raise ReauthRequired("fake grant is gone")
        if self._dead_cursor and mode is SyncMode.DELTA:
            raise CursorInvalidated("fake cursor expired", "fake")
        credentials.get()
        yield SyncBatch(
            records=(_record("fake-1"), _record("fake-2")),
            cursor={"fake": {"cursor": "2"}},
            surface="fake",
        )

    def revoke(self, credentials: dict) -> None:
        del credentials


def _record(external_id: str) -> NormalizedRecord:
    return NormalizedRecord(
        external_id=external_id,
        type="message",
        source="fake",
        occurred_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        direction="incoming",
        subject="Fake subject",
        body_text="Fake body long enough to be chunked into the semantic index later.",
        participants=(
            NormalizedParticipant(
                source_address="peer@example.test",
                role="sender",
                display_name="Peer Person",
                identity_hint={"email": "peer@example.test"},
            ),
        ),
        raw_ref=f"fake://{external_id}",
    )


def assert_protocol(connector: SourceConnector) -> None:
    assert isinstance(connector, SourceConnector)
    assert connector.source_type
    capabilities = connector.capabilities
    assert isinstance(capabilities, dict)
    assert capabilities.get("surfaces"), "a connector must declare its surfaces"
    assert capabilities.get("write_access") in {True, False}


def assert_auth_challenge(connector: SourceConnector, *, expect_redirect: bool) -> None:
    challenge = connector.initiate_auth("https://api.test/api/connections/x/callback", "state-1")
    if expect_redirect:
        assert challenge.redirect_url, "an OAuth connector must return a redirect URL"
        assert "state-1" in challenge.redirect_url, "the state nonce must be bound into the URL"


def assert_records_are_normalized(batches: list[SyncBatch]) -> None:
    assert batches, "a sync must yield at least one batch"
    for batch in batches:
        assert batch.surface, "every batch must name its surface"
        for record in batch.records:
            for field in REQUIRED_RECORD_FIELDS:
                assert getattr(record, field) is not None, f"{field} is required"
            assert record.occurred_at.tzinfo is not None, "timestamps must be timezone aware"
            for participant in record.participants:
                assert participant.role
                assert participant.source_address


def assert_idempotent_replay(batches: list[SyncBatch], repeat: list[SyncBatch]) -> None:
    """Replaying the same cursor must produce the same external ids, never new ones."""

    first = [record.external_id for batch in batches for record in batch.records]
    second = [record.external_id for batch in repeat for record in batch.records]
    assert first == second


def fresh_records(count: int = 2) -> tuple[NormalizedRecord, ...]:
    base = _record("shared-1")
    return tuple(
        replace(
            base,
            external_id=f"shared-{index}",
            occurred_at=base.occurred_at + timedelta(hours=index),
        )
        for index in range(count)
    )


@pytest.fixture
def fake_credentials() -> DictCredentials:
    return DictCredentials({"access_token": "token", "refresh_token": "refresh"})
