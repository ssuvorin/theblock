"""One authenticated JSON reader for every Google surface.

It owns the two things both surfaces get wrong when written twice: refreshing an expired
access token exactly once per call (persisting it, so the next sync starts valid) and turning
Google's status codes into the connector vocabulary. A dead cursor stays a distinguishable
``GoogleApiError`` because 404 means "resync Gmail" and 410 means "resync Calendar" — the
surface decides, not the transport.
"""

from __future__ import annotations

from datetime import datetime

import httpx

from app.connectors.base import CredentialStore, RateLimited, ReauthRequired, SourceUnavailable
from app.connectors.google.oauth import GoogleOAuth
from app.models import utcnow

GMAIL_ROOT = "https://gmail.googleapis.com/gmail/v1/users/me"
CALENDAR_ROOT = "https://www.googleapis.com/calendar/v3"
RATE_LIMIT_REASONS = frozenset({"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded"})


class GoogleApiError(RuntimeError):
    """A 4xx the caller has to interpret, carrying the status and Google's reason."""

    def __init__(self, status_code: int, reason: str) -> None:
        super().__init__(f"Google API returned {status_code}: {reason}")
        self.status_code = status_code
        self.reason = reason


class GoogleApi:
    """Bearer-authenticated reads against Gmail and Calendar."""

    def __init__(self, credentials: CredentialStore, oauth: GoogleOAuth, timeout: float) -> None:
        self._credentials = credentials
        self._oauth = oauth
        self._timeout = timeout

    def get(self, url: str, params: dict | None = None) -> dict:
        token = self._token()
        response = self._send(url, params, token)
        if response.status_code == 401:
            response = self._send(url, params, self._refresh())
        return self._decode(response)

    def _send(self, url: str, params: dict | None, token: str) -> httpx.Response:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                return client.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.HTTPError as error:
            raise SourceUnavailable(f"Google request failed: {error}") from error

    def _decode(self, response: httpx.Response) -> dict:
        if response.status_code == 401:
            raise ReauthRequired("Google rejected the refreshed access token")
        if response.status_code == 429:
            raise RateLimited("Google asked us to slow down", _retry_after(response))
        reason = _reason(response)
        if response.status_code == 403 and reason in RATE_LIMIT_REASONS:
            raise RateLimited(f"Google quota hit: {reason}", _retry_after(response))
        if 400 <= response.status_code < 500:
            raise GoogleApiError(response.status_code, reason)
        if response.status_code >= 500:
            raise SourceUnavailable(f"Google returned {response.status_code}")
        try:
            return response.json()
        except ValueError as error:
            raise SourceUnavailable("Google response was not JSON") from error

    def _token(self) -> str:
        credentials = self._credentials.get()
        if _expired(credentials.get("expires_at")):
            return self._refresh()
        token = str(credentials.get("access_token") or "")
        if not token:
            return self._refresh()
        return token

    def _refresh(self) -> str:
        """Refresh and persist immediately, so a later failure cannot lose the new token."""

        current = self._credentials.get()
        refresh_token = str(current.get("refresh_token") or "")
        if not refresh_token:
            raise ReauthRequired("no Google refresh token is stored for this connection")
        refreshed = self._oauth.refresh(refresh_token)
        self._credentials.update(refreshed)
        return refreshed["access_token"]


def _expired(expires_at: object) -> bool:
    if not isinstance(expires_at, str) or not expires_at:
        return True
    try:
        deadline = datetime.fromisoformat(expires_at)
    except ValueError:
        return True
    return deadline <= utcnow()


def _reason(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:120]
    error = body.get("error")
    if isinstance(error, str):
        return error
    if not isinstance(error, dict):
        return "unknown"
    errors = error.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        return str(errors[0].get("reason") or error.get("status") or "unknown")
    return str(error.get("status") or error.get("message") or "unknown")


def _retry_after(response: httpx.Response) -> float | None:
    header = response.headers.get("Retry-After")
    if not header:
        return None
    try:
        return float(header)
    except ValueError:
        return None
