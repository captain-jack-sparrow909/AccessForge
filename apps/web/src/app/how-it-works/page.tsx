import Link from 'next/link';

const steps = [
  ['Describe', 'Start with the outcome you want. You do not need to name a diagnosis or explain your body.'],
  ['Confirm', 'Measurements and AI suggestions remain separate until you edit and confirm them.'],
  ['Constrain', 'Deterministic scope and risk rules block requests that could cause harm.'],
  ['Review', 'Reviewed parametric templates create bounded candidates with itemized checks.'],
];

export default function HowItWorksPage() {
  return <div className="af-container py-16"><p className="af-eyebrow">Transparent by design</p><h1 className="mt-4 max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">A co-design notebook, not a black box.</h1><div className="mt-8 grid gap-5 md:grid-cols-2">{steps.map(([title, body], index) => <article className="af-card p-6" key={title}><p className="text-sm font-bold text-[var(--af-primary)]">0{index + 1}</p><h2 className="mt-2 text-xl font-bold">{title}</h2><p className="mt-2 leading-7 text-[var(--af-muted)]">{body}</p></article>)}</div><Link href="/sign-in" className="af-button af-button-primary mt-10">Open a private project</Link></div>;
}
