from app.models import Owner, Person
from fastapi.testclient import TestClient


def test_demo_mode_hides_real_import_people(client: TestClient, auth: dict[str, str]) -> None:
    with client.app.state.database.session_factory() as session:
        owner = session.query(Owner).one()
        session.add(
            Person(
                owner_id=owner.id,
                display_name="Private Real Contact",
                current_title="Must stay hidden",
                data_origin="real_import",
            )
        )
        session.commit()
    response = client.get("/api/people", headers=auth)
    names = {person["display_name"] for person in response.json()["people"]}
    assert "Private Real Contact" not in names
