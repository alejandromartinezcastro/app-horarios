import Link from 'next/link';

import { api } from '@/lib/api';

export default async function ProjectsPage() {
  try {
    const projects = await api.listProjects();

    return (
      <main className="page grid">
        <section className="card">
          <p className="kicker">Proyectos</p>
          <h1>Tu espacio de planificación</h1>
          <p>
            Revisa proyectos existentes y entra al detalle para validar datos del problema antes de
            lanzar el solver.
          </p>
          <p className="badge">Total proyectos: {projects.length}</p>
        </section>

        {projects.length === 0 ? (
          <section className="card">
            <h2>No hay proyectos todavía</h2>
            <p>
              Cuando crees el primero desde el flujo del wizard aparecerá aquí para revisarlo y
              ejecutar la resolución.
            </p>
            <div className="actions">
              <Link href="/" className="button primary">
                Ir al inicio
              </Link>
            </div>
          </section>
        ) : (
          <section className="grid projects">
            {projects.map((project) => (
              <article key={project.id} className="card">
                <h3>{project.name}</h3>
                <p>ID: {project.id}</p>
                <div className="actions">
                  <Link className="button" href={`/projects/${project.id}`}>
                    Abrir detalle
                  </Link>
                </div>
              </article>
            ))}
          </section>
        )}
      </main>
    );
  } catch (error) {
    return (
      <main className="page grid">
        <section className="card error">
          <p className="kicker">Error de conexión</p>
          <h1>No se pudieron cargar los proyectos</h1>
          <p>
            Verifica que el backend esté levantado en <code>NEXT_PUBLIC_API_URL</code> y responde a
            <code> /projects</code>.
          </p>
          <pre className="code-block">{error instanceof Error ? error.message : 'Error desconocido'}</pre>
        </section>
      </main>
    );
  }
}
