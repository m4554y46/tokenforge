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
- `backend/prompt_optimizer.py` — Optimizer wrapper with 5 mode versions + progress
- `backend/app.py` — FastAPI routes, async optimization, progress polling
- `frontend/index.html`, `renderer.js`, `style.css` — SPA UI
- `main.js` — Electron main process
- `preload.js` — Electron preload bridge
- `admin/index.html` — Admin console (login: admin/tokenforge, endpoint `/console/`)
- `SPECS_LLM_GRAY_ZONE.md` — Specs for local LLM gray zone resolution

## State at Last Session
- **Pipeline SPC 18 phases** industrialisé : ingestion → protection → **semantic chunk filter** → parse → IR → constraint → negation → exact dedup → near dedup → discourse → structural → lexical → logical → temporal → example reduction → neural (KOMPRESS ⤑ LLMLingua-2 fallback) → reconstruction → validation → **quality check** → metrics
- **KOMPRESS natif** : ModernBertModel + token head + span CNN convolutif, 8192 contexte, 2.3× plus rapide que LLMLingua-2
- **5 modes UI** : Light (rule-based), Balanced (rule-based), Aggressive, Max, Industrial (tous avec neural + semantic chunk + quality)
- **Async + progression temps réel** : polling 400ms, barre avec %, phase, ETA
- **Historique corrigé** : dict→str dans save_optimization, chargement au clic
- **149/149 tests verts**, zéro régression
- **Projet pushé GitHub** : `https://github.com/m4554y46/tokenforge`
- **Semantic chunk filter** : chunk → embed (MiniLM) → score cosinus → drop low-relevance
- **Quality validation** : cosine similarity original vs compressed (seuil 0.55-0.60), critical content preservation, protected span integrity, token ratio

## Commands
```powershell
cd C:\Users\micas\tokenforge
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765  # start backend
npm start              # launch Electron GUI
npm run build:win      # build Windows .exe
```

## Notes
- Port 8765 must be free before starting (stale Python processes block it)
- Electron needs display (won't work from agent CLI)
- French + English prompts both supported
- Zero-regression on code/LaTeX/JSON/units/templates via Sanctuary
- `backend/spc/models/` contient CamemBERT + ModernBERT pour fine-tuning futur
