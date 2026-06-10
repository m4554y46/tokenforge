'use client';

import { useEffect, useState } from 'react';
import { KpiCard } from '../../components/KpiCard';
import { TrendChart } from '../../components/TrendChart';

const HEADERS = { 'X-Tenant-ID': 'default', 'X-User-ID': 'portal' };

function fmt$(n: number): string {
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}k`;
  if (n >= 1) return `$${n.toFixed(2)}`;
  return `${(n * 1000).toFixed(2)}¢`;
}

function Bar({ value, max, label, color, suffix }: { value: number; max: number; label: string; color: string; suffix?: string }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-28 text-gray-400 truncate text-right">{label}</span>
      <div className="flex-1 h-4 bg-gray-800 rounded overflow-hidden">
        <div className={`h-full rounded ${color}`} style={{ width: `${Math.max(pct, 2)}%` }} />
      </div>
      <span className="w-20 text-gray-300 font-mono text-right">{suffix ? `${value}${suffix}` : fmt$(value)}</span>
    </div>
  );
}

function Section({ title, subtitle, children, className }: { title: string; subtitle?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-gray-900 border border-gray-800 rounded-lg p-4 ${className ?? ''}`}>
      <h3 className="font-medium mb-1">{title}</h3>
      {subtitle && <p className="text-xs text-gray-500 mb-3">{subtitle}</p>}
      {children}
    </div>
  );
}

export default function FinOpsPage() {
  const [summary, setSummary] = useState<Record<string, any>>({});
  const [roi, setRoi] = useState<Record<string, any>>({});
  const [forecast, setForecast] = useState<Record<string, any>>({});
  const [anomalies, setAnomalies] = useState<Record<string, any>>({});
  const [budgets, setBudgets] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [topPrompts, setTopPrompts] = useState<any[]>([]);
  const [trendData, setTrendData] = useState<any[]>([]);
  const [topUsers, setTopUsers] = useState<any[]>([]);
  const [providerEff, setProviderEff] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch('/api/v2/finops/summary', { headers: HEADERS }).then(r => r.json()).then(setSummary),
      fetch('/api/v2/finops/roi', { headers: HEADERS }).then(r => r.json()).then(setRoi),
      fetch('/api/v2/finops/forecast', { headers: HEADERS }).then(r => r.json()).then(setForecast),
      fetch('/api/v2/finops/anomalies', { headers: HEADERS }).then(r => r.json()).then(setAnomalies),
      fetch('/api/v2/finops/budgets', { headers: HEADERS }).then(r => r.json()).then(setBudgets),
      fetch('/api/v2/finops/alerts', { headers: HEADERS }).then(r => r.json()).then(setAlerts),
      fetch('/api/v2/finops/top-prompts', { headers: HEADERS }).then(r => r.json()).then(setTopPrompts),
      fetch('/api/v2/finops/trend', { headers: HEADERS }).then(r => r.json()).then(setTrendData),
      fetch('/api/v2/finops/top-users', { headers: HEADERS }).then(r => r.json()).then(setTopUsers),
      fetch('/api/v2/finops/provider-efficiency', { headers: HEADERS }).then(r => r.json()).then(setProviderEff),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-400">Chargement du cockpit FinOps...</div>;

  const byModel: any[] = summary.by_model ?? [];
  const providersMap: Record<string, number> = {};
  const modelsMap: Record<string, number> = {};
  for (const row of byModel) {
    const p = row.provider ?? 'unknown';
    providersMap[p] = (providersMap[p] ?? 0) + (row.total_cost ?? 0);
    const m = row.model ?? 'unknown';
    modelsMap[m] = (modelsMap[m] ?? 0) + (row.total_cost ?? 0);
  }
  const maxProv = Math.max(...Object.values(providersMap), 0.001);
  const maxMod = Math.max(...Object.values(modelsMap), 0.001);

  const monthlyFc = forecast.monthly ?? {};
  const anomList: any[] = anomalies.anomalies ?? [];
  const spikeCount = anomalies.spike_count ?? 0;
  const driftCount = anomalies.drift_count ?? 0;

  const totalCost = summary.total_cost_usd ?? 0;
  const totalTokens = summary.total_tokens ?? 0;
  const totalReqs = summary.total_requests ?? 0;

  const topProvs = Object.entries(providersMap).sort((a, b) => b[1] - a[1]);
  const topModels = Object.entries(modelsMap).sort((a, b) => b[1] - a[1]);

  const budgetLimit = Math.max(...budgets.map(b => b.amount_usd ?? 0), 0);
  const budgetUtil = budgetLimit > 0 ? totalCost / budgetLimit : 0;

  const trendDays = trendData.map((d: any) => ({ day: d.day, cost: d.cost ?? 0 }));
  const trendCosts = trendDays.map(d => d.cost);
  const trendAvg = trendCosts.length > 0 ? trendCosts.reduce((a, b) => a + b, 0) / trendCosts.length : 0;
  const trendMax = Math.max(...trendCosts, 0);
  const trendMin = Math.min(...trendCosts, 0);

  const maxUserCost = Math.max(...topUsers.map((u: any) => u.total_cost ?? 0), 0.001);

  const recommendations: string[] = [];
  if (anomList.length > 0) {
    const spikes = anomList.filter(a => a.type === 'cost_spike');
    const drifts = anomList.filter(a => a.type === 'user_drift');
    if (spikes.length > 0) recommendations.push(`⚡ ${spikes.length} pic(s) de coût détecté(s) — investigatez les jours ${spikes.map(s => s.day).join(', ')}`);
    if (drifts.length > 0) recommendations.push(`👤 ${drifts.length} utilisateur(s) en dérive — envisagez un budget ou un blocage`);
  }
  if (topProvs.length > 1) {
    const sorted = [...topProvs].sort((a, b) => (b[1] as number) / (a[1] as number));
    const ratio = sorted.length > 1 ? (sorted[0][1] as number) / ((sorted[1][1] as number) || 1) : 1;
    if (ratio > 3) recommendations.push(`🏢 Forte concentration fournisseur sur ${sorted[0][0]} (${ratio.toFixed(1)}× vs #2) — risque de vendor lock-in`);
  }
  if (budgetUtil > 0.8) recommendations.push(`⚠️ Budget à ${Math.round(budgetUtil * 100)}% — configurez une alerte ou augmentez le plafond`);
  if (roi.roi_percent < 0) recommendations.push(`📉 ROI négatif (${roi.roi_percent}%) — le taux de compression est peut-être trop faible`);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold">FinOps Dashboard</h2>
        <p className="text-sm text-gray-500">
          Pilotage financier LLM — 30 jours glissants · {totalReqs.toLocaleString()} requêtes · {totalTokens.toLocaleString()} tokens
        </p>
      </div>

      {/* Row 1 — Financial Pulse */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Coût total période"
          value={fmt$(totalCost)}
          subtitle={`${totalReqs.toLocaleString()} requêtes · ${(summary.cost_per_token ?? 0) * 1000 < 0.001 ? '<0.001' : fmt$((summary.cost_per_token ?? 0) * 1000)}/1K tokens`}
          color="orange"
        />
        <KpiCard
          label="ROI net"
          value={`${roi.net_roi_usd >= 0 ? '+' : ''}${fmt$(roi.net_roi_usd ?? 0)}`}
          subtitle={`${roi.roi_percent ?? 0}% · ${roi.verdict === 'positive' ? 'Rentable ✓' : 'Neutre'}`}
          color={roi.net_roi_usd > 0 ? 'green' : roi.net_roi_usd < 0 ? 'red' : 'yellow'}
          trend={{ direction: roi.net_roi_usd > 0 ? 'up' : 'down', label: `${roi.roi_percent ?? 0}%` }}
        />
        <KpiCard
          label="Budget utilisé"
          value={`${Math.round(budgetUtil * 100)}%`}
          subtitle={budgets.length > 0 ? `${fmt$(totalCost)} / ${fmt$(budgetLimit)}` : 'Aucun budget défini'}
          color={budgetUtil > 0.9 ? 'red' : budgetUtil > 0.7 ? 'yellow' : 'green'}
          progress={budgets.length > 0 ? { current: Math.round(totalCost), max: Math.round(budgetLimit) } : undefined}
        />
        <KpiCard
          label="Économies brutes"
          value={fmt$(roi.gross_savings_usd ?? 0)}
          subtitle={`taux ${roi.assumed_rate ?? 0}% · Frais TF: ${fmt$(roi.tokenforge_cost_usd ?? 0)}`}
          color="green"
        />
      </div>

      {/* Row 2 — Trend Chart + Period Comparison */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Section title="Tendance quotidienne" subtitle="Évolution du coût jour par jour" className="lg:col-span-2">
          <TrendChart data={trendDays} height={100} />
          <div className="grid grid-cols-3 gap-3 mt-2 text-xs">
            <div className="bg-gray-800 rounded p-2 text-center">
              <p className="text-gray-400">Moyen</p>
              <p className="text-white font-mono">{fmt$(trendAvg)}</p>
            </div>
            <div className="bg-gray-800 rounded p-2 text-center">
              <p className="text-gray-400">Max</p>
              <p className="text-white font-mono">{fmt$(trendMax)}</p>
            </div>
            <div className="bg-gray-800 rounded p-2 text-center">
              <p className="text-gray-400">Min</p>
              <p className="text-white font-mono">{fmt$(trendMin)}</p>
            </div>
          </div>
        </Section>
        <Section title="Prévisions" subtitle="Projections sur 3 horizons">
          <div className="space-y-3">
            <div>
              <p className="text-xs text-gray-400">30 jours</p>
              <p className="text-lg font-bold text-white">{fmt$(monthlyFc.projected_usd ?? 0)}</p>
              <p className="text-xs text-gray-500">
                {monthlyFc.daily_avg_usd ? fmt$(monthlyFc.daily_avg_usd) : '—'}/j · Tendance {monthlyFc.trend_percent ?? 0}%
                · Confiance <span className={monthlyFc.confidence === 'high' ? 'text-green-400' : monthlyFc.confidence === 'medium' ? 'text-yellow-400' : 'text-gray-400'}>{monthlyFc.confidence ?? '—'}</span>
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <p className="text-xs text-gray-400">Trimestriel</p>
                <p className="text-sm font-bold text-white">{fmt$(forecast.quarterly?.projected_usd ?? 0)}</p>
                <p className="text-xs text-gray-500">Tend. {forecast.quarterly?.trend_percent ?? 0}%</p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Annuel</p>
                <p className="text-sm font-bold text-white">{fmt$(forecast.annual?.projected_usd ?? 0)}</p>
                <p className="text-xs text-gray-500">Tend. {forecast.annual?.trend_percent ?? 0}%</p>
              </div>
            </div>
          </div>
        </Section>
      </div>

      {/* Row 3 — Cost Breakdown + Provider Efficiency */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Section title="Coût par fournisseur" subtitle="Répartition par provider">
          {topProvs.length === 0 && <p className="text-gray-500 text-xs">Aucune donnée.</p>}
          <div className="space-y-1.5">
            {topProvs.map(([k, v]) => (
              <Bar key={k} label={k} value={v as number} max={maxProv} color="bg-blue-500" />
            ))}
          </div>
        </Section>
        <Section title="Coût par modèle" subtitle="Top modèles les plus coûteux">
          {topModels.length === 0 && <p className="text-gray-500 text-xs">Aucune donnée.</p>}
          <div className="space-y-1.5">
            {topModels.map(([k, v]) => (
              <Bar key={k} label={k} value={v as number} max={maxMod} color="bg-orange-500" />
            ))}
          </div>
        </Section>
        <Section title="Efficiency fournisseur" subtitle="Coût / 1K tokens par provider">
          {providerEff.length === 0 && <p className="text-gray-500 text-xs">Aucune donnée.</p>}
          <div className="space-y-1.5">
            {providerEff.map((p: any) => {
              const costPer1k = (p.cost_per_token ?? 0) * 1000;
              const allCosts = providerEff.map((x: any) => (x.cost_per_token ?? 0) * 1000);
              const maxCpt = Math.max(...allCosts, 0.001);
              return (
                <Bar
                  key={p.provider}
                  label={p.provider}
                  value={Number(costPer1k.toFixed(4))}
                  max={maxCpt}
                  color="bg-purple-500"
                  suffix="$/1K"
                />
              );
            })}
          </div>
          <p className="text-xs text-gray-600 mt-2">Plus le coût par token est bas, meilleur est le rapport qualité-prix du fournisseur.</p>
        </Section>
      </div>

      {/* Row 4 — Users + Prompts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Section title="Top utilisateurs" subtitle="Par coût total sur 30 jours">
          {topUsers.length === 0 ? (
            <p className="text-gray-500 text-xs">Aucune donnée utilisateur.</p>
          ) : (
            <div className="space-y-1.5">
              {topUsers.map((u: any, i: number) => (
                <div key={i} className="flex items-center gap-3 text-xs bg-gray-800 rounded p-2">
                  <span className="text-gray-500 w-4 text-right">{i + 1}.</span>
                  <span className="w-2 h-2 rounded-full bg-orange-500" />
                  <span className="text-gray-300 flex-1">{u.user_id}</span>
                  <span className="text-gray-300 font-mono">{fmt$(u.total_cost)}</span>
                  <span className="text-gray-500">{u.requests} req · {Math.round(u.avg_savings ?? 0)}% savings</span>
                </div>
              ))}
            </div>
          )}
        </Section>
        <Section title="Top 10 prompts les plus coûteux" subtitle="Classés par coût total cumulé">
          {topPrompts.length === 0 ? (
            <p className="text-gray-500 text-xs">Aucune donnée.</p>
          ) : (
            <div className="space-y-1.5 max-h-64 overflow-y-auto">
              {topPrompts.map((p: any, i: number) => (
                <div key={i} className="flex items-center gap-3 text-xs bg-gray-800 rounded p-2">
                  <span className="text-gray-500 w-4 text-right shrink-0">{i + 1}.</span>
                  <span className="text-gray-400 font-mono truncate flex-1">{p.prompt_preview ?? p.prompt_hash}</span>
                  <span className="text-gray-300 font-mono shrink-0">{fmt$(p.total_cost)}</span>
                  <span className="text-gray-500 shrink-0">({p.uses ?? 0}x)</span>
                </div>
              ))}
            </div>
          )}
        </Section>
      </div>

      {/* Row 5 — Anomalies + Budgets */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Section
          title="Anomalies & Dérives"
          subtitle={`${spikeCount} pic(s) de coût · ${driftCount} dérive(s) utilisateur · Statut: ${anomalies.status ?? 'normal'}`}
        >
          {anomList.length === 0 ? (
            <p className="text-green-400 text-xs">✓ Aucune anomalie détectée. Tout est nominal.</p>
          ) : (
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {anomList.map((a, i) => (
                <div key={i} className="flex items-center justify-between text-xs bg-gray-800 rounded p-2">
                  <div className="flex items-center gap-2">
                    <span className={`font-medium ${a.severity === 'critical' ? 'text-red-400' : 'text-yellow-400'}`}>
                      {a.type === 'cost_spike' ? '⚡' : '👤'}
                    </span>
                    <span className="text-gray-400">{a.type === 'cost_spike' ? a.day : a.user_id}</span>
                  </div>
                  <span className="text-gray-300 font-mono">
                    {a.type === 'cost_spike' ? fmt$(a.cost_usd) : `${a.cost_usd} req`}
                    {a.z_score ? ` (z=${a.z_score})` : ` (${a.ratio_vs_median}x)`}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Section>
        <Section title="Budgets & Alertes" subtitle={`${budgets.length} budget(s) · ${alerts.length} alerte(s)`}>
          {budgets.length === 0 ? (
            <p className="text-gray-500 text-xs">Aucun budget défini. POST /api/v2/finops/budgets pour créer un budget.</p>
          ) : (
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {budgets.map((b, i) => {
                const util = b.amount_usd > 0 ? ((b.spent_usd ?? 0) / b.amount_usd) : 0;
                const barColor = util > 0.9 ? 'bg-red-500' : util > 0.7 ? 'bg-yellow-500' : 'bg-green-500';
                const isAlert = util >= (b.alert_threshold ?? 0.8);
                return (
                  <div key={i} className="text-xs bg-gray-800 rounded p-2">
                    <div className="flex justify-between mb-0.5">
                      <span className="flex items-center gap-1">
                        {isAlert && <span className="text-red-400">🔔</span>}
                        <span className="text-gray-300">{b.scope_type}: {b.scope_id}</span>
                      </span>
                      <span className="text-gray-300 font-mono">{fmt$(b.spent_usd ?? 0)} / {fmt$(b.amount_usd)}</span>
                    </div>
                    <div className="w-full bg-gray-700 h-1.5 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${barColor}`} style={{ width: `${Math.min(util * 100, 100)}%` }} />
                    </div>
                    <p className="text-gray-500 mt-0.5">{b.period} · seuil: {Math.round((b.alert_threshold ?? 0.8) * 100)}% · dépensé: {Math.round(util * 100)}%</p>
                  </div>
                );
              })}
            </div>
          )}
        </Section>
      </div>

      {/* Row 6 — Actionable Insights */}
      {recommendations.length > 0 && (
        <Section title="Recommandations & Insights" subtitle="Suggestions actionnables basées sur les données">
          <div className="space-y-1.5">
            {recommendations.map((r, i) => (
              <div key={i} className="text-xs bg-gray-800 rounded p-2 text-gray-300">
                {r}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Row 7 — Context */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="font-medium mb-2">Méthodologie de calcul</h3>
        <div className="text-xs text-gray-500 space-y-1">
          <p><strong className="text-gray-400">Coûts:</strong> Calculés au prix catalogue des modèles via la table <code className="text-gray-300">provider_models</code> multiplié par les tokens consommés.</p>
          <p><strong className="text-gray-400">Baseline vs Optimisé:</strong> Le coût baseline est estimé à partir du coût réel divisé par (1 − taux de compression). L'optimisé est le coût réel après compression SPC.</p>
          <p><strong className="text-gray-400">ROI:</strong> (Économies brutes − Frais TokenForge) / Frais TokenForge. Le seuil de rentabilité est ROI &gt; 0.</p>
          <p><strong className="text-gray-400">Anomalies:</strong> Détection par écart-type (z-score ≥ 2.5) sur les coûts quotidiens et par écart à la médiane utilisateur (×3).</p>
          <p><strong className="text-gray-400">Budgets:</strong> 4 scopes hiérarchiques : user → team → application → tenant. L'alerte est déclenchée au seuil configuré (défaut 80%).</p>
        </div>
      </div>
    </div>
  );
}