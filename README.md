# TokenForge - AI Prompt Optimizer & Token Saver

**Optimisez vos prompts LLM, réduisez vos coûts jusqu'à 75%+.**

TokenForge est une application desktop qui analyse, optimise et compresse vos prompts LLM via un pipeline SPC (Semantic Prompt Compression) à 6 profils et 18 phases. Elle tourne entièrement en local (zéro dépendance cloud) avec des modèles de compression neuronaux embarqués et un petit LLM local en option pour les zones grises.

## Fonctionnalités

- **Pipeline SPC complet** : 18 phases, 6 profils (Safe, Light, Balanced, Aggressive, Max, Industrial)
- **Semantic chunk filter** (Stage 3) : chunk → MiniLM embed → cosinus score → drop low-relevance
- **Quality validation** (Stage 2) : cosine similarity original vs compressé, contenu critique, spans protégés
- **2 moteurs neuronaux embarqués** : KOMPRESS (ModernBert, 8192 tokens) + LLMLingua-2 (XLM-RoBERTa/BERT) — fallback automatique
- **Couche 2 — Gray Zone LLM** (optionnel) : petit LLM local (Phi-3-mini / Qwen2.5) pour ambiguïté, protection fine, validation causale, registre, ré-expansion
- **Cache LLM adaptatif** : LRU 1000 entrées, TTL 1h, profils utilisateur avec historique des corrections
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

Tous les modes Aggressive+ peuvent être affinés par la **Couche 2 Gray Zone LLM** (Phi-3-mini) si activé et si le modèle `.gguf` est présent.

## Pipeline SPC (18 phases)

```
Ingestion → Protection → Semantic Chunk Filter → Parse → IR → Constraint
→ Negation → Exact Dedup → Near Dedup → Discourse → Structural → Lexical
→ Logical → Temporal → Example Reduction → Neural (KOMPRESS ⤑ LLMLingua-2)
→ Reconstruction → Validation → Quality → Metrics
```

## Gray Zone LLM (Couche 2 — optionnel)

Un petit LLM local Phi-3-mini (3.8B, ~2.5GB RAM en Q4_K_M, CPU-only) résout les 5 zones grises que les règles+KOMPRESS ne peuvent pas traiter seuls :

| Zone | Problème | Solution LLM |
|---|---|---|
| Ambiguïté | "Tous sauf X" vs "Tous, sauf X" | Classifier CLEAR/AMBIGUOUS |
| Protection fine | Mots anodins à charge implicite | Token-level KEEP/REMOVE contextuel |
| Validation causale | Relations inversées après compression | PASS/FAIL avec description |
| Registre/Ton | Niveau de formalité uniformisé | 5 labels (FORMAL→TECHNICAL) |
| Ré-expansion | Texte télégraphique ambigu | +20% tokens max, préservation sémantique |

Le LLM est appelé uniquement si nécessaire (router + cache LRU 1000 entrées + profils utilisateur). **Zéro appel réseau, zéro coût API.**

### Activation

1. Téléchargez un modèle `.gguf` dans `backend/spc/models/` :
   ```bash
   # Phi-3-mini (recommandé, ~2.4 GB)
   python -c "import requests; r = requests.get('https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf', stream=True); f=open('backend/spc/models/phi-3-mini-4k-instruct-q4.gguf','wb'); [f.write(c) for c in r.iter_content(8192)]"

   # Alternative plus légère : Qwen2.5-1.5B (~0.9 GB)
   # https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF
   ```
2. Le backend détecte automatiquement le fichier `.gguf` au démarrage
3. Dans l'UI, activez le toggle **"Affinage LLM local"** dans les options avancées
4. Le badge **LLM** apparaît sur les résultats passés par la Couche 2

Le LLM est chargé une seule fois en mémoire (singleton thread-safe) et partagé entre toutes les requêtes.

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

Pour activer la Couche 2 Gray Zone LLM, installez aussi :
```bash
pip install llama-cpp-python
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

### 5. Télécharger le LLM Gray Zone (optionnel)

```bash
# Phi-3-mini (recommandé, ~2.4 GB, nécessite ~2.5 GB RAM)
python -c "import requests; requests.get('https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf', stream=True, timeout=30)"

# Alternative : Qwen2.5-1.5B-Instruct (~0.9 GB)
# Placez le fichier .gguf dans backend/spc/models/
```

### 6. Lancer en mode développement

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
│   ├── prompt_optimizer.py     # Optimiseur de prompts (5 modes + SPC + Gray Zone)
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
│       ├── gray_zone.py        # Routeur Couche 2 — 5 zones grises + cache LRU + profils
│       ├── llama_cpp.py        # Wrapper llama.cpp (python bindings + subprocess fallback)
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
│       ├── chunk_semantic.py   # Semantic chunk filter (Stage 3)
│       ├── quality.py          # Quality validation (Stage 2)
│       └── tests/              # Tests unitaires
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
│  │  └──────────────────────┬──────────────────────────┘ ││
│  │                         ▼                            ││
│  │  ┌─────────────────────────────────────────────────┐ ││
│  │  │  Couche 2 — Gray Zone LLM (optionnel)           │ ││
│  │  │  Phi-3-mini → router (5 zones) → cache LRU      │ ││
│  │  │  Ambiguïté / Protection / Validation / Registre  │ ││
│  │  │  / Ré-expansion                                  │ ││
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

# Télécharger le LLM Gray Zone (Phi-3-mini, ~2.4 GB)
python -c "import requests; r=requests.get('https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf', stream=True); [f.write(c) for c in r.iter_content(8192)]" 2>nul

# Vérifier le statut du LLM local
curl http://127.0.0.1:8765/api/llm/status

# Tester une zone grise (validation causale)
curl -X POST http://127.0.0.1:8765/api/llm/refine -H "Content-Type: application/json" -d '{\"text\":\"fox jumps over lazy dog\",\"original\":\"fox jumps over the lazy dog\",\"zone\":\"causal_validation\"}'

# Build Windows
npm run build:win
```

## Techniques de compression

Voir [TECHNIQUES_COMPRESSION.md](./TECHNIQUES_COMPRESSION.md), [TECHNIQUES_TEMPLATES.md](./TECHNIQUES_TEMPLATES.md) et [SPECS_LLM_GRAY_ZONE.md](./SPECS_LLM_GRAY_ZONE.md) pour les specs détaillées du LLM local (Phi-3-mini) et des 5 zones grises.

## Licence

MIT

---

*Construit avec Electron, FastAPI, PyTorch, et beaucoup de café.*
