from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.api.deps import CurrentOwner, RuntimeSettings
from app.connectors.linkedin_export.importer import LinkedInImportPlan, load_linkedin_export
from app.services.chunking import chunk_interaction

router = APIRouter(prefix="/api/imports", tags=["imports"])
MAX_ARCHIVE_BYTES = 30 * 1024 * 1024
MAX_EXTRACTED_BYTES = 80 * 1024 * 1024


def import_summary(plan: LinkedInImportPlan) -> dict[str, object]:
    messages = plan.messages
    return {
        "status": "validated",
        "persistence": "dry_run",
        "data_origin": plan.data_origin,
        "messages": plan.interaction_count,
        "conversations": plan.conversation_count,
        "people_proposed": len(plan.people),
        "unique_identities": plan.unique_identity_count,
        "empty_messages": plan.empty_message_count,
        "invitation_people_created": plan.people_created_from_invitations,
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


@router.post("/linkedin")
async def inspect_linkedin_archive(
    archive: UploadFile,
    owner: CurrentOwner,
    settings: RuntimeSettings,
) -> dict[str, object]:
    del owner
    filename = (archive.filename or "").casefold()
    if settings.demo_mode and "synthetic" not in filename:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hosted demo accepts synthetic archives only",
        )
    content = await archive.read(MAX_ARCHIVE_BYTES + 1)
    if len(content) > MAX_ARCHIVE_BYTES:
        raise HTTPException(status_code=413, detail="Archive is too large")
    with TemporaryDirectory() as temporary:
        root = extract_archive(content, Path(temporary))
        plan = load_linkedin_export(root, data_origin="synthetic", demo_mode=settings.demo_mode)
    return import_summary(plan)
