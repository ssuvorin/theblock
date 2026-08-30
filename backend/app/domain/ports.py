from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Goal:
    role: str | None
    related_roles: list[str]
    industry: list[str]
    location: list[str]
    action: str


@dataclass(frozen=True)
class PublicSearchResult:
    url: str
    title: str
    source_domain: str
    excerpt: str
    role_title: str | None
    organization_name: str | None
    organization_domain: str | None
    location: str | None
    verification_status: str
    evidence_type: str
    checked_at: datetime
    verification_details: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketSearchResponse:
    results: list[PublicSearchResult]
    provider: str
    checked_at: datetime
    credits_consumed: int
    disclosure: str
    cache_hit: bool = False


class MarketSearchPort(Protocol):
    def search(self, owner_id: str, goal: Goal, num_results: int = 20) -> MarketSearchResponse:
        """Return bounded public market evidence for one parsed goal."""


class OutboundMessagePort(Protocol):
    def send(self, recipient: str, text: str) -> None:
        """Outbound capability intentionally not used by the draft flow."""
