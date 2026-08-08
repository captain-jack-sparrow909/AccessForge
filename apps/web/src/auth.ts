import NextAuth from 'next-auth';
import GitHub from 'next-auth/providers/github';
import Credentials from 'next-auth/providers/credentials';

const providers = [
  ...(process.env.AUTH_GITHUB_ID && process.env.AUTH_GITHUB_SECRET ? [GitHub({ clientId: process.env.AUTH_GITHUB_ID, clientSecret: process.env.AUTH_GITHUB_SECRET })] : []),
  ...(process.env.DEV_AUTH_ENABLED === 'true' ? [Credentials({ id: 'credentials', name: 'Local development account', credentials: { email: { label: 'Email', type: 'email' }, password: { label: 'Password', type: 'password' } }, async authorize(credentials) { const email = String(credentials?.email ?? '').trim().toLowerCase(); const password = String(credentials?.password ?? ''); if (email && email === (process.env.DEV_AUTH_EMAIL ?? '').trim().toLowerCase() && password === (process.env.DEV_AUTH_PASSWORD ?? '')) return { id: `dev:${email}`, email, name: 'Local developer' }; return null; } })] : []),
];

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers,
  trustHost: process.env.AUTH_TRUST_HOST === 'true',
  pages: { signIn: '/sign-in' },
  session: { strategy: 'jwt' },
  callbacks: { jwt({ token, user }) { if (user?.id) token.sub = user.id; if (user?.email) token.email = user.email; return token; }, session({ session, token }) { if (session.user && token.sub) session.user.id = token.sub; return session; } },
});
