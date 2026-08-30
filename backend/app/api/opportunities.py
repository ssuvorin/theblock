from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentOwner, DbSession, RuntimeSettings
from app.domain.schemas import OpportunityPatch
from app.repositories.opportunities import OpportunityRepository
from app.services.opportunity_cards import OpportunityCardBuilder
from app.services.query.ranking import QueryRanker

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


@router.get("")
def list_opportunities(
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
    verification_status: str | None = None,
    saved: bool | None = None,
    organization_id: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    repo = OpportunityRepository(db, owner.id, settings.demo_mode)
    opportunities, total = repo.list(
        verification_status=verification_status,
        saved=saved,
        organization_id=organization_id,
        page=page,
        limit=limit,
    )
    cards = _builder(repo).cards(opportunities)
    return {"opportunities": cards, "total": total, "page": page}


@router.get("/{opportunity_id}")
def get_opportunity(
    opportunity_id: str,
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
) -> dict:
    repo = OpportunityRepository(db, owner.id, settings.demo_mode)
    opportunity = _required(repo, opportunity_id)
    return {"opportunity": _builder(repo).card(opportunity)}


@router.patch("/{opportunity_id}")
def patch_opportunity(
    opportunity_id: str,
    payload: OpportunityPatch,
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
) -> dict:
    repo = OpportunityRepository(db, owner.id, settings.demo_mode)
    opportunity = _required(repo, opportunity_id)
    repo.patch(opportunity, saved=payload.saved, dismissed=payload.dismissed)
    return {"opportunity": _builder(repo).card(opportunity)}


def _builder(repo: OpportunityRepository) -> OpportunityCardBuilder:
    return OpportunityCardBuilder(repo, QueryRanker())


def _required(repo: OpportunityRepository, opportunity_id: str):
    opportunity = repo.get(opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return opportunity
