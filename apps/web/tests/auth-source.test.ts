import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function source(path: string) {
  return readFileSync(resolve(process.cwd(), path), 'utf8');
}

describe('Better Auth account access', () => {
  it('enables persistent email/password accounts and optional GitHub OAuth', () => {
    const auth = source('src/auth.ts');

    expect(auth).toContain("import { betterAuth } from 'better-auth'");
    expect(auth).toContain('emailAndPassword:');
    expect(auth).toContain('minPasswordLength: 10');
    expect(auth).toContain("modelName: 'auth_user'");
    expect(auth).toContain('encryptOAuthTokens: true');
    expect(auth).toContain('disableImplicitLinking: true');
    expect(auth).toContain('githubConfigured');
    expect(auth).not.toContain('DEV_AUTH_PASSWORD');
  });

  it('mounts Better Auth on the application auth route', () => {
    const route = source('src/app/api/auth/[...all]/route.ts');

    expect(route).toContain("from 'better-auth/next-js'");
    expect(route).toContain('toNextJsHandler(auth)');
    expect(route).toContain('authConfiguration.configured');
    expect(route).toContain('status: 503');
  });

  it('offers accessible sign-in and account-creation fields', () => {
    const form = source('src/app/sign-in/auth-form.tsx');

    expect(form).toContain('type="email"');
    expect(form).toContain('type="password"');
    expect(form).toContain('autoComplete="email"');
    expect(form).toContain("'current-password'");
    expect(form).toContain("'new-password'");
    expect(form).toContain('aria-live="polite"');
    expect(form.match(/className="af-input mt-2"/g)).toHaveLength(3);
    expect(form).toContain('Create account');
  });
});
