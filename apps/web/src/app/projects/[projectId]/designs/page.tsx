'use client';

import Link from 'next/link';
import { use, useEffect, useMemo, useState } from 'react';
import type {
  CadLengthInput,
  CadLengthUnit,
  CandidateDesign,
  DesignSpecCreateInput,
  DesignSpecRevision,
  Project,
  TemplateRelease,
} from '@accessforge/api-client';
import { CandidateModelViewer } from '@/components/candidate-model-viewer';
import { useProjectClient } from '../../project-api';

type ParameterDraft = { value: string; unit: CadLengthUnit };

const unitOptions: Array<{ value: CadLengthUnit; label: string }> = [
  { value: 'mm', label: 'millimetres (mm)' },
  { value: 'cm', label: 'centimetres (cm)' },
  { value: 'in', label: 'inches (in)' },
  { value: 'm', label: 'metres (m)' },
];

function templateKey(template: TemplateRelease) {
  return `${template.template_id}@${template.version}`;
}

function initialParameterDrafts(template: TemplateRelease): Record<string, ParameterDraft> {
  return Object.fromEntries(
    Object.entries(template.parameters).map(([name, parameter]) => [
      name,
      { value: String(parameter.default), unit: 'mm' },
    ]),
  );
}

function lines(value: string) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}

function directEntry(value: string, unit: CadLengthUnit, sourceRef: string): CadLengthInput {
  return {
    value: Number(value),
    unit,
    creator_type: 'user',
    source_ref: sourceRef,
    rationale: 'Entered directly by the project owner for this immutable DesignSpec.',
  };
}

function canonicalRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function canonicalLength(value: unknown) {
  const entry = canonicalRecord(value);
  const originalValue = entry.original_value;
  const originalUnit = entry.original_unit;
  return typeof originalValue === 'number' && typeof originalUnit === 'string'
    ? `${originalValue} ${originalUnit}`
    : 'Not recorded';
}

export default function DesignsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const client = useProjectClient();
  const [project, setProject] = useState<Project | null>(null);
  const [templates, setTemplates] = useState<TemplateRelease[]>([]);
  const [specs, setSpecs] = useState<DesignSpecRevision[]>([]);
  const [candidates, setCandidates] = useState<CandidateDesign[]>([]);
  const [selectedTemplateKey, setSelectedTemplateKey] = useState('');
  const [parameters, setParameters] = useState<Record<string, ParameterDraft>>({});
  const [materialProfile, setMaterialProfile] = useState<'pla_provisional' | 'petg_provisional'>(
    'pla_provisional',
  );
  const [nozzleDiameter, setNozzleDiameter] = useState('0.4');
  const [nozzleUnit, setNozzleUnit] = useState<CadLengthUnit>('mm');
  const [layerHeight, setLayerHeight] = useState('0.2');
  const [layerUnit, setLayerUnit] = useState<CadLengthUnit>('mm');
  const [fitClearance, setFitClearance] = useState('0.4');
  const [clearanceUnit, setClearanceUnit] = useState<CadLengthUnit>('mm');
  const [dimensionalTolerance, setDimensionalTolerance] = useState('0.15');
  const [toleranceUnit, setToleranceUnit] = useState<CadLengthUnit>('mm');
  const [assessedUses, setAssessedUses] = useState(
    'Bounded parameter range checks\nGenerated mesh integrity checks',
  );
  const [unassessedUses, setUnassessedUses] = useState(
    'Physical fit\nStrength and durability\nPrintability\nSafety or accessibility outcome',
  );
  const [confirmedAssumptions, setConfirmedAssumptions] = useState(
    'This is a synthetic, deterministic geometry review only.',
  );
  const [unresolvedAssumptions, setUnresolvedAssumptions] = useState('');
  const [generationSeed, setGenerationSeed] = useState('direct-parameter-revision-1');
  const [message, setMessage] = useState('Loading reviewed templates and private revisions…');
  const [busy, setBusy] = useState(false);
  const selectedTemplate = useMemo(
    () => templates.find((template) => templateKey(template) === selectedTemplateKey) ?? null,
    [selectedTemplateKey, templates],
  );

  function load() {
    Promise.all([
      client.getProject(projectId),
      client.listTemplates(),
      client.listDesignSpecs(projectId),
      client.listCandidates(projectId),
    ])
      .then(([nextProject, nextTemplates, nextSpecs, nextCandidates]) => {
        setProject(nextProject);
        setTemplates(nextTemplates);
        setSpecs(nextSpecs);
        setCandidates(nextCandidates);
        if (nextTemplates.length > 0) {
          setSelectedTemplateKey((current) => current || templateKey(nextTemplates[0]));
          setParameters((current) =>
            Object.keys(current).length > 0 ? current : initialParameterDrafts(nextTemplates[0]),
          );
        }
        setMessage('');
      })
      .catch((error: unknown) =>
        setMessage(error instanceof Error ? error.message : 'Could not load the CAD workspace.'),
      );
  }

  useEffect(() => {
    load();
    // The authenticated client is stable for the mounted page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, projectId]);

  function chooseTemplate(key: string) {
    const nextTemplate = templates.find((template) => templateKey(template) === key);
    setSelectedTemplateKey(key);
    if (nextTemplate) setParameters(initialParameterDrafts(nextTemplate));
  }

  function updateParameter(name: string, patch: Partial<ParameterDraft>) {
    setParameters((current) => ({
      ...current,
      [name]: { ...current[name], ...patch },
    }));
  }

  async function createSpec(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTemplate) return;
    if (!project || project.status !== 'risk_review' || project.scope_status !== 'supported') {
      setMessage(
        'Confirm requirements and remain in supported scope before preparing a DesignSpec.',
      );
      return;
    }
    const parameterEntries = Object.entries(parameters);
    if (
      parameterEntries.some(
        ([, entry]) => !Number.isFinite(Number(entry.value)) || Number(entry.value) <= 0,
      )
    ) {
      setMessage('Every template parameter must be a positive number in its selected unit.');
      return;
    }
    setBusy(true);
    setMessage('Validating ranges and saving an immutable DesignSpec…');
    try {
      const input: DesignSpecCreateInput = {
        template_id: selectedTemplate.template_id,
        template_version: selectedTemplate.version,
        parameters: Object.fromEntries(
          parameterEntries.map(([name, entry]) => [
            name,
            directEntry(entry.value, entry.unit, `user:parameter:${name}`),
          ]),
        ),
        manufacturing: {
          process: 'fdm',
          material_profile: materialProfile,
          nozzle_diameter: directEntry(nozzleDiameter, nozzleUnit, 'user:nozzle-diameter'),
          layer_height: directEntry(layerHeight, layerUnit, 'user:layer-height'),
          creator_type: 'user',
          source_ref: 'user:manufacturing-profile',
          rationale: 'Selected directly for an informational deterministic geometry record.',
        },
        fit_clearance: directEntry(fitClearance, clearanceUnit, 'user:fit-clearance'),
        dimensional_tolerance: directEntry(
          dimensionalTolerance,
          toleranceUnit,
          'user:dimensional-tolerance',
        ),
        uses_assessed: lines(assessedUses),
        uses_not_assessed: lines(unassessedUses),
        confirmed_assumptions: lines(confirmedAssumptions),
        unresolved_assumptions: lines(unresolvedAssumptions),
        generation_seed: generationSeed.trim(),
      };
      const revision = await client.createDesignSpec(projectId, input);
      setSpecs((current) => [revision, ...current]);
      setMessage(
        `Saved immutable DesignSpec revision ${revision.revision_number}. It remains informational until Phase 5 risk review.`,
      );
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Could not save the DesignSpec.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-5xl">
      <p className="af-eyebrow">Step 5 · deterministic CAD record</p>
      <h1 className="mt-4 text-4xl font-bold tracking-tight">Prepare a bounded DesignSpec.</h1>
      <p className="mt-4 max-w-3xl leading-7 text-[var(--af-muted)]">
        Choose one repository-reviewed template and enter every dimension with a unit. AccessForge
        records the exact template release, canonical values, field provenance, and assumptions. A
        saved spec is not a safety review, fit result, or instruction to manufacture a physical
        part.
      </p>

      <section
        className="af-card mt-8 border-[var(--af-warning)] p-6"
        aria-labelledby="phase-gate-heading"
      >
        <p className="af-eyebrow text-[var(--af-warning)]">Generation gate</p>
        <h2 id="phase-gate-heading" className="mt-2 text-xl font-bold">
          Phase 5 deterministic risk review is still required.
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--af-muted)]">
          Candidate planning is available only after the server records a current deterministic risk
          assessment that explicitly permits it. Review the risk decision to see what is blocked,
          unknown, or needed next.
        </p>
        <Link className="af-button af-button-secondary mt-4" href={`/projects/${projectId}/risk`}>
          Open Risk Review
        </Link>
      </section>

      <form className="af-card mt-8 space-y-7 p-7" onSubmit={createSpec}>
        <div>
          <label className="font-semibold" htmlFor="template-release">
            Reviewed template release
          </label>
          <select
            className="af-input mt-2"
            id="template-release"
            value={selectedTemplateKey}
            disabled={busy || templates.length === 0}
            onChange={(event) => chooseTemplate(event.target.value)}
          >
            {templates.map((template) => (
              <option key={templateKey(template)} value={templateKey(template)}>
                {template.title} · {template.version}
              </option>
            ))}
          </select>
          {selectedTemplate ? (
            <div className="mt-4 rounded-lg border border-[var(--af-line)] bg-[var(--af-paper)] p-4 text-sm">
              <p className="font-semibold">{selectedTemplate.description}</p>
              <p className="mt-2 text-[var(--af-muted)]">
                Release hash: <code className="break-all">{selectedTemplate.manifest_sha256}</code>
              </p>
              <p className="mt-3 text-[var(--af-muted)]">
                Prohibited: {selectedTemplate.prohibited_uses.join(' · ')}
              </p>
            </div>
          ) : null}
        </div>

        {selectedTemplate ? (
          <fieldset>
            <legend className="font-semibold">Direct template parameters</legend>
            <p className="mt-2 text-sm text-[var(--af-muted)]">
              Values outside a reviewed template range are rejected; AccessForge never silently
              clamps a dimension.
            </p>
            <div className="mt-4 grid gap-5 sm:grid-cols-2">
              {Object.entries(selectedTemplate.parameters).map(([name, parameter]) => {
                const value = parameters[name] ?? { value: String(parameter.default), unit: 'mm' };
                return (
                  <div key={name}>
                    <label className="font-semibold" htmlFor={`parameter-${name}`}>
                      {parameter.label}
                    </label>
                    <p className="mt-1 text-sm text-[var(--af-muted)]">{parameter.description}</p>
                    <div className="mt-2 flex gap-2">
                      <input
                        required
                        className="af-input min-w-0 flex-1"
                        id={`parameter-${name}`}
                        type="number"
                        inputMode="decimal"
                        step="any"
                        value={value.value}
                        onChange={(event) => updateParameter(name, { value: event.target.value })}
                      />
                      <select
                        aria-label={`${parameter.label} unit`}
                        className="af-input w-40"
                        value={value.unit}
                        onChange={(event) =>
                          updateParameter(name, { unit: event.target.value as CadLengthUnit })
                        }
                      >
                        {unitOptions.map((unit) => (
                          <option key={unit.value} value={unit.value}>
                            {unit.value}
                          </option>
                        ))}
                      </select>
                    </div>
                    <p className="mt-1 text-xs text-[var(--af-muted)]">
                      Reviewed range: {parameter.minimum}–{parameter.maximum} {parameter.unit}.
                    </p>
                  </div>
                );
              })}
            </div>
          </fieldset>
        ) : null}

        <fieldset>
          <legend className="font-semibold">Manufacturing and fit record</legend>
          <p className="mt-2 text-sm text-[var(--af-muted)]">
            These settings are provenance for the geometry record. They are not a printability or
            material-performance recommendation.
          </p>
          <div className="mt-4 grid gap-5 sm:grid-cols-2">
            <label>
              Provisional material profile
              <select
                className="af-input mt-2"
                value={materialProfile}
                onChange={(event) =>
                  setMaterialProfile(event.target.value as 'pla_provisional' | 'petg_provisional')
                }
              >
                <option value="pla_provisional">PLA (provisional)</option>
                <option value="petg_provisional">PETG (provisional)</option>
              </select>
            </label>
            <LengthInput
              id="nozzle-diameter"
              label="Nozzle diameter"
              value={nozzleDiameter}
              unit={nozzleUnit}
              onValueChange={setNozzleDiameter}
              onUnitChange={setNozzleUnit}
            />
            <LengthInput
              id="layer-height"
              label="Layer height"
              value={layerHeight}
              unit={layerUnit}
              onValueChange={setLayerHeight}
              onUnitChange={setLayerUnit}
            />
            <LengthInput
              id="fit-clearance"
              label="Fit clearance"
              value={fitClearance}
              unit={clearanceUnit}
              onValueChange={setFitClearance}
              onUnitChange={setClearanceUnit}
            />
            <LengthInput
              id="dimensional-tolerance"
              label="Dimensional tolerance"
              value={dimensionalTolerance}
              unit={toleranceUnit}
              onValueChange={setDimensionalTolerance}
              onUnitChange={setToleranceUnit}
            />
          </div>
        </fieldset>

        <fieldset className="grid gap-5 sm:grid-cols-2">
          <label>
            Uses assessed by this record (one per line)
            <textarea
              className="af-input mt-2 min-h-28"
              value={assessedUses}
              onChange={(event) => setAssessedUses(event.target.value)}
            />
          </label>
          <label>
            Uses not assessed (one per line)
            <textarea
              className="af-input mt-2 min-h-28"
              value={unassessedUses}
              onChange={(event) => setUnassessedUses(event.target.value)}
            />
          </label>
          <label>
            Confirmed assumptions (one per line)
            <textarea
              className="af-input mt-2 min-h-28"
              value={confirmedAssumptions}
              onChange={(event) => setConfirmedAssumptions(event.target.value)}
            />
          </label>
          <label>
            Unresolved assumptions (one per line)
            <textarea
              className="af-input mt-2 min-h-28"
              value={unresolvedAssumptions}
              onChange={(event) => setUnresolvedAssumptions(event.target.value)}
            />
          </label>
        </fieldset>

        <label className="block max-w-md">
          Deterministic seed label
          <input
            required
            className="af-input mt-2"
            value={generationSeed}
            onChange={(event) => setGenerationSeed(event.target.value)}
          />
        </label>
        <div className="flex flex-wrap items-center gap-4">
          <button
            className="af-button af-button-primary"
            type="submit"
            disabled={busy || !selectedTemplate || project?.status !== 'risk_review'}
          >
            {busy ? 'Saving…' : 'Save immutable DesignSpec'}
          </button>
          <Link
            className="af-button af-button-secondary"
            href={`/projects/${projectId}/requirements`}
          >
            Review requirements
          </Link>
        </div>
      </form>

      <section className="mt-10" aria-labelledby="specifications-heading">
        <p className="af-eyebrow">Immutable history</p>
        <h2 id="specifications-heading" className="mt-2 text-2xl font-bold">
          DesignSpec revisions
        </h2>
        {specs.length === 0 ? (
          <p className="mt-4 text-[var(--af-muted)]">No immutable DesignSpec has been saved yet.</p>
        ) : (
          <div className="mt-5 space-y-5">
            {specs.map((spec) => (
              <SpecificationCard key={spec.id} spec={spec} projectId={projectId} />
            ))}
          </div>
        )}
      </section>

      <section className="mt-10" aria-labelledby="candidates-heading">
        <p className="af-eyebrow">Private candidate jobs</p>
        <h2 id="candidates-heading" className="mt-2 text-2xl font-bold">
          Geometry, artifacts, and checks
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--af-muted)]">
          A later approved candidate will have private artifacts, a short-lived GLB preview, and a
          structured report. A passed software check is not an approval or physical-use claim.
        </p>
        {candidates.length === 0 ? (
          <p className="mt-5 text-[var(--af-muted)]">
            No candidate job has been approved or queued.
          </p>
        ) : (
          <div className="mt-5 space-y-5">
            {candidates.map((candidate) => (
              <CandidateCard key={candidate.id} candidate={candidate} projectId={projectId} />
            ))}
          </div>
        )}
      </section>
      <p role="status" className="mt-8 text-sm text-[var(--af-muted)]">
        {message}
      </p>
    </div>
  );
}

function LengthInput({
  id,
  label,
  value,
  unit,
  onValueChange,
  onUnitChange,
}: {
  id: string;
  label: string;
  value: string;
  unit: CadLengthUnit;
  onValueChange: (value: string) => void;
  onUnitChange: (value: CadLengthUnit) => void;
}) {
  return (
    <div>
      <label className="font-semibold" htmlFor={id}>
        {label}
      </label>
      <div className="mt-2 flex gap-2">
        <input
          required
          className="af-input min-w-0 flex-1"
          id={id}
          type="number"
          inputMode="decimal"
          min="0"
          step="any"
          value={value}
          onChange={(event) => onValueChange(event.target.value)}
        />
        <select
          aria-label={`${label} unit`}
          className="af-input w-40"
          value={unit}
          onChange={(event) => onUnitChange(event.target.value as CadLengthUnit)}
        >
          {unitOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.value}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

function SpecificationCard({ spec, projectId }: { spec: DesignSpecRevision; projectId: string }) {
  const parameters = canonicalRecord(spec.canonical_spec.parameters);
  return (
    <article className="af-card p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="af-eyebrow">Revision {spec.revision_number}</p>
          <h3 className="mt-2 text-xl font-bold">
            {spec.template_id.replaceAll('_', ' ')} · {spec.template_version}
          </h3>
          <p className="mt-2 text-sm text-[var(--af-muted)]">
            Created {new Date(spec.created_at).toLocaleString()} · seed {spec.generation_seed}
          </p>
        </div>
        <Link className="af-button af-button-primary" href={`/projects/${projectId}/risk`}>
          Open Risk Review
        </Link>
      </div>
      <p className="mt-4 rounded-lg border border-[var(--af-warning)] bg-[#fff8ed] p-3 text-sm text-[var(--af-muted)]">
        Candidate planning is intentionally unavailable from this page. The risk review uses a
        current server decision and its allowed actions; browser-visible DesignSpec fields never
        authorize candidate generation.
      </p>
      <dl className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(parameters).map(([name, value]) => (
          <div className="rounded-lg border border-[var(--af-line)] p-3" key={name}>
            <dt className="text-sm text-[var(--af-muted)]">{name.replaceAll('_', ' ')}</dt>
            <dd className="mt-1 font-semibold">{canonicalLength(value)}</dd>
          </div>
        ))}
      </dl>
      <details className="mt-5 rounded-lg border border-[var(--af-line)] p-4">
        <summary className="cursor-pointer font-semibold">View canonical structured record</summary>
        <pre className="mt-4 max-h-96 overflow-auto whitespace-pre-wrap text-xs leading-5 text-[var(--af-muted)]">
          {JSON.stringify(spec.canonical_spec, null, 2)}
        </pre>
      </details>
    </article>
  );
}

function CandidateCard({
  candidate,
  projectId,
}: {
  candidate: CandidateDesign;
  projectId: string;
}) {
  const client = useProjectClient();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewMessage, setPreviewMessage] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const report = canonicalRecord(candidate.validation_report);
  const findings = Array.isArray(report.findings) ? report.findings : [];
  const geometry = canonicalRecord(candidate.geometry_summary);
  const geometryEntries = Object.entries(geometry);
  const reportId = `candidate-${candidate.id}-structured-report`;

  async function loadPreview() {
    if (candidate.status !== 'succeeded' || previewLoading || previewUrl) return;
    setPreviewLoading(true);
    setPreviewMessage('');
    try {
      const preview = await client.getCandidatePreview(projectId, candidate.id);
      setPreviewUrl(preview.preview_url);
    } catch {
      setPreviewMessage('The optional private preview is not available right now.');
    } finally {
      setPreviewLoading(false);
    }
  }

  function hidePreview() {
    setPreviewUrl(null);
    setPreviewMessage('');
  }

  return (
    <article className="af-card p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="af-eyebrow">Candidate {candidate.candidate_number}</p>
          <h3 className="mt-2 text-xl font-bold">
            {candidate.template_id.replaceAll('_', ' ')} · {candidate.status.replaceAll('_', ' ')}
          </h3>
          <p className="mt-2 text-sm text-[var(--af-muted)]">
            Job {candidate.job?.status ?? 'not recorded'} · {candidate.job?.attempt_count ?? 0}{' '}
            attempt
            {candidate.job?.attempt_count === 1 ? '' : 's'}
          </p>
        </div>
        {candidate.failure_category ? (
          <p className="rounded-full border border-[var(--af-danger)] px-3 py-1 text-sm text-[var(--af-danger)]">
            {candidate.failure_category.replaceAll('_', ' ')}
          </p>
        ) : null}
      </div>
      <section
        className="mt-5 rounded-lg border border-[var(--af-line)] bg-[var(--af-paper)] p-4"
        aria-labelledby={reportId}
      >
        <h4 id={reportId} className="font-semibold">
          Structured candidate report
        </h4>
        <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
          This text record is available without loading or interpreting a 3D preview.
        </p>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <CandidateFact label="Candidate status" value={candidate.status.replaceAll('_', ' ')} />
          <CandidateFact
            label="Software validation"
            value={candidate.validation_status?.replaceAll('_', ' ') ?? 'Not recorded'}
          />
          <CandidateFact
            label="Template release"
            value={`${candidate.template_id} · ${candidate.template_version}`}
          />
          <CandidateFact
            label="Private artifacts"
            value={
              candidate.artifacts.length > 0
                ? candidate.artifacts.map((artifact) => artifact.filename).join(', ')
                : 'Not recorded'
            }
          />
        </dl>
        {geometryEntries.length > 0 ? (
          <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
            {geometryEntries.map(([name, value]) => (
              <CandidateFact
                key={name}
                label={name.replaceAll('_', ' ')}
                value={JSON.stringify(value)}
              />
            ))}
          </dl>
        ) : (
          <p className="mt-5 text-sm text-[var(--af-muted)]">
            No structured geometry summary was recorded for this candidate.
          </p>
        )}
        {findings.length > 0 ? (
          <section className="mt-5" aria-labelledby={`${reportId}-findings`}>
            <h5 id={`${reportId}-findings`} className="font-semibold">
              Validation findings
            </h5>
            <ul className="mt-3 space-y-2 text-sm">
              {findings.map((finding, index) => {
                const item = canonicalRecord(finding);
                return (
                  <li
                    className="rounded-lg border border-[var(--af-line)] bg-white p-3"
                    key={`${index}-${String(item.check_id)}`}
                  >
                    <span className="font-semibold">{String(item.check_id ?? 'check')}</span> ·{' '}
                    {String(item.status ?? 'not assessed')}
                    {typeof item.plain_language_explanation === 'string'
                      ? ` — ${item.plain_language_explanation}`
                      : ''}
                  </li>
                );
              })}
            </ul>
          </section>
        ) : (
          <p className="mt-5 text-sm text-[var(--af-muted)]">
            No itemized validation findings were recorded. This is not a statement that an
            unassessed property passed.
          </p>
        )}
      </section>
      {candidate.status === 'succeeded' ? (
        <CandidateModelViewer
          previewUrl={previewUrl}
          title={`${candidate.template_id} candidate ${candidate.candidate_number}`}
          isLoading={previewLoading}
          message={previewMessage}
          onLoad={() => void loadPreview()}
          onHide={hidePreview}
        />
      ) : null}
      {candidate.artifacts.length > 0 ? (
        <p className="mt-5 text-sm text-[var(--af-muted)]">
          Private artifacts: {candidate.artifacts.map((artifact) => artifact.filename).join(' · ')}
        </p>
      ) : null}
    </article>
  );
}

function CandidateFact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[var(--af-muted)]">{label}</dt>
      <dd className="mt-1 break-words font-semibold">{value}</dd>
    </div>
  );
}
