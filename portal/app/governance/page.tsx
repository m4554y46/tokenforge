'use client';

import { useEffect, useState } from 'react';

export default function GovernancePage() {
  const [policies, setPolicies] = useState<unknown[]>([]);

  useEffect(() => {
    fetch('/api/v2/governance/policies', { headers: { 'X-Tenant-ID': 'default', 'X-User-ID': 'portal' } })
      .then((r) => r.json()).then(setPolicies);
  }, []);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Policy Center</h2>
      <pre className="bg-gray-900 p-4 rounded text-sm">{JSON.stringify(policies, null, 2)}</pre>
    </div>
  );
}
