import Link from 'next/link';

import { api } from '@/lib/api';

export default async function ProjectDetailPage({ params }: { params: { id: string } }) {
  try {
    const project = await api.getProject(params.id);

    return (
      <main className="page grid">
        <section className="card">
          <p className="kicker">Detalle de proyecto</p>
          <h1>{project.name}</h1>
          <p>ID: {project.id}</p>
          <div className="actions">
            <Link className="button" href="/projects">
              ← Volver a proyectos
            </Link>
          </div>
        </section>

        <section className="card">
          <h2>Definición del problema</h2>
          <p>Este JSON alimenta la generación de horario del solver.</p>
          <pre className="code-block">{JSON.stringify(project.problem, null, 2)}</pre>
        </section>
      </main>
    );
  } catch (error) {
    return (
      <main className="page grid">
        <section className="card error">
          <h1>No se pudo cargar el proyecto</h1>
          <pre className="code-block">{error instanceof Error ? error.message : 'Error desconocido'}</pre>
          <div className="actions">
            <Link className="button" href="/projects">
              ← Volver a proyectos
            </Link>
          </div>
        </section>
      </main>
    );
  }
}
