from fastapi import APIRouter

from app.api.deps import CurrentOwner, DbSession, RuntimeSettings
from app.domain.schemas import QueryRequest
from app.services.query.orchestrator import OpportunityQueryOrchestrator

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query")
def query(
    payload: QueryRequest,
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
) -> dict:
    return OpportunityQueryOrchestrator(db, owner, settings).execute(payload.question)
