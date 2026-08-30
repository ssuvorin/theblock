import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Owner(Base):
    __tablename__ = "owner"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    display_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(80), default="UTC")
    location: Mapped[str | None] = mapped_column(String(200))
    current_goal: Mapped[str | None] = mapped_column(Text)
    self_person_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Organization(Base):
    __tablename__ = "organization"
    __table_args__ = (UniqueConstraint("owner_id", "domain"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owner.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(200))
    logo_url: Mapped[str | None] = mapped_column(Text)
    socials: Mapped[dict] = mapped_column(JSON, default=dict)
    address: Mapped[dict] = mapped_column(JSON, default=dict)
    enrichment_provider: Mapped[str | None] = mapped_column(String(80))
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Person(Base):
    __tablename__ = "person"
    __table_args__ = (
        CheckConstraint(
            "data_origin IN ('synthetic','real_import','live_connector')",
            name="ck_person_origin",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owner.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(200), index=True)
    photo_url: Mapped[str | None] = mapped_column(Text)
    current_title: Mapped[str | None] = mapped_column(String(255))
    current_org_id: Mapped[str | None] = mapped_column(ForeignKey("organization.id"))
    tags: Mapped[list] = mapped_column(JSON, default=list)
    manual_overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    data_origin: Mapped[str] = mapped_column(String(30), default="live_connector", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PersonIdentity(Base):
    __tablename__ = "person_identity"
    __table_args__ = (UniqueConstraint("owner_id", "kind", "normalized_value"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owner.id"), index=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    raw_value: Mapped[str] = mapped_column(Text)
    normalized_value: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Relationship(Base):
    __tablename__ = "relationship"
    __table_args__ = (UniqueConstraint("owner_id", "person_a_id", "person_b_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owner.id"), index=True)
    person_a_id: Mapped[str] = mapped_column(ForeignKey("person.id"))
    person_b_id: Mapped[str] = mapped_column(ForeignKey("person.id"), index=True)
    type: Mapped[str] = mapped_column(String(50), default="contact")
    strength_score: Mapped[float] = mapped_column(Float, default=0.0)
    strength_components: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="active")
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_interactions: Mapped[int] = mapped_column(Integer, default=0)
    introduced_by: Mapped[str | None] = mapped_column(ForeignKey("person.id"))
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InteractionEvent(Base):
    __tablename__ = "interaction_event"
    __table_args__ = (
        UniqueConstraint("owner_id", "source", "external_id"),
        CheckConstraint(
            "data_origin IN ('synthetic','real_import','live_connector')",
            name="ck_interaction_origin",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owner.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(50), index=True)
    direction: Mapped[str | None] = mapped_column(String(20))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    subject: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    raw_ref: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    data_origin: Mapped[str] = mapped_column(String(30), default="live_connector", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InteractionParticipant(Base):
    __tablename__ = "interaction_participant"
    __table_args__ = (UniqueConstraint("interaction_id", "source_address", "role"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owner.id"), index=True)
    interaction_id: Mapped[str] = mapped_column(ForeignKey("interaction_event.id"), index=True)
    person_id: Mapped[str | None] = mapped_column(ForeignKey("person.id"), index=True)
    source_address: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30))


class Opportunity(Base):
    __tablename__ = "opportunity"
    __table_args__ = (
        UniqueConstraint("owner_id", "canonical_url"),
        CheckConstraint(
            "verification_status IN ('verified_open_role','hiring_signal','unverified','stale')",
            name="ck_opportunity_verification",
        ),
        Index("idx_opportunity_owner_status", "owner_id", "verification_status", "checked_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owner.id"), index=True)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organization.id"))
    canonical_url: Mapped[str] = mapped_column(Text)
    source_domain: Mapped[str] = mapped_column(String(255))
    role_title: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(30), default="unverified")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str] = mapped_column(String(80))
    provider_disclosure: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OpportunityEvidence(Base):
    __tablename__ = "opportunity_evidence"
    __table_args__ = (UniqueConstraint("opportunity_id", "url", "content_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owner.id"), index=True)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunity.id"), index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(Text)
    source_domain: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(80))
    evidence_type: Mapped[str] = mapped_column(String(30))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verification_details: Mapped[dict] = mapped_column(JSON, default=dict)


class OpportunityPersonPath(Base):
    __tablename__ = "opportunity_person_path"
    __table_args__ = (UniqueConstraint("opportunity_id", "person_id", "path_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owner.id"), index=True)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunity.id"), index=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"))
    relationship_id: Mapped[str | None] = mapped_column(ForeignKey("relationship.id"))
    private_evidence_id: Mapped[str | None] = mapped_column(ForeignKey("interaction_event.id"))
    path_type: Mapped[str] = mapped_column(String(30))
    path_score: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text)
    suggested_action: Mapped[str] = mapped_column(Text)


class FollowUp(Base):
    __tablename__ = "follow_up"
    __table_args__ = (UniqueConstraint("owner_id", "source", "source_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owner.id"), index=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date)
    due_timezone: Mapped[str | None] = mapped_column(String(80))
    source: Mapped[str] = mapped_column(String(50), default="manual")
    source_key: Mapped[str | None] = mapped_column(String(255))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ContextCreditBudget(Base):
    __tablename__ = "context_credit_budget"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    total_cap: Mapped[int] = mapped_column(Integer, default=500)
    brand_cap: Mapped[int] = mapped_column(Integer, default=200)
    market_search_cap: Mapped[int] = mapped_column(Integer, default=100)
    reserve_floor: Mapped[int] = mapped_column(Integer, default=200)
    credits_used: Mapped[int] = mapped_column(Integer, default=0)
    brand_credits_used: Mapped[int] = mapped_column(Integer, default=0)
    search_credits_used: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ContextCreditUsage(Base):
    __tablename__ = "context_credit_usage"
    __table_args__ = (
        UniqueConstraint("category", "request_key"),
        CheckConstraint("category IN ('brand','market_search')", name="ck_credit_category"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owner.id"), index=True)
    category: Mapped[str] = mapped_column(String(30))
    request_key: Mapped[str] = mapped_column(String(128))
    credits_reserved: Mapped[int] = mapped_column(Integer)
    credits_consumed: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="reserved")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
