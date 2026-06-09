'use client';

import { useEffect, useState } from 'react';
import { KpiCard } from '../components/KpiCard';

export default function Dashboard() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch('/api/v2/dashboard', {
      headers: { 'X-Tenant-ID': 'default', 'X-User-ID': 'portal' },
    })
      .then((r) => r.json())
      .then(setData)
      .catch(() => setError('Erreur chargement dashboard'))
      .finally(() => setLoading(false));
  }, []);

  const finops = data?.finops as Record<string, number> | undefined;
  const roi = data?.roi as Record<string, number> | undefined;

  if (loading) return <div className="text-gray-400">Chargement...</div>;
  if (error) return <div className="text-red-400">{error}</div>;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Executive Dashboard</h2>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <KpiCard label="Coût total" value={`$${finops?.total_cost_usd ?? 0}`} />
        <KpiCard label="ROI net" value={`$${roi?.net_roi_usd ?? 0}`} />
        <KpiCard label="Économies %" value={`${roi?.avg_savings_percent ?? 0}%`} />
        <KpiCard label="Alertes budget" value={String((data?.budget_alerts as unknown[])?.length ?? 0)} />
      </div>
      <pre className="bg-gray-900 p-4 rounded text-xs overflow-auto max-h-96">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
