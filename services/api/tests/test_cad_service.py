"""Durable private-artifact behavior for the Phase 4 CAD worker."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from accessforge.cad import service as cad_service
from accessforge.cad.compiler import CompilationResult, compile_design_spec
from accessforge.cad.registry import get_template_release
from accessforge.cad.schemas import (
    DesignSpec,
    FieldProvenance,
    ManufacturingProfile,
    canonical_length_from_entry,
)
from accessforge.cad.service import process_cad_candidate
from accessforge.db.models import (
    Base,
    CadJob,
    CandidateArtifact,
    CandidateDesign,
    CandidateGenerationBatch,
    CandidateValidationRun,
    DesignPlan,
    DesignPlanProposal,
    DesignSpecRevision,
    Project,
    RequirementRevision,
    RiskAssessment,
    User,
)
from accessforge.planning.service import cancel_comparison_batch
from accessforge.risk.service import RiskGateError, phase6_export_preflight
from accessforge.validation.service import validation_limitations


def worker_fixture_spec() -> DesignSpec:
    template_id = "pull_tab_extender"
    release = get_template_release(template_id, "1.0.0")
    fixture = json.loads(
        (release.release_path / "preview-fixture.json").read_text(encoding="utf-8")
    )
    fixture_parameters = fixture["parameters"]
    assert isinstance(fixture_parameters, dict)
    parameters = {
        name: canonical_length_from_entry(value, "mm") for name, value in fixture_parameters.items()
    }
    provenance_names = {
        "schema_version",
        "project_id",
        "requirements_revision_id",
        "template_id",
        "template_version",
        "template_manifest_sha256",
        "manufacturing",
        "manufacturing.nozzle_diameter",
        "manufacturing.layer_height",
        "fit_clearance",
        "dimensional_tolerance",
        "uses_assessed",
        "uses_not_assessed",
        "risk_tier",
        "risk_rule_set_version",
        "confirmed_assumptions",
        "unresolved_assumptions",
        "generation_seed",
        *(f"parameters.{name}" for name in parameters),
    }
    provenance = {
        name: FieldProvenance(
            creator_type="reviewer",
            source_ref="fixture:cad-worker",
            rationale="Synthetic worker fixture only.",
        )
        for name in provenance_names
    }
    return DesignSpec(
        project_id="00000000-0000-0000-0000-000000000001",
        requirements_revision_id="00000000-0000-0000-0000-000000000002",
        template_id=template_id,
        template_version="1.0.0",
        template_manifest_sha256=release.manifest_sha256,
        parameters=parameters,
        manufacturing=ManufacturingProfile(
            process="fdm",
            material_profile="pla_provisional",
            nozzle_diameter=canonical_length_from_entry(0.4, "mm"),
            layer_height=canonical_length_from_entry(0.2, "mm"),
        ),
        fit_clearance=canonical_length_from_entry(0.4, "mm"),
        dimensional_tolerance=canonical_length_from_entry(0.15, "mm"),
        uses_assessed=("Synthetic worker test only.",),
        uses_not_assessed=("Physical use is not assessed.",),
        risk_tier="R1",
        risk_rule_set_version="fixture-risk-rules.v1",
        confirmed_assumptions=("Synthetic fixture only.",),
        unresolved_assumptions=(),
        generation_seed=str(fixture["generation_seed"]),
        field_provenance=provenance,
    )


async def create_worker_fixture(
    tmp_path: Path,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession], str, CompilationResult]:
    database_path = tmp_path / "cad-worker.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    spec = worker_fixture_spec()
    result = compile_design_spec(spec, tmp_path / "compiled")
    candidate_id = "00000000-0000-0000-0000-000000000004"
    risk_assessment_id = "00000000-0000-0000-0000-000000000006"
    async with factory() as session:
        session.add(User(id="phase4-worker-owner", email="worker@example.test"))
        project = Project(
            id=spec.project_id,
            owner_id="phase4-worker-owner",
            name="Synthetic CAD worker fixture",
            scope_status="supported",
            scope_reason="Synthetic test only.",
            active_requirement_revision_id=spec.requirements_revision_id,
            active_risk_assessment_id=risk_assessment_id,
            status="generating",
        )
        requirements = RequirementRevision(
            id=spec.requirements_revision_id,
            project_id=project.id,
            revision_number=1,
            source="synthetic_fixture",
            status="confirmed",
            content_hash="a" * 64,
            created_by="phase4-worker-owner",
        )
        design_spec = DesignSpecRevision(
            id="00000000-0000-0000-0000-000000000003",
            project_id=project.id,
            requirements_revision_id=requirements.id,
            revision_number=1,
            schema_version=spec.schema_version,
            template_id=spec.template_id,
            template_version=spec.template_version,
            template_manifest_sha256=spec.template_manifest_sha256,
            canonical_spec=spec.canonical_payload(),
            spec_hash=spec.content_hash,
            generation_seed=spec.generation_seed,
            created_by="phase4-worker-owner",
            risk_assessment_id=risk_assessment_id,
        )
        assessment = RiskAssessment(
            id=risk_assessment_id,
            project_id=project.id,
            requirements_revision_id=requirements.id,
            design_spec_id=design_spec.id,
            resulting_design_spec_id=design_spec.id,
            assessment_number=1,
            assessment_scope="synthetic_fixture",
            project_version=1,
            ruleset_version=spec.risk_rule_set_version,
            ruleset_hash="b" * 64,
            input_snapshot={"fixture": "cad-worker"},
            input_hash="c" * 64,
            tier="R1",
            status="current",
            allowed_actions=["generate_candidate"],
            unresolved_questions=[],
            user_explanation="Synthetic R1 fixture for worker-lineage coverage only.",
            decision_hash="d" * 64,
            created_by="phase4-worker-owner",
        )
        candidate = CandidateDesign(
            id=candidate_id,
            project_id=project.id,
            design_spec_id=design_spec.id,
            risk_assessment_id=risk_assessment_id,
            candidate_number=1,
            template_id=spec.template_id,
            template_version=spec.template_version,
            template_manifest_sha256=spec.template_manifest_sha256,
            spec_hash=spec.content_hash,
            generation_seed=spec.generation_seed,
        )
        job = CadJob(
            id="00000000-0000-0000-0000-000000000005",
            project_id=project.id,
            candidate_id=candidate.id,
            idempotency_key="synthetic-worker-job",
            input_hash=spec.content_hash,
            requested_by="phase4-worker-owner",
        )
        session.add_all([project, requirements, design_spec, assessment, candidate, job])
        await session.commit()
    return engine, factory, candidate_id, result


async def create_comparison_worker_fixture(
    tmp_path: Path,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession], tuple[str, str], str, CompilationResult]:
    """Extend the valid R1 worker fixture with a two-candidate private comparison."""

    engine, factory, first_candidate_id, result = await create_worker_fixture(tmp_path)
    batch_id = "00000000-0000-0000-0000-000000000007"
    plan_id = "00000000-0000-0000-0000-000000000008"
    second_spec_id = "00000000-0000-0000-0000-000000000009"
    second_candidate_id = "00000000-0000-0000-0000-000000000010"
    async with factory() as session:
        first_candidate = await session.get(CandidateDesign, first_candidate_id)
        assert first_candidate is not None
        project = await session.get(Project, first_candidate.project_id)
        assert project is not None
        source_spec = await session.get(DesignSpecRevision, first_candidate.design_spec_id)
        assert source_spec is not None
        assessment = await session.get(RiskAssessment, first_candidate.risk_assessment_id)
        assert assessment is not None
        second_spec = DesignSpecRevision(
            id=second_spec_id,
            project_id=project.id,
            requirements_revision_id=source_spec.requirements_revision_id,
            parent_design_spec_id=source_spec.id,
            risk_assessment_id=assessment.id,
            revision_number=2,
            schema_version=source_spec.schema_version,
            template_id=source_spec.template_id,
            template_version=source_spec.template_version,
            template_manifest_sha256=source_spec.template_manifest_sha256,
            canonical_spec=source_spec.canonical_spec,
            spec_hash=source_spec.spec_hash,
            generation_seed=source_spec.generation_seed,
            created_by="phase5-worker-owner",
        )
        plan = DesignPlan(
            id=plan_id,
            project_id=project.id,
            risk_assessment_id=assessment.id,
            source_design_spec_id=source_spec.id,
            plan_number=1,
            status="comparison_queued",
            input_hash="e" * 64,
            template_matches=[],
            critique_summary={"unassessed_properties": ["Synthetic test only."]},
            user_checkpoint="Synthetic comparison checkpoint.",
            created_by="phase5-worker-owner",
        )
        batch = CandidateGenerationBatch(
            id=batch_id,
            project_id=project.id,
            design_plan_id=plan.id,
            risk_assessment_id=assessment.id,
            idempotency_key="synthetic-comparison",
            input_hash="f" * 64,
            status="queued",
            requested_by="phase5-worker-owner",
        )
        first_candidate.generation_batch_id = batch.id
        first_candidate.variant_key = "baseline"
        first_candidate.variant_label = "Baseline geometry"
        second_candidate = CandidateDesign(
            id=second_candidate_id,
            project_id=project.id,
            design_spec_id=second_spec.id,
            risk_assessment_id=assessment.id,
            generation_batch_id=batch.id,
            variant_key="generous",
            variant_label="Generous geometry",
            candidate_number=2,
            template_id=source_spec.template_id,
            template_version=source_spec.template_version,
            template_manifest_sha256=source_spec.template_manifest_sha256,
            spec_hash=source_spec.spec_hash,
            generation_seed=source_spec.generation_seed,
        )
        second_job = CadJob(
            id="00000000-0000-0000-0000-000000000011",
            project_id=project.id,
            candidate_id=second_candidate.id,
            idempotency_key="synthetic-comparison-second",
            input_hash=second_candidate.spec_hash,
            requested_by="phase5-worker-owner",
        )
        session.add_all(
            [
                second_spec,
                plan,
                batch,
                second_candidate,
                second_job,
                DesignPlanProposal(
                    id="00000000-0000-0000-0000-000000000012",
                    plan_id=plan.id,
                    design_spec_id=source_spec.id,
                    proposal_number=1,
                    variant_key="baseline",
                    label="Baseline geometry",
                    rationale="Synthetic worker comparison fixture.",
                    tradeoffs=[],
                    critique={},
                    status="comparison_queued",
                ),
                DesignPlanProposal(
                    id="00000000-0000-0000-0000-000000000013",
                    plan_id=plan.id,
                    design_spec_id=second_spec.id,
                    proposal_number=2,
                    variant_key="generous",
                    label="Generous geometry",
                    rationale="Synthetic worker comparison fixture.",
                    tradeoffs=[],
                    critique={},
                    status="comparison_queued",
                ),
            ]
        )
        await session.commit()
    return engine, factory, (first_candidate_id, second_candidate_id), plan_id, result


@pytest.mark.asyncio
async def test_worker_persists_only_fixed_private_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, factory, candidate_id, result = await create_worker_fixture(tmp_path)
    stored: dict[str, bytes] = {}

    def put_private_bytes(*, object_key: str, content: bytes, content_type: str) -> None:
        assert content_type
        stored[object_key] = content

    monkeypatch.setattr("accessforge.cad.service.run_isolated_compilation", lambda _: result)
    monkeypatch.setattr("accessforge.cad.service.put_private_bytes", put_private_bytes)
    try:
        async with factory() as session:
            assert await process_cad_candidate(session, candidate_id) == "succeeded"
            candidate = await session.get(CandidateDesign, candidate_id)
            assert candidate is not None
            assert candidate.status == "succeeded"
            assert candidate.validation_status == "needs_confirmation"
            assert candidate.validation_report is not None
            assert validation_limitations(candidate.validation_report) == [
                "Minimum wall thickness has not been assessed by this Phase 4 compiler report.",
                "Print orientation and unsupported-overhang behavior have not been assessed.",
            ]
            assert (
                candidate.provenance_hash == result.artifact_metadata["provenance_json"]["sha256"]
            )
            project = await session.get(Project, candidate.project_id)
            assert project is not None
            assert project.status == "candidates_ready"
            job = await session.scalar(select(CadJob).where(CadJob.candidate_id == candidate.id))
            assert job is not None
            assert job.status == "succeeded"
            validation = await session.scalar(
                select(CandidateValidationRun).where(
                    CandidateValidationRun.candidate_id == candidate.id
                )
            )
            assert validation is not None
            assert validation.overall_status == "needs_confirmation"
            eligible, reasons = await phase6_export_preflight(
                session,
                project=project,
                candidate=candidate,
            )
            assert not eligible
            assert any("Phase 6 approval" in reason for reason in reasons)
            assert any("failed, unassessed" in reason for reason in reasons)
            artifacts = list(
                (
                    await session.scalars(
                        select(CandidateArtifact).where(
                            CandidateArtifact.candidate_id == candidate.id
                        )
                    )
                ).all()
            )
            assert {artifact.kind for artifact in artifacts} == set(result.artifacts)
            assert len(stored) == len(result.artifacts)
            for artifact in artifacts:
                assert artifact.object_key.startswith(
                    f"private/{candidate.project_id}/candidates/{candidate.id}/"
                )
                assert artifact.filename in {
                    "design.step",
                    "design.stl",
                    "preview.glb",
                    "design-spec.json",
                    "validation-report.json",
                    "README.txt",
                    "provenance.json",
                }
                assert (
                    hashlib.sha256(stored[artifact.object_key]).hexdigest()
                    == artifact.checksum_sha256
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_worker_delivery_does_not_persist_a_second_artifact_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """At-least-once broker delivery is fenced by the durable candidate/job claim."""

    engine, factory, candidate_id, result = await create_worker_fixture(tmp_path)
    stored: dict[str, bytes] = {}
    compilation_count = 0

    def compile_once(_: DesignSpec) -> CompilationResult:
        nonlocal compilation_count
        compilation_count += 1
        return result

    def put_private_bytes(*, object_key: str, content: bytes, content_type: str) -> None:
        assert content_type
        stored[object_key] = content

    monkeypatch.setattr("accessforge.cad.service.run_isolated_compilation", compile_once)
    monkeypatch.setattr("accessforge.cad.service.put_private_bytes", put_private_bytes)
    try:
        async with factory() as first_session:
            assert await process_cad_candidate(first_session, candidate_id) == "succeeded"
        async with factory() as duplicate_session:
            assert (
                await process_cad_candidate(duplicate_session, candidate_id) == "already_processed"
            )
            candidate = await duplicate_session.get(CandidateDesign, candidate_id)
            job = await duplicate_session.scalar(
                select(CadJob).where(CadJob.candidate_id == candidate_id)
            )
            artifacts = list(
                (
                    await duplicate_session.scalars(
                        select(CandidateArtifact).where(
                            CandidateArtifact.candidate_id == candidate_id
                        )
                    )
                ).all()
            )
            assert candidate is not None and candidate.status == "succeeded"
            assert job is not None and job.status == "succeeded"
            assert job.attempt_count == 1
            assert len(artifacts) == len(result.artifacts)
        assert compilation_count == 1
        assert len(stored) == len(result.artifacts)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_rechecks_risk_before_artifact_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stale server gate must fail closed after compilation and before uploads."""

    engine, factory, candidate_id, result = await create_worker_fixture(tmp_path)
    stored: dict[str, bytes] = {}
    original_gate = cad_service.assert_generation_allowed
    gate_calls = 0

    async def gate_that_changes_after_compile(
        session: AsyncSession,
        *,
        project: Project,
        design_spec: DesignSpecRevision,
        expected_assessment_id: str | None = None,
        authorized_plan_id: str | None = None,
    ) -> RiskAssessment:
        nonlocal gate_calls
        gate_calls += 1
        if gate_calls == 2:
            raise RiskGateError("The current deterministic risk decision was invalidated.")
        return await original_gate(
            session,
            project=project,
            design_spec=design_spec,
            expected_assessment_id=expected_assessment_id,
            authorized_plan_id=authorized_plan_id,
        )

    def put_private_bytes(*, object_key: str, content: bytes, content_type: str) -> None:
        stored[object_key] = content

    monkeypatch.setattr("accessforge.cad.service.run_isolated_compilation", lambda _: result)
    monkeypatch.setattr(
        "accessforge.cad.service.assert_generation_allowed", gate_that_changes_after_compile
    )
    monkeypatch.setattr("accessforge.cad.service.put_private_bytes", put_private_bytes)
    try:
        async with factory() as session:
            assert await process_cad_candidate(session, candidate_id) == "failed"
            candidate = await session.get(CandidateDesign, candidate_id)
            assert candidate is not None
            assert candidate.status == "failed"
            assert candidate.failure_category == "risk_gate_changed"
            assert stored == {}
            artifacts = list(
                (
                    await session.scalars(
                        select(CandidateArtifact).where(
                            CandidateArtifact.candidate_id == candidate_id
                        )
                    )
                ).all()
            )
            assert artifacts == []
            assert gate_calls >= 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_removes_uploaded_artifacts_and_records_failure_on_storage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, factory, candidate_id, result = await create_worker_fixture(tmp_path)
    stored: dict[str, bytes] = {}
    attempts = 0

    def put_private_bytes(*, object_key: str, content: bytes, content_type: str) -> None:
        nonlocal attempts
        assert content_type
        attempts += 1
        if attempts == 2:
            raise RuntimeError("synthetic object storage interruption")
        stored[object_key] = content

    def delete_object(*, object_key: str) -> None:
        stored.pop(object_key, None)

    monkeypatch.setattr("accessforge.cad.service.run_isolated_compilation", lambda _: result)
    monkeypatch.setattr("accessforge.cad.service.put_private_bytes", put_private_bytes)
    monkeypatch.setattr("accessforge.cad.service.delete_object", delete_object)
    try:
        async with factory() as session:
            assert await process_cad_candidate(session, candidate_id) == "failed"
            candidate = await session.get(CandidateDesign, candidate_id)
            assert candidate is not None
            assert candidate.status == "failed"
            assert candidate.failure_category == "artifact_storage_error"
            job = await session.scalar(select(CadJob).where(CadJob.candidate_id == candidate.id))
            assert job is not None
            assert job.status == "failed"
            project = await session.get(Project, candidate.project_id)
            assert project is not None
            assert project.status == "ready_for_generation"
            assert stored == {}
            artifacts = list(
                (
                    await session.scalars(
                        select(CandidateArtifact).where(
                            CandidateArtifact.candidate_id == candidate.id
                        )
                    )
                ).all()
            )
            assert artifacts == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_comparison_batch_stays_generating_until_every_child_is_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, factory, candidate_ids, plan_id, result = await create_comparison_worker_fixture(
        tmp_path
    )
    stored: dict[str, bytes] = {}

    def put_private_bytes(*, object_key: str, content: bytes, content_type: str) -> None:
        assert content_type
        stored[object_key] = content

    monkeypatch.setattr("accessforge.cad.service.run_isolated_compilation", lambda _: result)
    monkeypatch.setattr("accessforge.cad.service.put_private_bytes", put_private_bytes)
    try:
        async with factory() as session:
            assert await process_cad_candidate(session, candidate_ids[0]) == "succeeded"
            first_project = await session.get(Project, "00000000-0000-0000-0000-000000000001")
            first_batch = await session.scalar(
                select(CandidateGenerationBatch).where(
                    CandidateGenerationBatch.design_plan_id == plan_id
                )
            )
            first_plan = await session.get(DesignPlan, plan_id)
            assert first_project is not None and first_project.status == "generating"
            assert first_batch is not None and first_batch.status == "running"
            assert first_plan is not None and first_plan.status == "comparison_queued"

            assert await process_cad_candidate(session, candidate_ids[1]) == "succeeded"
            final_project = await session.get(Project, "00000000-0000-0000-0000-000000000001")
            final_batch = await session.scalar(
                select(CandidateGenerationBatch).where(
                    CandidateGenerationBatch.design_plan_id == plan_id
                )
            )
            final_plan = await session.get(DesignPlan, plan_id)
            assert final_project is not None and final_project.status == "candidates_ready"
            assert final_batch is not None and final_batch.status == "completed"
            assert final_batch.completed_at is not None
            assert final_plan is not None and final_plan.status == "comparison_ready"
            assert len(stored) == len(result.artifacts) * 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_comparison_batch_records_mixed_worker_outcomes_after_the_last_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, factory, candidate_ids, plan_id, result = await create_comparison_worker_fixture(
        tmp_path
    )

    def put_private_bytes(*, object_key: str, content: bytes, content_type: str) -> None:
        assert object_key and content and content_type

    monkeypatch.setattr("accessforge.cad.service.run_isolated_compilation", lambda _: result)
    monkeypatch.setattr("accessforge.cad.service.put_private_bytes", put_private_bytes)
    try:
        async with factory() as session:
            assert await process_cad_candidate(session, candidate_ids[0]) == "succeeded"

            def interrupted_storage(*, object_key: str, content: bytes, content_type: str) -> None:
                raise RuntimeError("synthetic comparison storage interruption")

            monkeypatch.setattr("accessforge.cad.service.put_private_bytes", interrupted_storage)
            assert await process_cad_candidate(session, candidate_ids[1]) == "failed"
            project = await session.get(Project, "00000000-0000-0000-0000-000000000001")
            batch = await session.scalar(
                select(CandidateGenerationBatch).where(
                    CandidateGenerationBatch.design_plan_id == plan_id
                )
            )
            plan = await session.get(DesignPlan, plan_id)
            second = await session.get(CandidateDesign, candidate_ids[1])
            assert project is not None and project.status == "candidates_ready"
            assert batch is not None and batch.status == "completed_with_failures"
            assert plan is not None and plan.status == "comparison_ready"
            assert second is not None and second.failure_category == "artifact_storage_error"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_comparison_batch_cancellation_finalizes_queued_children_without_artifacts(
    tmp_path: Path,
) -> None:
    engine, factory, candidate_ids, plan_id, _ = await create_comparison_worker_fixture(tmp_path)
    try:
        async with factory() as session:
            project = await session.get(Project, "00000000-0000-0000-0000-000000000001")
            plan = await session.get(DesignPlan, plan_id)
            batch = await session.scalar(
                select(CandidateGenerationBatch).where(
                    CandidateGenerationBatch.design_plan_id == plan_id
                )
            )
            assert project is not None and plan is not None and batch is not None
            await cancel_comparison_batch(
                session,
                project=project,
                plan=plan,
                batch=batch,
                actor_id="phase5-worker-owner",
            )
            refreshed_project = await session.get(Project, project.id)
            refreshed_plan = await session.get(DesignPlan, plan.id)
            refreshed_batch = await session.get(CandidateGenerationBatch, batch.id)
            assert (
                refreshed_project is not None and refreshed_project.status == "ready_for_generation"
            )
            assert refreshed_plan is not None and refreshed_plan.status == "comparison_cancelled"
            assert refreshed_batch is not None and refreshed_batch.status == "cancelled"
            for candidate_id in candidate_ids:
                candidate = await session.get(CandidateDesign, candidate_id)
                assert candidate is not None and candidate.status == "cancelled"
                artifacts = list(
                    (
                        await session.scalars(
                            select(CandidateArtifact).where(
                                CandidateArtifact.candidate_id == candidate.id
                            )
                        )
                    ).all()
                )
                assert artifacts == []
    finally:
        await engine.dispose()
