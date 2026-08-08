'use client';

import Link from 'next/link';
import { use, useEffect, useState } from 'react';
import type { Measurement } from '@accessforge/api-client';
import { useProjectClient } from '../../project-api';

export default function MeasurementsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const client = useProjectClient();
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [form, setForm] = useState({
    kind: 'grip diameter',
    value: '',
    unit: 'mm' as 'mm' | 'cm' | 'in',
    tolerance: '',
    method: 'ruler' as 'ruler' | 'caliper' | 'visual_estimate' | 'other',
    confirmed: false,
    unknown: false,
    notes: '',
  });
  const [message, setMessage] = useState('Loading measurements…');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    client
      .listMeasurements(projectId)
      .then((items) => {
        if (active) {
          setMeasurements(items);
          setMessage('');
        }
      })
      .catch((error: unknown) => {
        if (active)
          setMessage(error instanceof Error ? error.message : 'Could not load measurements.');
      });
    return () => {
      active = false;
    };
  }, [client, projectId]);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage('Saving measurement…');
    try {
      const measurement = await client.createMeasurement(projectId, {
        kind: form.kind,
        ...(form.unknown ? {} : { value: Number(form.value) }),
        unit: form.unit,
        ...(form.tolerance ? { tolerance: Number(form.tolerance) } : {}),
        method: form.method,
        confirmed: form.confirmed,
        unknown: form.unknown,
        notes: form.notes || undefined,
      });
      setMeasurements((current) => [...current, measurement]);
      setMessage('Measurement recorded. You can add another or continue.');
      setForm((current) => ({
        ...current,
        value: '',
        tolerance: '',
        notes: '',
        confirmed: false,
        unknown: false,
      }));
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Could not save measurement.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="max-w-4xl">
      <p className="af-eyebrow">Step 3 · manual measurements</p>
      <h1 className="mt-4 text-4xl font-bold tracking-tight">
        Measurements are suggestions, not a test.
      </h1>
      <p className="mt-4 max-w-2xl leading-7 text-[var(--af-muted)]">
        Use a ruler, caliper, or a careful visual estimate. Unknown values stay unknown; AccessForge
        will not fill them in.
      </p>
      <form className="af-card mt-8 space-y-6 p-7" onSubmit={submit}>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <label className="font-semibold" htmlFor="kind">
              What are you measuring?
            </label>
            <input
              required
              className="af-input mt-2"
              id="kind"
              value={form.kind}
              onChange={(event) => setForm({ ...form, kind: event.target.value })}
            />
          </div>
          <div>
            <label className="font-semibold" htmlFor="method">
              Method
            </label>
            <select
              className="af-input mt-2"
              id="method"
              value={form.method}
              onChange={(event) =>
                setForm({ ...form, method: event.target.value as typeof form.method })
              }
            >
              <option value="ruler">Ruler</option>
              <option value="caliper">Caliper</option>
              <option value="visual_estimate">Visual estimate</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label className="font-semibold" htmlFor="value">
              Value
            </label>
            <input
              className="af-input mt-2"
              id="value"
              type="number"
              min="0"
              step="any"
              inputMode="decimal"
              disabled={form.unknown}
              required={!form.unknown}
              value={form.value}
              onChange={(event) => setForm({ ...form, value: event.target.value })}
            />
          </div>
          <div>
            <label className="font-semibold" htmlFor="unit">
              Unit
            </label>
            <select
              className="af-input mt-2"
              id="unit"
              value={form.unit}
              onChange={(event) =>
                setForm({ ...form, unit: event.target.value as typeof form.unit })
              }
            >
              <option value="mm">millimetres (mm)</option>
              <option value="cm">centimetres (cm)</option>
              <option value="in">inches (in)</option>
            </select>
          </div>
          <div>
            <label className="font-semibold" htmlFor="tolerance">
              Tolerance (optional, same unit)
            </label>
            <input
              className="af-input mt-2"
              id="tolerance"
              type="number"
              min="0"
              step="any"
              inputMode="decimal"
              disabled={form.unknown}
              value={form.tolerance}
              onChange={(event) => setForm({ ...form, tolerance: event.target.value })}
            />
          </div>
          <div className="flex items-end gap-3 pb-2">
            <input
              className="h-5 w-5"
              id="unknown"
              type="checkbox"
              checked={form.unknown}
              onChange={(event) =>
                setForm({ ...form, unknown: event.target.checked, confirmed: false })
              }
            />
            <label htmlFor="unknown">
              <span className="font-semibold">I do not know yet</span>
              <span className="mt-1 block text-sm text-[var(--af-muted)]">
                Leave this value unresolved.
              </span>
            </label>
          </div>
        </div>
        <div>
          <label className="font-semibold" htmlFor="notes">
            Notes (optional)
          </label>
          <textarea
            className="af-input mt-2 min-h-20"
            id="notes"
            value={form.notes}
            onChange={(event) => setForm({ ...form, notes: event.target.value })}
          />
        </div>
        <label className="flex gap-3">
          <input
            className="mt-1 h-5 w-5"
            type="checkbox"
            checked={form.confirmed}
            disabled={form.unknown}
            onChange={(event) => setForm({ ...form, confirmed: event.target.checked })}
          />
          <span>
            <span className="font-semibold">I confirm this is my best current measurement</span>
            <span className="mt-1 block text-sm text-[var(--af-muted)]">
              You can revise it later; confirmation records your current choice.
            </span>
          </span>
        </label>
        <div className="flex flex-wrap items-center gap-4">
          <button className="af-button af-button-primary" type="submit" disabled={busy}>
            {busy ? 'Saving…' : 'Add measurement'}
          </button>
          <Link className="af-button af-button-secondary" href={`/projects/${projectId}`}>
            Finish for now
          </Link>
          <span role="status" className="text-sm text-[var(--af-muted)]">
            {message}
          </span>
        </div>
      </form>
      <section className="mt-9" aria-labelledby="measurement-list-heading">
        <h2 id="measurement-list-heading" className="text-2xl font-bold">
          Recorded measurements
        </h2>
        {measurements.length === 0 ? (
          <p className="mt-4 text-[var(--af-muted)]">
            No measurements yet. You can continue without one.
          </p>
        ) : (
          <ul className="mt-4 space-y-3">
            {measurements.map((item) => (
              <li
                className="af-card flex flex-wrap items-start justify-between gap-4 p-5"
                key={item.id}
              >
                <div>
                  <h3 className="font-bold">{item.kind}</h3>
                  <p className="mt-1 text-sm text-[var(--af-muted)]">
                    {item.unknown ? 'Unknown for now' : `${item.value} ${item.unit}`} ·{' '}
                    {item.method}
                  </p>
                </div>
                <span className="rounded-full border border-[var(--af-line)] px-3 py-1 text-sm">
                  {item.confirmed ? 'Confirmed' : 'Unconfirmed'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
