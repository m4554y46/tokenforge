'use client';

import { useEffect, useState } from 'react';
import { authFetch } from '../../lib/fetch';

interface AceStatus {
  enabled: boolean;
  cells_total: number;
  requests_total: number;
  avg_savings_percent: number;
  explorations_total: number;
  quality_model_available: boolean;
  embeddings_available: boolean;
  rates: number[];
}

interface Cell {
  cell: string;
  expected_quality: number;
  n_samples: number;
  n_explorations: number;
  rate: number;
}

type Tab = 'status' | 'cells';

export default function AcePage() {
  const [status, setStatus] = useState<AceStatus | null>(null);
  const [cells, setCells] = useState<Cell[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('status');

  useEffect(() => {
    authFetch('/api/v2/ace/status')
      .then(r => { if (!r.ok) throw new Error('Erreur status'); return r.json(); })
      .then(setStatus)
      .catch(e => setError(e.message));

    authFetch('/api/v2/ace/cells?min_samples=1')
      .then(r => { if (!r.ok) throw new Error('Erreur cells'); return r.json(); })
      .then(setCells)
      .catch(() => {});
  }, []);

  if (error) return <div className="text-red-400">Erreur: {error}</div>;
  if (!status) return <div className="text-gray-400">Chargement...</div>;

  const topCells = [...cells].sort((a, b) => b.n_samples - a.n_samples).slice(0, 100);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">ACE — Adaptive Compression Engine</h1>

      <div className="flex gap-2 mb-6">
        <button onClick={() => setTab('status')}
          className={`px-4 py-2 rounded ${tab === 'status' ? 'bg-orange-600' : 'bg-gray-700'}`}>
          Status
        </button>
        <button onClick={() => setTab('cells')}
          className={`px-4 py-2 rounded ${tab === 'cells' ? 'bg-orange-600' : 'bg-gray-700'}`}>
          Cellules ({cells.length})
        </button>
      </div>

      {tab === 'status' && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <Kpi label="Cellules" value={status.cells_total} />
          <Kpi label="Requêtes" value={status.requests_total} />
          <Kpi label="Économies moy." value={`${status.avg_savings_percent}%`} />
          <Kpi label="Explorations" value={status.explorations_total} />
          <Kpi label="Modèle qualité" value={status.quality_model_available ? 'Disponible' : 'Indisponible'} />
          <Kpi label="Embeddings" value={status.embeddings_available ? 'Disponible' : 'Indisponible'} />
          <Kpi label="Taux disponibles" value={status.rates.join(', ')} />
          <Kpi label="ACE" value={status.enabled ? 'Actif' : 'Désactivé'} />
        </div>
      )}

      {tab === 'cells' && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-400 border-b border-gray-700">
                <th className="py-2 pr-4">Cellule</th>
                <th className="py-2 pr-4">Qualité</th>
                <th className="py-2 pr-4">Échantillons</th>
                <th className="py-2 pr-4">Explorations</th>
                <th className="py-2 pr-4">Taux</th>
              </tr>
            </thead>
            <tbody>
              {topCells.map((c, i) => (
                <tr key={i} className="border-b border-gray-800 hover:bg-gray-800">
                  <td className="py-2 pr-4 font-mono text-xs">{c.cell}</td>
                  <td className="py-2 pr-4">
                    <span className={c.expected_quality >= 0.7 ? 'text-green-400' : c.expected_quality >= 0.4 ? 'text-yellow-400' : 'text-red-400'}>
                      {c.expected_quality.toFixed(3)}
                    </span>
                  </td>
                  <td className="py-2 pr-4">{c.n_samples}</td>
                  <td className="py-2 pr-4">{c.n_explorations}</td>
                  <td className="py-2 pr-4">{(c.rate * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
