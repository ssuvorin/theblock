"""Precision-first deterministic identity matching.

Only evidence explicitly allowed by FR-6.2 can auto-link. Similar names, employer
names, generic inboxes, shared phones, and messaging identifiers are intentionally
left for owner review.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from .normalize import IdentityKind, NormalizedIdentity, is_role_email


class MatchMethod(StrEnum):
    VERIFIED_EMAIL = "verified_email"
    PERSONAL_PHONE = "personal_phone"
    LINKEDIN_URL = "linkedin_url"


@dataclass(frozen=True, slots=True)
class MatchDecision:
    auto_link: bool
    method: MatchMethod | None
    reason: str


@dataclass(frozen=True, slots=True)
class IdentityMatch:
    left: NormalizedIdentity
    right: NormalizedIdentity
    decision: MatchDecision


class DeterministicIdentityMatcher:
    """Apply the small, auditable auto-link rule set."""

    def match(
        self,
        left: NormalizedIdentity,
        right: NormalizedIdentity,
    ) -> MatchDecision:
        if left.kind is not right.kind:
            return _no_match("identity kinds differ")
        if left.normalized_value != right.normalized_value:
            return _no_match("normalized values differ")
        if left.kind is IdentityKind.EMAIL:
            return self._match_email(left, right)
        if left.kind is IdentityKind.PHONE:
            return self._match_phone(left, right)
        if left.kind is IdentityKind.LINKEDIN_URL:
            return MatchDecision(True, MatchMethod.LINKEDIN_URL, "exact stable profile URL")
        return _no_match("identity kind is not approved for automatic linking")

    def _match_email(
        self,
        left: NormalizedIdentity,
        right: NormalizedIdentity,
    ) -> MatchDecision:
        if is_role_email(left.normalized_value):
            return _no_match("role email addresses never auto-link")
        if not left.is_verified or not right.is_verified:
            return _no_match("both email identities must be verified")
        return MatchDecision(True, MatchMethod.VERIFIED_EMAIL, "exact verified email")

    def _match_phone(
        self,
        left: NormalizedIdentity,
        right: NormalizedIdentity,
    ) -> MatchDecision:
        if left.is_shared or right.is_shared:
            return _no_match("shared phone numbers never auto-link")
        return MatchDecision(True, MatchMethod.PERSONAL_PHONE, "exact normalized personal phone")

    def matching_pairs(
        self,
        left_identities: Iterable[NormalizedIdentity],
        right_identities: Iterable[NormalizedIdentity],
    ) -> tuple[IdentityMatch, ...]:
        matches: list[IdentityMatch] = []
        right_values = tuple(right_identities)
        for left in left_identities:
            for right in right_values:
                decision = self.match(left, right)
                if decision.auto_link:
                    matches.append(IdentityMatch(left, right, decision))
        return tuple(matches)


def can_auto_link(left: NormalizedIdentity, right: NormalizedIdentity) -> bool:
    """Convenience predicate for callers that do not need match evidence."""

    return DeterministicIdentityMatcher().match(left, right).auto_link


def _no_match(reason: str) -> MatchDecision:
    return MatchDecision(False, None, reason)
