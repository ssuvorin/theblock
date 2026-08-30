from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentOwner, DbSession, RuntimeSettings
from app.models import Organization, Person, Relationship
from app.repositories.people import PeopleRepository
from app.services.presentation import (
    follow_up_json,
    identity_json,
    interaction_json,
    organization_json,
    relationship_json,
)

router = APIRouter(prefix="/api/people", tags=["people"])


@router.get("")
def list_people(
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
    q: str | None = None,
    tag: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    repo = PeopleRepository(db, owner.id, settings.demo_mode)
    rows = repo.list(q=q, tag=tag, status=status_filter)
    total = len(rows)
    rows = rows[(page - 1) * limit : page * limit]
    person_ids = [person.id for person, _, _ in rows]
    identity_map = repo.identity_sources(person_ids)
    interaction_map = repo.interaction_sources(person_ids)
    people = [
        _person_summary(person, relationship, org, identity_map, interaction_map)
        for person, relationship, org in rows
    ]
    return {"people": people, "total": total, "page": page}


@router.get("/{person_id}")
def get_person(
    person_id: str,
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
) -> dict:
    repo = PeopleRepository(db, owner.id, settings.demo_mode)
    person = repo.get(person_id)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    interactions = repo.interactions(person.id)
    organization = repo.organization(person)
    identities = repo.identities(person.id)
    source_badges = sorted(
        {identity.source for identity in identities}
        | {interaction.source for interaction in interactions}
    )
    profile = {
        "id": person.id,
        "display_name": person.display_name,
        "photo_url": person.photo_url,
        "current_title": person.current_title,
        "current_org": organization_json(organization),
        "tags": person.tags,
        "manual_overrides": person.manual_overrides,
        "identities": [identity_json(item) for item in identities],
        "employments": _employment(person.current_title, organization),
        "relationship": relationship_json(repo.relationship(person.id)),
        "interactions": [interaction_json(item) for item in interactions],
        "documents": [],
        "memory_facts": [],
        "follow_ups": [follow_up_json(item) for item in repo.follow_ups(person.id)],
        "source_badges": source_badges,
        "data_origin": person.data_origin,
    }
    return {"person": profile}


def _person_summary(
    person: Person,
    relationship: Relationship | None,
    organization: Organization | None,
    identity_map: dict[str, set[str]],
    interaction_map: dict[str, set[str]],
) -> dict:
    sources = sorted(identity_map.get(person.id, set()) | interaction_map.get(person.id, set()))
    return {
        "id": person.id,
        "display_name": person.display_name,
        "photo_url": person.photo_url,
        "current_title": person.current_title,
        "current_org": organization.name if organization else None,
        "relationship_status": relationship.status if relationship else "unknown",
        "strength_score": relationship.strength_score if relationship else None,
        "last_interaction_at": relationship_json(relationship)["last_interaction_at"],
        "tags": person.tags,
        "sources": sources,
    }


def _employment(title: str | None, organization: Organization | None) -> list[dict]:
    if organization is None:
        return []
    return [{"title": title, "org": organization.name, "start": None, "current": True}]
