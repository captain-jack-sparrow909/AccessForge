"""Add bounded retry and lease metadata for private deletion cleanup."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_phase7_deletion_recovery"
down_revision: str | None = "0006_phase6_controlled_export"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Keep the legacy column for schema compatibility only. Its historical
    # free-form values are removed below; new code records bounded opaque codes.
    with op.batch_alter_table("deletion_jobs") as batch_op:
        batch_op.add_column(
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0"))
        )
        batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_error_code", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column(
                "reconciliation_passes",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.add_column(
            sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True)
        )
    op.create_index(
        "ix_deletion_jobs_status_next_attempt_at",
        "deletion_jobs",
        ["status", "next_attempt_at"],
    )
    op.create_index(
        "ix_deletion_jobs_status_started_at",
        "deletion_jobs",
        ["status", "started_at"],
    )
    # Prior releases could persist raw provider error text. It is neither a
    # reliable recovery signal nor safe long-term status data, so remove it
    # from every legacy row before applying conservative status transitions.
    op.execute("UPDATE deletion_jobs SET error = NULL WHERE error IS NOT NULL")
    # Failed and in-flight pre-Phase-7 rows lack a trustworthy retry/lease
    # record. Surface them conservatively for manual review instead of silently
    # retrying uncertain cleanup with an old raw provider error.
    op.execute(
        """
        UPDATE deletion_jobs
        SET status = 'manual_review_required',
            started_at = NULL,
            next_attempt_at = NULL,
            last_error_code = 'legacy_failure_requires_review',
            last_error_at = requested_at,
            completed_at = COALESCE(completed_at, requested_at),
            error = NULL
        WHERE status = 'failed'
        """
    )
    op.execute(
        """
        UPDATE deletion_jobs
        SET status = 'manual_review_required',
            started_at = NULL,
            next_attempt_at = NULL,
            last_error_code = 'legacy_running_requires_review',
            last_error_at = requested_at,
            completed_at = COALESCE(completed_at, requested_at),
            error = NULL
        WHERE status = 'running'
        """
    )
    # Older source could insert more than one deletion row for a project.
    # Retain those audit records but keep only the newest active cleanup row;
    # a partial unique index below prevents a future concurrent duplicate.
    op.execute(
        """
        WITH ranked_active_jobs AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY project_id
                       ORDER BY requested_at DESC, id DESC
                   ) AS duplicate_rank
            FROM deletion_jobs
            WHERE status IN ('queued', 'manual_review_required')
        )
        UPDATE deletion_jobs
        SET status = 'superseded',
            started_at = NULL,
            next_attempt_at = NULL,
            last_error_code = 'duplicate_deletion_job_superseded',
            last_error_at = requested_at,
            completed_at = COALESCE(completed_at, requested_at),
            error = NULL
        WHERE id IN (
            SELECT id FROM ranked_active_jobs WHERE duplicate_rank > 1
        )
        """
    )
    active_statuses = sa.text("status IN ('queued', 'running', 'manual_review_required')")
    op.create_index(
        "uq_deletion_jobs_active_project_id",
        "deletion_jobs",
        ["project_id"],
        unique=True,
        postgresql_where=active_statuses,
        sqlite_where=active_statuses,
    )


def downgrade() -> None:
    op.drop_index("uq_deletion_jobs_active_project_id", table_name="deletion_jobs")
    op.drop_index("ix_deletion_jobs_status_started_at", table_name="deletion_jobs")
    op.drop_index("ix_deletion_jobs_status_next_attempt_at", table_name="deletion_jobs")
    with op.batch_alter_table("deletion_jobs") as batch_op:
        batch_op.drop_column("last_reconciled_at")
        batch_op.drop_column("reconciliation_passes")
        batch_op.drop_column("last_error_at")
        batch_op.drop_column("last_error_code")
        batch_op.drop_column("next_attempt_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("attempt_count")
