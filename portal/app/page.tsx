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
  const alerts = (data?.budget_alerts as unknown[]) ?? [];

  if (loading) return <div className="text-gray-400">Chargement...</div>;
  if (error) return <div className="text-red-400">{error}</div>;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Executive Dashboard</h2>
      <p className="text-sm text-gray-500 mb-6">
        Vue d'ensemble de l'activité LLM sur les 30 derniers jours.
        TokenForge analyse chaque appel, applique la compression SPC, et mesure l'impact économique.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div>
          <KpiCard label="Coût total" value={`$${finops?.total_cost_usd ?? 0}`} />
          <p className="text-xs text-gray-600 mt-1">
            Somme de tous les appels LLM enregistrés (optimisés ou non).
          </p>
        </div>
        <div>
          <KpiCard label="ROI net" value={`$${roi?.net_roi_usd ?? 0}`} />
          <p className="text-xs text-gray-600 mt-1">
            Économies réalisées moins le coût de la plateforme TokenForge.
            Calcul : (coût baseline − coût optimisé) − frais TokenForge.
          </p>
        </div>
        <div>
          <KpiCard label="Économies %" value={`${roi?.avg_savings_percent ?? 0}%`} />
          <p className="text-xs text-gray-600 mt-1">
            Réduction moyenne de tokens par appel grâce à la compression SPC.
            Plus le % est élevé, plus vous en avez pour votre argent.
          </p>
        </div>
        <div>
          <KpiCard label="Alertes budget" value={String(alerts.length)} />
          <p className="text-xs text-gray-600 mt-1">
            Budgets définis qui approchent ou dépassent leur seuil d'alerte.
            Les budgets sont configurables dans FinOps.
          </p>
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-6">
        <h3 className="font-medium mb-2">Détail du ROI</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-gray-400">Coût baseline (sans compression)</p>
            <p className="text-white font-mono">${roi?.baseline_cost_usd ?? 0}</p>
          </div>
          <div>
            <p className="text-gray-400">Coût réel (avec compression)</p>
            <p className="text-white font-mono">${roi?.optimized_cost_usd ?? 0}</p>
          </div>
          <div>
            <p className="text-gray-400">Frais TokenForge</p>
            <p className="text-white font-mono">${roi?.tokenforge_cost_usd ?? 0}</p>
          </div>
          <div>
            <p className="text-gray-400">ROI %</p>
            <p className="text-orange-400 font-mono">{roi?.roi_percent ?? 0}%</p>
          </div>
        </div>
        <p className="text-xs text-gray-600 mt-3">
          Le coût baseline est estimé au prix catalogue du modèle sans compression.
          Le coût optimisé reflète le volume réel après compression SPC (18 phases).
          ROI = (économies − coût TokenForge) / coût TokenForge × 100.
        </p>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="font-medium mb-2">Profil mémoire</h3>
        <div className="text-sm text-gray-400 space-y-1">
          <p>Utilisateur: {(data?.user_summary as any)?.summary ?? '—'}</p>
          <p>Tenant: {(data?.tenant_summary as any)?.summary ?? '—'}</p>
        </div>
        <p className="text-xs text-gray-600 mt-2">
          La mémoire utilisateur enregistre les préférences (langue, ton, format) pour personnaliser les réponses.
          La mémoire tenant stocke la terminologie métier (acronymes, définitions).
        </p>
      </div>
    </div>
  );
}
