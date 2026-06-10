'use client';

import { useEffect, useState } from 'react';
import './globals.css';

const NAV = [
  { href: '/', label: 'Dashboard' },
  { href: '/prompts', label: 'Prompt Analytics' },
  { href: '/finops', label: 'FinOps' },
  { href: '/ace', label: 'ACE Compression' },
  { href: '/ace/quality', label: 'Qualité' },
  { href: '/ace/onboarding', label: 'Calculateur ROI' },
  { href: '/governance', label: 'Governance' },
  { href: '/memory', label: 'Memory Center' },
  { href: '/experiments', label: 'Experiments' },
];

// Routes qui ne nécessitent pas d'authentification
const PUBLIC_ROUTES = ['/login'];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [authed, setAuthed] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const path = window.location.pathname;
    if (PUBLIC_ROUTES.includes(path)) {
      setChecking(false);
      return;
    }
    const tid = sessionStorage.getItem('tf_tenant_id');
    const uid = sessionStorage.getItem('tf_user_id');
    if (tid && uid) {
      setAuthed(true);
    } else {
      window.location.href = '/login';
    }
    setChecking(false);
  }, []);

  // Page de login : rendu sans layout
  if (typeof window !== 'undefined' && PUBLIC_ROUTES.includes(window.location.pathname)) {
    return <html lang="fr" className="dark"><body>{children}</body></html>;
  }

  if (checking) {
    return <html lang="fr" className="dark"><body><div className="min-h-screen flex items-center justify-center bg-gray-950"><p className="text-gray-400">Chargement...</p></div></body></html>;
  }

  if (!authed) {
    return <html lang="fr" className="dark"><body><div className="min-h-screen flex items-center justify-center bg-gray-950"><p className="text-gray-400">Redirection vers la connexion...</p></div></body></html>;
  }

  return (
    <html lang="fr" className="dark">
      <body>
        <div className="flex min-h-screen">
          <aside className="w-56 bg-gray-900 border-r border-gray-800 p-4 flex flex-col">
            <h1 className="text-lg font-bold text-orange-400 mb-6">TokenForge</h1>
            <nav className="space-y-1 flex-1">
              {NAV.map((item) => (
                <a key={item.href} href={item.href}
                  className="block px-3 py-2 rounded hover:bg-gray-800 text-sm text-gray-300">
                  {item.label}
                </a>
              ))}
            </nav>
            <div className="pt-4 border-t border-gray-800">
              <button onClick={() => { sessionStorage.clear(); window.location.href = '/login'; }}
                className="text-xs text-gray-500 hover:text-gray-300">
                Déconnexion
              </button>
            </div>
          </aside>
          <main className="flex-1 p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
