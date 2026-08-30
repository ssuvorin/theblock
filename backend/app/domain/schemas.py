from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    email: str
    password: str


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class OpportunityPatch(BaseModel):
    saved: bool | None = None
    dismissed: bool | None = None


class DraftRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=1000)
    opportunity_id: str
    action: str = "reconnect"
    channel: str = "generic"


class FollowUpCreate(BaseModel):
    person_id: str
    reason: str = Field(min_length=1, max_length=2000)
    due_date: date | None = None
    due_timezone: str | None = None
    priority: int = Field(default=0, ge=-100, le=100)
    source_key: str | None = None


class FollowUpPatch(BaseModel):
    status: str | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=2000)
    due_date: date | None = None
    due_timezone: str | None = None
    priority: int | None = Field(default=None, ge=-100, le=100)

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str | None) -> str | None:
        if value is not None and value not in {"pending", "done", "skipped"}:
            raise ValueError("status must be pending, done, or skipped")
        return value


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
