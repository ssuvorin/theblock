"""The import endpoint must write the graph, not just count rows it declines to store.

Before this, POST /api/imports/linkedin validated an archive and returned aggregates while
persisting nothing, so every screen rendered demo-seed fixtures regardless of what was
uploaded. These tests pin the persistence contract end to end over HTTP.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from app.models import InteractionEvent, InteractionParticipant, Person, Relationship
from fastapi.testclient import TestClient
from sqlalchemy import func, select

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_export"
ENDPOINT = "/api/imports/linkedin"


def _archive_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(FIXTURE.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(FIXTURE).as_posix())
    return buffer.getvalue()


def _upload(client: TestClient, auth: dict[str, str], **params: object) -> dict:
    response = client.post(
        ENDPOINT,
        headers=auth,
        params=params,
        files={"archive": ("synthetic-demo-export.zip", _archive_bytes(), "application/zip")},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _count(client: TestClient, model: type) -> int:
    with client.app.state.database.session_factory() as session:
        return session.scalar(select(func.count()).select_from(model))


def test_import_persists_people_interactions_and_relationships(
    client: TestClient,
    auth: dict[str, str],
) -> None:
    people_before = _count(client, Person)
    body = _upload(client, auth)

    assert body["status"] == "imported"
    assert body["persistence"] == "postgresql"
    written = body["written"]
    assert written["people_created"] > 0
    assert written["interactions_created"] == body["messages"]
    assert written["relationships_created"] > 0
    assert written["data_origin"] == "synthetic"
    assert _count(client, Person) == people_before + written["people_created"]
    assert _count(client, InteractionEvent) >= written["interactions_created"]
    assert _count(client, InteractionParticipant) > 0
    assert _count(client, Relationship) >= written["relationships_created"]


def test_dry_run_writes_nothing(client: TestClient, auth: dict[str, str]) -> None:
    before = (_count(client, Person), _count(client, InteractionEvent))
    body = _upload(client, auth, dry_run=True)

    assert body["status"] == "validated"
    assert body["persistence"] == "dry_run"
    assert "written" not in body
    assert (_count(client, Person), _count(client, InteractionEvent)) == before


def test_reimport_creates_no_duplicates(client: TestClient, auth: dict[str, str]) -> None:
    first = _upload(client, auth)["written"]
    people_after_first = _count(client, Person)
    second = _upload(client, auth)["written"]

    assert second["people_created"] == 0
    assert second["interactions_created"] == 0
    assert second["people_matched"] == first["people_created"]
    assert second["interactions_existing"] == first["interactions_created"]
    assert _count(client, Person) == people_after_first


def test_import_reports_owner_resolution_and_skipped_drafts(
    client: TestClient,
    auth: dict[str, str],
) -> None:
    body = _upload(client, auth)

    assert body["owner_resolution"]["confidence"] in {"high", "medium"}
    assert body["owner_resolution"]["method"] != "unresolved"
    assert body["drafts_skipped"] > 0
    assert body["warnings"] == []


def test_demo_mode_rejects_an_archive_not_marked_synthetic(
    client: TestClient,
    auth: dict[str, str],
) -> None:
    response = client.post(
        ENDPOINT,
        headers=auth,
        files={"archive": ("my-real-export.zip", _archive_bytes(), "application/zip")},
    )
    assert response.status_code == 403


def test_a_non_zip_upload_is_rejected(client: TestClient, auth: dict[str, str]) -> None:
    response = client.post(
        ENDPOINT,
        headers=auth,
        files={"archive": ("synthetic-demo.zip", b"not a zip at all", "application/zip")},
    )
    assert response.status_code == 400


def test_import_requires_authentication(client: TestClient) -> None:
    response = client.post(
        ENDPOINT,
        files={"archive": ("synthetic-demo.zip", _archive_bytes(), "application/zip")},
    )
    assert response.status_code == 401
