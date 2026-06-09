/**
 * TokenForge Intelligence Platform — SDK Node.js
 */
export class TokenForgeClient {
  constructor({ baseUrl = 'http://127.0.0.1:8765', apiKey = '', tenantId = 'default', userId = 'sdk' } = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.apiKey = apiKey;
    this.tenantId = tenantId;
    this.userId = userId;
  }

  _headers() {
    const h = { 'X-Tenant-ID': this.tenantId, 'X-User-ID': this.userId, 'Content-Type': 'application/json' };
    if (this.apiKey) h['Authorization'] = `Bearer ${this.apiKey}`;
    return h;
  }

  async health() {
    const r = await fetch(`${this.baseUrl}/api/v2/health`);
    return r.json();
  }

  async dashboard() {
    const r = await fetch(`${this.baseUrl}/api/v2/dashboard`, { headers: this._headers() });
    return r.json();
  }

  async finopsRoi() {
    const r = await fetch(`${this.baseUrl}/api/v2/finops/roi`, { headers: this._headers() });
    return r.json();
  }

  async routeRequest(prompt, model = 'gpt-4o') {
    const r = await fetch(`${this.baseUrl}/api/v2/gateway/route`, {
      method: 'POST', headers: this._headers(),
      body: JSON.stringify({ prompt, model }),
    });
    return r.json();
  }

  async chatCompletions(messages, model = 'gpt-4o', extra = {}) {
    const r = await fetch(`${this.baseUrl}/v1/chat/completions`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${this.apiKey || 'sk-tokenforge'}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, messages, ...extra }),
    });
    return r.json();
  }
}
