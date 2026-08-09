import Link from 'next/link';
import { auth } from '@/auth';
import { redirect } from 'next/navigation';

export default async function ProjectLayout({
  children,
  params,
}: Readonly<{ children: React.ReactNode; params: Promise<{ projectId: string }> }>) {
  const session = await auth();
  if (!session?.user) redirect('/sign-in');
  const { projectId } = await params;
  return (
    <div className="af-container py-10">
      <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
        <div>
          <Link
            href="/dashboard"
            className="text-sm text-[var(--af-muted)] underline underline-offset-4"
          >
            ← All projects
          </Link>
          <p className="af-eyebrow mt-4">Private co-design workspace</p>
        </div>
        <nav aria-label="Project workflow" className="flex flex-wrap gap-2 text-sm">
          <Link className="af-button af-button-secondary" href={`/projects/${projectId}`}>
            Overview
          </Link>
          <Link className="af-button af-button-secondary" href={`/projects/${projectId}/consent`}>
            Consent
          </Link>
          <Link className="af-button af-button-secondary" href={`/projects/${projectId}/capture`}>
            Capture
          </Link>
          <Link
            className="af-button af-button-secondary"
            href={`/projects/${projectId}/measurements`}
          >
            Measurements
          </Link>
          <Link
            className="af-button af-button-secondary"
            href={`/projects/${projectId}/requirements`}
          >
            Requirements
          </Link>
          <Link className="af-button af-button-secondary" href={`/projects/${projectId}/risk`}>
            Risk Review
          </Link>
          <Link className="af-button af-button-secondary" href={`/projects/${projectId}/designs`}>
            DesignSpec
          </Link>
          <Link className="af-button af-button-secondary" href={`/projects/${projectId}/export`}>
            Controlled Export
          </Link>
        </nav>
      </div>
      {children}
    </div>
  );
}
