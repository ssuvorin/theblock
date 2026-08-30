from __future__ import annotations

from collections.abc import Sequence

from app.domain.ports import Goal
from app.models import Opportunity, Organization
from app.repositories.opportunities import OpportunityRepository
from app.services.presentation import opportunity_base, warm_path_json
from app.services.query.ranking import QueryRanker


class OpportunityCardBuilder:
    """Builds one opportunity card shape shared by the query answer and the REST endpoints."""

    def __init__(self, repo: OpportunityRepository, ranker: QueryRanker) -> None:
        self._repo = repo
        self._ranker = ranker

    def card(self, opportunity: Opportunity, goal: Goal | None = None) -> dict:
        """Public evidence plus every evidence-backed warm path for one opportunity."""

        return self._assemble(opportunity, self._repo.paths(opportunity.id), goal)

    def cards(self, opportunities: Sequence[Opportunity], goal: Goal | None = None) -> list[dict]:
        """Same shape for many opportunities, loading all warm paths in a single query."""

        grouped = self._repo.paths_by_opportunity([item.id for item in opportunities])
        return [self._assemble(item, grouped.get(item.id, []), goal) for item in opportunities]

    def public_only_card(self, opportunity: Opportunity, goal: Goal | None = None) -> dict:
        """Public evidence only, stating that private warm-path retrieval is unavailable."""

        card = self._assemble(opportunity, [], goal)
        card["warm_path_status"] = "private_search_unavailable"
        return card

    @staticmethod
    def sources_checked(cards: Sequence[dict]) -> int:
        """Distinct public evidence URLs actually attached to the returned cards."""

        return len(
            {
                citation["url"]
                for card in cards
                for citation in card.get("public_citations", [])
                if citation.get("url")
            }
        )

    def _assemble(
        self,
        opportunity: Opportunity,
        rows: Sequence[tuple],
        goal: Goal | None,
    ) -> dict:
        organization = self._repo.organization(opportunity.organization_id)
        warm_paths = [self._warm_path(row, organization) for row in rows]
        card = opportunity_base(opportunity, organization, self._repo.evidence(opportunity.id))
        card.update(
            warm_paths=warm_paths,
            warm_path_count=len(warm_paths),
            warm_path_status="found" if warm_paths else "no_warm_path_found",
        )
        if goal is not None:
            card.update(self._goal_fields(opportunity, goal, organization, warm_paths))
        return card

    def _warm_path(self, row: tuple, organization: Organization | None) -> dict:
        path, person, relationship, interaction = row
        factors = self._ranker.path_factors(relationship, interaction, path.path_score)
        return warm_path_json(path, person, relationship, interaction, organization, factors)

    def _goal_fields(
        self,
        opportunity: Opportunity,
        goal: Goal,
        organization: Organization | None,
        warm_paths: list[dict],
    ) -> dict:
        quality = max((item["ranking_factors"]["score"] for item in warm_paths), default=0.0)
        factors = self._ranker.opportunity_factors(
            opportunity,
            goal,
            organization is not None,
            quality,
        )
        return {
            "goal_fit": "strong" if factors["goal_fit"] >= 0.8 else "related",
            "ranking_factors": factors,
        }
