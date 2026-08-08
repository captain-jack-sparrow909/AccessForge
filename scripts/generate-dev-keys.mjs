import { execFileSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const root = resolve(new URL('..', import.meta.url).pathname);
const webEnvPath = resolve(root, 'apps/web/.env.local');
const composeEnvPath = resolve(root, '.env');
if (existsSync(webEnvPath) || existsSync(composeEnvPath)) {
  console.error('Local environment already exists; rotate it manually if intended.');
  process.exit(1);
}
const privateKey = execFileSync('openssl', [
  'ecparam',
  '-name',
  'prime256v1',
  '-genkey',
  '-noout',
]).toString();
const publicKey = execFileSync('openssl', ['ec', '-pubout'], { input: privateKey }).toString();
const escapedPrivateKey = privateKey.replaceAll('\n', '\\n');
const publicKeyJson = JSON.stringify({ local: publicKey });
mkdirSync(dirname(webEnvPath), { recursive: true });
writeFileSync(
  webEnvPath,
  [
    `AUTH_SECRET=${randomBytes(32).toString('base64url')}`,
    'AUTH_TRUST_HOST=true',
    'DEV_AUTH_ENABLED=true',
    'DEV_AUTH_EMAIL=demo@accessforge.local',
    'DEV_AUTH_PASSWORD=accessforge-local-only',
    'NEXT_PUBLIC_API_URL=http://localhost:8000',
    `BACKEND_TOKEN_PRIVATE_KEY=${escapedPrivateKey}`,
    'BACKEND_TOKEN_KID=local',
    '',
  ].join('\n'),
  { mode: 0o600 },
);
writeFileSync(
  composeEnvPath,
  [`BACKEND_TOKEN_PUBLIC_KEYS_JSON=${JSON.stringify(publicKeyJson)}`, ''].join('\n'),
  { mode: 0o600 },
);
console.log(
  'Created apps/web/.env.local and .env for local development. These files are gitignored.',
);
