'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { createAccessForgeClient, type Project } from '@accessforge/api-client';

export default function DashboardClient({ email }: { email: string }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState('My first access project');
  const [status, setStatus] = useState('Loading private projects…');
  const client = useMemo(
    () =>
      createAccessForgeClient({
        baseUrl: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000',
        getToken: async () => {
          const response = await fetch('/api/backend-token', { cache: 'no-store' });
          if (!response.ok) throw new Error('Backend token is not configured.');
          return ((await response.json()) as { access_token: string }).access_token;
        },
      }),
    [],
  );
  useEffect(() => {
    let active = true;
    client
      .listProjects()
      .then((items) => {
        if (active) {
          setProjects(items);
          setStatus('Ready');
        }
      })
      .catch((error: unknown) => {
        if (active) setStatus(error instanceof Error ? error.message : 'Could not load projects.');
      });
    return () => {
      active = false;
    };
  }, [client]);
  async function createProject() {
    setStatus('Creating private project…');
    try {
      const project = await client.createProject({ name });
      setProjects((current) => [project, ...current]);
      setStatus('Project created');
    } catch (error: unknown) {
      setStatus(error instanceof Error ? error.message : 'Could not create project.');
    }
  }
  return (
    <div className="af-container af-section">
      <div className="grid gap-8 lg:grid-cols-[1fr_auto] lg:items-end">
        <div>
          <p className="af-eyebrow">Private dashboard</p>
          <h1 className="af-page-title mt-5">Your access projects</h1>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <span className="af-badge">Signed in as {email}</span>
            <span role="status" className="text-sm text-[var(--af-muted)]">
              {status}
            </span>
          </div>
        </div>
        <Link className="af-button af-button-primary px-5" href="/projects/new">
          Start a guided project <span aria-hidden="true">→</span>
        </Link>
      </div>
      <section
        className="mt-12 grid gap-6 lg:grid-cols-[0.7fr_1.3fr]"
        aria-labelledby="projects-heading"
      >
        <div className="af-card h-fit p-6 sm:p-7">
          <span className="af-icon-tile" aria-hidden="true">
            +
          </span>
          <h2 className="mt-6 text-2xl font-extrabold">Quick project</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
            Create a private placeholder now, or use the guided project flow for the complete scope
            questions.
          </p>
          <label className="mt-6 block text-sm font-bold" htmlFor="project-name">
            Project name
          </label>
          <input
            className="af-input mt-2"
            id="project-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <button
            className="af-button af-button-secondary mt-3 w-full"
            type="button"
            onClick={createProject}
            disabled={!name.trim()}
          >
            Create private project
          </button>
        </div>
        <div>
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="af-eyebrow">Workspace</p>
              <h2 id="projects-heading" className="mt-3 text-3xl font-extrabold">
                Recent projects
              </h2>
            </div>
            <span className="af-status-pill">{projects.length} total</span>
          </div>
          {projects.length === 0 ? (
            <div className="af-card mt-5 p-8 text-center">
              <span
                className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-[var(--af-primary-soft)] text-2xl"
                aria-hidden="true"
              >
                ◇
              </span>
              <h3 className="mt-5 text-xl font-extrabold">A clear workspace to begin</h3>
              <p className="mx-auto mt-2 max-w-md text-[var(--af-muted)]">
                No projects yet. Start with one everyday outcome and keep every later choice private
                and inspectable.
              </p>
            </div>
          ) : (
            <ul className="mt-5 grid gap-4 md:grid-cols-2">
              {projects.map((project) => (
                <li className="af-card af-card-link p-6" key={project.id}>
                  <div className="flex items-center justify-between gap-4">
                    <span className="af-status-pill">{project.status.replaceAll('_', ' ')}</span>
                    <span className="text-xl text-[var(--af-line-strong)]" aria-hidden="true">
                      ↗
                    </span>
                  </div>
                  <h3 className="mt-6 text-xl font-extrabold">
                    <Link href={`/projects/${project.id}`}>{project.name}</Link>
                  </h3>
                  <p className="mt-3 text-sm text-[var(--af-muted)]">
                    Created {new Date(project.created_at).toLocaleDateString()}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
