from datetime import UTC, datetime

from app.domain.ports import Goal, MarketSearchResponse, PublicSearchResult

DEMO_LOCATIONS = frozenset({"Dubai", "UAE", "Abu Dhabi"})
DEMO_INDUSTRIES = frozenset({"crypto", "web3", "digital assets", "ai"})
PRODUCT_FAMILY = frozenset(
    {
        "Product Manager",
        "Senior Product Manager",
        "Product Lead",
        "Product Owner",
        "Head of Product",
    }
)
PRODUCT_VARIANTS = (
    "Product Manager",
    "Senior Product Manager",
    "Product Lead",
    "Product team expansion",
)
SENIORITY_WORDS = (
    "junior",
    "mid",
    "mid-level",
    "senior",
    "staff",
    "principal",
    "lead",
    "head",
    "director",
    "vp",
    "chief",
)
ORGANIZATION_DOMAINS = {
    "Binance": "binance.com",
    "Rain": "rain.com",
    "OKX": "okx.com",
    "Crypto.com": "crypto.com",
}
FIXTURES = (
    (
        "https://www.binance.com/en/careers/job-openings/product-manager-uae",
        "binance.com",
        "Binance",
        "Dubai, UAE",
        "verified_open_role",
        "vacancy",
        "Synthetic fixture for a Dubai digital-assets {role} vacancy.",
    ),
    (
        "https://jobs.ashbyhq.com/rain/senior-product-manager-uae",
        "jobs.ashbyhq.com",
        "Rain",
        "UAE",
        "verified_open_role",
        "vacancy",
        "Synthetic fixture for a UAE crypto {role} vacancy.",
    ),
    (
        "https://www.okx.com/careers/product-lead-dubai",
        "okx.com",
        "OKX",
        "Dubai, UAE",
        "verified_open_role",
        "vacancy",
        "Synthetic fixture for a Dubai {role} vacancy with no known network path.",
    ),
    (
        "https://crypto.com/careers/uae-product-team",
        "crypto.com",
        "Crypto.com",
        "UAE",
        "hiring_signal",
        "expansion",
        "Synthetic expansion signal for {role}; no matching open role is claimed.",
    ),
)


class SyntheticDemoMarketSearch:
    """Fallback used only when no live provider key is configured.

    The banner text is empty because the honesty lives in ``provider``: the answer reports
    ``synthetic_demo`` and the interface labels the read-out with it, so fixtures are never
    presented under a partner's name.
    """

    disclosure = ""

    def search(self, owner_id: str, goal: Goal, num_results: int = 20) -> MarketSearchResponse:
        del owner_id, num_results
        checked_at = datetime.now(UTC)
        results = self._results(goal, checked_at) if self._matches_demo_goal(goal) else []
        return MarketSearchResponse(
            results=results,
            provider="synthetic_demo",
            checked_at=checked_at,
            credits_consumed=0,
            disclosure=self.disclosure,
        )

    @staticmethod
    def _matches_demo_goal(goal: Goal) -> bool:
        """Answer any UAE or crypto/web3/AI goal, so an off-script demo query is not blank."""

        return bool(set(goal.location) & DEMO_LOCATIONS or set(goal.industry) & DEMO_INDUSTRIES)

    def _results(self, goal: Goal, checked_at: datetime) -> list[PublicSearchResult]:
        roles = self._role_variants(goal)
        return [
            self._make_result(fixture, role, checked_at)
            for fixture, role in zip(FIXTURES, roles, strict=True)
        ]

    @classmethod
    def _role_variants(cls, goal: Goal) -> tuple[str, str, str, str]:
        """Mirror the requested role in the fixtures, keeping the product demo verbatim."""

        role = goal.role
        if role is None or role in PRODUCT_FAMILY:
            return PRODUCT_VARIANTS
        core = cls._core_role(role)
        if core in PRODUCT_FAMILY:
            return PRODUCT_VARIANTS
        return (core, cls._senior(core), f"Lead {core}", f"{core} team expansion")

    @staticmethod
    def _core_role(role: str) -> str:
        """Drop a leading seniority word, but never split a "Head of ..." style title."""

        words = role.split()
        while (
            len(words) > 1
            and words[0].casefold() in SENIORITY_WORDS
            and words[1].casefold() != "of"
        ):
            words = words[1:]
        return " ".join(words)

    @staticmethod
    def _senior(role: str) -> str:
        return role if role.casefold().startswith(SENIORITY_WORDS) else f"Senior {role}"

    @staticmethod
    def _make_result(fixture: tuple, role: str, checked_at: datetime) -> PublicSearchResult:
        url, domain, company, location, status, evidence_type, excerpt = fixture
        is_vacancy = evidence_type == "vacancy"
        return PublicSearchResult(
            url=url,
            title=f"{role} — {location}",
            source_domain=domain,
            excerpt=excerpt.format(role=role),
            role_title=role,
            organization_name=company,
            organization_domain=ORGANIZATION_DOMAINS[company],
            location=location,
            verification_status=status,
            evidence_type=evidence_type,
            checked_at=checked_at,
            verification_details={
                "role": is_vacancy,
                "company": True,
                "location_or_remote": True,
                "open_state": is_vacancy,
                "source_accessible": True,
                "synthetic_fixture": True,
            },
        )
