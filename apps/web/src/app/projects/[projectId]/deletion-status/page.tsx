'use client';

import Link from 'next/link';
import { use, useEffect, useState } from 'react';
import type { DeletionStatus } from '@accessforge/api-client';
import { useProjectClient } from '../../project-api';

function readableStatus(value: string) {
  return value.replaceAll('_', ' ');
}

function readableTime(value: string | null) {
  return value ? new Date(value).toLocaleString() : 'Not recorded';
}

export default function DeletionStatusPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const client = useProjectClient();
  const [deletionStatus, setDeletionStatus] = useState<DeletionStatus | null>(null);
  const [message, setMessage] = useState('Loading deletion status…');
  const [isRefreshing, setIsRefreshing] = useState(false);

  async function loadStatus(isManualRefresh = false) {
    setIsRefreshing(isManualRefresh);
    setMessage(isManualRefresh ? 'Refreshing deletion status…' : 'Loading deletion status…');
    try {
      const nextStatus = await client.getDeletionStatus(projectId);
      setDeletionStatus(nextStatus);
      setMessage('');
    } catch (error: unknown) {
      setMessage(
        error instanceof Error ? error.message : 'Could not load the private deletion status.',
      );
    } finally {
      setIsRefreshing(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    void client
      .getDeletionStatus(projectId)
      .then((nextStatus) => {
        if (!cancelled) {
          setDeletionStatus(nextStatus);
          setMessage('');
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setMessage(
            error instanceof Error ? error.message : 'Could not load the private deletion status.',
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [client, projectId]);

  return (
    <div className="max-w-3xl">
      <p className="af-eyebrow">Private data lifecycle</p>
      <h1 className="mt-4 text-4xl font-bold tracking-tight">Deletion status</h1>
      <p className="mt-4 max-w-2xl leading-7 text-[var(--af-muted)]">
        The project is no longer available for ordinary use. This page shows only the safe cleanup
        status, not object names, storage details, credentials, or requester information.
      </p>

      {deletionStatus ? (
        <section className="af-card mt-8 p-6" aria-labelledby="deletion-status-heading">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 id="deletion-status-heading" className="text-xl font-bold">
                Cleanup is {readableStatus(deletionStatus.status)}
              </h2>
              <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
                Automatic cleanup is bounded and auditable. A status of manual review required means
                it stopped rather than silently declaring private data removed.
              </p>
            </div>
            <button
              className="af-button af-button-secondary"
              type="button"
              disabled={isRefreshing}
              onClick={() => void loadStatus(true)}
            >
              {isRefreshing ? 'Refreshing…' : 'Refresh status'}
            </button>
          </div>
          <dl className="mt-6 grid gap-4 sm:grid-cols-2">
            <StatusFact label="Requested" value={readableTime(deletionStatus.requested_at)} />
            <StatusFact label="Attempts" value={String(deletionStatus.attempt_count)} />
            <StatusFact
              label="Current lease began"
              value={readableTime(deletionStatus.started_at)}
            />
            <StatusFact
              label="Next automatic retry"
              value={readableTime(deletionStatus.next_attempt_at)}
            />
            <StatusFact
              label="Last safe error category"
              value={deletionStatus.last_error_code ?? 'None'}
            />
            <StatusFact
              label="Last error recorded"
              value={readableTime(deletionStatus.last_error_at)}
            />
            <StatusFact
              label="Empty prefix confirmations"
              value={String(deletionStatus.reconciliation_passes)}
            />
            <StatusFact
              label="Last prefix confirmation"
              value={readableTime(deletionStatus.last_reconciled_at)}
            />
            <StatusFact label="Completed" value={readableTime(deletionStatus.completed_at)} />
          </dl>
        </section>
      ) : null}

      <p role="status" className="mt-6 text-sm text-[var(--af-muted)]">
        {message}
      </p>
      <Link className="af-button af-button-secondary mt-6" href="/dashboard">
        Return to projects
      </Link>
    </div>
  );
}

function StatusFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--af-line)] bg-[var(--af-paper)] p-4">
      <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--af-muted)]">
        {label}
      </dt>
      <dd className="mt-2 break-words text-sm font-medium">{value}</dd>
    </div>
  );
}
