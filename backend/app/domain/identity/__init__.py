"""Identity normalization and deterministic matching primitives."""

from .matcher import DeterministicIdentityMatcher, MatchDecision, MatchMethod, can_auto_link
from .normalize import (
    IdentityKind,
    IdentityNormalizationError,
    NormalizedIdentity,
    canonicalize_linkedin_url,
    is_role_email,
    normalize_email,
    normalize_identity,
    normalize_phone,
    normalize_whatsapp,
)

__all__ = [
    "DeterministicIdentityMatcher",
    "IdentityKind",
    "IdentityNormalizationError",
    "MatchDecision",
    "MatchMethod",
    "NormalizedIdentity",
    "can_auto_link",
    "canonicalize_linkedin_url",
    "is_role_email",
    "normalize_email",
    "normalize_identity",
    "normalize_phone",
    "normalize_whatsapp",
]
