import Link from 'next/link';

import { isSupabaseConfigured } from '@/lib/supabase/env';

export default function Home() {
  const supabaseReady = isSupabaseConfigured();

  return (
    <main>
      <h1>Timetable App</h1>
      <p>
        Estado Supabase frontend:{' '}
        <strong>{supabaseReady ? 'configurado' : 'pendiente de configurar'}</strong>
      </p>
      {!supabaseReady ? (
        <p>
          Define <code>NEXT_PUBLIC_SUPABASE_URL</code> y{' '}
          <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> en <code>frontend/.env.local</code>.
        </p>
      ) : null}
      <ul>
        <li>
          <Link href="/projects">Go to Projects</Link>
        </li>
      </ul>
    </main>
  );
}
