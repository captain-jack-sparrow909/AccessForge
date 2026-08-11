'use client';

import dynamic from 'next/dynamic';

const InteractiveCandidateModelViewer = dynamic(
  () =>
    import('./interactive-candidate-model-viewer').then(
      (module) => module.InteractiveCandidateModelViewer,
    ),
  {
    ssr: false,
    loading: () => (
      <p role="status" className="mt-4 text-sm text-[var(--af-muted)]">
        Loading the optional 3D preview…
      </p>
    ),
  },
);

type CandidateModelViewerProps = {
  previewUrl: string | null;
  title: string;
  isLoading: boolean;
  message: string;
  onLoad: () => void;
  onHide: () => void;
};

export function CandidateModelViewer({
  previewUrl,
  title,
  isLoading,
  message,
  onLoad,
  onHide,
}: CandidateModelViewerProps) {
  const viewerId = `candidate-preview-${title.replaceAll(/[^a-zA-Z0-9_-]/g, '-').toLowerCase()}`;
  const descriptionId = `${viewerId}-description`;
  return (
    <section
      className="mt-5 rounded-xl border border-[var(--af-line)] bg-[var(--af-paper)] p-4"
      aria-busy={isLoading}
    >
      <h4 className="font-semibold">Optional interactive 3D preview</h4>
      <p id={descriptionId} className="mt-2 text-sm leading-6 text-[var(--af-muted)]">
        The structured candidate report above is the primary record. Loading this private visual is
        optional and may use additional data.
      </p>
      {previewUrl ? (
        <>
          <InteractiveCandidateModelViewer
            previewUrl={previewUrl}
            title={title}
            viewerId={viewerId}
          />
          <button className="af-button af-button-secondary mt-4" type="button" onClick={onHide}>
            Hide optional 3D preview
          </button>
        </>
      ) : (
        <>
          <button
            className="af-button af-button-secondary mt-4"
            type="button"
            aria-describedby={descriptionId}
            disabled={isLoading}
            onClick={onLoad}
          >
            {isLoading ? 'Preparing optional 3D preview…' : 'Load optional interactive 3D preview'}
          </button>
          {message ? (
            <p role="alert" className="mt-3 text-sm text-[var(--af-danger)]">
              {message}
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}
