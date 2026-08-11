import { auth, authConfiguration } from '@/auth';
import { toNextJsHandler } from 'better-auth/next-js';

const handlers = toNextJsHandler(auth);

function unavailable() {
  return Response.json({ detail: 'Authentication is not configured.' }, { status: 503 });
}

export const GET = authConfiguration.configured ? handlers.GET : unavailable;
export const POST = authConfiguration.configured ? handlers.POST : unavailable;
