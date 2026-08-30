from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import (
    Settings,
    has_live_context_key,
    has_secret_vault,
    has_semantic_index,
)
from app.connectors.registry import AVAILABLE, ConnectorRegistry
from app.services.context_credits import ContextCreditLedger


class DependencyPreflight:
    """Report what this deployment can actually reach, never a hardcoded placeholder."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def check(self) -> dict:
        semantic = "ready" if has_semantic_index(self._settings) else "not_configured"
        registry = ConnectorRegistry(self._settings)
        checks: dict[str, object] = {
            "postgresql": self._database_status(),
            "redis": "not_configured",
            "convex": semantic,
            "openrouter": semantic,
            "embedding_model": self._settings.embedding_model if semantic == "ready" else None,
            "embedding_version": self._settings.embedding_version,
            "secret_vault": "ready" if has_secret_vault(self._settings) else "not_configured",
            "evolution": "not_configured",
            "google_oauth": self._source(registry, "google"),
            "collabute": self._source(registry, "collabute"),
            "meeting_scheduling": self._scheduling(),
        }
        snapshot = ContextCreditLedger(self._session).snapshot()
        checks["context_dev"] = {
            "web_search": "ready",
            "provider_mode": "live" if has_live_context_key(self._settings) else "synthetic_demo",
            **snapshot,
        }
        return checks

    def _source(self, registry: ConnectorRegistry, source: str) -> str:
        """Report configuration, not connection: this endpoint has no owner to look one up for."""

        availability, _ = registry.availability(source)
        return "ready" if availability == AVAILABLE else availability

    def _scheduling(self) -> str:
        if not self._settings.google_meeting_scheduling:
            return "disabled"
        return "ready" if has_secret_vault(self._settings) else "not_configured"

    def _database_status(self) -> str:
        try:
            self._session.execute(text("SELECT 1"))
        except Exception:
            return "unhealthy"
        return "healthy"
