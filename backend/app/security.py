import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status

from app.config import Settings


class SessionTokenService:
    def __init__(self, settings: Settings) -> None:
        self._secret = settings.auth_secret.get_secret_value()
        self._lifetime = timedelta(minutes=settings.session_minutes)

    def issue(self, owner_id: str) -> tuple[str, int]:
        now = datetime.now(UTC)
        expires = now + self._lifetime
        payload = {"sub": owner_id, "iat": now, "exp": expires, "aud": "second-brain-owner"}
        token = jwt.encode(payload, self._secret, algorithm="HS256")
        return token, int(self._lifetime.total_seconds())

    def owner_id(self, token: str) -> str:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience="second-brain-owner",
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired owner session",
            ) from exc
        return str(payload["sub"])


class OwnerCredentialService:
    def __init__(self, settings: Settings) -> None:
        self._email = settings.owner_email.casefold()
        self._password = settings.owner_password.get_secret_value()

    def valid(self, email: str, password: str) -> bool:
        email_ok = secrets.compare_digest(email.casefold(), self._email)
        password_ok = secrets.compare_digest(password, self._password)
        return email_ok and password_ok
