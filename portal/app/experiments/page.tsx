'use client';

import { useEffect, useState } from 'react';
import { KpiCard } from '../../components/KpiCard';
import { authFetchJson } from '../../lib/fetch';

function computeWinner(variants: Record<string, any>, metric: string): string | null {
  const keys = Object.keys(variants);
  if (keys.length < 2) return null;
  const a = variants[keys[0]];
  const b = variants[keys[1]];
  if (metric === 'cost') {
    return (a.total_cost / a.samples) < (b.total_cost / b.samples) ? keys[0] : keys[1];
  }
  return (a.total_quality / a.samples) > (b.total_quality / b.samples) ? keys[0] : keys[1];
}

function formatCost(c: number): string {
  return c < 0.01 ? `$${(c * 1000).toFixed(2)}k` : `$${c.toFixed(2)}`;
}

export default function ExperimentsPage() {
  const [experiments, setExperiments] = useState<any[]>([]);

  useEffect(() => {
    authFetchJson<any[]>('/api/v2/experiments').then(d => d && setExperiments(d));
  }, []);

  const active = experiments.filter(e => e.status === 'active');
  const completed = experiments.filter(e => e.status === 'completed');

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">A/B Experiments</h2>
      <p className="text-sm text-gray-500 mb-6">
        Les tests A/B comparent deux variantes (modèle, configuration, fournisseur) pour déterminer
        laquelle est la plus performante sur une métrique donnée. La métrique peut être le <strong>coût</strong>
        (le moins cher gagne) ou la <strong>qualité</strong> (le mieux noté gagne).
        Les utilisateurs sont répartis aléatoirement entre les deux variantes (50/50).
      </p>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div>
          <KpiCard label="Total expériences" value={String(experiments.length)} />
          <p className="text-xs text-gray-600 mt-1">Nombre total de tests A/B lancés dans votre tenant.</p>
        </div>
        <div>
          <KpiCard label="Actives" value={String(active.length)} />
          <p className="text-xs text-gray-600 mt-1">Expériences en cours. Les données sont encore collectées.</p>
        </div>
        <div>
          <KpiCard label="Terminées" value={String(completed.length)} />
          <p className="text-xs text-gray-600 mt-1">Expériences avec suffisamment d'échantillons pour conclure.</p>
        </div>
        <div>
          <KpiCard label="Métrique principale" value="Cost / Quality" />
          <p className="text-xs text-gray-600 mt-1">
            Cost = coût moyen par requête (le moins cher gagne).
            Quality = score de qualité moyen (le plus haut gagne).
          </p>
        </div>
      </div>

      <section className="mb-8">
        <h3 className="text-lg font-semibold mb-2">Expériences actives</h3>
        <p className="text-xs text-gray-500 mb-3">
          Ces expériences sont en phase de collecte de données. Les résultats affichés sont partiels
          et peuvent encore évoluer. Le vainqueur est calculé à partir des données disponibles.
        </p>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {active.map((exp: any) => (
            <ExpCard key={exp.id} exp={exp} />
          ))}
          {active.length === 0 && (
            <p className="text-gray-500 text-sm">Aucune expérience active. Lancez-en une via l'API.</p>
          )}
        </div>
      </section>

      {completed.length > 0 && (
        <section>
          <h3 className="text-lg font-semibold mb-2">Expériences terminées</h3>
          <p className="text-xs text-gray-500 mb-3">
            Expériences avec données consolidées. La variante gagnante est déterminée
            par la métrique choisie : coût moyen par requête ou score de qualité moyen.
          </p>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {completed.map((exp: any) => (
              <ExpCard key={exp.id} exp={exp} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function ExpCard({ exp }: { exp: any }) {
  const variants = exp.results ?? {};
  const winner = computeWinner(variants, exp.metric);
  const metricLabel = exp.metric === 'cost' ? 'Coût' : 'Qualité';

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-medium">{exp.name}</h4>
        <span className={`text-xs px-2 py-0.5 rounded font-medium ${
          exp.status === 'active' ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-400'
        }`}>
          {exp.status === 'active' ? 'Actif' : 'Terminé'}
        </span>
      </div>
      <p className="text-xs text-gray-500 mb-3">
        Compare {exp.variant_a} vs {exp.variant_b} sur la métrique {metricLabel}.
        {exp.metric === 'cost' ? " Le moins cher est déclaré vainqueur." : " Le mieux noté est déclaré vainqueur."}
      </p>
      <div className="grid grid-cols-2 gap-3">
        {Object.entries(variants).map(([name, data]: [string, any]) => {
          const avgCost = data.total_cost / data.samples;
          const avgQuality = data.total_quality / data.samples;
          const isWinner = winner === name;
          return (
            <div key={name} className={`rounded-lg p-3 border ${isWinner ? 'border-orange-500 bg-orange-900/20' : 'border-gray-700 bg-gray-800'}`}>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium">{name}</span>
                {isWinner && <span className="text-xs text-orange-400 font-medium">vainqueur</span>}
              </div>
              <div className="text-xs text-gray-400 space-y-0.5">
                <p>Coût moy: {formatCost(avgCost)}</p>
                <p>Qualité: {avgQuality.toFixed(2)}/5</p>
                <p>Tokens: {(data.total_tokens / data.samples).toFixed(0)}/req</p>
                <p>Échantillons: {data.samples}</p>
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-xs text-gray-600 mt-2">
        Chaque utilisateur est assigné aléatoirement à une variante (hash de son user_id).
        Les résultats incluent coût, qualité perçue et consommation tokens.
      </p>
    </div>
  );
}
