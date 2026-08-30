"""Apply the schema through Alembic, which is the only thing that creates tables.

``app/models.py`` is where the schema is authored and ``app/migrations`` is how it is
applied — everywhere, including tests. Migrations live inside the package so they ship with
the installed wheel instead of depending on the working directory.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def alembic_config(connection: Connection) -> Config:
    """Build a config bound to an existing connection rather than a URL."""

    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.attributes["connection"] = connection
    return config


def upgrade_to_head(engine: Engine) -> None:
    """Bring the database to the latest revision inside a single transaction."""

    with engine.begin() as connection:
        command.upgrade(alembic_config(connection), "head")
