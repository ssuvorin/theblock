"""SQL for the durable outbox that keeps the derived semantic index consistent.

PostgreSQL stays canonical. Every interaction write leaves a pending row here, so an
unconfigured, throttled, or crashed vector store can always catch up later without the
import path knowing anything about embeddings.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, insert, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import (
    InteractionEvent,
    InteractionParticipant,
    SemanticIndexOutbox,
    new_id,
    utcnow,
)

OP_UPSERT = "upsert"
OP_TOMBSTONE = "tombstone"
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
MAX_ERROR_CHARS = 500

_ID_BATCH = 500
_ROW_LOCK_DIALECTS = frozenset({"postgresql", "mysql", "mariadb", "oracle"})
_CONFLICT_BUILDERS = {"postgresql": postgres_insert, "sqlite": sqlite_insert}


def _batched(values: Sequence[str]) -> list[list[str]]:
    return [list(values[start : start + _ID_BATCH]) for start in range(0, len(values), _ID_BATCH)]


def truncate_error(error: str) -> str:
    """Keep queue rows small and readable; adapters are responsible for redaction."""

    collapsed = " ".join(error.split())
    return collapsed[:MAX_ERROR_CHARS]


class SemanticOutboxRepository:
    """Enqueue, claim, and settle semantic index work for one owner."""

    def __init__(self, session: Session, owner_id: str) -> None:
        self._session = session
        self._owner_id = owner_id

    def enqueue_upsert(self, interaction_ids: Sequence[str], embedding_version: str) -> int:
        """Queue one upsert per interaction and return rows created plus rows reset.

        Re-importing the same archive never duplicates or raises: the unique constraint is
        honoured up front, and a row that already finished is reset to ``pending`` because
        the interaction body may have changed since it was indexed.
        """

        return self._enqueue(interaction_ids, embedding_version, OP_UPSERT)

    def enqueue_tombstone(self, interaction_id: str, embedding_version: str) -> None:
        """Queue removal of one interaction's chunks; safe to call repeatedly."""

        self._enqueue([interaction_id], embedding_version, OP_TOMBSTONE)

    def claim(self, limit: int) -> list[SemanticIndexOutbox]:
        """Take up to ``limit`` pending rows oldest-first and mark them ``processing``.

        On engines that support it the select locks rows with ``FOR UPDATE SKIP LOCKED`` so
        parallel drains cannot double-process; SQLite has no row locks and falls back to a
        plain ordered select.
        """

        if limit <= 0:
            return []
        statement = (
            select(SemanticIndexOutbox)
            .where(
                SemanticIndexOutbox.owner_id == self._owner_id,
                SemanticIndexOutbox.status == STATUS_PENDING,
            )
            .order_by(SemanticIndexOutbox.created_at, SemanticIndexOutbox.id)
            .limit(limit)
        )
        if self._dialect() in _ROW_LOCK_DIALECTS:
            statement = statement.with_for_update(skip_locked=True)
        rows = list(self._session.scalars(statement))
        for row in rows:
            row.status = STATUS_PROCESSING
        self._session.flush()
        return rows

    def mark_done(self, row: SemanticIndexOutbox, chunks_written: int) -> None:
        """Settle one row as processed, recording how many chunks it produced."""

        row.status = STATUS_DONE
        row.chunks_written = chunks_written
        row.last_error = None
        row.processed_at = utcnow()
        self._session.flush()

    def mark_failed(self, row: SemanticIndexOutbox, error: str) -> None:
        """Settle one row as failed, counting the attempt and storing a truncated reason."""

        row.status = STATUS_FAILED
        row.attempts = (row.attempts or 0) + 1
        row.last_error = truncate_error(error)
        row.processed_at = utcnow()
        self._session.flush()

    def pending_count(self) -> int:
        return (
            self._session.scalar(
                select(func.count())
                .select_from(SemanticIndexOutbox)
                .where(
                    SemanticIndexOutbox.owner_id == self._owner_id,
                    SemanticIndexOutbox.status == STATUS_PENDING,
                )
            )
            or 0
        )

    def status_counts(self) -> dict[str, int]:
        """Row counts per status for import reporting and staleness banners."""

        rows = self._session.execute(
            select(SemanticIndexOutbox.status, func.count())
            .where(SemanticIndexOutbox.owner_id == self._owner_id)
            .group_by(SemanticIndexOutbox.status)
        ).all()
        return {status: count for status, count in rows}

    def _enqueue(self, interaction_ids: Sequence[str], embedding_version: str, op: str) -> int:
        unique = list(dict.fromkeys(interaction_ids))
        touched = 0
        for batch in _batched(unique):
            touched += self._enqueue_batch(batch, embedding_version, op)
        return touched

    def _enqueue_batch(self, interaction_ids: list[str], embedding_version: str, op: str) -> int:
        existing = {
            row.interaction_id: row
            for row in self._session.scalars(
                select(SemanticIndexOutbox).where(
                    SemanticIndexOutbox.owner_id == self._owner_id,
                    SemanticIndexOutbox.interaction_id.in_(interaction_ids),
                    SemanticIndexOutbox.embedding_version == embedding_version,
                    SemanticIndexOutbox.op == op,
                )
            )
        }
        reset = 0
        for row in existing.values():
            if row.status != STATUS_PENDING:
                self._reset(row)
                reset += 1
        missing = [item for item in interaction_ids if item not in existing]
        self._insert_pending(missing, embedding_version, op)
        self._session.flush()
        return reset + len(missing)

    def _reset(self, row: SemanticIndexOutbox) -> None:
        row.status = STATUS_PENDING
        row.chunks_written = None
        row.last_error = None
        row.processed_at = None

    def _insert_pending(self, interaction_ids: list[str], embedding_version: str, op: str) -> None:
        if not interaction_ids:
            return
        values = [
            {
                "id": new_id(),
                "owner_id": self._owner_id,
                "interaction_id": interaction_id,
                "embedding_version": embedding_version,
                "op": op,
                "status": STATUS_PENDING,
                "attempts": 0,
                "created_at": utcnow(),
            }
            for interaction_id in interaction_ids
        ]
        builder = _CONFLICT_BUILDERS.get(self._dialect())
        if builder is None:
            self._session.execute(insert(SemanticIndexOutbox), values)
            return
        self._session.execute(builder(SemanticIndexOutbox).on_conflict_do_nothing(), values)

    def _dialect(self) -> str:
        return self._session.get_bind().dialect.name


class SemanticSourceRepository:
    """Read the canonical rows the semantic index is derived from."""

    def __init__(self, session: Session, owner_id: str) -> None:
        self._session = session
        self._owner_id = owner_id

    def interaction_ids(self, sources: Sequence[str] | None = None) -> list[str]:
        """Every non-deleted interaction for this owner, oldest first."""

        statement = (
            select(InteractionEvent.id)
            .where(
                InteractionEvent.owner_id == self._owner_id,
                InteractionEvent.is_deleted.is_(False),
            )
            .order_by(InteractionEvent.occurred_at, InteractionEvent.id)
        )
        if sources:
            statement = statement.where(InteractionEvent.source.in_(list(sources)))
        return list(self._session.scalars(statement))

    def interactions_by_id(self, interaction_ids: Sequence[str]) -> dict[str, InteractionEvent]:
        """Load claimed interactions in one query per batch, keyed by id."""

        unique = list(dict.fromkeys(interaction_ids))
        loaded: dict[str, InteractionEvent] = {}
        for batch in _batched(unique):
            rows = self._session.scalars(
                select(InteractionEvent).where(
                    InteractionEvent.owner_id == self._owner_id,
                    InteractionEvent.id.in_(batch),
                )
            )
            loaded.update({row.id: row for row in rows})
        return loaded

    def person_ids_by_interaction(
        self, interaction_ids: Sequence[str]
    ) -> dict[str, tuple[str, ...]]:
        """Resolved participant person ids per interaction, deduplicated in stable order."""

        unique = list(dict.fromkeys(interaction_ids))
        grouped: dict[str, list[str]] = {}
        for batch in _batched(unique):
            rows = self._session.execute(
                select(InteractionParticipant.interaction_id, InteractionParticipant.person_id)
                .where(
                    InteractionParticipant.owner_id == self._owner_id,
                    InteractionParticipant.interaction_id.in_(batch),
                    InteractionParticipant.person_id.is_not(None),
                )
                .order_by(InteractionParticipant.interaction_id, InteractionParticipant.person_id)
            ).all()
            for interaction_id, person_id in rows:
                bucket = grouped.setdefault(interaction_id, [])
                if person_id not in bucket:
                    bucket.append(person_id)
        return {key: tuple(value) for key, value in grouped.items()}
