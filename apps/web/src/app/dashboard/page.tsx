import Link from 'next/link';
import { auth } from '@/auth';
import DashboardClient from './dashboard-client';

export default async function DashboardPage() {
  const session = await auth();
  if (!session?.user)
    return (
      <div className="af-container af-section">
        <div className="af-card max-w-2xl p-8 sm:p-10">
          <p className="af-eyebrow">Private workspace</p>
          <h1 className="mt-5 text-4xl font-extrabold">Sign in to see your projects</h1>
          <p className="mt-4 leading-7 text-[var(--af-muted)]">
            Projects are scoped to your account and are not public.
          </p>
          <Link href="/sign-in" className="af-button af-button-primary mt-7">
            Sign in <span aria-hidden="true">→</span>
          </Link>
        </div>
      </div>
    );
  return <DashboardClient email={session.user.email ?? session.user.name ?? 'signed-in user'} />;
}
