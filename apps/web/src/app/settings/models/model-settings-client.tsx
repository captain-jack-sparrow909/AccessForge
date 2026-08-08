'use client';

import { useEffect, useState } from 'react';
import type { ModelProviderConfig } from '@accessforge/api-client';
import { useProjectClient } from '@/app/projects/project-api';

type ProviderType = 'deepseek' | 'openai_compatible' | 'openai' | 'anthropic' | 'google' | 'fake';
type CredentialMode = 'byok' | 'deployment_managed' | 'development_fake';

const providerLabels: Record<ProviderType, string> = {
  deepseek: 'DeepSeek',
  openai_compatible: 'Custom OpenAI-compatible endpoint',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  google: 'Google Gemini',
  fake: 'Offline fake provider (development only)',
};

export default function ModelSettingsClient() {
  const client = useProjectClient();
  const [configs, setConfigs] = useState<ModelProviderConfig[]>([]);
  const [message, setMessage] = useState('Loading model configurations…');
  const [busy, setBusy] = useState(false);
  const [providerType, setProviderType] = useState<ProviderType>('deepseek');
  const [credentialMode, setCredentialMode] = useState<CredentialMode>('byok');
  const [label, setLabel] = useState('My DeepSeek key');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [fastModel, setFastModel] = useState('');
  const [reasoningModel, setReasoningModel] = useState('');
  const [visionModel, setVisionModel] = useState('');
  const [embeddingModel, setEmbeddingModel] = useState('');
  const [inputCostPerMillion, setInputCostPerMillion] = useState('');
  const [outputCostPerMillion, setOutputCostPerMillion] = useState('');
  const [shareProjectText, setShareProjectText] = useState(true);
  const [shareMeasurements, setShareMeasurements] = useState(true);
  function load() {
    client
      .listModelProviders()
      .then((items) => {
        setConfigs(items);
        setMessage('');
      })
      .catch((error: unknown) =>
        setMessage(error instanceof Error ? error.message : 'Could not load model configurations.'),
      );
  }
  useEffect(() => {
    load();
    // The client instance is stable for the mounted page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);
  function changeProvider(next: ProviderType) {
    setProviderType(next);
    setCredentialMode(next === 'fake' ? 'development_fake' : 'byok');
    setLabel(next === 'fake' ? 'Synthetic offline demo' : `My ${providerLabels[next]} key`);
    setApiKey('');
    setBaseUrl('');
  }
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const allowedDataCategories = [
      ...(shareProjectText ? (['project_text'] as const) : []),
      ...(shareMeasurements ? (['measurements'] as const) : []),
    ];
    if (allowedDataCategories.length === 0) {
      setMessage('Choose at least one category of derived project data to share.');
      return;
    }
    setBusy(true);
    setMessage('Saving configuration and checking capabilities…');
    try {
      await client.createModelProvider({
        label,
        provider_type: providerType,
        credential_mode: credentialMode,
        ...(credentialMode === 'byok' ? { api_key: apiKey } : {}),
        ...(providerType === 'openai_compatible' && baseUrl ? { base_url: baseUrl } : {}),
        ...(fastModel ? { fast_model: fastModel } : {}),
        ...(reasoningModel ? { reasoning_model: reasoningModel } : {}),
        ...(visionModel ? { vision_model: visionModel } : {}),
        ...(embeddingModel ? { embedding_model: embeddingModel } : {}),
        ...(inputCostPerMillion ? { input_cost_per_million_usd: Number(inputCostPerMillion) } : {}),
        ...(outputCostPerMillion
          ? { output_cost_per_million_usd: Number(outputCostPerMillion) }
          : {}),
        allowed_data_categories: allowedDataCategories,
      });
      setApiKey('');
      setMessage('Configuration saved. Its key is no longer held by this page.');
      load();
    } catch (error: unknown) {
      setMessage(
        error instanceof Error ? error.message : 'Could not save the model configuration.',
      );
    } finally {
      setBusy(false);
    }
  }
  async function testConfig(config: ModelProviderConfig) {
    setBusy(true);
    setMessage(`Testing ${config.label} without project content…`);
    try {
      const updated = await client.testModelProvider(config.id);
      setConfigs((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setMessage('Capability check completed. Review the reported capabilities before use.');
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Could not test this configuration.');
    } finally {
      setBusy(false);
    }
  }
  async function revokeConfig(config: ModelProviderConfig) {
    if (!window.confirm(`Revoke ${config.label}? Its stored credential will be removed.`)) return;
    setBusy(true);
    setMessage('Revoking configuration…');
    try {
      await client.revokeModelProvider(config.id);
      setConfigs((current) => current.filter((item) => item.id !== config.id));
      setMessage(
        'Configuration revoked. Existing AI runs retain only non-sensitive audit metadata.',
      );
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Could not revoke this configuration.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="af-container max-w-4xl py-12">
      <p className="af-eyebrow">Model provider settings</p>
      <h1 className="mt-4 text-4xl font-bold tracking-tight">
        Choose an AI provider with clear boundaries.
      </h1>
      <p className="mt-4 max-w-3xl leading-7 text-[var(--af-muted)]">
        AccessForge sends only the derived text and measurements you choose, and only after separate
        project consent. It never sends raw images or videos in this phase. A provider can propose
        requirements; it cannot generate geometry or declare an output safe.
      </p>
      <form className="af-card mt-8 space-y-6 p-7" onSubmit={save}>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <label className="font-semibold" htmlFor="provider-type">
              Provider
            </label>
            <select
              className="af-input mt-2"
              id="provider-type"
              value={providerType}
              onChange={(event) => changeProvider(event.target.value as ProviderType)}
            >
              {Object.entries(providerLabels).map(([value, text]) => (
                <option key={value} value={value}>
                  {text}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="font-semibold" htmlFor="provider-label">
              Label
            </label>
            <input
              required
              className="af-input mt-2"
              id="provider-label"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
            />
          </div>
        </div>
        {providerType !== 'fake' ? (
          <fieldset>
            <legend className="font-semibold">Credential source</legend>
            <div className="mt-3 flex flex-wrap gap-4">
              <label className="flex gap-2">
                <input
                  type="radio"
                  checked={credentialMode === 'byok'}
                  onChange={() => setCredentialMode('byok')}
                />
                Bring my own key
              </label>
              <label className="flex gap-2">
                <input
                  type="radio"
                  checked={credentialMode === 'deployment_managed'}
                  onChange={() => setCredentialMode('deployment_managed')}
                />
                Use deployment-managed key
              </label>
            </div>
          </fieldset>
        ) : null}
        {credentialMode === 'byok' ? (
          <div>
            <label className="font-semibold" htmlFor="provider-key">
              API key
            </label>
            <input
              required
              className="af-input mt-2"
              id="provider-key"
              type="password"
              autoComplete="off"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
            />
            <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
              The key is sent once to the backend, encrypted there, and never returned to this page.
            </p>
          </div>
        ) : null}
        {providerType === 'openai_compatible' ? (
          <div>
            <label className="font-semibold" htmlFor="provider-url">
              HTTPS endpoint
            </label>
            <input
              required
              className="af-input mt-2"
              id="provider-url"
              type="url"
              placeholder="https://provider.example/v1"
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
            />
            <p className="mt-2 text-sm text-[var(--af-muted)]">
              Hosted deployments reject private, loopback, credentialed, or non-HTTPS endpoints.
            </p>
          </div>
        ) : null}
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <label className="font-semibold" htmlFor="fast-model">
              Fast extraction model
            </label>
            <input
              className="af-input mt-2"
              id="fast-model"
              value={fastModel}
              onChange={(event) => setFastModel(event.target.value)}
            />
          </div>
          <div>
            <label className="font-semibold" htmlFor="reasoning-model">
              Planning model (optional)
            </label>
            <input
              className="af-input mt-2"
              id="reasoning-model"
              value={reasoningModel}
              onChange={(event) => setReasoningModel(event.target.value)}
            />
          </div>
          <div>
            <label className="font-semibold" htmlFor="vision-model">
              Vision model (reserved for a later phase)
            </label>
            <input
              className="af-input mt-2"
              id="vision-model"
              value={visionModel}
              onChange={(event) => setVisionModel(event.target.value)}
            />
          </div>
          <div>
            <label className="font-semibold" htmlFor="embedding-model">
              Embedding model (optional)
            </label>
            <input
              className="af-input mt-2"
              id="embedding-model"
              value={embeddingModel}
              onChange={(event) => setEmbeddingModel(event.target.value)}
            />
          </div>
        </div>
        <fieldset>
          <legend className="font-semibold">Optional usage-cost estimate</legend>
          <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
            Enter the model&apos;s current USD price per million tokens if you want completed runs
            to retain an estimate. Leave both blank when pricing is unknown; AccessForge will not
            guess.
          </p>
          <div className="mt-3 grid gap-5 sm:grid-cols-2">
            <div>
              <label className="font-semibold" htmlFor="input-cost">
                Input USD / 1M tokens
              </label>
              <input
                className="af-input mt-2"
                id="input-cost"
                min="0"
                step="any"
                type="number"
                value={inputCostPerMillion}
                onChange={(event) => setInputCostPerMillion(event.target.value)}
              />
            </div>
            <div>
              <label className="font-semibold" htmlFor="output-cost">
                Output USD / 1M tokens
              </label>
              <input
                className="af-input mt-2"
                id="output-cost"
                min="0"
                step="any"
                type="number"
                value={outputCostPerMillion}
                onChange={(event) => setOutputCostPerMillion(event.target.value)}
              />
            </div>
          </div>
        </fieldset>
        <fieldset>
          <legend className="font-semibold">
            What may leave AccessForge for this configuration?
          </legend>
          <div className="mt-3 space-y-3">
            <label className="flex gap-3">
              <input
                className="mt-1 h-5 w-5"
                type="checkbox"
                checked={shareProjectText}
                onChange={(event) => setShareProjectText(event.target.checked)}
              />
              <span>Derived project text and text observations</span>
            </label>
            <label className="flex gap-3">
              <input
                className="mt-1 h-5 w-5"
                type="checkbox"
                checked={shareMeasurements}
                onChange={(event) => setShareMeasurements(event.target.checked)}
              />
              <span>Manual measurements and confirmation state</span>
            </label>
          </div>
        </fieldset>
        <div className="flex flex-wrap items-center gap-4">
          <button className="af-button af-button-primary" type="submit" disabled={busy}>
            {busy ? 'Saving…' : 'Save configuration'}
          </button>
          <span role="status" className="text-sm text-[var(--af-muted)]">
            {message}
          </span>
        </div>
      </form>
      <section className="mt-10" aria-labelledby="configured-providers">
        <h2 id="configured-providers" className="text-2xl font-bold">
          Saved configurations
        </h2>
        {configs.length === 0 ? (
          <p className="mt-4 text-[var(--af-muted)]">
            No provider is configured. Your project workflow still works without AI.
          </p>
        ) : (
          <ul className="mt-4 space-y-4">
            {configs.map((config) => (
              <li className="af-card p-6" key={config.id}>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-sm text-[var(--af-muted)]">
                      {providerLabels[config.provider_type as ProviderType] ?? config.provider_type}
                    </p>
                    <h3 className="mt-1 text-xl font-bold">{config.label}</h3>
                    <p className="mt-2 text-sm text-[var(--af-muted)]">
                      {config.credential_fingerprint ??
                        'Deployment-managed or development credential'}{' '}
                      · {config.status}
                    </p>
                  </div>
                  <div className="flex gap-3">
                    <button
                      className="af-button af-button-secondary"
                      type="button"
                      disabled={busy}
                      onClick={() => void testConfig(config)}
                    >
                      Test
                    </button>
                    <button
                      className="af-button af-button-secondary text-[var(--af-danger)]"
                      type="button"
                      disabled={busy}
                      onClick={() => void revokeConfig(config)}
                    >
                      Revoke
                    </button>
                  </div>
                </div>
                <p className="mt-4 text-sm leading-6 text-[var(--af-muted)]">
                  Data categories: {config.allowed_data_categories.join(', ') || 'none'}. Structured
                  JSON: {config.capabilities?.structured_json ?? 'not checked'}.
                </p>
                <p className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
                  Usage estimate: {formatCostRate(config.input_cost_per_million_usd)} input /{' '}
                  {formatCostRate(config.output_cost_per_million_usd)} output per 1M tokens.
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function formatCostRate(value: number | null): string {
  return value === null ? 'not configured' : `$${value.toFixed(4)}`;
}
