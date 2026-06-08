# TokenForge - AI Prompt Optimizer & Token Saver

**Optimisez vos prompts LLM, réduisez vos coûts jusqu'à 75%+.**

TokenForge est une application desktop qui analyse, optimise et compresse vos prompts LLM via un pipeline SPC (Semantic Prompt Compression) à 6 profils et 18 phases. Elle tourne entièrement en local (zéro dépendance cloud) avec des modèles de compression neuronaux embarqués.

## Fonctionnalités

- **Pipeline SPC complet** : 18 phases, 6 profils (Safe, Light, Balanced, Aggressive, Max, Industrial)
- **Semantic chunk filter** (Stage 3) : chunk → MiniLM embed → cosinus score → drop low-relevance
- **Quality validation** (Stage 2) : cosine similarity original vs compressé, contenu critique, spans protégés
- **2 moteurs neuronaux embarqués** : KOMPRESS (ModernBert, 8192 tokens) + LLMLingua-2 (XLM-RoBERTa/BERT) — fallback automatique
- **Compression intelligente** : contenu protégé (code, LaTeX, JSON, URLs), détection de langue (FR/EN), 24 formats de documents
- **Import de documents** : PDF, DOCX, PPTX, XLSX, CSV, JSON, XML, HTML, Markdown, images (OCR), code source et plus
- **Optimisation via IA externe** : utilisez Claude 4, GPT-4o ou Gemini 2.5 Pro pour optimiser vos prompts
- **Simulateur de coûts** : comparez le coût d'un prompt sur tous les modèles (OpenAI, Anthropic, Google, Mistral, Meta)
- **Historique complet** : toutes les optimisations sont stockées localement (SQLite)
- **Barre de progression temps réel** : pourcentage + phase + ETA pendant l'optimisation
- **Dashboard KPI** : statistiques, économies, répartition par mode
- **Templates** : créez et réutilisez des prompts
- **Interface dark mode** : design moderne, professionnel
- **100% local** : vos données restent sur votre machine

## Modes de compression

| Mode | Moteur | Réduction | Description |
|---|---|---|---|---|
| Safe | rule-based | 10-20% | Protection + exact dedup + structural cleanup |
| Light | rule-based | 15-25% | + Suppression bruit conversationnel |
| Balanced | rule-based | 25-40% | + Restructuration logique, near-dedup MinHash |
| Aggressive | KOMPRESS ⤑ LLMLingua-2 | 40-60% | + Semantic chunk filter + KOMPRESS neural + règles |
| Max | KOMPRESS ⤑ LLMLingua-2 | 45-65% | + KOMPRESS neural + semantic chunk + quality validation |
| Industrial | KOMPRESS ⤑ LLMLingua-2 | 50-75% | Production-grade : KOMPRESS + semantic chunk + quality + rules |

## Pipeline SPC (18 phases)

```
Ingestion → Protection → Semantic Chunk Filter → Parse → IR → Constraint
→ Negation → Exact Dedup → Near Dedup → Discourse → Structural → Lexical
→ Logical → Temporal → Example Reduction → Neural (KOMPRESS ⤑ LLMLingua-2)
→ Reconstruction → Validation → Quality → Metrics
```

## Prérequis

- **Node.js 18+** ([nodejs.org](https://nodejs.org))
- **Python 3.11+** ([python.org](https://python.org))
- **pip** (inclus avec Python)

## Installation rapide

### 1. Cloner le projet

```bash
git clone https://github.com/m4554y46/tokenforge
cd tokenforge
```

### 2. Installer les dépendances Python

```bash
pip install -r requirements.txt
```

### 3. Installer les dépendances Node

```bash
npm install
```

### 4. Télécharger les modèles de compression (optionnel — 7 GB)

```bash
python backend/spc/download_models.py
```

Sans téléchargement, le pipeline utilise le fallback rule-based. Les modèles sont chargés en local `files_only=True` dès qu'ils sont présents dans `backend/spc/models/`.

### 5. Lancer en mode développement

```bash
npm start
```

Le backend démarre automatiquement sur `http://127.0.0.1:8765`.

## Structure du projet

```
tokenforge/
├── main.js                     # Point d'entrée Electron
├── preload.js                  # Bridge Electron sécurisé
├── package.json                # Configuration Node/Electron
├── requirements.txt            # Dépendances Python
├── AGENTS.md                   # Notes de développement
├── .gitignore
├── backend/
│   ├── app.py                  # API FastAPI (endpoints REST + progress async)
│   ├── prompt_optimizer.py     # Optimiseur de prompts (3 niveaux + SPC)
│   ├── document_analyzer.py    # Analyseur de documents (24 formats)
│   ├── document_router.py      # Routes API documents (upload/compress)
│   ├── token_counter.py        # Compteur de tokens (tiktoken)
│   ├── models.py               # Définitions des modèles LLM
│   ├── database.py             # SQLite (historique, clés, templates)
│   ├── utils.py                # Chiffrement AES-256
│   └── spc/                    # Semantic Prompt Compression engine
│       ├── pipeline.py         # Orchestrateur 18 phases
│       ├── profiles.py         # 6 profils de compression
│       ├── llmlingua2.py       # Moteur LLMLingua-2 natif
│       ├── kompress.py         # Moteur KOMPRESS natif (ModernBert)
│       ├── protection.py       # Détection code/LaTeX/JSON/URLs
│       ├── parser.py           # Analyse syntaxique
│       ├── ir.py               # Information Retrieval (TF-IDF)
│       ├── discourse.py        # Relations discursives
│       ├── constraint.py       # Contraintes et négations
│       ├── lexical.py          # Compression lexicale
│       ├── structural.py       # Compression structurelle
│       ├── dedup.py            # Déduplication exacte + MinHash
│       ├── negation.py         # Préservation des négations
│       ├── example_reducer.py  # Réduction d'exemples
│       ├── metrics.py          # Métriques de compression
│       ├── ingestion.py        # Prétraitement entrée
│       ├── cli.py              # Interface CLI
│       ├── validator.py        # Validation post-compression
│       ├── reconstruction.py   # Reconstruction finale
│       └── tests/              # 149 tests unitaires
│           ├── bench_comprehensive.py  # Benchmark 45 combinaisons
│           └── ...
├── frontend/
│   ├── index.html              # Interface utilisateur SPA
│   ├── style.css               # Styles dark mode
│   └── renderer.js             # Logique frontend
└── assets/                     # Icônes et ressources
```

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   Electron (Node.js)                     │
│  ┌─────────────┐          ┌───────────────────────────┐ │
│  │  main.js     │          │  frontend/                │ │
│  │  (process)   │◄──IPC──►│  index.html               │ │
│  │              │          │  renderer.js              │ │
│  └──────┬───────┘          │  style.css                │ │
│         │                  └───────────┬───────────────┘ │
│         │  spawn                       │ HTTP + polling   │
│         ▼                              ▼                 │
│  ┌──────────────────────────────────────────────────────┐│
│  │              Python FastAPI (port 8765)               ││
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ││
│  │  │ token_   │ │prompt_   │ │document_ │ │database │ ││
│  │  │ counter  │ │optimizer │ │analyzer  │ │(SQLite) │ ││
│  │  └──────────┘ └────┬─────┘ └──────────┘ └─────────┘ ││
│  │                     │                                 ││
│  │  ┌──────────────────▼──────────────────────────────┐ ││
│  │  │         SPC Pipeline (18 phases)                │ ││
│  │  │  Sanctuary → IR → Compression → Validation      │ ││
│  │  │  KOMPRESS ⤑ LLMLingua-2 (fallback auto)        │ ││
│  │  └─────────────────────────────────────────────────┘ ││
│  └──────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────┘
```

## Utilisation

### Optimisation de prompts

1. Lancez l'application
2. Collez votre prompt dans la zone de texte
3. Sélectionnez le **modèle cible** (GPT-4o, Claude, Gemini, etc.)
4. Choisissez la **catégorie** (ou laissez l'auto-détection)
5. Cliquez sur **Optimiser** — la barre de progression s'affiche
6. Comparez les 5 versions proposées (Light → Industrial)
7. Copiez ou utilisez la version choisie

### Import de documents

1. Allez dans l'onglet **Documents**
2. Importez un fichier (PDF, DOCX, PPTX, XLSX, etc.)
3. Choisissez le **mode de compression** et la **catégorie**
4. Cliquez sur **Compresser**
5. Visualisez la prévisualisation originale/compressée

### Compression des modes

| Mode | Dans l'UI | Pour document |
|---|---|---|
| Light | ✓ | ✓ |
| Balanced | ✓ | ✓ |
| Aggressive | ✓ | ✓ |
| Max | ✓ | ✓ |
| Industrial | ✓ | ✓ |

### Configuration des clés API

Les clés API sont nécessaires pour utiliser l'optimisation via LLM externe (OpenAI, Anthropic, Google). Vous pouvez les configurer :
- Depuis l'onglet **API Keys** dans l'application
- Directement depuis l'écran d'optimisation en sélectionnant un fournisseur

Les clés sont chiffrées et stockées localement (chiffrement AES-256 via `cryptography`).

## Build pour production

### Windows (.exe)

```bash
build.bat
```

### macOS (.dmg) / Linux (.AppImage)

```bash
chmod +x build.sh
./build.sh
```

Les packages de distribution seront créés dans le dossier `dist/`.

## Développement

### Commandes utiles

```bash
# Lancer le backend seul (debug)
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765 --reload

# Lancer l'app Electron en mode dev
npm start

# Tests SPC (149 tests)
python -m unittest backend.spc.tests

# Benchmark complet (45 combinaisons profiles × catégories)
python backend/spc/tests/bench_comprehensive.py

# Benchmark KOMPRESS vs LLMLingua-2
python backend/spc/tests/bench_kompress_vs_llmlingua.py

# Télécharger les modèles
python backend/spc/download_models.py

# Build Windows
npm run build:win
```

## Techniques de compression

Voir [TECHNIQUES_COMPRESSION.md](./TECHNIQUES_COMPRESSION.md), [TECHNIQUES_TEMPLATES.md](./TECHNIQUES_TEMPLATES.md) et [SPECS_LLM_GRAY_ZONE.md](./SPECS_LLM_GRAY_ZONE.md) pour les specs LLM local (Phi-3-mini / Qwen2.5-1.5B) sur les 5 zones grises.

## Licence

MIT

---

*Construit avec Electron, FastAPI, PyTorch, et beaucoup de café.*
