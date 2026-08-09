'use client';

import Link from 'next/link';
import { use, useEffect, useMemo, useState } from 'react';
import type {
  CandidateComparisonBatch,
  CandidateDesign,
  ComparisonCandidate,
  DesignPlan,
  DesignPlanProposal,
  DesignSpecRevision,
  Project,
  RiskAssessment,
  RiskAssessmentInput,
  RiskTier,
} from '@accessforge/api-client';
import { useProjectClient } from '../../project-api';

type RiskForm = Omit<RiskAssessmentInput, 'design_spec_id'>;
type SelectOption = { value: string; label: string };

const bodyContactOptions: SelectOption[] = [
  { value: 'unknown', label: 'Unknown or not yet described' },
  { value: 'none', label: 'No body contact' },
  { value: 'incidental', label: 'Incidental body contact' },
  { value: 'prolonged', label: 'Prolonged or sustained body contact' },
];
const loadOptions: SelectOption[] = [
  { value: 'unknown', label: 'Unknown or not yet described' },
  { value: 'none', label: 'No meaningful load' },
  { value: 'low_energy_occasional', label: 'Low-energy, occasional load' },
  { value: 'repetitive', label: 'Repetitive load' },
  { value: 'high', label: 'High load or force' },
  { value: 'body_weight', label: 'Body-weight bearing or support' },
];
const temperatureOptions: SelectOption[] = [
  { value: 'unknown', label: 'Unknown or not yet described' },
  { value: 'room_temperature', label: 'Room temperature' },
  { value: 'hot', label: 'Hot surface or environment' },
  { value: 'cold', label: 'Cold surface or environment' },
];
const chemicalOptions: SelectOption[] = [
  { value: 'unknown', label: 'Unknown or not yet described' },
  { value: 'none', label: 'No chemical exposure' },
  { value: 'household', label: 'Household chemical exposure' },
  { value: 'laboratory', label: 'Laboratory, industrial, or unbounded chemicals' },
];
const electricityOptions: SelectOption[] = [
  { value: 'unknown', label: 'Unknown or not yet described' },
  { value: 'none', label: 'No electrical interaction' },
  { value: 'low_voltage', label: 'Low-voltage electrical interaction' },
  { value: 'mains', label: 'Mains-powered electrical interaction' },
];
const ageOptions: SelectOption[] = [
  { value: 'unknown', label: 'Unknown or not yet described' },
  { value: 'adult', label: 'Adult use' },
  { value: 'child', label: 'Child use or use around children' },
];
const safetyFeatureOptions: SelectOption[] = [
  { value: 'unknown', label: 'Unknown or not yet described' },
  { value: 'none', label: 'No safety feature interaction' },
  { value: 'possible', label: 'Possible interaction with a safety feature' },
  { value: 'yes', label: 'Directly interacts with a safety feature' },
];
const consequenceOptions: SelectOption[] = [
  { value: 'unknown', label: 'Unknown or not yet described' },
  { value: 'minor_inconvenience', label: 'Minor inconvenience if it fails' },
  { value: 'loss_of_access', label: 'Loss of access or usability if it fails' },
  { value: 'injury', label: 'Potential injury if it fails' },
  { value: 'safety_critical', label: 'Safety-critical consequence if it fails' },
];
const durationOptions: SelectOption[] = [
  { value: 'unknown', label: 'Unknown or not yet described' },
  { value: 'occasional', label: 'Occasional or short duration' },
  { value: 'prolonged', label: 'Prolonged or repeated duration' },
];
const fatigueOptions: SelectOption[] = [
  { value: 'unknown', label: 'Unknown or not yet described' },
  { value: 'not_expected', label: 'Fatigue not expected' },
  { value: 'possible', label: 'Fatigue is possible' },
  { value: 'likely', label: 'Fatigue is likely' },
];
const manufacturingOptions: SelectOption[] = [
  { value: 'unknown', label: 'Unknown or not yet described' },
  { value: 'bounded', label: 'Bounded, reviewed manufacturing assumptions' },
  { value: 'provisional', label: 'Provisional manufacturing assumptions' },
];

function initialRiskForm(): RiskForm {
  return {
    intended_use: '',
    body_contact: 'unknown',
    load: 'unknown',
    temperature: 'unknown',
    chemicals: 'unknown',
    electricity: 'unknown',
    age_group: 'unknown',
    safety_feature_interaction: 'unknown',
    failure_consequence: 'unknown',
    duration: 'unknown',
    fatigue: 'unknown',
    manufacturing_uncertainty: 'unknown',
  };
}

function projectLoadToRiskLoad(loadContext: string | null): RiskForm['load'] {
  switch (loadContext?.toLowerCase()) {
    case 'none':
      return 'none';
    case 'low':
    case 'low_energy':
    case 'occasional':
      return 'low_energy_occasional';
    case 'repetitive':
      return 'repetitive';
    case 'high':
      return 'high';
    case 'body_weight':
    case 'body-weight':
      return 'body_weight';
    default:
      return 'unknown';
  }
}

function humanize(value: string) {
  return value.replaceAll('_', ' ');
}

function tierExplanation(tier: RiskTier) {
  switch (tier) {
    case 'R0':
      return 'Informational scope only. A recorded result is not a safety, fit, or manufacturing approval.';
    case 'R1':
      return 'Bounded candidate planning may be permitted, but only when the server explicitly lists the next action.';
    case 'R2':
      return 'Professional review is required before this work can move forward in AccessForge.';
    case 'R3':
      return 'This use is outside the supported scope. AccessForge must not create geometry for it.';
  }
}

function isComparisonActive(status: string) {
  return ['queued', 'running', 'cancellation_requested'].includes(status);
}

function comparisonStatusExplanation(status: string) {
  switch (status) {
    case 'queued':
      return 'The private compiler queue has accepted each bounded variant.';
    case 'running':
      return 'The private compiler is processing the bounded variants.';
    case 'cancellation_requested':
      return 'Cancellation was requested. In-flight work stops cooperatively before artifact persistence.';
    case 'completed':
      return 'Every comparison candidate completed its software-only compiler path.';
    case 'completed_with_failures':
      return 'The comparison completed with a mix of successful and failed candidates.';
    case 'cancelled':
      return 'The private comparison was cancelled. No selection is available from this batch.';
    case 'failed':
      return 'The private comparison did not produce a selectable complete candidate.';
    default:
      return 'The server recorded the private comparison state.';
  }
}

function dateTime(value: string | null | undefined) {
  if (!value) return 'Not recorded';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default function RiskReviewPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const client = useProjectClient();
  const [project, setProject] = useState<Project | null>(null);
  const [specs, setSpecs] = useState<DesignSpecRevision[]>([]);
  const [risk, setRisk] = useState<RiskAssessment | null>(null);
  const [plans, setPlans] = useState<DesignPlan[]>([]);
  const [selectedDesignSpecId, setSelectedDesignSpecId] = useState('');
  const [form, setForm] = useState<RiskForm>(initialRiskForm);
  const [busyAction, setBusyAction] = useState<
    | 'assessing'
    | 'planning'
    | 'updating-plan'
    | 'generating'
    | 'queueing-comparison'
    | 'cancelling-comparison'
    | 'selecting-comparison'
    | null
  >(null);
  const [queuedCandidate, setQueuedCandidate] = useState<CandidateDesign | null>(null);
  const [message, setMessage] = useState('Loading the deterministic risk review…');

  useEffect(() => {
    let active = true;
    Promise.all([
      client.getProject(projectId),
      client.listDesignSpecs(projectId),
      client.getRisk(projectId),
      client.listDesignPlans(projectId),
    ])
      .then(([nextProject, nextSpecs, nextRisk, nextPlans]) => {
        if (!active) return;
        setProject(nextProject);
        setSpecs(nextSpecs);
        setRisk(nextRisk);
        setPlans(nextPlans);
        setSelectedDesignSpecId((current) => current || nextSpecs[0]?.id || '');
        setForm((current) => ({
          ...current,
          intended_use:
            current.intended_use ||
            nextProject.goal ||
            nextProject.action_description ||
            nextProject.description ||
            '',
          load:
            current.load === 'unknown'
              ? projectLoadToRiskLoad(nextProject.load_context)
              : current.load,
        }));
        setMessage('');
      })
      .catch((error: unknown) => {
        if (active) {
          setMessage(
            error instanceof Error
              ? error.message
              : 'Could not load the deterministic risk review.',
          );
        }
      });
    return () => {
      active = false;
    };
  }, [client, projectId]);

  const canStartCandidatePlanning = useMemo(
    () => Boolean(risk?.allowed_actions.includes('create_design_plan')),
    [risk],
  );

  function updateField<Field extends keyof RiskForm>(field: Field, value: RiskForm[Field]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function refreshPlans() {
    const nextPlans = await client.listDesignPlans(projectId);
    setPlans(nextPlans);
  }

  const hasActiveComparison = useMemo(
    () =>
      plans.some(
        (plan) =>
          plan.comparison_batch !== null && isComparisonActive(plan.comparison_batch.status),
      ),
    [plans],
  );

  useEffect(() => {
    if (!hasActiveComparison) return undefined;
    const interval = window.setInterval(() => {
      void client
        .listDesignPlans(projectId)
        .then((nextPlans) => setPlans(nextPlans))
        .catch(() => undefined);
    }, 4_000);
    return () => window.clearInterval(interval);
  }, [client, hasActiveComparison, projectId]);

  async function assessRisk(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDesignSpecId) {
      setMessage('Save a DesignSpec before running a deterministic risk review.');
      return;
    }
    if (!form.intended_use.trim()) {
      setMessage('Describe the intended use before running the review.');
      return;
    }
    setBusyAction('assessing');
    setMessage('Applying the versioned deterministic ruleset…');
    try {
      const assessment = await client.assessRisk(projectId, {
        ...form,
        intended_use: form.intended_use.trim(),
        design_spec_id: selectedDesignSpecId,
      });
      setRisk(assessment);
      try {
        await refreshPlans();
      } catch {
        // The assessment has been saved; plan history can be refreshed later.
      }
      setMessage('Risk review recorded. Read the server-provided next actions below.');
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Could not record the risk review.');
    } finally {
      setBusyAction(null);
    }
  }

  async function createDesignPlan() {
    if (!risk || !canStartCandidatePlanning) {
      setMessage(
        'Candidate planning is unavailable until the current server decision explicitly permits it.',
      );
      return;
    }
    setBusyAction('planning');
    setMessage('Requesting server-authorized candidate planning…');
    try {
      const plan = await client.createDesignPlan(projectId, risk.id);
      setPlans((current) => [plan, ...current.filter((item) => item.id !== plan.id)]);
      setMessage('Candidate planning has been recorded. Its status is shown below.');
      void refreshPlans().catch(() => undefined);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Could not start candidate planning.');
    } finally {
      setBusyAction(null);
    }
  }

  async function selectProposal(plan: DesignPlan, proposal: DesignPlanProposal) {
    setBusyAction('updating-plan');
    setMessage(`Selecting ${proposal.label} through the server-controlled plan…`);
    try {
      const nextPlan = await client.selectDesignPlanProposal(projectId, plan.id, proposal.id);
      setPlans((current) => current.map((item) => (item.id === nextPlan.id ? nextPlan : item)));
      setMessage('The proposal selection was recorded. Review the updated plan status.');
      void refreshPlans().catch(() => undefined);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Could not select that proposal.');
    } finally {
      setBusyAction(null);
    }
  }

  async function queueSelectedProposal(plan: DesignPlan, proposal: DesignPlanProposal) {
    if (!proposal.design_spec_id) {
      setMessage('The selected proposal is missing its immutable DesignSpec and cannot be queued.');
      return;
    }
    setBusyAction('generating');
    setMessage('Requesting a private candidate through the server-controlled generation gate…');
    try {
      const candidate = await client.generateCandidate(
        projectId,
        proposal.design_spec_id,
        `phase5-plan-${plan.id}-proposal-${proposal.id}`,
      );
      setQueuedCandidate(candidate);
      setMessage(
        `Private candidate ${candidate.candidate_number} is ${candidate.status.replaceAll('_', ' ')}. The server re-checked the current scope, risk decision, selected plan, and immutable DesignSpec.`,
      );
    } catch (error: unknown) {
      setMessage(
        error instanceof Error
          ? error.message
          : 'The server did not authorize a private candidate request.',
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function queueComparison(plan: DesignPlan) {
    setBusyAction('queueing-comparison');
    setMessage('Requesting the full private comparison through the server-controlled gate…');
    try {
      const batch = await client.generateComparison(
        projectId,
        plan.id,
        `phase5-comparison-${plan.id}`,
      );
      setPlans((current) =>
        current.map((item) =>
          item.id === plan.id
            ? { ...item, status: 'comparison_queued', comparison_batch: batch }
            : item,
        ),
      );
      try {
        await refreshPlans();
      } catch {
        // The server returned the durable batch; polling will reconcile the rest of the view.
      }
      setMessage(
        `${batch.candidates.length} bounded variants are in the private comparison. The server will re-check the current risk decision and immutable DesignSpecs before each compiler run.`,
      );
    } catch (error: unknown) {
      setMessage(
        error instanceof Error
          ? error.message
          : 'The server did not authorize the private comparison request.',
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function cancelComparison(plan: DesignPlan) {
    if (!window.confirm(`Cancel the private comparison for “${plan.label}”?`)) return;
    setBusyAction('cancelling-comparison');
    setMessage('Requesting cooperative cancellation of the private comparison…');
    try {
      const batch = await client.cancelComparison(projectId, plan.id);
      setPlans((current) =>
        current.map((item) => (item.id === plan.id ? { ...item, comparison_batch: batch } : item)),
      );
      try {
        await refreshPlans();
      } catch {
        // The returned batch state is durable, and active comparisons continue to poll.
      }
      setMessage(
        'Cancellation was recorded. Any in-flight compiler work will stop cooperatively before persisting artifacts.',
      );
    } catch (error: unknown) {
      setMessage(
        error instanceof Error ? error.message : 'Could not cancel the private comparison.',
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function selectComparisonCandidate(plan: DesignPlan, candidate: ComparisonCandidate) {
    setBusyAction('selecting-comparison');
    setMessage(`Choosing candidate ${candidate.candidate_number} for software review only…`);
    try {
      const nextPlan = await client.selectComparisonCandidate(projectId, plan.id, candidate.id);
      setPlans((current) => current.map((item) => (item.id === nextPlan.id ? nextPlan : item)));
      setMessage(
        `Candidate ${candidate.candidate_number} was recorded for software review only. This does not approve export, manufacturing, physical use, fit, or safety.`,
      );
    } catch (error: unknown) {
      setMessage(
        error instanceof Error
          ? error.message
          : 'The server did not allow that comparison candidate to be selected.',
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function cancelPlan(plan: DesignPlan) {
    if (!window.confirm(`Cancel candidate planning “${plan.label}”?`)) return;
    setBusyAction('updating-plan');
    setMessage('Cancelling candidate planning…');
    try {
      const nextPlan = await client.cancelDesignPlan(projectId, plan.id);
      setPlans((current) => current.map((item) => (item.id === nextPlan.id ? nextPlan : item)));
      setMessage('Candidate planning was cancelled.');
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Could not cancel candidate planning.');
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <div className="max-w-5xl">
      <p className="af-eyebrow">Step 6 · deterministic scope and risk review</p>
      <h1 className="mt-4 text-4xl font-bold tracking-tight">
        Review the bounded use before planning.
      </h1>
      <p className="mt-4 max-w-3xl leading-7 text-[var(--af-muted)]">
        This versioned ruleset checks the declared use and records why AccessForge can or cannot
        continue. It does not establish safety, fit, clinical suitability, material performance, or
        permission to manufacture or use a physical part.
      </p>

      <section className="af-card mt-8 p-6" aria-labelledby="project-context-heading">
        <h2 id="project-context-heading" className="text-xl font-bold">
          Project context used as evidence
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--af-muted)]">
          Environment stays a project fact rather than an inferred risk-form answer. Review it here,
          then describe the bounded use explicitly below.
        </p>
        <dl className="mt-5 grid gap-3 sm:grid-cols-2">
          <ContextFact label="Environment" value={project?.environment} />
          <ContextFact label="Project load context" value={project?.load_context} />
          <ContextFact
            label="Safety system noted"
            value={
              project?.safety_system === undefined || project.safety_system === null
                ? null
                : project.safety_system
                  ? 'Yes'
                  : 'No'
            }
          />
          <ContextFact label="Age context" value={project?.age_context} />
        </dl>
      </section>

      <section className="mt-10" aria-labelledby="risk-status-heading">
        <p className="af-eyebrow">Current decision</p>
        <h2 id="risk-status-heading" className="mt-2 text-2xl font-bold">
          Deterministic risk status
        </h2>
        <RiskStatusCard assessment={risk} projectId={projectId} />
      </section>

      <form className="af-card mt-10 space-y-7 p-7" onSubmit={assessRisk}>
        <div>
          <h2 className="text-2xl font-bold">Record or re-run the review</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--af-muted)]">
            Select every applicable category. “Unknown” is intentional evidence: it may limit what
            the ruleset permits and should not be replaced with a guess.
          </p>
        </div>

        <div>
          <label className="font-semibold" htmlFor="risk-design-spec">
            DesignSpec to review
          </label>
          <select
            required
            className="af-input mt-2"
            id="risk-design-spec"
            value={selectedDesignSpecId}
            disabled={busyAction !== null || specs.length === 0}
            onChange={(event) => setSelectedDesignSpecId(event.target.value)}
          >
            {specs.length === 0 ? <option value="">No saved DesignSpec yet</option> : null}
            {specs.map((spec) => (
              <option key={spec.id} value={spec.id}>
                Revision {spec.revision_number} · {spec.template_id.replaceAll('_', ' ')} ·{' '}
                {spec.template_version}
              </option>
            ))}
          </select>
          {specs.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--af-warning)]">
              <Link
                className="underline underline-offset-4"
                href={`/projects/${projectId}/designs`}
              >
                Save a bounded DesignSpec first.
              </Link>
            </p>
          ) : null}
        </div>

        <div>
          <label className="font-semibold" htmlFor="risk-intended-use">
            Intended use
          </label>
          <p id="risk-intended-use-help" className="mt-1 text-sm text-[var(--af-muted)]">
            State what the object is intended to do and the bounded setting. Do not describe a
            medical, safety-critical, or otherwise unsupported use as a workaround.
          </p>
          <textarea
            required
            aria-describedby="risk-intended-use-help"
            className="af-input mt-2 min-h-28"
            id="risk-intended-use"
            value={form.intended_use}
            disabled={busyAction !== null}
            onChange={(event) => updateField('intended_use', event.target.value)}
          />
        </div>

        <fieldset>
          <legend className="font-semibold">Use and consequence categories</legend>
          <p className="mt-1 text-sm text-[var(--af-muted)]">
            These are deterministic inputs, not predictions. Pick “unknown” where the evidence is
            incomplete.
          </p>
          <div className="mt-5 grid gap-5 sm:grid-cols-2">
            <RiskSelect
              id="risk-body-contact"
              label="Body contact"
              value={form.body_contact}
              options={bodyContactOptions}
              disabled={busyAction !== null}
              onChange={(value) =>
                updateField('body_contact', value as RiskAssessmentInput['body_contact'])
              }
            />
            <RiskSelect
              id="risk-load"
              label="Load or force"
              value={form.load}
              options={loadOptions}
              disabled={busyAction !== null}
              onChange={(value) => updateField('load', value as RiskAssessmentInput['load'])}
            />
            <RiskSelect
              id="risk-temperature"
              label="Temperature exposure"
              value={form.temperature}
              options={temperatureOptions}
              disabled={busyAction !== null}
              onChange={(value) =>
                updateField('temperature', value as RiskAssessmentInput['temperature'])
              }
            />
            <RiskSelect
              id="risk-chemicals"
              label="Chemical exposure"
              value={form.chemicals}
              options={chemicalOptions}
              disabled={busyAction !== null}
              onChange={(value) =>
                updateField('chemicals', value as RiskAssessmentInput['chemicals'])
              }
            />
            <RiskSelect
              id="risk-electricity"
              label="Electrical interaction"
              value={form.electricity}
              options={electricityOptions}
              disabled={busyAction !== null}
              onChange={(value) =>
                updateField('electricity', value as RiskAssessmentInput['electricity'])
              }
            />
            <RiskSelect
              id="risk-age-group"
              label="Age group"
              value={form.age_group}
              options={ageOptions}
              disabled={busyAction !== null}
              onChange={(value) =>
                updateField('age_group', value as RiskAssessmentInput['age_group'])
              }
            />
            <RiskSelect
              id="risk-safety-feature"
              label="Interaction with a safety feature"
              value={form.safety_feature_interaction}
              options={safetyFeatureOptions}
              disabled={busyAction !== null}
              onChange={(value) =>
                updateField(
                  'safety_feature_interaction',
                  value as RiskAssessmentInput['safety_feature_interaction'],
                )
              }
            />
            <RiskSelect
              id="risk-consequence"
              label="Consequence if it fails"
              value={form.failure_consequence}
              options={consequenceOptions}
              disabled={busyAction !== null}
              onChange={(value) =>
                updateField(
                  'failure_consequence',
                  value as RiskAssessmentInput['failure_consequence'],
                )
              }
            />
            <RiskSelect
              id="risk-duration"
              label="Duration or frequency"
              value={form.duration}
              options={durationOptions}
              disabled={busyAction !== null}
              onChange={(value) =>
                updateField('duration', value as RiskAssessmentInput['duration'])
              }
            />
            <RiskSelect
              id="risk-fatigue"
              label="Fatigue likelihood"
              value={form.fatigue}
              options={fatigueOptions}
              disabled={busyAction !== null}
              onChange={(value) => updateField('fatigue', value as RiskAssessmentInput['fatigue'])}
            />
            <RiskSelect
              id="risk-manufacturing"
              label="Manufacturing uncertainty"
              value={form.manufacturing_uncertainty}
              options={manufacturingOptions}
              disabled={busyAction !== null}
              onChange={(value) =>
                updateField(
                  'manufacturing_uncertainty',
                  value as RiskAssessmentInput['manufacturing_uncertainty'],
                )
              }
            />
          </div>
        </fieldset>

        <div className="flex flex-wrap items-center gap-4">
          <button
            className="af-button af-button-primary"
            type="submit"
            disabled={busyAction !== null || !selectedDesignSpecId}
          >
            {busyAction === 'assessing' ? 'Reviewing…' : 'Run deterministic risk review'}
          </button>
          <Link className="af-button af-button-secondary" href={`/projects/${projectId}/designs`}>
            Review DesignSpecs
          </Link>
        </div>
      </form>

      <section className="mt-10" aria-labelledby="candidate-planning-heading">
        <p className="af-eyebrow">Server-authorized next step</p>
        <h2 id="candidate-planning-heading" className="mt-2 text-2xl font-bold">
          Candidate planning
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--af-muted)]">
          This control never infers permission from the tier shown in the browser. It is available
          only when the current server decision includes the explicit{' '}
          <code>create_design_plan</code> action. The server re-checks that decision when a plan is
          requested.
        </p>
        <div className="af-card mt-5 p-6">
          {canStartCandidatePlanning && risk ? (
            <div className="flex flex-wrap items-center justify-between gap-4">
              <p className="max-w-2xl text-sm leading-6 text-[var(--af-muted)]">
                The current assessment permits bounded candidate planning. Starting a plan records a
                server-controlled workflow; it is not a request to manufacture or use a part.
              </p>
              <button
                className="af-button af-button-primary"
                type="button"
                disabled={busyAction !== null}
                onClick={() => void createDesignPlan()}
              >
                {busyAction === 'planning' ? 'Starting plan…' : 'Start candidate planning'}
              </button>
            </div>
          ) : (
            <p className="text-sm leading-6 text-[var(--af-muted)]">
              Candidate planning is not currently available. Run or update the deterministic risk
              review, then follow the exact next actions returned by the server.
            </p>
          )}
        </div>
        {plans.length === 0 ? (
          <p className="mt-5 text-[var(--af-muted)]">No candidate planning records yet.</p>
        ) : (
          <div className="mt-5 space-y-5">
            {plans.map((plan) => (
              <DesignPlanCard
                key={plan.id}
                plan={plan}
                busy={busyAction !== null}
                onCancel={() => void cancelPlan(plan)}
                onCancelComparison={() => void cancelComparison(plan)}
                onGenerateComparison={() => void queueComparison(plan)}
                onQueueCandidate={(proposal) => void queueSelectedProposal(plan, proposal)}
                onSelectComparisonCandidate={(candidate) =>
                  void selectComparisonCandidate(plan, candidate)
                }
                onSelect={(proposal) => void selectProposal(plan, proposal)}
              />
            ))}
          </div>
        )}
        {queuedCandidate ? (
          <div className="mt-5 rounded-lg border border-[var(--af-line)] bg-[var(--af-paper)] p-5 text-sm leading-6">
            <p className="font-semibold">Private candidate request recorded</p>
            <p className="mt-1 text-[var(--af-muted)]">
              Candidate {queuedCandidate.candidate_number} is {humanize(queuedCandidate.status)}. It
              remains a software-only job and does not establish a safety, fit, manufacturing, or
              physical-use result.
            </p>
            <Link
              className="af-button af-button-secondary mt-4"
              href={`/projects/${projectId}/designs`}
            >
              View private candidate jobs
            </Link>
          </div>
        ) : null}
      </section>

      <p role="status" className="mt-8 text-sm text-[var(--af-muted)]">
        {message}
      </p>
    </div>
  );
}

function ContextFact({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="rounded-lg border border-[var(--af-line)] bg-[var(--af-paper)] p-4">
      <dt className="text-sm text-[var(--af-muted)]">{label}</dt>
      <dd className="mt-1 font-semibold">{value || 'Not provided'}</dd>
    </div>
  );
}

function RiskSelect({
  id,
  label,
  value,
  options,
  disabled,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: SelectOption[];
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label className="font-semibold" htmlFor={id}>
        {label}
      </label>
      <select
        className="af-input mt-2"
        id={id}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function RiskStatusCard({
  assessment,
  projectId,
}: {
  assessment: RiskAssessment | null;
  projectId: string;
}) {
  if (!assessment) {
    return (
      <div className="af-card mt-5 p-6">
        <p className="font-semibold">No deterministic risk review has been recorded yet.</p>
        <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
          Save a DesignSpec, complete the explicit categories below, and run the ruleset. Candidate
          planning remains unavailable until the server records an allowed next action.
        </p>
      </div>
    );
  }

  const invalidated = Boolean(assessment.invalidated_at) || assessment.status === 'invalidated';
  return (
    <article
      className={`af-card mt-5 p-6 ${invalidated ? 'border-[var(--af-warning)]' : ''}`}
      aria-live="polite"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="af-eyebrow">{humanize(assessment.status)}</p>
          <h3 className="mt-2 text-xl font-bold">
            {invalidated ? 'Risk assessment is no longer current.' : `Tier ${assessment.tier}`}
          </h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--af-muted)]">
            {tierExplanation(assessment.tier)}
          </p>
        </div>
        <p className="rounded-full border border-[var(--af-line)] px-3 py-1 text-sm font-semibold">
          {invalidated ? 'Re-review required' : `Tier ${assessment.tier}`}
        </p>
      </div>

      {invalidated ? (
        <p className="mt-5 rounded-lg border border-[var(--af-warning)] bg-[#fff8ed] p-4 text-sm leading-6">
          {assessment.invalidated_reason ||
            'A project or DesignSpec change made this assessment no longer current.'}
          <span className="block mt-1 text-[var(--af-muted)]">
            Invalidated {dateTime(assessment.invalidated_at)}. Re-run the review before relying on
            any displayed next action.
          </span>
        </p>
      ) : null}

      <section className="mt-6" aria-labelledby="allowed-actions-heading">
        <h4 id="allowed-actions-heading" className="font-semibold">
          Allowed next actions from the server
        </h4>
        {assessment.allowed_actions.length > 0 ? (
          <ul className="mt-3 flex flex-wrap gap-2 text-sm">
            {assessment.allowed_actions.map((action) => (
              <li className="rounded-full border border-[var(--af-primary)] px-3 py-1" key={action}>
                {humanize(action)}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-[var(--af-muted)]">
            The server did not permit a next action for this review.
          </p>
        )}
      </section>

      <section className="mt-6" aria-labelledby="decision-explanation-heading">
        <h4 id="decision-explanation-heading" className="font-semibold">
          Plain-language result
        </h4>
        <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
          {assessment.user_explanation || 'No explanatory text was recorded.'}
        </p>
      </section>

      <section className="mt-6" aria-labelledby="unresolved-questions-heading">
        <h4 id="unresolved-questions-heading" className="font-semibold">
          Unresolved questions
        </h4>
        {assessment.unresolved_questions.length > 0 ? (
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-[var(--af-muted)]">
            {assessment.unresolved_questions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-[var(--af-muted)]">None recorded by this ruleset run.</p>
        )}
      </section>

      <section className="mt-6" aria-labelledby="matched-rules-heading">
        <h4 id="matched-rules-heading" className="font-semibold">
          Matched deterministic rules
        </h4>
        {assessment.matched_rules.length === 0 ? (
          <p className="mt-2 text-sm text-[var(--af-muted)]">
            No matching rule details were returned.
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {assessment.matched_rules.map((rule) => (
              <article
                className="rounded-lg border border-[var(--af-line)] bg-[var(--af-paper)] p-4"
                key={rule.rule_id}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h5 className="font-semibold">{rule.rule_id}</h5>
                  <p className="text-sm text-[var(--af-muted)]">
                    Tier {rule.tier} · {humanize(rule.status)}
                  </p>
                </div>
                <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">{rule.explanation}</p>
                {rule.remediation ? (
                  <p className="mt-2 text-sm leading-6">
                    <span className="font-semibold">What to do next: </span>
                    {rule.remediation}
                  </p>
                ) : null}
                {rule.evidence_refs.length > 0 ? (
                  <p className="mt-2 text-xs leading-5 text-[var(--af-muted)]">
                    Evidence: {rule.evidence_refs.join(' · ')}
                  </p>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </section>

      <div className="mt-6 flex flex-wrap items-center gap-3 text-sm">
        <Link className="af-button af-button-secondary" href={`/projects/${projectId}/designs`}>
          Review DesignSpecs
        </Link>
        {assessment.resulting_design_spec_id ? (
          <span className="text-[var(--af-muted)]">
            Resulting DesignSpec: {assessment.resulting_design_spec_id}
          </span>
        ) : null}
      </div>

      <details className="mt-6 rounded-lg border border-[var(--af-line)] p-4 text-sm">
        <summary className="cursor-pointer font-semibold">Decision record and versioning</summary>
        <dl className="mt-4 grid gap-3 sm:grid-cols-2">
          <DecisionFact label="Recorded" value={dateTime(assessment.created_at)} />
          <DecisionFact label="Ruleset version" value={assessment.ruleset_version} />
          <DecisionFact label="Ruleset hash" value={assessment.ruleset_hash} />
          <DecisionFact label="Input hash" value={assessment.input_hash} />
          <DecisionFact label="Decision hash" value={assessment.decision_hash} />
          <DecisionFact label="Requirements revision" value={assessment.requirements_revision_id} />
        </dl>
      </details>
    </article>
  );
}

function DecisionFact({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-[var(--af-muted)]">{label}</dt>
      <dd className="mt-1 break-all font-mono text-xs">{value || 'Not recorded'}</dd>
    </div>
  );
}

function DesignPlanCard({
  plan,
  busy,
  onCancel,
  onCancelComparison,
  onGenerateComparison,
  onQueueCandidate,
  onSelectComparisonCandidate,
  onSelect,
}: {
  plan: DesignPlan;
  busy: boolean;
  onCancel: () => void;
  onCancelComparison: () => void;
  onGenerateComparison: () => void;
  onQueueCandidate: (proposal: DesignPlanProposal) => void;
  onSelectComparisonCandidate: (candidate: ComparisonCandidate) => void;
  onSelect: (proposal: DesignPlanProposal) => void;
}) {
  const proposals = plan.proposals ?? [];
  const batch = plan.comparison_batch;
  const canStartComparison =
    plan.status === 'waiting_for_user' &&
    batch === null &&
    proposals.length >= 2 &&
    proposals.length <= 3;
  const canUseSingleSelection = plan.status === 'waiting_for_user' && batch === null;
  const selectedProposal = proposals.find((proposal) => proposal.status === 'selected');
  return (
    <article className="af-card p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="af-eyebrow">{humanize(plan.status)}</p>
          <h3 className="mt-2 text-xl font-bold">{plan.label}</h3>
          {plan.created_at ? (
            <p className="mt-2 text-sm text-[var(--af-muted)]">
              Created {dateTime(plan.created_at)}
            </p>
          ) : null}
        </div>
        {batch && ['queued', 'running'].includes(batch.status) ? (
          <button
            className="af-button af-button-secondary text-[var(--af-danger)]"
            type="button"
            disabled={busy}
            onClick={onCancelComparison}
          >
            Cancel private comparison
          </button>
        ) : batch?.status === 'cancellation_requested' ? (
          <p className="text-sm font-semibold text-[var(--af-muted)]">Cancellation requested</p>
        ) : canUseSingleSelection ? (
          <button
            className="af-button af-button-secondary text-[var(--af-danger)]"
            type="button"
            disabled={busy}
            onClick={onCancel}
          >
            Cancel plan
          </button>
        ) : null}
      </div>
      {plan.waiting_for_user_message || plan.required_user_action ? (
        <p className="mt-5 rounded-lg border border-[var(--af-warning)] bg-[#fff8ed] p-4 text-sm leading-6">
          <span className="font-semibold">Planning needs your input: </span>
          {plan.waiting_for_user_message || plan.required_user_action}
        </p>
      ) : null}
      {plan.failure_category ? (
        <p className="mt-5 text-sm text-[var(--af-danger)]">
          Planning did not complete: {humanize(plan.failure_category)}.
        </p>
      ) : null}
      {plan.tradeoffs.length > 0 ? (
        <section className="mt-5" aria-label="Plan tradeoffs">
          <h4 className="font-semibold">Tradeoffs</h4>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-[var(--af-muted)]">
            {plan.tradeoffs.map((tradeoff) => (
              <li key={tradeoff}>{tradeoff}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {batch ? (
        <ComparisonBatchCard
          batch={batch}
          busy={busy}
          plan={plan}
          proposals={proposals}
          onSelectCandidate={onSelectComparisonCandidate}
        />
      ) : null}
      {canStartComparison ? (
        <section
          className="mt-6 rounded-lg border border-[var(--af-primary)] bg-[var(--af-paper)] p-5"
          aria-label="Primary private comparison checkpoint"
        >
          <p className="af-eyebrow">Primary checkpoint</p>
          <h4 className="mt-2 font-semibold">Compare all {proposals.length} bounded variants</h4>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--af-muted)]">
            Queue the complete private software comparison to inspect the reviewed parameter
            variants side by side. The browser does not grant this permission: the server verifies
            the current risk record, plan lineage, and every immutable DesignSpec before each run.
          </p>
          <button
            className="af-button af-button-primary mt-4"
            type="button"
            disabled={busy}
            onClick={onGenerateComparison}
          >
            Queue {proposals.length} private comparison candidates
          </button>
          <p className="mt-3 text-xs leading-5 text-[var(--af-muted)]">
            This is software-only work. It does not approve export, manufacturing, physical use,
            fit, or safety.
          </p>
        </section>
      ) : null}
      {proposals.length > 0 && batch === null ? (
        <section className="mt-6" aria-label="Plan proposals">
          {canUseSingleSelection ? (
            <details className="rounded-lg border border-[var(--af-line)] p-4">
              <summary className="cursor-pointer font-semibold">
                Use one starting point instead of the full comparison
              </summary>
              <p className="mt-3 text-sm leading-6 text-[var(--af-muted)]">
                This alternate path records one starting point and rejects the other variants. It is
                separate from the preferred comparison and still requires a later server gate before
                one private candidate can be queued.
              </p>
              <ProposalList proposals={proposals} busy={busy} onSelect={onSelect} />
            </details>
          ) : (
            <>
              <h4 className="font-semibold">Plan variants</h4>
              <ProposalList proposals={proposals} busy onSelect={onSelect} />
            </>
          )}
        </section>
      ) : null}
      {plan.status === 'confirmed' && selectedProposal ? (
        <section className="mt-6 rounded-lg border border-[var(--af-line)] bg-[var(--af-paper)] p-5">
          <h4 className="font-semibold">Single starting point recorded</h4>
          <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
            {selectedProposal.label} was selected instead of the full comparison. The following
            request remains server-gated; nothing shown in this browser authorizes generation.
          </p>
          <button
            className="af-button af-button-primary mt-4"
            type="button"
            disabled={busy || !selectedProposal.design_spec_id}
            onClick={() => onQueueCandidate(selectedProposal)}
          >
            Queue one private software candidate
          </button>
          <p className="mt-3 text-xs leading-5 text-[var(--af-muted)]">
            This does not approve export, manufacturing, physical use, fit, or safety.
          </p>
        </section>
      ) : null}
    </article>
  );
}

function ProposalList({
  proposals,
  busy,
  onSelect,
}: {
  proposals: DesignPlanProposal[];
  busy: boolean;
  onSelect: (proposal: DesignPlanProposal) => void;
}) {
  return (
    <div className="mt-4 space-y-3">
      {proposals.map((proposal) => (
        <div
          className="rounded-lg border border-[var(--af-line)] bg-[var(--af-paper)] p-4"
          key={proposal.id}
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-semibold">{proposal.label}</p>
              <p className="mt-1 text-sm text-[var(--af-muted)]">
                {humanize(proposal.status)}
                {proposal.design_spec_id ? ` · DesignSpec ${proposal.design_spec_id}` : ''}
              </p>
            </div>
            <button
              className="af-button af-button-secondary"
              type="button"
              disabled={
                busy || ['selected', 'rejected', 'cancelled', 'canceled'].includes(proposal.status)
              }
              onClick={() => onSelect(proposal)}
            >
              Select one starting point
            </button>
          </div>
          {proposal.explanation ? (
            <p className="mt-3 text-sm leading-6 text-[var(--af-muted)]">{proposal.explanation}</p>
          ) : null}
          {proposal.tradeoffs.length > 0 ? (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-[var(--af-muted)]">
              {proposal.tradeoffs.map((tradeoff) => (
                <li key={tradeoff}>{tradeoff}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function ComparisonBatchCard({
  batch,
  busy,
  plan,
  proposals,
  onSelectCandidate,
}: {
  batch: CandidateComparisonBatch;
  busy: boolean;
  plan: DesignPlan;
  proposals: DesignPlanProposal[];
  onSelectCandidate: (candidate: ComparisonCandidate) => void;
}) {
  const isActive = isComparisonActive(batch.status);
  return (
    <section
      className="mt-6 rounded-lg border border-[var(--af-primary)] bg-[var(--af-paper)] p-5"
      aria-label="Private candidate comparison"
      aria-live="polite"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="af-eyebrow">Private comparison batch</p>
          <h4 className="mt-2 font-semibold">{batch.candidates.length} bounded variants</h4>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--af-muted)]">
            {comparisonStatusExplanation(batch.status)}
          </p>
        </div>
        <p className="rounded-full border border-[var(--af-line)] px-3 py-1 text-sm font-semibold">
          {humanize(batch.status)}
        </p>
      </div>
      <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-3">
        <DecisionFact label="Requested" value={dateTime(batch.requested_at)} />
        <DecisionFact label="Cancellation requested" value={dateTime(batch.cancel_requested_at)} />
        <DecisionFact label="Completed" value={dateTime(batch.completed_at)} />
      </dl>
      {isActive ? (
        <p className="mt-4 text-sm leading-6 text-[var(--af-muted)]">
          This view refreshes while the private batch is active. No comparison result is an export,
          approval, manufacturing instruction, safety conclusion, fit result, or physical-use
          permission.
        </p>
      ) : null}
      {batch.candidates.length === 0 ? (
        <p className="mt-5 text-sm text-[var(--af-muted)]">
          The server has not returned comparison candidates yet.
        </p>
      ) : (
        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          {batch.candidates.map((candidate) => {
            const proposal = proposals.find(
              (item) => item.design_spec_id === candidate.design_spec_id,
            );
            const unknowns = Array.from(
              new Set([
                ...(proposal?.tradeoffs ?? []),
                ...(plan.tradeoffs ?? []),
                ...candidate.validation_limitations,
              ]),
            );
            const selectedForSoftwareReview = proposal?.status === 'comparison_selected';
            const canSelect =
              plan.status === 'comparison_ready' && candidate.status === 'succeeded';
            return (
              <article
                className="rounded-lg border border-[var(--af-line)] bg-white p-4"
                key={candidate.id}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">
                      {candidate.variant_label ||
                        proposal?.label ||
                        `Variant ${candidate.candidate_number}`}
                    </p>
                    <p className="mt-1 text-sm text-[var(--af-muted)]">
                      Candidate {candidate.candidate_number} · {humanize(candidate.status)}
                    </p>
                  </div>
                  {selectedForSoftwareReview ? (
                    <p className="rounded-full border border-[var(--af-primary)] px-3 py-1 text-sm font-semibold">
                      Software review selection
                    </p>
                  ) : null}
                </div>
                <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-[var(--af-muted)]">Validation record</dt>
                    <dd className="mt-1 font-semibold">
                      {candidate.validation_status
                        ? humanize(candidate.validation_status)
                        : 'Not recorded yet'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[var(--af-muted)]">Variant key</dt>
                    <dd className="mt-1 break-all font-mono text-xs">
                      {candidate.variant_key || 'Not recorded'}
                    </dd>
                  </div>
                </dl>
                {proposal?.explanation ? (
                  <p className="mt-4 text-sm leading-6 text-[var(--af-muted)]">
                    {proposal.explanation}
                  </p>
                ) : null}
                {candidate.failure_category ? (
                  <p className="mt-4 rounded-lg border border-[var(--af-danger)] p-3 text-sm text-[var(--af-danger)]">
                    Compiler outcome: {humanize(candidate.failure_category)}
                  </p>
                ) : null}
                <section className="mt-4" aria-label="Unknowns and unassessed properties">
                  <h5 className="text-sm font-semibold">Unknowns and unassessed properties</h5>
                  {unknowns.length > 0 ? (
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-[var(--af-muted)]">
                      {unknowns.map((unknown) => (
                        <li key={unknown}>{unknown}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
                      No additional comparison-specific unknowns were returned. This does not assess
                      physical performance, fit, safety, or manufacturability.
                    </p>
                  )}
                </section>
                {canSelect ? (
                  <div className="mt-5 rounded-lg border border-[var(--af-line)] bg-[var(--af-paper)] p-4">
                    <p className="text-sm leading-6 text-[var(--af-muted)]">
                      This candidate completed its private software path. You may record one
                      selection for software review; the server will verify its status and lineage
                      again.
                    </p>
                    <button
                      className="af-button af-button-primary mt-3"
                      type="button"
                      disabled={busy}
                      onClick={() => onSelectCandidate(candidate)}
                    >
                      Choose for software review only
                    </button>
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      )}
      <details className="mt-5 rounded-lg border border-[var(--af-line)] p-4 text-sm">
        <summary className="cursor-pointer font-semibold">Comparison record</summary>
        <dl className="mt-4 grid gap-3 sm:grid-cols-2">
          <DecisionFact label="Batch ID" value={batch.id} />
          <DecisionFact label="Input hash" value={batch.input_hash} />
          <DecisionFact label="Risk assessment" value={batch.risk_assessment_id} />
          <DecisionFact label="Plan ID" value={batch.design_plan_id} />
        </dl>
      </details>
    </section>
  );
}
