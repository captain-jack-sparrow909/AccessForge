import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function source(path: string) {
  return readFileSync(resolve(process.cwd(), path), 'utf8');
}

describe('Phase 7 accessibility source safeguards', () => {
  it('keeps the 3D viewer optional, lazy, and free of automatic rotation', () => {
    const viewer = source('src/components/candidate-model-viewer.tsx');
    const interactiveViewer = source('src/components/interactive-candidate-model-viewer.tsx');
    const designs = source('src/app/projects/[projectId]/designs/page.tsx');

    expect(viewer).toContain('dynamic(');
    expect(viewer).toContain('Load optional interactive 3D preview');
    expect(viewer).not.toContain("import '@google/model-viewer'");
    expect(interactiveViewer).not.toContain('auto-rotate');
    expect(designs).toContain('async function loadPreview()');
    expect(designs).not.toMatch(/useEffect\([\s\S]{0,500}getCandidatePreview/);
    expect(designs.indexOf('Structured candidate report')).toBeLessThan(
      designs.indexOf('<CandidateModelViewer'),
    );
  });

  it('keeps capture inputs keyboard-reachable with explicit help text', () => {
    const capture = source('src/app/projects/[projectId]/capture/page.tsx');

    expect(capture).not.toContain('className="sr-only"');
    expect(capture).toContain('htmlFor="still-image"');
    expect(capture).toContain('htmlFor="video"');
    expect(capture).toContain('aria-describedby="still-image-help"');
    expect(capture).toContain('aria-describedby="video-help"');
    expect(capture).toContain('aria-busy={busy}');
    expect(capture.match(/className="af-input mt-2"/g)).toHaveLength(2);
  });

  it('preserves explicit visible-focus, reduced-motion, forced-colors, and reflow safeguards', () => {
    const styles = source('src/app/globals.css');
    const layout = source('src/app/layout.tsx');

    expect(styles).toContain(':focus-visible');
    expect(styles).toContain('@media (prefers-reduced-motion: reduce)');
    expect(styles).toContain('@media (forced-colors: active)');
    expect(styles).toContain('select,');
    expect(styles).toContain('summary,');
    expect(layout).toContain('flex-wrap');
    expect(layout).toContain('min-h-11');
  });
});
