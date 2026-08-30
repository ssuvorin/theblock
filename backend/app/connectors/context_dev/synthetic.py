from datetime import UTC, datetime

from app.domain.ports import Goal, MarketSearchResponse, PublicSearchResult


class SyntheticDemoMarketSearch:
    """Clearly labelled fallback used only when no live provider key is configured."""

    disclosure = (
        "Synthetic demo provider data; URLs resemble public first-party/ATS sources, "
        "but this response is not a live vacancy check."
    )

    def search(self, owner_id: str, goal: Goal, num_results: int = 20) -> MarketSearchResponse:
        del owner_id, num_results
        checked_at = datetime.now(UTC)
        results = self._results(checked_at) if self._matches_demo_goal(goal) else []
        return MarketSearchResponse(
            results=results,
            provider="synthetic_demo",
            checked_at=checked_at,
            credits_consumed=0,
            disclosure=self.disclosure,
        )

    @staticmethod
    def _matches_demo_goal(goal: Goal) -> bool:
        return bool(
            goal.role
            and "Product" in goal.role
            and set(goal.industry) & {"crypto", "web3", "digital assets"}
            and set(goal.location) & {"Dubai", "UAE"}
        )

    def _results(self, checked_at: datetime) -> list[PublicSearchResult]:
        definitions = [
            (
                "https://www.binance.com/en/careers/job-openings/product-manager-uae",
                "Product Manager — Dubai, UAE",
                "binance.com",
                "Binance",
                "Product Manager",
                "Dubai, UAE",
                "verified_open_role",
                "vacancy",
                "Synthetic fixture for a Dubai digital-assets product vacancy.",
            ),
            (
                "https://jobs.ashbyhq.com/rain/senior-product-manager-uae",
                "Senior Product Manager — UAE",
                "jobs.ashbyhq.com",
                "Rain",
                "Senior Product Manager",
                "UAE",
                "verified_open_role",
                "vacancy",
                "Synthetic fixture for a UAE crypto product vacancy.",
            ),
            (
                "https://www.okx.com/careers/product-lead-dubai",
                "Product Lead — Dubai",
                "okx.com",
                "OKX",
                "Product Lead",
                "Dubai, UAE",
                "verified_open_role",
                "vacancy",
                "Synthetic fixture intentionally has no known network path.",
            ),
            (
                "https://crypto.com/careers/uae-product-team",
                "UAE product-team expansion",
                "crypto.com",
                "Crypto.com",
                "Product team expansion",
                "UAE",
                "hiring_signal",
                "expansion",
                "Synthetic expansion signal; no matching open role is claimed.",
            ),
        ]
        return [self._make_result(item, checked_at) for item in definitions]

    @staticmethod
    def _make_result(definition: tuple, checked_at: datetime) -> PublicSearchResult:
        url, title, domain, company, role, location, status, evidence_type, excerpt = definition
        is_vacancy = evidence_type == "vacancy"
        return PublicSearchResult(
            url=url,
            title=title,
            source_domain=domain,
            excerpt=excerpt,
            role_title=role,
            organization_name=company,
            organization_domain={
                "Binance": "binance.com",
                "Rain": "rain.com",
                "OKX": "okx.com",
                "Crypto.com": "crypto.com",
            }[company],
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
