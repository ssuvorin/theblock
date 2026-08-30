"""Source connection lifecycle: catalog, authorize, callback, status, sync, pause, delete.

Two decisions are worth reading before changing anything here.

The callback is not session-authenticated. It is a top-level browser navigation from the
provider, so instead of hoping a cookie survives the redirect, the one-time ``state`` nonce is
looked up and it carries the owner. The nonce is single-use, expiring, and stored only as a
hash, which is what makes that safe.

Syncs return 202 and run as a background task on their own session. A sync that took a minute
inside the request would hold a connection open and time out the browser, and the owner can
poll ``/status`` for progress that is recorded per run.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.api.deps import CurrentOwner, DbSession, RuntimeSettings
from app.config import Settings
from app.connectors.base import (
    ConnectorError,
    SourceStatus,
    SyncMode,
)
from app.connectors.registry import AVAILABLE, ConnectorRegistry
from app.database import Database
from app.domain.identity.normalize import IdentityKind
from app.models import OAuthAuthorization, Owner, SourceConnection, SyncRun
from app.repositories.connections import (
    OAuthAuthorizationRepository,
    SourceConnectionRepository,
    SyncRunRepository,
    new_state,
)
from app.services.connector_graph import ConnectorGraphWriter
from app.services.connector_sync import ConnectionPaused, ConnectorSyncService
from app.services.secret_vault import SecretVault, SecretVaultUnavailable
from app.services.source_deletion import delete_connection_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/connections", tags=["connections"])
PENDING_PURPOSE = "oauth_pending"
TOKEN_PURPOSE = "oauth_tokens"


def connection_json(connection: SourceConnection, item_count: int | None = None) -> dict:
    return {
        "id": connection.id,
        "source": connection.source,
        "external_account_id": connection.external_account_id or None,
        "status": connection.status,
        "paused": connection.paused,
        "scopes": list(connection.scopes or []),
        "capabilities": dict(connection.capabilities or {}),
        "sync_cursor": dict(connection.sync_cursor or {}),
        "last_sync_at": _iso(connection.last_sync_at),
        "last_error": connection.last_error,
        "consent_granted_at": _iso(connection.consent_granted_at),
        "item_count": item_count,
    }


def sync_run_json(run: SyncRun) -> dict:
    return {
        "id": run.id,
        "mode": run.mode,
        "status": run.status,
        "processed": run.processed,
        "skipped": run.skipped,
        "errors": run.errors,
        "counters": dict(run.counters or {}),
        "error_message": run.error_message,
        "started_at": _iso(run.started_at),
        "finished_at": _iso(run.finished_at),
    }


@router.get("")
def list_connections(owner: CurrentOwner, db: DbSession) -> dict:
    connections = SourceConnectionRepository(db, owner.id).all()
    return {"connections": [connection_json(item) for item in connections]}


@router.get("/sources")
def list_sources(owner: CurrentOwner, settings: RuntimeSettings) -> dict:
    """The catalog is the consent disclosure: what is declared here is what is requested."""

    del owner
    return {"sources": ConnectorRegistry(settings).catalog()}


@router.post("/{source}/connect")
def connect_source(
    source: str,
    request: Request,
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
) -> dict:
    registry = ConnectorRegistry(settings)
    if not registry.known(source):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown source")
    availability, reason = registry.availability(source)
    if availability != AVAILABLE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reason)
    connector = registry.get(source)
    redirect_uri = _redirect_uri(request, settings, source)
    vault = SecretVault(db, owner.id, settings)
    connection = SourceConnectionRepository(db, owner.id).pending(source, connector.capabilities)
    # One state, one challenge: the nonce is minted first so the PKCE verifier that gets
    # vaulted is the same one embedded in the redirect the browser receives.
    state = new_state()
    try:
        challenge = connector.initiate_auth(redirect_uri, state)
    except ConnectorError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    secret_ref = (
        vault.store(PENDING_PURPOSE, challenge.pending_secrets)
        if challenge.pending_secrets
        else None
    )
    OAuthAuthorizationRepository(db, owner.id).open(
        source,
        state,
        redirect_uri,
        secret_ref,
        settings.oauth_state_minutes,
    )
    db.commit()
    return {
        "connection_id": connection.id,
        "redirect_url": challenge.redirect_url,
        "qr_code_base64": challenge.qr_code_base64,
        "state_expires_in_minutes": settings.oauth_state_minutes,
    }


@router.get("/{source}/callback")
def oauth_callback(
    source: str,
    request: Request,
    db: DbSession,
    settings: RuntimeSettings,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Redeem the code and always land the owner back on the connections screen."""

    if error or not code or not state:
        return _back(settings, source, "error", error or "authorization was not completed")
    attempt = OAuthAuthorizationRepository(db).consume(source, state)
    if attempt is None:
        return _back(settings, source, "error", "authorization state is invalid or expired")
    # Burn the nonce before the exchange. Rolling back a failed exchange would otherwise undo
    # the consumption too and leave the state replayable for the rest of its lifetime.
    db.commit()
    owner = db.get(Owner, attempt.owner_id)
    if owner is None:
        return _back(settings, source, "error", "owner no longer exists")
    try:
        _finish(db, owner, settings, source, code, attempt)
    except (ConnectorError, SecretVaultUnavailable) as failure:
        db.rollback()
        logger.warning("%s authorization failed: %s", source, failure)
        return _back(settings, source, "error", str(failure))
    db.commit()
    return _back(settings, source, "ok", None)


def _finish(
    db: DbSession,
    owner: Owner,
    settings: Settings,
    source: str,
    code: str,
    attempt: OAuthAuthorization,
) -> SourceConnection:
    connector = ConnectorRegistry(settings).get(source)
    vault = SecretVault(db, owner.id, settings)
    pending = vault.load(attempt.secret_ref) if attempt.secret_ref else {}
    grant = connector.complete_auth(code, attempt.redirect_uri, pending)
    vault.delete(attempt.secret_ref)
    connections = SourceConnectionRepository(db, owner.id)
    connection = connections.promote(
        connections.pending(source, grant.capabilities),
        external_account_id=grant.external_account_id,
        auth_ref=vault.store(TOKEN_PURPOSE, grant.credentials),
        scopes=grant.scopes,
        capabilities=grant.capabilities,
    )
    _bind_owner_identity(db, owner, connection, grant.external_account_id)
    return connection


def _bind_owner_identity(
    db: DbSession,
    owner: Owner,
    connection: SourceConnection,
    account: str,
) -> None:
    """Claim the authorized address for the owner so their own messages resolve to self."""

    if "@" not in account:
        return
    ConnectorGraphWriter(db, owner, connection).attach_owner_identity(
        IdentityKind.EMAIL,
        account,
    )


@router.get("/{connection_id}/status")
def connection_status(connection_id: str, owner: CurrentOwner, db: DbSession) -> dict:
    connection = _require(db, owner, connection_id)
    runs = SyncRunRepository(db, owner.id).recent(connection.id)
    return {
        **connection_json(connection),
        "sync_runs": [sync_run_json(item) for item in runs],
    }


@router.post("/{connection_id}/sync", status_code=status.HTTP_202_ACCEPTED)
def sync_connection(
    connection_id: str,
    request: Request,
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
    background: BackgroundTasks,
    full: bool = False,
) -> dict:
    connection = _require(db, owner, connection_id)
    if connection.paused:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Connection is paused")
    if not connection.auth_ref:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Connection is not authorized yet",
        )
    mode = SyncMode.INITIAL if full else None
    background.add_task(
        run_sync,
        request.app.state.database,
        owner.id,
        connection.id,
        settings,
        mode,
    )
    return {"connection_id": connection.id, "status": "queued", "mode": mode or "auto"}


def run_sync(
    database: Database,
    owner_id: str,
    connection_id: str,
    settings: Settings,
    mode: SyncMode | None,
) -> None:
    """Sync on a session of its own so one source's failure cannot affect another."""

    with database.session_factory() as session:
        owner = session.get(Owner, owner_id)
        connection = session.get(SourceConnection, connection_id)
        if owner is None or connection is None:
            return
        try:
            ConnectorSyncService(session, owner, settings).run(connection, mode)
        except (ConnectorError, ConnectionPaused, SecretVaultUnavailable):
            logger.exception("sync failed for connection %s", connection_id)
            session.rollback()
        except Exception:
            logger.exception("sync crashed for connection %s", connection_id)
            session.rollback()
            raise


@router.post("/{connection_id}/pause")
def pause_connection(connection_id: str, owner: CurrentOwner, db: DbSession) -> dict:
    return _set_paused(db, owner, connection_id, paused=True)


@router.post("/{connection_id}/resume")
def resume_connection(connection_id: str, owner: CurrentOwner, db: DbSession) -> dict:
    return _set_paused(db, owner, connection_id, paused=False)


def _set_paused(db: DbSession, owner: Owner, connection_id: str, *, paused: bool) -> dict:
    connection = _require(db, owner, connection_id)
    connection.paused = paused
    db.commit()
    return {"id": connection.id, "paused": connection.paused, "status": connection.status}


@router.delete("/{connection_id}")
def disconnect_source(
    connection_id: str,
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
    delete_data: bool = False,
) -> dict:
    """Revoke at the provider, forget the credentials, and optionally drop the imported data."""

    connection = _require(db, owner, connection_id)
    vault = SecretVault(db, owner.id, settings)
    _try_revoke(connection, settings, vault)
    deleted = delete_connection_data(db, owner, connection) if delete_data else 0
    vault.delete(connection.auth_ref)
    connection.auth_ref = None
    SourceConnectionRepository(db, owner.id).delete(connection)
    db.commit()
    return {
        "id": connection_id,
        "status": SourceStatus.DISCONNECTED.value,
        "data_deleted": bool(delete_data),
        "interactions_deleted": deleted,
    }


def _try_revoke(connection: SourceConnection, settings: Settings, vault: SecretVault) -> None:
    if not connection.auth_ref:
        return
    try:
        connector = ConnectorRegistry(settings).get(connection.source)
        connector.revoke(vault.load(connection.auth_ref))
    except (ConnectorError, SecretVaultUnavailable) as error:
        # Disconnect must always succeed locally; a provider that refuses is still disconnected.
        logger.info("revocation skipped for %s: %s", connection.source, error)


def _require(db: DbSession, owner: Owner, connection_id: str) -> SourceConnection:
    connection = SourceConnectionRepository(db, owner.id).by_id(connection_id)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source connection not found",
        )
    return connection


def _redirect_uri(request: Request, settings: Settings, source: str) -> str:
    base = settings.api_base_url.rstrip("/") or str(request.base_url).rstrip("/")
    return f"{base}/api/connections/{source}/callback"


def _back(settings: Settings, source: str, outcome: str, reason: str | None) -> RedirectResponse:
    query = f"?status={outcome}&source={source}"
    if reason:
        query += f"&reason={reason[:200]}"
    target = f"{settings.frontend_base_url.rstrip('/')}/settings/connections{query}"
    return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)


def _iso(value: object) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None
