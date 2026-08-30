"""Read-only Collabute meeting import over MCP.

Scope is deliberate. The workspace grants ``meeting:write`` and ``calendar:write``, but the
only MCP tools behind them are ``meeting.delete`` and approval-gated ``propose_*`` calls —
nothing that can create a meeting, register a Meet link, or add a notetaker. So this adapter
reads and never writes, and the connections UI says exactly that.

Each sync opens one short-lived MCP session, lists recent meetings, and enriches each one
with ``meeting.get`` so summaries, decisions and action items arrive with the meeting rather
than in a second pass that could half-fail.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import timedelta

from app.config import Settings
from app.connectors.base import (
    AuthChallenge,
    AuthGrant,
    ConnectorNotConfigured,
    CredentialStore,
    NormalizedRecord,
    SourceUnavailable,
    SyncBatch,
    SyncMode,
)
from app.connectors.collabute import normalize
from app.connectors.collabute.mcp import McpProtocolError, McpSession, McpToolError
from app.connectors.collabute.oauth import CollabuteOAuth, new_pkce
from app.connectors.collabute.tools import (
    GET_MEETING,
    LIST_RECENT,
    PING,
    ToolBinding,
    ToolUnavailable,
)
from app.models import utcnow

logger = logging.getLogger(__name__)

SOURCE_TYPE = "collabute"
SURFACE = "collabute_meeting"
CURSOR_KEY = "meetings"
DEFAULT_LIMIT = 50


class CollabuteConnector:
    """Import meetings, participants, decisions and action items. Never write."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._oauth = CollabuteOAuth(settings)

    @property
    def source_type(self) -> str:
        return SOURCE_TYPE

    @property
    def capabilities(self) -> dict:
        return {
            "surfaces": [SURFACE],
            "scopes": self._settings.collabute_scopes.split(),
            "lookback_days": self._settings.connector_lookback_days,
            "write_access": False,
            "transport": "streamable_http_mcp",
            "endpoint": self._settings.collabute_mcp_url,
        }

    def initiate_auth(self, redirect_uri: str, state: str) -> AuthChallenge:
        """Build the AuthKit URL and stop. A human completes the login, never an agent."""

        verifier, challenge = new_pkce()
        client_id = self._oauth.client_id(redirect_uri)
        return AuthChallenge(
            redirect_url=self._oauth.authorize_url(redirect_uri, state, challenge, client_id),
            pending_secrets={"code_verifier": verifier, "client_id": client_id},
        )

    def complete_auth(self, code: str, redirect_uri: str, pending: dict) -> AuthGrant:
        verifier = str(pending.get("code_verifier") or "")
        client_id = str(pending.get("client_id") or "")
        if not verifier or not client_id:
            raise ConnectorNotConfigured(
                "the Collabute authorization attempt is missing its PKCE verifier"
            )
        credentials = self._oauth.exchange(code, redirect_uri, verifier, client_id)
        identity, binding = self._introspect(credentials)
        return AuthGrant(
            external_account_id=identity,
            scopes=tuple(str(credentials.get("scope") or "").split())
            or tuple(self._settings.collabute_scopes.split()),
            capabilities={**self.capabilities, **binding.capability_summary()},
            credentials=credentials,
        )

    def fetch(
        self,
        mode: SyncMode,
        cursor: dict,
        credentials: CredentialStore,
    ) -> Iterator[SyncBatch]:
        since = self._since(mode, cursor)
        with self._session(credentials) as session:
            binding = ToolBinding(session.list_tools())
            try:
                binding.require(LIST_RECENT)
            except ToolUnavailable as error:
                raise SourceUnavailable(str(error)) from error
            records = self._meetings(session, binding, since)
        latest = max((record.occurred_at for record in records), default=None)
        yield SyncBatch(
            records=records,
            cursor={CURSOR_KEY: {"cursor": (latest or utcnow()).isoformat()}},
            surface=SURFACE,
            resynced=since is None and mode is SyncMode.DELTA,
        )

    def revoke(self, credentials: dict) -> None:
        """Collabute publishes no revocation endpoint; forgetting the token is the revocation."""

        del credentials

    def _meetings(
        self,
        session: McpSession,
        binding: ToolBinding,
        since: str | None,
    ) -> tuple[NormalizedRecord, ...]:
        listed = session.call_tool(
            LIST_RECENT,
            binding.arguments(LIST_RECENT, limit=DEFAULT_LIMIT, since=since),
        )
        records = []
        for item in normalize.meeting_items(normalize.unwrap(listed)):
            enriched = self._enrich(session, binding, item)
            record = normalize.normalize_meeting(enriched)
            if record is not None:
                records.append(record)
        return tuple(records)

    def _enrich(self, session: McpSession, binding: ToolBinding, item: dict) -> dict:
        """Merge the detail view over the list entry, tolerating a per-meeting failure.

        One unreadable meeting must not cost the whole sync: the list entry is still a real
        interaction, so it is imported with whatever it already carries.
        """

        meeting_id = normalize.meeting_id(item)
        if not meeting_id or not binding.has(GET_MEETING):
            return item
        try:
            detail = session.call_tool(
                GET_MEETING,
                binding.arguments(GET_MEETING, meetingId=meeting_id),
            )
        except (McpToolError, McpProtocolError):
            logger.warning("collabute meeting %s could not be enriched", meeting_id)
            return item
        payload = normalize.unwrap(detail)
        merged = dict(item)
        if isinstance(payload, dict):
            merged.update({key: value for key, value in payload.items() if value is not None})
        return merged

    def _introspect(self, credentials: dict) -> tuple[str, ToolBinding]:
        """Identify the tenant and bind tools in one session, so connect fails fast."""

        with self._session(_StaticCredentials(credentials)) as session:
            binding = ToolBinding(session.list_tools())
            identity = ""
            if binding.has(PING):
                payload = normalize.unwrap(session.call_tool(PING, binding.arguments(PING)))
                identity = _tenant(payload)
        return identity or "collabute-workspace", binding

    def _session(self, credentials: CredentialStore) -> McpSession:
        return McpSession(
            self._settings.collabute_mcp_url,
            credentials,
            self._oauth,
            self._settings.connector_timeout_seconds,
        )

    def _since(self, mode: SyncMode, cursor: dict) -> str | None:
        """Delta means "since the newest meeting we stored"; initial means the whole window."""

        stored = str((cursor.get(CURSOR_KEY) or {}).get("cursor") or "")
        if mode is SyncMode.DELTA and stored:
            return stored
        horizon = utcnow() - timedelta(days=self._settings.connector_lookback_days)
        return horizon.isoformat()


class _StaticCredentials:
    """Credentials held in memory during connect, before a row exists to persist into."""

    def __init__(self, credentials: dict) -> None:
        self._credentials = dict(credentials)

    def get(self) -> dict:
        return dict(self._credentials)

    def update(self, credentials: dict) -> None:
        self._credentials.update(credentials)


def _tenant(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("organizationId", "organization_id", "tenantId", "workspaceId"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
