'use client';

import { useEffect, useState } from 'react';
import { KpiCard } from '../../components/KpiCard';

const CATEGORY_LABELS: Record<string, string> = {
  acronym: 'Acronymes',
  terminology: 'Terminologie',
  document_type: 'Types de documents',
  policy: 'Politiques',
};

const CATEGORY_COLORS: Record<string, string> = {
  acronym: 'bg-purple-900 text-purple-300',
  terminology: 'bg-blue-900 text-blue-300',
  document_type: 'bg-green-900 text-green-300',
  policy: 'bg-red-900 text-red-300',
};

export default function MemoryPage() {
  const [profile, setProfile] = useState<Record<string, any>>({});
  const [knowledge, setKnowledge] = useState<any[]>([]);
  const [summary, setSummary] = useState<Record<string, any>>({});

  useEffect(() => {
    const h = { 'X-Tenant-ID': 'default', 'X-User-ID': 'portal' };
    fetch('/api/v2/memory/user/profile', { headers: h }).then(r => r.json()).then(setProfile);
    fetch('/api/v2/memory/tenant/knowledge', { headers: h }).then(r => r.json()).then(d => setKnowledge(d.value ?? d));
    fetch('/api/v2/memory/user/summary', { headers: h }).then(r => r.json()).then(setSummary).catch(() => {});
  }, []);

  const prefs = profile.preferences ?? {};
  const prefCount = Object.keys(prefs).length;
  const validatedCount = knowledge.filter(k => k.validated).length;
  const categories = [...new Set(knowledge.map(k => k.category))];

  const grouped = categories.reduce((acc, cat) => {
    acc[cat] = knowledge.filter(k => k.category === cat);
    return acc;
  }, {} as Record<string, any[]>);

  const confidenceAvg = prefCount > 0
    ? (Object.values(prefs).reduce((sum: number, p: any) => sum + (p.confidence ?? 0), 0) / prefCount * 100).toFixed(0)
    : '0';

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Memory Center</h2>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <KpiCard label="Préférences utilisateur" value={String(prefCount)} />
        <KpiCard label="Confiance moyenne" value={`${confidenceAvg}%`} />
        <KpiCard label="Termes connaissance" value={String(knowledge.length)} />
        <KpiCard label="Termes validés" value={String(validatedCount)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <section>
          <h3 className="text-lg font-semibold mb-3">Préférences utilisateur</h3>
          <div className="space-y-2">
            {Object.entries(prefs).map(([key, p]: [string, any]) => (
              <div key={key} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium capitalize">{key.replace(/_/g, ' ')}</span>
                  <span className="text-xs text-gray-400">
                    {(p.confidence * 100).toFixed(0)}% confiance
                  </span>
                </div>
                <p className="text-sm text-orange-400">
                  {Array.isArray(p.value) ? p.value.join(', ') : String(p.value)}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  Source: {p.source} · {new Date(p.updated_at).toLocaleString('fr-FR')}
                </p>
              </div>
            ))}
            {prefCount === 0 && (
              <p className="text-gray-500 text-sm">Aucune préférence enregistrée.</p>
            )}
          </div>
        </section>

        <section>
          <h3 className="text-lg font-semibold mb-3">Connaissance tenant</h3>
          <div className="space-y-3">
            {categories.map(cat => (
              <div key={cat}>
                <h4 className="text-sm font-medium text-gray-400 mb-2 flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded ${CATEGORY_COLORS[cat] || 'bg-gray-700 text-gray-300'}`}>
                    {CATEGORY_LABELS[cat] || cat}
                  </span>
                  <span className="text-xs text-gray-600">({grouped[cat].length})</span>
                </h4>
                <div className="space-y-1.5">
                  {grouped[cat].map((k: any) => (
                    <div key={k.id} className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-sm">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{k.term}</span>
                        {k.validated ? (
                          <span className="text-xs text-green-400">✓ validé</span>
                        ) : (
                          <span className="text-xs text-yellow-400">en attente</span>
                        )}
                      </div>
                      {k.definition && (
                        <p className="text-xs text-gray-400 mt-1">{k.definition}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
            {knowledge.length === 0 && (
              <p className="text-gray-500 text-sm">Aucune connaissance enregistrée.</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
