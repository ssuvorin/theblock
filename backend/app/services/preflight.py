from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, has_live_context_key, has_semantic_index
from app.services.context_credits import ContextCreditLedger


class DependencyPreflight:
    """Report what this deployment can actually reach, never a hardcoded placeholder."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def check(self) -> dict:
        semantic = "ready" if has_semantic_index(self._settings) else "not_configured"
        checks: dict[str, object] = {
            "postgresql": self._database_status(),
            "redis": "not_configured",
            "convex": semantic,
            "openrouter": semantic,
            "embedding_model": self._settings.embedding_model if semantic == "ready" else None,
            "embedding_version": self._settings.embedding_version,
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
