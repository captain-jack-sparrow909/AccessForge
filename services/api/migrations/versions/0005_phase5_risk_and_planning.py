"""Add deterministic risk, bounded planning, validation, and batch lineage."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_phase5_risk_and_planning"
down_revision: str | None = "0004_phase4_cad_candidates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects", sa.Column("active_risk_assessment_id", sa.String(length=36), nullable=True)
    )
    op.create_index(
        "ix_projects_active_risk_assessment_id", "projects", ["active_risk_assessment_id"]
    )

    with op.batch_alter_table("design_spec_revisions") as batch_op:
        batch_op.add_column(sa.Column("parent_design_spec_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("risk_assessment_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_design_spec_revisions_parent_design_spec_id",
            "design_spec_revisions",
            ["parent_design_spec_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_index(
        "ix_design_spec_revisions_parent_design_spec_id",
        "design_spec_revisions",
        ["parent_design_spec_id"],
    )
    op.create_index(
        "ix_design_spec_revisions_risk_assessment_id",
        "design_spec_revisions",
        ["risk_assessment_id"],
    )

    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("requirements_revision_id", sa.String(length=36), nullable=False),
        sa.Column("design_spec_id", sa.String(length=36), nullable=False),
        sa.Column("resulting_design_spec_id", sa.String(length=36), nullable=True),
        sa.Column("previous_assessment_id", sa.String(length=36), nullable=True),
        sa.Column("assessment_number", sa.Integer(), nullable=False),
        sa.Column("assessment_scope", sa.String(length=40), nullable=False),
        sa.Column("project_version", sa.Integer(), nullable=False),
        sa.Column("ruleset_version", sa.String(length=120), nullable=False),
        sa.Column("ruleset_hash", sa.String(length=64), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("tier", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("allowed_actions", sa.JSON(), nullable=False),
        sa.Column("unresolved_questions", sa.JSON(), nullable=False),
        sa.Column("user_explanation", sa.Text(), nullable=False),
        sa.Column("decision_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["requirements_revision_id"], ["requirement_revisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["design_spec_id"], ["design_spec_revisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["resulting_design_spec_id"], ["design_spec_revisions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "assessment_number", name="uq_risk_assessments_project_number"
        ),
    )
    op.create_index("ix_risk_assessments_project_id", "risk_assessments", ["project_id"])
    op.create_index(
        "ix_risk_assessments_requirements_revision_id",
        "risk_assessments",
        ["requirements_revision_id"],
    )
    op.create_index("ix_risk_assessments_design_spec_id", "risk_assessments", ["design_spec_id"])
    op.create_index(
        "ix_risk_assessments_resulting_design_spec_id",
        "risk_assessments",
        ["resulting_design_spec_id"],
    )
    op.create_index(
        "ix_risk_assessments_previous_assessment_id",
        "risk_assessments",
        ["previous_assessment_id"],
    )

    op.create_table(
        "risk_findings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("risk_assessment_id", sa.String(length=36), nullable=False),
        sa.Column("rule_id", sa.String(length=160), nullable=False),
        sa.Column("rule_version", sa.String(length=80), nullable=False),
        sa.Column("tier", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["risk_assessment_id"], ["risk_assessments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risk_findings_risk_assessment_id", "risk_findings", ["risk_assessment_id"])

    op.create_table(
        "design_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("risk_assessment_id", sa.String(length=36), nullable=False),
        sa.Column("source_design_spec_id", sa.String(length=36), nullable=False),
        sa.Column("agent_run_id", sa.String(length=36), nullable=True),
        sa.Column("plan_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("template_matches", sa.JSON(), nullable=False),
        sa.Column("critique_summary", sa.JSON(), nullable=False),
        sa.Column("user_checkpoint", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["risk_assessment_id"], ["risk_assessments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_design_spec_id"], ["design_spec_revisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "plan_number", name="uq_design_plans_project_number"),
    )
    op.create_index("ix_design_plans_project_id", "design_plans", ["project_id"])
    op.create_index("ix_design_plans_risk_assessment_id", "design_plans", ["risk_assessment_id"])
    op.create_index(
        "ix_design_plans_source_design_spec_id", "design_plans", ["source_design_spec_id"]
    )
    op.create_index("ix_design_plans_agent_run_id", "design_plans", ["agent_run_id"])

    op.create_table(
        "design_plan_proposals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("design_spec_id", sa.String(length=36), nullable=False),
        sa.Column("proposal_number", sa.Integer(), nullable=False),
        sa.Column("variant_key", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("tradeoffs", sa.JSON(), nullable=False),
        sa.Column("critique", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["design_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["design_spec_id"], ["design_spec_revisions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "plan_id", "proposal_number", name="uq_design_plan_proposals_plan_number"
        ),
    )
    op.create_index("ix_design_plan_proposals_plan_id", "design_plan_proposals", ["plan_id"])
    op.create_index(
        "ix_design_plan_proposals_design_spec_id",
        "design_plan_proposals",
        ["design_spec_id"],
    )

    op.create_table(
        "candidate_validation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("risk_assessment_id", sa.String(length=36), nullable=True),
        sa.Column("design_spec_id", sa.String(length=36), nullable=False),
        sa.Column("validator_version", sa.String(length=120), nullable=False),
        sa.Column("validator_hash", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("overall_status", sa.String(length=40), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("report_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate_designs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["design_spec_id"], ["design_spec_revisions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_candidate_validation_runs_project_id", "candidate_validation_runs", ["project_id"]
    )
    op.create_index(
        "ix_candidate_validation_runs_candidate_id", "candidate_validation_runs", ["candidate_id"]
    )
    op.create_index(
        "ix_candidate_validation_runs_risk_assessment_id",
        "candidate_validation_runs",
        ["risk_assessment_id"],
    )
    op.create_index(
        "ix_candidate_validation_runs_design_spec_id",
        "candidate_validation_runs",
        ["design_spec_id"],
    )

    op.create_table(
        "candidate_generation_batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("design_plan_id", sa.String(length=36), nullable=False),
        sa.Column("risk_assessment_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["design_plan_id"], ["design_plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["risk_assessment_id"], ["risk_assessments.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "idempotency_key",
            name="uq_candidate_generation_batches_project_idempotency",
        ),
        sa.UniqueConstraint("design_plan_id", name="uq_candidate_generation_batches_design_plan"),
    )
    op.create_index(
        "ix_candidate_generation_batches_project_id", "candidate_generation_batches", ["project_id"]
    )
    op.create_index(
        "ix_candidate_generation_batches_design_plan_id",
        "candidate_generation_batches",
        ["design_plan_id"],
    )
    op.create_index(
        "ix_candidate_generation_batches_risk_assessment_id",
        "candidate_generation_batches",
        ["risk_assessment_id"],
    )

    # SQLite cannot add foreign-key constraints with ALTER TABLE. Batch mode
    # safely rebuilds this still-unreleased table shape on SQLite while using
    # normal ALTER semantics on production-capable dialects.
    with op.batch_alter_table("candidate_designs") as batch_op:
        batch_op.add_column(sa.Column("risk_assessment_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("generation_batch_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("variant_key", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("variant_label", sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column("validation_status", sa.String(length=40), nullable=True))
        batch_op.create_foreign_key(
            "fk_candidate_designs_risk_assessment_id",
            "risk_assessments",
            ["risk_assessment_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_candidate_designs_generation_batch_id",
            "candidate_generation_batches",
            ["generation_batch_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_index(
        "ix_candidate_designs_risk_assessment_id", "candidate_designs", ["risk_assessment_id"]
    )
    op.create_index(
        "ix_candidate_designs_generation_batch_id", "candidate_designs", ["generation_batch_id"]
    )

    op.add_column(
        "cad_jobs", sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("cad_jobs", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("cad_jobs", "cancelled_at")
    op.drop_column("cad_jobs", "cancel_requested_at")
    op.drop_index("ix_candidate_designs_generation_batch_id", table_name="candidate_designs")
    op.drop_index("ix_candidate_designs_risk_assessment_id", table_name="candidate_designs")
    with op.batch_alter_table("candidate_designs") as batch_op:
        batch_op.drop_constraint("fk_candidate_designs_generation_batch_id", type_="foreignkey")
        batch_op.drop_constraint("fk_candidate_designs_risk_assessment_id", type_="foreignkey")
        batch_op.drop_column("validation_status")
        batch_op.drop_column("variant_label")
        batch_op.drop_column("variant_key")
        batch_op.drop_column("generation_batch_id")
        batch_op.drop_column("risk_assessment_id")

    op.drop_index(
        "ix_candidate_generation_batches_risk_assessment_id",
        table_name="candidate_generation_batches",
    )
    op.drop_index(
        "ix_candidate_generation_batches_design_plan_id", table_name="candidate_generation_batches"
    )
    op.drop_index(
        "ix_candidate_generation_batches_project_id", table_name="candidate_generation_batches"
    )
    op.drop_table("candidate_generation_batches")

    op.drop_index(
        "ix_candidate_validation_runs_design_spec_id", table_name="candidate_validation_runs"
    )
    op.drop_index(
        "ix_candidate_validation_runs_risk_assessment_id", table_name="candidate_validation_runs"
    )
    op.drop_index(
        "ix_candidate_validation_runs_candidate_id", table_name="candidate_validation_runs"
    )
    op.drop_index("ix_candidate_validation_runs_project_id", table_name="candidate_validation_runs")
    op.drop_table("candidate_validation_runs")

    op.drop_index("ix_design_plan_proposals_design_spec_id", table_name="design_plan_proposals")
    op.drop_index("ix_design_plan_proposals_plan_id", table_name="design_plan_proposals")
    op.drop_table("design_plan_proposals")

    op.drop_index("ix_design_plans_agent_run_id", table_name="design_plans")
    op.drop_index("ix_design_plans_source_design_spec_id", table_name="design_plans")
    op.drop_index("ix_design_plans_risk_assessment_id", table_name="design_plans")
    op.drop_index("ix_design_plans_project_id", table_name="design_plans")
    op.drop_table("design_plans")

    op.drop_index("ix_risk_findings_risk_assessment_id", table_name="risk_findings")
    op.drop_table("risk_findings")

    op.drop_index("ix_risk_assessments_previous_assessment_id", table_name="risk_assessments")
    op.drop_index("ix_risk_assessments_resulting_design_spec_id", table_name="risk_assessments")
    op.drop_index("ix_risk_assessments_design_spec_id", table_name="risk_assessments")
    op.drop_index("ix_risk_assessments_requirements_revision_id", table_name="risk_assessments")
    op.drop_index("ix_risk_assessments_project_id", table_name="risk_assessments")
    op.drop_table("risk_assessments")

    op.drop_index("ix_design_spec_revisions_risk_assessment_id", table_name="design_spec_revisions")
    op.drop_index(
        "ix_design_spec_revisions_parent_design_spec_id", table_name="design_spec_revisions"
    )
    with op.batch_alter_table("design_spec_revisions") as batch_op:
        batch_op.drop_constraint(
            "fk_design_spec_revisions_parent_design_spec_id", type_="foreignkey"
        )
        batch_op.drop_column("risk_assessment_id")
        batch_op.drop_column("parent_design_spec_id")

    op.drop_index("ix_projects_active_risk_assessment_id", table_name="projects")
    op.drop_column("projects", "active_risk_assessment_id")
