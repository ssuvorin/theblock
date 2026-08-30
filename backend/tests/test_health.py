from fastapi.testclient import TestClient

from conftest import TEST_PASSWORD, TEST_SECRET


def test_health_and_dependency_preflight_do_not_leak_secrets(client: TestClient) -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

    response = client.get("/api/health/deps")
    assert response.status_code == 200
    body = response.json()
    assert body["postgresql"] == "healthy"
    assert body["context_dev"]["provider_mode"] == "synthetic_demo"
    rendered = response.text
    assert TEST_SECRET not in rendered
    assert TEST_PASSWORD not in rendered
