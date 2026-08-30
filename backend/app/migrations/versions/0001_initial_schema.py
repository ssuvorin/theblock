"""Initial schema, derived from and kept identical to app/models.py.

Alembic is the only thing that creates tables, so this revision must stay byte-for-byte
equivalent to the declarative metadata. ``alembic check`` is the guard: it fails the build when
``app/models.py`` moves without a matching revision.

Revision ID: 0001_initial
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORIGIN_CHECK = "data_origin IN ('synthetic','real_import','live_connector')"
TABLES_IN_DEPENDENCY_ORDER = (
    "context_credit_budget",
    "owner",
    "organization",
    "person",
    "person_identity",
    "relationship",
    "interaction_event",
    "interaction_participant",
    "opportunity",
    "opportunity_evidence",
    "opportunity_person_path",
    "follow_up",
    "semantic_index_outbox",
    "context_credit_usage",
)


def _tz() -> sa.DateTime:
    return sa.DateTime(timezone=True)


def _owned_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
    ]


def _owner_constraints() -> list[sa.schema.SchemaItem]:
    return [
        sa.ForeignKeyConstraint(["owner_id"], ["owner.id"]),
        sa.PrimaryKeyConstraint("id"),
    ]


def upgrade() -> None:
    _create_owner()
    _create_organization()
    _create_person()
    _create_person_identity()
    _create_relationship()
    _create_interaction_event()
    _create_interaction_participant()
    _create_opportunity()
    _create_opportunity_evidence()
    _create_opportunity_person_path()
    _create_follow_up()
    _create_semantic_index_outbox()
    _create_credit_ledger()


def downgrade() -> None:
    for table in reversed(TABLES_IN_DEPENDENCY_ORDER):
        op.drop_table(table)


def _create_owner() -> None:
    op.create_table(
        "owner",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("current_goal", sa.Text(), nullable=True),
        sa.Column("self_person_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", _tz(), nullable=False),
        sa.Column("updated_at", _tz(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_owner_email", "owner", ["email"], unique=True)


def _create_organization() -> None:
    op.create_table(
        "organization",
        *_owned_columns(),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(length=200), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("socials", sa.JSON(), nullable=False),
        sa.Column("address", sa.JSON(), nullable=False),
        sa.Column("enrichment_provider", sa.String(length=80), nullable=True),
        sa.Column("enriched_at", _tz(), nullable=True),
        sa.Column("created_at", _tz(), nullable=False),
        sa.Column("updated_at", _tz(), nullable=False),
        *_owner_constraints(),
        sa.UniqueConstraint("owner_id", "domain"),
    )
    op.create_index("ix_organization_domain", "organization", ["domain"], unique=False)
    op.create_index("ix_organization_owner_id", "organization", ["owner_id"], unique=False)


def _create_person() -> None:
    op.create_table(
        "person",
        *_owned_columns(),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("photo_url", sa.Text(), nullable=True),
        sa.Column("current_title", sa.String(length=255), nullable=True),
        sa.Column("current_org_id", sa.String(length=36), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("manual_overrides", sa.JSON(), nullable=False),
        sa.Column("data_origin", sa.String(length=30), nullable=False),
        sa.Column("created_at", _tz(), nullable=False),
        sa.Column("updated_at", _tz(), nullable=False),
        sa.CheckConstraint(ORIGIN_CHECK, name="ck_person_origin"),
        sa.ForeignKeyConstraint(["current_org_id"], ["organization.id"]),
        *_owner_constraints(),
    )
    op.create_index("ix_person_data_origin", "person", ["data_origin"], unique=False)
    op.create_index("ix_person_display_name", "person", ["display_name"], unique=False)
    op.create_index("ix_person_owner_id", "person", ["owner_id"], unique=False)


def _create_person_identity() -> None:
    op.create_table(
        "person_identity",
        *_owned_columns(),
        sa.Column("person_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("created_at", _tz(), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        *_owner_constraints(),
        sa.UniqueConstraint("owner_id", "kind", "normalized_value"),
    )
    op.create_index("ix_person_identity_owner_id", "person_identity", ["owner_id"], unique=False)
    op.create_index("ix_person_identity_person_id", "person_identity", ["person_id"], unique=False)


def _create_relationship() -> None:
    op.create_table(
        "relationship",
        *_owned_columns(),
        sa.Column("person_a_id", sa.String(length=36), nullable=False),
        sa.Column("person_b_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("strength_score", sa.Float(), nullable=False),
        sa.Column("strength_components", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("last_interaction_at", _tz(), nullable=True),
        sa.Column("total_interactions", sa.Integer(), nullable=False),
        sa.Column("introduced_by", sa.String(length=36), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", _tz(), nullable=False),
        sa.Column("updated_at", _tz(), nullable=False),
        sa.ForeignKeyConstraint(["introduced_by"], ["person.id"]),
        sa.ForeignKeyConstraint(["person_a_id"], ["person.id"]),
        sa.ForeignKeyConstraint(["person_b_id"], ["person.id"]),
        *_owner_constraints(),
        sa.UniqueConstraint("owner_id", "person_a_id", "person_b_id"),
    )
    op.create_index("ix_relationship_owner_id", "relationship", ["owner_id"], unique=False)
    op.create_index("ix_relationship_person_b_id", "relationship", ["person_b_id"], unique=False)


def _create_interaction_event() -> None:
    op.create_table(
        "interaction_event",
        *_owned_columns(),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=True),
        sa.Column("occurred_at", _tz(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("raw_ref", sa.Text(), nullable=True),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("data_origin", sa.String(length=30), nullable=False),
        sa.Column("created_at", _tz(), nullable=False),
        sa.CheckConstraint(ORIGIN_CHECK, name="ck_interaction_origin"),
        *_owner_constraints(),
        sa.UniqueConstraint("owner_id", "source", "external_id"),
    )
    table = "interaction_event"
    op.create_index("ix_interaction_event_data_origin", table, ["data_origin"], unique=False)
    op.create_index("ix_interaction_event_is_deleted", table, ["is_deleted"], unique=False)
    op.create_index("ix_interaction_event_occurred_at", table, ["occurred_at"], unique=False)
    op.create_index("ix_interaction_event_owner_id", table, ["owner_id"], unique=False)
    op.create_index("ix_interaction_event_source", table, ["source"], unique=False)


def _create_interaction_participant() -> None:
    op.create_table(
        "interaction_participant",
        *_owned_columns(),
        sa.Column("interaction_id", sa.String(length=36), nullable=False),
        sa.Column("person_id", sa.String(length=36), nullable=True),
        sa.Column("source_address", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["interaction_id"], ["interaction_event.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        *_owner_constraints(),
        sa.UniqueConstraint("interaction_id", "source_address", "role"),
    )
    table = "interaction_participant"
    op.create_index(f"ix_{table}_interaction_id", table, ["interaction_id"], unique=False)
    op.create_index(f"ix_{table}_owner_id", table, ["owner_id"], unique=False)
    op.create_index(f"ix_{table}_person_id", table, ["person_id"], unique=False)


def _create_opportunity() -> None:
    op.create_table(
        "opportunity",
        *_owned_columns(),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("source_domain", sa.String(length=255), nullable=False),
        sa.Column("role_title", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("verification_status", sa.String(length=30), nullable=False),
        sa.Column("checked_at", _tz(), nullable=False),
        sa.Column("published_at", _tz(), nullable=True),
        sa.Column("saved_at", _tz(), nullable=True),
        sa.Column("dismissed_at", _tz(), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("provider_disclosure", sa.Text(), nullable=True),
        sa.Column("created_at", _tz(), nullable=False),
        sa.Column("updated_at", _tz(), nullable=False),
        sa.CheckConstraint(
            "verification_status IN ('verified_open_role','hiring_signal','unverified','stale')",
            name="ck_opportunity_verification",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        *_owner_constraints(),
        sa.UniqueConstraint("owner_id", "canonical_url"),
    )
    op.create_index(
        "idx_opportunity_owner_status",
        "opportunity",
        ["owner_id", "verification_status", "checked_at"],
        unique=False,
    )
    op.create_index("ix_opportunity_owner_id", "opportunity", ["owner_id"], unique=False)


def _create_opportunity_evidence() -> None:
    op.create_table(
        "opportunity_evidence",
        *_owned_columns(),
        sa.Column("opportunity_id", sa.String(length=36), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("source_domain", sa.String(length=255), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("evidence_type", sa.String(length=30), nullable=False),
        sa.Column("checked_at", _tz(), nullable=False),
        sa.Column("verification_details", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunity.id"]),
        *_owner_constraints(),
        sa.UniqueConstraint("opportunity_id", "url", "content_hash"),
    )
    table = "opportunity_evidence"
    op.create_index(f"ix_{table}_opportunity_id", table, ["opportunity_id"], unique=False)
    op.create_index(f"ix_{table}_owner_id", table, ["owner_id"], unique=False)


def _create_opportunity_person_path() -> None:
    op.create_table(
        "opportunity_person_path",
        *_owned_columns(),
        sa.Column("opportunity_id", sa.String(length=36), nullable=False),
        sa.Column("person_id", sa.String(length=36), nullable=False),
        sa.Column("relationship_id", sa.String(length=36), nullable=True),
        sa.Column("private_evidence_id", sa.String(length=36), nullable=True),
        sa.Column("path_type", sa.String(length=30), nullable=False),
        sa.Column("path_score", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunity.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.ForeignKeyConstraint(["private_evidence_id"], ["interaction_event.id"]),
        sa.ForeignKeyConstraint(["relationship_id"], ["relationship.id"]),
        *_owner_constraints(),
        sa.UniqueConstraint("opportunity_id", "person_id", "path_type"),
    )
    table = "opportunity_person_path"
    op.create_index(f"ix_{table}_opportunity_id", table, ["opportunity_id"], unique=False)
    op.create_index(f"ix_{table}_owner_id", table, ["owner_id"], unique=False)


def _create_follow_up() -> None:
    op.create_table(
        "follow_up",
        *_owned_columns(),
        sa.Column("person_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("due_timezone", sa.String(length=80), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_key", sa.String(length=255), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", _tz(), nullable=False),
        sa.Column("updated_at", _tz(), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        *_owner_constraints(),
        sa.UniqueConstraint("owner_id", "source", "source_key"),
    )
    op.create_index("ix_follow_up_owner_id", "follow_up", ["owner_id"], unique=False)
    op.create_index("ix_follow_up_person_id", "follow_up", ["person_id"], unique=False)


def _create_semantic_index_outbox() -> None:
    op.create_table(
        "semantic_index_outbox",
        *_owned_columns(),
        sa.Column("interaction_id", sa.String(length=36), nullable=False),
        sa.Column("embedding_version", sa.String(length=20), nullable=False),
        sa.Column("op", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("chunks_written", sa.Integer(), nullable=True),
        sa.Column("created_at", _tz(), nullable=False),
        sa.Column("processed_at", _tz(), nullable=True),
        sa.CheckConstraint("op IN ('upsert','tombstone')", name="ck_outbox_op"),
        sa.CheckConstraint(
            "status IN ('pending','processing','done','failed')",
            name="ck_outbox_status",
        ),
        sa.ForeignKeyConstraint(["interaction_id"], ["interaction_event.id"]),
        *_owner_constraints(),
        sa.UniqueConstraint("owner_id", "interaction_id", "embedding_version", "op"),
    )
    table = "semantic_index_outbox"
    op.create_index("idx_outbox_claim", table, ["status", "created_at"], unique=False)
    op.create_index(f"ix_{table}_interaction_id", table, ["interaction_id"], unique=False)
    op.create_index(f"ix_{table}_owner_id", table, ["owner_id"], unique=False)
    op.create_index(f"ix_{table}_status", table, ["status"], unique=False)


def _create_credit_ledger() -> None:
    op.create_table(
        "context_credit_budget",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("total_cap", sa.Integer(), nullable=False),
        sa.Column("brand_cap", sa.Integer(), nullable=False),
        sa.Column("market_search_cap", sa.Integer(), nullable=False),
        sa.Column("reserve_floor", sa.Integer(), nullable=False),
        sa.Column("credits_used", sa.Integer(), nullable=False),
        sa.Column("brand_credits_used", sa.Integer(), nullable=False),
        sa.Column("search_credits_used", sa.Integer(), nullable=False),
        sa.Column("updated_at", _tz(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "context_credit_usage",
        *_owned_columns(),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("request_key", sa.String(length=128), nullable=False),
        sa.Column("credits_reserved", sa.Integer(), nullable=False),
        sa.Column("credits_consumed", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", _tz(), nullable=False),
        sa.Column("reconciled_at", _tz(), nullable=True),
        sa.CheckConstraint("category IN ('brand','market_search')", name="ck_credit_category"),
        *_owner_constraints(),
        sa.UniqueConstraint("category", "request_key"),
    )
    op.create_index(
        "ix_context_credit_usage_owner_id", "context_credit_usage", ["owner_id"], unique=False
    )
