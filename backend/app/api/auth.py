from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentOwner, DbSession, RuntimeSettings
from app.domain.schemas import LoginRequest
from app.repositories.owners import OwnerRepository
from app.security import OwnerCredentialService, SessionTokenService

router = APIRouter(prefix="/api", tags=["authentication"])


@router.post("/auth/session")
def create_session(
    payload: LoginRequest,
    response: Response,
    db: DbSession,
    settings: RuntimeSettings,
) -> dict:
    if not OwnerCredentialService(settings).valid(payload.email, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    owner = OwnerRepository(db).by_email(payload.email)
    if owner is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Owner not found")
    token, expires_in = SessionTokenService(settings).issue(owner.id)
    response.set_cookie(
        key="owner_session",
        value=token,
        max_age=expires_in,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in}


@router.delete("/auth/session")
def delete_session(response: Response) -> dict[str, bool]:
    response.delete_cookie("owner_session", path="/")
    return {"logged_out": True}


@router.get("/owner/current")
def current_owner(owner: CurrentOwner) -> dict:
    return {
        "owner": {
            "id": owner.id,
            "display_name": owner.display_name,
            "email": owner.email,
            "timezone": owner.timezone,
            "location": owner.location,
            "current_goal": owner.current_goal,
        }
    }
