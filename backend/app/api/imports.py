import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, UploadFile, status

from app.api.deps import CurrentOwner, DbSession, RuntimeSettings
from app.config import Settings
from app.connectors.linkedin_export.importer import LinkedInImportPlan, load_linkedin_export
from app.connectors.linkedin_export.parse import LinkedInArchiveError
from app.database import Database
from app.models import Owner
from app.services.chunking import chunk_interaction
from app.services.demo_reset import DemoSeedReset
from app.services.graph_writer import ArchiveGraphWriter
from app.services.semantic_runtime import build_runtime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/imports", tags=["imports"])
MAX_ARCHIVE_BYTES = 30 * 1024 * 1024
MAX_EXTRACTED_BYTES = 80 * 1024 * 1024
SYNTHETIC_FILENAME_MARKERS = ("synthetic", "demo", "fake")
DRAIN_BATCH = 40


def import_summary(plan: LinkedInImportPlan) -> dict[str, object]:
    messages = plan.messages
    return {
        "data_origin": plan.data_origin,
        "messages": plan.interaction_count,
        "conversations": plan.conversation_count,
        "people_proposed": len(plan.people),
        "unique_identities": plan.unique_identity_count,
        "empty_messages": plan.empty_message_count,
        "drafts_skipped": plan.drafts_skipped,
        "connections_seen": plan.connections_seen,
        "connections_matched": plan.connections_matched,
        "owner_resolution": {
            "method": plan.owner_resolution_method,
            "confidence": plan.owner_resolution_confidence,
        },
        "warnings": list(plan.warnings),
        "chunks_proposed": sum(
            len(chunk_interaction(message.external_id, 1, message.body_text))
            for message in messages
        ),
    }


def extract_archive(content: bytes, destination: Path) -> Path:
    archive_path = destination / "archive.zip"
    archive_path.write_bytes(content)
    try:
        with ZipFile(archive_path) as zipped:
            members = zipped.infolist()
            if sum(item.file_size for item in members) > MAX_EXTRACTED_BYTES:
                raise HTTPException(status_code=413, detail="Extracted archive is too large")
            unsafe_path = any(
                Path(item.filename).is_absolute() or ".." in Path(item.filename).parts
                for item in members
            )
            if unsafe_path:
                raise HTTPException(status_code=400, detail="Archive contains an unsafe path")
            zipped.extractall(destination / "export")
    except BadZipFile as error:
        raise HTTPException(status_code=400, detail="Archive is not a valid ZIP file") from error
    messages = next((destination / "export").rglob("messages.csv"), None)
    return messages.parent if messages else destination / "export"


def persist_plan(
    session: DbSession,
    owner: Owner,
    plan: LinkedInImportPlan,
    settings: RuntimeSettings,
) -> dict[str, object]:
    """Write the parsed archive into the canonical graph, reporting what changed.

    The demo seed is cleared first: it carries its own self person and its own copies of the
    same contacts, so leaving it in place would give the owner two identities and duplicate
    every person who appears in both.

    Indexing is queued in the same transaction rather than performed here: embeddings are a
    paid external call, so the owner gets their graph immediately and the vector store
    catches up afterwards without the import being able to lose it.
    """

    demo_removed = DemoSeedReset(session, owner).run()
    try:
        report = ArchiveGraphWriter(session, owner).write(plan)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    written = report.as_dict()
    written["demo_seed_cleared"] = demo_removed.as_dict()
    written["semantic_index"] = queue_for_indexing(session, owner, settings)
    return written


def queue_for_indexing(
    session: DbSession,
    owner: Owner,
    settings: RuntimeSettings,
) -> dict[str, object]:
    """Enqueue every stored interaction and report the queue without contacting a provider."""

    runtime = build_runtime(session, owner.id, settings)
    enqueued = runtime.indexer.enqueue_owner_interactions()
    return {
        "provider": runtime.status,
        "embedding_version": settings.embedding_version,
        "enqueued": enqueued,
        "pending": runtime.outbox.pending_count(),
    }


def drain_after_import(database: Database, owner_id: str, settings: Settings) -> None:
    """Work the queue down after the response, on a session of its own.

    The request session is already closed by now, and a provider failure must not surface as a
    failed import: the graph is committed and every unfinished row stays claimable.
    """

    with database.session_factory() as session:
        runtime = build_runtime(session, owner_id, settings)
        if not runtime.configured:
            return
        try:
            while runtime.outbox.pending_count():
                if runtime.indexer.drain(limit=DRAIN_BATCH).interactions_indexed == 0:
                    break
                session.commit()
        except Exception:
            logger.exception("semantic drain stopped for owner %s; queue is retryable", owner_id)
            session.rollback()
        else:
            session.commit()


@router.post("/linkedin")
async def import_linkedin_archive(
    request: Request,
    archive: UploadFile,
    owner: CurrentOwner,
    settings: RuntimeSettings,
    session: DbSession,
    background: BackgroundTasks,
    dry_run: bool = False,
) -> dict[str, object]:
    """Import a LinkedIn export into the owner's graph, or validate it without writing."""

    filename = (archive.filename or "").casefold()
    if settings.demo_mode and not any(marker in filename for marker in SYNTHETIC_FILENAME_MARKERS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hosted demo accepts synthetic archives only",
        )
    content = await archive.read(MAX_ARCHIVE_BYTES + 1)
    if len(content) > MAX_ARCHIVE_BYTES:
        raise HTTPException(status_code=413, detail="Archive is too large")
    with TemporaryDirectory() as temporary:
        root = extract_archive(content, Path(temporary))
        try:
            plan = load_linkedin_export(root, data_origin="synthetic", demo_mode=settings.demo_mode)
        except LinkedInArchiveError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
    summary = import_summary(plan)
    if dry_run:
        return {"status": "validated", "persistence": "dry_run", **summary}
    written = persist_plan(session, owner, plan, settings)
    background.add_task(drain_after_import, request.app.state.database, owner.id, settings)
    return {
        "status": "imported",
        "persistence": "postgresql",
        **summary,
        "written": written,
    }
