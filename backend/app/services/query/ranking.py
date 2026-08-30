from datetime import UTC, datetime

from app.domain.ports import Goal
from app.models import InteractionEvent, Opportunity, Relationship


class QueryRanker:
    """Produces transparent principal ranking factors for cards and paths."""

    def opportunity_factors(
        self,
        opportunity: Opportunity,
        goal: Goal,
        organization_resolved: bool,
        warm_path_quality: float,
    ) -> dict[str, float]:
        goal_fit = self._goal_fit(opportunity, goal)
        evidence_quality = {
            "verified_open_role": 1.0,
            "hiring_signal": 0.65,
            "unverified": 0.25,
            "stale": 0.0,
        }[opportunity.verification_status]
        freshness = self._freshness(opportunity.checked_at)
        org_resolution = 1.0 if organization_resolved else 0.0
        score = (
            goal_fit * 0.35
            + evidence_quality * 0.25
            + freshness * 0.15
            + org_resolution * 0.1
            + warm_path_quality * 0.15
        )
        return {
            "goal_fit": round(goal_fit, 3),
            "evidence_quality": evidence_quality,
            "freshness": round(freshness, 3),
            "organization_resolution": org_resolution,
            "warm_path_quality": round(warm_path_quality, 3),
            "score": round(score, 3),
        }

    def path_factors(
        self,
        relationship: Relationship,
        interaction: InteractionEvent,
        path_score: float,
    ) -> dict[str, float]:
        recency = self._freshness(interaction.occurred_at, horizon_days=365)
        score = path_score * 0.3 + relationship.strength_score * 0.3 + recency * 0.2 + 1.0 * 0.2
        return {
            "semantic_relevance": round(path_score, 3),
            "evidence_backed_path": 1.0,
            "relationship_strength": round(relationship.strength_score, 3),
            "recency": round(recency, 3),
            "score": round(score, 3),
        }

    @staticmethod
    def _goal_fit(opportunity: Opportunity, goal: Goal) -> float:
        role_text = (opportunity.role_title or "").casefold()
        role_match = bool(goal.role and goal.role.casefold() in role_text)
        related_match = any(item.casefold() in role_text for item in goal.related_roles)
        location_text = (opportunity.location or "").casefold()
        location_match = any(item.casefold() in location_text for item in goal.location)
        return min(
            1.0,
            (0.6 if role_match else 0.45 if related_match else 0.2)
            + (0.4 if location_match else 0.0),
        )

    @staticmethod
    def _freshness(value: datetime, horizon_days: int = 90) -> float:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        age_days = max(0.0, (datetime.now(UTC) - value).total_seconds() / 86400)
        return max(0.0, 1.0 - age_days / horizon_days)
