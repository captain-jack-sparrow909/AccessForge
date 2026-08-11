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
      router.push(`/projects/${projectId}/deletion-status`);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Could not queue deletion.');
    }
  }
  if (!project) return <p role="status">{message}</p>;
  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div>
          <span className="af-status-pill">{project.status.replaceAll('_', ' ')}</span>
          <h1 className="mt-5 max-w-3xl text-4xl font-extrabold tracking-tight sm:text-5xl">
            {project.name}
          </h1>
          <p className="mt-4 max-w-2xl text-lg leading-8 text-[var(--af-muted)]">
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
      <section
        className="af-card mt-9 grid gap-5 p-6 sm:grid-cols-[auto_1fr_auto] sm:items-center sm:p-7"
        aria-labelledby="scope-heading"
      >
        <span className="af-icon-tile" aria-hidden="true">
          ◎
        </span>
        <div>
          <h2 id="scope-heading" className="text-xl font-extrabold">
            Scope pre-screen
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">{project.scope_reason}</p>
        </div>
        <p className="af-status-pill w-fit">{project.scope_status.replaceAll('_', ' ')}</p>
      </section>
      <div className="mt-12 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="af-eyebrow">Guided workflow</p>
          <h2 className="mt-3 text-3xl font-extrabold">Build the record step by step</h2>
        </div>
        <p className="max-w-md text-sm leading-6 text-[var(--af-muted)]">
          Each step keeps its source, status, and limitations visible.
        </p>
      </div>
      <div className="mt-6 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
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
        <WorkflowCard
          title="Controlled Export"
          copy="Review current evidence gates, exact-revision acknowledgement, and private feedback."
          href={`/projects/${projectId}/export`}
          complete={project.status === 'export_ready'}
        />
      </div>
      <section className="mt-12" aria-labelledby="facts-heading">
        <p className="af-eyebrow">Current context</p>
        <h2 id="facts-heading" className="mt-3 text-3xl font-extrabold">
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
    <Link className="af-card af-card-link group block p-6" href={href}>
      <div className="flex items-center justify-between gap-4">
        <p className="af-status-pill">{complete ? 'Recorded' : 'Next step'}</p>
        <span
          className="text-xl text-[var(--af-line-strong)] transition group-hover:text-[var(--af-primary)]"
          aria-hidden="true"
        >
          ↗
        </span>
      </div>
      <h2 className="mt-6 text-xl font-extrabold">{title}</h2>
      <p className="mt-3 text-sm leading-6 text-[var(--af-muted)]">{copy}</p>
    </Link>
  );
}

function Fact({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="af-fact">
      <dt className="text-sm text-[var(--af-muted)]">{label}</dt>
      <dd className="mt-1 font-semibold">{value || 'Not provided yet'}</dd>
    </div>
  );
}
