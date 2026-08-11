import Link from 'next/link';
import { signIn } from '@/auth';

export default function SignInPage() {
  const githubConfigured = Boolean(process.env.AUTH_GITHUB_ID && process.env.AUTH_GITHUB_SECRET);
  const devAuthEnabled = process.env.DEV_AUTH_ENABLED === 'true';
  return (
    <div className="af-container grid min-h-[76vh] gap-8 py-12 lg:grid-cols-[0.95fr_1.05fr] lg:items-stretch lg:py-16">
      <section className="af-dark-panel hidden p-10 lg:flex lg:flex-col lg:justify-between">
        <div className="relative z-10">
          <p className="text-sm font-extrabold uppercase tracking-[0.14em] text-[var(--af-accent)]">
            Your private workspace
          </p>
          <h1 className="mt-5 max-w-lg text-5xl font-extrabold leading-[1.02]">
            Pick up exactly where your thinking left off.
          </h1>
          <p className="mt-6 max-w-md text-lg leading-8 text-white/70">
            Projects, consent choices, requirements, risk decisions, and structured candidate
            reports remain scoped to your account.
          </p>
        </div>
        <div className="relative z-10 grid gap-3">
          {[
            'Private by default',
            'Text-only workflow available',
            'Every limitation stays visible',
          ].map((item) => (
            <div
              className="flex items-center gap-3 rounded-2xl border border-white/12 bg-white/8 px-4 py-3 text-sm font-semibold"
              key={item}
            >
              <span className="text-[var(--af-accent)]" aria-hidden="true">
                ✓
              </span>
              {item}
            </div>
          ))}
        </div>
      </section>

      <section className="af-card flex items-center p-7 sm:p-10 lg:p-14">
        <div className="mx-auto w-full max-w-md">
          <span className="af-badge">
            <span className="af-badge-dot" aria-hidden="true" />
            Secure account access
          </span>
          <h2 className="mt-6 text-4xl font-extrabold">Welcome to AccessForge</h2>
          <p className="mt-4 leading-7 text-[var(--af-muted)]">
            Sign in to open your private co-design workspace. Use synthetic data only until the
            required privacy, accessibility, and operational reviews are complete.
          </p>
          <div className="mt-8 space-y-3">
            {githubConfigured ? (
              <form
                action={async () => {
                  'use server';
                  await signIn('github', { redirectTo: '/dashboard' });
                }}
              >
                <button className="af-button af-button-primary w-full" type="submit">
                  Continue with GitHub <span aria-hidden="true">→</span>
                </button>
              </form>
            ) : null}
            {devAuthEnabled ? (
              <form
                action={async () => {
                  'use server';
                  await signIn('credentials', {
                    email: process.env.DEV_AUTH_EMAIL,
                    password: process.env.DEV_AUTH_PASSWORD,
                    redirectTo: '/dashboard',
                  });
                }}
              >
                <button className="af-button af-button-secondary w-full" type="submit">
                  Use local development account
                </button>
              </form>
            ) : null}
            {!githubConfigured && !devAuthEnabled ? (
              <div className="rounded-2xl border border-[var(--af-line)] bg-[var(--af-paper)] p-4 text-sm leading-6 text-[var(--af-muted)]">
                Authentication is not configured. Add GitHub OAuth credentials or enable the
                development-only account in <code>apps/web/.env.local</code>.
              </div>
            ) : null}
          </div>
          <Link href="/" className="af-button af-button-ghost mt-5 px-0">
            <span aria-hidden="true">←</span> Return home
          </Link>
        </div>
      </section>
    </div>
  );
}
