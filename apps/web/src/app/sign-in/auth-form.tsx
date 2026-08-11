'use client';

import { useRouter } from 'next/navigation';
import { FormEvent, useState } from 'react';
import { authClient } from '@/auth-client';

type Mode = 'sign-in' | 'sign-up';

function friendlyAuthError(message?: string) {
  if (!message) return 'We could not complete that request. Please try again.';
  if (/invalid email or password/i.test(message)) return 'The email or password is incorrect.';
  if (/user already exists/i.test(message)) return 'An account already exists for this email.';
  if (/password/i.test(message) && /10|short|length/i.test(message))
    return 'Use a password with at least 10 characters.';
  return message;
}

export function AuthForm({
  enabled,
  githubConfigured,
}: {
  enabled: boolean;
  githubConfigured: boolean;
}) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>('sign-in');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

  function changeMode(nextMode: Mode) {
    setMode(nextMode);
    setError('');
    setPassword('');
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !enabled) return;
    setPending(true);
    setError('');

    const normalizedEmail = email.trim().toLowerCase();
    const result =
      mode === 'sign-in'
        ? await authClient.signIn.email({
            email: normalizedEmail,
            password,
            callbackURL: '/dashboard',
          })
        : await authClient.signUp.email({
            name: name.trim(),
            email: normalizedEmail,
            password,
            callbackURL: '/dashboard',
          });

    if (result.error) {
      setError(friendlyAuthError(result.error.message));
      setPending(false);
      return;
    }

    router.push('/dashboard');
    router.refresh();
  }

  async function continueWithGitHub() {
    if (pending || !enabled) return;
    setPending(true);
    setError('');
    const result = await authClient.signIn.social({
      provider: 'github',
      callbackURL: '/dashboard',
    });
    if (result?.error) {
      setError(friendlyAuthError(result.error.message));
      setPending(false);
    }
  }

  return (
    <div className="mt-8">
      <div
        className="grid grid-cols-2 rounded-2xl bg-[var(--af-paper)] p-1"
        aria-label="Account action"
      >
        <button
          className={`rounded-xl px-4 py-3 text-sm font-extrabold transition ${
            mode === 'sign-in'
              ? 'bg-white text-[var(--af-ink)] shadow-sm'
              : 'text-[var(--af-muted)] hover:text-[var(--af-ink)]'
          }`}
          type="button"
          aria-pressed={mode === 'sign-in'}
          onClick={() => changeMode('sign-in')}
        >
          Sign in
        </button>
        <button
          className={`rounded-xl px-4 py-3 text-sm font-extrabold transition ${
            mode === 'sign-up'
              ? 'bg-white text-[var(--af-ink)] shadow-sm'
              : 'text-[var(--af-muted)] hover:text-[var(--af-ink)]'
          }`}
          type="button"
          aria-pressed={mode === 'sign-up'}
          onClick={() => changeMode('sign-up')}
        >
          Create account
        </button>
      </div>

      <form className="mt-6 space-y-4" onSubmit={submit}>
        {mode === 'sign-up' ? (
          <label className="block text-sm font-bold text-[var(--af-ink)]">
            Name
            <input
              className="af-input mt-2"
              type="text"
              name="name"
              autoComplete="name"
              required
              disabled={!enabled}
              maxLength={100}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Your name"
            />
          </label>
        ) : null}
        <label className="block text-sm font-bold text-[var(--af-ink)]">
          Email
          <input
            className="af-input mt-2"
            type="email"
            name="email"
            autoComplete="email"
            inputMode="email"
            required
            disabled={!enabled}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
          />
        </label>
        <label className="block text-sm font-bold text-[var(--af-ink)]">
          Password
          <input
            className="af-input mt-2"
            type="password"
            name="password"
            autoComplete={mode === 'sign-in' ? 'current-password' : 'new-password'}
            required
            disabled={!enabled}
            minLength={10}
            maxLength={128}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder={mode === 'sign-in' ? 'Your password' : 'At least 10 characters'}
          />
        </label>

        <div className="min-h-6" aria-live="polite">
          {error ? (
            <p className="text-sm font-semibold text-[var(--af-danger)]" role="alert">
              {error}
            </p>
          ) : null}
        </div>

        <button
          className="af-button af-button-primary w-full"
          type="submit"
          disabled={pending || !enabled}
        >
          {pending ? 'Please wait…' : mode === 'sign-in' ? 'Sign in with email' : 'Create account'}
          {!pending ? <span aria-hidden="true">→</span> : null}
        </button>
      </form>

      {githubConfigured ? (
        <>
          <div className="my-6 flex items-center gap-3 text-xs font-bold uppercase tracking-[0.12em] text-[var(--af-muted)]">
            <span className="h-px flex-1 bg-[var(--af-line)]" />
            or
            <span className="h-px flex-1 bg-[var(--af-line)]" />
          </div>
          <button
            className="af-button af-button-secondary w-full"
            type="button"
            disabled={pending}
            onClick={continueWithGitHub}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-current">
              <path d="M12 .8a11.4 11.4 0 0 0-3.6 22.2c.6.1.8-.2.8-.6v-2.2c-3.3.7-4-1.4-4-1.4-.6-1.4-1.4-1.8-1.4-1.8-1.1-.8.1-.8.1-.8 1.2.1 1.9 1.3 1.9 1.3 1.1 1.9 2.9 1.3 3.6 1 .1-.8.4-1.3.8-1.6-2.7-.3-5.5-1.3-5.5-6a4.7 4.7 0 0 1 1.3-3.3c-.1-.3-.6-1.6.1-3.3 0 0 1-.3 3.5 1.3a12 12 0 0 1 6.3 0c2.4-1.6 3.5-1.3 3.5-1.3.7 1.7.3 3 .1 3.3a4.7 4.7 0 0 1 1.3 3.3c0 4.6-2.8 5.7-5.5 6 .4.4.8 1.1.8 2.2v3.3c0 .4.2.7.8.6A11.4 11.4 0 0 0 12 .8Z" />
            </svg>
            Continue with GitHub
          </button>
        </>
      ) : null}
    </div>
  );
}
