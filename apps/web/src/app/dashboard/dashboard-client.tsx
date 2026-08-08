'use client';

import { useEffect, useMemo, useState } from 'react';
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
    <div className="af-container py-16">
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <p className="af-eyebrow">Private dashboard</p>
          <h1 className="mt-4 text-4xl font-bold tracking-tight">Your access projects</h1>
          <p className="mt-3 text-[var(--af-muted)]">Signed in as {email}</p>
        </div>
        <span role="status" className="text-sm text-[var(--af-muted)]">
          {status}
        </span>
      </div>
      <section className="af-card mt-10 p-6" aria-labelledby="new-project-heading">
        <h2 id="new-project-heading" className="text-xl font-bold">
          Create an empty project
        </h2>
        <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
          Capture and AI workflows arrive in later phases. This slice proves identity and private
          project ownership.
        </p>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row">
          <label className="sr-only" htmlFor="project-name">
            Project name
          </label>
          <input
            className="min-h-11 flex-1 rounded-lg border border-[var(--af-line)] bg-white px-3"
            id="project-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <button
            className="af-button af-button-primary"
            type="button"
            onClick={createProject}
            disabled={!name.trim()}
          >
            Create project
          </button>
        </div>
      </section>
      <section className="mt-8" aria-labelledby="projects-heading">
        <h2 id="projects-heading" className="text-xl font-bold">
          Projects
        </h2>
        {projects.length === 0 ? (
          <div className="af-card mt-4 p-6 text-[var(--af-muted)]">No projects yet.</div>
        ) : (
          <ul className="mt-4 grid gap-4 md:grid-cols-2">
            {projects.map((project) => (
              <li className="af-card p-6" key={project.id}>
                <p className="text-sm text-[var(--af-muted)]">{project.status}</p>
                <h3 className="mt-2 text-lg font-bold">{project.name}</h3>
                <p className="mt-2 text-sm text-[var(--af-muted)]">
                  Created {new Date(project.created_at).toLocaleString()}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
