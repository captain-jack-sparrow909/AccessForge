import { getSession } from '@/auth';
import { redirect } from 'next/navigation';
import NewProjectForm from './new-project-form';

export default async function NewProjectPage() {
  const session = await getSession();
  if (!session?.user) redirect('/sign-in');
  return <NewProjectForm />;
}
