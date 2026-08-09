import type { DetailedHTMLProps, HTMLAttributes } from 'react';

declare module 'react' {
  namespace JSX {
    interface IntrinsicElements {
      'model-viewer': DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement> & {
        src?: string;
        alt?: string;
        'auto-rotate'?: boolean;
        'camera-controls'?: boolean;
        'interaction-prompt'?: 'auto' | 'none' | 'when-focused';
        'shadow-intensity'?: string;
      };
    }
  }
}
