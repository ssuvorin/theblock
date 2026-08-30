from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Owner


class OwnerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def by_email(self, email: str) -> Owner | None:
        return self._session.scalar(select(Owner).where(Owner.email == email.casefold()))

    def by_id(self, owner_id: str) -> Owner | None:
        return self._session.get(Owner, owner_id)
