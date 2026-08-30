from fastapi.testclient import TestClient

QUERY = (
    "I'm looking for a Product Manager role at a crypto company in Dubai. "
    "Which companies are hiring now, and which warm paths should I follow?"
)


def test_query_is_opportunity_first_and_separates_evidence(
    client: TestClient,
    auth: dict[str, str],
) -> None:
    response = client.post("/api/query", json={"question": QUERY}, headers=auth)
    assert response.status_code == 200
    answer = response.json()["answer"]
    assert answer["search"]["provider"] == "synthetic_demo"
    assert "not a live vacancy check" in answer["search"]["disclosure"]
    assert answer["evidence_quality"] == "sufficient"
    assert len(answer["opportunities"]) == 4
    for opportunity in answer["opportunities"]:
        assert opportunity["public_citations"]
        assert "ranking_factors" in opportunity
        for path in opportunity["warm_paths"]:
            assert path["private_citations"]
            assert "public_citations" not in path
            assert path["path"][-1] == opportunity["organization"]["name"]


def test_verified_result_without_path_is_explicit_and_no_path_is_fabricated(
    client: TestClient,
    auth: dict[str, str],
) -> None:
    answer = client.post("/api/query", json={"question": QUERY}, headers=auth).json()["answer"]
    okx = next(item for item in answer["opportunities"] if item["organization"]["name"] == "OKX")
    assert okx["verification_status"] == "verified_open_role"
    assert okx["warm_paths"] == []
    assert okx["warm_path_status"] == "no_warm_path_found"
    known_people = {"Marta", "John", "Sergey Lapin"}
    returned_people = {
        path["display_name"] for item in answer["opportunities"] for path in item["warm_paths"]
    }
    assert returned_people <= known_people


def test_unsupported_goal_returns_honest_no_evidence(
    client: TestClient,
    auth: dict[str, str],
) -> None:
    response = client.post(
        "/api/query",
        json={"question": "Find me a marine biologist role in Oslo"},
        headers=auth,
    )
    answer = response.json()["answer"]
    assert answer["opportunities"] == []
    assert answer["network_candidates"] == []
    assert answer["evidence_quality"] == "insufficient"
