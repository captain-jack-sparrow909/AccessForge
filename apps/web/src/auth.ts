import { betterAuth } from 'better-auth';
import { nextCookies } from 'better-auth/next-js';
import { headers } from 'next/headers';
import { Pool } from 'pg';

const databaseUrl = process.env.BETTER_AUTH_DATABASE_URL ?? process.env.DATABASE_URL;
const authSecret = process.env.BETTER_AUTH_SECRET ?? process.env.AUTH_SECRET;
const authConfigured = Boolean(databaseUrl && authSecret);
const githubConfigured = Boolean(process.env.AUTH_GITHUB_ID && process.env.AUTH_GITHUB_SECRET);

const authPool = new Pool({
  connectionString: databaseUrl,
  max: 5,
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 10_000,
  allowExitOnIdle: true,
});

export const auth = betterAuth({
  appName: 'AccessForge',
  baseURL: process.env.BETTER_AUTH_URL ?? process.env.NEXT_PUBLIC_APP_URL,
  // The public sign-in screen remains renderable before setup. Auth API routes
  // return 503 until both real values are present, so this disabled-state
  // placeholder can never authorize a session.
  secret: authSecret ?? 'accessforge-auth-disabled-until-server-configuration',
  database: authPool,
  emailAndPassword: {
    enabled: true,
    autoSignIn: true,
    minPasswordLength: 10,
    maxPasswordLength: 128,
  },
  socialProviders:
    authConfigured && githubConfigured
      ? {
          github: {
            clientId: process.env.AUTH_GITHUB_ID!,
            clientSecret: process.env.AUTH_GITHUB_SECRET!,
          },
        }
      : undefined,
  user: { modelName: 'auth_user' },
  session: { modelName: 'auth_session' },
  account: {
    modelName: 'auth_account',
    encryptOAuthTokens: true,
    accountLinking: {
      enabled: true,
      disableImplicitLinking: true,
      allowDifferentEmails: false,
    },
  },
  verification: { modelName: 'auth_verification' },
  advanced: {
    cookiePrefix: 'accessforge',
  },
  plugins: [nextCookies()],
});

export async function getSession() {
  if (!authConfigured) return null;
  return auth.api.getSession({ headers: await headers() });
}

export const authConfiguration = {
  configured: authConfigured,
  githubConfigured,
};
