from typing import ClassVar

from app.domain.ports import Goal


class DeterministicGoalParser:
    """Extracts the bounded P0 job-search goal without an LLM dependency."""

    _roles = (
        ("senior product manager", "Senior Product Manager"),
        ("product manager", "Product Manager"),
        ("product lead", "Product Lead"),
        ("product owner", "Product Owner"),
        ("head of product", "Head of Product"),
    )
    _product_roles: ClassVar[list[str]] = [
        "Senior Product Manager",
        "Product Lead",
        "Product Owner",
        "Head of Product",
    ]

    def parse(self, question: str) -> Goal:
        normalized = question.casefold()
        role = next((title for phrase, title in self._roles if phrase in normalized), None)
        if (
            role is None
            and "product" in normalized
            and any(word in normalized for word in ("role", "job", "hiring", "opportunity"))
        ):
            role = "Product Manager"
        industry = self._industry(normalized)
        location = self._location(normalized)
        related = [title for title in self._product_roles if title != role] if role else []
        return Goal(
            role=role,
            related_roles=related,
            industry=industry,
            location=location,
            action="Find current opportunities, then identify warm paths through my network",
        )

    @staticmethod
    def _industry(question: str) -> list[str]:
        if any(term in question for term in ("crypto", "web3", "digital asset", "blockchain")):
            return ["crypto", "web3", "digital assets"]
        if "fintech" in question:
            return ["fintech"]
        return []

    @staticmethod
    def _location(question: str) -> list[str]:
        if "dubai" in question:
            return ["Dubai", "UAE"]
        if "uae" in question or "united arab emirates" in question:
            return ["UAE"]
        return []
