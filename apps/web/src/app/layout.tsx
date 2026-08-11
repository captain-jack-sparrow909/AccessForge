import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: 'AccessForge — co-design everyday access',
  description: 'A transparent workspace for low-risk assistive adapter candidates.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        <div className="af-shell">
          <header className="af-site-header">
            <div className="af-container flex min-h-20 flex-wrap items-center justify-between gap-4 py-3">
              <Link className="af-brand" href="/" aria-label="AccessForge home">
                <span className="af-brand-mark" aria-hidden="true">
                  AF
                </span>
                <span>
                  Access<span className="text-[var(--af-primary)]">Forge</span>
                </span>
              </Link>
              <nav
                aria-label="Primary navigation"
                className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm"
              >
                <Link className="af-nav-link min-h-11" href="/how-it-works">
                  How it works
                </Link>
                <Link className="af-nav-link min-h-11" href="/safety">
                  Safety limits
                </Link>
                <Link className="af-nav-link min-h-11" href="/privacy">
                  Privacy
                </Link>
                <Link className="af-button af-button-primary" href="/dashboard">
                  Open workspace <span aria-hidden="true">↗</span>
                </Link>
              </nav>
            </div>
          </header>
          <main className="flex-1" id="main-content">
            {children}
          </main>
          <footer className="af-site-footer py-12 text-sm text-[var(--af-muted)]">
            <div className="af-container grid gap-10 md:grid-cols-[1.4fr_0.7fr_0.7fr]">
              <div className="max-w-md">
                <Link className="af-brand text-[var(--af-ink)]" href="/">
                  <span className="af-brand-mark" aria-hidden="true">
                    AF
                  </span>
                  AccessForge
                </Link>
                <p className="mt-4 leading-6">
                  A transparent, privacy-minded co-design workspace for exploring bounded everyday
                  access ideas.
                </p>
                <p className="mt-3 text-xs leading-5">
                  Early-stage software. Not a medical device, professional approval, or safety
                  certification service.
                </p>
              </div>
              <div>
                <p className="font-bold text-[var(--af-ink)]">Explore</p>
                <div className="mt-4 grid gap-3">
                  <Link className="hover:text-[var(--af-primary-dark)]" href="/how-it-works">
                    How it works
                  </Link>
                  <Link className="hover:text-[var(--af-primary-dark)]" href="/safety">
                    Safety limits
                  </Link>
                  <Link className="hover:text-[var(--af-primary-dark)]" href="/dashboard">
                    Your workspace
                  </Link>
                </div>
              </div>
              <div>
                <p className="font-bold text-[var(--af-ink)]">Principles</p>
                <div className="mt-4 grid gap-3">
                  <Link className="hover:text-[var(--af-primary-dark)]" href="/privacy">
                    Privacy by default
                  </Link>
                  <Link className="hover:text-[var(--af-primary-dark)]" href="/settings/models">
                    Model settings
                  </Link>
                </div>
              </div>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
