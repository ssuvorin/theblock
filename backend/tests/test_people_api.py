from collections.abc import Iterator
from contextlib import contextmanager

from app.models import Owner, Person
from fastapi.testclient import TestClient
from sqlalchemy import event


@contextmanager
def query_counter(client: TestClient) -> Iterator[list[int]]:
    engine = client.app.state.database.engine
    counter = [0]

    def on_execute(conn, cursor, statement, parameters, context, executemany) -> None:
        counter[0] += 1

    event.listen(engine, "before_cursor_execute", on_execute)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", on_execute)


def add_people(client: TestClient, count: int) -> None:
    with client.app.state.database.session_factory() as session:
        owner = session.query(Owner).one()
        for index in range(count):
            session.add(
                Person(
                    owner_id=owner.id,
                    display_name=f"Extra Person {index:03d}",
                    current_title="Padding contact",
                    data_origin="synthetic",
                )
            )
        session.commit()


def test_people_list_exposes_avatar_and_strength(client: TestClient, auth: dict[str, str]) -> None:
    response = client.get("/api/people", headers=auth)
    assert response.status_code == 200
    people = response.json()["people"]
    assert people
    for person in people:
        assert "photo_url" in person
        assert "strength_score" in person
        assert "sources" in person
        assert "location" not in person
    scores = [person["strength_score"] for person in people]
    assert any(isinstance(score, int | float) for score in scores)


def test_person_detail_keeps_identities_and_badges(
    client: TestClient, auth: dict[str, str]
) -> None:
    listing = client.get("/api/people", headers=auth)
    person_id = listing.json()["people"][0]["id"]
    response = client.get(f"/api/people/{person_id}", headers=auth)
    assert response.status_code == 200
    profile = response.json()["person"]
    assert "identities" in profile
    assert "source_badges" in profile


def test_people_list_query_count_is_constant(client: TestClient, auth: dict[str, str]) -> None:
    with query_counter(client) as counter:
        assert client.get("/api/people", headers=auth).status_code == 200
        baseline = counter[0]

    add_people(client, 15)

    with query_counter(client) as counter:
        grown = client.get("/api/people", headers=auth)
        assert grown.status_code == 200
        after = counter[0]

    assert len(grown.json()["people"]) > 15
    assert after == baseline
