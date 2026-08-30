import hashlib
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (
    ContextCreditBudget,
    FollowUp,
    InteractionEvent,
    InteractionParticipant,
    Opportunity,
    OpportunityEvidence,
    OpportunityPersonPath,
    Organization,
    Owner,
    Person,
    PersonIdentity,
    Relationship,
)

_NAMESPACE = uuid.UUID("bfb9563e-04bb-4baf-adcc-e3965f6f6081")

SEEDED_ORG_KEYS = ("binance", "rain", "okx", "crypto", "neural", "crescent", "palm")
SEEDED_PERSON_KEYS = (
    "alex",
    "marta",
    "sergey",
    "john",
    "daniel",
    "nadia",
    "omar",
    "lena",
    "tom",
    "ruth",
)
SEEDED_OPPORTUNITY_KEYS = ("binance", "rain", "okx", "crypto")
SEEDED_INTERACTION_KEYS = ("marta", "john", "sergey", "daniel")


def stable_id(label: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, label))


def seeded_ids(prefix: str, keys: tuple[str, ...]) -> list[str]:
    """Recompute the ids the seeder produced, so they can be removed exactly."""

    return [stable_id(f"{prefix}:{key}") for key in keys]


class DemoSeeder:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._now = datetime.now(UTC)

    def seed(self) -> None:
        if self._session.scalar(select(Owner).limit(1)):
            ensure_budget(self._session)
            return
        owner = self._seed_owner()
        organizations = self._seed_organizations(owner.id)
        people = self._seed_people(owner, organizations)
        relationships = self._seed_relationships(owner.id, people)
        interactions = self._seed_interactions(owner.id, people)
        opportunities = seed_opportunities(self._session, owner.id, organizations, self._now)
        seed_paths(self._session, owner.id, people, relationships, interactions, opportunities)
        seed_follow_up(self._session, owner.id, people["john"], interactions["john"])
        ensure_budget(self._session)
        self._session.commit()

    def _seed_owner(self) -> Owner:
        owner = Owner(
            id=stable_id("owner:alex"),
            display_name=self._settings.owner_display_name,
            email=self._settings.owner_email.casefold(),
            timezone="Asia/Dubai",
            location="Dubai, UAE",
            current_goal="Find a Product Manager role at a crypto company in Dubai",
        )
        self._session.add(owner)
        self._session.flush()
        return owner

    def _seed_organizations(self, owner_id: str) -> dict[str, Organization]:
        definitions = {
            "binance": ("Binance", "binance.com", "Digital assets"),
            "rain": ("Rain", "rain.com", "Crypto infrastructure"),
            "okx": ("OKX", "okx.com", "Digital assets"),
            "crypto": ("Crypto.com", "crypto.com", "Digital assets"),
            "neural": ("NeuralPay Labs", "neuralpay.example", "AI technology"),
            "crescent": ("Crescent Digital Ventures", "crescent.example", "Venture capital"),
            "palm": ("Palm Logistics", "palmlogistics.example", "Logistics"),
        }
        organizations: dict[str, Organization] = {}
        for key, (name, domain, industry) in definitions.items():
            organization = Organization(
                id=stable_id(f"org:{key}"),
                owner_id=owner_id,
                name=name,
                domain=domain,
                industry=industry,
            )
            self._session.add(organization)
            organizations[key] = organization
        self._session.flush()
        return organizations

    def _seed_people(
        self,
        owner: Owner,
        organizations: dict[str, Organization],
    ) -> dict[str, Person]:
        definitions = self._person_definitions(organizations)
        people: dict[str, Person] = {}
        for key, (name, title, org_id, tags) in definitions.items():
            person = Person(
                id=stable_id(f"person:{key}"),
                owner_id=owner.id,
                display_name=name,
                current_title=title,
                current_org_id=org_id,
                tags=tags,
                data_origin="synthetic",
            )
            self._session.add(person)
            people[key] = person
            self._add_identity(owner.id, person, key)
        self._session.flush()
        owner.self_person_id = people["alex"].id
        return people

    @staticmethod
    def _person_definitions(organizations: dict[str, Organization]) -> dict[str, tuple]:
        return {
            "alex": ("Alex Ivanov", "Marketing lead; crypto builder", None, ["crypto"]),
            "marta": (
                "Marta",
                "VP Product, crypto infrastructure, Dubai",
                organizations["binance"].id,
                ["product", "crypto", "dubai"],
            ),
            "sergey": (
                "Sergey Lapin",
                "CTO, AI technology startup, Dubai",
                organizations["neural"].id,
                ["ai", "hiring", "dubai"],
            ),
            "john": (
                "John",
                "Investor, digital assets, UAE",
                organizations["crescent"].id,
                ["investor", "crypto", "uae"],
            ),
            "daniel": (
                "Daniel Ruiz",
                "Ops lead, Palm Logistics, Dubai",
                organizations["palm"].id,
                ["operations", "dubai"],
            ),
            "nadia": ("Nadia", "Growth advisor", None, ["growth"]),
            "omar": ("Omar", "Founder", None, ["founder"]),
            "lena": ("Lena", "Product designer", None, ["design"]),
            "tom": ("Tom", "Engineer", None, ["engineering"]),
            "ruth": ("Ruth", "Recruiter", None, ["recruiting"]),
        }

    def _add_identity(self, owner_id: str, person: Person, key: str) -> None:
        source = "whatsapp" if key == "daniel" else "gmail"
        value = f"{key}@synthetic.example"
        kind = "whatsapp_jid" if source == "whatsapp" else "email"
        if source == "whatsapp":
            value = "971500000000@s.whatsapp.net"
        self._session.add(
            PersonIdentity(
                id=stable_id(f"identity:{key}"),
                owner_id=owner_id,
                person_id=person.id,
                kind=kind,
                raw_value=value,
                normalized_value=value.casefold(),
                source=source,
                is_verified=True,
                is_primary=True,
            )
        )

    def _seed_relationships(
        self,
        owner_id: str,
        people: dict[str, Person],
    ) -> dict[str, Relationship]:
        strengths = {"marta": 0.82, "sergey": 0.76, "john": 0.91, "daniel": 0.55}
        relationships: dict[str, Relationship] = {}
        for index, key in enumerate(k for k in people if k != "alex"):
            active = key in strengths
            score = strengths.get(key, max(0.12, 0.35 - index * 0.03))
            relationship = Relationship(
                id=stable_id(f"relationship:{key}"),
                owner_id=owner_id,
                person_a_id=people["alex"].id,
                person_b_id=people[key].id,
                strength_score=score,
                strength_components=self._strength_components(score),
                status="active" if active else "cold",
                last_interaction_at=self._now - timedelta(days=30 if active else 500 + index),
                total_interactions=18 if active else 2,
                introduced_by=people["alex"].id if key == "marta" else None,
            )
            self._session.add(relationship)
            relationships[key] = relationship
        self._session.flush()
        return relationships

    @staticmethod
    def _strength_components(score: float) -> dict[str, float]:
        return {
            "recency": round(score * 0.9, 2),
            "frequency": round(score * 0.8, 2),
            "channel_diversity": round(score * 0.7, 2),
            "manual_adjust": 0.0,
        }

    def _seed_interactions(
        self,
        owner_id: str,
        people: dict[str, Person],
    ) -> dict[str, InteractionEvent]:
        definitions = {
            "marta": (
                "gmail",
                "TOKEN2049 follow-up",
                "Great discussing digital-asset infrastructure. Happy to reconnect "
                "about our Dubai product team.",
                240,
            ),
            "john": (
                "collabute",
                "Digital assets portfolio introductions",
                "John offered to introduce Alex to product leaders in Rain's UAE "
                "portfolio network.",
                21,
            ),
            "sergey": (
                "whatsapp",
                "UAE product expansion",
                "We discussed hiring and a Crypto.com product-team expansion in the UAE.",
                14,
            ),
            "daniel": (
                "whatsapp",
                "Palm Logistics role",
                "Daniel shared an operations role at Palm Logistics in Dubai.",
                45,
            ),
        }
        interactions: dict[str, InteractionEvent] = {}
        for key, (source, subject, body, days_ago) in definitions.items():
            event = InteractionEvent(
                id=stable_id(f"interaction:{key}"),
                owner_id=owner_id,
                external_id=f"synthetic-{key}-1",
                type="meeting" if source == "collabute" else "message",
                source=source,
                direction="incoming",
                occurred_at=self._now - timedelta(days=days_ago),
                subject=subject,
                body_text=body,
                metadata_json={"citation_locator": "body:0", "fixture": True},
                raw_ref=f"synthetic://{source}/{key}/1",
                data_origin="synthetic",
            )
            self._session.add(event)
            self._add_participants(owner_id, event, people["alex"], people[key])
            interactions[key] = event
        self._session.flush()
        return interactions

    def _add_participants(
        self,
        owner_id: str,
        event: InteractionEvent,
        owner_person: Person,
        contact: Person,
    ) -> None:
        for person, role in ((contact, "sender"), (owner_person, "recipient")):
            self._session.add(
                InteractionParticipant(
                    id=stable_id(f"participant:{event.id}:{person.id}"),
                    owner_id=owner_id,
                    interaction_id=event.id,
                    person_id=person.id,
                    source_address=f"{person.display_name}@synthetic.example",
                    role=role,
                )
            )


def opportunity_definitions(organizations: dict[str, Organization]) -> dict[str, tuple]:
    return {
        "binance": (
            organizations["binance"],
            "https://www.binance.com/en/careers/job-openings/product-manager-uae",
            "Product Manager",
            "Dubai, UAE",
            "verified_open_role",
            "Synthetic fixture for a Dubai digital-assets product vacancy.",
            "vacancy",
        ),
        "rain": (
            organizations["rain"],
            "https://jobs.ashbyhq.com/rain/senior-product-manager-uae",
            "Senior Product Manager",
            "UAE",
            "verified_open_role",
            "Synthetic fixture for a UAE crypto product vacancy.",
            "vacancy",
        ),
        "okx": (
            organizations["okx"],
            "https://www.okx.com/careers/product-lead-dubai",
            "Product Lead",
            "Dubai, UAE",
            "verified_open_role",
            "Synthetic fixture intentionally has no known network path.",
            "vacancy",
        ),
        "crypto": (
            organizations["crypto"],
            "https://crypto.com/careers/uae-product-team",
            "Product team expansion",
            "UAE",
            "hiring_signal",
            "Synthetic expansion signal; no matching open role is claimed.",
            "expansion",
        ),
    }


def add_evidence(session: Session, owner_id: str, opportunity: Opportunity, kind: str) -> None:
    is_vacancy = kind == "vacancy"
    excerpt = opportunity.summary or ""
    session.add(
        OpportunityEvidence(
            id=stable_id(f"evidence:{opportunity.id}"),
            owner_id=owner_id,
            opportunity_id=opportunity.id,
            url=opportunity.canonical_url,
            title=f"{opportunity.role_title} — {opportunity.location}",
            excerpt=excerpt,
            source_domain=opportunity.source_domain,
            content_hash=hashlib.sha256(excerpt.encode()).hexdigest(),
            evidence_type=kind,
            checked_at=opportunity.checked_at,
            verification_details={
                "role": is_vacancy,
                "company": True,
                "location_or_remote": True,
                "open_state": is_vacancy,
                "source_accessible": True,
                "synthetic_fixture": True,
            },
        )
    )


def seed_opportunities(
    session: Session,
    owner_id: str,
    organizations: dict[str, Organization],
    now: datetime,
) -> dict[str, Opportunity]:
    opportunities: dict[str, Opportunity] = {}
    for key, definition in opportunity_definitions(organizations).items():
        org, url, role, location, status, summary, evidence_type = definition
        opportunity = Opportunity(
            id=stable_id(f"opportunity:{key}"),
            owner_id=owner_id,
            organization_id=org.id,
            canonical_url=url,
            source_domain=url.split("/")[2],
            role_title=role,
            location=location,
            summary=summary,
            verification_status=status,
            checked_at=now,
            provider="synthetic_demo",
            provider_disclosure="Synthetic demo market evidence; not a live vacancy check.",
        )
        session.add(opportunity)
        session.flush()
        add_evidence(session, owner_id, opportunity, evidence_type)
        opportunities[key] = opportunity
    return opportunities


def seed_paths(
    session: Session,
    owner_id: str,
    people: dict[str, Person],
    relationships: dict[str, Relationship],
    interactions: dict[str, InteractionEvent],
    opportunities: dict[str, Opportunity],
) -> None:
    definitions = {
        "marta": ("binance", "reconnection", 0.92, "Reconnect and ask about the product team"),
        "john": ("rain", "introduction", 0.88, "Ask for an introduction to a product leader"),
        "sergey": ("crypto", "direct", 0.69, "Reconnect before a role is advertised"),
    }
    for person_key, (opp_key, path_type, score, action) in definitions.items():
        session.add(
            OpportunityPersonPath(
                id=stable_id(f"path:{person_key}:{opp_key}"),
                owner_id=owner_id,
                opportunity_id=opportunities[opp_key].id,
                person_id=people[person_key].id,
                relationship_id=relationships[person_key].id,
                private_evidence_id=interactions[person_key].id,
                path_type=path_type,
                path_score=score,
                rationale=(
                    f"Evidence-backed {path_type} path through {people[person_key].display_name}"
                ),
                suggested_action=action,
            )
        )


def seed_follow_up(
    session: Session,
    owner_id: str,
    person: Person,
    evidence: InteractionEvent,
) -> None:
    session.add(
        FollowUp(
            id=stable_id("followup:john:intro"),
            owner_id=owner_id,
            person_id=person.id,
            reason="Ask John about the Rain product leadership introduction",
            due_date=date.today() + timedelta(days=7),
            due_timezone="Asia/Dubai",
            source="collabute",
            source_key=f"synthetic-action:{evidence.id}",
            priority=10,
            status="pending",
        )
    )


def ensure_budget(session: Session) -> None:
    if session.get(ContextCreditBudget, 1) is None:
        session.add(ContextCreditBudget(id=1))
        session.flush()
