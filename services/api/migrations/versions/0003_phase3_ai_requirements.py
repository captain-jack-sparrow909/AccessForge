"""Add provider, agent-run, and immutable requirements persistence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_phase3_ai_requirements"
down_revision: str | None = "0002_phase2_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_provider_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=160), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("provider_type", sa.String(length=80), nullable=False),
        sa.Column("credential_mode", sa.String(length=40), nullable=False),
        sa.Column("encrypted_credential", sa.Text(), nullable=True),
        sa.Column("credential_fingerprint", sa.String(length=80), nullable=True),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("fast_model", sa.String(length=160), nullable=True),
        sa.Column("reasoning_model", sa.String(length=160), nullable=True),
        sa.Column("vision_model", sa.String(length=160), nullable=True),
        sa.Column("embedding_model", sa.String(length=160), nullable=True),
        sa.Column("input_cost_per_million_usd", sa.Float(), nullable=True),
        sa.Column("output_cost_per_million_usd", sa.Float(), nullable=True),
        sa.Column("allowed_data_categories", sa.JSON(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=True),
        sa.Column("capabilities_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_provider_configs_owner_id", "model_provider_configs", ["owner_id"])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("provider_config_id", sa.String(length=36), nullable=True),
        sa.Column("workflow_type", sa.String(length=80), nullable=False),
        sa.Column("provider_type", sa.String(length=80), nullable=True),
        sa.Column("model_identifier", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("prompt_id", sa.String(length=160), nullable=False),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_category", sa.String(length=80), nullable=True),
        sa.Column("result_rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["provider_config_id"], ["model_provider_configs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_project_id", "agent_runs", ["project_id"])
    op.create_index("ix_agent_runs_provider_config_id", "agent_runs", ["provider_config_id"])

    op.create_table(
        "agent_steps",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("agent_run_id", sa.String(length=36), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("tool_name", sa.String(length=120), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_category", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_run_id", "step_number", name="uq_agent_steps_run_step"),
    )
    op.create_index("ix_agent_steps_agent_run_id", "agent_steps", ["agent_run_id"])

    op.create_table(
        "requirement_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("agent_run_id", sa.String(length=36), nullable=True),
        sa.Column("provider_config_id", sa.String(length=36), nullable=True),
        sa.Column("prompt_id", sa.String(length=160), nullable=True),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column("unknowns", sa.JSON(), nullable=True),
        sa.Column("clarifying_questions", sa.JSON(), nullable=True),
        sa.Column("risk_signals", sa.JSON(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.String(length=160), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["provider_config_id"], ["model_provider_configs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "revision_number", name="uq_requirement_revisions_project_number"
        ),
    )
    op.create_index("ix_requirement_revisions_project_id", "requirement_revisions", ["project_id"])
    op.create_index(
        "ix_requirement_revisions_agent_run_id", "requirement_revisions", ["agent_run_id"]
    )
    op.create_index(
        "ix_requirement_revisions_provider_config_id",
        "requirement_revisions",
        ["provider_config_id"],
    )

    op.create_table(
        "requirements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("revision_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=120), nullable=False),
        sa.Column("value_number", sa.Float(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("needs_confirmation", sa.Boolean(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revision_id"], ["requirement_revisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_requirements_project_id", "requirements", ["project_id"])
    op.create_index("ix_requirements_revision_id", "requirements", ["revision_id"])

    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("model_provider_config_id", sa.String(length=36), nullable=True))
        batch.add_column(
            sa.Column("active_requirement_revision_id", sa.String(length=36), nullable=True)
        )
        batch.create_foreign_key(
            "fk_projects_model_provider_config_id",
            "model_provider_configs",
            ["model_provider_config_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_projects_model_provider_config_id", ["model_provider_config_id"])
        batch.create_index(
            "ix_projects_active_requirement_revision_id", ["active_requirement_revision_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.drop_index("ix_projects_active_requirement_revision_id")
        batch.drop_index("ix_projects_model_provider_config_id")
        batch.drop_constraint("fk_projects_model_provider_config_id", type_="foreignkey")
        batch.drop_column("active_requirement_revision_id")
        batch.drop_column("model_provider_config_id")
    op.drop_index("ix_requirements_revision_id", table_name="requirements")
    op.drop_index("ix_requirements_project_id", table_name="requirements")
    op.drop_table("requirements")
    op.drop_index("ix_requirement_revisions_provider_config_id", table_name="requirement_revisions")
    op.drop_index("ix_requirement_revisions_agent_run_id", table_name="requirement_revisions")
    op.drop_index("ix_requirement_revisions_project_id", table_name="requirement_revisions")
    op.drop_table("requirement_revisions")
    op.drop_index("ix_agent_steps_agent_run_id", table_name="agent_steps")
    op.drop_table("agent_steps")
    op.drop_index("ix_agent_runs_provider_config_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_project_id", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_model_provider_configs_owner_id", table_name="model_provider_configs")
    op.drop_table("model_provider_configs")
