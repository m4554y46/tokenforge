import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'TokenForge Intelligence Platform',
  description: 'Le Datadog + FinOps + CDN des LLM',
};

const NAV = [
  { href: '/', label: 'Dashboard' },
  { href: '/prompts', label: 'Prompt Analytics' },
  { href: '/finops', label: 'FinOps' },
  { href: '/governance', label: 'Governance' },
  { href: '/memory', label: 'Memory Center' },
  { href: '/experiments', label: 'Experiments' },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className="dark">
      <body>
        <div className="flex min-h-screen">
          <aside className="w-56 bg-gray-900 border-r border-gray-800 p-4">
            <h1 className="text-lg font-bold text-orange-400 mb-6">TokenForge</h1>
            <nav className="space-y-1">
              {NAV.map((item) => (
                <a key={item.href} href={item.href}
                  className="block px-3 py-2 rounded hover:bg-gray-800 text-sm text-gray-300">
                  {item.label}
                </a>
              ))}
            </nav>
          </aside>
          <main className="flex-1 p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
