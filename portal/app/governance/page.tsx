'use client';

import { useEffect, useState } from 'react';
import { KpiCard } from '../../components/KpiCard';

const RULE_TYPE_LABELS: Record<string, string> = {
  deny_model: 'Deny Model',
  limit_provider: 'Limit Provider',
  force_compression: 'Force Compression',
  force_cache: 'Force Cache',
  max_tokens: 'Max Tokens',
  require_approval: 'Require Approval',
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

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <KpiCard label="Politiques actives" value={String(activePolicies.length)} />
        <KpiCard label="Total politiques" value={String(policies.length)} />
        <KpiCard label="Règles de blocage" value={String(denyCount)} />
        <KpiCard label="Frameworks conformité" value={String(Object.keys(frameworks).length)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <section>
          <h3 className="text-lg font-semibold mb-3">Politiques</h3>
          <div className="space-y-2">
            {policies.map((p: any) => (
              <div key={p.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium">{p.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${p.enabled ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-400'}`}>
                    {p.enabled ? 'Actif' : 'Inactif'}
                  </span>
                </div>
                <div className="flex gap-2 text-xs text-gray-400">
                  <span className="bg-gray-800 px-2 py-0.5 rounded">{RULE_TYPE_LABELS[p.rule_type] || p.rule_type}</span>
                  {p.compliance_tags && p.compliance_tags.split(',').map((tag: string) => (
                    <span key={tag} className="bg-blue-900 text-blue-300 px-2 py-0.5 rounded">{tag.trim()}</span>
                  ))}
                </div>
                {p.config && Object.keys(p.config).length > 0 && (
                  <pre className="text-xs text-gray-500 mt-2">{JSON.stringify(p.config)}</pre>
                )}
              </div>
            ))}
          </div>
        </section>

        <section>
          <h3 className="text-lg font-semibold mb-3">Journal d'audit</h3>
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
          </div>
        </section>
      </div>

      {Object.keys(frameworks).length > 0 && (
        <section className="mt-8">
          <h3 className="text-lg font-semibold mb-3">Frameworks de conformité</h3>
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
