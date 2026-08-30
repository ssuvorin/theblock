from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationInput:
    has_role: bool
    has_company: bool
    has_location_or_remote: bool
    has_open_state: bool
    source_accessible: bool
    full_document_checked: bool
    evidence_type: str = "other"
    was_verified: bool = False


@dataclass(frozen=True)
class VerificationOutcome:
    status: str
    checks: dict[str, bool]


class OpportunityVerifier:
    """Applies the five explicit source checks without promoting snippets."""

    def verify(self, evidence: VerificationInput) -> VerificationOutcome:
        checks = {
            "role": evidence.has_role,
            "company": evidence.has_company,
            "location_or_remote": evidence.has_location_or_remote,
            "open_state": evidence.has_open_state,
            "source_accessible": evidence.source_accessible,
            "full_document_checked": evidence.full_document_checked,
        }
        if evidence.was_verified and (
            not evidence.source_accessible or not evidence.has_open_state
        ):
            return VerificationOutcome("stale", checks)
        if all(checks.values()):
            return VerificationOutcome("verified_open_role", checks)
        if evidence.evidence_type in {"careers_page", "funding", "expansion", "office"}:
            return VerificationOutcome("hiring_signal", checks)
        return VerificationOutcome("unverified", checks)
