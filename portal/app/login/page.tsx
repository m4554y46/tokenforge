'use client';

import { useState } from 'react';

export default function LoginPage() {
  const [tenantId, setTenantId] = useState('demo');
  const [userId, setUserId] = useState('alice');
  const [error, setError] = useState('');

  const login = () => {
    if (!tenantId.trim() || !userId.trim()) {
      setError('Veuillez remplir tous les champs');
      return;
    }
    sessionStorage.setItem('tf_tenant_id', tenantId.trim());
    sessionStorage.setItem('tf_user_id', userId.trim());
    window.location.href = '/';
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950">
      <div className="bg-gray-900 rounded-xl p-8 w-full max-w-md border border-gray-800">
        <h1 className="text-2xl font-bold text-orange-400 mb-2 text-center">TokenForge</h1>
        <p className="text-gray-400 text-sm mb-6 text-center">
          Intelligence Platform — Connexion
        </p>

        <div className="mb-4">
          <label className="block text-sm text-gray-400 mb-1">Tenant ID</label>
          <input type="text" value={tenantId} onChange={e => setTenantId(e.target.value)}
            className="w-full bg-gray-800 rounded p-3 text-sm border border-gray-700"
            placeholder="Ex: demo, acme-corp" />
        </div>

        <div className="mb-6">
          <label className="block text-sm text-gray-400 mb-1">Utilisateur</label>
          <input type="text" value={userId} onChange={e => setUserId(e.target.value)}
            className="w-full bg-gray-800 rounded p-3 text-sm border border-gray-700"
            placeholder="Ex: alice, bob" />
        </div>

        {error && <div className="text-red-400 text-sm mb-4">{error}</div>}

        <button onClick={login}
          className="w-full bg-orange-600 hover:bg-orange-500 py-3 rounded font-medium">
          Se connecter
        </button>

        <div className="mt-6 text-xs text-gray-500 text-center">
          <p>Tenant de démo : <code className="text-gray-300">demo</code></p>
          <p>Utilisateurs : <code className="text-gray-300">alice, bob, carole, david, emma</code></p>
        </div>
      </div>
    </div>
  );
}
