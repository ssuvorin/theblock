from __future__ import annotations

from app.connectors.linkedin_export.owner import (
    dominant_sender_url,
    invitation_owner_url,
    named_sender_url,
    owner_display_name,
    resolve_owner_url,
)

OWNER_URL = "https://www.linkedin.com/in/maya-haddad"
CONTACT_URL = "https://www.linkedin.com/in/nora-moretti"
PROFILE = {"First Name": "Maya", "Last Name": "Haddad", "Headline": "Product Manager"}


def _message(sender: str, url: str, recipients: str = "") -> dict[str, str]:
    return {
        "FROM": sender,
        "SENDER PROFILE URL": url,
        "RECIPIENT PROFILE URLS": recipients,
        "CONTENT": "hello",
    }


def _invitation(direction: str, inviter: str) -> dict[str, str]:
    return {"Direction": direction, "inviterProfileUrl": inviter, "inviteeProfileUrl": CONTACT_URL}


def test_owner_display_name_joins_profile_columns() -> None:
    assert owner_display_name(PROFILE) == "Maya Haddad"
    assert owner_display_name(None) == ""
    assert owner_display_name({"First Name": "Maya", "Last Name": ""}) == "Maya"


def test_real_export_profile_without_url_still_resolves_owner() -> None:
    messages = [_message("Maya Haddad", OWNER_URL)] * 3 + [_message("Nora", CONTACT_URL)]
    invitations = [_invitation("OUTGOING", OWNER_URL)] * 5 + [_invitation("INCOMING", CONTACT_URL)]

    resolution = resolve_owner_url(PROFILE, messages, invitations)

    assert resolution.profile_url == OWNER_URL
    assert resolution.method == "invitations"
    assert resolution.confidence == "high"
    assert "profile_name" in resolution.corroborated_by


def test_declared_profile_url_takes_priority() -> None:
    profile = {**PROFILE, "Profile URL": OWNER_URL}

    resolution = resolve_owner_url(profile, [], [])

    assert resolution.profile_url == OWNER_URL
    assert resolution.method == "profile_url"
    assert resolution.confidence == "medium"


def test_invitations_identify_owner_as_single_outgoing_inviter() -> None:
    invitations = [_invitation("OUTGOING", OWNER_URL) for _ in range(4)]
    assert invitation_owner_url(invitations) == OWNER_URL

    ambiguous = [*invitations, _invitation("OUTGOING", CONTACT_URL)]
    assert invitation_owner_url(ambiguous) is None
    assert invitation_owner_url([_invitation("INCOMING", CONTACT_URL)]) is None


def test_named_sender_requires_an_unambiguous_match() -> None:
    messages = [_message("Maya Haddad", OWNER_URL), _message("Nora", CONTACT_URL)]
    assert named_sender_url(messages, "Maya Haddad") == OWNER_URL
    assert named_sender_url(messages, "  maya   haddad ") == OWNER_URL
    assert named_sender_url(messages, "Unknown Person") is None
    assert named_sender_url(messages, "") is None

    conflicting = [*messages, _message("Maya Haddad", "https://www.linkedin.com/in/other")]
    assert named_sender_url(conflicting, "Maya Haddad") is None


def test_dominant_sender_needs_a_meaningful_share() -> None:
    lopsided = [_message("Maya", OWNER_URL)] * 6 + [_message("Nora", CONTACT_URL)]
    assert dominant_sender_url(lopsided) == OWNER_URL
    assert dominant_sender_url([]) is None

    flat = [_message("A", f"https://www.linkedin.com/in/p{index}") for index in range(10)]
    assert dominant_sender_url(flat) is None


def test_dominant_sender_is_only_a_low_confidence_fallback() -> None:
    messages = [_message("Someone Else", OWNER_URL)] * 9 + [_message("Nora", CONTACT_URL)]

    resolution = resolve_owner_url({"First Name": "", "Last Name": ""}, messages, [])

    assert resolution.profile_url == OWNER_URL
    assert resolution.method == "dominant_sender"
    assert resolution.confidence == "low"


def test_unresolved_owner_is_reported_rather_than_guessed() -> None:
    resolution = resolve_owner_url(PROFILE, [], [])

    assert resolution.profile_url is None
    assert resolution.method == "unresolved"
    assert resolution.resolved is False
