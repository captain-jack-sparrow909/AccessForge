import { auth } from '@/auth';
import { importPKCS8, SignJWT } from 'jose';
import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET() {
  const session = await auth();
  if (!session?.user?.id)
    return NextResponse.json({ detail: 'Authentication required.' }, { status: 401 });
  const rawPrivateKey = process.env.BACKEND_TOKEN_PRIVATE_KEY;
  if (!rawPrivateKey)
    return NextResponse.json(
      { detail: 'Backend token signing is not configured.' },
      { status: 503 },
    );
  const privateKey = await importPKCS8(rawPrivateKey.replace(/\\n/g, '\n'), 'ES256');
  const now = Math.floor(Date.now() / 1000);
  const token = await new SignJWT({ email: session.user.email ?? undefined, role: 'member' })
    .setProtectedHeader({ alg: 'ES256', kid: process.env.BACKEND_TOKEN_KID ?? 'default' })
    .setSubject(session.user.id)
    .setIssuer('accessforge-web')
    .setAudience('accessforge-api')
    .setIssuedAt(now)
    .setExpirationTime(now + 300)
    .setJti(crypto.randomUUID())
    .sign(privateKey);
  return NextResponse.json({ access_token: token, token_type: 'Bearer', expires_in: 300 });
}
