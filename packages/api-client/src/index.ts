export type { paths } from './generated';
export type Project = { id: string; name: string; description: string | null; status: string; created_at: string; updated_at: string };
type ProblemDetail = { title?: string; detail?: string };
type ClientOptions = { baseUrl: string; getToken: () => Promise<string> };

async function readError(response: Response): Promise<never> {
  let detail = `Request failed with status ${response.status}.`;
  try { const body = (await response.json()) as ProblemDetail; detail = body.detail ?? body.title ?? detail; } catch { /* Keep the status-based message. */ }
  throw new Error(detail);
}

export function createAccessForgeClient({ baseUrl, getToken }: ClientOptions) {
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const token = await getToken();
    const response = await fetch(`${baseUrl.replace(/\/$/, '')}${path}`, { ...init, headers: { Accept: 'application/json', Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...init?.headers }, cache: 'no-store' });
    if (!response.ok) await readError(response);
    return (await response.json()) as T;
  }
  return { listProjects: () => request<Project[]>('/v1/projects'), createProject: (input: { name: string; description?: string }) => request<Project>('/v1/projects', { method: 'POST', body: JSON.stringify(input) }), getProject: (id: string) => request<Project>(`/v1/projects/${encodeURIComponent(id)}`) };
}
