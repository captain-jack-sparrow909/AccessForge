"""Add consent, capture, measurement, asset, and deletion workflow tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_phase2_workflow"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("goal", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("object_description", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("action_description", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("environment", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("load_context", sa.String(length=80), nullable=True))
    op.add_column("projects", sa.Column("safety_system", sa.Boolean(), nullable=True))
    op.add_column("projects", sa.Column("age_context", sa.String(length=80), nullable=True))
    op.add_column(
        "projects",
        sa.Column(
            "scope_status",
            sa.String(length=40),
            nullable=False,
            server_default="needs_confirmation",
        ),
    )
    op.add_column("projects", sa.Column("scope_reason", sa.Text(), nullable=True))
    op.add_column(
        "projects", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )

    op.create_table(
        "project_participants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("relationship_to_user", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_participants_project_id", "project_participants", ["project_id"])

    op.create_table(
        "consent_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("participant_id", sa.String(length=36), nullable=False),
        sa.Column("consent_type", sa.String(length=80), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("consent_version", sa.String(length=40), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["participant_id"], ["project_participants.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consent_records_project_id", "consent_records", ["project_id"])
    op.create_index("ix_consent_records_participant_id", "consent_records", ["participant_id"])

    op.create_table(
        "observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("input_mode", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_observations_project_id", "observations", ["project_id"])

    op.create_table(
        "measurements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("canonical_value_mm", sa.Float(), nullable=True),
        sa.Column("tolerance", sa.Float(), nullable=True),
        sa.Column("canonical_tolerance_mm", sa.Float(), nullable=True),
        sa.Column("method", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("unknown", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_measurements_project_id", "measurements", ["project_id"])

    op.create_table(
        "media_assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("media_type", sa.String(length=40), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=True),
        sa.Column("expected_size", sa.Integer(), nullable=False),
        sa.Column("actual_size", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index("ix_media_assets_project_id", "media_assets", ["project_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=160), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("from_state", sa.String(length=40), nullable=True),
        sa.Column("to_state", sa.String(length=40), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_project_id", "audit_events", ["project_id"])

    op.create_table(
        "deletion_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deletion_jobs_project_id", "deletion_jobs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_deletion_jobs_project_id", table_name="deletion_jobs")
    op.drop_table("deletion_jobs")
    op.drop_index("ix_audit_events_project_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_media_assets_project_id", table_name="media_assets")
    op.drop_table("media_assets")
    op.drop_index("ix_measurements_project_id", table_name="measurements")
    op.drop_table("measurements")
    op.drop_index("ix_observations_project_id", table_name="observations")
    op.drop_table("observations")
    op.drop_index("ix_consent_records_participant_id", table_name="consent_records")
    op.drop_index("ix_consent_records_project_id", table_name="consent_records")
    op.drop_table("consent_records")
    op.drop_index("ix_project_participants_project_id", table_name="project_participants")
    op.drop_table("project_participants")
    op.drop_column("projects", "version")
    op.drop_column("projects", "scope_reason")
    op.drop_column("projects", "scope_status")
    op.drop_column("projects", "age_context")
    op.drop_column("projects", "safety_system")
    op.drop_column("projects", "load_context")
    op.drop_column("projects", "environment")
    op.drop_column("projects", "action_description")
    op.drop_column("projects", "object_description")
    op.drop_column("projects", "goal")
