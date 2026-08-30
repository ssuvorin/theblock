"""The connections API over HTTP: honest availability, safe callbacks, real lifecycle.

The callback tests matter most. It is the one unauthenticated route in the product, so the
state nonce is the whole of its security and every way of getting it wrong is asserted here.
"""

from __future__ import annotations

import base64
import os
from collections.abc import Iterator

import pytest
from app.config import Settings
from app.main import create_app
from app.models import OAuthAuthorization, Owner, SourceConnection, SourceSecret, utcnow
from app.repositories.connections import hash_state
from fastapi.testclient import TestClient
from sqlalchemy import select

from conftest import TEST_PASSWORD, TEST_SECRET

ENCRYPTION_KEY = base64.urlsafe_b64encode(os.urandom(32)).decode()


def _settings(**overrides: object) -> Settings:
    base = {
        "database_url": "sqlite://",
        "auth_secret": TEST_SECRET,
        "owner_password": TEST_PASSWORD,
        "demo_mode": True,
        "seed_demo_data": True,
        "api_base_url": "https://api.test",
        "frontend_base_url": "https://app.test",
    }
    return Settings(**{**base, **overrides})


@pytest.fixture
def configured_client() -> Iterator[TestClient]:
    settings = _settings(
        encryption_key=ENCRYPTION_KEY,
        google_client_id="client-id",
        google_client_secret="client-secret",
    )
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        yield client


@pytest.fixture
def bare_client() -> Iterator[TestClient]:
    with TestClient(create_app(_settings()), base_url="https://testserver") as client:
        yield client


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/session",
        json={"email": "alex@example.test", "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _session(client: TestClient):
    return client.app.state.database.session_factory()


def test_the_catalog_declares_exactly_the_scopes_that_will_be_requested(
    configured_client: TestClient,
) -> None:
    response = configured_client.get("/api/connections/sources", headers=_auth(configured_client))

    assert response.status_code == 200
    sources = {item["source"]: item for item in response.json()["sources"]}
    google = sources["google"]
    assert google["availability"] == "available"
    assert google["write_access"] is False
    assert all("readonly" in scope for scope in google["scopes"])
    assert google["disclosure"]
    assert sources["collabute"]["write_access"] is False
    assert "no tool that creates a meeting" in sources["collabute"]["disclosure"]


def test_an_unconfigured_source_says_what_is_missing_instead_of_offering_connect(
    bare_client: TestClient,
) -> None:
    headers = _auth(bare_client)

    catalog = {
        item["source"]: item
        for item in bare_client.get("/api/connections/sources").json()["sources"]
    }
    assert catalog["google"]["availability"] == "not_configured"
    assert "ENCRYPTION_KEY" in catalog["google"]["reason"]

    refused = bare_client.post("/api/connections/google/connect", headers=headers)
    assert refused.status_code == 409
    assert "ENCRYPTION_KEY" in refused.json()["detail"]


def test_whatsapp_is_reported_unsupported_rather_than_broken(
    configured_client: TestClient,
) -> None:
    headers = _auth(configured_client)
    catalog = {
        item["source"]: item
        for item in configured_client.get("/api/connections/sources").json()["sources"]
    }

    assert catalog["whatsapp"]["availability"] == "unsupported"
    assert configured_client.post("/api/connections/whatsapp/connect", headers=headers).status_code
    assert (
        configured_client.post("/api/connections/whatsapp/connect", headers=headers).status_code
        == 409
    )


def test_an_unknown_source_is_a_404(configured_client: TestClient) -> None:
    response = configured_client.post(
        "/api/connections/telegram/connect",
        headers=_auth(configured_client),
    )
    assert response.status_code == 404


def test_connect_returns_a_google_redirect_and_records_one_pending_attempt(
    configured_client: TestClient,
) -> None:
    response = configured_client.post(
        "/api/connections/google/connect",
        headers=_auth(configured_client),
    )

    assert response.status_code == 200
    url = response.json()["redirect_url"]
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "calendar.events" not in url, "the write scope must not be requested by default"
    with _session(configured_client) as session:
        attempts = list(session.scalars(select(OAuthAuthorization)))
        assert len(attempts) == 1
        assert attempts[0].source == "google"
        assert attempts[0].consumed_at is None
        connections = list(session.scalars(select(SourceConnection)))
        assert [item.status for item in connections] == ["authorizing"]


def test_the_state_nonce_is_stored_only_as_a_hash(configured_client: TestClient) -> None:
    """A database dump must not be enough to forge a callback."""

    state = _open_attempt(configured_client, source="google")

    with _session(configured_client) as session:
        attempt = session.scalars(select(OAuthAuthorization)).one()
        assert attempt.state_hash == hash_state(state)
        assert state not in attempt.state_hash


def test_a_state_can_only_be_redeemed_once(configured_client: TestClient) -> None:
    state = _open_attempt(configured_client, source="google")
    params = {"code": "abc", "state": state}

    first = configured_client.get(
        "/api/connections/google/callback", params=params, follow_redirects=False
    )
    second = configured_client.get(
        "/api/connections/google/callback", params=params, follow_redirects=False
    )

    # The first attempt fails at the token exchange because Google is unreachable in tests, but
    # it must still burn the nonce so a replay cannot reuse it.
    assert "status=error" in first.headers["location"]
    assert "invalid or expired" in second.headers["location"].replace("%20", " ")


def test_a_callback_without_a_code_lands_on_the_error_screen(
    configured_client: TestClient,
) -> None:
    response = configured_client.get(
        "/api/connections/google/callback",
        params={"error": "access_denied"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://app.test/settings/connections?status=error")
    assert "access_denied" in location


def test_an_unknown_state_is_refused(configured_client: TestClient) -> None:
    response = configured_client.get(
        "/api/connections/google/callback",
        params={"code": "abc", "state": "not-a-real-state"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "status=error" in response.headers["location"]
    assert "invalid+or+expired" in response.headers["location"].replace("%20", "+")


def test_a_state_from_another_source_is_refused(configured_client: TestClient) -> None:
    state = _open_attempt(configured_client, source="collabute")

    response = configured_client.get(
        "/api/connections/google/callback",
        params={"code": "abc", "state": state},
        follow_redirects=False,
    )

    assert "status=error" in response.headers["location"]


def test_an_expired_state_is_refused(configured_client: TestClient) -> None:
    state = _open_attempt(configured_client, source="google", expired=True)

    response = configured_client.get(
        "/api/connections/google/callback",
        params={"code": "abc", "state": state},
        follow_redirects=False,
    )

    assert "status=error" in response.headers["location"]


def _open_attempt(client: TestClient, *, source: str, expired: bool = False) -> str:
    from datetime import timedelta

    state = "state-under-test"
    with _session(client) as session:
        owner = session.scalars(select(Owner)).first()
        assert owner is not None
        session.add(
            OAuthAuthorization(
                owner_id=owner.id,
                source=source,
                state_hash=hash_state(state),
                redirect_uri="https://api.test/api/connections/x/callback",
                expires_at=utcnow() - timedelta(minutes=1)
                if expired
                else utcnow() + timedelta(minutes=10),
            )
        )
        session.commit()
    return state


def test_sync_and_status_require_a_real_connection(configured_client: TestClient) -> None:
    headers = _auth(configured_client)

    assert (
        configured_client.post("/api/connections/missing/sync", headers=headers).status_code == 404
    )
    assert (
        configured_client.get("/api/connections/missing/status", headers=headers).status_code == 404
    )


def test_an_unauthorized_connection_cannot_be_synced(configured_client: TestClient) -> None:
    headers = _auth(configured_client)
    connection_id = configured_client.post(
        "/api/connections/google/connect",
        headers=headers,
    ).json()["connection_id"]

    response = configured_client.post(f"/api/connections/{connection_id}/sync", headers=headers)

    assert response.status_code == 409
    assert "not authorized" in response.json()["detail"]


def test_pause_and_resume_are_reflected_in_the_listing(configured_client: TestClient) -> None:
    headers = _auth(configured_client)
    connection_id = configured_client.post(
        "/api/connections/google/connect",
        headers=headers,
    ).json()["connection_id"]

    assert configured_client.post(
        f"/api/connections/{connection_id}/pause", headers=headers
    ).json()["paused"]
    paused = configured_client.post(f"/api/connections/{connection_id}/sync", headers=headers)
    assert paused.status_code == 409

    assert not configured_client.post(
        f"/api/connections/{connection_id}/resume", headers=headers
    ).json()["paused"]
    listing = configured_client.get("/api/connections", headers=headers).json()["connections"]
    assert listing[0]["paused"] is False


def test_disconnect_forgets_the_credentials(configured_client: TestClient) -> None:
    headers = _auth(configured_client)
    connection_id = configured_client.post(
        "/api/connections/google/connect",
        headers=headers,
    ).json()["connection_id"]

    response = configured_client.delete(
        f"/api/connections/{connection_id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "disconnected"
    with _session(configured_client) as session:
        assert list(session.scalars(select(SourceConnection))) == []
        assert list(session.scalars(select(SourceSecret))) == []


def test_a_connection_response_never_carries_a_token(configured_client: TestClient) -> None:
    headers = _auth(configured_client)
    configured_client.post("/api/connections/google/connect", headers=headers)

    body = configured_client.get("/api/connections", headers=headers).text

    assert "auth_ref" not in body
    assert "access_token" not in body
    assert "refresh_token" not in body
