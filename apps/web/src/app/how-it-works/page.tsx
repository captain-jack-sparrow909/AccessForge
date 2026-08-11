import Link from 'next/link';

const steps = [
  {
    title: 'Describe the outcome',
    body: 'Start with what you want to do and the everyday object involved. No diagnosis or body explanation is required.',
    note: 'Text-only is always available',
  },
  {
    title: 'Confirm what is known',
    body: 'Measurements, observations, model suggestions, and unknowns stay separate until you review them.',
    note: 'Nothing is silently assumed',
  },
  {
    title: 'Constrain the problem',
    body: 'Deterministic scope and risk rules stop requests outside the reviewed low-risk boundary.',
    note: 'Safety gates do not use AI',
  },
  {
    title: 'Review the candidate',
    body: 'A structured report presents parameters, checks, limitations, and uncertainty before any optional 3D view.',
    note: 'Software checks are not approval',
  },
];

export default function HowItWorksPage() {
  return (
    <div>
      <section className="af-container af-section grid gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:items-end">
        <div>
          <p className="af-eyebrow">Transparent by design</p>
          <h1 className="af-page-title mt-6">A co-design notebook, not a black box.</h1>
        </div>
        <p className="max-w-xl text-lg leading-8 text-[var(--af-muted)] lg:justify-self-end">
          AccessForge turns one everyday difficulty into a sequence of small, inspectable choices.
          You can see where information came from, what remains uncertain, and why a path is paused.
        </p>
      </section>

      <section className="af-section-tint af-section-tight">
        <div className="af-container">
          <ol className="grid gap-5 md:grid-cols-2">
            {steps.map((step, index) => (
              <li className="af-card af-card-link p-7 sm:p-8" key={step.title}>
                <div className="flex items-start justify-between gap-5">
                  <span className="af-number">0{index + 1}</span>
                  <span className="af-status-pill">{step.note}</span>
                </div>
                <h2 className="mt-10 text-2xl font-extrabold sm:text-3xl">{step.title}</h2>
                <p className="mt-4 max-w-xl leading-7 text-[var(--af-muted)]">{step.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="af-container af-section">
        <div className="af-dark-panel grid gap-7 px-7 py-10 sm:px-10 lg:grid-cols-[1fr_auto] lg:items-center lg:p-12">
          <div className="relative z-10">
            <p className="text-sm font-extrabold uppercase tracking-[0.14em] text-[var(--af-accent)]">
              Ready when you are
            </p>
            <h2 className="mt-4 max-w-2xl text-3xl font-extrabold sm:text-4xl">
              Begin with words. Add evidence only when it helps.
            </h2>
            <p className="mt-4 max-w-2xl leading-7 text-white/70">
              A private project can begin without camera, audio, external AI, or a 3D interaction.
            </p>
          </div>
          <Link
            href="/sign-in"
            className="af-button relative z-10 bg-white px-6 text-[var(--af-primary-dark)]"
          >
            Open a private project <span aria-hidden="true">→</span>
          </Link>
        </div>
      </section>
    </div>
  );
}
