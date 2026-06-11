# TokenForge Intelligence Platform v2

> **Guide complet :** [docs/GUIDE_V2_PLATFORM.md](./docs/GUIDE_V2_PLATFORM.md)

**Positionnement :** Le Datadog + FinOps + CDN des LLM.

Fork enterprise de [TokenForge v1](https://github.com/m4554y46/tokenforge) — conserve 100% du legacy (SPC, proxy, Electron) et ajoute la couche enterprise.

---

## Démarrage rapide

```bash
git clone https://github.com/m4554y46/TokenForgev2
cd TokenForgev2
pip install -r requirements.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
```

```bash
# Portail DSI (optionnel)
cd portal && npm install && npm run dev   # http://localhost:3000
```

---

## Les 6 piliers + modules transverses

### Pilier 1 — Memory Layer (`backend/memory/`)

Apprend les habitudes utilisateur et la terminologie entreprise pour réduire tokens et redondances.

| Fichier | Rôle | API |
|---------|------|-----|
| `user_memory_service.py` | Préférences user (langue, ton, format, modèle) | `GET/PUT /api/v2/memory/user/profile` |
| `tenant_memory_service.py` | Knowledge base métier (acronymes, templates) | `GET/POST /api/v2/memory/tenant/terms` |
| `memory_embeddings.py` | Vecteurs sémantiques (MiniLM) | interne |
| `memory_index.py` | Index Qdrant / mémoire | interne |
| `memory_retriever.py` | Assemble le contexte avant appel LLM | `POST /api/v2/memory/retrieve` |
| `memory_updater.py` | Apprentissage depuis interactions | `POST /api/v2/memory/learn` |
| `memory_summarizer.py` | Résumés pour dashboard | `GET /api/v2/memory/*/summary` |

**ROI :** −30% tokens en évitant de répéter préférences et contexte métier.

---

### Pilier 2 — Prompt Intelligence (`backend/prompts/`)

Analyse le parc de prompts de l'entreprise.

| Fichier | Rôle | API |
|---------|------|-----|
| `prompt_inventory.py` | Inventaire, fréquence, coût | `GET /api/v2/prompts/inventory` |
| `prompt_similarity.py` | Doublons, variantes, clusters | `GET /api/v2/prompts/similarity` |
| `prompt_diff.py` | Compare 2 prompts + impact coût | `POST /api/v2/prompts/diff` |
| `prompt_explainability.py` | Pourquoi / gain / risque | `POST /api/v2/prompts/explain` |

**ROI :** Identifie les prompts qui concentrent 80% des coûts.

---

### Pilier 3 — FinOps (`backend/finops/`)

Pilotage financier complet de l'IA.

| Fichier | Rôle | API |
|---------|------|-----|
| `cost_registry.py` | Enregistre chaque appel LLM | `GET /api/v2/finops/summary` |
| `budget_engine.py` | Budgets user/team/app/tenant | `GET/POST /api/v2/finops/budgets` |
| `forecast_engine.py` | Prévisions mensuel/trimestriel/annuel | `GET /api/v2/finops/forecast` |
| `anomaly_detection.py` | Pics de coût, dérives utilisateur | `GET /api/v2/finops/anomalies` |
| `roi_engine.py` | ROI net = économies − coût TokenForge | `GET /api/v2/finops/roi` |

**ROI :** Le DSI peut prouver la valeur au COMEX.

---

### Pilier 4 — Governance (`backend/governance/`)

Gouvernance et conformité.

| Fichier | Rôle | API |
|---------|------|-----|
| `rule_engine.py` | Interdire modèles, forcer compression/cache | `GET/POST /api/v2/governance/policies` |
| `compliance.py` | RGPD, SOC2, ISO27001, data residency | `GET /api/v2/governance/compliance` |
| `approval_workflows.py` | Validation des changements de politique | interne (cache) |

**ROI :** Réduit risques réglementaires et usages non conformes.

---

### Pilier 5 — Smart Gateway (`backend/gateway/`)

Route chaque requête vers la stratégie optimale.

| Fichier | Rôle | API |
|---------|------|-----|
| `predictive_router.py` | cache / compress / bypass / deny | `POST /api/v2/gateway/route` |
| `circuit_breaker.py` | Retry, timeout, fallback provider | `GET /api/v2/gateway/circuit-breaker` |
| `cache_governor.py` | Maximise le cache hit rate | `GET /api/v2/gateway/cache` |

Le proxy legacy `/v1/chat/completions` reste compatible SDK OpenAI.

**ROI :** Compression et cache automatiques sans changer le code client.

---

### Pilier 6 — Adaptive Compression Engine (`backend/ace/`)

Choisit dynamiquement le meilleur taux de compression pour chaque requête LLM en maximisant la marge économique nette. **11 couches** dont 6 nouvelles gates contractuelles (Phase 2).

| Fichier | Rôle | API | Nouveau |
|---------|------|-----|---------|
| `pif.py` | Prompt Information Footprint — entropie + redondance → headroom | intégré proxy | ✅ |
| `decider.py` | UCB Non-Monotone Cascade (explore/exploit par UCB décroissant) | intégré proxy | ✅ modifié |
| `integrity_gate.py` | Entropy Gate (quenching adaptatif) + Integrity Gate (4 vérifications) | intégré proxy | ✅ |
| `oracle.py` | Quality Oracle AND-logic — 5 dimensions toutes ≥ seuil | intégré proxy | ✅ |
| `ensemble_judge.py` | Dawid-Skene EM — consensus multi-juge (GPT-4o, BLEU, ROUGE, heuristic) | intégré proxy | ✅ |
| `drift_detector.py` | MMD-based drift detection (noyau RBF, fenêtre 100, permutation test) | `get_status()` | ✅ |
| `reconstruction_monitor.py` | factual_loss vs novelty_gain post-compression | intégré proxy | ✅ |
| `features.py` | Extraction contexte : task, specificity, length, cluster | interne | 🔧 |
| `state.py` | Cellules + 3 nouvelles tables (calibration, drift, oracle) | `GET /api/v2/ace/cells` | 🔧 |
| `signals.py` | Détection reformulation/continuation entre requêtes | interne | — |
| `models/quality_model.py` | LightGBM → ONNX, prédit qualité avec/sans signaux | `GET /api/v2/ace/train` | — |
| `exploration.py` | Knowledge Gradient : explore seulement si ça change $r^*$ | interne | — |
| `attribution.py` | Cause du signal : compression vs LLM vs user vs contexte | interne | — |
| `sanctuary.py` | Détection contenu protégé (code, JSON, LaTeX, YAML, tableaux) | intégré proxy | — |
| `embeddings.py` | SVD contextes × taux, cold-start par k-NN | interne | — |
| `judge.py` | QualityJudge GPT-4o (5 dimensions, fallback heuristique) | intégré oracle | — |
| `dashboard.py` | Agrégation qualité depuis ace_states/ace_requests | `GET /api/v2/ace/quality-dashboard` | — |
| `onboarding.py` | Calculateur ROI interactif pour prospects | `GET /api/v2/ace/onboarding` | — |
| `train.py` | Pipeline d'entraînement unifié (quality model + embeddings) | `GET /api/v2/ace/train` | — |

**Pipeline complet :**
```
PIF (headroom < 5% → bypass)
  → Sanctuary (contenu protégé → plafonnement)
    → UCB Cascade (tri par UCB décroissant)
      → Compression SPC + Entropy Gate (quenching)
        → Integrity Gate (validation post-check)
          → Forward LLM
            → Reconstruction Monitor (factual_loss)
              → Oracle (AND-logic 5 dimensions)
                → Dawid-Skene consensus + Drift sample
```

**ROI :** +36% marge nette vs profil fixe, bypass automatique si headroom < 5% ou utilité ≤ 0.

```bash
# Décision expliquée (pour le DSI)
curl "http://127.0.0.1:8765/api/v2/ace/explain?prompt=Analyse+les+tendances+Q3" -H "X-Tenant-ID: acme"
```

---

### Modules transverses

| Module | Rôle | API |
|--------|------|-----|
| `backend/observability/` | Métriques, traces, Prometheus | `/api/v2/observability/*` |
| `backend/experiments/` | A/B original vs compressé | `/api/v2/experiments` |
| `backend/core/` | DB, cache Redis, auth JWT, multi-tenant | headers `X-Tenant-ID` |
| `portal/` | Portail Next.js DSI | `http://localhost:3000` |
| `sdk/python/`, `sdk/node/` | Clients programmatiques | voir guide |

---

## Dashboard DSI

```bash
curl http://127.0.0.1:8765/api/v2/dashboard \
  -H "X-Tenant-ID: default" -H "X-User-ID: admin"
```

Retourne : finops, ROI, prompts, alertes budget, anomalies, cache, mémoire.

---

## Compatibilité v1

L'API v1 (`/api/*`), le proxy (`/v1/*`), Electron et le pipeline SPC sont **inchangés**.

---

## Tests

```bash
python -m unittest backend.spc.tests        # 149 tests SPC
python -m unittest tests.test_v2_platform   # 26 tests v2 platform
python -m pytest tests/test_ace.py -v       # 102 tests ACE
```

---

## Docker (production)

```bash
docker-compose up -d
```

PostgreSQL + Redis + Qdrant + API.

---

Voir **[docs/GUIDE_V2_PLATFORM.md](./docs/GUIDE_V2_PLATFORM.md)** pour exemples curl, SDK, configuration et déploiement détaillés.
