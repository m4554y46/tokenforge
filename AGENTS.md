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

## Notes
- Port 8765 doit être libre
- API v1 = zéro régression — ne pas modifier les signatures existantes
- v2 s'ajoute en parallèle via `/api/v2/*`
- DB v1 : `tokenforge.db` (SQLite) — historique, clés, templates
- DB v2 : `tokenforge_v2.db` ou PostgreSQL — mémoire, finops, gouvernance
- Headers v2 : `X-Tenant-ID`, `X-User-ID` sur toutes les routes enterprise
