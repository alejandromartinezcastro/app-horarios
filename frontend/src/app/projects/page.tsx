import Link from 'next/link';

import { api } from '@/lib/api';

export default async function ProjectsPage() {
  const projects = await api.listProjects();

  return (
    <main>
      <h1>Projects</h1>
      {projects.length === 0 ? (
        <p>No hay proyectos todavía.</p>
      ) : (
        <ul>
          {projects.map((project) => (
            <li key={project.id}>
              <Link href={`/projects/${project.id}`}>{project.name}</Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
