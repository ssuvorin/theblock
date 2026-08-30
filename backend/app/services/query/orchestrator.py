import logging
from dataclasses import asdict

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings, has_live_context_key
from app.connectors.context_dev.synthetic import SyntheticDemoMarketSearch
from app.connectors.context_dev.web_search import ContextDevWebSearch
from app.domain.ports import Goal, MarketSearchPort, MarketSearchResponse, MarketSearchUnavailable
from app.models import Opportunity, Owner
from app.repositories.opportunities import OpportunityRepository
from app.repositories.people import PeopleRepository
from app.services.opportunity_cards import OpportunityCardBuilder
from app.services.presentation import interaction_json
from app.services.query.goal_parser import DeterministicGoalParser
from app.services.query.ranking import QueryRanker

logger = logging.getLogger(__name__)

PRIVATE_RETRIEVAL_COMPONENT = "private_retrieval"
MARKET_SEARCH_COMPONENT = "context_dev_search"
MARKET_OUTAGE = (MarketSearchUnavailable, httpx.HTTPError)


class OpportunityQueryOrchestrator:
    """Connects bounded public opportunities to evidence-backed private paths."""

    def __init__(self, session: Session, owner: Owner, settings: Settings) -> None:
        self._session = session
        self._owner = owner
        self._settings = settings
        self._repo = OpportunityRepository(session, owner.id, settings.demo_mode)
        self._people = PeopleRepository(session, owner.id, settings.demo_mode)
        self._ranker = QueryRanker()
        self._cards = OpportunityCardBuilder(self._repo, self._ranker)
        self._provider = self._market_provider()

    def execute(self, question: str) -> dict:
        """Answer one goal, degrading only for named outages and never for a defect.

        The two catches below are the complete list of tolerated failures: a provider transport
        outage and a PostgreSQL error while reading the private graph. Everything else — a blank
        API key, a normalisation bug, schema drift — propagates and becomes a 500 rather than
        being relabelled as a partially available component.
        """

        goal = DeterministicGoalParser().parse(question)
        try:
            search = self._provider.search(self._owner.id, goal, num_results=20)
        except MARKET_OUTAGE:
            logger.exception(
                "market search unavailable for owner %s; answering from private graph only",
                self._owner.id,
            )
            return self._market_degraded(goal)
        opportunities = [
            self._repo.upsert_result(result, search.provider, search.disclosure)
            for result in search.results
        ]
        self._session.flush()
        try:
            cards = self._card_list(opportunities, goal)
        except SQLAlchemyError:
            logger.exception(
                "private warm-path retrieval failed for owner %s; returning public evidence only",
                self._owner.id,
            )
            cards = [self._public_only_card(item, goal) for item in opportunities]
            return self._answer(
                goal, search, cards, degraded_components=[PRIVATE_RETRIEVAL_COMPONENT]
            )
        cards.sort(key=lambda item: item["ranking_factors"]["score"], reverse=True)
        return self._answer(goal, search, cards)

    def _card_list(self, opportunities: list[Opportunity], goal: Goal) -> list[dict]:
        return self._cards.cards(opportunities, goal)

    def _public_only_card(self, opportunity: Opportunity, goal: Goal) -> dict:
        return self._cards.public_only_card(opportunity, goal)

    def _answer(
        self,
        goal: Goal,
        search: MarketSearchResponse,
        cards: list[dict],
        degraded_components: list[str] | None = None,
    ) -> dict:
        degraded_components = degraded_components or []
        has_paths = any(card["warm_paths"] for card in cards)
        quality = "partial" if degraded_components else "sufficient" if cards else "insufficient"
        return {
            "answer": {
                "summary": self._summary(cards, has_paths, degraded_components),
                "goal": asdict(goal),
                "search": {
                    "provider": search.provider,
                    "country": "ae",
                    "freshness": "last_month",
                    "checked_at": search.checked_at.isoformat(),
                    "credits_consumed": search.credits_consumed,
                    "cache_hit": search.cache_hit,
                    "disclosure": search.disclosure,
                    "sources_checked": self._cards.sources_checked(cards),
                },
                "opportunities": cards,
                "network_candidates": [],
                "evidence_quality": quality,
                "degraded": bool(degraded_components),
                "degraded_components": degraded_components,
                "private_retrieval": "owner-scoped prepared synthetic graph",
            }
        }

    def _market_degraded(self, goal: Goal) -> dict:
        candidates = self._network_candidates()
        return {
            "answer": {
                "summary": (
                    "Current vacancy search is unavailable; showing cited network candidates only."
                ),
                "goal": asdict(goal),
                "search": {
                    "provider": self._provider_name(),
                    "country": "ae",
                    "freshness": "last_month",
                    "checked_at": None,
                    "credits_consumed": 0,
                    "cache_hit": False,
                    "disclosure": (
                        "Public market search failed; no public vacancy evidence was retrieved."
                    ),
                    "sources_checked": 0,
                },
                "opportunities": [],
                "network_candidates": candidates,
                "evidence_quality": "partial" if candidates else "insufficient",
                "degraded": True,
                "degraded_components": [MARKET_SEARCH_COMPONENT],
                "private_retrieval": "owner-scoped prepared synthetic graph",
            }
        }

    def _network_candidates(self) -> list[dict]:
        candidates = []
        for person, relationship, _organization in self._people.list(status="active"):
            interactions = self._people.interactions(person.id)
            if not interactions:
                continue
            candidates.append(
                {
                    "person_id": person.id,
                    "display_name": person.display_name,
                    "current_role": person.current_title,
                    "relevance_reason": (
                        "Private relationship evidence may be relevant; no company path asserted."
                    ),
                    "private_citations": [interaction_json(interactions[0])],
                    "relationship_strength": relationship.strength_score if relationship else 0.0,
                }
            )
        return candidates[:5]

    def _market_provider(self) -> MarketSearchPort:
        if has_live_context_key(self._settings):
            return ContextDevWebSearch(self._session, self._settings)
        return SyntheticDemoMarketSearch()

    def _provider_name(self) -> str:
        return "context.dev" if has_live_context_key(self._settings) else "synthetic_demo"

    @staticmethod
    def _summary(cards: list[dict], has_paths: bool, degraded: list[str]) -> str:
        if degraded:
            return "Current opportunities were found, but private warm-path search is unavailable."
        if not cards:
            return "No verified opportunities or supported network paths were found for this goal."
        path_text = (
            "Evidence-backed warm paths are attached." if has_paths else "No warm paths were found."
        )
        return f"Found {len(cards)} current or high-confidence opportunity records. {path_text}"
