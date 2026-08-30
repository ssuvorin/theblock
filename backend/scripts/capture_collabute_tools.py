#!/usr/bin/env python3
"""Capture or verify the Collabute ``tools/list`` fixture the adapter is written against.

FR-4.3 requires the tool inventory to be a versioned artifact rather than an assumption, and
the tool names are OAuth-gated, so the fixture can only come from an authorized workspace.
This script is the one supported way to refresh it.

The human AuthKit login is never automated here. Authorize the connection in the browser
first, then run this against the stored credentials.

    python -m scripts.capture_collabute_tools --owner-email owner@example.test --check
    python -m scripts.capture_collabute_tools --owner-email owner@example.test --write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.config import Settings
from app.connectors.collabute.mcp import McpSession
from app.connectors.collabute.oauth import CollabuteOAuth
from app.connectors.collabute.tools import FIXTURE_PATH, ToolBinding
from app.database import Database
from app.models import Owner, SourceConnection
from app.services.secret_vault import SecretVault, VaultCredentials
from sqlalchemy import select

SOURCE = "collabute"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-email", required=True)
    parser.add_argument(
        "--write",
        action="store_true",
        help="overwrite the committed fixture with the live tool list",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero when the live tool list has drifted from the fixture",
    )
    return parser.parse_args(argv)


def load_tools(settings: Settings, owner_email: str) -> list[dict]:
    """Open one MCP session against the owner's stored Collabute grant."""

    database = Database(settings)
    with database.session_factory() as session:
        owner = session.scalar(select(Owner).where(Owner.email == owner_email.casefold()))
        if owner is None:
            raise SystemExit(f"no owner with email {owner_email}")
        connection = session.scalar(
            select(SourceConnection).where(
                SourceConnection.owner_id == owner.id,
                SourceConnection.source == SOURCE,
            )
        )
        if connection is None or not connection.auth_ref:
            raise SystemExit("Collabute is not connected; authorize it in the browser first")
        credentials = VaultCredentials(
            SecretVault(session, owner.id, settings),
            connection.auth_ref,
        )
        with McpSession(
            settings.collabute_mcp_url,
            credentials,
            CollabuteOAuth(settings),
            settings.connector_timeout_seconds,
        ) as mcp:
            tools = mcp.list_tools()
        session.commit()
    return tools


def report(tools: list[dict]) -> int:
    binding = ToolBinding(tools)
    drift = binding.drift()
    print(f"{len(tools)} tools exposed by this workspace:")
    for name in binding.names:
        print(f"  - {name}")
    if drift.required_missing:
        print(f"\nMISSING REQUIRED: {', '.join(drift.required_missing)}", file=sys.stderr)
    if not drift.fixture_available:
        print("\nno committed fixture to compare against", file=sys.stderr)
        return 1
    if drift.matches:
        print("\nlive tool list matches the committed fixture")
        return 0
    print("\nDRIFT from the committed fixture:", file=sys.stderr)
    for name in drift.missing:
        print(f"  gone:  {name}", file=sys.stderr)
    for name in drift.added:
        print(f"  new:   {name}", file=sys.stderr)
    return 1


def write_fixture(tools: list[dict], path: Path = FIXTURE_PATH) -> None:
    path.write_text(json.dumps({"tools": tools}, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(tools)} tools to {path}")


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(argv)
    settings = Settings()
    tools = load_tools(settings, arguments.owner_email)
    status = report(tools)
    if arguments.write:
        write_fixture(tools)
        return 0
    return status if arguments.check else 0


if __name__ == "__main__":
    raise SystemExit(main())
