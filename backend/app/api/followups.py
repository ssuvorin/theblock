from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentOwner, DbSession, RuntimeSettings
from app.domain.schemas import FollowUpCreate, FollowUpPatch
from app.repositories.followups import FollowUpRepository
from app.services.presentation import follow_up_json

router = APIRouter(prefix="/api/followups", tags=["follow-ups"])


@router.get("")
def list_follow_ups(
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str = "due_date",
) -> dict:
    del sort
    repo = FollowUpRepository(db, owner.id, settings.demo_mode)
    return {
        "follow_ups": [follow_up_json(item, person) for item, person in repo.list(status_filter)]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_follow_up(
    payload: FollowUpCreate,
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
) -> dict:
    repo = FollowUpRepository(db, owner.id, settings.demo_mode)
    try:
        follow_up = repo.create(
            person_id=payload.person_id,
            reason=payload.reason,
            due_date=payload.due_date,
            due_timezone=payload.due_timezone,
            priority=payload.priority,
            source_key=payload.source_key,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"follow_up": follow_up_json(follow_up)}


@router.patch("/{follow_up_id}")
def patch_follow_up(
    follow_up_id: str,
    payload: FollowUpPatch,
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
) -> dict:
    repo = FollowUpRepository(db, owner.id, settings.demo_mode)
    follow_up = repo.get(follow_up_id)
    if follow_up is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up not found")
    changes = payload.model_dump(exclude_unset=True)
    return {"follow_up": follow_up_json(repo.update(follow_up, changes))}


@router.delete("/{follow_up_id}")
def delete_follow_up(
    follow_up_id: str,
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
) -> dict:
    repo = FollowUpRepository(db, owner.id, settings.demo_mode)
    follow_up = repo.get(follow_up_id)
    if follow_up is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up not found")
    repo.delete(follow_up)
    return {"id": follow_up_id, "deleted": True}
