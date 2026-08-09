'use client';

import Link from 'next/link';
import { use, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  acknowledgementVersion,
  createExportApproval,
  createPrivateExport,
  downloadPrivateExportBundle,
  getExportReadiness,
  listExportCandidates,
  listPrivateExportBundles,
  reportCandidateHazard,
  submitCandidateFeedback,
  type ExportApproval,
  type ExportCandidate,
  type ExportReadiness,
  type PrivateExportBundle,
} from './export-api';

type BusyAction = 'approval' | 'export' | 'feedback' | 'hazard' | 'download' | null;

const acknowledgementLabels = {
  exact_revision_reviewed:
    'I reviewed the exact candidate revision and its recorded hashes shown on this page.',
  limitations_understood:
    'I understand this is not professional approval or evidence of safety, fit, durability, or physical suitability.',
  non_human_controlled_validation_only:
    'I will treat any available bundle only as a private, non-human controlled-validation record within its stated limits.',
} as const;

type Acknowledgements = Record<keyof typeof acknowledgementLabels, boolean>;

const initialAcknowledgements: Acknowledgements = {
  exact_revision_reviewed: false,
  limitations_understood: false,
  non_human_controlled_validation_only: false,
};

function dateTime(value: string | null | undefined) {
  if (!value) return 'Not recorded';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function shortHash(value: string | null | undefined) {
  if (!value) return 'Not recorded';
  return value.length > 24 ? `${value.slice(0, 12)}…${value.slice(-10)}` : value;
}

function candidateLabel(candidate: ExportCandidate) {
  return `Candidate ${candidate.candidate_number} · ${candidate.template_id.replaceAll('_', ' ')} · ${candidate.status.replaceAll('_', ' ')}`;
}

function gateHeading(readiness: ExportReadiness | null, loadError: string | null) {
  if (loadError) return 'No current server gate result — controlled export is denied';
  if (!readiness) return 'Checking current server gates…';
  if (readiness.allowed) return 'Evidence gate currently complete for a controlled export record';
  return 'Controlled export is currently unavailable';
}

function uniqueIdempotencyKey(prefix: string) {
  return `${prefix}-${crypto.randomUUID()}`;
}

export default function ControlledExportPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  const [candidates, setCandidates] = useState<ExportCandidate[]>([]);
  const [candidateId, setCandidateId] = useState('');
  const [readiness, setReadiness] = useState<ExportReadiness | null>(null);
  const [bundles, setBundles] = useState<PrivateExportBundle[]>([]);
  const [approval, setApproval] = useState<ExportApproval | null>(null);
  const [acknowledgements, setAcknowledgements] =
    useState<Acknowledgements>(initialAcknowledgements);
  const [feedbackCategory, setFeedbackCategory] = useState('fit');
  const [feedbackSeverity, setFeedbackSeverity] = useState('low');
  const [feedbackSummary, setFeedbackSummary] = useState('');
  const [hazardSeverity, setHazardSeverity] = useState('high');
  const [hazardSummary, setHazardSummary] = useState('');
  const [hazardConfirmed, setHazardConfirmed] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [message, setMessage] = useState('Loading private candidates…');
  const [busyAction, setBusyAction] = useState<BusyAction>(null);
  const readinessRequestVersion = useRef(0);

  const selectedCandidate = useMemo(
    () => candidates.find((candidate) => candidate.id === candidateId) ?? null,
    [candidateId, candidates],
  );
  const allAcknowledged = useMemo(
    () => Object.values(acknowledgements).every(Boolean),
    [acknowledgements],
  );
  const canRequestApproval = Boolean(readiness?.allowed && allAcknowledged && !busyAction);
  const canCreateExport = Boolean(readiness?.allowed && approval?.id && !busyAction);

  const refreshSelectedCandidate = useCallback(
    async (nextCandidateId: string, quiet = false, resetApproval = true) => {
      const requestVersion = ++readinessRequestVersion.current;
      // Keep every state update async. Candidate changes are an external server sync,
      // not a derived-state update during React's render/effect pass.
      await Promise.resolve();
      if (!nextCandidateId) {
        if (requestVersion !== readinessRequestVersion.current) return;
        setReadiness(null);
        setBundles([]);
        setLoadError(null);
        return;
      }
      try {
        const [nextReadiness, nextBundles] = await Promise.all([
          getExportReadiness(projectId, nextCandidateId),
          listPrivateExportBundles(projectId, nextCandidateId),
        ]);
        if (requestVersion !== readinessRequestVersion.current) return;
        setLoadError(null);
        if (resetApproval) setApproval(null);
        setAcknowledgements(initialAcknowledgements);
        setReadiness(nextReadiness);
        setBundles(nextBundles);
        if (!quiet) {
          setMessage(
            nextReadiness.allowed
              ? 'The server returned a current controlled-export evidence result. Read every limitation before acknowledging.'
              : 'The server currently denies controlled export. Read the evidence gaps below; no bundle can be created from this screen.',
          );
        }
      } catch (error: unknown) {
        if (requestVersion !== readinessRequestVersion.current) return;
        const detail =
          error instanceof Error
            ? error.message
            : 'Could not obtain a current controlled-export result.';
        setReadiness(null);
        setBundles([]);
        setLoadError(detail);
        setMessage(
          'A current server gate result is unavailable, so controlled export remains denied.',
        );
      }
    },
    [projectId],
  );

  useEffect(() => {
    let active = true;
    let initialReadinessRequestVersion = 0;
    listExportCandidates(projectId)
      .then(async (nextCandidates) => {
        if (!active) return;
        setCandidates(nextCandidates);
        const initiallySelected =
          nextCandidates.find((candidate) => candidate.status === 'succeeded') ?? nextCandidates[0];
        setCandidateId(initiallySelected?.id ?? '');
        if (!initiallySelected) {
          setMessage('No private candidate is available to evaluate for controlled export.');
          return;
        }
        const requestVersion = ++readinessRequestVersion.current;
        initialReadinessRequestVersion = requestVersion;
        const [nextReadiness, nextBundles] = await Promise.all([
          getExportReadiness(projectId, initiallySelected.id),
          listPrivateExportBundles(projectId, initiallySelected.id),
        ]);
        if (!active || requestVersion !== readinessRequestVersion.current) return;
        setReadiness(nextReadiness);
        setBundles(nextBundles);
        setMessage(
          nextReadiness.allowed
            ? 'The server returned a current controlled-export evidence result. Read every limitation before acknowledging.'
            : 'The server currently denies controlled export. Read the evidence gaps below; no bundle can be created from this screen.',
        );
      })
      .catch((error: unknown) => {
        if (
          !active ||
          (initialReadinessRequestVersion !== 0 &&
            initialReadinessRequestVersion !== readinessRequestVersion.current)
        )
          return;
        setLoadError(error instanceof Error ? error.message : 'Could not load private candidates.');
        setMessage('Private candidates are unavailable. Controlled export remains denied.');
      });
    return () => {
      active = false;
    };
  }, [projectId]);

  function chooseCandidate(nextCandidateId: string) {
    setCandidateId(nextCandidateId);
    setApproval(null);
    setAcknowledgements(initialAcknowledgements);
    setReadiness(null);
    setBundles([]);
    setLoadError(null);
    setMessage('Rechecking the server-owned controlled-export gate…');
    void refreshSelectedCandidate(nextCandidateId, true, false);
  }

  async function requestApproval() {
    if (!selectedCandidate || !canRequestApproval) return;
    setBusyAction('approval');
    setMessage(
      'Requesting a fresh server check and an acknowledgement bound to this exact revision…',
    );
    try {
      const nextApproval = await createExportApproval(
        projectId,
        selectedCandidate.id,
        acknowledgements,
        uniqueIdempotencyKey('phase6-approval'),
      );
      setApproval(nextApproval);
      setMessage(
        'The acknowledgement was recorded for this exact revision. It is not professional, safety, fit, or physical-use approval.',
      );
      await refreshSelectedCandidate(selectedCandidate.id, true, false);
    } catch (error: unknown) {
      setMessage(
        error instanceof Error
          ? error.message
          : 'The server did not record an acknowledgement for controlled export.',
      );
      await refreshSelectedCandidate(selectedCandidate.id, true, false);
    } finally {
      setBusyAction(null);
    }
  }

  async function createBundle() {
    if (!selectedCandidate || !approval?.id || !canCreateExport) return;
    setBusyAction('export');
    setMessage('Revalidating the exact revision before requesting the private bundle…');
    try {
      const bundle = await createPrivateExport(
        projectId,
        selectedCandidate.id,
        approval.id,
        uniqueIdempotencyKey('phase6-export'),
      );
      setBundles((current) => [bundle, ...current.filter((item) => item.id !== bundle.id)]);
      setMessage(
        'A private controlled-validation bundle was recorded after a fresh server check. It remains limited to its included report and controls.',
      );
      await refreshSelectedCandidate(selectedCandidate.id, true, false);
    } catch (error: unknown) {
      setMessage(
        error instanceof Error
          ? error.message
          : 'The private controlled-validation bundle was not created.',
      );
      await refreshSelectedCandidate(selectedCandidate.id, true);
    } finally {
      setBusyAction(null);
    }
  }

  async function downloadBundle(bundle: PrivateExportBundle) {
    if (bundle.status !== 'ready' || bundle.revoked_at || busyAction) return;
    setBusyAction('download');
    setMessage('Rechecking authorization before delivering the private bundle…');
    try {
      const content = await downloadPrivateExportBundle(projectId, bundle.id);
      const downloadUrl = URL.createObjectURL(content);
      const anchor = document.createElement('a');
      anchor.href = downloadUrl;
      anchor.download = bundle.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 0);
      setMessage(
        'The authenticated private bundle download began after a fresh server authorization check.',
      );
    } catch (error: unknown) {
      setMessage(
        error instanceof Error
          ? error.message
          : 'The private download link is no longer available.',
      );
      if (selectedCandidate) await refreshSelectedCandidate(selectedCandidate.id, true, false);
    } finally {
      setBusyAction(null);
    }
  }

  async function submitFeedback(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCandidate || !feedbackSummary.trim()) return;
    setBusyAction('feedback');
    setMessage('Recording private feedback without treating it as a safety conclusion…');
    try {
      await submitCandidateFeedback(projectId, selectedCandidate.id, {
        category: feedbackCategory,
        severity: feedbackSeverity,
        summary: feedbackSummary.trim(),
      });
      setFeedbackSummary('');
      setMessage('Private feedback was recorded. It does not establish fit, comfort, or safety.');
    } catch (error: unknown) {
      setMessage(
        error instanceof Error ? error.message : 'Private feedback could not be recorded.',
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function submitHazard(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCandidate || !hazardSummary.trim() || !hazardConfirmed) return;
    setBusyAction('hazard');
    setMessage('Reporting a potential hazard and blocking the current export path…');
    try {
      await reportCandidateHazard(projectId, selectedCandidate.id, {
        severity: hazardSeverity,
        summary: hazardSummary.trim(),
      });
      setApproval(null);
      setHazardSummary('');
      setHazardConfirmed(false);
      setMessage(
        'Potential hazard report recorded. The current export acknowledgement is no longer current; renewed review is required.',
      );
      await refreshSelectedCandidate(selectedCandidate.id, true, false);
    } catch (error: unknown) {
      setMessage(
        error instanceof Error ? error.message : 'Potential hazard report could not be recorded.',
      );
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <div className="max-w-5xl">
      <p className="af-eyebrow">Step 6 · controlled export boundary</p>
      <h1 className="mt-4 text-4xl font-bold tracking-tight">
        Review a private controlled-validation export.
      </h1>
      <p className="mt-4 max-w-3xl leading-7 text-[var(--af-muted)]">
        AccessForge checks server-owned lineage, deterministic validation, release controls, and
        current policy before it can assemble a private bundle. This workflow does not determine
        safety, clinical suitability, fit, strength, durability, printability, or permission for
        real-world use.
      </p>

      <section
        className="af-card mt-8 border-[var(--af-warning)] p-6"
        aria-labelledby="export-boundary-heading"
      >
        <p className="af-eyebrow text-[var(--af-warning)]">Default denied</p>
        <h2 id="export-boundary-heading" className="mt-2 text-xl font-bold">
          A user acknowledgement never overrides an evidence gap.
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--af-muted)]">
          The server must revalidate the exact candidate immediately before acknowledgement and
          again before bundling. Any changed revision, missing evidence, recalled release, stale
          approval, unavailable gate, or hazard report leaves export unavailable.
        </p>
      </section>

      <section className="af-card mt-8 p-6" aria-labelledby="candidate-heading">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="af-eyebrow">Exact revision</p>
            <h2 id="candidate-heading" className="mt-2 text-xl font-bold">
              Choose a private candidate
            </h2>
          </div>
          <Link className="af-button af-button-secondary" href={`/projects/${projectId}/designs`}>
            Open DesignSpec history
          </Link>
        </div>
        <label className="mt-5 block max-w-3xl" htmlFor="export-candidate">
          Candidate revision
          <select
            className="af-input mt-2"
            id="export-candidate"
            value={candidateId}
            disabled={candidates.length === 0 || Boolean(busyAction)}
            onChange={(event) => chooseCandidate(event.target.value)}
          >
            {candidates.length === 0 ? (
              <option value="">No private candidates recorded</option>
            ) : null}
            {candidates.map((candidate) => (
              <option key={candidate.id} value={candidate.id}>
                {candidateLabel(candidate)}
              </option>
            ))}
          </select>
        </label>
        {selectedCandidate ? (
          <dl className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metadata label="Candidate ID" value={selectedCandidate.id} />
            <Metadata
              label="Template release"
              value={`${selectedCandidate.template_id} · ${selectedCandidate.template_version}`}
            />
            <Metadata
              label="Compiler status"
              value={selectedCandidate.status.replaceAll('_', ' ')}
            />
            <Metadata
              label="Validation status"
              value={selectedCandidate.validation_status?.replaceAll('_', ' ') ?? 'Not recorded'}
            />
          </dl>
        ) : null}
      </section>

      <section className="af-card mt-8 p-6" aria-labelledby="readiness-heading" aria-live="polite">
        <p className="af-eyebrow">Server-owned gate</p>
        <h2 id="readiness-heading" className="mt-2 text-xl font-bold">
          {gateHeading(readiness, loadError)}
        </h2>
        <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
          {readiness?.allowed
            ? 'This indicates only that the current server controls permit the next controlled-export record. It is not a statement about a physical outcome.'
            : 'Until the server returns a complete, current result, this page treats controlled export as unavailable.'}
        </p>
        {loadError ? (
          <p className="mt-4 rounded-lg border border-[var(--af-danger)] bg-[#fff4f4] p-3 text-sm text-[var(--af-danger)]">
            {loadError}
          </p>
        ) : null}
        {readiness?.reasons.length ? (
          <ul className="mt-5 space-y-2" aria-label="Reasons controlled export is unavailable">
            {readiness.reasons.map((reason, index) => (
              <li
                className="rounded-lg border border-[var(--af-warning)] bg-[#fff8ed] p-3 text-sm"
                key={`${index}-${reason}`}
              >
                {reason}
              </li>
            ))}
          </ul>
        ) : readiness && !readiness.allowed ? (
          <p className="mt-5 rounded-lg border border-[var(--af-warning)] bg-[#fff8ed] p-3 text-sm">
            The server did not provide a usable completion reason. Controlled export remains denied.
          </p>
        ) : null}
        {readiness?.limitations ? (
          <p className="mt-5 rounded-lg border border-[var(--af-line)] bg-[var(--af-paper)] p-3 text-sm leading-6 text-[var(--af-muted)]">
            {readiness.limitations}
          </p>
        ) : null}
        {readiness ? (
          <dl className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Metadata label="Risk-decision hash" value={shortHash(readiness.risk_decision_hash)} />
            <Metadata
              label="Validation-report hash"
              value={shortHash(readiness.validation_report_hash)}
            />
            <Metadata
              label="Artifact-manifest hash"
              value={shortHash(readiness.artifact_manifest_hash)}
            />
          </dl>
        ) : null}
      </section>

      <section className="af-card mt-8 p-6" aria-labelledby="acknowledgement-heading">
        <p className="af-eyebrow">Exact-revision acknowledgement</p>
        <h2 id="acknowledgement-heading" className="mt-2 text-xl font-bold">
          Record acknowledgement only after the server gate is complete.
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--af-muted)]">
          Version <code>{acknowledgementVersion}</code>. The acknowledgement is bound to exact,
          immutable server-side lineage. It expires when relevant evidence changes or a hazard is
          reported.
        </p>
        <fieldset className="mt-5 space-y-4">
          <legend className="sr-only">Required acknowledgement statements</legend>
          {Object.entries(acknowledgementLabels).map(([key, label]) => {
            const acknowledgementKey = key as keyof typeof acknowledgementLabels;
            return (
              <label
                className="flex items-start gap-3 rounded-lg border border-[var(--af-line)] p-4"
                key={key}
              >
                <input
                  className="mt-1 h-4 w-4"
                  type="checkbox"
                  checked={acknowledgements[acknowledgementKey]}
                  disabled={!readiness?.allowed || Boolean(busyAction)}
                  onChange={(event) =>
                    setAcknowledgements((current) => ({
                      ...current,
                      [acknowledgementKey]: event.target.checked,
                    }))
                  }
                />
                <span className="text-sm leading-6">{label}</span>
              </label>
            );
          })}
        </fieldset>
        <div className="mt-6 flex flex-wrap items-center gap-4">
          <button
            className="af-button af-button-primary"
            type="button"
            disabled={!canRequestApproval}
            onClick={requestApproval}
          >
            {busyAction === 'approval' ? 'Recording…' : 'Record exact-revision acknowledgement'}
          </button>
          <span className="text-sm text-[var(--af-muted)]">
            {readiness?.allowed
              ? 'All three acknowledgements are required.'
              : 'Unavailable while the server gate is denied or unknown.'}
          </span>
        </div>
        {approval ? (
          <p className="mt-5 rounded-lg border border-[var(--af-primary)] bg-[#f0f7f2] p-3 text-sm">
            Current acknowledgement record: <code className="break-all">{approval.id}</code>
            {approval.approval_hash ? <> · hash {shortHash(approval.approval_hash)}</> : null}
          </p>
        ) : null}
      </section>

      <section className="af-card mt-8 p-6" aria-labelledby="bundle-heading">
        <p className="af-eyebrow">Private bundle</p>
        <h2 id="bundle-heading" className="mt-2 text-xl font-bold">
          Assemble only after fresh revalidation.
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--af-muted)]">
          Before any bundle is assembled, AccessForge rechecks the exact revision and verifies its
          private artifact hashes. A bundle is a record of those checks and stated limits; it is not
          a manufacturing instruction or a claim about a physical item.
        </p>
        <div className="mt-5 flex flex-wrap items-center gap-4">
          <button
            className="af-button af-button-primary"
            type="button"
            disabled={!canCreateExport}
            onClick={createBundle}
          >
            {busyAction === 'export'
              ? 'Revalidating…'
              : 'Create private controlled-validation bundle'}
          </button>
          <span className="text-sm text-[var(--af-muted)]">
            {approval?.id
              ? 'The server may still deny this if the acknowledgement or evidence is no longer current.'
              : 'An exact-revision acknowledgement is required first.'}
          </span>
        </div>
        {bundles.length ? (
          <div className="mt-6 space-y-3">
            {bundles.map((bundle) => {
              const available = bundle.status === 'ready' && !bundle.revoked_at;
              return (
                <article className="rounded-lg border border-[var(--af-line)] p-4" key={bundle.id}>
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <h3 className="font-semibold">{bundle.filename}</h3>
                      <p className="mt-1 text-sm text-[var(--af-muted)]">
                        Recorded {dateTime(bundle.created_at)} ·{' '}
                        {bundle.size_bytes.toLocaleString()} bytes
                      </p>
                      <p className="mt-1 break-all text-xs text-[var(--af-muted)]">
                        SHA-256 {bundle.checksum_sha256}
                      </p>
                    </div>
                    <button
                      className="af-button af-button-secondary"
                      type="button"
                      disabled={!available || Boolean(busyAction)}
                      onClick={() => downloadBundle(bundle)}
                    >
                      {bundle.revoked_at
                        ? 'Revoked'
                        : busyAction === 'download'
                          ? 'Preparing…'
                          : 'Get private download'}
                    </button>
                  </div>
                  {!available ? (
                    <p className="mt-3 text-sm text-[var(--af-danger)]">
                      This record is no longer available for download. Recheck the current server
                      gate.
                    </p>
                  ) : null}
                </article>
              );
            })}
          </div>
        ) : (
          <p className="mt-5 text-sm text-[var(--af-muted)]">
            No private controlled-validation bundle is recorded for this candidate.
          </p>
        )}
      </section>

      <section className="mt-8 grid gap-6 lg:grid-cols-2">
        <form className="af-card p-6" onSubmit={submitFeedback}>
          <p className="af-eyebrow">Private feedback</p>
          <h2 className="mt-2 text-xl font-bold">
            Record fit, comfort, breakage, or near-miss feedback.
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
            Reports are private observations, not verification of fit, comfort, or safety.
          </p>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label>
              Category
              <select
                className="af-input mt-2"
                value={feedbackCategory}
                onChange={(event) => setFeedbackCategory(event.target.value)}
              >
                <option value="fit">Fit observation</option>
                <option value="comfort">Comfort observation</option>
                <option value="breakage">Breakage or damage</option>
                <option value="near_miss">Near miss</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label>
              Reported severity
              <select
                className="af-input mt-2"
                value={feedbackSeverity}
                onChange={(event) => setFeedbackSeverity(event.target.value)}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>
          </div>
          <label className="mt-4 block">
            What did you observe?
            <textarea
              required
              className="af-input mt-2 min-h-32"
              value={feedbackSummary}
              disabled={!selectedCandidate || Boolean(busyAction)}
              onChange={(event) => setFeedbackSummary(event.target.value)}
            />
          </label>
          <button
            className="af-button af-button-secondary mt-5"
            type="submit"
            disabled={!selectedCandidate || !feedbackSummary.trim() || Boolean(busyAction)}
          >
            {busyAction === 'feedback' ? 'Recording…' : 'Record private feedback'}
          </button>
        </form>

        <form className="af-card border-[var(--af-danger)] p-6" onSubmit={submitHazard}>
          <p className="af-eyebrow text-[var(--af-danger)]">Potential hazard / recall signal</p>
          <h2 className="mt-2 text-xl font-bold">Report a potential hazardous result.</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
            This immediately asks the server to block the candidate’s current export path and
            invalidate its acknowledgement. It reports a concern; it does not make a diagnosis or
            safety determination.
          </p>
          <label className="mt-5 block">
            Reported severity
            <select
              className="af-input mt-2"
              value={hazardSeverity}
              onChange={(event) => setHazardSeverity(event.target.value)}
            >
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </label>
          <label className="mt-4 block">
            Describe the potential hazard
            <textarea
              required
              className="af-input mt-2 min-h-28"
              value={hazardSummary}
              disabled={!selectedCandidate || Boolean(busyAction)}
              onChange={(event) => setHazardSummary(event.target.value)}
            />
          </label>
          <label className="mt-4 flex items-start gap-3 text-sm leading-6">
            <input
              className="mt-1 h-4 w-4"
              type="checkbox"
              checked={hazardConfirmed}
              disabled={!selectedCandidate || Boolean(busyAction)}
              onChange={(event) => setHazardConfirmed(event.target.checked)}
            />
            <span>I want to report this potential hazard and block the current export path.</span>
          </label>
          <button
            className="af-button af-button-secondary mt-5 border-[var(--af-danger)] text-[var(--af-danger)]"
            type="submit"
            disabled={
              !selectedCandidate || !hazardSummary.trim() || !hazardConfirmed || Boolean(busyAction)
            }
          >
            {busyAction === 'hazard' ? 'Reporting…' : 'Report potential hazard'}
          </button>
        </form>
      </section>

      <p role="status" className="mt-8 text-sm text-[var(--af-muted)]">
        {message}
      </p>
    </div>
  );
}

function Metadata({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--af-line)] bg-[var(--af-paper)] p-3">
      <dt className="text-sm text-[var(--af-muted)]">{label}</dt>
      <dd className="mt-1 break-all font-semibold">{value}</dd>
    </div>
  );
}
