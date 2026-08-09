"""Add immutable DesignSpecs, CAD jobs, private candidates, and artifact metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_phase4_cad_candidates"
down_revision: str | None = "0003_phase3_ai_requirements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "design_spec_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("requirements_revision_id", sa.String(length=36), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=20), nullable=False),
        sa.Column("template_id", sa.String(length=80), nullable=False),
        sa.Column("template_version", sa.String(length=40), nullable=False),
        sa.Column("template_manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("canonical_spec", sa.JSON(), nullable=False),
        sa.Column("spec_hash", sa.String(length=64), nullable=False),
        sa.Column("generation_seed", sa.String(length=120), nullable=False),
        sa.Column("created_by", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["requirements_revision_id"], ["requirement_revisions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "revision_number", name="uq_design_spec_revisions_project_number"
        ),
    )
    op.create_index("ix_design_spec_revisions_project_id", "design_spec_revisions", ["project_id"])
    op.create_index(
        "ix_design_spec_revisions_requirements_revision_id",
        "design_spec_revisions",
        ["requirements_revision_id"],
    )

    op.create_table(
        "candidate_designs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("design_spec_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("template_id", sa.String(length=80), nullable=False),
        sa.Column("template_version", sa.String(length=40), nullable=False),
        sa.Column("template_manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("spec_hash", sa.String(length=64), nullable=False),
        sa.Column("generation_seed", sa.String(length=120), nullable=False),
        sa.Column("compiler_fingerprint", sa.JSON(), nullable=True),
        sa.Column("geometry_summary", sa.JSON(), nullable=True),
        sa.Column("validation_report", sa.JSON(), nullable=True),
        sa.Column("provenance_hash", sa.String(length=64), nullable=True),
        sa.Column("failure_category", sa.String(length=80), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["design_spec_id"], ["design_spec_revisions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "candidate_number", name="uq_candidate_designs_project_number"
        ),
    )
    op.create_index("ix_candidate_designs_project_id", "candidate_designs", ["project_id"])
    op.create_index("ix_candidate_designs_design_spec_id", "candidate_designs", ["design_spec_id"])

    op.create_table(
        "cad_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("failure_category", sa.String(length=80), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate_designs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", name="uq_cad_jobs_candidate"),
        sa.UniqueConstraint(
            "project_id", "idempotency_key", name="uq_cad_jobs_project_idempotency"
        ),
    )
    op.create_index("ix_cad_jobs_project_id", "cad_jobs", ["project_id"])
    op.create_index("ix_cad_jobs_candidate_id", "cad_jobs", ["candidate_id"])

    op.create_table(
        "candidate_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate_designs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
        sa.UniqueConstraint("candidate_id", "kind", name="uq_candidate_artifacts_candidate_kind"),
    )
    op.create_index("ix_candidate_artifacts_project_id", "candidate_artifacts", ["project_id"])
    op.create_index("ix_candidate_artifacts_candidate_id", "candidate_artifacts", ["candidate_id"])


def downgrade() -> None:
    op.drop_index("ix_candidate_artifacts_candidate_id", table_name="candidate_artifacts")
    op.drop_index("ix_candidate_artifacts_project_id", table_name="candidate_artifacts")
    op.drop_table("candidate_artifacts")
    op.drop_index("ix_cad_jobs_candidate_id", table_name="cad_jobs")
    op.drop_index("ix_cad_jobs_project_id", table_name="cad_jobs")
    op.drop_table("cad_jobs")
    op.drop_index("ix_candidate_designs_design_spec_id", table_name="candidate_designs")
    op.drop_index("ix_candidate_designs_project_id", table_name="candidate_designs")
    op.drop_table("candidate_designs")
    op.drop_index(
        "ix_design_spec_revisions_requirements_revision_id", table_name="design_spec_revisions"
    )
    op.drop_index("ix_design_spec_revisions_project_id", table_name="design_spec_revisions")
    op.drop_table("design_spec_revisions")
