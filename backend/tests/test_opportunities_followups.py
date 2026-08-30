from fastapi.testclient import TestClient


def test_opportunity_save_and_filter(client: TestClient, auth: dict[str, str]) -> None:
    opportunity = client.get("/api/opportunities", headers=auth).json()["opportunities"][0]
    patched = client.patch(
        f"/api/opportunities/{opportunity['id']}",
        json={"saved": True},
        headers=auth,
    )
    assert patched.status_code == 200
    assert patched.json()["opportunity"]["saved"] is True
    saved = client.get("/api/opportunities?saved=true", headers=auth).json()
    assert {item["id"] for item in saved["opportunities"]} == {opportunity["id"]}


def test_follow_up_crud(client: TestClient, auth: dict[str, str]) -> None:
    person = next(
        item
        for item in client.get("/api/people", headers=auth).json()["people"]
        if item["display_name"] == "Marta"
    )
    created = client.post(
        "/api/followups",
        json={"person_id": person["id"], "reason": "Reconnect", "priority": 3},
        headers=auth,
    )
    assert created.status_code == 201
    follow_up_id = created.json()["follow_up"]["id"]
    updated = client.patch(
        f"/api/followups/{follow_up_id}",
        json={"status": "done"},
        headers=auth,
    )
    assert updated.json()["follow_up"]["status"] == "done"
    deleted = client.delete(f"/api/followups/{follow_up_id}", headers=auth)
    assert deleted.json() == {"id": follow_up_id, "deleted": True}
