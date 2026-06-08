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
- 3 compression modes: Light (-20-55%), Balanced (-3.8% to +13.8% on 50w+), Aggressive (-35-70%)
- Pipeline: Sanctuary → lang detect → cancellation → purge → dedup → fragment → classify → IR build + scoring → compress → validate → build → reinject
- Catégories (6) + Documents (24 formats) + Dashboard KPI
- Audit complet (~50+ issues) réalisé et corrigé en juin 2026

## Audit Corrections Applied (Juin 2026)
### Backend
| Fichier | Correctifs |
|---|---|
| `utils.py` | Clé AES aléatoire persistée (`~/.tokenforge/.key`), fallback machine, `InvalidToken` explicite |
| `prompt_optimizer.py` | ReDoS JSON → pattern borné ; tous regex précompilés dans `__init__` ; `re.escape()` sur triggers cancellation ; déduplication `tool_words_en` ; fillers/connectors précompilés |
| `app.py` | `shell=True` retiré ; silent except → `logging.warning` ; coût ratio output 30% |
| `document_analyzer.py` | Setext heading dedupliqué ; `_key_sentences` O(n²)→O(n) ; détection registre via regex alternance précompilée |
| `document_router.py` | Analyzer + extensions set en cache (module-level singletons) ; import `REGISTER_KEYWORDS` déplacé en haut |

### Frontend
| Fichier | Correctifs |
|---|---|
| `index.html` | CSP sans `unsafe-eval` + `object-src: none` + `base-uri: self` ; nav `<div>`→`<button>` ARIA ; duplicate Documents supprimé ; toast `aria-live="polite"` |
| `renderer.js` | Debounce 400ms `onSimPromptChange` ; empty catches → `console.warn` ; `escapeHtml` sur `v.label` ; MutationObserver mort retiré ; Escape key modaux ; focus automatique inputs modaux |
| `style.css` | `--border-color`→`--border` ; `.agressive`→`.aggressive` |

## Remaining (Low Priority)
- Refactor `innerHTML` → DOM API sécurisée (`renderer.js`)
- Lazy loading des views + pagination historique
- Vérification CVE des dépendances (`pip-audit`)

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
