from __future__ import annotations

import pytest
from app.domain.identity.matcher import DeterministicIdentityMatcher, MatchMethod
from app.domain.identity.normalize import (
    IdentityKind,
    IdentityNormalizationError,
    canonicalize_linkedin_url,
    normalize_identity,
    normalize_phone,
    normalize_whatsapp,
)


def test_email_is_lowercase_with_raw_value_and_source_retained() -> None:
    identity = normalize_identity(
        "email",
        "  Alex.Ivanov@Example.COM ",
        source="gmail",
        is_verified=True,
    )
    assert identity.normalized_value == "alex.ivanov@example.com"
    assert identity.raw_value == "  Alex.Ivanov@Example.COM "
    assert identity.source == "gmail"


def test_phone_normalizes_to_e164_without_dependency() -> None:
    assert normalize_phone("+971 (50) 555-0101") == "+971505550101"
    assert normalize_phone("0044 20 7946 0958") == "+442079460958"
    assert normalize_phone("(415) 555-0101", default_country_code="1") == "+14155550101"
    with pytest.raises(IdentityNormalizationError):
        normalize_phone("020 7946 0958")


def test_linkedin_url_is_stable_and_tracking_free() -> None:
    variants = (
        "linkedin.com/in/Alex-Ivanov/",
        "https://www.linkedin.com/in/alex-ivanov?trk=public_profile",
        "http://ae.linkedin.com/in/alex-ivanov/#about",
    )
    assert {canonicalize_linkedin_url(value) for value in variants} == {
        "https://www.linkedin.com/in/alex-ivanov"
    }


def test_whatsapp_jid_and_lid_keep_raw_value_and_kind() -> None:
    jid_raw = "+14155550101"
    jid = normalize_identity("whatsapp_jid", jid_raw, source="whatsapp")
    lid_raw = "8833221100@lid"
    lid = normalize_identity("whatsapp_lid", lid_raw, source="whatsapp")
    assert jid.kind is IdentityKind.WHATSAPP_JID
    assert jid.normalized_value == "14155550101@s.whatsapp.net"
    assert jid.raw_value == jid_raw
    assert lid.kind is IdentityKind.WHATSAPP_LID
    assert lid.normalized_value == lid_raw
    assert lid.raw_value == lid_raw
    assert normalize_whatsapp("14155550101@c.us")[1] == "14155550101@s.whatsapp.net"


def test_matcher_only_auto_links_approved_exact_evidence() -> None:
    matcher = DeterministicIdentityMatcher()
    email_a = normalize_identity("email", "person@example.com", source="gmail", is_verified=True)
    email_b = normalize_identity("email", "PERSON@example.com", source="linkedin", is_verified=True)
    email_match = matcher.match(email_a, email_b)
    assert email_match.auto_link
    assert email_match.method is MatchMethod.VERIFIED_EMAIL

    profile_a = normalize_identity(
        "linkedin_url",
        "linkedin.com/in/a-person",
        source="linkedin_export",
    )
    profile_b = normalize_identity(
        "linkedin_url",
        "https://www.linkedin.com/in/A-PERSON/?trk=x",
        source="manual",
    )
    assert matcher.match(profile_a, profile_b).method is MatchMethod.LINKEDIN_URL


def test_role_addresses_shared_phones_and_messaging_ids_never_auto_merge() -> None:
    matcher = DeterministicIdentityMatcher()
    role_a = normalize_identity("email", "sales@example.com", source="gmail", is_verified=True)
    role_b = normalize_identity("email", "SALES@example.com", source="manual", is_verified=True)
    assert not matcher.match(role_a, role_b).auto_link

    phone_a = normalize_identity("phone", "+14155550101", source="gmail", is_shared=True)
    phone_b = normalize_identity("phone", "+1 415 555 0101", source="whatsapp")
    assert not matcher.match(phone_a, phone_b).auto_link

    jid_a = normalize_identity("whatsapp_jid", "+14155550101", source="whatsapp")
    jid_b = normalize_identity("whatsapp_jid", "14155550101@c.us", source="backup")
    assert not matcher.match(jid_a, jid_b).auto_link
