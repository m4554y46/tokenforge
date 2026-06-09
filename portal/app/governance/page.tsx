'use client';

import { useEffect, useState } from 'react';
import { KpiCard } from '../../components/KpiCard';

const RULE_TYPE_DESC: Record<string, string> = {
  deny_model: 'Interdit l\'utilisation de certains modèles (gpt-4o, claude-opus…)',
  limit_provider: 'Limite ou interdit certains fournisseurs (Anthropic, Azure…)',
  force_compression: 'Impose la compression SPC sur les modèles ciblés',
  force_cache: 'Force la mise en cache des réponses pour réduire les coûts',
  max_tokens: 'Limite le nombre maximum de tokens par requête',
  require_approval: 'Nécessite une validation humaine avant exécution',
};

export default function GovernancePage() {
  const [policies, setPolicies] = useState<any[]>([]);
  const [auditLog, setAuditLog] = useState<any[]>([]);
  const [frameworks, setFrameworks] = useState<Record<string, any>>({});

  useEffect(() => {
    const h = { 'X-Tenant-ID': 'default', 'X-User-ID': 'portal' };
    fetch('/api/v2/governance/policies', { headers: h }).then(r => r.json()).then(d => setPolicies(d.value ?? d));
    fetch('/api/v2/governance/audit', { headers: h }).then(r => r.json()).then(d => setAuditLog(d.value ?? d));
    fetch('/api/v2/governance/compliance/frameworks', { headers: h }).then(r => r.json()).then(setFrameworks);
  }, []);

  const activePolicies = policies.filter(p => p.enabled);
  const denyCount = policies.filter(p => p.rule_type === 'deny_model' || p.rule_type === 'limit_provider').length;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Policy Center</h2>
      <p className="text-sm text-gray-500 mb-6">
        Les politiques de gouvernance contrôlent automatiquement chaque appel LLM.
        Elles permettent d'interdire des modèles coûteux, forcer la compression, limiter les tokens,
        ou exiger une validation humaine. Les règles sont évaluées à chaque requête.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div>
          <KpiCard label="Politiques actives" value={String(activePolicies.length)} />
          <p className="text-xs text-gray-600 mt-1">Règles actuellement en vigueur et appliquées aux appels LLM.</p>
        </div>
        <div>
          <KpiCard label="Total politiques" value={String(policies.length)} />
          <p className="text-xs text-gray-600 mt-1">Toutes les règles définies, actives et inactives confondues.</p>
        </div>
        <div>
          <KpiCard label="Règles de blocage" value={String(denyCount)} />
          <p className="text-xs text-gray-600 mt-1">Politiques qui interdisent des modèles ou fournisseurs spécifiques.</p>
        </div>
        <div>
          <KpiCard label="Frameworks conformité" value={String(Object.keys(frameworks).length)} />
          <p className="text-xs text-gray-600 mt-1">Cadres réglementaires supportés (RGPD, SOC2, ISO27001).</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <section>
          <h3 className="text-lg font-semibold mb-2">Politiques</h3>
          <p className="text-xs text-gray-500 mb-3">
            Chaque politique définit une règle avec son type et sa configuration.
            Les politiques actives (vert) sont appliquées, les inactives (gris) sont désactivées.
          </p>
          <div className="space-y-2">
            {policies.map((p: any) => (
              <div key={p.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium">{p.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${p.enabled ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-400'}`}>
                    {p.enabled ? 'Actif' : 'Inactif'}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mb-2">{RULE_TYPE_DESC[p.rule_type] || p.rule_type}</p>
                <div className="flex flex-wrap gap-2 text-xs text-gray-400">
                  <span className="bg-gray-800 px-2 py-0.5 rounded font-mono">{p.rule_type}</span>
                  {p.compliance_tags && p.compliance_tags.split(',').map((tag: string) => (
                    <span key={tag} className="bg-blue-900 text-blue-300 px-2 py-0.5 rounded">{tag.trim()}</span>
                  ))}
                </div>
                {p.config && Object.keys(p.config).length > 0 && (
                  <pre className="text-xs text-gray-600 mt-2">{JSON.stringify(p.config)}</pre>
                )}
              </div>
            ))}
            {policies.length === 0 && (
              <p className="text-gray-500 text-sm">Aucune politique définie. Créez-en une via l'API.</p>
            )}
          </div>
        </section>

        <section>
          <h3 className="text-lg font-semibold mb-2">Journal d'audit</h3>
          <p className="text-xs text-gray-500 mb-3">
            Historique des actions de gouvernance : création de politiques, évaluations, décisions de blocage.
            Chaque entrée montre l'action, l'acteur et les détails.
          </p>
          <div className="space-y-2">
            {auditLog.map((a: any) => (
              <div key={a.id} className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-sm">
                <div className="flex gap-2 mb-1">
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                    a.action === 'create' ? 'bg-green-900 text-green-300' :
                    a.action === 'evaluate' ? 'bg-blue-900 text-blue-300' :
                    'bg-gray-700 text-gray-300'
                  }`}>{a.action}</span>
                  <span className="text-gray-400">{a.actor}</span>
                </div>
                <p className="text-gray-500 text-xs">{a.details_json}</p>
                <p className="text-gray-600 text-xs mt-1">{new Date(a.created_at).toLocaleString('fr-FR')}</p>
              </div>
            ))}
            {auditLog.length === 0 && (
              <p className="text-gray-500 text-sm">Aucune entrée d'audit pour le moment.</p>
            )}
          </div>
        </section>
      </div>

      {Object.keys(frameworks).length > 0 && (
        <section className="mt-8">
          <h3 className="text-lg font-semibold mb-2">Frameworks de conformité</h3>
          <p className="text-xs text-gray-500 mb-3">
            Cadres réglementaires que TokenForge peut vérifier automatiquement.
            Chaque framework liste les exigences techniques supportées.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Object.entries(frameworks).map(([key, fw]: [string, any]) => (
              <div key={key} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <h4 className="font-medium text-orange-400 mb-1">{key}</h4>
                <p className="text-xs text-gray-400 mb-2">{fw.description}</p>
                <div className="flex flex-wrap gap-1">
                  {fw.requirements?.map((req: string) => (
                    <span key={req} className="text-xs bg-gray-800 text-gray-300 px-2 py-0.5 rounded">{req}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
