'use client';

import '@google/model-viewer';

type InteractiveCandidateModelViewerProps = {
  previewUrl: string;
  title: string;
  viewerId: string;
};

/**
 * This component intentionally lives behind a dynamic import. A 3D preview is
 * an optional visual aid, never the only way to inspect a candidate.
 */
export function InteractiveCandidateModelViewer({
  previewUrl,
  title,
  viewerId,
}: InteractiveCandidateModelViewerProps) {
  return (
    <div
      id={viewerId}
      className="mt-4 overflow-hidden rounded-xl border border-[var(--af-line)] bg-[#edf2ee]"
    >
      <model-viewer
        src={previewUrl}
        alt={`Optional interactive 3D preview of ${title}`}
        camera-controls
        interaction-prompt="none"
        shadow-intensity="0.8"
        style={{ display: 'block', height: '22rem', width: '100%' }}
      >
        <p className="p-5 text-sm text-[var(--af-muted)]">
          This browser could not display the optional private GLB preview. The structured candidate
          report remains available above.
        </p>
      </model-viewer>
      <p className="border-t border-[var(--af-line)] bg-white px-4 py-3 text-sm text-[var(--af-muted)]">
        This optional visual view does not add a fit, strength, safety, or physical-use result. Use
        the structured report above for the candidate record and validation findings.
      </p>
    </div>
  );
}
