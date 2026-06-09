'use client';

import { useEffect, useState } from 'react';
import { KpiCard } from '../../components/KpiCard';

function TopPromptsSection({ title, desc, items }: { title: string; desc: string; items: any[] }) {
  if (!items || items.length === 0) return null;
  return (
    <section>
      <h3 className="text-lg font-semibold mb-1">{title}</h3>
      <p className="text-xs text-gray-500 mb-3">{desc}</p>
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

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Prompt Analytics</h2>
      <p className="text-sm text-gray-500 mb-6">
        Analyse de tous les prompts envoyés aux LLM. Chaque prompt est identifié par une empreinte unique
        (hash SHA-256) pour suivre sa fréquence, son coût et l'efficacité de la compression SPC.
        Les économies sont calculées par rapport au prix catalogue du modèle sans compression.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div>
          <KpiCard label="Prompts uniques" value={String(uniquePrompts)} />
          <p className="text-xs text-gray-600 mt-1">
            Nombre de prompts différents envoyés (dédupliqués par empreinte SHA-256).
            Un même prompt appelé 100 fois compte pour 1.
          </p>
        </div>
        <div>
          <KpiCard label="Appels totaux" value={String(totalCalls)} />
          <p className="text-xs text-gray-600 mt-1">
            Nombre total de requêtes LLM effectuées sur la période.
            Inclut tous les modèles et fournisseurs.
          </p>
        </div>
        <div>
          <KpiCard label="Économie moyenne" value={`${Number(avgSavings).toFixed(1)}%`} />
          <p className="text-xs text-gray-600 mt-1">
            Pourcentage moyen de tokens économisés par appel grâce à la compression SPC.
            Calculé sur l'ensemble des appels optimisés.
          </p>
        </div>
        <div>
          <KpiCard label="Économie $ estimée" value={`$${estimatedSavings}`} />
          <p className="text-xs text-gray-600 mt-1">
            Économie totale estimée = coût total × % économie / 100.
            Correspond aux tokens que vous n'avez pas payés.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {topData.most_used && (
          <TopPromptsSection
            title="Les plus utilisés"
            desc="Prompts ayant généré le plus grand nombre d'appels. Un prompt fréquent est un bon candidat pour l'optimisation."
            items={topData.most_used}
          />
        )}
        {topData.most_expensive && (
          <TopPromptsSection
            title="Les plus coûteux"
            desc="Prompts qui cumulent le coût total le plus élevé. Ce sont vos plus gros postes de dépense LLM."
            items={topData.most_expensive}
          />
        )}
        {topData.most_compressible && (
          <TopPromptsSection
            title="Les plus compressibles"
            desc="Prompts où la compression SPC est la plus efficace. Fort potentiel d'économie supplémentaire."
            items={topData.most_compressible}
          />
        )}
      </div>
      {!topData.most_used && !topData.most_expensive && !topData.most_compressible && (
        <p className="text-gray-500 text-sm">
          Aucune donnée de prompt disponible. Les données apparaissent après les premiers appels LLM.
        </p>
      )}
    </div>
  );
}
