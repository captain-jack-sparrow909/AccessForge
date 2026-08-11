import { getSession } from '@/auth';
import { redirect } from 'next/navigation';
import ModelSettingsClient from './model-settings-client';

export default async function ModelSettingsPage() {
  const session = await getSession();
  if (!session?.user) redirect('/sign-in');
  return <ModelSettingsClient />;
}
