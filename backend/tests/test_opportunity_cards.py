from fastapi.testclient import TestClient

from test_query_grounding import QUERY


def test_opportunity_list_carries_warm_paths_with_private_citations(
    client: TestClient,
    auth: dict[str, str],
) -> None:
    response = client.get("/api/opportunities?limit=50&page=1", headers=auth)
    assert response.status_code == 200
    opportunities = response.json()["opportunities"]
    assert opportunities
    with_paths = [item for item in opportunities if item["warm_paths"]]
    assert with_paths
    for item in with_paths:
        for path in item["warm_paths"]:
            assert path["private_citations"]
            assert path["ranking_factors"]
            assert "public_citations" not in path


def test_every_listed_opportunity_states_its_warm_path_status(
    client: TestClient,
    auth: dict[str, str],
) -> None:
    opportunities = client.get("/api/opportunities?limit=50", headers=auth).json()["opportunities"]
    assert opportunities
    for item in opportunities:
        assert item["warm_path_status"] in {"found", "no_warm_path_found"}
        assert item["warm_path_count"] == len(item["warm_paths"])


def test_listed_opportunity_without_path_is_explicit(
    client: TestClient,
    auth: dict[str, str],
) -> None:
    opportunities = client.get("/api/opportunities?limit=50", headers=auth).json()["opportunities"]
    okx = next(item for item in opportunities if item["organization"]["name"] == "OKX")
    assert okx["warm_paths"] == []
    assert okx["warm_path_status"] == "no_warm_path_found"
    detail = client.get(f"/api/opportunities/{okx['id']}", headers=auth).json()["opportunity"]
    assert detail["warm_path_status"] == "no_warm_path_found"
    assert detail["warm_path_count"] == 0


def test_opportunity_detail_matches_list_card_shape(
    client: TestClient,
    auth: dict[str, str],
) -> None:
    opportunities = client.get("/api/opportunities?limit=50", headers=auth).json()["opportunities"]
    listed = next(item for item in opportunities if item["warm_paths"])
    detail = client.get(f"/api/opportunities/{listed['id']}", headers=auth).json()["opportunity"]
    assert detail == listed


def test_query_reports_real_distinct_public_sources_checked(
    client: TestClient,
    auth: dict[str, str],
) -> None:
    answer = client.post("/api/query", json={"question": QUERY}, headers=auth).json()["answer"]
    expected = len(
        {
            citation["url"]
            for item in answer["opportunities"]
            for citation in item["public_citations"]
        }
    )
    assert answer["search"]["sources_checked"] > 0
    assert answer["search"]["sources_checked"] == expected


def test_query_without_evidence_reports_zero_sources_checked(
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
    assert answer["search"]["sources_checked"] == 0
