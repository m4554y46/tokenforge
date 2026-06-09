'use client';

import { useEffect, useState } from 'react';
import { KpiCard } from '../../components/KpiCard';

export default function PromptsPage() {
  const [dashboard, setDashboard] = useState<Record<string, any>>({});
  const [top, setTop] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const h = { 'X-Tenant-ID': 'default', 'X-User-ID': 'portal' };
    Promise.all([
      fetch('/api/v2/prompts/dashboard', { headers: h }).then(r => r.json()).then(setDashboard).catch(() => {}),
      fetch('/api/v2/prompts/top', { headers: h }).then(r => r.json()).then(d => setTop(d?.value ?? d ?? [])).catch(() => {}),
    ]).catch(() => setError('Erreur chargement prompts'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-400">Chargement...</div>;
  if (error) return <div className="text-red-400">{error}</div>;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Prompt Analytics</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <KpiCard label="Prompts analysés" value={String(dashboard?.total_prompts ?? 0)} />
        <KpiCard label="Tokens économisés" value={String(dashboard?.total_saved_tokens ?? 0)} />
        <KpiCard label="Économie $ estimée" value={`$${dashboard?.estimated_savings_usd ?? 0}`} />
      </div>

      <section>
        <h3 className="text-lg font-semibold mb-3">Top prompts</h3>
        {top.length === 0 ? (
          <p className="text-gray-500 text-sm">Aucune donnée de prompt disponible.</p>
        ) : (
          <div className="space-y-2">
            {top.map((p: any, i: number) => (
              <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-sm">
                <div className="flex justify-between mb-1">
                  <span className="font-medium truncate max-w-md">{p.prompt_preview || p.prompt || '(aucun)'}</span>
                  <span className="text-orange-400 font-mono">{p.count || p.uses || 0} appels</span>
                </div>
                {p.total_tokens && <p className="text-xs text-gray-500">{p.total_tokens} tokens</p>}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
