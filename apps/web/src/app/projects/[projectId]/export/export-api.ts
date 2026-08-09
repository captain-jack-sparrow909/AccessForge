'use client';

const ACKNOWLEDGEMENT_VERSION = 'phase6-controlled-export.v1';

export type ExportCandidate = {
  id: string;
  candidate_number: number;
  status: string;
  template_id: string;
  template_version: string;
  validation_status: string | null;
  completed_at: string | null;
};

export type ExportReadiness = {
  allowed: boolean;
  reasons: string[];
  acknowledgement_version?: string;
  limitations?: string;
  artifact_manifest_hash?: string | null;
  validation_report_hash?: string | null;
  risk_decision_hash?: string | null;
  artifact_manifest?: Record<string, unknown>;
};

export type ExportApproval = {
  id: string;
  status?: string;
  approval_hash?: string;
  approved_at?: string;
};

export type PrivateExportBundle = {
  id: string;
  filename: string;
  status: string;
  checksum_sha256: string;
  size_bytes: number;
  created_at: string;
  revoked_at?: string | null;
};

export type FeedbackReceipt = {
  id: string;
  category: string;
  severity: string;
  created_at: string;
};

export type HazardReceipt = {
  id: string;
  candidate_id: string;
  feedback_report_id: string | null;
  status: string;
  reported_at: string;
};

type ProblemDetail = { title?: string; detail?: string };

function apiUrl(path: string) {
  const baseUrl = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');
  return `${baseUrl}${path}`;
}

async function backendToken() {
  const response = await fetch('/api/backend-token', { cache: 'no-store' });
  if (!response.ok) throw new Error('Your session is not ready for private project access.');
  const payload = (await response.json()) as { access_token?: string };
  if (!payload.access_token) throw new Error('Your session token is unavailable.');
  return payload.access_token;
}

async function readError(response: Response): Promise<never> {
  let detail = `Request failed with status ${response.status}.`;
  try {
    const payload = (await response.json()) as ProblemDetail;
    detail = payload.detail ?? payload.title ?? detail;
  } catch {
    // Keep the status-based fallback when an intermediary returned non-JSON.
  }
  throw new Error(detail);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await backendToken();
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${token}`,
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
    cache: 'no-store',
  });
  if (!response.ok) await readError(response);
  return (await response.json()) as T;
}

async function requestPrivateZip(path: string): Promise<Blob> {
  const token = await backendToken();
  const response = await fetch(apiUrl(path), {
    headers: {
      Accept: 'application/zip',
      Authorization: `Bearer ${token}`,
    },
    cache: 'no-store',
  });
  if (!response.ok) await readError(response);
  return response.blob();
}

function candidatePath(projectId: string, candidateId: string) {
  return `/v1/projects/${encodeURIComponent(projectId)}/candidates/${encodeURIComponent(candidateId)}`;
}

export const acknowledgementVersion = ACKNOWLEDGEMENT_VERSION;

export function listExportCandidates(projectId: string) {
  return request<ExportCandidate[]>(`/v1/projects/${encodeURIComponent(projectId)}/candidates`);
}

export function getExportReadiness(projectId: string, candidateId: string) {
  return request<ExportReadiness>(`${candidatePath(projectId, candidateId)}/export-readiness`);
}

export function createExportApproval(
  projectId: string,
  candidateId: string,
  acknowledgements: Record<string, boolean>,
  idempotencyKey: string,
) {
  return request<ExportApproval>(`${candidatePath(projectId, candidateId)}:approve-export`, {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({
      acknowledgement_version: ACKNOWLEDGEMENT_VERSION,
      acknowledgements,
    }),
  });
}

export function createPrivateExport(
  projectId: string,
  candidateId: string,
  approvalEventId: string,
  idempotencyKey: string,
) {
  return request<PrivateExportBundle>(`${candidatePath(projectId, candidateId)}:export`, {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ approval_event_id: approvalEventId }),
  });
}

export function listPrivateExportBundles(projectId: string, candidateId: string) {
  return request<PrivateExportBundle[]>(`${candidatePath(projectId, candidateId)}/exports`);
}

export function downloadPrivateExportBundle(projectId: string, bundleId: string) {
  return requestPrivateZip(
    `/v1/projects/${encodeURIComponent(projectId)}/exports/${encodeURIComponent(bundleId)}/download`,
  );
}

export function submitCandidateFeedback(
  projectId: string,
  candidateId: string,
  input: { category: string; severity: string; summary: string },
) {
  return request<FeedbackReceipt>(`${candidatePath(projectId, candidateId)}/feedback`, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function reportCandidateHazard(
  projectId: string,
  candidateId: string,
  input: { severity: string; summary: string },
) {
  return request<HazardReceipt>(`${candidatePath(projectId, candidateId)}:report-hazard`, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}
