const principles = [
  [
    'Separate choices',
    'Recording, provider sharing, helper access, and future publication use distinct consent choices.',
  ],
  [
    'Minimum necessary',
    'The system is designed to send only the selected information needed for the chosen step.',
  ],
  [
    'Private artifacts',
    'Media and generated artifacts stay behind authenticated, short-lived access boundaries.',
  ],
  [
    'Visible deletion',
    'A deleted project disappears from ordinary use while sanitized cleanup progress remains available.',
  ],
];

export default function PrivacyPage() {
  return (
    <div>
      <section className="af-container af-section grid gap-10 lg:grid-cols-[1fr_1fr] lg:items-center">
        <div>
          <p className="af-eyebrow">Privacy principles</p>
          <h1 className="af-page-title mt-6">Your project is private by default.</h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-[var(--af-muted)]">
            Everyday access media can reveal a person, their home, routines, or health-related
            context. AccessForge treats sharing as a series of explicit decisions—not a blanket
            checkbox.
          </p>
        </div>
        <div className="af-dark-panel p-8 sm:p-10">
          <div className="relative z-10 rounded-2xl border border-white/15 bg-white/8 p-6">
            <span
              className="grid h-12 w-12 place-items-center rounded-2xl bg-[var(--af-accent)] text-xl text-[var(--af-primary-dark)]"
              aria-hidden="true"
            >
              ◇
            </span>
            <p className="mt-6 text-sm font-extrabold uppercase tracking-[0.14em] text-[var(--af-accent)]">
              Default state
            </p>
            <p className="mt-3 text-3xl font-extrabold">Private. Unpublished. User-controlled.</p>
            <p className="mt-4 leading-7 text-white/70">
              A configured model provider does not override project-level sharing consent.
            </p>
          </div>
        </div>
      </section>

      <section className="af-section-tint af-section-tight">
        <div className="af-container grid gap-5 sm:grid-cols-2">
          {principles.map(([title, copy], index) => (
            <article className="af-card p-7" key={title}>
              <span className="af-number">0{index + 1}</span>
              <h2 className="mt-7 text-2xl font-extrabold">{title}</h2>
              <p className="mt-3 leading-7 text-[var(--af-muted)]">{copy}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
