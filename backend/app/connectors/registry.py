"""The composition root for source adapters, and the catalog the owner sees.

Adding a source is one entry in ``_DESCRIPTORS`` plus one factory line. Nothing in the sync
service, the graph writer, entity resolution, or the query path knows the list of sources.

The catalog doubles as the pre-sync consent disclosure required by FR-13.1: whatever a
source declares here is exactly what the UI promises before the owner authorizes it, so a
scope cannot be requested without being shown.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.config import Settings, has_collabute, has_google_oauth, has_secret_vault
from app.connectors.base import ConnectorNotConfigured, SourceConnector
from app.connectors.collabute.connector import CollabuteConnector
from app.connectors.google.connector import GoogleConnector
from app.connectors.google.oauth import scopes_for

AVAILABLE = "available"
NOT_CONFIGURED = "not_configured"
UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class SourceDescriptor:
    """Everything the owner is told about a source before any data is read."""

    source: str
    label: str
    kind: str
    surfaces: tuple[str, ...]
    scopes: tuple[str, ...]
    processors: tuple[str, ...]
    disclosure: str
    lookback_days: int | None = None
    write_access: bool = False
    requirements: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self, availability: str, reason: str | None) -> dict:
        return {
            "source": self.source,
            "label": self.label,
            "kind": self.kind,
            "availability": availability,
            "reason": reason,
            "surfaces": list(self.surfaces),
            "scopes": list(self.scopes),
            "processors": list(self.processors),
            "disclosure": self.disclosure,
            "lookback_days": self.lookback_days,
            "write_access": self.write_access,
            "requirements": list(self.requirements),
        }


READ_DISCLOSURE = (
    "Reads mail metadata, plain-text bodies and calendar events for the selected account. "
    "Message bodies are chunked into the semantic index via OpenRouter and Convex."
)
WRITE_DISCLOSURE = (
    " Scheduling is enabled, so this app can also create one calendar event with a Google "
    "Meet link and email the guests you name — only when you press the button, never "
    "automatically. It still cannot send mail, or modify or delete anything that exists."
)
COLLABUTE_DISCLOSURE = (
    "Imports existing meetings over MCP: title, time, participants, summary, decisions and "
    "action items. Read-only — Collabute's MCP surface exposes no tool that creates a "
    "meeting or adds a notetaker, so this app never schedules, records or transcribes on "
    "Collabute's behalf. The human login step is completed by you in the browser."
)


def descriptors_for(settings: Settings) -> tuple[SourceDescriptor, ...]:
    """Build the catalog from settings so a declared scope is always the requested scope."""

    scheduling = settings.google_meeting_scheduling
    return (
        SourceDescriptor(
            source="google",
            label="Google (Gmail + Calendar)",
            kind="oauth",
            surfaces=("gmail", "google_calendar"),
            scopes=scopes_for(settings),
            processors=("OpenRouter (embeddings)", "Convex (semantic index)"),
            disclosure=READ_DISCLOSURE + (WRITE_DISCLOSURE if scheduling else ""),
            lookback_days=settings.connector_lookback_days,
            write_access=scheduling,
            requirements=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "ENCRYPTION_KEY"),
        ),
        SourceDescriptor(
            source="collabute",
            label="Collabute meetings",
            kind="oauth_pkce",
            surfaces=("collabute_meeting",),
            scopes=tuple(settings.collabute_scopes.split()),
            processors=("Collabute (MCP)", "OpenRouter (embeddings)", "Convex (semantic index)"),
            disclosure=COLLABUTE_DISCLOSURE,
            lookback_days=settings.connector_lookback_days,
            write_access=False,
            requirements=("ENCRYPTION_KEY",),
        ),
        SourceDescriptor(
            source="whatsapp",
            label="WhatsApp",
            kind="qr",
            surfaces=("whatsapp",),
            scopes=(),
            processors=(),
            disclosure="Not built on this deployment. Nothing is read and nothing is synced.",
            write_access=False,
            requirements=("EVOLUTION_API_URL", "EVOLUTION_API_KEY"),
        ),
    )


class ConnectorRegistry:
    """Resolve a source name to a configured adapter, or explain why it cannot."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._descriptors = descriptors_for(settings)
        self._factories: dict[str, Callable[[], SourceConnector]] = {
            "google": lambda: GoogleConnector(settings),
            "collabute": lambda: CollabuteConnector(settings),
        }

    @property
    def descriptors(self) -> tuple[SourceDescriptor, ...]:
        return self._descriptors

    def known(self, source: str) -> bool:
        return any(item.source == source for item in self._descriptors)

    def availability(self, source: str) -> tuple[str, str | None]:
        if source not in self._factories:
            return UNSUPPORTED, "This deployment does not implement the source."
        if not has_secret_vault(self._settings):
            return NOT_CONFIGURED, "ENCRYPTION_KEY is unset, so tokens cannot be stored."
        if source == "google" and not has_google_oauth(self._settings):
            return NOT_CONFIGURED, "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are unset."
        if source == "collabute" and not has_collabute(self._settings):
            return NOT_CONFIGURED, "COLLABUTE_MCP_URL is unset."
        return AVAILABLE, None

    def catalog(self) -> list[dict]:
        entries = []
        for descriptor in self._descriptors:
            availability, reason = self.availability(descriptor.source)
            entries.append(descriptor.as_dict(availability, reason))
        return entries

    def get(self, source: str) -> SourceConnector:
        availability, reason = self.availability(source)
        if availability != AVAILABLE:
            raise ConnectorNotConfigured(reason or f"{source} is not available")
        return self._factories[source]()
