'use client';

import { useEffect, useState } from 'react';
import { KpiCard } from '../../components/KpiCard';

function TopPromptsSection({ title, items }: { title: string; items: any[] }) {
  if (!items || items.length === 0) return null;
  return (
    <section>
      <h3 className="text-lg font-semibold mb-3">{title}</h3>
      <div className="space-y-2">
        {items.map((p: any, i: number) => (
          <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-sm">
            <div className="flex justify-between mb-1">
              <span className="font-medium truncate max-w-md">{p.preview || p.prompt_preview || p.prompt || '(aucun)'}</span>
              <span className="text-orange-400 font-mono">{p.count || p.uses || 0} appels</span>
            </div>
            <div className="flex gap-3 text-xs text-gray-500">
              {p.total_tokens != null && <span>{p.total_tokens} tokens</span>}
              {p.total_cost != null && <span>${Number(p.total_cost).toFixed(4)}</span>}
              {p.avg_savings != null && <span>{Number(p.avg_savings).toFixed(1)}% économie</span>}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function PromptsPage() {
  const [dashboard, setDashboard] = useState<Record<string, any>>({});
  const [topData, setTopData] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const h = { 'X-Tenant-ID': 'default', 'X-User-ID': 'portal' };
    Promise.all([
      fetch('/api/v2/prompts/dashboard', { headers: h }).then(r => r.json()).then(setDashboard).catch(() => {}),
      fetch('/api/v2/prompts/top', { headers: h }).then(r => r.json()).then(setTopData).catch(() => {}),
    ]).catch(() => setError('Erreur chargement prompts'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-400">Chargement...</div>;
  if (error) return <div className="text-red-400">{error}</div>;

  const d = dashboard;
  const uniquePrompts = d.unique_prompts ?? d.total_prompts ?? 0;
  const totalCalls = d.total_calls ?? 0;
  const totalCost = d.total_cost ?? 0;
  const avgSavings = d.avg_savings ?? 0;
  const estimatedSavings = totalCost > 0 ? (totalCost * avgSavings / 100).toFixed(4) : '0';
  const savedTokens = d.total_saved_tokens ?? Math.round(totalCalls * 500);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Prompt Analytics</h2>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <KpiCard label="Prompts uniques" value={String(uniquePrompts)} />
        <KpiCard label="Appels totaux" value={String(totalCalls)} />
        <KpiCard label="Économie moyenne" value={`${Number(avgSavings).toFixed(1)}%`} />
        <KpiCard label="Économie $ estimée" value={`$${estimatedSavings}`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {topData.most_used && <TopPromptsSection title="Les plus utilisés" items={topData.most_used} />}
        {topData.most_expensive && <TopPromptsSection title="Les plus coûteux" items={topData.most_expensive} />}
        {topData.most_compressible && <TopPromptsSection title="Les plus compressibles" items={topData.most_compressible} />}
      </div>
    </div>
  );
}
