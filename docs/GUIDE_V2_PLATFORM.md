# Guide complet — TokenForge Intelligence Platform v2

> **Positionnement :** Le Datadog + FinOps + CDN des LLM  
> **Principe :** chaque fonctionnalité doit réduire les coûts, réduire les risques, ou les deux.

---

## Sommaire

1. [Vue d'ensemble](#1-vue-densemble)
2. [Infrastructure core](#2-infrastructure-core)
3. [Pilier 1 — Memory Layer](#3-pilier-1--memory-layer)
4. [Pilier 2 — Prompt Intelligence](#4-pilier-2--prompt-intelligence)
5. [Pilier 3 — FinOps](#5-pilier-3--finops)
6. [Pilier 4 — Governance](#6-pilier-4--governance)
7. [Pilier 5 — Smart Gateway](#7-pilier-5--smart-gateway)
8. [Observability & Experiments](#8-observability--experiments)
9. [Portail web (Next.js)](#9-portail-web-nextjs)
10. [SDKs](#10-sdks)
11. [Référence API v2](#11-référence-api-v2)
12. [Configuration & déploiement](#12-configuration--déploiement)

---

## 1. Vue d'ensemble

TokenForge v2 **conserve intégralement** TokenForge v1 (compression SPC, proxy OpenAI, Electron, UI legacy) et ajoute une couche enterprise accessible via :

| Interface | URL / chemin | Public cible |
|-----------|--------------|--------------|
| API v1 (legacy) | `/api/*`, `/v1/*` | Développeurs, desktop |
| API v2 (enterprise) | `/api/v2/*` | DSI, plateforme, intégrations |
| Portail Next.js | `http://localhost:3000` | DSI, FinOps, admins |
| UI Electron legacy | `frontend/` ou `npm start` | Utilisateurs finaux |

### Architecture globale

```
Clients (SDK / apps / IDE)
        │
        ▼
┌───────────────────────────────────────────────┐
│  Smart Gateway (/v1/* + /api/v2/gateway)    │
│  Circuit breaker · Routeur · Cache governor   │
└───────────────┬───────────────────────────────┘
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
 Memory      FinOps     Governance
 Layer       Platform    Engine
    │           │           │
    └───────────┼───────────┘
                ▼
        SPC Pipeline (v1)
                │
                ▼
         Providers LLM
```

### Headers multi-tenant (API v2)

Toutes les routes v2 acceptent :

| Header | Obligatoire | Description |
|--------|-------------|-------------|
| `X-Tenant-ID` | Recommandé | Identifiant entreprise (défaut : `default`) |
| `X-User-ID` | Recommandé | Identifiant utilisateur (défaut : `anonymous`) |
| `Authorization` | Optionnel | `Bearer <token>` JWT pour RBAC |

---

## 2. Infrastructure core

### `backend/config.py`

**Rôle :** Configuration centralisée via variables d'environnement.

**Apporte :** Un seul point de configuration pour dev (SQLite) et prod (PostgreSQL, Redis, Qdrant).

**Variables clés :**

| Variable | Défaut | Usage |
|----------|--------|-------|
| `DATABASE_URL` | `tokenforge_v2.db` | SQLite fichier ou `postgresql://...` |
| `REDIS_URL` | vide | Cache distribué (fallback mémoire si absent) |
| `QDRANT_URL` | `http://localhost:6333` | Index vectoriel mémoire |
| `JWT_SECRET` | dev secret | Signature tokens API |
| `FORGE_COMPRESSION_PROFILE` | `industrial` | Profil SPC du proxy |

---

### `backend/core/database_v2.py`

**Rôle :** Couche persistance enterprise (multi-tenant).

**Apporte :** Tables `user_memory`, `tenant_memory`, `prompt_events`, `budgets`, `policies`, `experiments`, etc.

**Tables principales :**

| Table | Contenu |
|-------|---------|
| `user_memory` | Préférences par utilisateur (langue, ton, format…) |
| `tenant_memory` | Terminologie métier validée par l'entreprise |
| `prompt_events` | Chaque appel LLM observé (coût, tokens, compression) |
| `budgets` | Plafonds par user/team/app/tenant |
| `policies` | Règles de gouvernance |
| `policy_audit` | Journal d'audit des politiques |
| `experiments` | Tests A/B actifs |

**Utilisation :** Initialisée automatiquement au démarrage (`init_v2_db()` dans `app.py`).

---

### `backend/core/cache.py`

**Rôle :** Cache Redis avec fallback LRU en mémoire.

**Apporte :** Réponses LLM mises en cache, compteurs de fréquence de prompts, workflows d'approbation temporaires.

**Utilisation :** Utilisé par le gateway et les workflows — transparent pour l'appelant.

---

### `backend/core/tenant.py`

**Rôle :** Isolation multi-tenant via contexte HTTP.

**Apporte :** Chaque requête v2 est scopée à un tenant et un utilisateur.

**Exemple :**
```bash
curl -H "X-Tenant-ID: acme-corp" -H "X-User-ID: alice" \
  http://127.0.0.1:8765/api/v2/dashboard
```

---

### `backend/core/auth.py`

**Rôle :** JWT simplifié + RBAC par rôles.

**Apporte :** Tokens pour intégrations machine-to-machine.

**Obtenir un token :**
```bash
curl -X POST http://127.0.0.1:8765/api/v2/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice", "tenant_id": "acme-corp"}'
```

---

## 3. Pilier 1 — Memory Layer

**Objectif :** Apprendre progressivement les habitudes pour réduire tokens, latence et redondances.

### `user_memory_service.py`

| Fonction | Description |
|----------|-------------|
| `get_profile()` | Lit le profil complet d'un utilisateur |
| `set_preference()` | Enregistre une préférence (langue, ton, format, modèle favori…) |
| `update_profile()` | Mise à jour manuelle en lot |
| `export_profile()` | Export JSON (RGPD — droit à la portabilité) |
| `delete_profile()` | Suppression (RGPD — droit à l'effacement) |

**ROI :** Évite de répéter « réponds en français, ton professionnel, format tableau » dans chaque prompt.

**API :**
- `GET /api/v2/memory/user/profile`
- `PUT /api/v2/memory/user/profile` — body : `{"updates": {"language": "fr", "tone": "professional"}}`
- `GET /api/v2/memory/user/export`
- `DELETE /api/v2/memory/user/profile`

---

### `tenant_memory_service.py`

| Fonction | Description |
|----------|-------------|
| `add_term()` | Ajoute acronyme, terme métier, type de document |
| `validate_term()` | Validation humaine par un admin |
| `correct_term()` | Correction de définition |
| `get_validated_knowledge()` | Termes approuvés injectables dans les prompts |

**Exemples de termes :** RFP, ADR, Architecture Review, Change Request.

**ROI :** L'IA comprend le vocabulaire interne sans re-contextualisation coûteuse.

**API :**
- `GET /api/v2/memory/tenant/knowledge`
- `POST /api/v2/memory/tenant/terms` — `{"category": "acronym", "term": "RFP", "definition": "Request for Proposal"}`
- `PUT /api/v2/memory/tenant/terms/{category}/{term}/validate`

---

### `memory_embeddings.py`

**Rôle :** Génère des vecteurs sémantiques (SentenceTransformers `all-MiniLM-L6-v2` ou fallback hash déterministe).

**Apporte :** Recherche sémantique dans l'historique d'interactions.

---

### `memory_index.py`

**Rôle :** Index vectoriel Qdrant (prod) ou in-memory (dev).

**Apporte :** Retrouve des interactions passées similaires pour réutilisation / cache sémantique.

---

### `memory_retriever.py`

**Rôle :** Assemble le contexte mémoire avant un appel LLM.

**Retourne :** `context_prefix` (texte à injecter), `semantic_hits`, `cache_hint`.

**API :** `POST /api/v2/memory/retrieve` — body : `{"prompt": "Analyse ce RFP"}`

---

### `memory_updater.py`

**Rôle :** Apprend automatiquement depuis chaque interaction.

**Détecte :** langue, ton, format, modèle favori, acronymes métier.

**API :** `POST /api/v2/memory/learn` — body : `{"prompt": "...", "model": "gpt-4o", "response": "..."}`

---

### `memory_summarizer.py`

**Rôle :** Résumés pour dashboard et injection prompt.

**API :**
- `GET /api/v2/memory/user/summary`
- `GET /api/v2/memory/tenant/summary`

---

## 4. Pilier 2 — Prompt Intelligence

**Objectif :** Inventorier, analyser et optimiser le parc de prompts de l'entreprise.

### `prompt_inventory.py`

| Fonction | Description |
|----------|-------------|
| `list_prompts()` | Catalogue trié par coût, fréquence ou compressibilité |
| `top_prompts()` | Top 10 : plus utilisés, plus coûteux, plus compressibles |
| `estimate_compressibility()` | Test SPC sur un prompt sans l'envoyer au provider |
| `dashboard_stats()` | KPIs agrégés |

**ROI :** Identifie les 20% de prompts qui génèrent 80% des coûts.

**API :**
- `GET /api/v2/prompts/inventory?limit=50`
- `GET /api/v2/prompts/top`
- `GET /api/v2/prompts/dashboard`

---

### `prompt_similarity.py`

| Fonction | Description |
|----------|-------------|
| `find_exact_duplicates()` | Prompts identiques (normalisés) |
| `find_similar_pairs()` | Similarité cosinus ≥ seuil |
| `cluster()` | Regroupement par familles |
| `analyze_tenant()` | Analyse complète du tenant |

**ROI :** Élimine les doublons — un prompt dupliqué 100 fois = 100× le coût inutile.

**API :** `GET /api/v2/prompts/similarity`

---

### `prompt_diff.py`

**Rôle :** Compare deux versions d'un prompt.

**Retourne :** diff unified, delta tokens, delta coût USD, niveau de risque qualité.

**API :**
```bash
curl -X POST http://127.0.0.1:8765/api/v2/prompts/diff \
  -H "Content-Type: application/json" \
  -d '{"prompt_a": "Version longue...", "prompt_b": "Version courte...", "model": "gpt-4o"}'
```

---

### `prompt_explainability.py`

**Rôle :** Explique chaque optimisation : pourquoi, gain, risque.

**API :**
```bash
curl -X POST http://127.0.0.1:8765/api/v2/prompts/explain \
  -d '{"original_tokens": 1000, "optimized_tokens": 600, "profile": "balanced", "fallback": false}'
```

---

## 5. Pilier 3 — FinOps

**Objectif :** Permettre au DSI de voir, contrôler et prouver le ROI de l'IA.

### `cost_registry.py`

**Rôle :** Enregistre chaque événement LLM (provider, modèle, tokens, coût USD).

**Providers supportés :** OpenAI, Anthropic, Google, DeepSeek, Mistral, modèles internes (vLLM, TGI).

**API :** `GET /api/v2/finops/summary`

---

### `budget_engine.py`

**Rôle :** Budgets par scope (user, team, application, tenant) avec alertes à 80%.

**Exemple :**
```bash
curl -X POST http://127.0.0.1:8765/api/v2/finops/budgets \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: default" \
  -d '{"scope_type": "team", "scope_id": "engineering", "amount_usd": 500, "period": "monthly"}'
```

**API :**
- `GET /api/v2/finops/budgets`
- `GET /api/v2/finops/alerts`

---

### `forecast_engine.py`

**Rôle :** Prévisions mensuelles, trimestrielles, annuelles basées sur l'historique.

**API :** `GET /api/v2/finops/forecast`

---

### `anomaly_detection.py`

**Rôle :** Détecte pics de coût (z-score) et dérives par utilisateur.

**API :** `GET /api/v2/finops/anomalies`

---

### `roi_engine.py`

**Rôle :** Calcule le ROI net TokenForge.

**Formule :** `ROI net = économies brutes - coût TokenForge`

**Retourne :** `baseline_cost_usd`, `optimized_cost_usd`, `net_roi_usd`, `roi_percent`, `verdict`.

**API :** `GET /api/v2/finops/roi`

**Usage DSI :** Réponse à la question « combien TokenForge nous fait économiser ? »

---

## 6. Pilier 4 — Governance

**Objectif :** Contrôler qui utilise quoi, et prouver la conformité.

### `rule_engine.py`

**Types de règles :**

| Type | Exemple |
|------|---------|
| `deny_model` | Interdire GPT-5 pour RH |
| `limit_provider` | Limiter DeepSeek |
| `force_compression` | Compression obligatoire |
| `force_cache` | Cache obligatoire |
| `max_tokens` | Plafond tokens par requête |

**API :**
```bash
# Créer une politique
curl -X POST http://127.0.0.1:8765/api/v2/governance/policies \
  -d '{"name": "No GPT-5 HR", "rule_type": "deny_model", "config": {"models": ["gpt-5"]}}'

# Évaluer avant envoi
curl -X POST http://127.0.0.1:8765/api/v2/governance/evaluate \
  -d '{"model": "gpt-5", "provider": "openai", "tokens": 500}'
```

---

### `compliance.py`

**Frameworks :** RGPD, SOC2, ISO27001.

**Résidency :** UE, US, Private Cloud.

**API :**
- `GET /api/v2/governance/compliance`
- `GET /api/v2/governance/compliance/frameworks`

---

### `approval_workflows.py`

**Rôle :** Soumission / approbation / rejet de changements de politique avec historique.

**Apporte :** Traçabilité pour audits SOC2.

---

## 7. Pilier 5 — Smart Gateway

**Objectif :** Cœur technique — router chaque requête vers la stratégie optimale.

### `predictive_router.py`

**Décisions possibles :**

| Action | Quand |
|--------|-------|
| `cache_hit` | Réponse en cache — 0 appel provider |
| `compress` | Prompt long → pipeline SPC |
| `bypass` | Prompt trop court (< 50 chars) |
| `deny` | Politique de gouvernance bloque |

**API :**
```bash
curl -X POST http://127.0.0.1:8765/api/v2/gateway/route \
  -H "X-Tenant-ID: default" -H "X-User-ID: alice" \
  -d '{"prompt": "Votre long prompt...", "model": "gpt-4o", "provider": "openai"}'
```

**Proxy legacy (v1) :** Le proxy OpenAI existant (`/v1/chat/completions`) reste actif et compatible SDK OpenAI.

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8765/v1", api_key="sk-...")
client.chat.completions.create(model="gpt-4o", messages=[...])
```

---

### `circuit_breaker.py`

**Rôle :** Protège contre les cascades d'erreurs provider (retry, timeout, fallback).

**États :** `closed` → `open` → `half_open`.

**API :** `GET /api/v2/gateway/circuit-breaker`

---

### `cache_governor.py`

**Rôle :** Maximise le cache hit rate en priorisant les prompts fréquents et longs.

**API :** `GET /api/v2/gateway/cache`

---

## 8. Observability & Experiments

### `observability/hub.py`

**Rôle :** Logs structurés, compteurs, traces, export Prometheus.

**API :**
- `GET /api/v2/observability/metrics`
- `GET /api/v2/observability/traces`
- `GET /api/v2/observability/prometheus` — format compatible Grafana

---

### `experiments/experiment_manager.py`

**Rôle :** A/B testing — original vs compressé, ou provider A vs B.

**Exemple :**
```bash
curl -X POST http://127.0.0.1:8765/api/v2/experiments \
  -d '{"name": "compression-ab", "variant_a": "original", "variant_b": "compressed", "metric": "cost"}'
```

**API :** `GET /api/v2/experiments`

---

## 9. Portail web (Next.js)

**Chemin :** `portal/`

**Modules UI :**

| Page | Route | Contenu |
|------|-------|---------|
| Dashboard | `/` | KPI exécutifs, ROI, alertes |
| Prompt Analytics | `/prompts` | Top prompts, similarité |
| FinOps | `/finops` | Budgets, prévisions, ROI |
| Governance | `/governance` | Policy Center |
| Memory Center | `/memory` | Préférences user + knowledge tenant |
| Experiments | `/experiments` | Tests A/B actifs |

**Lancement :**
```bash
# Terminal 1 — backend
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765

# Terminal 2 — portail
cd portal && npm install && npm run dev
# → http://localhost:3000
```

Le portail proxy les appels API vers le backend via `next.config.js`.

---

## 10. SDKs

### Python (`sdk/python/tokenforge_v2/`)

```python
from tokenforge_v2 import TokenForgeClient

with TokenForgeClient(tenant_id="acme", user_id="alice") as client:
    print(client.dashboard())
    print(client.finops_roi())
    route = client.route_request("Mon long prompt...", model="gpt-4o")
    response = client.chat_completions(
        messages=[{"role": "user", "content": "Hello"}],
        model="gpt-4o",
    )
```

### Node.js (`sdk/node/`)

```javascript
import { TokenForgeClient } from './sdk/node/index.js';

const client = new TokenForgeClient({ tenantId: 'acme', userId: 'alice' });
const roi = await client.finopsRoi();
const route = await client.routeRequest('Mon prompt...', 'gpt-4o');
```

---

## 11. Référence API v2

### Dashboard exécutif

```bash
curl http://127.0.0.1:8765/api/v2/dashboard \
  -H "X-Tenant-ID: default" -H "X-User-ID: dsi"
```

Retourne : finops, roi, prompts, budget_alerts, anomalies, cache, résumés mémoire.

### Liste complète des endpoints

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/v2/health` | Santé plateforme v2 |
| POST | `/api/v2/auth/token` | Obtenir JWT |
| GET | `/api/v2/dashboard` | Vue DSI consolidée |
| GET | `/api/v2/memory/user/profile` | Profil utilisateur |
| PUT | `/api/v2/memory/user/profile` | Modifier profil |
| GET | `/api/v2/memory/user/export` | Export RGPD |
| DELETE | `/api/v2/memory/user/profile` | Suppression profil |
| GET | `/api/v2/memory/user/summary` | Résumé profil |
| GET | `/api/v2/memory/tenant/knowledge` | Knowledge base tenant |
| POST | `/api/v2/memory/tenant/terms` | Ajouter terme |
| PUT | `/api/v2/memory/tenant/terms/{cat}/{term}/validate` | Valider terme |
| POST | `/api/v2/memory/learn` | Apprentissage auto |
| POST | `/api/v2/memory/retrieve` | Contexte mémoire |
| GET | `/api/v2/prompts/inventory` | Inventaire prompts |
| GET | `/api/v2/prompts/top` | Top prompts |
| GET | `/api/v2/prompts/similarity` | Doublons & clusters |
| POST | `/api/v2/prompts/diff` | Comparer 2 prompts |
| POST | `/api/v2/prompts/explain` | Explicabilité |
| GET | `/api/v2/finops/summary` | Résumé coûts |
| GET | `/api/v2/finops/forecast` | Prévisions |
| GET | `/api/v2/finops/roi` | ROI net |
| GET | `/api/v2/finops/anomalies` | Anomalies |
| GET/POST | `/api/v2/finops/budgets` | Budgets |
| GET | `/api/v2/finops/alerts` | Alertes budget |
| GET/POST | `/api/v2/governance/policies` | Politiques |
| POST | `/api/v2/governance/evaluate` | Évaluer politique |
| GET | `/api/v2/governance/audit` | Journal audit |
| GET | `/api/v2/governance/compliance` | Check conformité |
| POST | `/api/v2/gateway/route` | Routage prédictif |
| GET | `/api/v2/gateway/circuit-breaker` | État circuit breaker |
| GET | `/api/v2/gateway/cache` | Stats cache |
| GET | `/api/v2/observability/metrics` | Métriques |
| GET | `/api/v2/observability/prometheus` | Export Prometheus |
| GET/POST | `/api/v2/experiments` | A/B tests |

---

## 12. Configuration & déploiement

### Mode développement (local)

```bash
git clone https://github.com/m4554y46/TokenForgev2
cd TokenForgev2
pip install -r requirements.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
```

### Mode production (Docker)

```bash
docker-compose up -d
# API : http://localhost:8765
# PostgreSQL : 5432 | Redis : 6379 | Qdrant : 6333
```

### Tests

```bash
python -m unittest backend.spc.tests       # 149 tests — régression SPC v1
python -m unittest tests.test_v2_platform # Tests plateforme v2
```

### Documentation complémentaire

| Document | Contenu |
|----------|---------|
| [README.md](../README.md) | Vue d'ensemble v1 + v2 |
| [GUIDE_UTILISATION.md](../GUIDE_UTILISATION.md) | Guide utilisateur desktop |
| [docs/adr/](./adr/) | Décisions d'architecture |
| [TECHNIQUES_COMPRESSION.md](../TECHNIQUES_COMPRESSION.md) | Pipeline SPC détaillé |
| [SPECS_LLM_GRAY_ZONE.md](../SPECS_LLM_GRAY_ZONE.md) | Couche 2 Gray Zone |

---

*TokenForge Intelligence Platform v2 — MIT License*
