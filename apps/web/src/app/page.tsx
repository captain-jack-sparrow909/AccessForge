import Link from 'next/link';

const supported = [
  'Zipper or pull-tab extenders',
  'Cylindrical grip thickeners',
  'Cabinet or drawer handle sleeves',
];

export default function HomePage() {
  return (
    <div>
      <section className="af-container grid gap-10 py-20 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
        <div>
          <p className="af-eyebrow">Phase 1 foundation · private by default</p>
          <h1 className="mt-5 max-w-3xl text-5xl font-bold leading-[1.04] tracking-tight sm:text-6xl">
            Make everyday objects easier to use, with you in control.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-[var(--af-muted)]">
            AccessForge is being built to help people describe a low-risk access difficulty, explore
            a reviewed adapter template, and see exactly what was checked. It is not a medical
            device or a safety certification service.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/sign-in" className="af-button af-button-primary">
              Start a private project
            </Link>
            <Link href="/how-it-works" className="af-button af-button-secondary">
              See how it works
            </Link>
          </div>
        </div>
        <aside className="af-card p-7" aria-labelledby="supported-heading">
          <p className="af-eyebrow">MVP boundary</p>
          <h2 id="supported-heading" className="mt-3 text-2xl font-bold">
            A deliberately small first step
          </h2>
          <p className="mt-3 leading-7 text-[var(--af-muted)]">
            The first release supports passive, non-load-bearing, low-energy grip and pull aids at
            room temperature.
          </p>
          <ul className="mt-5 space-y-3">
            {supported.map((item) => (
              <li key={item} className="flex gap-3 leading-6">
                <span
                  aria-hidden="true"
                  className="mt-2 h-2 w-2 shrink-0 rounded-full bg-[var(--af-primary)]"
                />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </aside>
      </section>
      <section className="bg-[var(--af-primary-dark)] py-14 text-white">
        <div className="af-container grid gap-8 md:grid-cols-3">
          <div>
            <p className="text-sm font-bold uppercase tracking-[.12em] text-[var(--af-accent)]">
              01
            </p>
            <h2 className="mt-3 text-xl font-bold">You describe the goal</h2>
            <p className="mt-2 leading-7 text-white/75">
              Text-only and helper paths are always available.
            </p>
          </div>
          <div>
            <p className="text-sm font-bold uppercase tracking-[.12em] text-[var(--af-accent)]">
              02
            </p>
            <h2 className="mt-3 text-xl font-bold">The system shows its work</h2>
            <p className="mt-2 leading-7 text-white/75">
              Requirements, assumptions, and checks remain visible.
            </p>
          </div>
          <div>
            <p className="text-sm font-bold uppercase tracking-[.12em] text-[var(--af-accent)]">
              03
            </p>
            <h2 className="mt-3 text-xl font-bold">You decide what leaves</h2>
            <p className="mt-2 leading-7 text-white/75">
              Projects stay private unless you choose to share them.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
