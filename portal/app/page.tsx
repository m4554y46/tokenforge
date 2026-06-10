'use client';

import { useEffect, useState } from 'react';
import { KpiCard } from '../components/KpiCard';
import { authFetch, authFetchJson } from '../lib/fetch';

const COMPRESSION_PROFILES = [
  { label: 'Light (35%)',   rate: 0.35 },
  { label: 'Balanced (50%)', rate: 0.50 },
  { label: 'Aggressive (65%)', rate: 0.65 },
];

const TF_RATE_PER_1K = 0.002;

function fmt$(n: number): string {
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}k`;
  if (n >= 1) return `$${n.toFixed(2)}`;
  return `${(n * 1000).toFixed(2)}¢`;
}

function Bar({ value, max, label, color }: { value: number; max: number; label: string; color: string }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-24 text-gray-400 truncate text-right">{label}</span>
      <div className="flex-1 h-4 bg-gray-800 rounded overflow-hidden">
        <div className={`h-full rounded ${color}`} style={{ width: `${Math.max(pct, 2)}%` }} />
      </div>
      <span className="w-16 text-gray-300 font-mono text-right">{fmt$(value)}</span>
    </div>
  );
}

export default function Dashboard() {
  const [raw, setRaw] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [compressionRate, setCompressionRate] = useState(0.50);

  useEffect(() => {
    setLoading(true);
    setError('');
    authFetchJson<Record<string, any>>(`/api/v2/dashboard?savings_rate=${compressionRate}`)
      .then((data) => {
        if (data) setRaw(data);
        else setError('Erreur chargement dashboard');
      })
      .catch(() => setError('Erreur chargement dashboard'))
      .finally(() => setLoading(false));
  }, [compressionRate]);

  if (loading) return <div className="text-gray-400 p-8">Chargement du cockpit...</div>;
  if (error) return <div className="text-red-400 p-8">{error}</div>;

  const finops = raw?.finops ?? {};
  const roi = raw?.roi ?? {};
  const byProvider: Record<string, number> = raw?.cost_breakdown?.by_provider ?? {};
  const byModel: Record<string, number> = raw?.cost_breakdown?.by_model ?? {};
  const budgetAlerts: any[] = raw?.budget_alerts ?? [];
  const anomalyData = raw?.anomalies ?? {};
  const anomalies: any[] = anomalyData.anomalies ?? [];
  const policies = raw?.governance ?? {};
  const experiments = raw?.experiments ?? {};
  const totalCost = finops.total_cost_usd ?? 0;
  const maxProvider = Math.max(...Object.values(byProvider), 0.001);
  const maxModel = Math.max(...Object.values(byModel), 0.001);
  const budgetLimit = Math.max(...(raw?.budget_alerts ?? []).map((a: any) => a.limit ?? 0), 1);
  const budgetSpent = Math.max(...(raw?.budget_alerts ?? []).map((a: any) => a.spent ?? 0), 0);
  const budgetUtil = budgetLimit > 0 ? (budgetSpent / budgetLimit) : (totalCost > 0 ? 0 : 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Cockpit Exécutif</h2>
          <p className="text-sm text-gray-500">Pilotage financier, opérationnel et organisationnel — 30 jours glissants</p>
        </div>
        <div className="flex items-center gap-4">
          <label className="text-sm text-gray-400">Taux compression:</label>
          <select
            className="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-white"
            value={compressionRate}
            onChange={(e) => { setCompressionRate(Number(e.target.value)); }}
          >
            {COMPRESSION_PROFILES.map((p) => (
              <option key={p.rate} value={p.rate}>{p.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Row 1 — Financial Pulse */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div>
          <KpiCard
            label="Coût période"
            value={fmt$(totalCost)}
            subtitle={`${(finops.total_requests ?? 0).toLocaleString()} requêtes`}
          />
          <p className="text-xs text-gray-600 mt-1">Coût réel de tous les appels LLM (optimisés ou non) sur les 30 derniers jours.</p>
        </div>
        <div>
          <KpiCard
            label="ROI net"
            value={`${roi.net_roi_usd >= 0 ? '+' : ''}${fmt$(roi.net_roi_usd ?? 0)}`}
            color={roi.net_roi_usd > 0 ? 'green' : roi.net_roi_usd < 0 ? 'red' : 'orange'}
            subtitle={`${roi.roi_percent ?? 0}% de rendement`}
          />
          <p className="text-xs text-gray-600 mt-1">Économies − frais TokenForge. Calculé avec un taux de {Math.round(compressionRate * 100)}% de compression.</p>
        </div>
        <div>
          <KpiCard
            label="Budget utilisé"
            value={`${Math.round(budgetUtil * 100)}%`}
            color={budgetUtil > 0.9 ? 'red' : budgetUtil > 0.7 ? 'yellow' : 'green'}
            progress={raw?.budget_alerts?.length > 0 ? { current: Math.round(budgetSpent), max: Math.round(budgetLimit) } : undefined}
          />
          <p className="text-xs text-gray-600 mt-1">
            {raw?.budget_alerts?.length > 0 ? `${fmt$(budgetSpent)} / ${fmt$(budgetLimit)}` : 'Aucun budget défini'}
            {budgetAlerts.length > 0 ? ` — ${budgetAlerts.length} alerte(s)` : ''}
          </p>
        </div>
        <div>
          <KpiCard label="Économie brute" value={fmt$(roi.gross_savings_usd ?? 0)} color="green" />
          <p className="text-xs text-gray-600 mt-1">Basé sur un taux de compression de {Math.round(compressionRate * 100)}%. Ajustez le curseur pour simuler.</p>
        </div>
      </div>

      {/* Row 2 — Cost Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h3 className="font-medium mb-3">Coût par fournisseur</h3>
          <div className="space-y-1.5">
            {Object.entries(byProvider).length === 0 && <p className="text-gray-500 text-xs">Aucune donnée — effectuez des appels LLM via le proxy pour alimenter le tableau de bord.</p>}
            {Object.entries(byProvider).map(([k, v]) => (
              <Bar key={k} label={k} value={v} max={maxProvider} color="bg-blue-500" />
            ))}
          </div>
          <p className="text-xs text-gray-600 mt-2">Répartition du coût total par fournisseur d'IA. Permet d'identifier les fournisseurs les plus dépensiers.</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h3 className="font-medium mb-3">Coût par modèle</h3>
          <div className="space-y-1.5">
            {Object.entries(byModel).length === 0 && <p className="text-gray-500 text-xs">Aucune donnée — les coûts par modèle apparaîtront après les premiers appels via le proxy.</p>}
            {Object.entries(byModel).map(([k, v]) => (
              <Bar key={k} label={k} value={v} max={maxModel} color="bg-orange-500" />
            ))}
          </div>
          <p className="text-xs text-gray-600 mt-2">Top modèles les plus coûteux. Permet de cibler les politiques de blocage (deny_model) sur les modèles trop chers.</p>
        </div>
      </div>

      {/* Row 3 — ROI What-If */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="font-medium mb-3">Simulation ROI — Quel taux de compression pour quel résultat ?</h3>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="col-span-1">
            <label className="text-sm text-gray-400 block mb-2">Taux de compression attendu : <strong className="text-white">{Math.round(compressionRate * 100)}%</strong></label>
            <input
              type="range"
              min="5"
              max="80"
              value={Math.round(compressionRate * 100)}
              onChange={(e) => setCompressionRate(Number(e.target.value) / 100)}
              className="w-full accent-orange-500"
            />
            <div className="flex justify-between text-xs text-gray-600 mt-1">
              <span>5% (sans risque)</span>
              <span>40% (recommandé)</span>
              <span>80% (déconseillé)</span>
            </div>
            <p className="text-xs text-gray-600 mt-2">Glissez le curseur pour simuler l'impact du taux de compression sur le ROI. Les données se mettent à jour automatiquement. La recommendation TokenForge est Balanced (50%) — bon compromis économie/qualité.</p>
          </div>
          <div className="col-span-2 grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-gray-800 rounded p-3">
              <p className="text-xs text-gray-400">Baseline estimé</p>
              <p className="text-lg font-bold text-white">{fmt$(roi.baseline_cost_usd ?? 0)}</p>
              <p className="text-xs text-gray-600">Coût sans compression</p>
            </div>
            <div className="bg-gray-800 rounded p-3">
              <p className="text-xs text-gray-400">Économie brute</p>
              <p className="text-lg font-bold text-green-400">{fmt$(roi.gross_savings_usd ?? 0)}</p>
              <p className="text-xs text-gray-600">{Math.round(compressionRate * 100)}% de {fmt$(roi.baseline_cost_usd ?? 0)}</p>
            </div>
            <div className="bg-gray-800 rounded p-3">
              <p className="text-xs text-gray-400">Frais TokenForge</p>
              <p className="text-lg font-bold text-white">{fmt$(roi.tokenforge_cost_usd ?? 0)}</p>
              <p className="text-xs text-gray-600">{(roi.total_tokens ?? 0).toLocaleString()} tokens × ${TF_RATE_PER_1K}/k</p>
            </div>
            <div className="bg-gray-800 rounded p-3">
              <p className="text-xs text-gray-400">ROI final</p>
              <p className={`text-lg font-bold ${roi.net_roi_usd > 0 ? 'text-green-400' : 'text-orange-400'}`}>
                {roi.roi_percent ?? 0}%
              </p>
              <p className="text-xs text-gray-600">{roi.net_roi_usd > 0 ? 'Rentable' : 'En dessous du seuil'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Row 4 — Operational Pulse */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-medium text-sm">Gouvernance</h3>
            <span className="text-xs text-orange-400">{policies.active_policies ?? 0} / {policies.total_policies ?? 0} actives</span>
          </div>
          <div className="space-y-1">
            {(policies.policies ?? []).slice(0, 3).map((p: any) => (
              <div key={p.id} className="flex items-center gap-2 text-xs">
                <span className={`w-2 h-2 rounded-full ${p.enabled ? 'bg-green-500' : 'bg-gray-600'}`} />
                <span className="text-gray-400 truncate flex-1">{p.name}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-gray-600 mt-2">
            {policies.active_policies ?? 0} politiques actives sur {policies.total_policies ?? 0}. Les politiques bloquent les modèles coûteux, forcent la compression et limitent les tokens.
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-medium text-sm">Expériences A/B</h3>
            <span className="text-xs text-orange-400">{experiments.active ?? 0} en cours</span>
          </div>
          {experiments.total > 0 ? (
            <div className="text-xs text-gray-400 space-y-1">
              <p>Total: {experiments.total}</p>
              <p>Actives: {experiments.active}</p>
              <p>Dernière: {(experiments.active_experiments ?? [])[0]?.name ?? '—'}</p>
            </div>
          ) : (
            <p className="text-xs text-gray-500">Aucune expérience A/B lancée. Créez-en une pour comparer modèles, profils ou fournisseurs.</p>
          )}
          <p className="text-xs text-gray-600 mt-2">
            Les A/B tests comparent deux variantes (coût ou qualité) pour déterminer la meilleure configuration.
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h3 className="font-medium text-sm mb-2">Alertes & Anomalies</h3>
          {anomalies.length > 0 ? (
            <div className="space-y-1">
              {anomalies.slice(0, 3).map((a: any, i: number) => (
                <p key={i} className="text-xs text-red-400">⚠ {a.type ?? a.title ?? 'Anomalie'}</p>
              ))}
            </div>
          ) : (
            <p className="text-xs text-green-400">✓ Aucune anomalie détectée</p>
          )}
          <p className="text-xs text-gray-600 mt-2">
            Les anomalies sont détectées automatiquement par analyse de variance des coûts quotidiens.
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h3 className="font-medium text-sm mb-2">Cache</h3>
          <p className="text-2xl font-bold text-orange-400">{raw?.cache?.size ?? 0}</p>
          <p className="text-xs text-gray-400">Entrées en cache</p>
          <p className="text-xs text-gray-600 mt-2">
            Le cache intelligent évite de recompresser des prompts identiques. Plus le cache est grand, plus les gains de performance sont importants.
          </p>
        </div>
      </div>
    </div>
  );
}
