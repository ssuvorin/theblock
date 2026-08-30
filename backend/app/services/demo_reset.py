"""Remove the demo seed once a real archive has been imported.

The seed exists only so the app is not empty before the first import. Afterwards the two
compete for the same graph: the seed has its own self person, so the owner would end up with
two identities, and a contact who appears in both is duplicated because a seeded person
carries no profile URL to match on and matching people by name is not safe enough to do
automatically. Seeded rows all have deterministic ids, so they can be deleted exactly rather
than guessed at.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.models import (
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
from app.services.demo_seed import (
    SEEDED_INTERACTION_KEYS,
    SEEDED_OPPORTUNITY_KEYS,
    SEEDED_ORG_KEYS,
    SEEDED_PERSON_KEYS,
    seeded_ids,
)


@dataclass
class DemoResetReport:
    people_removed: int = 0
    interactions_removed: int = 0
    relationships_removed: int = 0
    opportunities_removed: int = 0
    organizations_removed: int = 0
    paths_removed: int = 0

    @property
    def removed_anything(self) -> bool:
        return any(value for value in asdict(self).values())

    def as_dict(self) -> dict[str, object]:
        return {**asdict(self), "removed": self.removed_anything}


class DemoSeedReset:
    """Delete the seeded graph, keeping the owner row that authentication depends on."""

    def __init__(self, session: Session, owner: Owner) -> None:
        self._session = session
        self._owner = owner
        self._people = seeded_ids("person", SEEDED_PERSON_KEYS)
        self._orgs = seeded_ids("org", SEEDED_ORG_KEYS)
        self._opportunities = seeded_ids("opportunity", SEEDED_OPPORTUNITY_KEYS)
        self._interactions = seeded_ids("interaction", SEEDED_INTERACTION_KEYS)

    def run(self) -> DemoResetReport:
        report = DemoResetReport()
        if not self._present():
            return report
        report.paths_removed = self._delete_paths()
        self._delete(
            OpportunityEvidence,
            OpportunityEvidence.opportunity_id.in_(self._opportunities),
        )
        report.opportunities_removed = self._delete(
            Opportunity, Opportunity.id.in_(self._opportunities)
        )
        self._delete(FollowUp, FollowUp.person_id.in_(self._people))
        self._delete(
            InteractionParticipant,
            or_(
                InteractionParticipant.interaction_id.in_(self._interactions),
                InteractionParticipant.person_id.in_(self._people),
            ),
        )
        report.interactions_removed = self._delete(
            InteractionEvent, InteractionEvent.id.in_(self._interactions)
        )
        report.relationships_removed = self._delete_relationships()
        self._delete(PersonIdentity, PersonIdentity.person_id.in_(self._people))
        report.people_removed = self._delete(Person, Person.id.in_(self._people))
        report.organizations_removed = self._delete(Organization, Organization.id.in_(self._orgs))
        self._release_self_person()
        self._session.flush()
        return report

    def _present(self) -> bool:
        return bool(
            self._session.scalar(
                select(Person.id).where(
                    Person.owner_id == self._owner.id,
                    Person.id.in_(self._people),
                )
            )
        )

    def _delete_paths(self) -> int:
        return self._delete(
            OpportunityPersonPath,
            or_(
                OpportunityPersonPath.opportunity_id.in_(self._opportunities),
                OpportunityPersonPath.person_id.in_(self._people),
            ),
        )

    def _delete_relationships(self) -> int:
        return self._delete(
            Relationship,
            or_(
                Relationship.person_a_id.in_(self._people),
                Relationship.person_b_id.in_(self._people),
            ),
        )

    def _delete(self, model: type, condition) -> int:
        statement = delete(model).where(model.owner_id == self._owner.id, condition)
        return self._session.execute(statement).rowcount or 0

    def _release_self_person(self) -> None:
        if self._owner.self_person_id in self._people:
            self._owner.self_person_id = None
