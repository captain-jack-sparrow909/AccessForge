'use client';

import Link from 'next/link';
import { use, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useProjectClient } from '../../../project-api';

export default function ObservationPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const client = useProjectClient();
  const router = useRouter();
  const [text, setText] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  async function save(inputMode: 'text' | 'skipped') {
    setBusy(true);
    setMessage('Saving observation…');
    try {
      await client.createObservation(projectId, { text, input_mode: inputMode });
      router.push(`/projects/${projectId}/measurements`);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Could not save observation.');
      setBusy(false);
    }
  }
  return (
    <div className="max-w-3xl">
      <p className="af-eyebrow">Text-only observation</p>
      <h1 className="mt-4 text-4xl font-bold tracking-tight">What happens when you try?</h1>
      <p className="mt-4 leading-7 text-[var(--af-muted)]">
        You can describe the object, the movement, what makes it difficult, and what currently
        helps. Do not repeat an action that causes pain or fatigue.
      </p>
      <div className="af-card mt-8 p-7">
        <label className="font-semibold" htmlFor="observation">
          Your observation
        </label>
        <textarea
          className="af-input mt-2 min-h-48"
          id="observation"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Example: The zipper tab is small and slips between my fingers. A larger loop would be easier to pull."
        />
        <div className="mt-6 flex flex-wrap items-center gap-4">
          <button
            className="af-button af-button-primary"
            type="button"
            disabled={busy || !text.trim()}
            onClick={() => void save('text')}
          >
            Save observation
          </button>
          <button
            className="af-button af-button-secondary"
            type="button"
            disabled={busy}
            onClick={() => void save('skipped')}
          >
            Skip observation
          </button>
          <Link className="af-button af-button-secondary" href={`/projects/${projectId}/capture`}>
            Back
          </Link>
          <span role="status" className="text-sm text-[var(--af-muted)]">
            {message}
          </span>
        </div>
      </div>
    </div>
  );
}
