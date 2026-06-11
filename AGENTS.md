# TokenForge — Notes de développement

## Project
Plateforme LLM enterprise (v2) + application desktop de compression (v1 legacy).
- **Backend**: Python FastAPI sur `http://127.0.0.1:8765`
- **Frontend v1**: Electron SPA (`frontend/`) — vanilla JS, dark mode
- **Portail v2**: Next.js 14 (`portal/`) — Dashboard DSI
- **Stack**: FastAPI, SQLite/PostgreSQL, Redis (opt), Qdrant (opt), Electron 33, PyTorch
- **Repo**: https://github.com/m4554y46/TokenForgev2

## Documentation
| Fichier | Contenu |
|---------|---------|
| [docs/GUIDE_V2_PLATFORM.md](./docs/GUIDE_V2_PLATFORM.md) | **Référence complète v2** — chaque module, API, SDK |
| [README.md](./README.md) | Vue d'ensemble v1 + v2 |
| [README_V2.md](./README_V2.md) | Index rapide modules v2 |
| [GUIDE_UTILISATION.md](./GUIDE_UTILISATION.md) | Guide utilisateur (desktop + section v2) |
| [docs/adr/](./docs/adr/) | Architecture Decision Records |

## Key Files — v1 (legacy, inchangé)

- `backend/spc/pipeline.py` — Orchestrateur SPC 18 phases
- `backend/spc/kompress.py` — Moteur KOMPRESS (ModernBert)
- `backend/spc/llmlingua2.py` — Fallback LLMLingua-2
- `backend/spc/gray_zone.py` — Gray Zone router (5 zones, cache LRU)
- `backend/spc/llama_cpp.py` — Wrapper llama.cpp (Phi-3-mini)
- `backend/prompt_optimizer.py` — Optimiseur 5 modes + SPC + Gray Zone
- `backend/middleware/proxy.py` — Proxy OpenAI `/v1/chat/completions`
- `backend/app.py` — FastAPI v1 + montage v2
- `frontend/` — UI desktop legacy
- `forge_proxy_demo.py` — Démo SDK proxy

## Key Files — v2 (enterprise)

### Infrastructure
- `backend/config.py` — Configuration (env vars)
- `backend/core/database_v2.py` — Persistance multi-tenant
- `backend/core/cache.py` — Redis / fallback mémoire
- `backend/core/tenant.py` — Contexte X-Tenant-ID / X-User-ID
- `backend/core/auth.py` — JWT + RBAC

### Piliers
- `backend/memory/` — User/Tenant Memory (7 fichiers)
- `backend/prompts/` — Prompt Analytics (inventory, similarity, diff, explain)
- `backend/finops/` — Cost registry, budgets, forecast, anomalies, ROI
- `backend/governance/` — Rule engine, compliance, approval workflows
- `backend/gateway/` — Predictive router, circuit breaker, cache governor
- `backend/observability/hub.py` — Métriques, traces, Prometheus
- `backend/experiments/experiment_manager.py` — A/B testing

### API & UI
- `backend/api/v2/router.py` — Tous les endpoints `/api/v2/*`
- `portal/` — Portail Next.js (Dashboard, FinOps, Memory, Governance…)
- `sdk/python/tokenforge_v2/client.py` — SDK Python
- `sdk/node/index.js` — SDK Node.js
- `tests/test_v2_platform.py` — Tests plateforme v2

## API Surface

| Préfixe | Version | Usage |
|---------|---------|-------|
| `/api/*` | v1 | Optimisation, historique, clés, templates |
| `/v1/*` | v1 | Proxy OpenAI-compatible |
| `/api/v2/*` | v2 | Intelligence Platform enterprise |

## Commands
```powershell
cd C:\Users\michel.assayag-exter\Documents\TokenForgev2

# Backend
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765

# Desktop legacy
npm start

# Portail v2
cd portal && npm run dev

# Tests
python -m unittest backend.spc.tests
python -m unittest tests.test_v2_platform

# Docker prod
docker-compose up -d
```

## ACE — Fichiers clés

- `backend/ace/state.py` — Constantes + `FAILURE_COST_BY_TASK` (9 types) + `get_failure_cost(task_type)` + `MIN_CLIENT_SAVINGS_BY_MODEL` (8 modèles) + `get_min_client_savings(model)` + CellState + DB ops
- `backend/ace/decider.py` — Decision engine: `decide()` → `compute_utility()` → `is_valid()`, utilise `get_failure_cost()` + `get_min_client_savings()` + `max_safe_rate()` (Sanctuary) + **UCB cascade non-monotone**
- `backend/ace/pif.py` — Prompt Information Footprint : entropie + redondance + contenu protégé → headroom, exemption contractuelle si < 5%
- `backend/ace/integrity_gate.py` — Entropy Gate (quenching dynamique) + Integrity Gate (4 vérifications post-check : ratio, entropie, structure, non-vide)
- `backend/ace/oracle.py` — Quality Oracle AND-logic : 5 dimensions seuillées, pas de gaming par moyenne
- `backend/ace/ensemble_judge.py` — Dawid-Skene EM : consensus multi-juge (GPT-4o, BLEU, ROUGE, heuristic) + fiabilité estimée
- `backend/ace/drift_detector.py` — MMD test (noyau RBF) avec fenêtre glissante 100 samples + permutation test
- `backend/ace/reconstruction_monitor.py` — factual_loss (compression) vs novelty_gain (LLM)
- `backend/ace/models/quality_model.py` — LightGBM → pickle, entraîné sur signaux, predict(features, signals) → qualité [0,1]
- `backend/ace/embeddings.py` — SVD embeddings pour cold start k-NN
- `backend/ace/train_seed.py` — Génère 600 requêtes synthétiques + lance l'entraînement (qualité + embeddings)
- `backend/ace/_models/` — Modèles entraînés : `quality_model.pkl`, `embeddings.pkl`
- `backend/ace/sanctuary.py` — Détecteur contenu protégé (code, JSON, LaTeX, tableaux, YAML) → `max_safe_rate()` plafonne la compression
- `backend/ace/judge.py` — QualityJudge GPT-4o : évalue réponse compressée vs référence → score 0-1 (5 dimensions)
- `backend/ace/dashboard.py` — Dashboard qualité : agrégation DB (ace_states, ace_requests) par profil/tâche, alertes
- `backend/ace/onboarding.py` — Calculateur ROI interactif : analyse prompt × volume mensuel → projection financière par profil
- `backend/spc/kompress.py` — KOMPRESS avec Entropy Gate (quenching adaptatif remplace 15% fixe)
- `backend/spc/local_rewrite.py` — Local LLM Rewriter : réécriture de phrases via Qwen2.5 (GGUF), remplace KOMPRESS pour les profils agressifs quand un modèle local est dispo
- `backend/middleware/proxy.py` — Pipeline complet : PIF → Sanctuary → UCB Cascade → Compress + Entropy Gate → Integrity Gate → Forward → Reconstruction Monitor → Oracle → Drift sample
- `crash_test_ace.py` — Test de la frontière de compression (10 prompts, seed cells, décisions ACE)

## API endpoints ACE

| Endpoint | Description |
|----------|-------------|
| `GET /api/v2/ace/status` | Statut ACE (cells, requests, model dispo) |
| `GET /api/v2/ace/cells` | Liste des cellules |
| `GET /api/v2/ace/train` | Déclenche entraînement du modèle qualité |
| `GET /api/v2/ace/explain` | Explication détaillée d'une décision |
| `GET /api/v2/ace/quality-dashboard` | Dashboard qualité agrégé (summary, by_profile, by_task_type, alerts) |
| `GET /api/v2/ace/onboarding` | Calculateur ROI pour un prompt (`?prompt=...&model=...&monthly_requests=...`) |

## Tests ACE

Tests dans `tests/test_ace.py` (102 tests) :
- **TestSanctuary** (8) : détection blocs protégés, plafonnement taux, intégration decider
- **TestQualityJudge** (5) : évaluation qualité, mock GPT-4o, reprise sur erreur, singleton
- **TestQualityDashboard** (5) : agrégation DB, alertes, endpoint
- **TestOnboardingROI** (7) : calculateur ROI, projection financière, Sanctuary respecté
- **TestEndToEndFlow** (4) : pipeline complet features → décision → enregistrement → signal
- **TestPIF** (5) : headroom, entropie, redondance, contenu protégé, exemption
- **TestIntegrityGate** (6) : validation normale, sortie vide, troncature, quenching threshold, safe threshold, structure
- **TestOracle** (4) : AND-logic passed/fails, contract compliant
- **TestEnsembleJudge** (6) : BLEU/ROUGE identique/différent, consensus, stats
- **TestDriftDetector** (5) : samples insuffisants, pas de drift, incrément, status, history
- **TestReconstructionMonitor** (5) : factual_loss identique/avec dates, novelty_gain, should_retry, reconstruction_score

## Session Log

### 2026-06-10 — Sanctuary + Judge + Dashboard + Onboarding + E2E tests

**Sanctuary — détecteur de contenu protégé :**
- `backend/ace/sanctuary.py` : 7 patterns (fenced code, LaTeX display/inline, YAML front matter, markdown tables, XML, JSON blocks)
- Seuils : >30% protégé → max 15%, >15% → 25%, >5% → 40%
- Intégré dans `decider.py` : `max_safe_rate(prompt_text)` filtre les candidats dans `decide()`
- `prompt_text` passé via `features["prompt_text"]` par `proxy.py`
- 8 tests : fenced code, LaTeX, JSON, tableaux, ratio élevé, mixte, pas de contenu, intégration decider

**Quality Judge — évaluateur automatique GPT-4o :**
- `backend/ace/judge.py` : `QualityJudge` classe avec `evaluate(prompt, response_a, response_b)` → score [0,1]
- Prompt système avec 5 critères (exactitude, complétude, cohérence, fidélité, style)
- Fallback 0.85 si pas de clé API OpenAI
- Singleton via `get_judge()`, support batch `evaluate_batch()`, stats de latence
- 5 tests : fallback, parsing JSON, retry, singleton, batch

**Dashboard qualité ACE :**
- `backend/ace/dashboard.py` : agrège `ace_states` + `ace_requests` par profil et type de tâche
- Endpoint : `GET /api/v2/ace/quality-dashboard?days=7`
- Alertes automatiques : qualité basse par profil, bypass ratio >50%, qualité dégradée par tâche
- 5 tests

**Onboarding + ROI calculator :**
- `backend/ace/onboarding.py` : prend un prompt + modèle + volume mensuel → projection par profil
- Endpoint : `GET /api/v2/ace/onboarding?prompt=...&model=...&monthly_requests=...`
- Respecte Sanctuary (contient protégé → taux max limité)
- 7 tests

**End-to-end tests :**
- `TestEndToEndFlow` (4) : cycle complet features → décision → enregistrement → signal, Sanctuary rate limit, quality model update, MIN_CLIENT_SAVINGS respecté
- 71 ACE tests + 20 v2 platform = 91 total, tous passent

### 2026-06-10 — ACE: FAILURE_COST par tâche + qualité model entraîné

**FAILURE_COST dynamique par type de tâche :**
- `backend/ace/state.py` : ajout `FAILURE_COST_BY_TASK` (9 types de $0.002 à $0.025)
- `backend/ace/state.py` : ajout `get_failure_cost(task_type)` → lookup avec fallback global $0.01
- `backend/ace/decider.py` : `compute_utility()` utilise `get_failure_cost(task_type)` au lieu de `FAILURE_COST` global
- Impact crash test : passe de 1/10 à 4/10 prompts compressés (seuil ~1200 tokens pour tâche analytique)

**Modèle de qualité LightGBM entraîné :**
- `backend/ace/train_seed.py` : nouveau fichier — génère 600 requêtes synthétiques avec signaux réalistes
- Entraînement : 600 samples → LightGBM sauvegardé en pickle (`quality_model.pkl`)
- Le modèle apprend : copy+thumbs_up → Q=0.99, reformulation → Q=0.40
- `_update_cell_quality()` utilise déjà le modèle via `_lazy_load_model()` + `predict(features, signals)`
- `_get_quality()` n'utilise PAS le quality model (réservé aux mises à jour post-réponse avec signaux)
- ONNX export non fonctionnel (onnxmltools non installé) — fallback pickle, suffisant pour backend Python

**Corrections :**
- `quality_model.py` : `predict()` utilisait `predict_proba` sur un `LGBMRegressor` → remplacé par `predict()`
- `quality_model.py` : `predict()` n'alignait pas les dimensions features (26 vs 33) → toujours utiliser `_encode_features_with_signals` (zéro si pas de signaux)
- `embeddings.py` : `cold_start_quality()` retourne None si pas de contexte similaire (le caller fait le fallback)
- `tests/test_ace.py` : test embeddings adapté pour ne pas exiger de float quand le contexte n'existe pas

## Crash test — embed

Pour lancer le crash test ACE complet (v1) :
```bash
$env:FORGE_ACE_ENABLED=0; python crash_test_ace.py
```

### 2026-06-11 — Phase 2-3 : 6 gates contractuelles + UCB cascade + batterie 92 prompts

**Nouveaux modules créés :**

| Module | Fichier | Tests |
|--------|---------|-------|
| **PIF** | `backend/ace/pif.py` | 5 (TestPIF) |
| **Integrity Gate** (Entropy Gate + post-check) | `backend/ace/integrity_gate.py` | 6 (TestIntegrityGate) |
| **Quality Oracle** (AND-logic) | `backend/ace/oracle.py` | 4 (TestOracle) |
| **Ensemble Judge** (Dawid-Skene EM) | `backend/ace/ensemble_judge.py` | 6 (TestEnsembleJudge) |
| **Drift Detector** (MMD test) | `backend/ace/drift_detector.py` | 5 (TestDriftDetector) |
| **Reconstruction Monitor** | `backend/ace/reconstruction_monitor.py` | 5 (TestReconstructionMonitor) |

**Fichiers modifiés :**
- `backend/ace/decider.py` : UCB Non-Monotone Cascade (remplace cascade linéaire)
- `backend/spc/kompress.py` : Entropy Gate (quenching adaptatif remplace 15% fixe)
- `backend/middleware/proxy.py` : Pipeline complet PIF → UCB → Integrity → Reconstruction → Oracle → Drift
- `backend/ace/tables.py` : 3 nouvelles tables (calibration_samples, drift_events, oracle_evaluations) + colonnes pif_headroom, integrity_passed
- `backend/ace/state.py` : record_request() accepte pif_headroom et integrity_passed
- `tests/test_ace.py` : 6 nouvelles classes de test (31 tests) → total 102 tests ACE

**Pipeline final :**
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

**Docs mis à jour :**
- `docs/GUIDE_V2_PLATFORM.md` : section ACE complète réécrite (11 couches)
- `README_V2.md` : table ACE avec tous les nouveaux modules
- `README.md` : section ACE réécrite (11 couches), test count 102
- `GUIDE_UTILISATION.md` : ligne ACE dans le tableau des piliers
- `docs/adr/004-ace-phase2-contractual-gates.md` : nouvelle ADR
- `AGENTS.md` : fichiers clés + tests + session log mis à jour

**Tests : 128 passent (102 ACE + 26 v2 platform), batterie 92 prompts fonctionnelle**

**Backend corrigé :**
- `backend/finops/anomaly_detection.py` : ajout `import statistics` manquant (NameError)
- `backend/api/v2/router.py` : taux compression hardcodé 75% → réel via ROI ; appel redondant `_roi.calculate()` factorisé ; ajout endpoints `/finops/trend`, `/finops/top-users`, `/finops/provider-efficiency`
- `backend/finops/cost_registry.py` : nouveaux champs `total_tokens`, `total_requests`, `cost_per_token`, `avg_cost_per_request` ; nouvelles méthodes `get_cost_trend()`, `get_top_users()`, `get_provider_efficiency()`
- Dashboard endpoint enrichi : trend journalier, comparaison période, top users, provider efficiency

**Frontend portail (Next.js 14) :**
- `portal/components/KpiCard.tsx` : ajout `color`, `subtitle`, `trend`, `progress` (barre)
- `portal/components/TrendChart.tsx` : nouveau composant SVG line chart (sans dépendance)
- `portal/app/finops/page.tsx` : réécrit — 10 appels API parallèles, 7 rangées de KPIs :
  1. Financial Pulse (4 KPIs avec couleurs + trends)
  2. Trend chart + Prévisions 3 horizons
  3. Breakdown provider/modèle + Efficiency fournisseur ($/token)
  4. Top utilisateurs + Top prompts coûteux
  5. Anomalies & Dérives + Budgets & Alertes
  6. Recommandations actionnables (insights auto-générés)
  7. Méthodologie de calcul
- `portal/app/page.tsx` (Cockpit Exécutif `/`) : taux TF hardcodé 0.005 → 0.002 ; budget via API réelle (plus state local $500) ; suppression calcul local redondant

**Plugin autosave :**
- Installé : `opencode-autosave-conversation@1.1.0` (npm global)
- Configuré : `opencode.json` avec `"plugin": ["opencode-autosave-conversation"]`
- Sauvegarde auto dans `./conversations/` + backup `~/.conversations/tokenforge/`

## Notes
- Port 8765 doit être libre
- API v1 = zéro régression — ne pas modifier les signatures existantes
- v2 s'ajoute en parallèle via `/api/v2/*`
- DB v1 : `tokenforge.db` (SQLite) — historique, clés, templates
- DB v2 : `tokenforge_v2.db` ou PostgreSQL — mémoire, finops, gouvernance
- Headers v2 : `X-Tenant-ID`, `X-User-ID` sur toutes les routes enterprise
