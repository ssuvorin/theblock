"""PostgreSQL-canonical demo schema.

Revision ID: 0001_demo_schema
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_demo_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=False)
JSONB = postgresql.JSONB(astext_type=sa.Text())
TZ = sa.DateTime(timezone=True)


def owned_columns() -> list[sa.Column]:
    return [
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", UUID, sa.ForeignKey("owner.id"), nullable=False),
    ]


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    _create_owner()
    _create_people_graph()
    _create_interactions()
    _create_opportunities()
    _create_followups_and_credits()
    op.create_foreign_key("fk_owner_self_person", "owner", "person", ["self_person_id"], ["id"])


def _create_owner() -> None:
    op.create_table(
        "owner",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("timezone", sa.Text(), nullable=False, server_default="UTC"),
        sa.Column("location", sa.Text()),
        sa.Column("current_goal", sa.Text()),
        sa.Column("self_person_id", UUID),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
    )


def _create_people_graph() -> None:
    op.create_table(
        "organization",
        *owned_columns(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("industry", sa.Text()),
        sa.Column("logo_url", sa.Text()),
        sa.Column("socials", JSONB, nullable=False, server_default="{}"),
        sa.Column("address", JSONB, nullable=False, server_default="{}"),
        sa.Column("enrichment_provider", sa.Text()),
        sa.Column("enriched_at", TZ),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("owner_id", "domain"),
    )
    op.create_table(
        "person",
        *owned_columns(),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("photo_url", sa.Text()),
        sa.Column("current_title", sa.Text()),
        sa.Column("current_org_id", UUID, sa.ForeignKey("organization.id")),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("manual_overrides", JSONB, nullable=False, server_default="{}"),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "data_origin IN ('synthetic','real_import','live_connector')",
            name="ck_person_origin",
        ),
    )
    op.create_table(
        "person_identity",
        *owned_columns(),
        sa.Column("person_id", UUID, sa.ForeignKey("person.id"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("owner_id", "kind", "normalized_value"),
    )
    op.create_table(
        "relationship",
        *owned_columns(),
        sa.Column("person_a_id", UUID, sa.ForeignKey("person.id"), nullable=False),
        sa.Column("person_b_id", UUID, sa.ForeignKey("person.id"), nullable=False),
        sa.Column("type", sa.Text(), nullable=False, server_default="contact"),
        sa.Column("strength_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("strength_components", JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("last_interaction_at", TZ),
        sa.Column("total_interactions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("introduced_by", UUID, sa.ForeignKey("person.id")),
        sa.Column("evidence", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("owner_id", "person_a_id", "person_b_id"),
    )


def _create_interactions() -> None:
    op.create_table(
        "interaction_event",
        *owned_columns(),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text()),
        sa.Column("occurred_at", TZ, nullable=False),
        sa.Column("subject", sa.Text()),
        sa.Column("body_text", sa.Text()),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("raw_ref", sa.Text()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("owner_id", "source", "external_id"),
        sa.CheckConstraint(
            "data_origin IN ('synthetic','real_import','live_connector')",
            name="ck_interaction_origin",
        ),
    )
    op.create_table(
        "interaction_participant",
        *owned_columns(),
        sa.Column("interaction_id", UUID, sa.ForeignKey("interaction_event.id"), nullable=False),
        sa.Column("person_id", UUID, sa.ForeignKey("person.id")),
        sa.Column("source_address", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.UniqueConstraint("interaction_id", "source_address", "role"),
    )


def _create_opportunities() -> None:
    op.create_table(
        "opportunity",
        *owned_columns(),
        sa.Column("organization_id", UUID, sa.ForeignKey("organization.id")),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("source_domain", sa.Text(), nullable=False),
        sa.Column("role_title", sa.Text()),
        sa.Column("location", sa.Text()),
        sa.Column("summary", sa.Text()),
        sa.Column("verification_status", sa.Text(), nullable=False),
        sa.Column("checked_at", TZ, nullable=False),
        sa.Column("published_at", TZ),
        sa.Column("saved_at", TZ),
        sa.Column("dismissed_at", TZ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_disclosure", sa.Text()),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("owner_id", "canonical_url"),
        sa.CheckConstraint(
            "verification_status IN ('verified_open_role','hiring_signal','unverified','stale')",
            name="ck_opportunity_verification",
        ),
    )
    op.create_index(
        "idx_opportunity_owner_status",
        "opportunity",
        ["owner_id", "verification_status", sa.text("checked_at DESC")],
    )
    op.create_table(
        "opportunity_evidence",
        *owned_columns(),
        sa.Column("opportunity_id", UUID, sa.ForeignKey("opportunity.id"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("excerpt", sa.Text()),
        sa.Column("source_domain", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("evidence_type", sa.Text(), nullable=False),
        sa.Column("checked_at", TZ, nullable=False),
        sa.Column("verification_details", JSONB, nullable=False, server_default="{}"),
        sa.UniqueConstraint("opportunity_id", "url", "content_hash"),
    )
    op.create_table(
        "opportunity_person_path",
        *owned_columns(),
        sa.Column("opportunity_id", UUID, sa.ForeignKey("opportunity.id"), nullable=False),
        sa.Column("person_id", UUID, sa.ForeignKey("person.id"), nullable=False),
        sa.Column("relationship_id", UUID, sa.ForeignKey("relationship.id")),
        sa.Column("private_evidence_id", UUID, sa.ForeignKey("interaction_event.id")),
        sa.Column("path_type", sa.Text(), nullable=False),
        sa.Column("path_score", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=False),
        sa.UniqueConstraint("opportunity_id", "person_id", "path_type"),
    )


def _create_followups_and_credits() -> None:
    op.create_table(
        "follow_up",
        *owned_columns(),
        sa.Column("person_id", UUID, sa.ForeignKey("person.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("due_timezone", sa.Text()),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_key", sa.Text()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("owner_id", "source", "source_key"),
    )
    op.create_table(
        "context_credit_budget",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("total_cap", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("brand_cap", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("market_search_cap", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("reserve_floor", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("credits_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("brand_credits_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("search_credits_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("id = 1", name="ck_context_budget_singleton"),
    )
    op.execute("INSERT INTO context_credit_budget (id) VALUES (1) ON CONFLICT DO NOTHING")
    op.create_table(
        "context_credit_usage",
        *owned_columns(),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("request_key", sa.Text(), nullable=False),
        sa.Column("credits_reserved", sa.Integer(), nullable=False),
        sa.Column("credits_consumed", sa.Integer()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("reconciled_at", TZ),
        sa.UniqueConstraint("category", "request_key"),
        sa.CheckConstraint("category IN ('brand','market_search')", name="ck_credit_category"),
    )


def downgrade() -> None:
    op.drop_constraint("fk_owner_self_person", "owner", type_="foreignkey")
    for table in (
        "context_credit_usage",
        "context_credit_budget",
        "follow_up",
        "opportunity_person_path",
        "opportunity_evidence",
        "opportunity",
        "interaction_participant",
        "interaction_event",
        "relationship",
        "person_identity",
        "person",
        "organization",
        "owner",
    ):
        op.drop_table(table)
