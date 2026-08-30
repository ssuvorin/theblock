"""Deterministic normalization for source identities.

Normalization never discards the source spelling: callers persist ``raw_value`` beside
``normalized_value`` so merge decisions remain explainable and reversible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import quote, unquote, urlsplit


class IdentityNormalizationError(ValueError):
    """Raised when an identity cannot be normalized without guessing."""


class IdentityKind(StrEnum):
    EMAIL = "email"
    PHONE = "phone"
    LINKEDIN_URL = "linkedin_url"
    TELEGRAM_USERNAME = "telegram_username"
    WHATSAPP_JID = "whatsapp_jid"
    WHATSAPP_LID = "whatsapp_lid"


@dataclass(frozen=True, slots=True)
class NormalizedIdentity:
    kind: IdentityKind
    raw_value: str
    normalized_value: str
    source: str
    is_verified: bool = False
    is_primary: bool = False
    is_shared: bool = False


_ROLE_LOCAL_PARTS = frozenset(
    {
        "admin",
        "billing",
        "careers",
        "contact",
        "hello",
        "help",
        "hr",
        "info",
        "jobs",
        "marketing",
        "office",
        "sales",
        "security",
        "support",
        "team",
    }
)
_PHONE_EXTENSION = re.compile(r"(?:ext\.?|extension|x)\s*\d+\s*$", re.IGNORECASE)


def normalize_email(value: str) -> str:
    """Return a lowercase mailbox with an IDNA-normalized domain."""

    raw = value.strip()
    if raw.count("@") != 1:
        raise IdentityNormalizationError("email must contain one @")
    local, domain = raw.rsplit("@", 1)
    if not local or not domain or any(character.isspace() for character in raw):
        raise IdentityNormalizationError("email is incomplete")
    try:
        ascii_domain = domain.casefold().encode("idna").decode("ascii")
    except UnicodeError as error:
        raise IdentityNormalizationError("email domain is invalid") from error
    return f"{local.casefold()}@{ascii_domain}"


def is_role_email(value: str) -> bool:
    """Identify generic role mailboxes, which are unsafe auto-merge evidence."""

    normalized = normalize_email(value)
    local = normalized.split("@", 1)[0]
    root = re.split(r"[+._-]", local, maxsplit=1)[0]
    return root in _ROLE_LOCAL_PARTS


def normalize_phone(value: str, default_country_code: str | None = None) -> str:
    """Normalize an international phone to E.164 without a numbering dependency.

    Local numbers require an explicit ``default_country_code``. This deliberately
    avoids guessing a country from formatting or digit count.
    """

    without_extension = _PHONE_EXTENSION.sub("", value.strip())
    has_plus = without_extension.startswith("+")
    has_double_zero = without_extension.startswith("00")
    digits = "".join(character for character in without_extension if character.isdigit())
    if has_double_zero:
        digits = digits[2:]
    if not digits:
        raise IdentityNormalizationError("phone has no digits")
    if not has_plus and not has_double_zero:
        country_code = _country_code_digits(default_country_code)
        national = digits
        if national.startswith(country_code) and len(national) > 10:
            pass
        else:
            national = national.lstrip("0")
            digits = f"{country_code}{national}"
    if digits.startswith("0") or not 7 <= len(digits) <= 15:
        raise IdentityNormalizationError("phone is not a valid E.164 length")
    return f"+{digits}"


def _country_code_digits(default_country_code: str | None) -> str:
    if default_country_code is None:
        raise IdentityNormalizationError("local phone needs a default country code")
    digits = "".join(character for character in default_country_code if character.isdigit())
    if not 1 <= len(digits) <= 3 or digits.startswith("0"):
        raise IdentityNormalizationError("default country code is invalid")
    return digits


def canonicalize_linkedin_url(value: str) -> str:
    """Canonicalize a LinkedIn URL to HTTPS, stable host/path, and no tracking."""

    candidate = value.strip()
    if not candidate:
        raise IdentityNormalizationError("LinkedIn URL is empty")
    if "://" not in candidate:
        candidate = f"https://{candidate.lstrip('/')}"
    parsed = urlsplit(candidate)
    hostname = (parsed.hostname or "").casefold().rstrip(".")
    if hostname != "linkedin.com" and not hostname.endswith(".linkedin.com"):
        raise IdentityNormalizationError("URL is not a LinkedIn URL")
    path = re.sub(r"/+", "/", unquote(parsed.path)).rstrip("/")
    if not path:
        raise IdentityNormalizationError("LinkedIn URL has no profile path")
    canonical_path = quote(path.casefold(), safe="/@:+-._~")
    return f"https://www.linkedin.com{canonical_path}"


def normalize_telegram_username(value: str) -> str:
    username = value.strip().lstrip("@").casefold()
    if not re.fullmatch(r"[a-z0-9_]{5,32}", username):
        raise IdentityNormalizationError("Telegram username is invalid")
    return username


def normalize_whatsapp(value: str) -> tuple[IdentityKind, str]:
    """Normalize a WhatsApp phone JID or opaque LID while preserving its kind."""

    raw = value.strip().casefold()
    if not raw:
        raise IdentityNormalizationError("WhatsApp identity is empty")
    local, separator, server = raw.partition("@")
    if not separator:
        phone = normalize_phone(local)
        return IdentityKind.WHATSAPP_JID, f"{phone[1:]}@s.whatsapp.net"
    if server in {"lid", "lid.whatsapp.net"}:
        normalized_local = _normalize_whatsapp_local(local, allow_device=True)
        return IdentityKind.WHATSAPP_LID, f"{normalized_local}@lid"
    if server in {"c.us", "s.whatsapp.net"}:
        normalized_local = _normalize_whatsapp_local(local, allow_device=True)
        return IdentityKind.WHATSAPP_JID, f"{normalized_local}@s.whatsapp.net"
    raise IdentityNormalizationError("WhatsApp identity has an unknown server")


def _normalize_whatsapp_local(value: str, *, allow_device: bool) -> str:
    pattern = r"\d+(?::\d+)?" if allow_device else r"\d+"
    compact = value.removeprefix("+").replace(" ", "").replace("-", "")
    if not re.fullmatch(pattern, compact):
        raise IdentityNormalizationError("WhatsApp identity local part is invalid")
    return compact


def normalize_identity(
    kind: IdentityKind | str,
    raw_value: str,
    *,
    source: str,
    is_verified: bool = False,
    is_primary: bool = False,
    is_shared: bool = False,
    default_country_code: str | None = None,
) -> NormalizedIdentity:
    """Normalize one identity and retain all provenance needed by the matcher."""

    requested_kind = IdentityKind(kind)
    actual_kind = requested_kind
    if requested_kind is IdentityKind.EMAIL:
        normalized = normalize_email(raw_value)
    elif requested_kind is IdentityKind.PHONE:
        normalized = normalize_phone(raw_value, default_country_code)
    elif requested_kind is IdentityKind.LINKEDIN_URL:
        normalized = canonicalize_linkedin_url(raw_value)
    elif requested_kind is IdentityKind.TELEGRAM_USERNAME:
        normalized = normalize_telegram_username(raw_value)
    elif requested_kind in {IdentityKind.WHATSAPP_JID, IdentityKind.WHATSAPP_LID}:
        actual_kind, normalized = normalize_whatsapp(raw_value)
        if requested_kind is not actual_kind:
            raise IdentityNormalizationError("WhatsApp identity kind does not match value")
    else:  # pragma: no cover - Enum conversion makes this defensive.
        raise IdentityNormalizationError(f"unsupported identity kind: {kind}")
    return NormalizedIdentity(
        kind=actual_kind,
        raw_value=raw_value,
        normalized_value=normalized,
        source=source,
        is_verified=is_verified,
        is_primary=is_primary,
        is_shared=is_shared,
    )
