from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentOwner, DbSession, RuntimeSettings
from app.repositories.people import InteractionRepository, PeopleRepository
from app.services.presentation import interaction_json

router = APIRouter(prefix="/api", tags=["interactions"])


@router.get("/people/{person_id}/interactions")
def person_interactions(
    person_id: str,
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
    source: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    repo = PeopleRepository(db, owner.id, settings.demo_mode)
    if repo.get(person_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    interactions = repo.interactions(person_id, source)
    total = len(interactions)
    selected = interactions[(page - 1) * limit : page * limit]
    return {
        "interactions": [interaction_json(item) for item in selected],
        "total": total,
        "page": page,
    }


@router.get("/interactions/{interaction_id}")
def interaction_detail(
    interaction_id: str,
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
) -> dict:
    repo = InteractionRepository(db, owner.id, settings.demo_mode)
    interaction = repo.get(interaction_id)
    if interaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interaction not found")
    result = interaction_json(interaction)
    result["body_text"] = interaction.body_text
    result["participants"] = [
        {
            "person_id": participant.person_id,
            "display_name": person.display_name if person else None,
            "source_address": participant.source_address,
            "role": participant.role,
        }
        for participant, person in repo.participants(interaction.id)
    ]
    return {"interaction": result}
