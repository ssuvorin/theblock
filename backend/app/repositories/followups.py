from datetime import date

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models import FollowUp, Person, utcnow


class FollowUpRepository:
    def __init__(self, session: Session, owner_id: str, demo_mode: bool) -> None:
        self._session = session
        self._owner_id = owner_id
        self._demo_mode = demo_mode

    def list(self, status: str | None = None) -> list[tuple[FollowUp, Person]]:
        overdue = case(
            (FollowUp.due_date < date.today(), 0),
            (FollowUp.due_date.is_(None), 2),
            else_=1,
        )
        statement = (
            select(FollowUp, Person)
            .join(Person, Person.id == FollowUp.person_id)
            .where(FollowUp.owner_id == self._owner_id)
            .order_by(overdue, FollowUp.due_date, FollowUp.priority.desc())
        )
        if self._demo_mode:
            statement = statement.where(Person.data_origin != "real_import")
        if status:
            statement = statement.where(FollowUp.status == status)
        return list(self._session.execute(statement).all())

    def get(self, follow_up_id: str) -> FollowUp | None:
        statement = (
            select(FollowUp)
            .join(Person, Person.id == FollowUp.person_id)
            .where(
                FollowUp.id == follow_up_id,
                FollowUp.owner_id == self._owner_id,
            )
        )
        if self._demo_mode:
            statement = statement.where(Person.data_origin != "real_import")
        return self._session.scalar(statement)

    def create(
        self,
        person_id: str,
        reason: str,
        due_date: date | None,
        due_timezone: str | None,
        priority: int,
        source_key: str | None,
    ) -> FollowUp:
        person = self._visible_person(person_id)
        if person is None:
            raise LookupError("person not found")
        if source_key:
            existing = self._session.scalar(
                select(FollowUp).where(
                    FollowUp.owner_id == self._owner_id,
                    FollowUp.source == "manual",
                    FollowUp.source_key == source_key,
                )
            )
            if existing:
                return existing
        follow_up = FollowUp(
            owner_id=self._owner_id,
            person_id=person_id,
            reason=reason,
            due_date=due_date,
            due_timezone=due_timezone,
            priority=priority,
            source="manual",
            source_key=source_key,
        )
        self._session.add(follow_up)
        self._session.flush()
        return follow_up

    def update(self, follow_up: FollowUp, changes: dict) -> FollowUp:
        for key, value in changes.items():
            setattr(follow_up, key, value)
        follow_up.updated_at = utcnow()
        self._session.flush()
        return follow_up

    def delete(self, follow_up: FollowUp) -> None:
        self._session.delete(follow_up)
        self._session.flush()

    def _visible_person(self, person_id: str) -> Person | None:
        statement = select(Person).where(
            Person.id == person_id,
            Person.owner_id == self._owner_id,
        )
        if self._demo_mode:
            statement = statement.where(Person.data_origin != "real_import")
        return self._session.scalar(statement)
