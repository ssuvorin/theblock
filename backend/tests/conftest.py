import os
import secrets

import pytest
from fastapi.testclient import TestClient

TEST_SECRET = secrets.token_urlsafe(40)
TEST_PASSWORD = secrets.token_urlsafe(14)
os.environ["CRM_AUTH_SECRET"] = TEST_SECRET
os.environ["CRM_OWNER_PASSWORD"] = TEST_PASSWORD

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        auth_secret=TEST_SECRET,
        owner_password=TEST_PASSWORD,
        cookie_secure=True,
        demo_mode=True,
        seed_demo_data=True,
    )


@pytest.fixture
def client(settings: Settings):
    application = create_app(settings)
    with TestClient(application, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/session",
        json={"email": "alex@example.test", "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
