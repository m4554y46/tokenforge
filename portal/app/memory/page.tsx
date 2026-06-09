'use client';

import { useEffect, useState } from 'react';

export default function MemoryPage() {
  const [profile, setProfile] = useState<Record<string, unknown>>({});

  useEffect(() => {
    fetch('/api/v2/memory/user/profile', {
      headers: { 'X-Tenant-ID': 'default', 'X-User-ID': 'portal' },
    }).then((r) => r.json()).then(setProfile);
  }, []);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Memory Center</h2>
      <section className="mb-8">
        <h3 className="text-lg font-semibold mb-2">User Preferences</h3>
        <pre className="bg-gray-900 p-4 rounded text-sm">{JSON.stringify(profile, null, 2)}</pre>
      </section>
    </div>
  );
}
