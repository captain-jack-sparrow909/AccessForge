"""Add fail-closed Phase 6 approval, export, and controlled-validation records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_phase6_controlled_export"
down_revision: str | None = "0005_phase5_risk_and_planning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "risk_assessment_contexts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("risk_assessment_id", sa.String(length=36), nullable=False),
        sa.Column("context_hash", sa.String(length=64), nullable=False),
        sa.Column("envelope_version", sa.String(length=40), nullable=False),
        sa.Column("encrypted_context", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["risk_assessment_id"], ["risk_assessments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("risk_assessment_id"),
    )
    op.create_index(
        "ix_risk_assessment_contexts_risk_assessment_id",
        "risk_assessment_contexts",
        ["risk_assessment_id"],
    )

    op.create_table(
        "export_validation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("risk_assessment_id", sa.String(length=36), nullable=False),
        sa.Column("design_spec_id", sa.String(length=36), nullable=False),
        sa.Column("validation_run_id", sa.String(length=36), nullable=False),
        sa.Column("boundary", sa.String(length=40), nullable=False),
        sa.Column("risk_input_hash", sa.String(length=64), nullable=False),
        sa.Column("risk_decision_hash", sa.String(length=64), nullable=False),
        sa.Column("validation_report_hash", sa.String(length=64), nullable=False),
        sa.Column("artifact_manifest", sa.JSON(), nullable=False),
        sa.Column("artifact_manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate_designs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["risk_assessment_id"], ["risk_assessments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["design_spec_id"], ["design_spec_revisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["validation_run_id"], ["candidate_validation_runs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "project_id",
        "candidate_id",
        "risk_assessment_id",
        "design_spec_id",
        "validation_run_id",
    ):
        op.create_index(f"ix_export_validation_runs_{column}", "export_validation_runs", [column])

    op.create_table(
        "approval_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("design_plan_id", sa.String(length=36), nullable=False),
        sa.Column("generation_batch_id", sa.String(length=36), nullable=False),
        sa.Column("requirements_revision_id", sa.String(length=36), nullable=False),
        sa.Column("risk_assessment_id", sa.String(length=36), nullable=False),
        sa.Column("design_spec_id", sa.String(length=36), nullable=False),
        sa.Column("export_validation_run_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("acknowledgement_version", sa.String(length=80), nullable=False),
        sa.Column("acknowledgements", sa.JSON(), nullable=False),
        sa.Column("risk_decision_hash", sa.String(length=64), nullable=False),
        sa.Column("design_spec_hash", sa.String(length=64), nullable=False),
        sa.Column("template_manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("validation_report_hash", sa.String(length=64), nullable=False),
        sa.Column("artifact_manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("approval_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("approved_by", sa.String(length=160), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidate_designs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["design_plan_id"], ["design_plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["generation_batch_id"], ["candidate_generation_batches.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["requirements_revision_id"], ["requirement_revisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["risk_assessment_id"], ["risk_assessments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["design_spec_id"], ["design_spec_revisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["export_validation_run_id"], ["export_validation_runs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "idempotency_key", name="uq_approval_events_project_idempotency"
        ),
    )
    for column in (
        "project_id",
        "candidate_id",
        "design_plan_id",
        "generation_batch_id",
        "requirements_revision_id",
        "risk_assessment_id",
        "design_spec_id",
        "export_validation_run_id",
    ):
        op.create_index(f"ix_approval_events_{column}", "approval_events", [column])

    op.create_table(
        "export_bundles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("approval_event_id", sa.String(length=36), nullable=False),
        sa.Column("export_validation_run_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidate_designs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["approval_event_id"], ["approval_events.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["export_validation_run_id"], ["export_validation_runs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
        sa.UniqueConstraint(
            "project_id", "idempotency_key", name="uq_export_bundles_project_idempotency"
        ),
    )
    for column in ("project_id", "candidate_id", "approval_event_id", "export_validation_run_id"):
        op.create_index(f"ix_export_bundles_{column}", "export_bundles", [column])

    op.create_table(
        "controlled_physical_validation_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=80), nullable=False),
        sa.Column("template_version", sa.String(length=40), nullable=False),
        sa.Column("template_manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("protocol_version", sa.String(length=80), nullable=False),
        sa.Column("record_type", sa.String(length=40), nullable=False),
        sa.Column("process_record", sa.JSON(), nullable=False),
        sa.Column("measured_dimensions", sa.JSON(), nullable=False),
        sa.Column("stop_criteria_observed", sa.JSON(), nullable=False),
        sa.Column("evidence_hashes", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("recorded_by", sa.String(length=160), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidate_designs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_controlled_physical_validation_records_project_id",
        "controlled_physical_validation_records",
        ["project_id"],
    )
    op.create_index(
        "ix_controlled_physical_validation_records_candidate_id",
        "controlled_physical_validation_records",
        ["candidate_id"],
    )

    op.create_table(
        "feedback_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=True),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("reported_by", sa.String(length=160), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidate_designs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedback_reports_project_id", "feedback_reports", ["project_id"])
    op.create_index("ix_feedback_reports_candidate_id", "feedback_reports", ["candidate_id"])

    op.create_table(
        "hazard_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("feedback_report_id", sa.String(length=36), nullable=True),
        sa.Column("template_id", sa.String(length=80), nullable=False),
        sa.Column("template_version", sa.String(length=40), nullable=False),
        sa.Column("template_manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("reported_by", sa.String(length=160), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidate_designs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["feedback_report_id"], ["feedback_reports.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("project_id", "candidate_id", "feedback_report_id"):
        op.create_index(f"ix_hazard_reports_{column}", "hazard_reports", [column])

    op.create_table(
        "template_release_controls",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=80), nullable=False),
        sa.Column("template_version", sa.String(length=40), nullable=False),
        sa.Column("template_manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("protocol_version", sa.String(length=80), nullable=True),
        sa.Column("evidence_hashes", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("control_hash", sa.String(length=64), nullable=False),
        sa.Column("recorded_by", sa.String(length=160), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_template_release_controls_template_id", "template_release_controls", ["template_id"])

    # SQLite needs a table rebuild to add this foreign key.  The durable
    # selected-candidate pointer makes later approval/export lineage explicit
    # without changing Phase 5 generation authorization semantics.
    with op.batch_alter_table("design_plans") as batch_op:
        batch_op.add_column(sa.Column("selected_candidate_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_design_plans_selected_candidate_id",
            "candidate_designs",
            ["selected_candidate_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_index(
        "ix_design_plans_selected_candidate_id", "design_plans", ["selected_candidate_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_design_plans_selected_candidate_id", table_name="design_plans")
    with op.batch_alter_table("design_plans") as batch_op:
        batch_op.drop_constraint("fk_design_plans_selected_candidate_id", type_="foreignkey")
        batch_op.drop_column("selected_candidate_id")

    op.drop_index("ix_template_release_controls_template_id", table_name="template_release_controls")
    op.drop_table("template_release_controls")

    for column in ("feedback_report_id", "candidate_id", "project_id"):
        op.drop_index(f"ix_hazard_reports_{column}", table_name="hazard_reports")
    op.drop_table("hazard_reports")

    op.drop_index("ix_feedback_reports_candidate_id", table_name="feedback_reports")
    op.drop_index("ix_feedback_reports_project_id", table_name="feedback_reports")
    op.drop_table("feedback_reports")

    op.drop_index(
        "ix_controlled_physical_validation_records_candidate_id",
        table_name="controlled_physical_validation_records",
    )
    op.drop_index(
        "ix_controlled_physical_validation_records_project_id",
        table_name="controlled_physical_validation_records",
    )
    op.drop_table("controlled_physical_validation_records")

    for column in ("export_validation_run_id", "approval_event_id", "candidate_id", "project_id"):
        op.drop_index(f"ix_export_bundles_{column}", table_name="export_bundles")
    op.drop_table("export_bundles")

    for column in (
        "export_validation_run_id",
        "design_spec_id",
        "risk_assessment_id",
        "requirements_revision_id",
        "generation_batch_id",
        "design_plan_id",
        "candidate_id",
        "project_id",
    ):
        op.drop_index(f"ix_approval_events_{column}", table_name="approval_events")
    op.drop_table("approval_events")

    for column in (
        "validation_run_id",
        "design_spec_id",
        "risk_assessment_id",
        "candidate_id",
        "project_id",
    ):
        op.drop_index(f"ix_export_validation_runs_{column}", table_name="export_validation_runs")
    op.drop_table("export_validation_runs")

    op.drop_index(
        "ix_risk_assessment_contexts_risk_assessment_id", table_name="risk_assessment_contexts"
    )
    op.drop_table("risk_assessment_contexts")
