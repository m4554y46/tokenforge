'use client';

import { useEffect, useState } from 'react';
import { KpiCard } from '../../components/KpiCard';

export default function FinOpsPage() {
  const [roi, setRoi] = useState<Record<string, number>>({});
  const [forecast, setForecast] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const h = { 'X-Tenant-ID': 'default', 'X-User-ID': 'portal' };
    Promise.all([
      fetch('/api/v2/finops/roi', { headers: h }).then(r => r.json()).then(setRoi).catch(() => setError('Erreur chargement ROI')),
      fetch('/api/v2/finops/forecast', { headers: h }).then(r => r.json()).then(setForecast).catch(() => setError('Erreur chargement prévisions')),
    ]).finally(() => setLoading(false));
  }, []);

  const monthly = forecast.monthly as Record<string, number> | undefined;

  if (loading) return <div className="text-gray-400">Chargement...</div>;
  if (error) return <div className="text-red-400">{error}</div>;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">FinOps Dashboard</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <KpiCard label="Coût baseline" value={`$${roi.baseline_cost_usd ?? 0}`} />
        <KpiCard label="Coût optimisé" value={`$${roi.optimized_cost_usd ?? 0}`} />
        <KpiCard label="Prévision mensuelle" value={`$${monthly?.projected_usd ?? 0}`} />
      </div>
    </div>
  );
}
