import Link from 'next/link';

const supported = [
  {
    number: '01',
    title: 'Pull-tab extenders',
    copy: 'Explore a larger, easier-to-find grip for a small zipper or passive pull tab.',
  },
  {
    number: '02',
    title: 'Cylindrical grips',
    copy: 'Review bounded grip-thickening ideas for light, room-temperature everyday objects.',
  },
  {
    number: '03',
    title: 'Handle sleeves',
    copy: 'Describe a low-energy cabinet or drawer interaction and keep every assumption visible.',
  },
];

const principles = [
  {
    symbol: '✦',
    title: 'Your words come first',
    copy: 'Describe the outcome without naming a diagnosis or explaining your body.',
  },
  {
    symbol: '◎',
    title: 'Every decision is visible',
    copy: 'Requirements, uncertainty, risk boundaries, and software checks stay inspectable.',
  },
  {
    symbol: '↗',
    title: 'Nothing leaves quietly',
    copy: 'Projects remain private and external model sharing requires a separate choice.',
  },
];

export default function HomePage() {
  return (
    <div>
      <section className="af-container grid gap-12 py-16 lg:grid-cols-[1.02fr_0.98fr] lg:items-center lg:py-24">
        <div>
          <span className="af-badge">
            <span className="af-badge-dot" aria-hidden="true" />
            Private, transparent co-design
          </span>
          <h1 className="af-display-title mt-7">
            Everyday access, <span className="af-highlight">shaped with you.</span>
          </h1>
          <p className="mt-7 max-w-xl text-lg leading-8 text-[var(--af-muted)] sm:text-xl">
            Turn a frustrating everyday interaction into a clear, bounded design brief—without
            hiding the assumptions, uncertainty, or safety limits.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Link href="/sign-in" className="af-button af-button-primary px-5">
              Start a private project <span aria-hidden="true">→</span>
            </Link>
            <Link href="/how-it-works" className="af-button af-button-secondary px-5">
              Explore the process
            </Link>
          </div>
          <div className="mt-10 flex flex-wrap gap-x-7 gap-y-3 border-t border-[var(--af-line)] pt-6 text-sm font-semibold text-[var(--af-ink-soft)]">
            <span className="inline-flex items-center gap-2">
              <span className="text-[var(--af-primary)]" aria-hidden="true">
                ✓
              </span>
              Text-only path
            </span>
            <span className="inline-flex items-center gap-2">
              <span className="text-[var(--af-primary)]" aria-hidden="true">
                ✓
              </span>
              Optional AI
            </span>
            <span className="inline-flex items-center gap-2">
              <span className="text-[var(--af-primary)]" aria-hidden="true">
                ✓
              </span>
              3D never required
            </span>
          </div>
        </div>

        <div className="af-hero-visual" aria-label="Illustration of a transparent design workspace">
          <div className="af-visual-note af-visual-note-top">
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-extrabold uppercase tracking-[0.12em] text-[var(--af-primary)]">
                Design brief
              </span>
              <span className="af-status-pill">Private</span>
            </div>
            <p className="mt-3 text-sm font-bold">A larger zipper grip for a gentle pull</p>
            <div className="mt-3 grid gap-2" aria-hidden="true">
              <div className="af-visual-line af-visual-line-strong" />
              <div className="af-visual-line" />
            </div>
          </div>
          <div className="af-visual-object" aria-hidden="true" />
          <div className="af-visual-note af-visual-note-bottom">
            <p className="text-xs font-extrabold uppercase tracking-[0.12em] text-[var(--af-primary)]">
              What stays visible
            </p>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-bold">
              <span className="rounded-lg bg-[var(--af-primary-soft)] px-2 py-2">Measurements</span>
              <span className="rounded-lg bg-[var(--af-warning-soft)] px-2 py-2">Unknowns</span>
              <span className="rounded-lg bg-[#e5f1f2] px-2 py-2">Checks</span>
              <span className="rounded-lg bg-[var(--af-danger-soft)] px-2 py-2">Limits</span>
            </div>
          </div>
        </div>
      </section>

      <section className="af-section-tint af-section-tight">
        <div className="af-container">
          <div className="grid gap-8 md:grid-cols-3">
            {principles.map((principle) => (
              <article key={principle.title} className="grid grid-cols-[auto_1fr] gap-4">
                <span className="af-icon-tile" aria-hidden="true">
                  {principle.symbol}
                </span>
                <div>
                  <h2 className="text-lg font-extrabold">{principle.title}</h2>
                  <p className="mt-1 text-sm leading-6 text-[var(--af-muted)]">{principle.copy}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="af-section">
        <div className="af-container">
          <div className="grid gap-8 lg:grid-cols-[0.72fr_1.28fr] lg:items-end">
            <div>
              <p className="af-eyebrow">A deliberately small scope</p>
              <h2 className="mt-5 max-w-lg text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
                Start with useful, low-risk everyday interactions.
              </h2>
            </div>
            <p className="max-w-2xl text-lg leading-8 text-[var(--af-muted)] lg:justify-self-end">
              AccessForge does not accept every idea. The initial boundary is passive,
              non-load-bearing, low-energy grip and pull aids at room temperature. Small scope is
              part of the safety model.
            </p>
          </div>
          <div className="mt-12 grid gap-5 md:grid-cols-3">
            {supported.map((item) => (
              <article className="af-card af-card-link group p-7" key={item.title}>
                <div className="flex items-center justify-between">
                  <span className="af-number">{item.number}</span>
                  <span
                    aria-hidden="true"
                    className="text-2xl text-[var(--af-line-strong)] transition group-hover:text-[var(--af-primary)]"
                  >
                    ↗
                  </span>
                </div>
                <h3 className="mt-8 text-2xl font-extrabold">{item.title}</h3>
                <p className="mt-3 leading-7 text-[var(--af-muted)]">{item.copy}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="af-section pt-0">
        <div className="af-container">
          <div className="af-dark-panel grid gap-10 px-7 py-10 sm:px-10 lg:grid-cols-[0.9fr_1.1fr] lg:p-14">
            <div className="relative z-10">
              <p className="af-eyebrow text-[var(--af-accent)]">How the workspace thinks</p>
              <h2 className="mt-5 max-w-lg text-4xl font-extrabold leading-tight sm:text-5xl">
                No mystery leap from problem to object.
              </h2>
              <p className="mt-5 max-w-lg leading-7 text-white/72">
                The process pauses for consent, missing facts, risk review, and your confirmation.
                Software output never quietly becomes a physical-use claim.
              </p>
              <Link
                href="/how-it-works"
                className="af-button mt-8 border border-white/25 bg-white text-[var(--af-primary-dark)] hover:bg-[var(--af-accent)]"
              >
                See every step <span aria-hidden="true">→</span>
              </Link>
            </div>
            <ol className="relative z-10 grid gap-3">
              {[
                ['Describe', 'Start with the outcome and the object in your own language.'],
                ['Clarify', 'Keep measurements, evidence, suggestions, and unknowns separate.'],
                ['Review', 'Use deterministic scope and risk gates before bounded design work.'],
                ['Decide', 'Inspect the structured report and choose what happens next.'],
              ].map(([title, copy], index) => (
                <li
                  key={title}
                  className="grid grid-cols-[auto_1fr] gap-4 rounded-2xl border border-white/12 bg-white/8 p-4 backdrop-blur-sm"
                >
                  <span className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--af-accent)] text-sm font-black text-[var(--af-primary-dark)]">
                    {index + 1}
                  </span>
                  <div>
                    <h3 className="font-extrabold">{title}</h3>
                    <p className="mt-1 text-sm leading-6 text-white/68">{copy}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      <section className="af-section-tint af-section">
        <div className="af-container text-center">
          <p className="af-eyebrow">Begin with a private brief</p>
          <h2 className="mx-auto mt-5 max-w-3xl text-4xl font-extrabold leading-tight tracking-tight sm:text-6xl">
            Make the next everyday interaction feel less frustrating.
          </h2>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-[var(--af-muted)]">
            Start with text. Add only what helps. Keep uncertainty visible and stay in control of
            every sharing decision.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link href="/sign-in" className="af-button af-button-primary px-6">
              Start a private project <span aria-hidden="true">→</span>
            </Link>
            <Link href="/safety" className="af-button af-button-secondary px-6">
              Read the safety boundary
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
