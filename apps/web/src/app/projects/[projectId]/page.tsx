'use client';

import Link from 'next/link';
import { use, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import type { Measurement, Observation, Project } from '@accessforge/api-client';
import { useProjectClient } from '../project-api';

export default function ProjectOverview({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const client = useProjectClient();
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [message, setMessage] = useState('Loading project…');
  useEffect(() => {
    let active = true;
    Promise.all([
      client.getProject(projectId),
      client.listObservations(projectId),
      client.listMeasurements(projectId),
    ])
      .then(([nextProject, nextObservations, nextMeasurements]) => {
        if (!active) return;
        setProject(nextProject);
        setObservations(nextObservations);
        setMeasurements(nextMeasurements);
        setMessage('');
      })
      .catch((error: unknown) =>
        setMessage(error instanceof Error ? error.message : 'Could not load project.'),
      );
    return () => {
      active = false;
    };
  }, [client, projectId]);
  async function deleteProject() {
    if (
      !window.confirm(
        'Queue this private project and its media for deletion? This cannot be undone.',
      )
    )
      return;
    setMessage('Queueing deletion…');
    try {
      await client.deleteProject(projectId);
      router.push('/dashboard');
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Could not queue deletion.');
    }
  }
  if (!project) return <p role="status">{message}</p>;
  return (
    <div className="max-w-4xl">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div>
          <p className="af-eyebrow">{project.status.replaceAll('_', ' ')}</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">{project.name}</h1>
          <p className="mt-3 max-w-2xl leading-7 text-[var(--af-muted)]">
            {project.goal || project.description}
          </p>
        </div>
        <button
          className="af-button af-button-secondary text-[var(--af-danger)]"
          type="button"
          onClick={deleteProject}
        >
          Delete project
        </button>
      </div>
      <section className="af-card mt-8 p-6" aria-labelledby="scope-heading">
        <h2 id="scope-heading" className="text-xl font-bold">
          Scope pre-screen
        </h2>
        <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">{project.scope_reason}</p>
        <p className="mt-3 inline-flex rounded-full border border-[var(--af-line)] px-3 py-1 text-sm font-semibold">
          {project.scope_status.replaceAll('_', ' ')}
        </p>
      </section>
      <div className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-5">
        <WorkflowCard
          title="Consent"
          copy="Choose separately what you want to share."
          href={`/projects/${projectId}/consent`}
          complete={project.status !== 'draft'}
        />
        <WorkflowCard
          title="Observation"
          copy="Use text only, upload a still, or skip capture."
          href={`/projects/${projectId}/capture`}
          complete={observations.length > 0}
        />
        <WorkflowCard
          title="Measurements"
          copy="Add a value, method, tolerance, and confirmation."
          href={`/projects/${projectId}/measurements`}
          complete={measurements.length > 0}
        />
        <WorkflowCard
          title="Requirements"
          copy="Review AI proposals or continue with your own requirements."
          href={`/projects/${projectId}/requirements`}
          complete={Boolean(project.active_requirement_revision_id)}
        />
        <WorkflowCard
          title="Risk Review"
          copy="Record the declared use; only the server can allow candidate planning."
          href={`/projects/${projectId}/risk`}
          complete={project.status === 'ready_for_generation'}
        />
        <WorkflowCard
          title="DesignSpec"
          copy="Record bounded template parameters and see the Phase 5 generation gate."
          href={`/projects/${projectId}/designs`}
          complete={project.status === 'risk_review' || project.status === 'ready_for_generation'}
        />
      </div>
      <section className="mt-9" aria-labelledby="facts-heading">
        <h2 id="facts-heading" className="text-xl font-bold">
          Project facts
        </h2>
        <dl className="mt-4 grid gap-3 sm:grid-cols-2">
          <Fact label="Object" value={project.object_description} />
          <Fact label="Action" value={project.action_description} />
          <Fact label="Environment" value={project.environment} />
          <Fact label="Load context" value={project.load_context} />
        </dl>
      </section>
      <p role="status" className="mt-8 text-sm text-[var(--af-muted)]">
        {message}
      </p>
    </div>
  );
}

function WorkflowCard({
  title,
  copy,
  href,
  complete,
}: {
  title: string;
  copy: string;
  href: string;
  complete: boolean;
}) {
  return (
    <Link
      className="af-card block p-6 transition hover:-translate-y-0.5 hover:border-[var(--af-primary)]"
      href={href}
    >
      <p className="text-sm font-semibold text-[var(--af-primary)]">
        {complete ? 'Recorded' : 'Next step'}
      </p>
      <h2 className="mt-2 text-xl font-bold">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">{copy}</p>
    </Link>
  );
}

function Fact({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-lg border border-[var(--af-line)] bg-[var(--af-surface)] p-4">
      <dt className="text-sm text-[var(--af-muted)]">{label}</dt>
      <dd className="mt-1 font-semibold">{value || 'Not provided yet'}</dd>
    </div>
  );
}
