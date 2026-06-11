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
de qualité **garantie contractuellement**.

**Principe :** Au lieu d'appliquer un profil fixe (ex. `balanced` à toutes
les requêtes), ACE est un **bandit contextuel augmenté de 6 gates
contractuelles** qui forment une chaîne de garanties avant/pendant/après
la compression :

```
PIF pre-check               →   headroom < 5% → bypass (exemption)
Sanctuary                   →   contenu protégé → plafonnement
UCB Cascade (non-monotone)  →   explore/exploit par UCB décroissant
Entropy Gate (quenching)    →   threshold adaptatif dans KOMPRESS
Integrity Gate (post-check) →   4 vérifications : ratio, entropie, structure, non-vide
Reconstruction Monitor      →   factual_loss < 15%
Oracle (AND-logic)          →   5 dimensions toutes ≥ seuil
Dawid-Skene (consensus)     →   fiabilité estimée des juges
Drift Detector (MMD)        →   surveillance distributionnelle
```

### Fonction d'utilité

$$U(r,x) = S(r,x) \cdot TF_{share} - C_{TF}(r) - [1 - g(r,x)] \cdot C_{fail}$$

ACE choisit le premier taux $r$ dont $U(r,x) > 0$ selon l'ordre UCB
décroissant (cascade non-monotone), avec la possibilité de ne pas compresser
($r=0$) si l'utilité est négative.

### Les 11 couches d'ACE

| # | Couche | Fichier | Description | Nouveauté |
|---|--------|---------|-------------|-----------|
| 1 | **PIF** | `pif.py` | Prompt Information Footprint : estime la compressibilité théorique via entropie + redondance + contenu protégé | ✅ Phase 2 |
| 2 | **Sanctuary** | `sanctuary.py` | Détecte contenu protégé (code, JSON, LaTeX, tableaux, YAML) et plafonne le taux max | Legacy |
| 3 | **UCB Cascade** | `decider.py` | Tri des taux par UCB décroissant (au lieu de linéaire), exploration KG intégrée | ✅ Phase 2 |
| 4 | **Quality Model** | `models/quality_model.py` | LightGBM qui prédit $P(qualité \mid x, r, s)$ | Legacy |
| 5 | **Cell State** | `state.py` | Mémoire $(tenant, cluster, task, length, model, rate) \to qualité$ | Legacy |
| 6 | **Entropy Gate** | `integrity_gate.py` | Floor adaptatif basé sur l'entropie du prompt (remplace le 15% fixe dans KOMPRESS) | ✅ Phase 2 |
| 7 | **Integrity Gate** | `integrity_gate.py` | 4 vérifications post-compression : ratio tokens, effondrement entropique, intégrité structurelle, sortie non-vide | ✅ Phase 2 |
| 8 | **Reconstruction Monitor** | `reconstruction_monitor.py` | Sépare factual_loss (compression artifact) de novelty_gain (créativité LLM) | ✅ Phase 2 |
| 9 | **Quality Oracle** | `oracle.py` | Évaluation AND-logique : chaque dimension (5) doit passer son seuil individuellement | ✅ Phase 2 |
| 10 | **Ensemble Judge** | `ensemble_judge.py` | Dawid-Skene EM : consensus entre 4 juges (GPT-4o, BLEU, ROUGE-L, heuristic) + fiabilité estimée | ✅ Phase 2 |
| 11 | **Drift Detector** | `drift_detector.py` | MMD test avec noyau RBF, fenêtre glissante 100 échantillons, permutation test p-value | ✅ Phase 2 |

---

### `backend/ace/pif.py` — Prompt Information Footprint

**Rôle :** Estimer la compressibilité théorique d'un prompt *avant*
compression, via trois métriques :

- **Entropie empirique** (Shannon, 4-grams) — densité d'information
- **Redondance lexicale** — ratio types/tokens normalisé
- **Contenu protégé** — ratio détecté par Sanctuary

**Formule :**
$$PIF = H_{norm} \cdot (1 - R_{lex}) + P_{protégé} \cdot 0.5$$
$$Headroom = 1.0 - PIF$$

**Classe `PIFResult` :**

| Attribut | Description |
|----------|-------------|
| `headroom` | Taux de compressibilité estimé [0, 1] |
| `entropy` | Entropie empirique normalisée |
| `redundancy` | Redondance lexicale [0, 1] |
| `protected_ratio` | Fraction de contenu protégé |
| `is_compressible` | `headroom >= 0.05` |

**Fonctions :**

| Fonction | Description |
|----------|-------------|
| `compute_footprint(prompt)` | Calcule PIF + headroom |
| `is_incompressible(pif)` | True si headroom < 5% → exemption |

**Intégration proxy :** Appelé dans `proxy.py` avant `decider.decide()`. Si
PIF headroom < 5%, bypass direct sans compression. Compteur
`pif_bypass_count` dans les stats.

---

### `backend/ace/decider.py` — UCB Non-Monotone Cascade

**Rôle :** Moteur de décision avec **cascade UCB** au lieu de la recherche
linéaire par agressivité.

**Principe :** Pour chaque taux candidat, calculer le score UCB :

$$UCB(r) = g(r) + \beta \cdot \frac{\sqrt{Var[g(r)]}}{n_r}$$

Trier les 6 taux par UCB décroissant. Le premier candidat valide ($U > 0$,
qualité $\geq$ 0.80, client savings $\geq$ seuil) est choisi. Cela permet :

- D'**explorer les taux incertains** (variance élevée $=$ priorité haute)
- D'**exploiter les taux connus** (qualité élevée = candidat sérieux)
- De choisir un taux **moins agressif** mais plus fiable si UCB supérieur
  (cascade non-monotone)

**Fonctions :**

| Fonction | Description |
|----------|-------------|
| `decide(features, ...)` | UCB cascade → `(profile, was_exploration, rate)` |
| `compute_utility(rate, ...)` | Calcule $U(r,x)$ |
| `is_valid(rate, ...)` | Vérifie contraintes (qualité ≥ 0.80, client savings) |
| `on_response(...)` | Enregistre la requête + session après compression |
| `on_next_request(...)` | Détecte signaux, attribue cause, met à jour cellule |

**Exploration KG** : même mécanisme que précédemment (Knowledge Gradient),
explore si l'incertitude peut changer $r^*$. Conditions : contrat ≥ 90 jours.

**Sanctuary** : toujours appliqué avant la cascade — les taux >
`sanctuary_max_rate` sont exclus des candidats.

---

### `backend/ace/integrity_gate.py` — Entropy Gate + Integrity Gate

**Rôle :** Deux gates complémentaires qui s'assurent que la compression
produit une sortie valide.

#### Entropy Gate (pre-compression)

Calcule un **threshold dynamique** pour KOMPRESS en fonction de l'entropie
du prompt, remplaçant le 15% fixe antérieur :

$$floor = 0.10 + H_{norm} \cdot 0.20 + P_{protégé} \cdot 0.15$$

- Prompt redondant ($H$ bas) → floor bas → compression agressive
- Prompt dense ($H$ haut) → floor haut → compression conservatrice

**Fonction :** `quenching_threshold(prompt)` → float [0.05, 0.50]

#### Integrity Gate (post-compression)

4 vérifications indépendantes :

| Vérification | Seuil | Détecte |
|-------------|-------|---------|
| Token ratio | $|c| / |o| \geq 0.15$ | Vidage complet |
| Entropy collapse | $H_c / H_o \geq 0.20$ | Sortie sans structure |
| Structure integrity | Patterns (code/JSON/YAML) préservés | Fences cassés |
| Non-empty | $len(c) \geq 3$ car. | Sortie vide |

**Fonctions :**

| Fonction | Description |
|----------|-------------|
| `estimate_safe_threshold(prompt)` | Seuil adaptatif pré-compression |
| `validate_compression(original, compressed)` | Post-check → `IntegrityResult` |
| `quenching_threshold(prompt)` | Floor dynamique pour KOMPRESS |

**Intégration :** `validate_compression()` appelé dans `proxy.py` après la
compression. Si échec, fallback vers le texte original + compteur
`integrity_fallback_count`.

---

### `backend/ace/reconstruction_monitor.py` — Reconstruction Monitor

**Rôle :** Sépare la **perte factuelle** (dommage dû à la compression) du
**gain créatif** (nouveauté introduite par le LLM).

**Méthode :**
- Extrait les éléments factuels du prompt original (dates, nombres, emails,
  URLs, entités nommées)
- Compare leur présence dans le prompt compressé → `factual_loss`
- Détecte les marqueurs de nouveauté dans la réponse → `novelty_gain`
- Si `factual_loss > 0.15`, la compression a probablement endommagé le prompt

**Classe `ReconstructionResult` :**

| Attribut | Description |
|----------|-------------|
| `factual_loss` | Perte d'éléments factuels [0, 1] |
| `novelty_gain` | Gain créatif dans la réponse [0, 1] |
| `reconstruction_score` | `1.0 - factual_loss` |
| `is_acceptable` | `factual_loss <= 0.15` |

**Fonctions :**

| Fonction | Description |
|----------|-------------|
| `analyze(original, compressed, ref_response, comp_response)` | Calcule perte/gain |
| `should_retry(result)` | True si factual_loss > 0.15 ET novelty_gain < loss |

**Intégration :** Exécuté en post-réponse dans `proxy.py` (non-streaming).
Log warning si `is_acceptable = False`.

---

### `backend/ace/oracle.py` — Quality Oracle (AND-logic)

**Rôle :** Évaluer la qualité avec une **logique AND** : chaque dimension
doit passer son seuil individuellement. Pas de moyenne — pas de gaming.

**Seuils AND par dimension :**

| Dimension | Seuil | Interprétation |
|-----------|:-----:|----------------|
| Exactitude factuelle | 0.80 | Les faits/chiffres sont préservés |
| Complétude | 0.75 | Tous les points clés sont dans la réponse |
| Cohérence | 0.70 | Le raisonnement est logique |
| Fidélité | 0.85 | Pas de contradiction avec la référence |
| Style | 0.60 | Le ton et le niveau de détail sont similaires |

**Logique :**
$$Oracle = \begin{cases}
1.0 & \text{si } \forall d : score_d \geq seuil_d \\
\min(score_d) & \text{sinon}
\end{cases}$$

**Classe `OracleResult` :**

| Attribut | Description |
|----------|-------------|
| `passed` | AND-logic : toutes les dimensions passent |
| `dimensions` | Scores par dimension |
| `score` | `1.0` si passed, sinon `min(dimensions)` |
| `failure_dimensions` | Liste des dimensions sous seuil |

**Fonctions :**

| Fonction | Description |
|----------|-------------|
| `evaluate(prompt, response_a, response_b)` | Score AND-logic |
| `is_contract_compliant(result)` | `result.passed` |

---

### `backend/ace/ensemble_judge.py` — Ensemble Judge Dawid-Skene

**Rôle :** Agréger les avis de 4 juges via l'algorithme EM de Dawid-Skene
pour obtenir un consensus robuste, avec estimation de la fiabilité de chaque
juge.

**Juges :**

| Juge | Métrique | Fiabilité initiale |
|------|----------|:------------------:|
| GPT-4o | QualityJudge existant | 0.90 |
| BLEU | Précision n-gram (n=1-4, pénalité bréveté) | 0.75 |
| ROUGE-L | F1 basé sur la plus longue sous-séquence commune | 0.70 |
| Heuristic | Jaccard + bigram + length ratio | 0.65 |

**Algorithme Dawid-Skene EM :**

1. **E-step** : estimer la vraie qualité à partir des scores pondérés par
   les fiabilités actuelles
2. **M-step** : mettre à jour la fiabilité de chaque juge (1 - erreur)
3. Itérer jusqu'à convergence ($\Delta < 10^{-4}$, max 20 itérations)

**Classe `DawidSkeneResult` :**

| Attribut | Description |
|----------|-------------|
| `consensus_score` | Score agrégé [0, 1] |
| `judge_reliabilities` | Fiabilité estimée par juge |
| `n_iterations` | Nombre d'itérations EM |
| `converged` | True si convergence atteinte |

**Fonctions :**

| Fonction | Description |
|----------|-------------|
| `evaluate(prompt, response_a, response_b)` | Consensus + fiabilités |
| `get_judge_reliability(name)` | Fiabilité d'un juge spécifique |

**Avantage :** Si un juge donne un score aberrant (ex. BLEU très bas sur
contenu créatif), Dawid-Skene le pondère automatiquement à ~0, le consensus
repose sur les juges fiables.

---

### `backend/ace/drift_detector.py` — Drift Detector MMD

**Rôle :** Détecter le **drift distributionnel** entre le set de calibrage
(entraînement) et les échantillons de production via Maximum Mean
Discrepancy (MMD) avec noyau RBF.

**Méthode :**
- Convertit les features (task, specificity, length, token_count, cluster)
  en vecteurs numériques
- **MMD$^2$** = $K_{XX} + K_{YY} - 2K_{XY}$ (estimateur non-biaisé)
- **Permutation test** (500 itérations) → p-value
- Alerte si MMD > 0.05 ET p-value < 0.05
- Fenêtre glissante : 100 derniers échantillons de production

**Classe `DriftResult` :**

| Attribut | Description |
|----------|-------------|
| `drift_detected` | True si MMD > threshold |
| `mmd_value` | MMD$^2$ observé |
| `p_value` | p-value du test de permutation |
| `window_size` | Nombre d'échantillons de production |

**Classe `DriftDetector` :**

| Méthode | Description |
|---------|-------------|
| `set_calibration(features)` | Définit le set de calibration |
| `record_sample(features)` | Ajoute un échantillon à la fenêtre |
| `detect()` | Test MMD → `DriftResult` ou None |
| `get_status()` | État courant du drift |
| `reset_production_window()` | Vide la fenêtre |

**Intégration :** Activé par `FORGE_DRIFT_ENABLED=1`. Chaque requête
enregistre un sample. Interrogeable via `get_status()` pour le dashboard.

---

### Modules existants (conservés)

Les modules suivants sont inchangés et conservent leur documentation
antérieure. Seules leurs interactions avec les nouveaux modules sont
décrites ici.

| Module | Fichier | Interaction avec les nouvelles gates |
|--------|---------|--------------------------------------|
| **Sanctuary** | `sanctuary.py` | Alimente `pif.py` (protected_ratio) et reste dans le pipeline pré-UCB |
| **Signals** | `signals.py` | Non modifié — toujours appelé entre requêtes consécutives |
| **Quality Model** | `models/quality_model.py` | Non modifié — prédiction qualité avec/sans signaux |
| **Attribution** | `attribution.py` | Non modifié — toujours utilisé pour filtrer les mise à jour de cellules |
| **Exploration KG** | `exploration.py` | Non modifié — intégré dans UCB cascade via `_explore_or_exploit()` |
| **Embeddings** | `embeddings.py` | Non modifié — cold-start pour cellules < 5 échantillons |
| **Dashboard** | `dashboard.py` | Non modifié — agrège depuis `ace_states` et `ace_requests` |
| **Onboarding** | `onboarding.py` | Non modifié — calculateur ROI interactif |
| **Quality Judge** | `judge.py` | Réutilisé par `oracle.py` et `ensemble_judge.py` |

### `backend/ace/features.py` — Feature extraction

**Rôle :** Extrait le contexte de chaque requête en 4 dimensions.

| Feature | Valeurs | Méthode |
|---------|---------|---------|
| `task_type` | 8 valeurs | Détection par mots-clés |
| `specificity` | `generic`, `domain_jargon`, `entity_rich` | Ratio de termes spécialisés |
| `length_bucket` | `short`, `medium`, `long`, `very_long` | Seuils : 50, 500, 2000 tokens |
| `user_cluster` | 0–19 (20 clusters) | Hash déterministe du `user_id` |

### `backend/ace/state.py` — Cell state & persistence

**Rôle :** Persistance et cache des cellules d'état.

**Classe `CellState` :**

| Attribut | Type | Défaut | Description |
|----------|------|--------|-------------|
| `rate` | float | requis | Taux de compression (0.0–0.70) |
| `quality_sum` | float | 0.0 | Somme pondérée des qualités observées |
| `n_samples` | float | 0.0 | Nombre d'échantillons (poids) |
| `n_explorations` | int | 0 | Requêtes en mode exploration |
| `expected_quality` | float | calculée | `quality_sum / n_samples` (ou fallback) |

**Tables SQL :**

| Table | Colonnes | Rôle |
|-------|----------|------|
| `ace_states` | tenant, cluster, task, length, model, rate, quality_sum, n_samples, n_explorations | Cellules d'état |
| `ace_requests` | colonnes historiques + `pif_headroom`, `integrity_passed` | Historique des requêtes |
| `ace_sessions` | session, tenant, user, prompt_hash, response_hash, profile | Sessions de chat |
| `calibration_samples` | tenant, prompt_hash, task, specificity, length, cluster, model, token_count, pif_headroom, features_json | Échantillons de calibration |
| `drift_events` | mmd_value, p_value, n_production, n_calibration, tenant | Historique des drifts |
| `oracle_evaluations` | request_id, passed, score, dimensions_json, failure_dimensions | Résultats Oracle |

### API ACE

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/v2/ace/status` | GET | Stats globales (cells, requests, pif_bypass_count, integrity_fallback_count) |
| `/api/v2/ace/cells` | GET | Liste des cellules |
| `/api/v2/ace/train` | GET | Déclenche l'entraînement (quality model + embeddings) |
| `/api/v2/ace/explain` | GET | Décompose l'utilité par profil pour un prompt donné |
| `/api/v2/ace/quality-dashboard` | GET | Dashboard qualité agrégé |
| `/api/v2/ace/onboarding` | GET | Calculateur ROI interactif |

### Pipeline complet (12 étapes)

```
Requête API
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. PIF (pif.py) : compute_footprint(prompt)                     │
│    → headroom < 5% ? BYPASS + enregistrement                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Sanctuary (sanctuary.py) : max_safe_rate(prompt)             │
│    → sanctuary_max_rate plafonne les candidats                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. extract_features(prompt) → task, specificity, length, cluster│
│ 4. read_cells_for_context(...) → g(r,x) pour 6 taux             │
│ 5. UCB Cascade : tri par UCB décroissant                         │
│ 6. Cascade : premier taux valide (U > 0, qualité ≥ 0.80) gagne  │
│ 7. Exploration KG : exploration si incertitude peut changer r*  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. Compression (SPC + KOMPRESS) avec Entropy Gate :             │
│    quenching_threshold() remplace le 15% fixe                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. Integrity Gate (integrity_gate.py) : validate_compression()  │
│    → Échec ? Fallback original + compteur + log                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
                     Forward upstream LLM
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 10. Reconstruction Monitor (reconstruction_monitor.py)          │
│     → factual_loss, novelty_gain, is_acceptable                 │
│ 11. Oracle (oracle.py) : évaluation AND-logic 5 dimensions      │
│     → failure_dimensions → oracle_failures + log                │
│ 12. enregistrement ACE (on_response) + Drift Detector sample    │
└─────────────────────────────────────────────────────────────────┘
```

### Variables d'environnement (nouvelles)

| Variable | Défaut | Description |
|----------|--------|-------------|
| `FORGE_PIF_ENABLED` | `1` | Active le PIF pre-check |
| `FORGE_INTEGRITY_GATE_ENABLED` | `1` | Active l'Integrity Gate post-check |
| `FORGE_DRIFT_ENABLED` | `0` | Active le Drift Detector (MMD) |

### Nouvelles statistiques proxy

| Stat | Compteur | Description |
|------|----------|-------------|
| `pif_bypass_count` | Incrémenté | Requêtes bypassées par PIF (headroom < 5%) |
| `integrity_fallback_count` | Incrémenté | Compressions rejetées par Integrity Gate |
| `oracle_failures` | Incrémenté | Évaluations Oracle avec une dimension sous seuil |

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
python -m unittest tests.test_v2_platform   # 26 tests — plateforme v2
python -m pytest tests/test_ace.py -v       # 102 tests — ACE (Sanctuary, Judge, Dashboard, Onboarding, E2E, PIF, Integrity Gate, Oracle, Ensemble Judge, Drift Detector, Reconstruction Monitor)
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
