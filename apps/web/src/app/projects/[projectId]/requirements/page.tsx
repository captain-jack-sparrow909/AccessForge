'use client';

import Link from 'next/link';
import { use, useEffect, useMemo, useState } from 'react';
import type {
  ModelProviderConfig,
  RequirementProposal,
  RequirementRevision,
} from '@accessforge/api-client';
import { useProjectClient } from '../../project-api';

type EditableRequirement = RequirementProposal & { id?: string };

export default function RequirementsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const client = useProjectClient();
  const [revisions, setRevisions] = useState<RequirementRevision[]>([]);
  const [providers, setProviders] = useState<ModelProviderConfig[]>([]);
  const [selectedProvider, setSelectedProvider] = useState('');
  const [editable, setEditable] = useState<EditableRequirement[]>([]);
  const [editing, setEditing] = useState(false);
  const [message, setMessage] = useState('Loading requirements…');
  const [busy, setBusy] = useState(false);
  const activeRevision = revisions[0] ?? null;
  const usableProviders = useMemo(
    () => providers.filter((provider) => provider.status === 'ready'),
    [providers],
  );
  function load() {
    Promise.all([client.listRequirements(projectId), client.listModelProviders()])
      .then(([nextRevisions, nextProviders]) => {
        setRevisions(nextRevisions);
        setProviders(nextProviders);
        if (!selectedProvider && nextProviders.length > 0) setSelectedProvider(nextProviders[0].id);
        setMessage('');
      })
      .catch((error: unknown) =>
        setMessage(error instanceof Error ? error.message : 'Could not load requirements.'),
      );
  }
  useEffect(() => {
    load();
    // The client instance is stable for the mounted page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, projectId]);
  function beginEditing(revision: RequirementRevision) {
    setEditable(revision.requirements.map(({ id: _id, provenance: _provenance, ...item }) => item));
    setEditing(true);
  }
  function changeRequirement(index: number, patch: Partial<EditableRequirement>) {
    setEditable((current) =>
      current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    );
  }
  async function extract() {
    setBusy(true);
    setMessage('Creating an editable proposal from the selected text and measurements…');
    try {
      const revision = await client.extractRequirements(
        projectId,
        selectedProvider ? { provider_config_id: selectedProvider } : {},
      );
      setRevisions((current) => [revision, ...current]);
      setEditable(
        revision.requirements.map(({ id: _id, provenance: _provenance, ...item }) => item),
      );
      setEditing(true);
      setMessage('Proposal ready. Review and correct every item before confirming.');
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Could not create a proposal.');
    } finally {
      setBusy(false);
    }
  }
  async function confirm() {
    if (!activeRevision) return;
    setBusy(true);
    setMessage('Creating an immutable confirmed revision…');
    try {
      const revision = await client.confirmRequirements(projectId, activeRevision.id, {
        requirements: editable.map(({ id: _id, ...item }) => item),
        unknowns: activeRevision.unknowns,
        clarifying_questions: activeRevision.clarifying_questions,
        risk_signals: activeRevision.risk_signals,
        rationale: activeRevision.rationale ?? undefined,
      });
      setRevisions((current) => [revision, ...current]);
      setEditing(false);
      setMessage('Confirmed revision saved. Later risk review has not been performed yet.');
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Could not confirm this revision.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="max-w-5xl">
      <p className="af-eyebrow">Step 4 · editable requirements</p>
      <h1 className="mt-4 text-4xl font-bold tracking-tight">Check what AccessForge understood.</h1>
      <p className="mt-4 max-w-3xl leading-7 text-[var(--af-muted)]">
        AI suggestions are proposals, not facts. Only the selected derived text and measurements may
        be sent to a provider, never raw photos or video. You can correct every item before creating
        a confirmed revision.
      </p>
      <section className="af-card mt-8 p-7" aria-labelledby="proposal-heading">
        <h2 id="proposal-heading" className="text-xl font-bold">
          Create a proposal
        </h2>
        <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
          External providers require the separate “AI-provider sharing” consent choice from your
          project. An offline fake provider is clearly marked synthetic and available only in
          development.
        </p>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row">
          <label className="sr-only" htmlFor="requirements-provider">
            Provider configuration
          </label>
          <select
            className="af-input flex-1"
            id="requirements-provider"
            value={selectedProvider}
            onChange={(event) => setSelectedProvider(event.target.value)}
          >
            <option value="">Choose a provider configuration</option>
            {usableProviders.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.label} · {provider.status}
              </option>
            ))}
          </select>
          <button
            className="af-button af-button-primary"
            type="button"
            disabled={busy || !selectedProvider}
            onClick={() => void extract()}
          >
            {busy ? 'Working…' : 'Create editable proposal'}
          </button>
        </div>
        {usableProviders.length === 0 ? (
          <p className="mt-4 text-sm text-[var(--af-muted)]">
            No configuration is available.{' '}
            <Link className="underline underline-offset-4" href="/settings/models">
              Add a provider configuration
            </Link>{' '}
            or continue your project without AI.
          </p>
        ) : null}
      </section>
      {activeRevision ? (
        <section className="mt-9" aria-labelledby="revision-heading">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="af-eyebrow">Revision {activeRevision.revision_number}</p>
              <h2 id="revision-heading" className="mt-2 text-2xl font-bold">
                {activeRevision.status === 'confirmed'
                  ? 'Confirmed requirements'
                  : 'Review this proposal'}
              </h2>
            </div>
            {!editing && activeRevision.status !== 'confirmed' ? (
              <button
                className="af-button af-button-secondary"
                type="button"
                onClick={() => beginEditing(activeRevision)}
              >
                Edit proposal
              </button>
            ) : null}
          </div>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--af-muted)]">
            {activeRevision.rationale || 'No additional rationale was provided.'}
          </p>
          {editing ? (
            <div className="mt-6 space-y-4">
              {editable.map((item, index) => (
                <EditableCard
                  key={`${item.kind}-${index}`}
                  item={item}
                  index={index}
                  onChange={changeRequirement}
                  onRemove={() =>
                    setEditable((current) => current.filter((_, itemIndex) => itemIndex !== index))
                  }
                />
              ))}
              <button
                className="af-button af-button-secondary"
                type="button"
                onClick={() =>
                  setEditable((current) => [
                    ...current,
                    {
                      kind: 'user_goal',
                      value_number: null,
                      value_text: '',
                      unit: null,
                      source_refs: ['user:confirmation'],
                      confidence: 1,
                      needs_confirmation: false,
                      explanation: 'Added by you.',
                    },
                  ])
                }
              >
                Add a requirement
              </button>
            </div>
          ) : (
            <RequirementCards revision={activeRevision} />
          )}
          <SupportLists revision={activeRevision} />
          {editing ? (
            <div className="mt-7 flex flex-wrap gap-4">
              <button
                className="af-button af-button-primary"
                type="button"
                disabled={busy}
                onClick={() => void confirm()}
              >
                {busy ? 'Saving…' : 'Confirm this revision'}
              </button>
              <button
                className="af-button af-button-secondary"
                type="button"
                disabled={busy}
                onClick={() => {
                  setEditing(false);
                  setEditable([]);
                }}
              >
                Cancel edits
              </button>
            </div>
          ) : null}
        </section>
      ) : (
        <section className="af-card mt-9 p-7">
          <h2 className="text-xl font-bold">No requirements proposal yet</h2>
          <p className="mt-2 text-[var(--af-muted)]">
            You can proceed without AI. When you decide to use it, make sure your provider and
            consent choices are set.
          </p>
        </section>
      )}
      <p role="status" className="mt-8 text-sm text-[var(--af-muted)]">
        {message}
      </p>
    </div>
  );
}

function EditableCard({
  item,
  index,
  onChange,
  onRemove,
}: {
  item: EditableRequirement;
  index: number;
  onChange: (index: number, patch: Partial<EditableRequirement>) => void;
  onRemove: () => void;
}) {
  const isNumeric = item.value_number !== null;
  return (
    <fieldset className="af-card p-5">
      <legend className="sr-only">Requirement {index + 1}</legend>
      <div className="flex flex-wrap justify-between gap-3">
        <p className="font-bold">Requirement {index + 1}</p>
        <button
          className="text-sm text-[var(--af-danger)] underline underline-offset-4"
          type="button"
          onClick={onRemove}
        >
          Remove
        </button>
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label>
          Kind
          <input
            className="af-input mt-1"
            value={item.kind}
            onChange={(event) => onChange(index, { kind: event.target.value })}
          />
        </label>
        <label>
          Confidence (0–1)
          <input
            className="af-input mt-1"
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={item.confidence}
            onChange={(event) => onChange(index, { confidence: Number(event.target.value) })}
          />
        </label>
      </div>
      <fieldset className="mt-4">
        <legend className="font-semibold">Value type</legend>
        <label className="mr-4 inline-flex gap-2">
          <input
            type="radio"
            checked={isNumeric}
            onChange={() =>
              onChange(index, { value_number: 0, value_text: null, unit: item.unit || 'mm' })
            }
          />
          Number
        </label>
        <label className="inline-flex gap-2">
          <input
            type="radio"
            checked={!isNumeric}
            onChange={() => onChange(index, { value_number: null, value_text: '', unit: null })}
          />
          Text
        </label>
      </fieldset>
      {isNumeric ? (
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label>
            Value
            <input
              className="af-input mt-1"
              type="number"
              step="any"
              value={item.value_number ?? ''}
              onChange={(event) => onChange(index, { value_number: Number(event.target.value) })}
            />
          </label>
          <label>
            Unit
            <input
              className="af-input mt-1"
              value={item.unit ?? ''}
              onChange={(event) => onChange(index, { unit: event.target.value })}
            />
          </label>
        </div>
      ) : (
        <label className="mt-4 block">
          Value
          <input
            className="af-input mt-1"
            value={item.value_text ?? ''}
            onChange={(event) => onChange(index, { value_text: event.target.value })}
          />
        </label>
      )}
      <label className="mt-4 block">
        Explanation
        <textarea
          className="af-input mt-1 min-h-20"
          value={item.explanation}
          onChange={(event) => onChange(index, { explanation: event.target.value })}
        />
      </label>
      <label className="mt-4 flex gap-3">
        <input
          className="mt-1 h-5 w-5"
          type="checkbox"
          checked={item.needs_confirmation}
          onChange={(event) => onChange(index, { needs_confirmation: event.target.checked })}
        />
        <span>Still needs confirmation</span>
      </label>
      <p className="mt-4 text-sm text-[var(--af-muted)]">
        Sources: {item.source_refs.join(', ') || 'No source selected'}
      </p>
    </fieldset>
  );
}

function RequirementCards({ revision }: { revision: RequirementRevision }) {
  return (
    <ul className="mt-6 grid gap-4 md:grid-cols-2">
      {revision.requirements.map((item) => (
        <li className="af-card p-5" key={item.id}>
          <p className="text-sm font-semibold text-[var(--af-primary)]">
            {revision.source === 'ai_proposal' ? 'Suggested by AccessForge' : 'Confirmed by you'}
          </p>
          <h3 className="mt-2 text-lg font-bold">{item.kind.replaceAll('_', ' ')}</h3>
          <p className="mt-2 font-semibold">
            {item.value_number !== null ? `${item.value_number} ${item.unit}` : item.value_text}
          </p>
          <p className="mt-3 text-sm leading-6 text-[var(--af-muted)]">{item.explanation}</p>
          <dl className="mt-4 text-sm text-[var(--af-muted)]">
            <div>
              <dt className="inline">Sources: </dt>
              <dd className="inline">{item.source_refs.join(', ')}</dd>
            </div>
            <div>
              <dt className="inline">Confidence: </dt>
              <dd className="inline">{Math.round(item.confidence * 100)}%</dd>
            </div>
            <div>
              <dt className="inline">Status: </dt>
              <dd className="inline">
                {item.needs_confirmation ? 'Needs confirmation' : 'Confirmed'}
              </dd>
            </div>
          </dl>
        </li>
      ))}
    </ul>
  );
}

function SupportLists({ revision }: { revision: RequirementRevision }) {
  return (
    <div className="mt-7 grid gap-5 md:grid-cols-3">
      {revision.unknowns.length > 0 ? (
        <section className="af-card p-5">
          <h3 className="font-bold">Still unknown</h3>
          <ul className="mt-3 space-y-3 text-sm leading-6 text-[var(--af-muted)]">
            {revision.unknowns.map((item) => (
              <li key={item.kind}>
                <span className="font-semibold text-[var(--af-ink)]">
                  {item.kind.replaceAll('_', ' ')}
                </span>
                <br />
                {item.explanation}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {revision.clarifying_questions.length > 0 ? (
        <section className="af-card p-5">
          <h3 className="font-bold">Questions to consider</h3>
          <ol className="mt-3 space-y-3 text-sm leading-6 text-[var(--af-muted)]">
            {revision.clarifying_questions.map((item) => (
              <li key={item.id}>
                <span className="font-semibold text-[var(--af-ink)]">{item.question}</span>
                <br />
                {item.why_it_matters}
              </li>
            ))}
          </ol>
        </section>
      ) : null}
      {revision.risk_signals.length > 0 ? (
        <section className="af-card border-[var(--af-warning)] p-5">
          <h3 className="font-bold">Needs attention</h3>
          <ul className="mt-3 space-y-3 text-sm leading-6 text-[var(--af-muted)]">
            {revision.risk_signals.map((item) => (
              <li key={item.kind}>
                <span className="font-semibold text-[var(--af-ink)]">
                  {item.level.replaceAll('_', ' ')}: {item.kind.replaceAll('_', ' ')}
                </span>
                <br />
                {item.explanation}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
