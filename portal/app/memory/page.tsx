'use client';

import { useEffect, useState } from 'react';
import { KpiCard } from '../../components/KpiCard';
import { authFetchJson } from '../../lib/fetch';

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
    authFetchJson('/api/v2/memory/user/profile').then(d => d && setProfile(d));
    authFetchJson<any[]>('/api/v2/memory/tenant/knowledge').then(d => d && setKnowledge(d));
    authFetchJson('/api/v2/memory/user/summary').then(d => d && setSummary(d));
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
      <p className="text-sm text-gray-500 mb-6">
        Le Memory Center stocke deux types d'information : les préférences utilisateur (comment l'utilisateur
        aime ses réponses) et la connaissance tenant (le vocabulaire métier de l'entreprise).
        Ces données sont injectées automatiquement dans les prompts pour personnaliser les réponses LLM.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div>
          <KpiCard label="Préférences utilisateur" value={String(prefCount)} />
          <p className="text-xs text-gray-600 mt-1">
            Paramètres personnels (langue, ton, format, modèle favori).
            Sont appris automatiquement ou définis manuellement.
          </p>
        </div>
        <div>
          <KpiCard label="Confiance moyenne" value={`${confidenceAvg}%`} />
          <p className="text-xs text-gray-600 mt-1">
            Niveau de certitude moyen des préférences. Une préférence définie manuellement
            a une confiance de 100% ; une préférence inférée a une confiance moindre.
          </p>
        </div>
        <div>
          <KpiCard label="Termes connaissance" value={String(knowledge.length)} />
          <p className="text-xs text-gray-600 mt-1">
            Mots et définitions spécifiques au métier de l'entreprise.
            Permet au LLM de comprendre le vocabulaire interne.
          </p>
        </div>
        <div>
          <KpiCard label="Termes validés" value={String(validatedCount)} />
          <p className="text-xs text-gray-600 mt-1">
            Termes vérifiés manuellement comme corrects. Un terme non validé
            (jaune) n'est pas encore confirmé par un humain.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <section>
          <h3 className="text-lg font-semibold mb-2">Préférences utilisateur</h3>
          <p className="text-xs text-gray-500 mb-3">
            Chaque préférence a une valeur, un score de confiance (0-100%),
            une source (manuelle ou inférée), et une date de mise à jour.
            Ces préférences sont injectées dans le contexte de chaque appel LLM.
          </p>
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
              <p className="text-gray-500 text-sm">
                Aucune préférence enregistrée. Les préférences sont créées automatiquement
                quand vous utilisez le service.
              </p>
            )}
          </div>
        </section>

        <section>
          <h3 className="text-lg font-semibold mb-2">Connaissance tenant</h3>
          <p className="text-xs text-gray-500 mb-3">
            Base de connaissances métier de l'entreprise. Les termes sont organisés par catégorie
            (acronymes, terminologie, types de documents, politiques internes).
            Un terme validé (vert) a été confirmé par un humain.
          </p>
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
                          <span className="text-xs text-green-400">validé</span>
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
              <p className="text-gray-500 text-sm">
                Aucune connaissance enregistrée. Les termes sont ajoutés automatiquement
                via l'apprentissage des interactions ou manuellement via l'API.
              </p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
