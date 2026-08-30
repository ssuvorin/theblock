"""Deterministic parsing of a free-text job-search question into a bounded goal.

The vocabulary is explicit on purpose: a seniority prefix plus a role noun is recognised
without an LLM, so an off-script question such as "im looking job in dubai in web3 AI engineer"
still produces a role, while an unrecognised question keeps ``role=None`` instead of a guess.
"""

import re
from typing import ClassVar

from app.domain.ports import Goal

SENIORITY_PREFIXES: tuple[tuple[str, str], ...] = (
    ("head of", "Head of"),
    ("director of", "Director of"),
    ("vp of", "VP of"),
    ("mid-level", "Mid-Level"),
    ("junior", "Junior"),
    ("senior", "Senior"),
    ("staff", "Staff"),
    ("principal", "Principal"),
    ("chief", "Chief"),
    ("lead", "Lead"),
    ("mid", "Mid"),
)
ROLE_NOUNS: tuple[tuple[str, str], ...] = (
    ("machine learning engineer", "Machine Learning Engineer"),
    ("ai engineer", "AI Engineer"),
    ("ml engineer", "ML Engineer"),
    ("data scientist", "Data Scientist"),
    ("data engineer", "Data Engineer"),
    ("data analyst", "Data Analyst"),
    ("business analyst", "Business Analyst"),
    ("software engineer", "Software Engineer"),
    ("backend engineer", "Backend Engineer"),
    ("back-end engineer", "Backend Engineer"),
    ("frontend engineer", "Frontend Engineer"),
    ("front-end engineer", "Frontend Engineer"),
    ("full stack engineer", "Full Stack Engineer"),
    ("full-stack engineer", "Full Stack Engineer"),
    ("fullstack engineer", "Full Stack Engineer"),
    ("security engineer", "Security Engineer"),
    ("devops engineer", "DevOps Engineer"),
    ("platform engineer", "Platform Engineer"),
    ("product manager", "Product Manager"),
    ("product designer", "Product Designer"),
    ("product owner", "Product Owner"),
    ("ux designer", "UX Designer"),
    ("operations manager", "Operations Manager"),
    ("full stack", "Full Stack Engineer"),
    ("full-stack", "Full Stack Engineer"),
    ("engineer", "Engineer"),
    ("developer", "Developer"),
    ("designer", "Designer"),
    ("analyst", "Analyst"),
    ("researcher", "Researcher"),
    ("marketer", "Marketer"),
    ("recruiter", "Recruiter"),
    ("architect", "Architect"),
    ("founder", "Founder"),
    ("devops", "DevOps Engineer"),
    ("backend", "Backend Engineer"),
    ("frontend", "Frontend Engineer"),
    ("operations", "Operations"),
    ("security", "Security Engineer"),
)
ADJACENT_ROLES: dict[str, tuple[str, ...]] = {
    "AI Engineer": ("ML Engineer", "Machine Learning Engineer", "Backend Engineer"),
    "ML Engineer": ("AI Engineer", "Machine Learning Engineer", "Data Scientist"),
    "Machine Learning Engineer": ("AI Engineer", "ML Engineer", "Data Scientist"),
    "Data Scientist": ("ML Engineer", "Data Analyst", "Data Engineer"),
    "Data Engineer": ("Backend Engineer", "Data Scientist", "Platform Engineer"),
    "Data Analyst": ("Data Scientist", "Business Analyst", "Analyst"),
    "Business Analyst": ("Data Analyst", "Analyst", "Operations Manager"),
    "Software Engineer": ("Backend Engineer", "Full Stack Engineer", "Frontend Engineer"),
    "Backend Engineer": ("Software Engineer", "Full Stack Engineer", "Platform Engineer"),
    "Frontend Engineer": ("Full Stack Engineer", "Software Engineer", "Product Designer"),
    "Full Stack Engineer": ("Backend Engineer", "Frontend Engineer", "Software Engineer"),
    "Platform Engineer": ("DevOps Engineer", "Backend Engineer", "Software Engineer"),
    "DevOps Engineer": ("Platform Engineer", "Backend Engineer", "Security Engineer"),
    "Security Engineer": ("DevOps Engineer", "Platform Engineer", "Backend Engineer"),
    "Engineer": ("Software Engineer", "Backend Engineer", "Developer"),
    "Developer": ("Software Engineer", "Engineer", "Full Stack Engineer"),
    "Designer": ("Product Designer", "UX Designer", "Frontend Engineer"),
    "Product Designer": ("UX Designer", "Designer", "Frontend Engineer"),
    "UX Designer": ("Product Designer", "Designer", "Researcher"),
    "Researcher": ("Data Scientist", "Analyst", "ML Engineer"),
    "Analyst": ("Data Analyst", "Business Analyst", "Researcher"),
    "Marketer": ("Growth Marketer", "Product Marketer", "Marketing Manager"),
    "Recruiter": ("Talent Partner", "Talent Acquisition Manager", "Head of Talent"),
    "Architect": ("Solutions Architect", "Platform Engineer", "Backend Engineer"),
    "Founder": ("Co-Founder", "General Manager", "Head of Product"),
    "Operations": ("Operations Manager", "Business Analyst", "Chief of Staff"),
    "Operations Manager": ("Operations", "Business Analyst", "General Manager"),
}
INDUSTRY_TERMS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("crypto", "web3", "digital asset", "digital assets", "blockchain"),
        ("crypto", "web3", "digital assets"),
    ),
    (("fintech", "payments"), ("fintech",)),
    (("ai", "a.i.", "artificial intelligence", "machine learning", "ml", "llm"), ("ai",)),
    (("saas", "b2b software"), ("saas",)),
    (("logistics", "supply chain", "freight"), ("logistics",)),
    (("healthtech", "health tech", "healthcare", "medtech"), ("healthtech",)),
    (("gaming", "games", "game studio", "esports"), ("gaming",)),
)
LOCATION_TERMS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("dubai",), ("Dubai", "UAE")),
    (("abu dhabi",), ("Abu Dhabi", "UAE")),
    (("uae", "united arab emirates"), ("UAE",)),
    (("riyadh",), ("Riyadh",)),
    (("remote",), ("Remote",)),
    (("london",), ("London",)),
    (("berlin",), ("Berlin",)),
    (("singapore",), ("Singapore",)),
)
_PREFIX_ALTERNATION = "|".join(prefix for prefix, _ in SENIORITY_PREFIXES)
_NOUN_ALTERNATION = "|".join(
    re.escape(noun) for noun, _ in sorted(ROLE_NOUNS, key=lambda item: -len(item[0]))
)
_ROLE_PATTERN = re.compile(
    rf"\b(?:({_PREFIX_ALTERNATION})\s+)?({_NOUN_ALTERNATION})s?\b",
)
_NOUN_TITLES = dict(ROLE_NOUNS)
_PREFIX_TITLES = dict(SENIORITY_PREFIXES)


def _mentions(text: str, term: str) -> bool:
    """Match a vocabulary term as whole words so "Dubai" never counts as an "ai" mention."""

    return re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", text) is not None


def _unique(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return list(seen)


class DeterministicGoalParser:
    """Extracts the bounded job-search goal from free text without an LLM dependency."""

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
        role = self._role(normalized)
        return Goal(
            role=role,
            related_roles=self._related(role),
            industry=self._industry(normalized),
            location=self._location(normalized),
            action="Find current opportunities, then identify warm paths through my network",
        )

    def _role(self, question: str) -> str | None:
        """Prefer the explicit product phrases, then the general vocabulary, then nothing."""

        explicit = next((title for phrase, title in self._roles if phrase in question), None)
        if explicit:
            return explicit
        general = self._general_role(question)
        if general:
            return general
        if "product" in question and any(
            word in question for word in ("role", "job", "hiring", "opportunity")
        ):
            return "Product Manager"
        return None

    @staticmethod
    def _general_role(question: str) -> str | None:
        match = _ROLE_PATTERN.search(question)
        if match is None:
            return None
        noun = _NOUN_TITLES[match.group(2)]
        prefix = _PREFIX_TITLES.get(match.group(1) or "")
        if prefix is None or noun.startswith(prefix):
            return noun
        return f"{prefix} {noun}"

    def _related(self, role: str | None) -> list[str]:
        """List roles adjacent to the detected one, keeping the product family as it was."""

        if role is None:
            return []
        if role in self._product_roles or role == "Product Manager":
            return [title for title in self._product_roles if title != role]
        base = self._without_seniority(role)
        adjacent = list(ADJACENT_ROLES.get(base, ()))
        if base != role:
            adjacent.insert(0, base)
        if not adjacent:
            adjacent = [f"Senior {base}", f"Lead {base}"]
        return [title for title in _unique(adjacent) if title != role][:4]

    @staticmethod
    def _without_seniority(role: str) -> str:
        for _, prefix in SENIORITY_PREFIXES:
            if role.startswith(f"{prefix} ") and role != f"{prefix} ":
                return role[len(prefix) + 1 :]
        return role

    @staticmethod
    def _industry(question: str) -> list[str]:
        found: list[str] = []
        for terms, labels in INDUSTRY_TERMS:
            if any(_mentions(question, term) for term in terms):
                found.extend(labels)
        return _unique(found)

    @staticmethod
    def _location(question: str) -> list[str]:
        found: list[str] = []
        for terms, labels in LOCATION_TERMS:
            if any(_mentions(question, term) for term in terms):
                found.extend(labels)
        return _unique(found)
