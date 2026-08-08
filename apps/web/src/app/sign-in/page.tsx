import Link from 'next/link';
import { signIn } from '@/auth';

export default function SignInPage() {
  const githubConfigured = Boolean(process.env.AUTH_GITHUB_ID && process.env.AUTH_GITHUB_SECRET);
  const devAuthEnabled = process.env.DEV_AUTH_ENABLED === 'true';
  return (
    <div className="af-container flex min-h-[70vh] items-center justify-center py-16">
      <div className="af-card w-full max-w-md p-8">
        <p className="af-eyebrow">Private workspace</p>
        <h1 className="mt-4 text-3xl font-bold">Sign in to AccessForge</h1>
        <p className="mt-3 leading-7 text-[var(--af-muted)]">
          Phase 1 creates empty private projects only. Do not add real participant media yet.
        </p>
        <div className="mt-7 space-y-3">
          {githubConfigured ? (
            <form
              action={async () => {
                'use server';
                await signIn('github', { redirectTo: '/dashboard' });
              }}
            >
              <button className="af-button af-button-primary w-full" type="submit">
                Continue with GitHub
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
            <div className="rounded-lg border border-[var(--af-line)] bg-[var(--af-paper)] p-4 text-sm leading-6 text-[var(--af-muted)]">
              Authentication is not configured. Add GitHub OAuth credentials or enable the
              development-only account in <code>apps/web/.env.local</code>.
            </div>
          ) : null}
        </div>
        <Link href="/" className="mt-6 inline-block text-sm underline underline-offset-4">
          Return home
        </Link>
      </div>
    </div>
  );
}
