from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentOwner

router = APIRouter(prefix="/api/connections", tags=["connections"])
SUPPORTED_SOURCES = {"gmail", "whatsapp", "collabute"}


@router.get("")
def list_connections(owner: CurrentOwner) -> dict[str, list]:
    del owner
    return {"connections": []}


@router.post("/{source}/connect")
def connect_source(source: str, owner: CurrentOwner) -> dict:
    del owner
    if source not in SUPPORTED_SOURCES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown source")
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"{source} credentials are not configured for this demo deployment",
    )


@router.post("/{connection_id}/sync")
def sync_connection(connection_id: str, owner: CurrentOwner) -> dict:
    del connection_id, owner
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Source connection not found",
    )
