'use client';

import { useEffect, useState } from 'react';

export default function ExperimentsPage() {
  const [experiments, setExperiments] = useState<unknown[]>([]);

  useEffect(() => {
    fetch('/api/v2/experiments', { headers: { 'X-Tenant-ID': 'default', 'X-User-ID': 'portal' } })
      .then((r) => r.json()).then(setExperiments);
  }, []);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">A/B Experiments</h2>
      <pre className="bg-gray-900 p-4 rounded text-sm">{JSON.stringify(experiments, null, 2)}</pre>
    </div>
  );
}
