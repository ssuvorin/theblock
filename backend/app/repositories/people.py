from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.models import (
    FollowUp,
    InteractionEvent,
    InteractionParticipant,
    Organization,
    Person,
    PersonIdentity,
    Relationship,
)


class PeopleRepository:
    def __init__(self, session: Session, owner_id: str, demo_mode: bool) -> None:
        self._session = session
        self._owner_id = owner_id
        self._demo_mode = demo_mode

    def list(
        self,
        q: str | None = None,
        tag: str | None = None,
        status: str | None = None,
    ) -> list[tuple[Person, Relationship | None, Organization | None]]:
        statement = (
            select(Person, Relationship, Organization)
            .outerjoin(
                Relationship,
                (Relationship.person_b_id == Person.id) & (Relationship.owner_id == self._owner_id),
            )
            .outerjoin(Organization, Organization.id == Person.current_org_id)
            .where(Person.owner_id == self._owner_id)
        )
        if self._demo_mode:
            statement = statement.where(Person.data_origin != "real_import")
        if q:
            needle = f"%{q}%"
            statement = statement.where(
                or_(Person.display_name.ilike(needle), Person.current_title.ilike(needle))
            )
        if status:
            statement = statement.where(Relationship.status == status)
        rows = list(self._session.execute(statement.order_by(Person.display_name)).all())
        if tag:
            rows = [
                row
                for row in rows
                if tag.casefold() in {str(item).casefold() for item in row[0].tags}
            ]
        return rows

    def get(self, person_id: str) -> Person | None:
        statement = select(Person).where(
            Person.id == person_id,
            Person.owner_id == self._owner_id,
        )
        if self._demo_mode:
            statement = statement.where(Person.data_origin != "real_import")
        return self._session.scalar(statement)

    def organization(self, person: Person) -> Organization | None:
        if not person.current_org_id:
            return None
        return self._session.scalar(
            select(Organization).where(
                Organization.id == person.current_org_id,
                Organization.owner_id == self._owner_id,
            )
        )

    def identities(self, person_id: str) -> list[PersonIdentity]:
        return list(
            self._session.scalars(
                select(PersonIdentity).where(
                    PersonIdentity.owner_id == self._owner_id,
                    PersonIdentity.person_id == person_id,
                )
            )
        )

    def identity_sources(self, person_ids: Sequence[str]) -> dict[str, set[str]]:
        """Map person ids to their identity source names in one query."""

        ids = list(person_ids)
        if not ids:
            return {}
        statement = select(PersonIdentity.person_id, PersonIdentity.source).where(
            PersonIdentity.owner_id == self._owner_id,
            PersonIdentity.person_id.in_(ids),
        )
        return self._grouped_sources(statement)

    def interaction_sources(self, person_ids: Sequence[str]) -> dict[str, set[str]]:
        """Map person ids to their interaction source names in one query."""

        ids = list(person_ids)
        if not ids:
            return {}
        statement = (
            select(InteractionParticipant.person_id, InteractionEvent.source)
            .join(
                InteractionEvent,
                InteractionEvent.id == InteractionParticipant.interaction_id,
            )
            .where(
                InteractionEvent.owner_id == self._owner_id,
                InteractionParticipant.person_id.in_(ids),
                InteractionEvent.is_deleted.is_(False),
            )
        )
        if self._demo_mode:
            statement = statement.where(InteractionEvent.data_origin != "real_import")
        return self._grouped_sources(statement)

    def _grouped_sources(self, statement: Select) -> dict[str, set[str]]:
        grouped: dict[str, set[str]] = {}
        for person_id, source in self._session.execute(statement).all():
            grouped.setdefault(person_id, set()).add(source)
        return grouped

    def relationship(self, person_id: str) -> Relationship | None:
        return self._session.scalar(
            select(Relationship).where(
                Relationship.owner_id == self._owner_id,
                Relationship.person_b_id == person_id,
            )
        )

    def interactions(
        self,
        person_id: str,
        source: str | None = None,
    ) -> list[InteractionEvent]:
        statement = (
            select(InteractionEvent)
            .join(
                InteractionParticipant,
                InteractionParticipant.interaction_id == InteractionEvent.id,
            )
            .where(
                InteractionEvent.owner_id == self._owner_id,
                InteractionParticipant.person_id == person_id,
                InteractionEvent.is_deleted.is_(False),
            )
        )
        if self._demo_mode:
            statement = statement.where(InteractionEvent.data_origin != "real_import")
        if source:
            statement = statement.where(InteractionEvent.source == source)
        return list(
            self._session.scalars(statement.order_by(InteractionEvent.occurred_at.desc())).unique()
        )

    def follow_ups(self, person_id: str) -> list[FollowUp]:
        return list(
            self._session.scalars(
                select(FollowUp).where(
                    FollowUp.owner_id == self._owner_id,
                    FollowUp.person_id == person_id,
                )
            )
        )


class InteractionRepository:
    def __init__(self, session: Session, owner_id: str, demo_mode: bool) -> None:
        self._session = session
        self._owner_id = owner_id
        self._demo_mode = demo_mode

    def get(self, interaction_id: str) -> InteractionEvent | None:
        statement = select(InteractionEvent).where(
            InteractionEvent.id == interaction_id,
            InteractionEvent.owner_id == self._owner_id,
            InteractionEvent.is_deleted.is_(False),
        )
        if self._demo_mode:
            statement = statement.where(InteractionEvent.data_origin != "real_import")
        return self._session.scalar(statement)

    def participants(
        self, interaction_id: str
    ) -> list[tuple[InteractionParticipant, Person | None]]:
        statement = (
            select(InteractionParticipant, Person)
            .outerjoin(Person, Person.id == InteractionParticipant.person_id)
            .where(
                InteractionParticipant.owner_id == self._owner_id,
                InteractionParticipant.interaction_id == interaction_id,
            )
        )
        if self._demo_mode:
            statement = statement.where(
                or_(Person.id.is_(None), Person.data_origin != "real_import")
            )
        return list(self._session.execute(statement).all())
