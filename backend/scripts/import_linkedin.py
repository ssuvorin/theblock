"""Inspect a LinkedIn export through the real importer without persistence."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

try:  # Root invocation: python -m backend.scripts.import_linkedin
    from backend.app.connectors.linkedin_export.importer import (
        LinkedInImportPlan,
        load_linkedin_export,
    )
    from backend.app.services.chunking import chunk_interaction
    from backend.app.services.import_guard import DataOrigin, ImportOriginRejected
except ModuleNotFoundError as error:  # Backend invocation: python -m scripts.import_linkedin
    if error.name != "backend":
        raise
    from app.connectors.linkedin_export.importer import LinkedInImportPlan, load_linkedin_export
    from app.services.chunking import chunk_interaction
    from app.services.import_guard import DataOrigin, ImportOriginRejected


def safe_summary(plan: LinkedInImportPlan) -> dict[str, object]:
    """Build aggregate-only output containing no message text or identity values."""

    chunk_count = sum(
        len(chunk_interaction(message.external_id, 1, message.body_text))
        for message in plan.messages
    )
    return {
        "chunks_proposed": chunk_count,
        "conversations": plan.conversation_count,
        "data_origin": plan.data_origin,
        "empty_messages": plan.empty_message_count,
        "file_counts": dict(sorted(plan.file_counts.items())),
        "identity_hints": len(plan.identity_hints),
        "invitation_identity_matches": plan.invitation_identity_match_count,
        "invitations_seen": len(plan.invitations),
        "messages": plan.interaction_count,
        "people_proposed": len(plan.people),
        "unique_identities": plan.unique_identity_count,
        "warnings": len(plan.warnings),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument(
        "--origin",
        choices=tuple(origin.value for origin in DataOrigin),
        default=DataOrigin.REAL_IMPORT.value,
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.dry_run:
        parser.error("only --dry-run is available until a persistence adapter is injected")
    try:
        plan = load_linkedin_export(args.archive, data_origin=args.origin)
    except (ImportOriginRejected, ValueError) as error:
        print(f"import_rejected={error}", file=sys.stderr)
        return 2
    print(json.dumps(safe_summary(plan), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
