"""The contract every source adapter implements, and the vocabulary it speaks.

Adapters know how to authorize against one provider and how to page through it. They never
touch the database, never decide what a person is, and never own a transaction — that keeps
each provider's quirks isolated in one file and lets the sync service treat Gmail, Calendar
and Collabute identically.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable


class SourceStatus(StrEnum):
    DISCONNECTED = "disconnected"
    AUTHORIZING = "authorizing"
    CONNECTED = "connected"
    SYNCING = "syncing"
    DEGRADED = "degraded"
    REAUTH_REQUIRED = "reauth_required"
    ERROR = "error"


class SyncMode(StrEnum):
    INITIAL = "initial"
    DELTA = "delta"


class ConnectorError(RuntimeError):
    """Base class for failures an adapter can report without being a defect."""


class ConnectorNotConfigured(ConnectorError):
    """The deployment has no credentials for this source, so it cannot be connected."""


class ReauthRequired(ConnectorError):
    """The grant is gone or revoked. The cursor stays put until a human re-consents."""


class CursorInvalidated(ConnectorError):
    """The provider dropped our checkpoint, so this surface needs a bounded resync."""

    def __init__(self, message: str, surface: str | None = None) -> None:
        super().__init__(message)
        self.surface = surface


class SourceUnavailable(ConnectorError):
    """A transport or provider-side failure. Retryable, and never a lost cursor."""


class RateLimited(SourceUnavailable):
    """The provider asked us to slow down; ``retry_after`` is seconds when it said so."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(frozen=True, slots=True)
class NormalizedParticipant:
    """One counterpart on an interaction, with whatever is known about their identity."""

    source_address: str
    role: str
    display_name: str | None = None
    identity_hint: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NormalizedRecord:
    """One provider artifact expressed in the canonical shape the graph writer accepts."""

    external_id: str
    type: str
    source: str
    occurred_at: datetime
    direction: str | None = None
    subject: str | None = None
    body_text: str | None = None
    participants: tuple[NormalizedParticipant, ...] = ()
    metadata: dict = field(default_factory=dict)
    raw_ref: str = ""
    content_version: int = 1
    is_deleted: bool = False


@dataclass(frozen=True, slots=True)
class SyncBatch:
    """A page of records plus the cursor that is safe to persist once they are written."""

    records: tuple[NormalizedRecord, ...]
    cursor: dict
    surface: str
    resynced: bool = False


@dataclass(frozen=True, slots=True)
class AuthChallenge:
    """What the owner has to do next, and the short-lived secrets that attempt needs."""

    redirect_url: str | None = None
    qr_code_base64: str | None = None
    pending_secrets: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuthGrant:
    """A completed authorization: who it belongs to, what it allows, what to encrypt."""

    external_account_id: str
    scopes: tuple[str, ...]
    capabilities: dict
    credentials: dict


class CredentialStore(Protocol):
    """Read-write access to one connection's credentials, persisting every rotation."""

    def get(self) -> dict: ...

    def update(self, credentials: dict) -> None: ...


@runtime_checkable
class SourceConnector(Protocol):
    """Contract for all source adapters. Registering one requires no core changes."""

    @property
    def source_type(self) -> str:
        """Extensible string identifier, for example ``google`` or ``collabute``."""
        ...

    @property
    def capabilities(self) -> dict:
        """Declared surfaces, scopes and limits, shown to the owner before first sync."""
        ...

    def initiate_auth(self, redirect_uri: str, state: str) -> AuthChallenge:
        """Begin the authorization the owner has to complete in a browser."""
        ...

    def complete_auth(self, code: str, redirect_uri: str, pending: dict) -> AuthGrant:
        """Exchange the callback code for credentials and identify the account."""
        ...

    def fetch(
        self,
        mode: SyncMode,
        cursor: dict,
        credentials: CredentialStore,
    ) -> Iterator[SyncBatch]:
        """Yield pages of normalized records, newest cursor last."""
        ...

    def revoke(self, credentials: dict) -> None:
        """Best-effort credential revocation at the provider."""
        ...
