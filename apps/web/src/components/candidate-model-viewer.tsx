'use client';

import '@google/model-viewer';

export function CandidateModelViewer({ previewUrl, title }: { previewUrl: string; title: string }) {
  return (
    <div className="overflow-hidden rounded-xl border border-[var(--af-line)] bg-[#edf2ee]">
      <model-viewer
        src={previewUrl}
        alt={`Interactive 3D preview of ${title}`}
        camera-controls
        auto-rotate
        shadow-intensity="0.8"
        interaction-prompt="auto"
        style={{ display: 'block', height: '22rem', width: '100%' }}
      >
        <p className="p-5 text-sm text-[var(--af-muted)]">
          This browser could not display the private GLB preview. The structured validation report
          remains available below.
        </p>
      </model-viewer>
      <p className="border-t border-[var(--af-line)] bg-white px-4 py-3 text-sm text-[var(--af-muted)]">
        Drag to inspect the geometry. This is an on-screen representation, not a fit, strength, or
        safety result.
      </p>
    </div>
  );
}
