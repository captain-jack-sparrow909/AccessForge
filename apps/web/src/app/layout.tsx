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
        <a className="skip-link" href="#main-content">Skip to content</a>
        <div className="af-shell">
          <header className="border-b border-[var(--af-line)] bg-[var(--af-surface)]">
            <div className="af-container flex min-h-16 items-center justify-between gap-4">
              <Link className="font-bold tracking-tight" href="/" aria-label="AccessForge home">
                Access<span className="text-[var(--af-primary)]">Forge</span>
              </Link>
              <nav aria-label="Primary navigation" className="flex items-center gap-4 text-sm">
                <Link className="hover:text-[var(--af-primary)]" href="/how-it-works">How it works</Link>
                <Link className="hover:text-[var(--af-primary)]" href="/safety">Safety limits</Link>
                <Link className="af-button af-button-secondary" href="/dashboard">Dashboard</Link>
              </nav>
            </div>
          </header>
          <main id="main-content">{children}</main>
          <footer className="border-t border-[var(--af-line)] py-8 text-sm text-[var(--af-muted)]">
            <div className="af-container flex flex-wrap justify-between gap-3">
              <span>AccessForge is early-stage software, not a safety certification.</span>
              <Link href="/privacy" className="underline underline-offset-4">Privacy principles</Link>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
