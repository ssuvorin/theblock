from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentOwner, DbSession, RuntimeSettings
from app.domain.schemas import DraftRequest
from app.services.draft_service import DraftService

router = APIRouter(prefix="/api/people", tags=["drafts"])


@router.post("/{person_id}/draft")
def create_draft(
    person_id: str,
    payload: DraftRequest,
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
) -> dict:
    try:
        draft = DraftService(db, owner, settings).create(
            person_id=person_id,
            opportunity_id=payload.opportunity_id,
            goal=payload.goal,
            action=payload.action,
            channel=payload.channel,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"draft": draft}
