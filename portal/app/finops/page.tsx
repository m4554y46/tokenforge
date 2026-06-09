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
  const quarterly = forecast.quarterly as Record<string, number> | undefined;
  const annual = forecast.annual as Record<string, number> | undefined;

  if (loading) return <div className="text-gray-400">Chargement...</div>;
  if (error) return <div className="text-red-400">{error}</div>;

  const confidenceLabel = String(monthly?.confidence ?? 'low');
  const confidenceColor = confidenceLabel === 'high' ? 'text-green-400' : confidenceLabel === 'medium' ? 'text-yellow-400' : 'text-gray-400';

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">FinOps Dashboard</h2>
      <p className="text-sm text-gray-500 mb-6">
        Suivi des coûts LLM et ROI de la compression TokenForge.
        Les montants sont calculés à partir de l'historique des appels et des prix catalogue des modèles.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div>
          <KpiCard label="Coût baseline" value={`$${roi.baseline_cost_usd ?? 0}`} />
          <p className="text-xs text-gray-600 mt-1">
            Estimation de ce que vous auriez payé SANS compression TokenForge,
            calculé au prix catalogue du modèle utilisé.
          </p>
        </div>
        <div>
          <KpiCard label="Coût optimisé" value={`$${roi.optimized_cost_usd ?? 0}`} />
          <p className="text-xs text-gray-600 mt-1">
            Coût réel APRÈS application de la compression SPC (18 phases).
            Inclut la réduction de tokens et le routage intelligent.
          </p>
        </div>
        <div>
          <KpiCard label="Prévision mensuelle" value={`$${monthly?.projected_usd ?? 0}`} />
          <p className={`text-xs ${confidenceColor} mt-1`}>
            Projection sur 30 jours basée sur la consommation moyenne quotidienne.
            Confiance: {confidenceLabel === 'high' ? 'élevée' : confidenceLabel === 'medium' ? 'moyenne' : 'faible'}
            {' '}({monthly?.data_points ?? 0} points de données).
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <p className="text-sm text-gray-400">Économies brutes</p>
          <p className="text-xl font-bold text-green-400">${roi.gross_savings_usd ?? 0}</p>
          <p className="text-xs text-gray-600 mt-1">
            Baseline − Optimisé. C'est l'argent économisé grâce à la compression.
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <p className="text-sm text-gray-400">Frais TokenForge</p>
          <p className="text-xl font-bold text-white">${roi.tokenforge_cost_usd ?? 0}</p>
          <p className="text-xs text-gray-600 mt-1">
            Coût de la plateforme (${(roi as any).total_tokens ?? 0} tokens × tarif contractuel).
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <p className="text-sm text-gray-400">ROI net</p>
          <p className="text-xl font-bold text-orange-400">${roi.net_roi_usd ?? 0}</p>
          <p className="text-xs text-gray-600 mt-1">
            Économies − Frais TokenForge. Si positif, la plateforme est rentable.
          </p>
        </div>
      </div>

      {monthly && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h3 className="font-medium mb-2">Prévisions détaillées</h3>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-gray-400">Mensuelle</p>
              <p className="text-lg font-mono text-white">${monthly.projected_usd ?? 0}</p>
              <p className="text-xs text-gray-500">Tendance: {monthly.trend_percent ?? 0}%</p>
            </div>
            <div>
              <p className="text-gray-400">Trimestrielle</p>
              <p className="text-lg font-mono text-white">${quarterly?.projected_usd ?? 0}</p>
              <p className="text-xs text-gray-500">Tendance: {quarterly?.trend_percent ?? 0}%</p>
            </div>
            <div>
              <p className="text-gray-400">Annuelle</p>
              <p className="text-lg font-mono text-white">${annual?.projected_usd ?? 0}</p>
              <p className="text-xs text-gray-500">Tendance: {annual?.trend_percent ?? 0}%</p>
            </div>
          </div>
          <p className="text-xs text-gray-600 mt-3">
            Les prévisions sont calculées en projetant la moyenne quotidienne des coûts observés
            sur la période correspondante, ajustée d'une tendance linéaire sur les 7 derniers jours.
            La confiance augmente avec le nombre de jours d'historique disponibles.
          </p>
        </div>
      )}
    </div>
  );
}
