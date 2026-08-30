"""Persist a parsed relationship archive into the canonical PostgreSQL graph.

The connector stays persistence-neutral; this service owns every write. Reruns of the
same archive update existing rows instead of creating duplicates, because people are
keyed on their canonical profile URL and messages on their deterministic external id.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.linkedin_export.importer import LinkedInImportPlan, ProposedPerson
from app.connectors.linkedin_export.normalize import NormalizedMessage, NormalizedParticipant
from app.models import (
    InteractionEvent,
    InteractionParticipant,
    Organization,
    Owner,
    Person,
    PersonIdentity,
    utcnow,
)
from app.services.relationship_graph import (
    RelationshipDeriver,
    collect_reciprocity,
    interaction_id_index,
)

INTERACTION_SOURCE = "linkedin"
IDENTITY_SOURCE = "linkedin_export"
LINKEDIN_IDENTITY_KIND = "linkedin_url"


@dataclass
class ImportReport:
    people_created: int = 0
    people_matched: int = 0
    identities_created: int = 0
    interactions_created: int = 0
    interactions_existing: int = 0
    participants_created: int = 0
    participants_unresolved: int = 0
    relationships_created: int = 0
    relationships_updated: int = 0
    organizations_created: int = 0
    contacts_without_title: int = 0
    self_person_id: str | None = None
    data_origin: str = "synthetic"

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class ArchiveGraphWriter:
    """Write people, identities, interactions, participants, and edges for one owner."""

    def __init__(self, session: Session, owner: Owner) -> None:
        self._session = session
        self._owner = owner
        self._report = ImportReport()
        self._identities: dict[tuple[str, str], PersonIdentity] = {}
        self._organizations: dict[str, Organization] = {}

    def write(self, plan: LinkedInImportPlan) -> ImportReport:
        self._report.data_origin = plan.data_origin
        self._identities = self._identity_index()
        self._organizations = self._organization_index()
        people = self._upsert_people(plan)
        self_person = self._resolve_self_person(plan, people)
        if self_person is None:
            raise ValueError("archive has no owner profile and no existing self person")
        self._upsert_owner_identities(plan, self_person)
        fresh = self._upsert_interactions(plan)
        self._upsert_participants(plan, fresh, people)
        self._derive_edges(plan, people, self_person)
        self._report.self_person_id = self_person.id
        self._report.contacts_without_title = sum(
            1
            for person in people.values()
            if person.id != self_person.id and not person.current_title
        )
        return self._report

    def _identity_index(self) -> dict[tuple[str, str], PersonIdentity]:
        rows = self._session.scalars(
            select(PersonIdentity).where(PersonIdentity.owner_id == self._owner.id)
        )
        return {(row.kind, row.normalized_value): row for row in rows}

    def _upsert_people(self, plan: LinkedInImportPlan) -> dict[str, Person]:
        people: dict[str, Person] = {}
        for proposed in plan.people:
            url = proposed.linkedin_url
            identity = self._identities.get((LINKEDIN_IDENTITY_KIND, url))
            person = self._session.get(Person, identity.person_id) if identity else None
            if person is not None:
                self._refresh_display_name(person, proposed.display_name)
                self._report.people_matched += 1
            else:
                person = self._create_person(proposed.display_name, url, plan.data_origin)
            self._apply_employment(person, proposed)
            people[url] = person
        self._session.flush()
        return people

    def _create_person(self, display_name: str, url: str, data_origin: str) -> Person:
        person = Person(
            owner_id=self._owner.id,
            display_name=display_name or url,
            data_origin=data_origin,
        )
        self._session.add(person)
        self._session.flush()
        self._add_identity(
            person_id=person.id,
            kind=LINKEDIN_IDENTITY_KIND,
            raw_value=url,
            normalized_value=url,
            is_verified=True,
            is_primary=True,
        )
        self._report.people_created += 1
        return person

    def _apply_employment(self, person: Person, proposed: ProposedPerson) -> None:
        """Fill title and employer from the connection list without overwriting owner edits."""

        if proposed.current_title and "current_title" not in person.manual_overrides:
            person.current_title = proposed.current_title
        if proposed.current_company and "current_org_id" not in person.manual_overrides:
            person.current_org_id = self._organization(proposed.current_company).id

    def _organization(self, name: str) -> Organization:
        existing = self._organizations.get(name.casefold())
        if existing is not None:
            return existing
        organization = Organization(owner_id=self._owner.id, name=name)
        self._session.add(organization)
        self._session.flush()
        self._organizations[name.casefold()] = organization
        self._report.organizations_created += 1
        return organization

    def _organization_index(self) -> dict[str, Organization]:
        rows = self._session.scalars(
            select(Organization).where(Organization.owner_id == self._owner.id)
        )
        return {row.name.casefold(): row for row in rows}

    def _add_identity(
        self,
        *,
        person_id: str,
        kind: str,
        raw_value: str,
        normalized_value: str,
        is_verified: bool,
        is_primary: bool,
    ) -> None:
        key = (kind, normalized_value)
        if key in self._identities:
            return
        row = PersonIdentity(
            owner_id=self._owner.id,
            person_id=person_id,
            kind=kind,
            raw_value=raw_value,
            normalized_value=normalized_value,
            source=IDENTITY_SOURCE,
            is_verified=is_verified,
            is_primary=is_primary,
        )
        self._session.add(row)
        self._identities[key] = row
        self._report.identities_created += 1

    @staticmethod
    def _refresh_display_name(person: Person, display_name: str) -> None:
        if not display_name or "display_name" in person.manual_overrides:
            return
        if person.display_name != display_name:
            person.display_name = display_name
            person.updated_at = utcnow()

    def _resolve_self_person(
        self,
        plan: LinkedInImportPlan,
        people: dict[str, Person],
    ) -> Person | None:
        url = plan.owner_profile.profile_url if plan.owner_profile else None
        person = people.get(url) if url else None
        if person is None and self._owner.self_person_id:
            person = self._session.get(Person, self._owner.self_person_id)
        if person is None:
            return None
        self._owner.self_person_id = person.id
        headline = plan.owner_profile.headline if plan.owner_profile else None
        if headline and not person.current_title:
            person.current_title = headline
        return person

    def _upsert_owner_identities(self, plan: LinkedInImportPlan, self_person: Person) -> None:
        for identity in plan.owner_identities:
            self._add_identity(
                person_id=self_person.id,
                kind=identity.kind.value,
                raw_value=identity.raw_value,
                normalized_value=identity.normalized_value,
                is_verified=identity.is_verified,
                is_primary=identity.is_primary,
            )
        self._session.flush()

    def _upsert_interactions(self, plan: LinkedInImportPlan) -> dict[str, InteractionEvent]:
        existing = {
            row.external_id: row
            for row in self._session.scalars(
                select(InteractionEvent).where(
                    InteractionEvent.owner_id == self._owner.id,
                    InteractionEvent.source == INTERACTION_SOURCE,
                )
            )
        }
        fresh: dict[str, InteractionEvent] = {}
        for message in plan.messages:
            if message.external_id in existing or message.external_id in fresh:
                self._report.interactions_existing += 1
                continue
            event = InteractionEvent(
                owner_id=self._owner.id,
                external_id=message.external_id,
                type="message",
                source=INTERACTION_SOURCE,
                direction=message.direction,
                occurred_at=message.occurred_at,
                subject=message.subject,
                body_text=message.body_text,
                metadata_json=_message_metadata(message),
                raw_ref=f"linkedin_export://{message.conversation_external_id}",
                data_origin=message.data_origin,
            )
            self._session.add(event)
            fresh[message.external_id] = event
            self._report.interactions_created += 1
        self._session.flush()
        return fresh

    def _upsert_participants(
        self,
        plan: LinkedInImportPlan,
        fresh: dict[str, InteractionEvent],
        people: dict[str, Person],
    ) -> None:
        for message in plan.messages:
            event = fresh.get(message.external_id)
            if event is None:
                continue
            seen: set[tuple[str, str]] = set()
            for participant, role in _participants(message):
                address = _source_address(participant)
                if (address, role) in seen:
                    continue
                seen.add((address, role))
                person_id = _participant_person(participant, people)
                self._session.add(
                    InteractionParticipant(
                        owner_id=self._owner.id,
                        interaction_id=event.id,
                        person_id=person_id,
                        source_address=address,
                        role=role,
                    )
                )
                self._report.participants_created += 1
                if person_id is None:
                    self._report.participants_unresolved += 1
        self._session.flush()

    def _derive_edges(
        self,
        plan: LinkedInImportPlan,
        people: dict[str, Person],
        self_person: Person,
    ) -> None:
        owner_url = plan.owner_profile.profile_url if plan.owner_profile else None
        stats = collect_reciprocity(plan.messages, owner_url)
        deriver = RelationshipDeriver(self._session, self._owner.id, self_person)
        created, updated = deriver.apply(
            stats,
            people,
            interaction_id_index(self._session, self._owner.id),
        )
        self._report.relationships_created = created
        self._report.relationships_updated = updated


def _participants(message: NormalizedMessage) -> tuple[tuple[NormalizedParticipant, str], ...]:
    return (
        (message.sender, "sender"),
        *((recipient, "recipient") for recipient in message.recipients),
    )


def _participant_person(
    participant: NormalizedParticipant,
    people: dict[str, Person],
) -> str | None:
    if not participant.profile_url:
        return None
    person = people.get(participant.profile_url)
    return person.id if person else None


def _source_address(participant: NormalizedParticipant) -> str:
    return participant.source_address or participant.profile_url or "unknown"


def _message_metadata(message: NormalizedMessage) -> dict[str, object]:
    return {
        "conversation_id": message.conversation_external_id,
        "conversation_type": message.conversation_type,
        "folder": message.folder,
        "attachments": message.attachments,
        "citation_locator": "body:0",
    }


def latest_import_at(session: Session, owner_id: str) -> datetime | None:
    return session.scalar(
        select(InteractionEvent.created_at)
        .where(
            InteractionEvent.owner_id == owner_id,
            InteractionEvent.source == INTERACTION_SOURCE,
        )
        .order_by(InteractionEvent.created_at.desc())
        .limit(1)
    )
