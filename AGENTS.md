# TokenForge — AI Prompt Optimizer

## Project
Desktop app (Electron + Python FastAPI) for optimizing LLM prompts and reducing token costs.
- **Backend**: Python FastAPI on `http://127.0.0.1:8765`
- **Frontend**: Electron SPA (vanilla JS, dark mode)
- **Stack**: Electron 33, Python 3.x, SQLite, AES-256 key encryption, tiktoken
- **Repo**: https://github.com/m4554y46/tokenforge

## Key Files
- `backend/spc/pipeline.py` — SPC pipeline orchestrator (18 phases)
- `backend/spc/kompress.py` — KOMPRESS neural engine (ModernBert + token head)
- `backend/spc/llmlingua2.py` — LLMLingua-2 native implementation (fallback engine)
- `backend/spc/chunk_semantic.py` — Semantic chunk filter (Stage 3, MiniLM embedding)
- `backend/spc/quality.py` — Quality validation (cosine similarity + integrity checks)
- `backend/spc/profiles.py` — 6 profiles (Safe → Industrial)
- **`backend/spc/gray_zone.py`** — Gray Zone router (5 zones, cache LRU 1000, profils utilisateur)
- **`backend/spc/llama_cpp.py`** — llama.cpp wrapper (python bindings + subprocess fallback, n_ctx=4096)
- `backend/prompt_optimizer.py` — Optimizer wrapper with 5 mode versions + progress + Gray Zone refine
- `backend/app.py` — FastAPI routes, async optimization, progress polling, **LLM singleton** `_get_llm()`
- `frontend/index.html`, `renderer.js`, `style.css` — SPA UI (LLM toggle + badge)
- `main.js` — Electron main process
- `preload.js` — Electron preload bridge
- `admin/index.html` — Admin console (login: admin/tokenforge, endpoint `/console/`)
- `SPECS_LLM_GRAY_ZONE.md` — Specs for local LLM gray zone resolution
- `SPECS_LLM_GRAY_ZONE.md` — Specs for local LLM gray zone resolution (5 zones, prompts, architecture)

## State at Last Session
- **Pipeline SPC 18 phases** : ingestion → protection → semantic chunk filter → parse → IR → constraint → negation → exact dedup → near dedup → discourse → structural → lexical → logical → temporal → example reduction → neural (KOMPRESS ⤑ LLMLingua-2) → reconstruction → validation → quality check → metrics
- **KOMPRESS natif** : ModernBertModel + token head + span CNN, 8192 contexte, 2.3× plus rapide que LLMLingua-2
- **5 modes UI** : Light/Balanced rule-based, Aggressive/Max/Industrial KOMPRESS neural + semantic chunk + quality
- **Async + progression temps réel** : polling 400ms, barre %, phase, ETA
- **Couche 2 Gray Zone LLM activée** : Phi-3-mini-4k-instruct Q4_K_M (~2.4 GB, CPU, ~2.5 GB RAM)
  - 5 zones grises fonctionnelles : ambiguïté, protection fine, validation causale, registre, ré-expansion
  - ChatML template (`<|system|>`/`<|user|>`/`<|assistant|>`) pour compatibilité Phi-3
  - Singleton `_get_llm()` dans app.py évite le rechargement à chaque requête
  - Frontend toggle "Affinage LLM local" + badge `LLM` sur les résultats
  - Endpoints : `GET /api/llm/status` (check fichier, ne charge pas le modèle) + `POST /api/llm/refine`
  - Cache LRU 1000 entrées, TTL 1h, profils utilisateur
- **8 fichiers modifiés** pour l'activation de la Couche 2 : `app.py`, `llama_cpp.py`, `gray_zone.py`, `prompt_optimizer.py`, `renderer.js`, `index.html`, `style.css`, `requirements.txt`
- **Historique corrigé** : `"\n".join(list[dict])` → extraction `description`. `loadHistory()` au clic.
- **Semantic chunk filter** : chunk → embed (MiniLM) → score cosinus → drop low-relevance
- **Quality validation** : cosine similarity original vs compressed (seuil 0.55-0.60), contenu critique, spans protégés, token ratio

## Commands
```powershell
cd C:\Users\micas\tokenforge
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765  # start backend
npm start              # launch Electron GUI
npm run build:win      # build Windows .exe

# Gray Zone LLM
curl http://127.0.0.1:8765/api/llm/status                              # check LLM status
curl -X POST http://127.0.0.1:8765/api/llm/refine -H "Content-Type: application/json" -d '{\"text\":\"...\",\"zone\":\"causal_validation\"}'  # test refine
```

## Notes
- Port 8765 must be free before starting (stale Python processes block it)
- Electron needs display (won't work from agent CLI)
- French + English prompts both supported
- Zero-regression on code/LaTeX/JSON/units/templates via Sanctuary
- `backend/spc/models/` contient CamemBERT + ModernBERT + KOMPRESS + Phi-3-mini GGUF
- LLM singleton (`_get_llm()`) lazy-loaded, thread-safe
