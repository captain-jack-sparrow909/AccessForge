'use client';

import { useMemo } from 'react';
import { createAccessForgeClient } from '@accessforge/api-client';

export function useProjectClient() {
  return useMemo(
    () =>
      createAccessForgeClient({
        baseUrl: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000',
        getToken: async () => {
          const response = await fetch('/api/backend-token', { cache: 'no-store' });
          if (!response.ok)
            throw new Error('Your session is not ready for private project access.');
          return ((await response.json()) as { access_token: string }).access_token;
        },
      }),
    [],
  );
}

export async function sha256Hex(file: File): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}
