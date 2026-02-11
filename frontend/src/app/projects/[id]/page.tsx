import { api } from '@/lib/api';

export default async function ProjectDetailPage({ params }: { params: { id: string } }) {
  const project = await api.getProject(params.id);

  return (
    <main>
      <h1>{project.name}</h1>
      <p>ID: {project.id}</p>
      <pre>{JSON.stringify(project.problem, null, 2)}</pre>
    </main>
  );
}
