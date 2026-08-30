"""Google OAuth2 for a server-side confidential client.

The code exchange happens here and nowhere else: the browser only ever carries an
authorization code, and the client secret never leaves the backend. Scopes are a fixed
read-only tuple rather than a parameter, so no caller can widen them.
"""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.connectors.base import ConnectorNotConfigured, ReauthRequired, SourceUnavailable
from app.models import utcnow

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
SCOPES: tuple[str, ...] = (GMAIL_SCOPE, CALENDAR_SCOPE)
REFRESH_SKEW_SECONDS = 300


class GoogleOAuth:
    """Build authorization URLs and trade codes and refresh tokens for access tokens."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._timeout = settings.connector_timeout_seconds

    def authorize_url(self, redirect_uri: str, state: str) -> str:
        """`prompt=consent` every time, because Google only issues a refresh token then."""

        query = urlencode(
            {
                "client_id": self._client_id(),
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": " ".join(SCOPES),
                "state": state,
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "false",
            }
        )
        return f"{AUTH_URL}?{query}"

    def exchange(self, code: str, redirect_uri: str) -> dict:
        payload = {
            "code": code,
            "client_id": self._client_id(),
            "client_secret": self._client_secret(),
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        return self._credentials(self._post(payload))

    def refresh(self, refresh_token: str) -> dict:
        payload = {
            "refresh_token": refresh_token,
            "client_id": self._client_id(),
            "client_secret": self._client_secret(),
            "grant_type": "refresh_token",
        }
        body = self._post(payload)
        # Google omits refresh_token on refresh; keeping the old one is required, not optional.
        return self._credentials(body, fallback_refresh=refresh_token)

    def revoke(self, token: str) -> None:
        """Best effort: an already-invalid grant is the outcome we wanted anyway."""

        try:
            with httpx.Client(timeout=self._timeout) as client:
                client.post(REVOKE_URL, data={"token": token})
        except httpx.HTTPError:
            return

    def _post(self, payload: dict) -> dict:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(TOKEN_URL, data=payload)
        except httpx.HTTPError as error:
            raise SourceUnavailable(f"Google token endpoint unreachable: {error}") from error
        if response.status_code == 400 and _is_invalid_grant(response):
            raise ReauthRequired("Google refused the grant; the owner must re-authorize")
        if response.status_code >= 400:
            raise SourceUnavailable(f"Google token endpoint returned {response.status_code}")
        try:
            return response.json()
        except ValueError as error:
            raise SourceUnavailable("Google token response was not JSON") from error

    @staticmethod
    def _credentials(body: dict, fallback_refresh: str | None = None) -> dict:
        expires_in = int(body.get("expires_in") or 0)
        expires_at = utcnow() + timedelta(seconds=max(0, expires_in - REFRESH_SKEW_SECONDS))
        refresh_token = body.get("refresh_token") or fallback_refresh
        if not refresh_token:
            raise ReauthRequired(
                "Google returned no refresh token; re-authorize with consent prompted"
            )
        return {
            "access_token": str(body.get("access_token") or ""),
            "refresh_token": str(refresh_token),
            "scope": str(body.get("scope") or " ".join(SCOPES)),
            "expires_at": expires_at.isoformat(),
        }

    def _client_id(self) -> str:
        value = (self._settings.google_client_id or "").strip()
        if not value:
            raise ConnectorNotConfigured("GOOGLE_CLIENT_ID is not set")
        return value

    def _client_secret(self) -> str:
        secret = self._settings.google_client_secret
        value = secret.get_secret_value().strip() if secret else ""
        if not value:
            raise ConnectorNotConfigured("GOOGLE_CLIENT_SECRET is not set")
        return value


def _is_invalid_grant(response: httpx.Response) -> bool:
    try:
        return str(response.json().get("error")) == "invalid_grant"
    except ValueError:
        return False
