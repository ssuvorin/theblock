"""Collabute OAuth 2.1: discovery, dynamic client registration, and PKCE.

Collabute is a public client with no secret, so PKCE is the only thing binding the callback
to the request that started it — the verifier is generated here, vaulted, and never leaves
the backend. Refresh tokens rotate on every use and the new one must be stored, otherwise
the next sync arrives with a token Collabute has already retired.

The human AuthKit login is deliberately not automated. This module builds the URL and stops.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode, urlsplit

import httpx

from app.config import Settings
from app.connectors.base import ReauthRequired, SourceUnavailable
from app.models import utcnow

DISCOVERY_PATH = "/.well-known/oauth-authorization-server"
REFRESH_SKEW_RATIO = 0.8
VERIFIER_BYTES = 64


@dataclass(frozen=True, slots=True)
class AuthorizationServer:
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str | None


def new_pkce() -> tuple[str, str]:
    """Return an S256 verifier and its challenge."""

    verifier = _b64(secrets.token_bytes(VERIFIER_BYTES))
    challenge = _b64(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


class CollabuteOAuth:
    """Resolve endpoints, register a client on demand, and trade codes for tokens."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._timeout = settings.connector_timeout_seconds
        self._resource = settings.collabute_mcp_url.rstrip("/")
        self._base = _origin(self._resource)
        self._server: AuthorizationServer | None = None

    @property
    def resource(self) -> str:
        return self._resource

    def server(self) -> AuthorizationServer:
        """Prefer published metadata; fall back to the documented paths if it is absent."""

        if self._server is None:
            self._server = self._discover() or self._documented_endpoints()
        return self._server

    def client_id(self, redirect_uri: str) -> str:
        """Use the configured client if there is one, otherwise register one now."""

        configured = (self._settings.collabute_client_id or "").strip()
        if configured:
            return configured
        return self._register(redirect_uri)

    def authorize_url(
        self,
        redirect_uri: str,
        state: str,
        challenge: str,
        client_id: str,
    ) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": self._settings.collabute_scopes,
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "resource": self._resource,
            }
        )
        return f"{self.server().authorization_endpoint}?{query}"

    def exchange(self, code: str, redirect_uri: str, verifier: str, client_id: str) -> dict:
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "resource": self._resource,
        }
        return self._credentials(self._token(payload), client_id)

    def refresh(self, refresh_token: str, client_id: str) -> dict:
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "resource": self._resource,
        }
        body = self._token(payload)
        return self._credentials(body, client_id, fallback_refresh=refresh_token)

    def _discover(self) -> AuthorizationServer | None:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(f"{self._base}{DISCOVERY_PATH}")
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None
        try:
            body = response.json()
        except ValueError:
            return None
        authorize = str(body.get("authorization_endpoint") or "")
        token = str(body.get("token_endpoint") or "")
        if not authorize or not token:
            return None
        registration = body.get("registration_endpoint")
        return AuthorizationServer(
            authorization_endpoint=authorize,
            token_endpoint=token,
            registration_endpoint=str(registration) if registration else None,
        )

    def _documented_endpoints(self) -> AuthorizationServer:
        return AuthorizationServer(
            authorization_endpoint=f"{self._resource}/oauth/authorize",
            token_endpoint=f"{self._resource}/oauth/token",
            registration_endpoint=f"{self._resource}/oauth/register",
        )

    def _register(self, redirect_uri: str) -> str:
        endpoint = self.server().registration_endpoint
        if not endpoint:
            raise SourceUnavailable(
                "Collabute published no registration endpoint; set COLLABUTE_CLIENT_ID"
            )
        payload = {
            "redirect_uris": [redirect_uri],
            "client_name": "Career Brain",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        }
        body = self._post(endpoint, json_payload=payload)
        client_id = str(body.get("client_id") or "")
        if not client_id:
            raise SourceUnavailable("Collabute registration returned no client_id")
        return client_id

    def _token(self, payload: dict) -> dict:
        return self._post(self.server().token_endpoint, form_payload=payload)

    def _post(
        self,
        url: str,
        *,
        form_payload: dict | None = None,
        json_payload: dict | None = None,
    ) -> dict:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, data=form_payload, json=json_payload)
        except httpx.HTTPError as error:
            raise SourceUnavailable(f"Collabute OAuth endpoint unreachable: {error}") from error
        if response.status_code in {400, 401} and _needs_reauth(response):
            raise ReauthRequired("Collabute refused the grant; the owner must re-authorize")
        if response.status_code >= 400:
            raise SourceUnavailable(f"Collabute OAuth returned {response.status_code}")
        try:
            return response.json()
        except ValueError as error:
            raise SourceUnavailable("Collabute OAuth response was not JSON") from error

    @staticmethod
    def _credentials(body: dict, client_id: str, fallback_refresh: str | None = None) -> dict:
        access_token = str(body.get("access_token") or "")
        if not access_token:
            raise SourceUnavailable("Collabute returned no access token")
        expires_in = int(body.get("expires_in") or 0)
        # Refresh at 80% of the lifetime so a long sync never starts on a nearly dead token.
        lifetime = timedelta(seconds=max(0, int(expires_in * REFRESH_SKEW_RATIO)))
        return {
            "access_token": access_token,
            "refresh_token": str(body.get("refresh_token") or fallback_refresh or ""),
            "scope": str(body.get("scope") or ""),
            "client_id": client_id,
            "expires_at": (utcnow() + lifetime).isoformat(),
        }


def _needs_reauth(response: httpx.Response) -> bool:
    try:
        error = str(response.json().get("error") or "")
    except ValueError:
        return False
    return error in {"invalid_grant", "invalid_token", "unauthorized_client", "access_denied"}


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
