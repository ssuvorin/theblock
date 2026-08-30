from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.connectors.linkedin_export.importer import load_linkedin_export
from app.connectors.linkedin_export.normalize import deterministic_external_id
from scripts.import_linkedin import safe_summary

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_export"


def test_synthetic_archive_normalizes_without_warnings() -> None:
    plan = load_linkedin_export(FIXTURE, data_origin="synthetic", demo_mode=True)
    assert plan.interaction_count == 476
    assert plan.conversation_count == 160
    assert len(plan.people) == 13
    assert plan.unique_identity_count >= 30
    assert {identity.kind.value for identity in plan.owner_identities} == {
        "email",
        "linkedin_url",
        "phone",
    }
    assert plan.warnings == ()
    assert plan.empty_message_count > 0
    assert all(person.data_origin == "synthetic" for person in plan.people)
    assert all(message.data_origin == "synthetic" for message in plan.messages)
    assert all(invitation.data_origin == "synthetic" for invitation in plan.invitations)


def test_owner_url_is_resolved_without_a_profile_url_column() -> None:
    """The archive has no Profile URL column, so the owner must be inferred from evidence."""

    plan = load_linkedin_export(FIXTURE, data_origin="synthetic", demo_mode=True)
    assert plan.owner_profile is not None
    assert plan.owner_profile.profile_url == "https://www.linkedin.com/in/maya-haddad-product"
    assert plan.owner_resolution_method == "invitations"
    assert plan.owner_resolution_confidence == "high"


def test_unsent_drafts_are_not_imported_as_messages() -> None:
    plan = load_linkedin_export(FIXTURE, data_origin="synthetic", demo_mode=True)
    assert plan.drafts_skipped > 0
    assert plan.interaction_count + plan.drafts_skipped == 480


def test_connections_add_titles_but_never_create_people() -> None:
    """A connection list proves no interaction, so it must not inflate the graph."""

    plan = load_linkedin_export(FIXTURE, data_origin="synthetic", demo_mode=True)
    assert plan.connections_seen > len(plan.people)
    assert plan.connections_matched > 0
    titled = [person for person in plan.people if person.current_title]
    assert titled
    assert all(not person.is_owner for person in titled)
    assert {person.current_company for person in titled} >= {"Rain", "Palm Logistics"}


def test_owner_is_never_given_a_connection_title() -> None:
    plan = load_linkedin_export(FIXTURE, data_origin="synthetic", demo_mode=True)
    owner = next(person for person in plan.people if person.is_owner)
    assert owner.current_title is None
    assert owner.current_company is None


def test_invitations_alone_create_no_people(tmp_path: Path) -> None:
    archive = tmp_path / "invitation-only"
    archive.mkdir()
    shutil.copyfile(FIXTURE / "Invitations.csv", archive / "Invitations.csv")
    plan = load_linkedin_export(archive, data_origin="synthetic", demo_mode=True)
    assert plan.invitations
    assert plan.messages == ()
    assert plan.people == ()
    assert plan.identity_hints


def test_message_external_ids_are_stable_and_content_derived() -> None:
    arguments = (
        "conversation-1",
        "2026-08-30 07:37:53 UTC",
        "https://linkedin.com/in/example/?trk=tracking",
        "A message with\nembedded detail.",
    )
    first = deterministic_external_id(*arguments)
    second = deterministic_external_id(*arguments)
    edited = deterministic_external_id(*arguments[:-1], "Edited content")
    assert first == second
    assert first != edited
    assert len(first) == 64


def test_reimport_has_identical_unique_ids() -> None:
    first = load_linkedin_export(FIXTURE, data_origin="synthetic", demo_mode=False)
    second = load_linkedin_export(FIXTURE, data_origin="synthetic", demo_mode=False)
    first_ids = tuple(message.external_id for message in first.messages)
    second_ids = tuple(message.external_id for message in second.messages)
    assert first_ids == second_ids
    assert len(first_ids) == len(set(first_ids))


def test_direction_uses_owner_profile_url() -> None:
    plan = load_linkedin_export(FIXTURE, data_origin="synthetic", demo_mode=False)
    assert {message.direction for message in plan.messages} == {"incoming", "outgoing"}


def test_dry_run_summary_contains_aggregates_only() -> None:
    plan = load_linkedin_export(FIXTURE, data_origin="synthetic", demo_mode=False)
    rendered = json.dumps(safe_summary(plan), sort_keys=True).casefold()
    assert '"messages": 476' in rendered
    assert '"invitations_seen": 32' in rendered
    for private_value in (
        "maya haddad",
        "marta oliveira",
        "daniel ruiz",
        "example.test",
        "linkedin.com/in/",
        "whatsapp",
        "palm logistics",
    ):
        assert private_value not in rendered
