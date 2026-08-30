"""Migrations must stay the faithful projection of the models.

The previous migration described a different schema than ``app/models.py`` — postgresql UUID
and JSONB columns against String(36) and JSON models, and it was missing a table entirely —
while never running anywhere. These tests make that class of drift impossible: adding a model
column without generating a migration fails here instead of at runtime on the demo.
"""

from __future__ import annotations

from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from app.models import Base
from app.schema import MIGRATIONS_DIR, upgrade_to_head
from sqlalchemy import Engine, create_engine, inspect


def _migrated() -> Engine:
    engine = create_engine("sqlite://")
    upgrade_to_head(engine)
    return engine


def _snapshot(engine: Engine) -> dict[str, dict[str, tuple[str, bool]]]:
    inspector = inspect(engine)
    return {
        table: {
            column["name"]: (str(column["type"]).upper(), bool(column["nullable"]))
            for column in inspector.get_columns(table)
        }
        for table in inspector.get_table_names()
        if table != "alembic_version"
    }


def test_migrations_exist_and_are_versioned() -> None:
    revisions = sorted(path.name for path in (MIGRATIONS_DIR / "versions").glob("*.py"))
    assert revisions, "the schema must be applied by a migration, not by create_all"


def test_migrated_schema_matches_the_models_exactly() -> None:
    expected = create_engine("sqlite://")
    Base.metadata.create_all(expected)
    assert _snapshot(_migrated()) == _snapshot(expected)


def test_every_model_table_is_migrated() -> None:
    migrated = set(_snapshot(_migrated()))
    assert migrated == set(Base.metadata.tables)


def test_autogenerate_reports_no_pending_changes() -> None:
    """A non-empty diff means a model changed without a matching migration."""

    engine = _migrated()
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        diff = compare_metadata(context, Base.metadata)
    relevant = [entry for entry in diff if _is_structural(entry)]
    assert relevant == [], f"models and migrations disagree: {relevant}"


def _is_structural(entry: object) -> bool:
    """Ignore index-only noise SQLite reflection invents; keep tables and columns."""

    if not isinstance(entry, tuple) or not entry:
        return False
    action = entry[0]
    if isinstance(action, list):
        return any(_is_structural(item) for item in action)
    return isinstance(action, str) and action.split("_")[0] in {"add", "remove", "modify"}
