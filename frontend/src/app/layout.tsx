import type { Metadata } from 'next';
import Link from 'next/link';

import '../styles/globals.css';

export const metadata: Metadata = {
  title: 'Timetable App',
  description: 'UI para gestionar y resolver horarios',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body>
        <div className="app-shell">
          <header className="topbar">
            <div className="topbar-inner">
              <Link className="brand" href="/">
                <span className="brand-dot" />
                Timetable App
              </Link>
              <nav className="nav">
                <Link href="/">Inicio</Link>
                <Link href="/projects">Proyectos</Link>
              </nav>
            </div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
