import Link from 'next/link';
import { getSession } from '@/auth';
import { redirect } from 'next/navigation';

export default async function ProjectLayout({
  children,
  params,
}: Readonly<{ children: React.ReactNode; params: Promise<{ projectId: string }> }>) {
  const session = await getSession();
  if (!session?.user) redirect('/sign-in');
  const { projectId } = await params;
  return (
    <div className="af-container py-8 sm:py-10">
      <div className="mb-9 grid gap-5">
        <div>
          <Link href="/dashboard" className="af-button af-button-ghost min-h-0 px-0 py-1 text-sm">
            <span aria-hidden="true">←</span> All projects
          </Link>
          <p className="af-eyebrow mt-4">Private co-design workspace</p>
        </div>
        <nav aria-label="Project workflow" className="af-workflow-nav flex flex-wrap gap-1 text-sm">
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
