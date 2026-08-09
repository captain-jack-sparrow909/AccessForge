from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    projects: Mapped[list["Project"]] = relationship(back_populates="owner")


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment: Mapped[str | None] = mapped_column(Text, nullable=True)
    load_context: Mapped[str | None] = mapped_column(String(80), nullable=True)
    safety_system: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    age_context: Mapped[str | None] = mapped_column(String(80), nullable=True)
    scope_status: Mapped[str] = mapped_column(
        String(40), default="needs_confirmation", nullable=False
    )
    scope_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_provider_config_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_provider_configs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    active_requirement_revision_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    # This is a convenience pointer only.  The immutable RiskAssessment row and
    # its bound input hashes remain the source of truth for every gate.
    active_risk_assessment_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    owner: Mapped[User] = relationship(back_populates="projects")


class ProjectParticipant(Base):
    __tablename__ = "project_participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    relationship_to_user: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    participant_id: Mapped[str] = mapped_column(
        ForeignKey("project_participants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    consent_type: Mapped[str] = mapped_column(String(80), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    consent_version: Mapped[str] = mapped_column(String(40), default="0.1", nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    input_mode: Mapped[str] = mapped_column(String(40), default="text", nullable=False)
    source: Mapped[str] = mapped_column(String(40), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    canonical_value_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    tolerance: Mapped[float | None] = mapped_column(Float, nullable=True)
    canonical_tolerance_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    method: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(40), default="user", nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    unknown: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    object_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    media_type: Mapped[str] = mapped_column(String(40), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expected_size: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class DeletionJob(Base):
    __tablename__ = "deletion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)
    requested_by: Mapped[str] = mapped_column(String(160), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ModelProviderConfig(Base):
    __tablename__ = "model_provider_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(80), nullable=False)
    credential_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    encrypted_credential: Mapped[str | None] = mapped_column(Text, nullable=True)
    credential_fingerprint: Mapped[str | None] = mapped_column(String(80), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fast_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reasoning_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    vision_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    input_cost_per_million_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_cost_per_million_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    allowed_data_categories: Mapped[list[str]] = mapped_column(
        JSON, default=lambda: ["project_text", "measurements"], nullable=False
    )
    capabilities: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    capabilities_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="unverified", nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider_config_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_provider_configs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    workflow_type: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_identifier: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)
    prompt_id: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    result_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class RequirementRevision(Base):
    __tablename__ = "requirement_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    agent_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider_config_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_provider_configs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    prompt_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unknowns: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)
    clarifying_questions: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)
    risk_signals: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(160), nullable=True)


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    revision_id: Mapped[str] = mapped_column(
        ForeignKey("requirement_revisions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(120), nullable=False)
    value_number: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    needs_confirmation: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class DesignSpecRevision(Base):
    """An immutable canonical input to a fixed reviewed CAD template release."""

    __tablename__ = "design_spec_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    requirements_revision_id: Mapped[str] = mapped_column(
        ForeignKey("requirement_revisions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    parent_design_spec_id: Mapped[str | None] = mapped_column(
        ForeignKey("design_spec_revisions.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # Kept as a durable lineage ID rather than a database foreign key so a risk
    # decision can point back to its resulting immutable revision without a
    # circular migration dependency.
    risk_assessment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    template_id: Mapped[str] = mapped_column(String(80), nullable=False)
    template_version: Mapped[str] = mapped_column(String(40), nullable=False)
    template_manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_spec: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    spec_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_seed: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class CandidateDesign(Base):
    """A mutable job status around otherwise immutable candidate inputs and outputs."""

    __tablename__ = "candidate_designs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    design_spec_id: Mapped[str] = mapped_column(
        ForeignKey("design_spec_revisions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    risk_assessment_id: Mapped[str | None] = mapped_column(
        ForeignKey("risk_assessments.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    generation_batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("candidate_generation_batches.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    variant_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    variant_label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    candidate_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)
    template_id: Mapped[str] = mapped_column(String(80), nullable=False)
    template_version: Mapped[str] = mapped_column(String(40), nullable=False)
    template_manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    spec_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_seed: Mapped[str] = mapped_column(String(120), nullable=False)
    compiler_fingerprint: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    geometry_summary: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    validation_report: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    validation_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provenance_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class CadJob(Base):
    """Durable queue metadata; worker inputs are always database IDs only."""

    __tablename__ = "cad_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_designs.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[str] = mapped_column(String(160), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CandidateArtifact(Base):
    """Private immutable artifact metadata; object keys are never public API values."""

    __tablename__ = "candidate_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_designs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class RiskAssessment(Base):
    """Immutable result of a versioned deterministic risk evaluation."""

    __tablename__ = "risk_assessments"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "assessment_number", name="uq_risk_assessments_project_number"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    requirements_revision_id: Mapped[str] = mapped_column(
        ForeignKey("requirement_revisions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    design_spec_id: Mapped[str] = mapped_column(
        ForeignKey("design_spec_revisions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    resulting_design_spec_id: Mapped[str | None] = mapped_column(
        ForeignKey("design_spec_revisions.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    previous_assessment_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    assessment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    assessment_scope: Mapped[str] = mapped_column(String(40), nullable=False)
    project_version: Mapped[int] = mapped_column(Integer, nullable=False)
    ruleset_version: Mapped[str] = mapped_column(String(120), nullable=False)
    ruleset_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    tier: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="current", nullable=False)
    allowed_actions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    unresolved_questions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    user_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    decision_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class RiskFinding(Base):
    """Normalized deterministic evidence for an immutable risk assessment."""

    __tablename__ = "risk_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    risk_assessment_id: Mapped[str] = mapped_column(
        ForeignKey("risk_assessments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    rule_id: Mapped[str] = mapped_column(String(160), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(80), nullable=False)
    tier: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    remediation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class DesignPlan(Base):
    """A bounded, checkpointed plan of reviewed-template parameter variants."""

    __tablename__ = "design_plans"
    __table_args__ = (
        UniqueConstraint("project_id", "plan_number", name="uq_design_plans_project_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    risk_assessment_id: Mapped[str] = mapped_column(
        ForeignKey("risk_assessments.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    source_design_spec_id: Mapped[str] = mapped_column(
        ForeignKey("design_spec_revisions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    # This is assigned only after every child in a completed comparison batch is
    # terminal and the project owner chooses one successful candidate for the
    # next review step.  Keeping the selection on the immutable plan lineage
    # avoids deriving export authorization from mutable UI state.
    selected_candidate_id: Mapped[str | None] = mapped_column(
        ForeignKey("candidate_designs.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    agent_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    plan_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="waiting_for_user", nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    template_matches: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    critique_summary: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    user_checkpoint: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DesignPlanProposal(Base):
    """An immutable, server-validated parameter variant in a design plan."""

    __tablename__ = "design_plan_proposals"
    __table_args__ = (
        UniqueConstraint("plan_id", "proposal_number", name="uq_design_plan_proposals_plan_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("design_plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    design_spec_id: Mapped[str] = mapped_column(
        ForeignKey("design_spec_revisions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    proposal_number: Mapped[int] = mapped_column(Integer, nullable=False)
    variant_key: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    tradeoffs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    critique: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="proposed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class CandidateValidationRun(Base):
    """Immutable normalization of deterministic post-generation checks."""

    __tablename__ = "candidate_validation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_designs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    risk_assessment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    design_spec_id: Mapped[str] = mapped_column(
        ForeignKey("design_spec_revisions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    validator_version: Mapped[str] = mapped_column(String(120), nullable=False)
    validator_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    overall_status: Mapped[str] = mapped_column(String(40), nullable=False)
    report: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    report_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class CandidateGenerationBatch(Base):
    """Durable multi-variant queue coordination for a selected design plan."""

    __tablename__ = "candidate_generation_batches"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "idempotency_key",
            name="uq_candidate_generation_batches_project_idempotency",
        ),
        UniqueConstraint("design_plan_id", name="uq_candidate_generation_batches_design_plan"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    design_plan_id: Mapped[str] = mapped_column(
        ForeignKey("design_plans.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    risk_assessment_id: Mapped[str] = mapped_column(
        ForeignKey("risk_assessments.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)
    requested_by: Mapped[str] = mapped_column(String(160), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RiskAssessmentContext(Base):
    """Private sealed risk input retained only for deterministic export rechecks.

    The public immutable risk snapshot deliberately hashes free text.  Phase 6
    must nevertheless rerun the deterministic engine without trusting a browser
    resubmission, so this separate record stores an authenticated encrypted
    context and is never returned by an API response.
    """

    __tablename__ = "risk_assessment_contexts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    risk_assessment_id: Mapped[str] = mapped_column(
        ForeignKey("risk_assessments.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    envelope_version: Mapped[str] = mapped_column(String(40), nullable=False)
    encrypted_context: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ExportValidationRun(Base):
    """Immutable pre-approval or pre-export revalidation evidence.

    It is intentionally separate from the compiler's Phase 4/5 validation
    records: the original validation report remains historical evidence while
    this row records a fresh risk/lineage/artifact check at a specific boundary.
    """

    __tablename__ = "export_validation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_designs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    risk_assessment_id: Mapped[str] = mapped_column(
        ForeignKey("risk_assessments.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    design_spec_id: Mapped[str] = mapped_column(
        ForeignKey("design_spec_revisions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    validation_run_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_validation_runs.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    boundary: Mapped[str] = mapped_column(String(40), nullable=False)
    risk_input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_decision_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_report_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_manifest: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    artifact_manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ApprovalEvent(Base):
    """An immutable acknowledgement for one exact private export revision.

    This is deliberately not professional, safety, manufacture, or physical-use
    approval.  It merely binds a user acknowledgement to the exact lineage that
    the server would need before it can make a private export bundle available.
    """

    __tablename__ = "approval_events"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "idempotency_key", name="uq_approval_events_project_idempotency"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_designs.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    design_plan_id: Mapped[str] = mapped_column(
        ForeignKey("design_plans.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    generation_batch_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_generation_batches.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    requirements_revision_id: Mapped[str] = mapped_column(
        ForeignKey("requirement_revisions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    risk_assessment_id: Mapped[str] = mapped_column(
        ForeignKey("risk_assessments.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    design_spec_id: Mapped[str] = mapped_column(
        ForeignKey("design_spec_revisions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    export_validation_run_id: Mapped[str] = mapped_column(
        ForeignKey("export_validation_runs.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    acknowledgement_version: Mapped[str] = mapped_column(String(80), nullable=False)
    acknowledgements: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    risk_decision_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    design_spec_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    template_manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_report_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    approved_by: Mapped[str] = mapped_column(String(160), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExportBundle(Base):
    """Private immutable ZIP metadata; object keys remain server-only."""

    __tablename__ = "export_bundles"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "idempotency_key", name="uq_export_bundles_project_idempotency"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_designs.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    approval_event_id: Mapped[str] = mapped_column(
        ForeignKey("approval_events.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    export_validation_run_id: Mapped[str] = mapped_column(
        ForeignKey("export_validation_runs.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="ready", nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    manifest: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ControlledPhysicalValidationRecord(Base):
    """Reviewer-recorded, non-human fixture or coupon evidence.

    The row preserves measurements and stop criteria without elevating them to a
    safety, fit, durability, or participant-use conclusion.
    """

    __tablename__ = "controlled_physical_validation_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_designs.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    template_id: Mapped[str] = mapped_column(String(80), nullable=False)
    template_version: Mapped[str] = mapped_column(String(40), nullable=False)
    template_manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    protocol_version: Mapped[str] = mapped_column(String(80), nullable=False)
    record_type: Mapped[str] = mapped_column(String(40), nullable=False)
    process_record: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    measured_dimensions: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    stop_criteria_observed: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    evidence_hashes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(160), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class FeedbackReport(Base):
    """Private typed feedback about a candidate; it never becomes a safety conclusion."""

    __tablename__ = "feedback_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    candidate_id: Mapped[str | None] = mapped_column(
        ForeignKey("candidate_designs.id", ondelete="SET NULL"), index=True, nullable=True
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    reported_by: Mapped[str] = mapped_column(String(160), nullable=False)
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class HazardReport(Base):
    """A local hazard block that must be reviewed before any further export attempt."""

    __tablename__ = "hazard_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_designs.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    feedback_report_id: Mapped[str | None] = mapped_column(
        ForeignKey("feedback_reports.id", ondelete="SET NULL"), index=True, nullable=True
    )
    template_id: Mapped[str] = mapped_column(String(80), nullable=False)
    template_version: Mapped[str] = mapped_column(String(40), nullable=False)
    template_manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="reported", nullable=False)
    reported_by: Mapped[str] = mapped_column(String(160), nullable=False)
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class TemplateReleaseControl(Base):
    """Immutable safety-review control for a specific repository release.

    A control can authorize *controlled, non-human validation only* or quarantine
    a release.  It never makes a release safe, approved for manufacture, or
    suitable for participant use.
    """

    __tablename__ = "template_release_controls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    template_id: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    template_version: Mapped[str] = mapped_column(String(40), nullable=False)
    template_manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    protocol_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    evidence_hashes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    control_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(160), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
