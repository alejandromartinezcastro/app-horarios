import Link from 'next/link';

import { isSupabaseConfigured } from '@/lib/supabase/env';

export default function Home() {
  const supabaseReady = isSupabaseConfigured();

  return (
    <main className="page grid">
      <section className="card">
        <p className="kicker">Planificador académico</p>
        <h1>UI base lista para avanzar con UX</h1>
        <p>
          Ya tienes el frontend preparado para trabajar con backend y Supabase. Desde aquí puedes
          revisar proyectos, validar el estado de configuración y continuar con el flujo del wizard.
        </p>
        <p className="badge" aria-live="polite">
          <span className={`status-dot ${supabaseReady ? 'status-ok' : 'status-warn'}`} />
          Supabase frontend: <strong>{supabaseReady ? 'configurado' : 'pendiente'}</strong>
        </p>
        {!supabaseReady ? (
          <p>
            Falta configurar <code>NEXT_PUBLIC_SUPABASE_URL</code> y/o{' '}
            <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> en <code>frontend/.env.local</code>.
          </p>
        ) : null}

        <div className="actions">
          <Link className="button primary" href="/projects">
            Ver proyectos
          </Link>
          <Link className="button" href="/projects">
            Continuar con flujo de creación
          </Link>
        </div>
      </section>

      <section className="card">
        <h2>Siguientes mejoras UX sugeridas</h2>
        <ul className="list-clean">
          <li>Form de creación rápida de proyecto en la lista.</li>
          <li>Estados de carga y error más guiados por paso del wizard.</li>
          <li>Persistencia de borradores y recuperación automática.</li>
        </ul>
      </section>
    </main>
  );
}
