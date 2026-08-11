const boundaries = [
  {
    label: 'Supported boundary',
    title: 'Passive and low energy',
    copy: 'Reviewed grip and pull templates with confirmed inputs, room-temperature use, and successful software checks.',
    tone: 'primary',
    symbol: '✓',
  },
  {
    label: 'Pause for review',
    title: 'Context changes the risk',
    copy: 'Hot, wet, chemical, repetitive, body-contact, uncertain-force, or otherwise unclear situations need qualified review.',
    tone: 'warning',
    symbol: '!',
  },
  {
    label: 'Not generated',
    title: 'Safety-critical uses',
    copy: 'Medical, mobility, vehicle, electrical, gas, weapon, child-safety, access-control, or life-safety parts stay blocked.',
    tone: 'danger',
    symbol: '×',
  },
];

export default function SafetyPage() {
  return (
    <div>
      <section className="af-container af-section grid gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:items-end">
        <div>
          <p className="af-eyebrow">Safety limits</p>
          <h1 className="af-page-title mt-6">A small scope is a safety feature.</h1>
        </div>
        <p className="max-w-xl text-lg leading-8 text-[var(--af-muted)] lg:justify-self-end">
          A passed software check is not professional approval and never means a candidate is
          universally safe, fit, printable, or ready for physical use.
        </p>
      </section>

      <section className="af-section-tint af-section-tight">
        <div className="af-container grid gap-5 lg:grid-cols-3">
          {boundaries.map((boundary) => (
            <article className="af-card p-7" key={boundary.title}>
              <div
                className={`grid h-12 w-12 place-items-center rounded-2xl text-xl font-black ${
                  boundary.tone === 'primary'
                    ? 'bg-[var(--af-primary-soft)] text-[var(--af-primary-dark)]'
                    : boundary.tone === 'warning'
                      ? 'bg-[var(--af-warning-soft)] text-[var(--af-warning)]'
                      : 'bg-[var(--af-danger-soft)] text-[var(--af-danger)]'
                }`}
                aria-hidden="true"
              >
                {boundary.symbol}
              </div>
              <p className="mt-7 text-xs font-extrabold uppercase tracking-[0.14em] text-[var(--af-muted)]">
                {boundary.label}
              </p>
              <h2 className="mt-2 text-2xl font-extrabold">{boundary.title}</h2>
              <p className="mt-4 leading-7 text-[var(--af-muted)]">{boundary.copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="af-container af-section">
        <div className="grid gap-8 lg:grid-cols-[0.78fr_1.22fr] lg:items-start">
          <div>
            <p className="af-eyebrow">What the checks mean</p>
            <h2 className="mt-5 text-3xl font-extrabold sm:text-4xl">Evidence, not promises.</h2>
          </div>
          <div className="af-card p-7 sm:p-9">
            <dl className="grid gap-6 sm:grid-cols-2">
              <div>
                <dt className="font-extrabold">Software validation can show</dt>
                <dd className="mt-2 leading-7 text-[var(--af-muted)]">
                  Bounded parameters, deterministic geometry checks, lineage, and recorded
                  limitations.
                </dd>
              </div>
              <div>
                <dt className="font-extrabold">It cannot establish</dt>
                <dd className="mt-2 leading-7 text-[var(--af-muted)]">
                  Fit, comfort, strength, durability, material behavior, clinical benefit, or safe
                  physical use.
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </section>
    </div>
  );
}
