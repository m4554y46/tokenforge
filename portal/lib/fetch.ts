"use client";

/** Fetch with auth headers from sessionStorage */
export function authFetch(url: string, init?: RequestInit): Promise<Response> {
  const tid = sessionStorage.getItem("tf_tenant_id") || "demo";
  const uid = sessionStorage.getItem("tf_user_id") || "portal";
  return fetch(url, {
    ...init,
    headers: {
      ...init?.headers,
      "X-Tenant-ID": tid,
      "X-User-ID": uid,
    },
  });
}

/** Fetch with auth headers, throws on non-ok response */
export async function authFetchOk(url: string, init?: RequestInit): Promise<Response> {
  const r = await authFetch(url, init);
  if (!r.ok) {
    const err = await r.text().catch(() => "");
    throw new Error(`HTTP ${r.status}: ${err || r.statusText}`);
  }
  return r;
}

/** Safe JSON fetch with auth, returns null on error */
export async function authFetchJson<T>(url: string, init?: RequestInit): Promise<T | null> {
  try {
    const r = await authFetchOk(url, init);
    return await r.json();
  } catch {
    return null;
  }
}
