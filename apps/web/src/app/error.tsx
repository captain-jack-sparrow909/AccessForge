'use client';

export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="af-container py-16">
      <div className="af-card max-w-xl p-8">
        <p className="af-eyebrow">Something went wrong</p>
        <h1 className="mt-4 text-3xl font-bold">The page could not load.</h1>
        <p className="mt-3 leading-7 text-[var(--af-muted)]">
          Try again. If this keeps happening, share the time and page with the maintainer—not
          private project media.
        </p>
        <button className="af-button af-button-primary mt-7" type="button" onClick={() => reset()}>
          Try again
        </button>
      </div>
    </div>
  );
}
