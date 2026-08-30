import hashlib
import json
import logging
import math
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.ports import (
    Goal,
    MarketSearchResponse,
    MarketSearchUnavailable,
    PublicSearchResult,
)
from app.services.context_credits import ContextCreditLedger

logger = logging.getLogger(__name__)


class WebSearchRequestBuilder:
    def build(self, goal: Goal, num_results: int) -> dict:
        bounded = min(30, max(10, num_results))
        roles = [item for item in [goal.role, *goal.related_roles] if item]
        role_query = " OR ".join(f'"{item}"' for item in roles) or '"job opportunity"'
        industry_query = " OR ".join(goal.industry) or "technology"
        location_query = " OR ".join(goal.location) or "UAE"
        query = f"({role_query}) ({industry_query}) ({location_query}) (jobs OR careers OR hiring)"
        return {
            "query": query[:500],
            "numResults": bounded,
            "country": "ae",
            "freshness": "last_month",
            "queryFanout": True,
            "excludeDomains": ["linkedin.com"],
            "markdownOptions": {"enabled": False},
        }

    @staticmethod
    def fingerprint(payload: dict) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class ContextDevWebSearch:
    """Budget-gated live Context.dev broad-discovery adapter."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._settings = settings
        self._ledger = ContextCreditLedger(session)
        self._builder = WebSearchRequestBuilder()

    def search(self, owner_id: str, goal: Goal, num_results: int = 20) -> MarketSearchResponse:
        payload = self._builder.build(goal, num_results)
        request_key = self._builder.fingerprint(payload)
        estimate = max(1, math.ceil(payload["numResults"] / 10))
        reservation = self._ledger.reserve(owner_id, "market_search", request_key, estimate)
        if not reservation.allowed:
            reason = (
                "cached request"
                if reservation.duplicate
                else f"budget exhausted: {reservation.reason}"
            )
            return MarketSearchResponse(
                [], "context.dev", datetime.now(UTC), 0, reason, cache_hit=reservation.duplicate
            )
        try:
            body = self._request(payload)
        except (httpx.HTTPError, ValueError) as error:
            self._release(request_key, "context.dev market search transport or decode failure")
            raise MarketSearchUnavailable(f"context.dev request failed: {error}") from error
        except BaseException:
            # Releasing credits is cleanup, so it must stay broad. Narrowing this clause only
            # loses the refund: an unlisted error would strand the reservation as "reserved"
            # forever and quietly shrink the budget. The re-raise keeps the failure visible.
            self._release(request_key, "context.dev market search failed before a usable response")
            raise
        consumed = self._credits_consumed(body, estimate)
        self._ledger.reconcile("market_search", request_key, consumed)
        checked_at = datetime.now(UTC)
        return MarketSearchResponse(
            results=self._normalize(body, checked_at),
            provider="context.dev",
            checked_at=checked_at,
            credits_consumed=consumed,
            disclosure=(
                "Live Context.dev broad discovery; results remain unverified "
                "until source checks pass."
            ),
        )

    def _release(self, request_key: str, message: str) -> None:
        """Log the failure and return the reserved credits, never logging the API key."""

        logger.exception(message)
        self._ledger.fail("market_search", request_key)

    def _request(self, payload: dict) -> dict:
        key = self._settings.context_dev_api_key
        if key is None:
            raise RuntimeError("Context.dev is not configured")
        headers = {"Authorization": f"Bearer {key.get_secret_value()}"}
        with httpx.Client(timeout=self._settings.context_timeout_seconds) as client:
            response = client.post(
                f"{self._settings.context_dev_base_url.rstrip('/')}/web/search",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _credits_consumed(body: dict, estimate: int) -> int:
        metadata = body.get("key_metadata") or body.get("keyMetadata") or {}
        return int(metadata.get("credits_consumed", metadata.get("creditsConsumed", estimate)))

    @staticmethod
    def _normalize(body: dict, checked_at: datetime) -> list[PublicSearchResult]:
        raw_results = body.get("results") or body.get("data") or []
        normalized: list[PublicSearchResult] = []
        for item in raw_results:
            url = str(item.get("url") or "")
            if not url or urlsplit(url).hostname in {"linkedin.com", "www.linkedin.com"}:
                continue
            domain = urlsplit(url).hostname or "unknown"
            normalized.append(
                PublicSearchResult(
                    url=url,
                    title=str(item.get("title") or "Untitled public result"),
                    source_domain=domain,
                    excerpt=str(item.get("excerpt") or item.get("snippet") or ""),
                    role_title=item.get("role_title"),
                    organization_name=item.get("company"),
                    organization_domain=item.get("company_domain"),
                    location=item.get("location"),
                    verification_status="unverified",
                    evidence_type="other",
                    checked_at=checked_at,
                    verification_details={"broad_search_snippet_only": True},
                )
            )
        return normalized
