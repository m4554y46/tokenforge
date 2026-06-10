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
8. [Pilier 6 — Adaptive Compression Engine](#8-pilier-6--adaptive-compression-engine-ace)
9. [Observability & Experiments](#9-observability--experiments)
10. [Portail web (Next.js)](#10-portail-web-nextjs)
11. [SDKs](#11-sdks)
12. [Référence API v2](#12-référence-api-v2)
13. [Configuration & déploiement](#13-configuration--déploiement)

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

## 8. Pilier 6 — Adaptive Compression Engine (ACE)

**Objectif :** Choisir dynamiquement le meilleur taux de compression pour
chaque requête LLM, en maximisant la marge économique nette sous contrainte
de qualité.

### Principe

Au lieu d'appliquer un profil fixe (ex. `balanced` à toutes les requêtes),
ACE est un **bandit contextuel** qui apprend la fonction d'utilité :

$$U(r,x) = S(r,x) \cdot TF_{share} - C_{TF}(r) - [1 - g(r,x)] \cdot C_{fail}$$

et choisit $r^* = \arg\max U(r,x)$, avec la possibilité de ne pas compresser
($r=0$) si l'utilité est négative.

### Les 5 couches d'ACE

| Couche | Fichier | Description | Originalité |
|--------|---------|-------------|-------------|
| **Quality Model** | `models/quality_model.py` | LightGBM qui prédit $P(qualité \mid x, r, s)$ | Pseudo-labels depuis signaux, ONNX export |
| **Cell State** | `state.py` | Mémoire $(tenant, cluster, task, length, model, rate) \to qualité$ | LRU 10k, cold-start embeddings |
| **Exploration KG** | `exploration.py` | Knowledge Gradient : explore si l'info peut changer $r^*$ | Pas de ε-greedy, pas d'UCB |
| **Attribution** | `attribution.py` | Cause du signal : compression vs LLM vs user vs contexte | Bayésienne à 4 causes |
| **Embeddings** | `embeddings.py` | Factorisation SVD $contextes \times taux$ | Cold-start par comportement, pas par sémantique |

### `backend/ace/decider.py`

**Rôle :** Moteur de décision principal. Reçoit les features, lit les cellules,
calcule l'utilité, décide d'explorer ou non, et retourne le profil choisi.

**Fonctions :**

| Fonction | Description |
|----------|-------------|
| `decide(features, force_profile, contract_age_days, tenant_allows_exploration)` | Retourne `(profile, was_exploration, rate)` |
| `compute_utility(rate, token_count, price, cell, features)` | Calcule $U(r,x)$ |
| `is_valid(rate, utility, token_count, price, cell, features)` | Vérifie contraintes (qualité ≥ 0.80, client savings ≥ $0.001) |
| `on_response(...)` | Enregistre la requête + session après compression |
| `on_next_request(session_id, user_id, tenant_id, current_prompt, previous_features, previous_rate)` | Détecte signaux, attribue cause, met à jour cellule |

**Décision détaillée /api/v2/ace/explain :**
```json
{
  "features": { "task_type": "analytique", "specificity": "domain_jargon", ... },
  "token_count": 250,
  "token_price": 0.000005,
  "explanations": [
    { "profile": "aggressive", "rate": 0.60,
      "expected_quality": 0.94, "n_samples": 45,
      "savings_usd": 0.000750, "cost_tf": 0.00030,
      "risk_usd": 0.00120, "utility": 0.000755, "valid": true },
    ...
  ],
  "recommendation": { "profile": "aggressive", "utility": 0.000755 }
}
```

### `backend/ace/features.py`

**Rôle :** Extrait le contexte de chaque requête en 4 dimensions.

| Feature | Valeurs | Méthode |
|---------|---------|---------|
| `task_type` | `factuel`, `analytique`, `code`, `creatif`, `resume`, `traduction`, `instruction`, `general` | Détection par mots-clés |
| `specificity` | `generic`, `domain_jargon`, `highly_specific` | Ratio de termes spécialisés |
| `length_bucket` | `short`, `medium`, `long`, `very_long` | Seuils : 50, 200, 1000 tokens |
| `user_cluster` | 0–19 (20 clusters) | Hash déterministe du `user_id` |

**Utilisation :**
```python
from backend.ace.features import extract_features
feats = extract_features(prompt, token_count, model="gpt-4o",
                         user_id="alice", tenant_id="acme")
# → {"task_type": "analytique", "specificity": "domain_jargon",
#     "length_bucket": "medium", "user_cluster": 7, ...}
```

### `backend/ace/state.py`

**Rôle :** Persistance et cache des cellules d'état.

**Classe `CellState` :**

| Attribut | Type | Défaut | Description |
|----------|------|--------|-------------|
| `rate` | float | requis | Taux de compression (0.0–0.75) |
| `quality_sum` | float | 0.0 | Somme pondérée des qualités observées |
| `n_samples` | float | 0.0 | Nombre d'échantillons (poids) |
| `n_explorations` | int | 0 | Requêtes en mode exploration |
| `expected_quality` | float | calculée | `quality_sum / n_samples` (ou fallback) |

**Fonctions principales :**

| Fonction | Description |
|----------|-------------|
| `read_cell(tenant, cluster, task, length, model, rate)` | Lit une cellule (LRU cache, 10k entries) |
| `read_cells_for_context(tenant, cluster, task, length, model)` | Lit toutes les cellules pour un contexte |
| `write_cell(cell)` | Écrit/merge une cellule en DB |
| `record_request(...)` | Enregistre la requête dans `ace_requests` |
| `record_session(...)` | Enregistre dans `ace_sessions` |

**Tables SQL :**

| Table | Colonnes | Rôle |
|-------|----------|------|
| `ace_states` | `tenant_id, user_cluster, task_type, length_bucket, model, rate, quality_sum, n_samples, n_explorations` | Cellules d'état |
| `ace_requests` | `id, tenant_id, user_id, session_id, task_type, specificity, length_bucket, user_cluster, model, provider, profile_chosen, rate_actual, tokens_original, tokens_compressed, latency_ms, was_exploration, signals_json, created_at` | Historique des requêtes |
| `ace_sessions` | `session_id, tenant_id, user_id, prompt_hash, prompt_preview, response_hash, profile_chosen, created_at` | Sessions de chat |

### `backend/ace/signals.py`

**Rôle :** Détecte les signaux comportementaux entre requêtes consécutives.

| Signal | Déclencheur | Fenêtre |
|--------|-------------|---------|
| `reformulation` | Token overlap ≥ 0.65 entre requête $N$ et $N+1$ | 30 secondes |
| `continuation` | Nouvelle requête sans overlap fort, même session | 60 secondes |

**Fonction :**
```python
from backend.ace.signals import detect_signals
signal = detect_signals(session_id, user_id, tenant_id, current_prompt)
# → SignalResult(reformulation=True, continuation=False,
#                 quality_proxy=0.3, confidence=0.85)
```

### `backend/ace/models/quality_model.py`

**Rôle :** LightGBM probabiliste qui prédit la qualité préservée.

**Architecture des features (80–120 dimensions) :**
- One-hot encodings : task (8), specificity (3), length (4), cluster (20), model (~10)
- Scalars : rate, log(token_count), rate×model interactions
- Avec signaux : quality_proxy, reformulation, continuation, confidence

**Fonction :**
```python
from backend.ace.models.quality_model import get_model
qm = get_model()
q = qm.predict(features, signals)  # → [0, 1]
```

**Pseudo-labels (entraînement) :**

| Condition | Label |
|-----------|-------|
| Reformulation sans continuation | 0.3 (échec probable) |
| Continuation sans reformulation | 0.7 (succès probable) |
| Aucun signal | 0.5 (incertain) |
| Reformulation + continuation | 0.9 (contradictoire) |

**API :**
- `GET /api/v2/ace/train` — déclenche l'entraînement
- `GET /api/v2/ace/status` — indique `quality_model_available: true/false`

### `backend/ace/exploration.py`

**Rôle :** Décide s'il faut explorer un taux alternatif (Knowledge Gradient).

**Formule :**
$$KG_j = \sigma_j \cdot \phi(\Delta_j/\sigma_j) + |\Delta_j| \cdot \Phi(|\Delta_j|/\sigma_j) - |\Delta_j|$$

**Fonctions :**

| Fonction | Description |
|----------|-------------|
| `knowledge_gradient(mean_j, var_j, other_means)` | KG pour un bras $j$ |
| `should_explore(rate, expected_quality, variance, cells, token_count, price, contract_age, tenant_allows)` | (bool, KG_value) |
| `pick_exploration_arm(cells, token_count, price, contract_age, tenant_allows)` | Retourne un taux à explorer ou None |

**Conditions d'activation :**
- Contrat ≥ 90 jours (pas d'exploration sur nouveaux clients)
- Tenant autorise l'exploration
- KG > 0 pour au moins un bras alternatif

### `backend/ace/attribution.py`

**Rôle :** Identifie la cause d'un signal pour éviter de pénaliser la
compression pour des erreurs qui ne sont pas de son fait.

**Modèle bayésien :**

$$P(cause = c \mid s, x) = \frac{score_c}{\sum_k score_k}$$

| Cause | Poids | Facteur |
|-------|-------|---------|
| Compression | 0.1 | $1 - g(r,x)$ |
| Modèle LLM | 0.4 | $1 - reliability(model)$ |
| Utilisateur | 0.3 | $1 - user\_history\_quality$ |
| Contexte | 0.2 | $\min(complexité, 0.5) / 0.5$ |

**Classe `AttributionResult` :**

| Attribut | Description |
|----------|-------------|
| `cause` | `"compression"`, `"model"`, `"user"`, `"context"`, `"unknown"` |
| `confidence` | Score normalisé [0, 1] |
| `is_compression_failure` | True si cause = compression ET reformulation |
| `details` | Dict des scores par cause |

**Règle de mise à jour :**
```python
def should_update_quality(attribution):
    if attribution.is_compression_failure: return True
    if cause == "model" and confidence > 0.7: return False
    if cause == "user" and confidence > 0.6: return False
    return True  # cas ambigus
```

### `backend/ace/sanctuary.py`

**Rôle :** Détecte le contenu protégé (code, JSON, LaTeX, tableaux markdown,
YAML) dans le prompt et plafonne le taux de compression max autorisé pour
éviter la corruption.

**Seuils :**

| Ratio protégé | Taux max | Profil max |
|:---|---:|:---|
| > 30 % | 0.15 | safe |
| > 15 % | 0.25 | light |
| > 5 % | 0.40 | balanced |

**Fonctions :**

| Fonction | Description |
|----------|-------------|
| `detect_protected_blocks(text)` | Liste des blocs détectés (type, start, end) |
| `protected_ratio(text)` | Fraction du texte protégé [0, 1] |
| `max_safe_rate(text)` | Taux max autorisé (1.0 = pas de limite) |

**Intégration :** Appelé dans `decider.decide()` avant l'énumération des taux.
Les taux > `sanctuary_max_rate` sont exclus de l'ensemble des candidats.

### `backend/ace/judge.py`

**Rôle :** Évaluateur qualité basé sur GPT-4o qui compare une réponse
compressée à une réponse de référence et produit un score de qualité [0, 1].

**Classe `QualityJudge` :**

| Méthode | Description |
|---------|-------------|
| `evaluate(prompt, response_a, response_b)` | Score unique via GPT-4o |
| `evaluate_batch(pairs)` | Batch (séquentiel) |
| `is_available()` | True si clé API OpenAI configurée |
| `get_stats()` | Stats latence |

**Critères d'évaluation (5 dimensions) :**
1. Exactitude factuelle (faits, chiffres, dates)
2. Complétude (points clés préservés)
3. Cohérence (raisonnement logique)
4. Fidélité (pas de contradiction)
5. Style (ton, niveau de détail)

**Fallback :** Sans clé API, retourne 0.85 (score par défaut).

### `backend/ace/dashboard.py`

**Rôle :** Agrège les métriques qualité ACE depuis `ace_states` et
`ace_requests` pour le dashboard DSI.

**Endpoint :** `GET /api/v2/ace/quality-dashboard?days=7`

**Retourne :**

| Champ | Description |
|-------|-------------|
| `summary` | Stats globales (cells, quality, savings) |
| `by_profile` | Qualité moyenne par profil de compression |
| `by_task_type` | Qualité moyenne par type de tâche |
| `alerts` | Alertes automatiques (qualité basse, bypass ratio, tâche dégradée) |

### `backend/ace/onboarding.py`

**Rôle :** Calculateur de ROI interactif pour prospects. Analyse un prompt
saisi par l'utilisateur et projette les économies potentielles pour chaque
profil de compression ACE.

**Endpoint :** `GET /api/v2/ace/onboarding?prompt=...&model=...&monthly_requests=...`

**Retourne :**

| Champ | Description |
|-------|-------------|
| `prompt_analysis` | Type de tâche, longueur, ratio protégé, taux max Sanctuary |
| `by_profile` | Chaque profil : économies, coût TF, net mensuel/annuel, ROI % |
| `recommendation` | Profil recommandé (net mensuel max) |
| `annual_projection` | Projection annuelle agrégée |

### `backend/ace/embeddings.py`

**Rôle :** Cold-start pour les cellules avec < 5 échantillons.

**Principe :** Factorisation SVD de la matrice $contextes \times taux$
où $M_{ij} = g(r_j, x_i)$. L'embedding d'un contexte capture comment il
**répond à la compression**, pas de quoi il parle.

**Fonctions :**

| Fonction | Description |
|----------|-------------|
| `cold_start_quality(features, rate)` | Qualité estimée via k-NN (k=5) ou None |
| `is_available()` | True si l'entraînement a été fait |
| `fit()` | Entraînement SVD depuis ace_states |
| `save(path)` | Sauvegarde U, V en .npy |

### `backend/ace/train.py`

**Rôle :** Pipeline d'entraînement unifié, exécutable via `python -m backend.ace.train`.

```bash
python -m backend.ace.train
# → Trains quality model + embeddings + exports ONNX
# → Nécessite ≥ 500 lignes avec signals_json non vide
```

**Phases :**
1. Charge les données de `ace_requests` (min_samples paramétrable)
2. Génère les pseudo-labels depuis les signaux
3. Entraîne le QualityModel (LightGBM)
4. Exporte en ONNX (~2 MB)
5. Entraîne les embeddings de compressibilité (SVD)
6. Sauvegarde U, V en .npy

### API ACE

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/v2/ace/status` | GET | Stats globales (cells, requests, taux exploration, qualité modèle disponible) |
| `/api/v2/ace/cells` | GET | Liste des cellules (filtrable par task_type, min_samples) |
| `/api/v2/ace/train` | GET | Déclenche l'entraînement (quality model + embeddings) |
| `/api/v2/ace/explain` | GET | Décompose l'utilité par profil pour un prompt donné |
| `/api/v2/ace/quality-dashboard` | GET | Dashboard qualité agrégé (summary, by_profile, by_task, alerts) |
| `/api/v2/ace/onboarding` | GET | Calculateur ROI interactif pour un prompt |

### Diagramme de flux

```
Requête API
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 0. Sanctuary : detect_protected_blocks(prompt)               │
│    → sanctuary_max_rate (plafonne les candidats)             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│ 1. extract_features(prompt) → task, specificity, etc │
│ 2. read_cells_for_context(...) → g(r,x) pour 6 taux  │
│ 3. Filtrer taux > sanctuary_max_rate                  │
│ 4. compute_utility(r,x) pour chaque taux              │
│ 5. is_valid(r, U, ...) → filtre les taux non rentables│
│ 6. pick_exploration_arm(...) → KG > 0 ?               │
│ 7. argmax U(r,x) → (profile, rate)                    │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
                    Compression SPC
                           │
                           ▼
                    Réponse LLM + enregistrement
                           │ (requête suivante)
                           ▼
┌──────────────────────────────────────────────────────┐
│ 8. detect_signals(session, user, tenant, prompt)     │
│ 9. attribute(features, rate, signals) → cause        │
│10. should_update_quality(attribution) ?               │
│11. update_cell(...) → g(r,x) += δ                    │
└──────────────────────────────────────────────────────┘
                           │ (batch, offline)
                           ▼
┌──────────────────────────────────────────────────────┐
│ Quality Judge : compare réponse compressée vs ref     │
│ → score qualité pour entraînement du modèle           │
└──────────────────────────────────────────────────────┘
```

### Modèle de données

```
ace_states (cellules)
┌────────────────────────────────────────────────┐
│ tenant_id │ cluster │ task │ length │ model │ r │
│ quality_sum │ n_samples │ n_explorations         │
│ PK: (tenant_id, cluster, task, length, model, r)│
└────────────────────────────────────────────────┘

ace_requests (historique)
┌────────────────────────────────────────────────┐
│ id │ tenant_id │ user_id │ session_id           │
│ task_type │ specificity │ length_bucket         │
│ user_cluster │ model │ provider                 │
│ profile_chosen │ rate_actual                    │
│ tokens_original │ tokens_compressed             │
│ latency_ms │ was_exploration                    │
│ signals_json (nullable)                         │
│ created_at                                      │
└────────────────────────────────────────────────┘

ace_sessions (sessions)
┌────────────────────────────────────────────────┐
│ session_id │ tenant_id │ user_id                │
│ prompt_hash │ prompt_preview                    │
│ response_hash │ profile_chosen                  │
│ created_at                                      │
└────────────────────────────────────────────────┘
```

---

## 9. Observability & Experiments

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

## 10. Portail web (Next.js)

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

## 11. SDKs

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

## 12. Référence API v2

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
| GET | `/api/v2/ace/status` | Stats ACE globales |
| GET | `/api/v2/ace/cells` | Liste des cellules |
| GET | `/api/v2/ace/train` | Entraînement modèle qualité |
| GET | `/api/v2/ace/explain` | Décomposition utilité par profil |
| GET | `/api/v2/ace/quality-dashboard` | Dashboard qualité agrégé |
| GET | `/api/v2/ace/onboarding` | Calculateur ROI interactif |

---

## 13. Configuration & déploiement

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
python -m unittest tests.test_v2_platform   # 20 tests — plateforme v2
python -m pytest tests/test_ace.py          # 71 tests — ACE (Sanctuary, Judge, Dashboard, Onboarding, E2E)
```

### Documentation complémentaire

| Document | Contenu |
|----------|---------|
| [README.md](../README.md) | Vue d'ensemble v1 + v2 |
| [GUIDE_UTILISATION.md](../GUIDE_UTILISATION.md) | Guide utilisateur desktop |
| [docs/adr/](./adr/) | Décisions d'architecture |
| [TECHNIQUES_COMPRESSION.md](../TECHNIQUES_COMPRESSION.md) | Pipeline SPC détaillé |
| [SPECS_LLM_GRAY_ZONE.md](../SPECS_LLM_GRAY_ZONE.md) | Couche 2 Gray Zone |
| [FORMALISATION_MATHEMATIQUE.md](./FORMALISATION_MATHEMATIQUE.md) | Modèle mathématique ACE |
| [CRASH_TEST_ACE.md](./CRASH_TEST_ACE.md) | Résultats crash test ACE |

---

*TokenForge Intelligence Platform v2 — MIT License*
