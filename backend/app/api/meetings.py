"""Schedule one Google Meet, on an explicit request, and record it in the graph.

This endpoint is the only outbound side effect in the product. Everything else — drafts,
opportunities, reminders — stops short of contacting anyone. So it is deliberately narrow:
one event per call, guests named by the owner, and a response that states plainly whether the
invite actually went out and whether Collabute can see the meeting.

It cannot hand the meeting to Collabute. Collabute's MCP surface exposes no tool that creates
a meeting or attaches a notetaker, so the response says the notetaker is not attached rather
than implying a handoff that did not happen.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import CurrentOwner, DbSession, RuntimeSettings
from app.connectors.base import ConnectorError, NormalizedParticipant, NormalizedRecord
from app.connectors.google.calendar import SOURCE as CALENDAR_SOURCE
from app.connectors.google.scheduling import (
    MeetingRequest,
    MeetingScheduler,
    ScheduledMeeting,
    SchedulingDisabled,
)
from app.domain.identity.normalize import (
    IdentityKind,
    IdentityNormalizationError,
    normalize_email,
)
from app.models import Owner, SourceConnection
from app.repositories.connections import SourceConnectionRepository
from app.services.connector_graph import ConnectorGraphWriter
from app.services.relationship_recompute import recompute_edges
from app.services.secret_vault import SecretVault, SecretVaultUnavailable, VaultCredentials

router = APIRouter(prefix="/api/meetings", tags=["meetings"])
GOOGLE_SOURCE = "google"
NOTETAKER_NOTE = (
    "Collabute exposes no MCP tool that registers a meeting or attaches a notetaker, so this "
    "meeting is not sent to Collabute. It will appear in Collabute only once Collabute's own "
    "calendar integration picks it up, and it can then be imported by a Collabute sync."
)


class ScheduleMeetingRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    guest_emails: list[str] = Field(min_length=1, max_length=20)
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    description: str | None = Field(default=None, max_length=4000)
    notify_guests: bool = True

    @field_validator("guest_emails")
    @classmethod
    def normalized_guests(cls, value: list[str]) -> list[str]:
        """Validate with the project's own normalizer so an invite address is one address."""

        normalized = []
        for raw in value:
            try:
                normalized.append(normalize_email(raw))
            except IdentityNormalizationError as error:
                raise ValueError(f"{raw!r} is not a usable email address") from error
        return list(dict.fromkeys(normalized))


@router.post("", status_code=status.HTTP_201_CREATED)
def schedule_meeting(
    payload: ScheduleMeetingRequest,
    owner: CurrentOwner,
    db: DbSession,
    settings: RuntimeSettings,
) -> dict:
    connection = _google_connection(db, owner)
    credentials = VaultCredentials(
        SecretVault(db, owner.id, settings),
        str(connection.auth_ref),
    )
    request = MeetingRequest(
        title=payload.title,
        starts_at=_aware(payload.starts_at),
        duration_minutes=payload.duration_minutes or settings.meeting_default_minutes,
        guest_emails=tuple(payload.guest_emails),
        description=payload.description,
        timezone=owner.timezone,
        notify_guests=payload.notify_guests,
    )
    try:
        scheduled = MeetingScheduler(settings, credentials).schedule(request)
    except SchedulingDisabled as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except (ConnectorError, SecretVaultUnavailable) as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    written = _record(db, owner, connection, request, scheduled)
    db.commit()
    return {
        "meeting": scheduled.as_dict(),
        "interaction_id": written,
        "collabute": {"notetaker_attached": False, "reason": NOTETAKER_NOTE},
    }


def _google_connection(db: DbSession, owner: Owner) -> SourceConnection:
    connections = [
        item
        for item in SourceConnectionRepository(db, owner.id).all()
        if item.source == GOOGLE_SOURCE and item.auth_ref
    ]
    if not connections:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Connect Google before scheduling a meeting",
        )
    return connections[0]


def _record(
    db: DbSession,
    owner: Owner,
    connection: SourceConnection,
    request: MeetingRequest,
    scheduled: ScheduledMeeting,
) -> str | None:
    """Store the event we just created so the graph does not wait for the next sync.

    The external id is Google's event id, which is the same id the Calendar delta will carry,
    so the next sync updates this row instead of creating a second copy of the meeting.
    """

    if not scheduled.event_id:
        return None
    record = NormalizedRecord(
        external_id=scheduled.event_id,
        type="meeting",
        source=CALENDAR_SOURCE,
        occurred_at=request.starts_at,
        direction="outgoing",
        subject=request.title,
        body_text=request.description,
        participants=tuple(_participants(owner, request)),
        metadata={
            "meet_url": scheduled.meet_url,
            "conference_status": scheduled.conference_status,
            "html_link": scheduled.html_link,
            "end": scheduled.ends_at,
            "created_by": "career_brain_scheduler",
            "invites_sent": scheduled.invites_sent,
        },
        raw_ref=f"google_calendar://{connection.external_account_id}/{scheduled.event_id}",
    )
    writer = ConnectorGraphWriter(db, owner, connection)
    delta = writer.write([record])
    recompute_edges(db, owner.id, writer.self_person_id, delta.touched_person_ids)
    return delta.interaction_ids[0] if delta.interaction_ids else None


def _participants(owner: Owner, request: MeetingRequest) -> list[NormalizedParticipant]:
    organizer = NormalizedParticipant(
        source_address=owner.email.casefold(),
        role="organizer",
        display_name=owner.display_name,
        identity_hint={IdentityKind.EMAIL.value: owner.email},
    )
    guests = [
        NormalizedParticipant(
            source_address=email,
            role="attendee",
            identity_hint={IdentityKind.EMAIL.value: email},
        )
        for email in request.guest_emails
    ]
    return [organizer, *guests]


def _aware(value: datetime) -> datetime:
    """A naive start time is read as UTC rather than silently as server-local time."""

    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
