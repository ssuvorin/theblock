"""Run one connector sync and record honestly what happened.

Every provider failure has exactly one meaning here, and the meaning decides what survives:

* ``ReauthRequired`` keeps the cursor and asks the owner to re-consent. Dropping the cursor
  would turn a re-consent into an unbounded re-import.
* ``CursorInvalidated`` is retried once in initial mode. That is the bounded resync.
* ``RateLimited`` and ``SourceUnavailable`` mark the connection degraded and keep the cursor,
  because the next attempt should resume, not restart.
* Anything else propagates. A normalisation bug must not be reported to the owner as a
  provider outage.

The cursor is committed after each batch, so a sync that dies halfway has still made
progress and one source failing never touches another connection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import Settings
from app.connectors.base import (
    ConnectorError,
    ConnectorNotConfigured,
    CursorInvalidated,
    RateLimited,
    ReauthRequired,
    SourceConnector,
    SourceStatus,
    SourceUnavailable,
    SyncBatch,
    SyncMode,
)
from app.connectors.registry import ConnectorRegistry
from app.models import Owner, SourceConnection, SyncRun, utcnow
from app.repositories.connections import SourceConnectionRepository, SyncRunRepository
from app.services.connector_graph import ConnectorGraphWriter, GraphDelta
from app.services.meeting_followups import create_meeting_followups
from app.services.relationship_recompute import recompute_edges
from app.services.secret_vault import SecretVault, VaultCredentials
from app.services.semantic_runtime import build_runtime

logger = logging.getLogger(__name__)

STATUS_SUCCEEDED = "succeeded"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"


class ConnectionPaused(RuntimeError):
    """A paused connection is not synced until the owner resumes it."""


@dataclass
class _Progress:
    delta: GraphDelta
    cursor: dict
    records: list
    resynced: set[str]

    def absorb(self, batch: SyncBatch, delta: GraphDelta) -> None:
        self.delta.merge(delta)
        self.cursor = batch.cursor
        self.records.extend(batch.records)
        if batch.resynced:
            self.resynced.add(batch.surface)


class ConnectorSyncService:
    """Drive one connection through one sync run."""

    def __init__(
        self,
        session: Session,
        owner: Owner,
        settings: Settings,
        registry: ConnectorRegistry | None = None,
    ) -> None:
        self._session = session
        self._owner = owner
        self._settings = settings
        self._registry = registry or ConnectorRegistry(settings)
        self._connections = SourceConnectionRepository(session, owner.id)
        self._runs = SyncRunRepository(session, owner.id)
        self._vault = SecretVault(session, owner.id, settings)

    def run(self, connection: SourceConnection, mode: SyncMode | None = None) -> SyncRun:
        if connection.paused:
            raise ConnectionPaused(f"{connection.source} is paused")
        if not connection.auth_ref:
            raise ConnectorNotConfigured(f"{connection.source} has no stored credentials")
        connector = self._registry.get(connection.source)
        resolved = mode or (SyncMode.DELTA if connection.sync_cursor else SyncMode.INITIAL)
        run = self._runs.start(connection, resolved.value)
        self._connections.mark(connection, SourceStatus.SYNCING)
        self._session.commit()
        return self._execute(connection, connector, resolved, run)

    def _execute(
        self,
        connection: SourceConnection,
        connector: SourceConnector,
        mode: SyncMode,
        run: SyncRun,
    ) -> SyncRun:
        progress = _Progress(GraphDelta(), dict(connection.sync_cursor or {}), [], set())
        try:
            self._drain(connection, connector, mode, progress)
        except CursorInvalidated as error:
            # The bounded resync: retry once from scratch, and treat a second dead cursor as a
            # degraded source rather than looping.
            logger.info("bounded resync for %s: %s", connection.source, error)
            progress.resynced.add(error.surface or connection.source)
            progress.cursor = {}
            try:
                self._drain(connection, connector, SyncMode.INITIAL, progress)
            except ConnectorError as retry_error:
                return self._settle(connection, run, progress, SourceStatus.DEGRADED, retry_error)
        except ReauthRequired as error:
            return self._settle(connection, run, progress, SourceStatus.REAUTH_REQUIRED, error)
        except (RateLimited, SourceUnavailable) as error:
            return self._settle(connection, run, progress, SourceStatus.DEGRADED, error)
        except ConnectorError as error:
            return self._settle(connection, run, progress, SourceStatus.ERROR, error)
        return self._settle(connection, run, progress, SourceStatus.CONNECTED, None)

    def _drain(
        self,
        connection: SourceConnection,
        connector: SourceConnector,
        mode: SyncMode,
        progress: _Progress,
    ) -> None:
        credentials = VaultCredentials(self._vault, str(connection.auth_ref))
        writer = ConnectorGraphWriter(self._session, self._owner, connection)
        for batch in connector.fetch(mode, progress.cursor, credentials):
            progress.absorb(batch, writer.write(batch.records))
            connection.sync_cursor = progress.cursor
            connection.updated_at = utcnow()
            self._session.commit()

    def _settle(
        self,
        connection: SourceConnection,
        run: SyncRun,
        progress: _Progress,
        status: SourceStatus,
        error: Exception | None,
    ) -> SyncRun:
        counters = self._derive(progress)
        if status is SourceStatus.CONNECTED:
            connection.last_sync_at = utcnow()
        connection.sync_cursor = progress.cursor
        self._connections.mark(connection, status, error=str(error) if error else None)
        self._runs.finish(
            run,
            status=_run_status(status, progress),
            processed=progress.delta.processed,
            skipped=progress.delta.skipped,
            errors=0 if error is None else 1,
            counters={**counters, "resynced": sorted(progress.resynced)},
            cursor_after=progress.cursor,
            error_message=str(error) if error else None,
        )
        self._session.commit()
        return run

    def _derive(self, progress: _Progress) -> dict:
        """Post-write derivations: edges, reminders, and the semantic index queue.

        These run even for a partially failed sync, because whatever did land is real and the
        owner should see it reflected in their graph rather than held back.
        """

        edges = recompute_edges(
            self._session,
            self._owner.id,
            self._owner.self_person_id or "",
            progress.delta.touched_person_ids,
        )
        follow_ups = create_meeting_followups(self._session, self._owner, progress.records)
        queued = self._queue_index(progress.delta.interaction_ids)
        return {
            **progress.delta.counters(),
            "relationships_created": edges.created,
            "relationships_updated": edges.updated,
            **follow_ups.counters(),
            "semantic_queued": queued,
        }

    def _queue_index(self, interaction_ids: list[str]) -> int:
        if not interaction_ids:
            return 0
        runtime = build_runtime(self._session, self._owner.id, self._settings)
        return runtime.outbox.enqueue_upsert(interaction_ids, self._settings.embedding_version)


def _run_status(status: SourceStatus, progress: _Progress) -> str:
    if status is SourceStatus.CONNECTED:
        return STATUS_SUCCEEDED
    return STATUS_PARTIAL if progress.delta.processed else STATUS_FAILED
