from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.api.deps import CurrentOwner, DbSession, RuntimeSettings
from app.connectors.linkedin_export.importer import LinkedInImportPlan, load_linkedin_export
from app.connectors.linkedin_export.parse import LinkedInArchiveError
from app.models import Owner
from app.services.chunking import chunk_interaction
from app.services.graph_writer import ArchiveGraphWriter

router = APIRouter(prefix="/api/imports", tags=["imports"])
MAX_ARCHIVE_BYTES = 30 * 1024 * 1024
MAX_EXTRACTED_BYTES = 80 * 1024 * 1024
SYNTHETIC_FILENAME_MARKERS = ("synthetic", "demo", "fake")


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
) -> dict[str, object]:
    """Write the parsed archive into the canonical graph, reporting what changed."""

    try:
        report = ArchiveGraphWriter(session, owner).write(plan)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return report.as_dict()


@router.post("/linkedin")
async def import_linkedin_archive(
    archive: UploadFile,
    owner: CurrentOwner,
    settings: RuntimeSettings,
    session: DbSession,
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
    return {
        "status": "imported",
        "persistence": "postgresql",
        **summary,
        "written": persist_plan(session, owner, plan),
    }
