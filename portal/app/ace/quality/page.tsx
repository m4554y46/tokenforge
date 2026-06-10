'use client';

import { useEffect, useState } from 'react';
import { authFetch } from '../../../lib/fetch';

interface DashboardData {
  summary: {
    total_cells: number;
    good_quality_cells: number;
    poor_quality_cells: number;
    good_quality_ratio: number;
    avg_quality: number;
    avg_compression_rate: number;
    total_requests: number;
    total_tokens_saved: number;
    avg_savings_percent: number;
    estimated_savings_usd: number;
  };
  by_profile: { profile: string; rate: number; avg_quality: number; count: number }[];
  by_task_type: { task_type: string; avg_quality: number; avg_rate: number; count: number; good_ratio: number }[];
  alerts: { type: string; severity: string; profile?: string; task_type?: string; message: string }[];
}

export default function QualityPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [days, setDays] = useState(7);

  useEffect(() => {
    authFetch(`/api/v2/ace/quality-dashboard?days=${days}`)
      .then(r => { if (!r.ok) throw new Error('Erreur'); return r.json(); })
      .then(setData)
      .catch(() => {});
  }, [days]);

  if (!data) return <div className="text-gray-400">Chargement...</div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Dashboard Qualité ACE</h1>
        <select value={days} onChange={e => setDays(Number(e.target.value))}
          className="bg-gray-700 rounded px-3 py-1 text-sm">
          <option value={1}>24h</option>
          <option value={7}>7 jours</option>
          <option value={30}>30 jours</option>
        </select>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <Kpi label="Cellules" value={data.summary.total_cells} />
        <Kpi label="Qualité moy." value={data.summary.avg_quality.toFixed(3)} color={data.summary.avg_quality >= 0.7 ? 'text-green-400' : data.summary.avg_quality >= 0.4 ? 'text-yellow-400' : 'text-red-400'} />
        <Kpi label="Taux comp. moy." value={`${(data.summary.avg_compression_rate * 100).toFixed(0)}%`} />
        <Kpi label="Requêtes" value={data.summary.total_requests} />
        <Kpi label="Tokens sauvés" value={data.summary.total_tokens_saved.toLocaleString()} />
        <Kpi label="Économies estimées" value={`${data.summary.estimated_savings_usd.toFixed(2)} USD`} color="text-green-400" />
        <Kpi label="Bon ratio" value={`${(data.summary.good_quality_ratio * 100).toFixed(0)}%`} />
        <Kpi label="Économies moy." value={`${data.summary.avg_savings_percent}%`} />
      </div>

      {/* Qualité par profil */}
      <h2 className="text-lg font-semibold mb-3">Qualité par profil</h2>
      <div className="overflow-x-auto mb-8">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-400 border-b border-gray-700">
              <th className="py-2 pr-4">Profil</th>
              <th className="py-2 pr-4">Taux</th>
              <th className="py-2 pr-4">Qualité moy.</th>
              <th className="py-2 pr-4">Échantillons</th>
            </tr>
          </thead>
          <tbody>
            {data.by_profile.map((p, i) => (
              <tr key={i} className="border-b border-gray-800">
                <td className="py-2 pr-4 font-medium">{p.profile}</td>
                <td className="py-2 pr-4">{(p.rate * 100).toFixed(0)}%</td>
                <td className="py-2 pr-4">
                  <span className={p.avg_quality >= 0.7 ? 'text-green-400' : p.avg_quality >= 0.4 ? 'text-yellow-400' : 'text-red-400'}>
                    {p.avg_quality.toFixed(3)}
                  </span>
                </td>
                <td className="py-2 pr-4">{p.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Qualité par type de tâche */}
      <h2 className="text-lg font-semibold mb-3">Qualité par type de tâche</h2>
      <div className="overflow-x-auto mb-8">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-400 border-b border-gray-700">
              <th className="py-2 pr-4">Tâche</th>
              <th className="py-2 pr-4">Qualité moy.</th>
              <th className="py-2 pr-4">Taux moy.</th>
              <th className="py-2 pr-4">Requêtes</th>
              <th className="py-2 pr-4">Bon ratio</th>
            </tr>
          </thead>
          <tbody>
            {data.by_task_type.map((t, i) => (
              <tr key={i} className="border-b border-gray-800">
                <td className="py-2 pr-4">{t.task_type}</td>
                <td className="py-2 pr-4">
                  <span className={t.avg_quality >= 0.7 ? 'text-green-400' : t.avg_quality >= 0.4 ? 'text-yellow-400' : 'text-red-400'}>
                    {t.avg_quality.toFixed(3)}
                  </span>
                </td>
                <td className="py-2 pr-4">{(t.avg_rate * 100).toFixed(0)}%</td>
                <td className="py-2 pr-4">{t.count}</td>
                <td className="py-2 pr-4">{(t.good_ratio * 100).toFixed(0)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Alertes */}
      {data.alerts.length > 0 && (
        <>
          <h2 className="text-lg font-semibold mb-3">Alertes</h2>
          <div className="space-y-2">
            {data.alerts.map((a, i) => (
              <div key={i} className={`rounded p-3 text-sm ${a.severity === 'warning' ? 'bg-yellow-900/50 text-yellow-300' : 'bg-gray-800 text-gray-300'}`}>
                {a.message}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Kpi({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${color ?? ''}`}>{value}</div>
    </div>
  );
}
