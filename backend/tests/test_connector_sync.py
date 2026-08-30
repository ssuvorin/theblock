"""What a sync must guarantee: idempotent replay, honest states, and a cursor that survives.

These are the promises the connections screen makes to the owner, so they are asserted against
the database rather than against a connector's return value.
"""

from __future__ import annotations

import base64
import os
from collections.abc import Iterator
from dataclasses import replace

import pytest
from app.config import Settings
from app.connectors.base import (
    CursorInvalidated,
    RateLimited,
    SourceStatus,
    SyncBatch,
    SyncMode,
)
from app.connectors.registry import ConnectorRegistry
from app.models import (
    Base,
    FollowUp,
    InteractionEvent,
    InteractionParticipant,
    Owner,
    Person,
    Relationship,
    SemanticIndexOutbox,
    SourceConnection,
)
from app.services.connector_sync import ConnectionPaused, ConnectorSyncService
from app.services.secret_vault import SecretVault
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from connectors.contract import FakeConnector, fresh_records


def _settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        auth_secret="s" * 40,
        owner_password="p" * 12,
        encryption_key=base64.urlsafe_b64encode(os.urandom(32)).decode(),
        demo_mode=False,
        seed_demo_data=False,
    )


class StubRegistry(ConnectorRegistry):
    """Registry that returns a prepared fake connector for the ``fake`` source."""

    def __init__(self, settings: Settings, connector: object) -> None:
        super().__init__(settings)
        self._connector = connector

    def availability(self, source: str) -> tuple[str, str | None]:
        return ("available", None) if source == "fake" else super().availability(source)

    def get(self, source: str):
        return self._connector if source == "fake" else super().get(source)


@pytest.fixture
def settings() -> Settings:
    return _settings()


@pytest.fixture
def session(settings: Settings) -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as active:
        active.add(Owner(id="owner-1", display_name="Owner", email="owner@example.test"))
        active.flush()
        yield active


@pytest.fixture
def owner(session: Session) -> Owner:
    return session.get(Owner, "owner-1")


@pytest.fixture
def connection(session: Session, owner: Owner, settings: Settings) -> SourceConnection:
    ref = SecretVault(session, owner.id, settings).store(
        "oauth_tokens",
        {"access_token": "t", "refresh_token": "r"},
    )
    row = SourceConnection(
        owner_id=owner.id,
        source="fake",
        external_account_id="fake@example.test",
        status=SourceStatus.CONNECTED,
        auth_ref=ref,
        capabilities={"surfaces": ["fake"]},
    )
    session.add(row)
    session.flush()
    return row


def _service(session: Session, owner: Owner, settings: Settings, connector: object):
    return ConnectorSyncService(session, owner, settings, StubRegistry(settings, connector))


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_a_sync_writes_people_interactions_and_participants(
    session: Session,
    owner: Owner,
    settings: Settings,
    connection: SourceConnection,
) -> None:
    run = _service(session, owner, settings, FakeConnector()).run(connection)

    assert run.status == "succeeded"
    assert run.processed == 2
    assert _count(session, InteractionEvent) == 2
    assert _count(session, InteractionParticipant) == 2
    assert session.scalar(select(Person).where(Person.display_name == "Peer Person")) is not None
    assert connection.status == SourceStatus.CONNECTED
    assert connection.last_sync_at is not None


def test_replaying_the_same_sync_creates_no_duplicates(
    session: Session,
    owner: Owner,
    settings: Settings,
    connection: SourceConnection,
) -> None:
    _service(session, owner, settings, FakeConnector()).run(connection)
    second = _service(session, owner, settings, FakeConnector()).run(connection)

    assert _count(session, InteractionEvent) == 2
    assert second.processed == 0
    assert second.skipped == 2


def test_the_owner_gets_a_self_person_and_an_edge_per_contact(
    session: Session,
    owner: Owner,
    settings: Settings,
    connection: SourceConnection,
) -> None:
    _service(session, owner, settings, FakeConnector()).run(connection)

    assert owner.self_person_id is not None
    edges = list(session.scalars(select(Relationship)))
    assert len(edges) == 1
    assert edges[0].person_a_id == owner.self_person_id
    assert edges[0].total_interactions == 2
    assert edges[0].evidence, "an edge must cite the interactions that support it"


def test_a_dead_cursor_triggers_exactly_one_bounded_resync(
    session: Session,
    owner: Owner,
    settings: Settings,
    connection: SourceConnection,
) -> None:
    connection.sync_cursor = {"fake": {"cursor": "1"}}
    session.flush()
    connector = FakeConnector(dead_cursor=True)

    run = _service(session, owner, settings, connector).run(connection)

    assert connector.modes == [SyncMode.DELTA, SyncMode.INITIAL]
    assert run.status == "succeeded"
    assert run.counters["resynced"] == ["fake"]
    assert connection.status == SourceStatus.CONNECTED


def test_a_revoked_grant_asks_for_reauth_and_keeps_the_cursor(
    session: Session,
    owner: Owner,
    settings: Settings,
    connection: SourceConnection,
) -> None:
    connection.sync_cursor = {"fake": {"cursor": "keep-me"}}
    session.flush()

    run = _service(session, owner, settings, FakeConnector(reauth=True)).run(connection)

    assert connection.status == SourceStatus.REAUTH_REQUIRED
    assert connection.sync_cursor == {"fake": {"cursor": "keep-me"}}
    assert run.status == "failed"
    assert "grant is gone" in (run.error_message or "")


def test_a_throttled_source_degrades_and_keeps_the_cursor(
    session: Session,
    owner: Owner,
    settings: Settings,
    connection: SourceConnection,
) -> None:
    class Throttled(FakeConnector):
        def fetch(self, mode, cursor, credentials):
            raise RateLimited("slow down", 30.0)
            yield  # pragma: no cover - generator protocol only

    connection.sync_cursor = {"fake": {"cursor": "keep-me"}}
    session.flush()

    _service(session, owner, settings, Throttled()).run(connection)

    assert connection.status == SourceStatus.DEGRADED
    assert connection.sync_cursor == {"fake": {"cursor": "keep-me"}}


def test_a_second_dead_cursor_degrades_instead_of_looping(
    session: Session,
    owner: Owner,
    settings: Settings,
    connection: SourceConnection,
) -> None:
    class AlwaysDead(FakeConnector):
        def fetch(self, mode, cursor, credentials) -> Iterator[SyncBatch]:
            self.modes.append(mode)
            raise CursorInvalidated("still dead", "fake")
            yield  # pragma: no cover - generator protocol only

    connection.sync_cursor = {"fake": {"cursor": "1"}}
    session.flush()
    connector = AlwaysDead()

    run = _service(session, owner, settings, connector).run(connection)

    assert connector.modes == [SyncMode.DELTA, SyncMode.INITIAL]
    assert connection.status == SourceStatus.DEGRADED
    assert run.status == "failed"


def test_a_paused_connection_is_not_synced(
    session: Session,
    owner: Owner,
    settings: Settings,
    connection: SourceConnection,
) -> None:
    connection.paused = True
    session.flush()

    with pytest.raises(ConnectionPaused):
        _service(session, owner, settings, FakeConnector()).run(connection)


def test_written_interactions_are_queued_for_the_semantic_index(
    session: Session,
    owner: Owner,
    settings: Settings,
    connection: SourceConnection,
) -> None:
    run = _service(session, owner, settings, FakeConnector()).run(connection)

    assert run.counters["semantic_queued"] == 2
    assert _count(session, SemanticIndexOutbox) == 2


def test_meeting_action_items_become_one_followup_each(
    session: Session,
    owner: Owner,
    settings: Settings,
    connection: SourceConnection,
) -> None:
    class Meetings(FakeConnector):
        def fetch(self, mode, cursor, credentials) -> Iterator[SyncBatch]:
            self.modes.append(mode)
            records = tuple(
                replace(
                    record,
                    type="meeting",
                    metadata={
                        "action_items": [
                            {
                                "text": "Send the spec",
                                "owner": "Peer Person",
                                "source_key": f"act-{record.external_id}",
                            }
                        ]
                    },
                )
                for record in fresh_records(1)
            )
            yield SyncBatch(records=records, cursor={"fake": {"cursor": "1"}}, surface="fake")

    _service(session, owner, settings, Meetings()).run(connection)
    _service(session, owner, settings, Meetings()).run(connection)

    follow_ups = list(session.scalars(select(FollowUp)))
    assert len(follow_ups) == 1
    assert follow_ups[0].source == "fake"
    assert "Send the spec" in follow_ups[0].reason
