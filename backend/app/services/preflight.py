from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, has_live_context_key
from app.services.context_credits import ContextCreditLedger


class DependencyPreflight:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def check(self) -> dict:
        checks: dict[str, object] = {
            "postgresql": self._database_status(),
            "redis": "not_configured",
            "convex": "not_configured",
            "openrouter": "not_configured",
            "evolution": "not_configured",
            "google_oauth": "not_configured",
            "collabute": "not_configured",
        }
        snapshot = ContextCreditLedger(self._session).snapshot()
        checks["context_dev"] = {
            "web_search": "ready",
            "provider_mode": "live" if has_live_context_key(self._settings) else "synthetic_demo",
            **snapshot,
        }
        return checks

    def _database_status(self) -> str:
        try:
            self._session.execute(text("SELECT 1"))
        except Exception:
            return "unhealthy"
        return "healthy"
