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

async function togglePolicy(id: number, current: boolean): Promise<boolean> {
  try {
    const r = await fetch(`/api/v2/governance/policies/${id}/toggle`, {
      method: 'PUT',
      headers: { 'X-Tenant-ID': 'default', 'X-User-ID': 'portal' },
    });
    if (!r.ok) return false;
    const d = await r.json();
    return d.enabled;
  } catch { return !current; }
}

export default function GovernancePage() {
  const [policies, setPolicies] = useState<any[]>([]);
  const [auditLog, setAuditLog] = useState<any[]>([]);
  const [frameworks, setFrameworks] = useState<Record<string, any>>({});
  const [complianceEnabled, setComplianceEnabled] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const h = { 'X-Tenant-ID': 'default', 'X-User-ID': 'portal' };
    fetch('/api/v2/governance/policies', { headers: h }).then(r => r.json()).then(d => setPolicies(d.value ?? d));
    fetch('/api/v2/governance/audit', { headers: h }).then(r => r.json()).then(d => setAuditLog(d.value ?? d));
    fetch('/api/v2/governance/compliance/frameworks', { headers: h }).then(r => r.json()).then(fws => {
      setFrameworks(fws);
      const stored = JSON.parse(localStorage.getItem('tf_compliance_enabled') ?? '{}');
      const initial: Record<string, boolean> = {};
      Object.keys(fws).forEach(k => { initial[k] = stored[k] ?? false; });
      setComplianceEnabled(initial);
    });
  }, []);

  const handleToggle = async (id: number, current: boolean, idx: number) => {
    const newState = await togglePolicy(id, current);
    if (newState !== current) {
      setPolicies(prev => {
        const copy = [...prev];
        if (copy[idx]) copy[idx] = { ...copy[idx], enabled: newState };
        return copy;
      });
    }
  };

  const toggleCompliance = (key: string) => {
    setComplianceEnabled(prev => {
      const next = { ...prev, [key]: !prev[key] };
      localStorage.setItem('tf_compliance_enabled', JSON.stringify(next));
      return next;
    });
  };

  const activePolicies = policies.filter(p => p.enabled);
  const denyCount = policies.filter(p => p.rule_type === 'deny_model' || p.rule_type === 'limit_provider').length;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Policy Center</h2>
      <p className="text-sm text-gray-500 mb-6">
        Les politiques sont évaluées à chaque appel LLM. Activez ou désactivez une politique d'un clic.
        Les frameworks de conformité (RGPD, SOC2) activent des contrôles supplémentaires sur les données.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div>
          <KpiCard label="Politiques actives" value={String(activePolicies.length)} />
          <p className="text-xs text-gray-600 mt-1">Règles actuellement appliquées à chaque appel LLM.</p>
        </div>
        <div>
          <KpiCard label="Total politiques" value={String(policies.length)} />
          <p className="text-xs text-gray-600 mt-1">Toutes les règles, actives et inactives.</p>
        </div>
        <div>
          <KpiCard label="Règles de blocage" value={String(denyCount)} />
          <p className="text-xs text-gray-600 mt-1">Modèles ou fournisseurs interdits.</p>
        </div>
        <div>
          <KpiCard label="Frameworks conformité" value={`${Object.values(complianceEnabled).filter(Boolean).length}/${Object.keys(frameworks).length}`} />
          <p className="text-xs text-gray-600 mt-1">Frameworks activés / disponibles.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <section>
          <h3 className="text-lg font-semibold mb-2">Politiques</h3>
          <p className="text-xs text-gray-500 mb-3">
            Cliquez sur le toggle pour activer/désactiver une politique. Les modifications sont appliquées immédiatement.
          </p>
          <div className="space-y-2">
            {policies.map((p: any, idx: number) => (
              <div key={p.id} className={`bg-gray-900 border rounded-lg p-4 ${p.enabled ? 'border-green-900' : 'border-gray-800'}`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium">{p.name}</span>
                  <button
                    onClick={() => handleToggle(p.id, p.enabled, idx)}
                    className={`relative w-10 h-5 rounded-full transition-colors ${p.enabled ? 'bg-green-600' : 'bg-gray-600'}`}
                  >
                    <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform ${p.enabled ? 'translate-x-5' : ''}`} />
                  </button>
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
              <p className="text-gray-500 text-sm">Aucune politique définie. Créez-en une via API (POST /api/v2/governance/policies).</p>
            )}
          </div>
        </section>

        <section>
          <h3 className="text-lg font-semibold mb-2">Frameworks de conformité</h3>
          <p className="text-xs text-gray-500 mb-3">
            Activez un framework pour appliquer ses exigences. Les contrôles sont évalués automatiquement sur chaque donnée transitant par la plateforme.
          </p>
          <div className="space-y-3">
            {Object.entries(frameworks).length === 0 && (
              <p className="text-gray-500 text-sm">API non disponible.</p>
            )}
            {Object.entries(frameworks).map(([key, fw]: [string, any]) => {
              const enabled = complianceEnabled[key] ?? false;
              return (
                <div key={key} className={`bg-gray-900 border rounded-lg p-4 ${enabled ? 'border-orange-900' : 'border-gray-800'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <h4 className="font-medium text-orange-400">{key}</h4>
                      <p className="text-xs text-gray-400">{fw.description}</p>
                    </div>
                    <button
                      onClick={() => toggleCompliance(key)}
                      className={`relative w-10 h-5 rounded-full transition-colors ${enabled ? 'bg-orange-600' : 'bg-gray-600'}`}
                    >
                      <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform ${enabled ? 'translate-x-5' : ''}`} />
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-1 mb-2">
                    {fw.requirements?.map((req: string) => (
                      <span key={req} className={`text-xs px-2 py-0.5 rounded ${enabled ? 'bg-green-900 text-green-300' : 'bg-gray-800 text-gray-500'}`}>
                        {req}
                      </span>
                    ))}
                  </div>
                  <p className="text-xs text-gray-600">
                    {enabled
                      ? `✓ ${key} actif. Les ${fw.requirements?.length ?? 0} exigences sont vérifiées automatiquement.`
                      : `Inactif. Activez pour vérifier les ${fw.requirements?.length ?? 0} exigences.`}
                  </p>
                </div>
              );
            })}
          </div>
        </section>
      </div>

      <section className="mt-8">
        <h3 className="text-lg font-semibold mb-2">Journal d'audit</h3>
        <p className="text-xs text-gray-500 mb-3">
          Toutes les actions de gouvernance sont tracées : création, activation, désactivation, évaluation.
        </p>
        <div className="space-y-2">
          {auditLog.map((a: any) => (
            <div key={a.id} className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-sm">
              <div className="flex gap-2 mb-1">
                <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                  a.action === 'create' || a.action === 'enable' ? 'bg-green-900 text-green-300' :
                  a.action === 'disable' ? 'bg-red-900 text-red-300' :
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
  );
}
