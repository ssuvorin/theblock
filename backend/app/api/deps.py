from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Owner
from app.repositories.owners import OwnerRepository
from app.security import SessionTokenService

bearer = HTTPBearer(auto_error=False)


def get_db(request: Request) -> Generator[Session, None, None]:
    yield from request.app.state.database.session()


def get_runtime_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_current_owner(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Owner:
    token = credentials.credentials if credentials else request.cookies.get("owner_session")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    owner_id = SessionTokenService(request.app.state.settings).owner_id(token)
    owner = OwnerRepository(db).by_id(owner_id)
    if owner is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Owner not found")
    return owner


DbSession = Annotated[Session, Depends(get_db)]
CurrentOwner = Annotated[Owner, Depends(get_current_owner)]
RuntimeSettings = Annotated[Settings, Depends(get_runtime_settings)]
