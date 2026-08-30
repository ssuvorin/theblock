from fastapi.testclient import TestClient

from conftest import TEST_PASSWORD


def test_protected_route_requires_auth(client: TestClient) -> None:
    response = client.get("/api/owner/current")
    assert response.status_code == 401


def test_owner_cookie_and_bearer_compatibility(client: TestClient) -> None:
    response = client.post(
        "/api/auth/session",
        json={"email": "alex@example.test", "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie
    assert client.get("/api/owner/current").status_code == 200
    token = response.json()["access_token"]
    bearer = client.get("/api/owner/current", headers={"Authorization": f"Bearer {token}"})
    assert bearer.json()["owner"]["display_name"] == "Alex Ivanov"


def test_invalid_credentials_are_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/auth/session",
        json={"email": "alex@example.test", "password": "not-the-test-password"},
    )
    assert response.status_code == 401
