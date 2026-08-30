"""Connector credentials must be unreadable at rest and rotations must actually persist."""

from __future__ import annotations

import base64
import os

import pytest
from app.config import Settings
from app.models import Base, Owner, SourceSecret
from app.services.secret_vault import SecretVault, SecretVaultUnavailable, VaultCredentials
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

TOKENS = {"access_token": "ya29.super-secret", "refresh_token": "1//rotate-me"}


def _key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def _settings(key: str | None) -> Settings:
    return Settings(
        database_url="sqlite://",
        auth_secret="s" * 40,
        owner_password="p" * 12,
        encryption_key=key,
    )


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as active:
        active.add(Owner(id="owner-1", display_name="Owner", email="owner@example.test"))
        active.flush()
        yield active


def test_stored_tokens_are_not_readable_in_the_database(session: Session) -> None:
    vault = SecretVault(session, "owner-1", _settings(_key()))
    ref = vault.store("oauth_tokens", TOKENS)

    stored = session.scalar(select(SourceSecret).where(SourceSecret.id == ref))
    assert stored is not None
    assert "ya29" not in stored.ciphertext
    assert "rotate-me" not in stored.ciphertext
    assert vault.load(ref) == TOKENS


def test_replace_persists_a_rotated_refresh_token(session: Session) -> None:
    vault = SecretVault(session, "owner-1", _settings(_key()))
    ref = vault.store("oauth_tokens", TOKENS)

    credentials = VaultCredentials(vault, ref)
    credentials.update({"refresh_token": "1//rotated"})

    assert VaultCredentials(vault, ref).get()["refresh_token"] == "1//rotated"
    assert vault.load(ref)["access_token"] == TOKENS["access_token"]


def test_a_changed_encryption_key_is_reported_not_silently_ignored(session: Session) -> None:
    ref = SecretVault(session, "owner-1", _settings(_key())).store("oauth_tokens", TOKENS)

    with pytest.raises(SecretVaultUnavailable, match="different ENCRYPTION_KEY"):
        SecretVault(session, "owner-1", _settings(_key())).load(ref)


def test_an_unset_key_refuses_to_store_credentials(session: Session) -> None:
    vault = SecretVault(session, "owner-1", _settings(None))

    assert vault.configured is False
    with pytest.raises(SecretVaultUnavailable, match="ENCRYPTION_KEY is not set"):
        vault.store("oauth_tokens", TOKENS)


def test_a_malformed_key_is_rejected_with_instructions(session: Session) -> None:
    with pytest.raises(SecretVaultUnavailable, match="base64-encoded 32-byte key"):
        SecretVault(session, "owner-1", _settings("too-short")).store("oauth_tokens", TOKENS)


def test_another_owners_secret_is_not_loadable(session: Session) -> None:
    key = _key()
    ref = SecretVault(session, "owner-1", _settings(key)).store("oauth_tokens", TOKENS)
    session.add(Owner(id="owner-2", display_name="Other", email="other@example.test"))
    session.flush()

    with pytest.raises(SecretVaultUnavailable, match="unknown for this owner"):
        SecretVault(session, "owner-2", _settings(key)).load(ref)
