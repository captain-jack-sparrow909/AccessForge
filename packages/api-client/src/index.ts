export type { paths } from './generated';
export type Project = {
  id: string;
  name: string;
  description: string | null;
  goal: string | null;
  object_description: string | null;
  action_description: string | null;
  environment: string | null;
  load_context: string | null;
  safety_system: boolean | null;
  age_context: string | null;
  scope_status: string;
  scope_reason: string | null;
  model_provider_config_id: string | null;
  active_requirement_revision_id: string | null;
  status: string;
  version: number;
  created_at: string;
  updated_at: string;
};
export type ConsentRecord = {
  id: string;
  participant_id: string;
  consent_type: string;
  granted: boolean;
  consent_version: string;
  recorded_at: string;
  revoked_at: string | null;
};
export type ConsentResponse = {
  participant: {
    id: string;
    display_name: string;
    role: string;
    relationship_to_user: string | null;
  };
  records: ConsentRecord[];
  project_status: string;
};
export type Observation = {
  id: string;
  text: string;
  input_mode: string;
  source: string;
  created_at: string;
  updated_at: string;
  version: number;
};
export type Measurement = {
  id: string;
  kind: string;
  value: number | null;
  unit: string;
  canonical_value_mm: number | null;
  tolerance: number | null;
  canonical_tolerance_mm: number | null;
  method: string;
  source: string;
  confirmed: boolean;
  unknown: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
  version: number;
};
export type MediaAsset = {
  id: string;
  media_type: string;
  content_type: string;
  original_name: string | null;
  expected_size: number;
  actual_size: number | null;
  checksum_sha256: string | null;
  status: string;
  expires_at: string;
  created_at: string;
  updated_at: string;
  version: number;
};
export type AssetPresignResponse = {
  asset_id: string;
  upload_url: string;
  expires_at: string;
  object_key: string;
  max_size_bytes: number;
};
export type ProviderCapabilities = {
  structured_json: 'confirmed' | 'unsupported' | 'unknown';
  native_json_schema: 'confirmed' | 'unsupported' | 'unknown';
  tool_calling: 'confirmed' | 'unsupported' | 'unknown';
  vision_input: 'confirmed' | 'unsupported' | 'unknown';
  streaming: 'confirmed' | 'unsupported' | 'unknown';
  max_context_tokens: number | null;
  max_output_tokens: number | null;
  supported_content_types: string[];
  reasoning_output: 'confirmed' | 'unsupported' | 'unknown';
};
export type ModelProviderConfig = {
  id: string;
  label: string;
  provider_type: string;
  credential_mode: string;
  credential_fingerprint: string | null;
  base_url: string | null;
  fast_model: string | null;
  reasoning_model: string | null;
  vision_model: string | null;
  embedding_model: string | null;
  input_cost_per_million_usd: number | null;
  output_cost_per_million_usd: number | null;
  allowed_data_categories: string[];
  capabilities: ProviderCapabilities | null;
  capabilities_checked_at: string | null;
  last_tested_at: string | null;
  last_error_code: string | null;
  status: string;
  revoked_at: string | null;
  created_at: string;
  updated_at: string;
  version: number;
};
export type RequirementProposal = {
  kind: string;
  value_number: number | null;
  value_text: string | null;
  unit: string | null;
  source_refs: string[];
  confidence: number;
  needs_confirmation: boolean;
  explanation: string;
};
export type RequirementRevision = {
  id: string;
  revision_number: number;
  source: string;
  status: string;
  agent_run_id: string | null;
  provider_config_id: string | null;
  prompt_id: string | null;
  prompt_hash: string | null;
  requirements: Array<RequirementProposal & { id: string; provenance: Record<string, unknown> }>;
  unknowns: Array<{ kind: string; explanation: string; source_refs: string[] }>;
  clarifying_questions: Array<{
    id: string;
    question: string;
    why_it_matters: string;
    priority: number;
    related_source_refs: string[];
  }>;
  risk_signals: Array<{
    kind: string;
    level: 'needs_confirmation' | 'blocked';
    explanation: string;
    source_refs: string[];
  }>;
  rationale: string | null;
  content_hash: string;
  created_at: string;
  confirmed_at: string | null;
  confirmed_by: string | null;
};
type ProblemDetail = { title?: string; detail?: string };
type ClientOptions = { baseUrl: string; getToken: () => Promise<string> };

async function readError(response: Response): Promise<never> {
  let detail = `Request failed with status ${response.status}.`;
  try {
    const body = (await response.json()) as ProblemDetail;
    detail = body.detail ?? body.title ?? detail;
  } catch {
    /* Keep the status-based message. */
  }
  throw new Error(detail);
}

export function createAccessForgeClient({ baseUrl, getToken }: ClientOptions) {
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const token = await getToken();
    const response = await fetch(`${baseUrl.replace(/\/$/, '')}${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...init?.headers,
      },
      cache: 'no-store',
    });
    if (!response.ok) await readError(response);
    return (await response.json()) as T;
  }
  return {
    listProjects: () => request<Project[]>('/v1/projects'),
    createProject: (input: {
      name: string;
      description?: string;
      goal?: string;
      object_description?: string;
      action_description?: string;
      environment?: string;
      load_context?: string;
      safety_system?: boolean;
      age_context?: string;
    }) => request<Project>('/v1/projects', { method: 'POST', body: JSON.stringify(input) }),
    getProject: (id: string) => request<Project>(`/v1/projects/${encodeURIComponent(id)}`),
    updateProject: (id: string, input: Record<string, unknown>) =>
      request<Project>(`/v1/projects/${encodeURIComponent(id)}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    deleteProject: (id: string) =>
      request<{ project_id: string; status: string }>(`/v1/projects/${encodeURIComponent(id)}`, {
        method: 'DELETE',
      }),
    listConsents: (id: string) =>
      request<ConsentResponse[]>(`/v1/projects/${encodeURIComponent(id)}/consents`),
    createConsent: (
      id: string,
      input: {
        display_name: string;
        role: 'participant' | 'co_designer' | 'helper';
        relationship_to_user?: string;
        choices: Record<string, boolean>;
      },
    ) =>
      request<ConsentResponse>(`/v1/projects/${encodeURIComponent(id)}/consents`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    listObservations: (id: string) =>
      request<Observation[]>(`/v1/projects/${encodeURIComponent(id)}/observations`),
    createObservation: (id: string, input: { text?: string; input_mode: 'text' | 'skipped' }) =>
      request<Observation>(`/v1/projects/${encodeURIComponent(id)}/observations`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    listMeasurements: (id: string) =>
      request<Measurement[]>(`/v1/projects/${encodeURIComponent(id)}/measurements`),
    createMeasurement: (
      id: string,
      input: {
        kind: string;
        value?: number;
        unit: 'mm' | 'cm' | 'in';
        tolerance?: number;
        method: 'ruler' | 'caliper' | 'visual_estimate' | 'other';
        confirmed?: boolean;
        unknown?: boolean;
        notes?: string;
      },
    ) =>
      request<Measurement>(`/v1/projects/${encodeURIComponent(id)}/measurements`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    updateMeasurement: (projectId: string, measurementId: string, input: Record<string, unknown>) =>
      request<Measurement>(
        `/v1/projects/${encodeURIComponent(projectId)}/measurements/${encodeURIComponent(measurementId)}`,
        { method: 'PATCH', body: JSON.stringify(input) },
      ),
    listAssets: (id: string) =>
      request<MediaAsset[]>(`/v1/projects/${encodeURIComponent(id)}/assets`),
    presignUpload: (
      id: string,
      input: {
        media_type: 'still_image' | 'video';
        content_type: string;
        size_bytes: number;
        original_name?: string;
      },
    ) =>
      request<AssetPresignResponse>(
        `/v1/projects/${encodeURIComponent(id)}/assets/presign-upload`,
        {
          method: 'POST',
          body: JSON.stringify(input),
        },
      ),
    completeUpload: (
      projectId: string,
      assetId: string,
      input: { actual_size_bytes: number; checksum_sha256: string },
    ) =>
      request<MediaAsset>(
        `/v1/projects/${encodeURIComponent(projectId)}/assets/${encodeURIComponent(assetId)}/complete`,
        { method: 'POST', body: JSON.stringify(input) },
      ),
    getAssetDownload: (projectId: string, assetId: string) =>
      request<{ asset: MediaAsset; download_url: string; expires_at: string }>(
        `/v1/projects/${encodeURIComponent(projectId)}/assets/${encodeURIComponent(assetId)}/download`,
      ),
    listModelProviders: () => request<ModelProviderConfig[]>('/v1/model-providers'),
    createModelProvider: (input: {
      label: string;
      provider_type: 'deepseek' | 'openai_compatible' | 'openai' | 'anthropic' | 'google' | 'fake';
      credential_mode: 'byok' | 'deployment_managed' | 'development_fake';
      api_key?: string;
      base_url?: string;
      fast_model?: string;
      reasoning_model?: string;
      vision_model?: string;
      embedding_model?: string;
      input_cost_per_million_usd?: number;
      output_cost_per_million_usd?: number;
      allowed_data_categories: Array<'project_text' | 'measurements'>;
    }) =>
      request<ModelProviderConfig>('/v1/model-providers', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    testModelProvider: (id: string) =>
      request<ModelProviderConfig>(`/v1/model-providers/${encodeURIComponent(id)}:test`, {
        method: 'POST',
      }),
    revokeModelProvider: (id: string) =>
      request<{ id: string; status: string }>(`/v1/model-providers/${encodeURIComponent(id)}`, {
        method: 'DELETE',
      }),
    listRequirements: (projectId: string) =>
      request<RequirementRevision[]>(`/v1/projects/${encodeURIComponent(projectId)}/requirements`),
    extractRequirements: (projectId: string, input: { provider_config_id?: string }) =>
      request<RequirementRevision>(
        `/v1/projects/${encodeURIComponent(projectId)}/requirements:extract`,
        { method: 'POST', body: JSON.stringify(input) },
      ),
    confirmRequirements: (
      projectId: string,
      revisionId: string,
      input: {
        requirements: RequirementProposal[];
        unknowns: RequirementRevision['unknowns'];
        clarifying_questions: RequirementRevision['clarifying_questions'];
        risk_signals: RequirementRevision['risk_signals'];
        rationale?: string;
      },
    ) =>
      request<RequirementRevision>(
        `/v1/projects/${encodeURIComponent(projectId)}/requirements/${encodeURIComponent(revisionId)}:confirm`,
        { method: 'POST', body: JSON.stringify(input) },
      ),
  };
}
