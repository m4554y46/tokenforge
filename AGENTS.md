# TokenForge — AI Prompt Optimizer

## Project
Desktop app (Electron + Python FastAPI) for optimizing LLM prompts and reducing token costs.
- **Backend**: Python FastAPI on `http://127.0.0.1:8765`
- **Frontend**: Electron SPA (vanilla JS, dark mode)
- **Stack**: Electron 33, Python 3.x, SQLite, AES-256 key encryption, tiktoken
- **Repo**: https://github.com/slegendre-dev/tokenforge

## Key Files
- `backend/prompt_optimizer.py` — All compression logic (6 phases)
- `backend/app.py` — FastAPI routes
- `frontend/index.html`, `renderer.js`, `style.css` — SPA UI
- `main.js` — Electron main process
- `preload.js` — Electron preload bridge
- `admin/index.html` — Console d'administration (login: admin/tokenforge, endpoint `/console/`)
- `TECHNIQUES_COMPRESSION.md` — Full documentation of all compression techniques

## State at Last Session
- All 6 phases of compression complete
- UI bugs fixed: API source indicator (badge), simulator comparison (original vs optimized), save-as-template button in editor
- Backend running and verified (health, optimize, count-tokens all work)
- 3 compression modes: Light (-20-55%), Balanced (-3.8% to +13.8% on 50w+), Aggressive (-35-70%)
- Pipeline: Sanctuary → lang detect → cancellation → purge → dedup → fragment → classify → IR build + scoring → compress → validate → build → reinject

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
- Zero-regression on code/LaTeX/JSON/units via Sanctuary
