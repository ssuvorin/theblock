"""Streamable HTTP MCP client for Collabute, written against the transport not an SDK.

The official SDK is async-first and this codebase is synchronous everywhere else, so the
transport is implemented directly: it is one POST per JSON-RPC message, a response that may
arrive as JSON or as a single SSE frame, and a session id that must be echoed once issued.

The session is short-lived and closes on both success and failure, because Collabute counts
open sessions against a 60 requests/minute budget and a leaked one is a sync that eventually
starts failing for reasons nobody can see.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from types import TracebackType

import httpx

from app.connectors.base import CredentialStore, RateLimited, ReauthRequired, SourceUnavailable
from app.connectors.collabute.oauth import CollabuteOAuth
from app.models import utcnow

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2025-06-18"
CLIENT_NAME = "second-brain-crm"
CLIENT_VERSION = "0.1.0"
SESSION_HEADER = "Mcp-Session-Id"
ACCEPT = "application/json, text/event-stream"


class McpProtocolError(SourceUnavailable):
    """The server answered, but not with something the protocol allows."""


class McpToolError(RuntimeError):
    """A tool ran and reported failure. That is the tool's answer, not a transport fault."""


class McpSession:
    """One initialize/use/close cycle against the Collabute MCP endpoint."""

    def __init__(
        self,
        url: str,
        credentials: CredentialStore,
        oauth: CollabuteOAuth,
        timeout: float,
    ) -> None:
        self._url = url
        self._credentials = credentials
        self._oauth = oauth
        self._client = httpx.Client(timeout=timeout)
        self._session_id: str | None = None
        self._server_info: dict = {}
        self._next_id = 0

    def __enter__(self) -> McpSession:
        self.initialize()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def server_info(self) -> dict:
        return dict(self._server_info)

    def initialize(self) -> dict:
        result = self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
            },
        )
        self._server_info = result if isinstance(result, dict) else {}
        self._notify("notifications/initialized")
        return self._server_info

    def list_tools(self) -> list[dict]:
        """Enumerate the tools this workspace exposes; nothing else may be called."""

        tools: list[dict] = []
        cursor: str | None = None
        while True:
            result = self._request("tools/list", {"cursor": cursor} if cursor else {})
            page = result.get("tools") if isinstance(result, dict) else None
            tools.extend(item for item in page or [] if isinstance(item, dict))
            cursor = result.get("nextCursor") if isinstance(result, dict) else None
            if not cursor:
                return tools

    def call_tool(self, name: str, arguments: dict) -> dict:
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        if not isinstance(result, dict):
            raise McpProtocolError(f"tool {name} returned a non-object result")
        if result.get("isError"):
            raise McpToolError(f"tool {name} reported an error: {_error_text(result)}")
        return result

    def close(self) -> None:
        """Release the server-side session, tolerating servers that do not support DELETE."""

        try:
            if self._session_id:
                self._client.request("DELETE", self._url, headers=self._headers())
        except httpx.HTTPError:
            logger.debug("Collabute MCP session delete failed; the session will lapse")
        finally:
            self._session_id = None
            self._client.close()

    def _request(self, method: str, params: dict) -> dict:
        self._next_id += 1
        envelope = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        response = self._send(envelope)
        self._capture_session(response)
        return _result(_payload(response, self._next_id), method)

    def _notify(self, method: str) -> None:
        response = self._send({"jsonrpc": "2.0", "method": method})
        self._capture_session(response)

    def _send(self, envelope: dict) -> httpx.Response:
        response = self._post(envelope, self._token())
        if response.status_code in {401, 403}:
            response = self._post(envelope, self._refresh())
        return self._checked(response)

    def _post(self, envelope: dict, token: str) -> httpx.Response:
        try:
            return self._client.post(self._url, json=envelope, headers=self._headers(token))
        except httpx.HTTPError as error:
            raise SourceUnavailable(f"Collabute MCP request failed: {error}") from error

    def _checked(self, response: httpx.Response) -> httpx.Response:
        if response.status_code in {401, 403}:
            raise ReauthRequired("Collabute rejected the refreshed access token")
        if response.status_code == 429:
            raise RateLimited("Collabute asked us to slow down", _retry_after(response))
        if response.status_code >= 500:
            raise SourceUnavailable(f"Collabute MCP returned {response.status_code}")
        if response.status_code >= 400:
            raise McpProtocolError(
                f"Collabute MCP returned {response.status_code}: {response.text[:200]}"
            )
        return response

    def _headers(self, token: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {token or self._token()}",
            "Accept": ACCEPT,
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        }
        if self._session_id:
            headers[SESSION_HEADER] = self._session_id
        return headers

    def _capture_session(self, response: httpx.Response) -> None:
        issued = response.headers.get(SESSION_HEADER)
        if issued:
            self._session_id = issued

    def _token(self) -> str:
        credentials = self._credentials.get()
        if _expired(credentials.get("expires_at")):
            return self._refresh()
        token = str(credentials.get("access_token") or "")
        return token or self._refresh()

    def _refresh(self) -> str:
        """Rotation is mandatory here: the new refresh token is stored before it is used."""

        current = self._credentials.get()
        refresh_token = str(current.get("refresh_token") or "")
        client_id = str(current.get("client_id") or "")
        if not refresh_token or not client_id:
            raise ReauthRequired("no Collabute refresh token is stored for this connection")
        refreshed = self._oauth.refresh(refresh_token, client_id)
        self._credentials.update(refreshed)
        return refreshed["access_token"]


def _payload(response: httpx.Response, request_id: int) -> dict:
    """Accept both transport shapes: a plain JSON body or SSE frames carrying one."""

    if response.status_code == 202 or not response.content:
        return {}
    content_type = response.headers.get("Content-Type", "")
    if "text/event-stream" in content_type:
        return _from_event_stream(response.text, request_id)
    try:
        body = response.json()
    except ValueError as error:
        raise McpProtocolError("Collabute MCP response was not JSON") from error
    return body if isinstance(body, dict) else {}


def _from_event_stream(text: str, request_id: int) -> dict:
    """Pick the frame answering our id; servers may interleave notifications."""

    fallback: dict = {}
    for frame in text.split("\n\n"):
        data = "".join(
            line[len("data:") :].strip() for line in frame.splitlines() if line.startswith("data:")
        )
        if not data:
            continue
        try:
            parsed = json.loads(data)
        except ValueError:
            continue
        if not isinstance(parsed, dict):
            continue
        if parsed.get("id") == request_id:
            return parsed
        fallback = fallback or parsed
    return fallback


def _result(payload: dict, method: str) -> dict:
    error = payload.get("error")
    if isinstance(error, dict):
        raise McpProtocolError(f"{method} failed: {error.get('message') or error}")
    result = payload.get("result")
    return result if isinstance(result, dict) else {}


def _error_text(result: dict) -> str:
    blocks = result.get("content")
    if not isinstance(blocks, list):
        return "no detail"
    texts = [
        str(item.get("text")) for item in blocks if isinstance(item, dict) and item.get("text")
    ]
    return " ".join(texts)[:200] or "no detail"


def _expired(expires_at: object) -> bool:
    if not isinstance(expires_at, str) or not expires_at:
        return True
    try:
        return datetime.fromisoformat(expires_at) <= utcnow()
    except ValueError:
        return True


def _retry_after(response: httpx.Response) -> float | None:
    header = response.headers.get("Retry-After")
    if not header:
        return None
    try:
        return float(header)
    except ValueError:
        return None
