"""Encrypted storage for connector credentials, addressed by an opaque reference.

Access tokens, refresh tokens and PKCE verifiers never appear in a connection row, an API
response, or a log line. Everything the connectors need is written here as ciphertext and
handed back only to the code that is about to make a provider call, so a leaked database
dump or a serialised ``SourceConnection`` cannot be replayed against Google or Collabute.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import SourceSecret, utcnow

KEY_BYTES = 32


class SecretVaultUnavailable(RuntimeError):
    """Raised when credentials cannot be encrypted or decrypted with the current key.

    Callers must surface this as a configuration problem rather than degrade quietly: a
    connector that cannot protect a refresh token has no business holding one.
    """


def _fernet_key(raw: str) -> bytes:
    """Accept a urlsafe or standard base64 32-byte key and return a Fernet key."""

    candidate = raw.strip()
    for decoder in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            material = decoder(_padded(candidate))
        except (binascii.Error, ValueError):
            continue
        if len(material) == KEY_BYTES:
            return base64.urlsafe_b64encode(material)
    raise SecretVaultUnavailable(
        "ENCRYPTION_KEY must be a base64-encoded 32-byte key; "
        "generate one with `python -c "
        '"import os,base64;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`'
    )


def _padded(value: str) -> str:
    return value + "=" * (-len(value) % 4)


class SecretVault:
    """Read and write one owner's connector credentials as encrypted rows."""

    def __init__(self, session: Session, owner_id: str, settings: Settings) -> None:
        self._session = session
        self._owner_id = owner_id
        self._raw_key = settings.encryption_key

    @property
    def configured(self) -> bool:
        return bool(self._raw_key and self._raw_key.get_secret_value().strip())

    def store(self, purpose: str, payload: dict) -> str:
        """Encrypt ``payload`` as a new secret and return the reference to keep."""

        secret = SourceSecret(
            owner_id=self._owner_id,
            purpose=purpose,
            ciphertext=self._encrypt(payload),
            key_fingerprint=self._fingerprint(),
        )
        self._session.add(secret)
        self._session.flush()
        return secret.id

    def replace(self, ref: str, payload: dict) -> None:
        """Rewrite an existing secret in place, which is how token rotation is persisted."""

        secret = self._row(ref)
        secret.ciphertext = self._encrypt(payload)
        secret.key_fingerprint = self._fingerprint()
        secret.updated_at = utcnow()
        self._session.flush()

    def load(self, ref: str) -> dict:
        secret = self._row(ref)
        if secret.key_fingerprint != self._fingerprint():
            raise SecretVaultUnavailable(
                "stored credentials were encrypted with a different ENCRYPTION_KEY; "
                "reconnect the source to re-authorize it"
            )
        try:
            decrypted = self._cipher().decrypt(secret.ciphertext.encode())
        except InvalidToken as error:
            raise SecretVaultUnavailable("stored credentials could not be decrypted") from error
        return json.loads(decrypted)

    def delete(self, ref: str | None) -> None:
        """Forget a secret. Missing references are already the desired end state."""

        if ref is None:
            return
        secret = self._session.get(SourceSecret, ref)
        if secret is not None and secret.owner_id == self._owner_id:
            self._session.delete(secret)
            self._session.flush()

    def purge(self) -> int:
        """Drop every secret for this owner, used by disconnect-and-delete."""

        rows = list(
            self._session.scalars(
                select(SourceSecret).where(SourceSecret.owner_id == self._owner_id)
            )
        )
        for row in rows:
            self._session.delete(row)
        self._session.flush()
        return len(rows)

    def _row(self, ref: str) -> SourceSecret:
        secret = self._session.get(SourceSecret, ref)
        if secret is None or secret.owner_id != self._owner_id:
            raise SecretVaultUnavailable("credential reference is unknown for this owner")
        return secret

    def _encrypt(self, payload: dict) -> str:
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        return self._cipher().encrypt(encoded).decode()

    def _cipher(self) -> Fernet:
        return Fernet(_fernet_key(self._key()))

    def _fingerprint(self) -> str:
        return hashlib.sha256(_fernet_key(self._key())).hexdigest()[:32]

    def _key(self) -> str:
        if not self.configured:
            raise SecretVaultUnavailable(
                "ENCRYPTION_KEY is not set, so connector credentials cannot be stored"
            )
        assert self._raw_key is not None
        return self._raw_key.get_secret_value()


class VaultCredentials:
    """A live view of one connection's credentials that persists every rotation.

    Connectors are handed this rather than a plain dict so a refreshed access token or a
    rotated refresh token is written back the moment the provider issues it, instead of
    being lost when the sync run ends or fails partway through.
    """

    def __init__(self, vault: SecretVault, ref: str) -> None:
        self._vault = vault
        self._ref = ref
        self._cached: dict | None = None

    def get(self) -> dict:
        if self._cached is None:
            self._cached = self._vault.load(self._ref)
        return dict(self._cached)

    def update(self, credentials: dict) -> None:
        merged = {**self.get(), **credentials}
        self._vault.replace(self._ref, merged)
        self._cached = merged
