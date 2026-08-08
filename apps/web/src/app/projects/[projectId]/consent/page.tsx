'use client';

import Link from 'next/link';
import { use, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useProjectClient } from '../../project-api';

const choices = [
  ['project_text', 'Use my project text and notes'],
  ['still_images', 'Upload still images of the object'],
  ['video', 'Upload a short video'],
  ['helper_access', 'Let a helper or co-designer assist'],
  ['ai_provider_sharing', 'Share selected derived text and measurements with an AI provider later'],
  ['community_publishing', 'Publish something to the community later'],
  ['future_contact', 'Contact me about future testing'],
] as const;

export default function ConsentPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const client = useProjectClient();
  const router = useRouter();
  const [displayName, setDisplayName] = useState('Me');
  const [role, setRole] = useState<'participant' | 'co_designer' | 'helper'>('participant');
  const [selected, setSelected] = useState<Record<string, boolean>>({ project_text: true });
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  function toggle(key: string) {
    setSelected((current) => ({ ...current, [key]: !current[key] }));
  }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage('Recording your choices…');
    try {
      await client.createConsent(projectId, { display_name: displayName, role, choices: selected });
      router.push(`/projects/${projectId}`);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Could not record consent.');
      setBusy(false);
    }
  }
  return (
    <div className="max-w-3xl">
      <p className="af-eyebrow">Step 1 · consent and co-design</p>
      <h1 className="mt-4 text-4xl font-bold tracking-tight">Choose what you want to share.</h1>
      <p className="mt-4 leading-7 text-[var(--af-muted)]">
        Each choice is separate. Saying no to an optional activity does not prevent a text-only
        project.
      </p>
      <form className="af-card mt-8 space-y-6 p-7" onSubmit={submit}>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <label className="font-semibold" htmlFor="display-name">
              Participant name or nickname
            </label>
            <input
              required
              className="af-input mt-2"
              id="display-name"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
            />
          </div>
          <div>
            <label className="font-semibold" htmlFor="role">
              Your role
            </label>
            <select
              className="af-input mt-2"
              id="role"
              value={role}
              onChange={(event) => setRole(event.target.value as typeof role)}
            >
              <option value="participant">Person who will use the adapter</option>
              <option value="co_designer">Co-designer</option>
              <option value="helper">Helper</option>
            </select>
          </div>
        </div>
        <fieldset>
          <legend className="font-semibold">Optional data choices</legend>
          <div className="mt-4 space-y-3">
            {choices.map(([key, label]) => (
              <label className="flex gap-3 rounded-lg border border-[var(--af-line)] p-4" key={key}>
                <input
                  className="mt-1 h-5 w-5"
                  type="checkbox"
                  checked={Boolean(selected[key])}
                  onChange={() => toggle(key)}
                />
                <span>
                  <span className="font-semibold">{label}</span>
                  <span className="mt-1 block text-sm leading-6 text-[var(--af-muted)]">
                    You can change or revoke this choice later.
                  </span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <div className="flex flex-wrap items-center gap-4">
          <button
            className="af-button af-button-primary"
            type="submit"
            disabled={busy || !selected.project_text}
          >
            {busy ? 'Recording…' : 'Continue with these choices'}
          </button>
          <Link className="af-button af-button-secondary" href={`/projects/${projectId}`}>
            Back to project
          </Link>
          <span role="status" className="text-sm text-[var(--af-muted)]">
            {message}
          </span>
        </div>
      </form>
    </div>
  );
}
