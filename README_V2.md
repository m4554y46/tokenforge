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

## Les 5 piliers + modules transverses

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
python -m unittest tests.test_v2_platform   # tests v2
```

---

## Docker (production)

```bash
docker-compose up -d
```

PostgreSQL + Redis + Qdrant + API.

---

Voir **[docs/GUIDE_V2_PLATFORM.md](./docs/GUIDE_V2_PLATFORM.md)** pour exemples curl, SDK, configuration et déploiement détaillés.
