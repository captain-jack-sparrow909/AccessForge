'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useProjectClient } from '../project-api';

export default function NewProjectForm() {
  const client = useProjectClient();
  const router = useRouter();
  const [form, setForm] = useState({
    name: '',
    goal: '',
    object_description: '',
    action_description: '',
    environment: 'indoors, room temperature',
    load_context: 'low',
    safety_system: 'unknown',
    age_context: 'adult',
  });
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  function update(field: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage('Saving your private project…');
    try {
      const project = await client.createProject({
        name: form.name,
        goal: form.goal,
        object_description: form.object_description,
        action_description: form.action_description,
        environment: form.environment,
        load_context: form.load_context,
        safety_system:
          form.safety_system === 'yes' ? true : form.safety_system === 'no' ? false : undefined,
        age_context: form.age_context,
      });
      router.push(`/projects/${project.id}/consent`);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Could not save the project.');
      setBusy(false);
    }
  }
  return (
    <div className="af-container af-section grid gap-10 lg:grid-cols-[0.68fr_1.32fr] lg:items-start">
      <aside className="lg:sticky lg:top-28">
        <span className="af-badge">
          <span className="af-badge-dot" aria-hidden="true" />
          New private project
        </span>
        <h1 className="mt-6 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
          What would you like to be able to do?
        </h1>
        <p className="mt-5 max-w-xl leading-7 text-[var(--af-muted)]">
          Describe the outcome in your own words. You do not need to name a diagnosis or explain
          your body. Unknown answers stay unknown and pause later design work.
        </p>
        <div className="mt-8 grid gap-3 text-sm text-[var(--af-ink-soft)]">
          {[
            'Your project starts private',
            'Text is enough to begin',
            'Unknown answers remain visible',
          ].map((item) => (
            <p className="flex items-center gap-3 font-semibold" key={item}>
              <span
                className="grid h-7 w-7 place-items-center rounded-lg bg-[var(--af-primary-soft)] text-[var(--af-primary-dark)]"
                aria-hidden="true"
              >
                ✓
              </span>
              {item}
            </p>
          ))}
        </div>
      </aside>
      <form className="af-card space-y-7 p-6 sm:p-9" onSubmit={submit}>
        <div className="border-b border-[var(--af-line)] pb-6">
          <p className="text-sm font-extrabold uppercase tracking-[0.12em] text-[var(--af-primary)]">
            Project brief
          </p>
          <h2 className="mt-2 text-2xl font-extrabold">Start with the everyday interaction</h2>
        </div>
        <div>
          <label className="font-semibold" htmlFor="name">
            Project name
          </label>
          <input
            required
            className="af-input mt-2"
            id="name"
            value={form.name}
            onChange={(event) => update('name', event.target.value)}
          />
        </div>
        <div>
          <label className="font-semibold" htmlFor="goal">
            What outcome do you want?
          </label>
          <textarea
            required
            className="af-input mt-2 min-h-28"
            id="goal"
            value={form.goal}
            onChange={(event) => update('goal', event.target.value)}
          />
          <p className="mt-2 text-sm text-[var(--af-muted)]">
            Example: “I want to pull my jacket zipper without pinching the small tab.”
          </p>
        </div>
        <div>
          <label className="font-semibold" htmlFor="object">
            What object is involved?
          </label>
          <textarea
            required
            className="af-input mt-2 min-h-24"
            id="object"
            value={form.object_description}
            onChange={(event) => update('object_description', event.target.value)}
          />
        </div>
        <div>
          <label className="font-semibold" htmlFor="action">
            What action is difficult or tiring?
          </label>
          <textarea
            required
            className="af-input mt-2 min-h-24"
            id="action"
            value={form.action_description}
            onChange={(event) => update('action_description', event.target.value)}
          />
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <label className="font-semibold" htmlFor="environment">
              Where and at what temperature?
            </label>
            <input
              required
              className="af-input mt-2"
              id="environment"
              value={form.environment}
              onChange={(event) => update('environment', event.target.value)}
            />
          </div>
          <div>
            <label className="font-semibold" htmlFor="load">
              How much force or load is involved?
            </label>
            <select
              className="af-input mt-2"
              id="load"
              value={form.load_context}
              onChange={(event) => update('load_context', event.target.value)}
            >
              <option value="low">Low / gentle pull or grip</option>
              <option value="medium">Medium / not sure</option>
              <option value="high">High force</option>
              <option value="unknown">I do not know yet</option>
            </select>
          </div>
          <div>
            <label className="font-semibold" htmlFor="safety-system">
              Is this part of a safety system or access control?
            </label>
            <select
              className="af-input mt-2"
              id="safety-system"
              value={form.safety_system}
              onChange={(event) => update('safety_system', event.target.value)}
            >
              <option value="unknown">I do not know yet</option>
              <option value="no">No</option>
              <option value="yes">Yes</option>
            </select>
          </div>
          <div>
            <label className="font-semibold" htmlFor="age-context">
              Who will use it?
            </label>
            <select
              className="af-input mt-2"
              id="age-context"
              value={form.age_context}
              onChange={(event) => update('age_context', event.target.value)}
            >
              <option value="adult">Adult</option>
              <option value="older_adult">Older adult</option>
              <option value="unknown">I do not know yet</option>
            </select>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-4 border-t border-[var(--af-line)] pt-6">
          <button className="af-button af-button-primary" type="submit" disabled={busy}>
            {busy ? 'Saving…' : 'Continue'} <span aria-hidden="true">→</span>
          </button>
          <button
            className="af-button af-button-secondary"
            type="button"
            onClick={() => router.push('/dashboard')}
          >
            Save and return later
          </button>
          <span role="status" className="text-sm text-[var(--af-muted)]">
            {message}
          </span>
        </div>
      </form>
    </div>
  );
}
