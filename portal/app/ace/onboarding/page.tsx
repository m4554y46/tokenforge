'use client';

import { useEffect, useState } from 'react';
import { authFetch } from '../../../lib/fetch';

interface ProfileResult {
  profile: string;
  rate: number;
  token_count_original: number;
  tokens_saved_per_request: number;
  tokens_after_compression: number;
  savings_usd_per_request: number;
  monthly_savings: number;
  monthly_tf_cost: number;
  net_monthly: number;
  net_annual: number;
  roi_percent: number;
}

interface OnboardingResult {
  prompt_analysis: {
    token_count: number;
    task_type: string;
    length_bucket: string;
    specificity: string;
    protected_ratio: number;
    sanctuary_max_rate: number;
  };
  model: string;
  token_price_per_1k: number;
  monthly_requests: number;
  min_client_savings: number;
  by_profile: ProfileResult[];
  recommendation: ProfileResult | null;
  annual_projection: {
    net_annual_recommended: number;
    total_savings_gross: number;
    total_tf_cost: number;
  };
}

export default function OnboardingPage() {
  const [prompt, setPrompt] = useState('');
  const [model, setModel] = useState('gpt-4o');
  const [monthlyReqs, setMonthlyReqs] = useState(100000);
  const [result, setResult] = useState<OnboardingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const calculate = () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setError(null);
    authFetch(`/api/v2/ace/onboarding?prompt=${encodeURIComponent(prompt)}&model=${model}&monthly_requests=${monthlyReqs}`)
      .then(r => { if (!r.ok) throw new Error('Erreur calcul'); return r.json(); })
      .then(setResult)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Calculateur de ROI interactif</h1>
      <p className="text-gray-400 mb-6">
        Testez l'impact de la compression ACE sur vos prompts et visualisez les économies potentielles.
      </p>

      <div className="bg-gray-800 rounded-lg p-6 mb-8">
        <div className="mb-4">
          <label className="block text-sm text-gray-400 mb-1">Votre prompt</label>
          <textarea value={prompt} onChange={e => setPrompt(e.target.value)}
            placeholder="Collez un exemple de prompt que vous envoyez à l'IA..."
            className="w-full bg-gray-900 rounded p-3 text-sm border border-gray-700 h-32"
          />
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Modèle</label>
            <select value={model} onChange={e => setModel(e.target.value)}
              className="w-full bg-gray-900 rounded p-2 text-sm border border-gray-700">
              <option value="gpt-4o">GPT-4o</option>
              <option value="gpt-4o-mini">GPT-4o Mini</option>
              <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
              <option value="claude-3-5-haiku">Claude 3.5 Haiku</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Requêtes / mois</label>
            <input type="number" value={monthlyReqs} onChange={e => setMonthlyReqs(Number(e.target.value))}
              className="w-full bg-gray-900 rounded p-2 text-sm border border-gray-700" />
          </div>
        </div>

        <button onClick={calculate} disabled={loading || !prompt.trim()}
          className="bg-orange-600 hover:bg-orange-500 disabled:bg-gray-600 px-6 py-2 rounded font-medium">
          {loading ? 'Calcul...' : 'Calculer le ROI'}
        </button>

        {error && <div className="text-red-400 mt-2 text-sm">{error}</div>}
      </div>

      {result && (
        <>
          {result.prompt_analysis.sanctuary_max_rate < 1 && (
            <div className="bg-yellow-900/50 text-yellow-300 rounded p-3 text-sm mb-6">
              Contenu protégé détecté ({Math.round(result.prompt_analysis.protected_ratio * 100)}%) — taux max limité à {Math.round(result.prompt_analysis.sanctuary_max_rate * 100)}% par Sanctuary.
            </div>
          )}

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <Kpi label="Tokens / requête" value={result.prompt_analysis.token_count} />
            <Kpi label="Type de tâche" value={result.prompt_analysis.task_type} />
            <Kpi label="Modèle" value={result.model} />
            <Kpi label="Volume mensuel" value={result.monthly_requests.toLocaleString()} />
          </div>

          {result.recommendation && (
            <div className="bg-green-900/30 border border-green-700 rounded-lg p-6 mb-8">
              <h2 className="text-lg font-semibold text-green-400 mb-2">Recommandation : {result.recommendation.profile}</h2>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <div className="text-xs text-gray-400">Économies nettes / mois</div>
                  <div className="text-xl font-bold text-green-400">{result.recommendation.net_monthly.toFixed(2)} USD</div>
                </div>
                <div>
                  <div className="text-xs text-gray-400">Économies nettes / an</div>
                  <div className="text-xl font-bold text-green-400">{result.recommendation.net_annual.toFixed(2)} USD</div>
                </div>
                <div>
                  <div className="text-xs text-gray-400">ROI</div>
                  <div className="text-xl font-bold text-green-400">{result.recommendation.roi_percent}%</div>
                </div>
              </div>
            </div>
          )}

          <h2 className="text-lg font-semibold mb-3">Comparaison par profil</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-700">
                  <th className="py-2 pr-4">Profil</th>
                  <th className="py-2 pr-4">Taux</th>
                  <th className="py-2 pr-4">Tokens/req</th>
                  <th className="py-2 pr-4">Éco./req</th>
                  <th className="py-2 pr-4">Net/mois</th>
                  <th className="py-2 pr-4">Net/an</th>
                  <th className="py-2 pr-4">ROI</th>
                </tr>
              </thead>
              <tbody>
                {result.by_profile.map((p, i) => (
                  <tr key={i} className={`border-b border-gray-800 ${p.profile === result.recommendation?.profile ? 'bg-green-900/20' : ''}`}>
                    <td className="py-2 pr-4 font-medium">{p.profile}</td>
                    <td className="py-2 pr-4">{(p.rate * 100).toFixed(0)}%</td>
                    <td className="py-2 pr-4">{p.tokens_after_compression}</td>
                    <td className="py-2 pr-4">{p.savings_usd_per_request.toFixed(6)}</td>
                    <td className="py-2 pr-4 text-green-400">{p.net_monthly.toFixed(2)}</td>
                    <td className="py-2 pr-4 text-green-400">{p.net_annual.toFixed(2)}</td>
                    <td className="py-2 pr-4">{p.roi_percent}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
