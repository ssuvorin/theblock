from fastapi.testclient import TestClient

from test_query_grounding import QUERY


def _path_target(client: TestClient, auth: dict[str, str]) -> tuple[str, str]:
    answer = client.post("/api/query", json={"question": QUERY}, headers=auth).json()["answer"]
    opportunity = next(item for item in answer["opportunities"] if item["warm_paths"])
    return opportunity["opportunity_id"], opportunity["warm_paths"][0]["person_id"]


def test_draft_is_cited_and_has_no_send_capability(
    client: TestClient,
    auth: dict[str, str],
) -> None:
    opportunity_id, person_id = _path_target(client, auth)
    response = client.post(
        f"/api/people/{person_id}/draft",
        json={
            "goal": "Find a Product Manager role at a crypto company in Dubai",
            "opportunity_id": opportunity_id,
            "action": "reconnect",
            "channel": "generic",
        },
        headers=auth,
    )
    assert response.status_code == 200
    draft = response.json()["draft"]
    assert draft["send_supported"] is False
    assert draft["apply_supported"] is False
    assert draft["outbound_calls"] == 0
    assert draft["allowed_actions"] == [
        "edit",
        "copy",
        "open_external_client",
        "create_reminder",
        "save_opportunity",
    ]
    assert draft["private_citations"] and draft["public_citations"]


def test_send_and_apply_actions_are_rejected(
    client: TestClient,
    auth: dict[str, str],
) -> None:
    opportunity_id, person_id = _path_target(client, auth)
    for action in ("send", "apply", "deliver"):
        response = client.post(
            f"/api/people/{person_id}/draft",
            json={
                "goal": "Dubai crypto product role",
                "opportunity_id": opportunity_id,
                "action": action,
            },
            headers=auth,
        )
        assert response.status_code == 400
