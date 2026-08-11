'use client';

import Link from 'next/link';
import { use, useState } from 'react';
import { useProjectClient, sha256Hex } from '../../project-api';

export default function CapturePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const client = useProjectClient();
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  async function upload(file: File, mediaType: 'still_image' | 'video') {
    setBusy(true);
    setMessage('Preparing a time-limited upload…');
    try {
      const presigned = await client.presignUpload(projectId, {
        media_type: mediaType,
        content_type: file.type,
        size_bytes: file.size,
        original_name: file.name,
      });
      const response = await fetch(presigned.upload_url, {
        method: 'PUT',
        headers: { 'Content-Type': file.type },
        body: file,
      });
      if (!response.ok)
        throw new Error('The direct upload did not complete. Try again or use text only.');
      await client.completeUpload(projectId, presigned.asset_id, {
        actual_size_bytes: file.size,
        checksum_sha256: await sha256Hex(file),
      });
      setMessage('Upload recorded. You can add a text observation or continue to measurements.');
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Could not upload this file.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="max-w-3xl">
      <p className="af-eyebrow">Step 2 · observation and capture</p>
      <h1 className="mt-4 text-4xl font-bold tracking-tight">Show only what feels comfortable.</h1>
      <p className="mt-4 leading-7 text-[var(--af-muted)]">
        You never need to hold a phone steady, repeat a painful action, speak, or use a camera.
        Text-only and manual measurement paths are complete options.
      </p>
      <div className="mt-8 grid gap-5 md:grid-cols-2">
        <Link className="af-card block p-6" href={`/projects/${projectId}/capture/observation`}>
          <p className="af-eyebrow">Recommended alternative</p>
          <h2 className="mt-3 text-xl font-bold">Use text only</h2>
          <p className="mt-2 leading-7 text-[var(--af-muted)]">
            Describe what happens in your own words, or skip observation entirely.
          </p>
        </Link>
        <div className="af-card p-6" aria-busy={busy}>
          <h2 className="text-xl font-bold">Upload a still image</h2>
          <p id="still-image-help" className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
            Only an allowlisted image type and size can be uploaded. The link expires.
          </p>
          <label className="mt-5 block font-semibold" htmlFor="still-image">
            Choose still image
          </label>
          <input
            className="af-input mt-2"
            id="still-image"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            disabled={busy}
            aria-describedby="still-image-help"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void upload(file, 'still_image');
            }}
          />
        </div>
        <div className="af-card p-6" aria-busy={busy}>
          <h2 className="text-xl font-bold">Upload a short video</h2>
          <p id="video-help" className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
            Video is off unless you granted separate video consent. No action needs to be repeated.
          </p>
          <label className="mt-5 block font-semibold" htmlFor="video">
            Choose short video
          </label>
          <input
            className="af-input mt-2"
            id="video"
            type="file"
            accept="video/mp4,video/webm"
            disabled={busy}
            aria-describedby="video-help"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void upload(file, 'video');
            }}
          />
        </div>
        <div className="af-card p-6">
          <h2 className="text-xl font-bold">Printable scale marker</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
            Print at actual size if you later choose a still image. A ruler or caliper is always
            acceptable.
          </p>
          <a
            className="af-button af-button-secondary mt-5"
            href="/accessforge-marker.svg"
            target="_blank"
            rel="noreferrer"
          >
            Open marker
          </a>
        </div>
      </div>
      <div className="mt-8 flex flex-wrap items-center gap-4">
        <Link className="af-button af-button-primary" href={`/projects/${projectId}/measurements`}>
          Continue to measurements
        </Link>
        <Link className="af-button af-button-secondary" href={`/projects/${projectId}`}>
          Back to project
        </Link>
        <span role="status" className="text-sm text-[var(--af-muted)]">
          {message}
        </span>
      </div>
    </div>
  );
}
