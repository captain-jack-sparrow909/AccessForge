export default function SafetyPage() {
  return (
    <div className="af-container py-16">
      <p className="af-eyebrow">Safety limits</p>
      <h1 className="mt-4 max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">
        A small scope is a safety feature.
      </h1>
      <p className="mt-6 max-w-3xl text-lg leading-8 text-[var(--af-muted)]">
        The MVP is limited to passive, non-load-bearing, low-energy grip and pull aids at room
        temperature. A passed automated check is not professional approval and never means a design
        is universally safe.
      </p>
      <div className="mt-10 grid gap-5 md:grid-cols-3">
        <article className="af-card border-l-4 border-l-[var(--af-primary)] p-6">
          <h2 className="text-xl font-bold">Supported</h2>
          <p className="mt-3 leading-7 text-[var(--af-muted)]">
            Reviewed low-risk templates with confirmed inputs and successful checks.
          </p>
        </article>
        <article className="af-card border-l-4 border-l-[var(--af-warning)] p-6">
          <h2 className="text-xl font-bold">Professional review</h2>
          <p className="mt-3 leading-7 text-[var(--af-muted)]">
            Hot, wet, chemical, repetitive, body-contact, or uncertain-use situations.
          </p>
        </article>
        <article className="af-card border-l-4 border-l-[var(--af-danger)] p-6">
          <h2 className="text-xl font-bold">Not generated</h2>
          <p className="mt-3 leading-7 text-[var(--af-muted)]">
            Medical, mobility, vehicle, electrical, gas, weapon, child-safety, or life-safety parts.
          </p>
        </article>
      </div>
    </div>
  );
}
