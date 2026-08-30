from fastapi import APIRouter

from app.api.deps import DbSession, RuntimeSettings
from app.services.preflight import DependencyPreflight

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def health(settings: RuntimeSettings) -> dict[str, str]:
    return {"status": "healthy", "version": settings.app_version}


@router.get("/deps")
def dependencies(db: DbSession, settings: RuntimeSettings) -> dict:
    return DependencyPreflight(db, settings).check()
