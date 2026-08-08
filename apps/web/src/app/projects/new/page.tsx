import { auth } from '@/auth';
import { redirect } from 'next/navigation';
import NewProjectForm from './new-project-form';

export default async function NewProjectPage() {
  const session = await auth();
  if (!session?.user) redirect('/sign-in');
  return <NewProjectForm />;
}
