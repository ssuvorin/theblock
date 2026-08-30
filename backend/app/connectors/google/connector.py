"""One Google connection covering Gmail and Calendar.

The two surfaces share a grant, so they share a connection and a cursor document with one
key each. They do not share failure: an expired Gmail history cursor resyncs Gmail only and
leaves the Calendar checkpoint alone, because the alternative — failing the whole run — costs
the owner a bounded re-import of a surface that was perfectly healthy.
"""

from __future__ import annotations

from collections.abc import Iterator

from app.config import Settings
from app.connectors.base import (
    AuthChallenge,
    AuthGrant,
    CredentialStore,
    CursorInvalidated,
    SyncBatch,
    SyncMode,
)
from app.connectors.google.api import GMAIL_ROOT, GoogleApi
from app.connectors.google.calendar import CalendarSurface
from app.connectors.google.gmail import GmailSurface
from app.connectors.google.oauth import SCOPES, GoogleOAuth

SOURCE_TYPE = "google"
GMAIL_KEY = "gmail"
CALENDAR_KEY = "calendar"


class GoogleConnector:
    """Read-only Gmail and Calendar adapter for a single Google account."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._oauth = GoogleOAuth(settings)

    @property
    def source_type(self) -> str:
        return SOURCE_TYPE

    @property
    def capabilities(self) -> dict:
        return {
            "surfaces": [GmailSurface.source, CalendarSurface.source],
            "scopes": list(SCOPES),
            "lookback_days": self._settings.connector_lookback_days,
            "write_access": False,
            "delta": {"gmail": "historyId", "calendar": "syncToken"},
        }

    def initiate_auth(self, redirect_uri: str, state: str) -> AuthChallenge:
        return AuthChallenge(redirect_url=self._oauth.authorize_url(redirect_uri, state))

    def complete_auth(self, code: str, redirect_uri: str, pending: dict) -> AuthGrant:
        del pending
        credentials = self._oauth.exchange(code, redirect_uri)
        account = self._account_email(credentials)
        return AuthGrant(
            external_account_id=account,
            scopes=tuple(str(credentials.get("scope") or "").split()) or SCOPES,
            capabilities={**self.capabilities, "account": account},
            credentials={**credentials, "account": account},
        )

    def fetch(
        self,
        mode: SyncMode,
        cursor: dict,
        credentials: CredentialStore,
    ) -> Iterator[SyncBatch]:
        api = self._api(credentials)
        account = str(credentials.get().get("account") or "")
        state = dict(cursor)
        for surface, key in self._surfaces(api, account):
            for batch in self._drain(surface, key, mode, state):
                state = batch.cursor
                yield batch

    def revoke(self, credentials: dict) -> None:
        token = str(credentials.get("refresh_token") or credentials.get("access_token") or "")
        if token:
            self._oauth.revoke(token)

    def _surfaces(
        self,
        api: GoogleApi,
        account: str,
    ) -> tuple[tuple[GmailSurface | CalendarSurface, str], ...]:
        lookback = self._settings.connector_lookback_days
        pages = self._settings.connector_page_limit
        return (
            (GmailSurface(api, account, lookback, pages), GMAIL_KEY),
            (CalendarSurface(api, account, lookback, pages), CALENDAR_KEY),
        )

    def _drain(
        self,
        surface: GmailSurface | CalendarSurface,
        key: str,
        mode: SyncMode,
        state: dict,
    ) -> Iterator[SyncBatch]:
        checkpoint = str((state.get(key) or {}).get("cursor") or "")
        wants_delta = mode is SyncMode.DELTA and bool(checkpoint)
        try:
            yield from self._pages(surface, key, state, checkpoint if wants_delta else None)
        except CursorInvalidated:
            # Bounded resync of this surface only; the other surface keeps its checkpoint.
            yield from self._pages(surface, key, state, None, resynced=True)

    def _pages(
        self,
        surface: GmailSurface | CalendarSurface,
        key: str,
        state: dict,
        checkpoint: str | None,
        *,
        resynced: bool = False,
    ) -> Iterator[SyncBatch]:
        pages = surface.delta(checkpoint) if checkpoint else surface.initial()
        current = dict(state)
        for records, cursor in pages:
            current = _advance(current, key, cursor)
            yield SyncBatch(
                records=records,
                cursor=current,
                surface=surface.surface,
                resynced=resynced,
            )

    def _api(self, credentials: CredentialStore) -> GoogleApi:
        return GoogleApi(credentials, self._oauth, self._settings.connector_timeout_seconds)

    def _account_email(self, credentials: dict) -> str:
        """Read the address from Gmail rather than asking for a profile scope we do not need."""

        api = GoogleApi(
            _StaticCredentials(credentials),
            self._oauth,
            self._settings.connector_timeout_seconds,
        )
        profile = api.get(f"{GMAIL_ROOT}/profile")
        return str(profile.get("emailAddress") or "").casefold()


class _StaticCredentials:
    """Credential view used before a connection row exists to persist rotations into."""

    def __init__(self, credentials: dict) -> None:
        self._credentials = dict(credentials)

    def get(self) -> dict:
        return dict(self._credentials)

    def update(self, credentials: dict) -> None:
        self._credentials.update(credentials)


def _advance(state: dict, key: str, cursor: str) -> dict:
    updated = {name: dict(value) for name, value in state.items() if isinstance(value, dict)}
    updated[key] = {"cursor": cursor}
    return updated
