'use client';

import { useEffect, useState } from 'react';

export default function PromptsPage() {
  const [top, setTop] = useState<Record<string, unknown>>({});

  useEffect(() => {
    fetch('/api/v2/prompts/top', { headers: { 'X-Tenant-ID': 'default', 'X-User-ID': 'portal' } })
      .then((r) => r.json()).then(setTop);
  }, []);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Prompt Analytics</h2>
      <pre className="bg-gray-900 p-4 rounded text-sm overflow-auto">{JSON.stringify(top, null, 2)}</pre>
    </div>
  );
}
