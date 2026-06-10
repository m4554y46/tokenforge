# TokenForge Intelligence Platform v2

**Optimisez vos prompts LLM, réduisez vos coûts jusqu'à 75%+ — et pilotez l'IA à l'échelle entreprise.**

TokenForge est une plateforme complète qui combine :

- **v1 (legacy)** — Application desktop + compression SPC locale, proxy OpenAI, Electron
- **v2 (enterprise)** — Memory Layer, FinOps, Gouvernance, Prompt Analytics, Smart Gateway, Observability

> Documentation v2 détaillée : **[docs/GUIDE_V2_PLATFORM.md](./docs/GUIDE_V2_PLATFORM.md)**

Le cœur reste le pipeline **SPC (Semantic Prompt Compression)** à 6 profils et 18 phases, exécutable entièrement en local avec des modèles neuronaux embarqués et un petit LLM local optionnel pour les zones grises.

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

## TokenForge v2 — Intelligence Platform

| Pilier | Dossier | Ce que ça fait | ROI client |
|--------|---------|----------------|------------|
| **Memory Layer** | `backend/memory/` | Apprend langue, ton, format, terminologie métier | −30% tokens répétitifs |
| **Prompt Intelligence** | `backend/prompts/` | Inventaire, doublons, diff, explicabilité | Cible les prompts les plus coûteux |
| **FinOps** | `backend/finops/` | Coûts, budgets, prévisions, anomalies, ROI | Budget maîtrisé, ROI prouvable |
| **Governance** | `backend/governance/` | Politiques, conformité RGPD/SOC2, audit | Réduit les risques réglementaires |
| **Smart Gateway** | `backend/gateway/` | Routeur prédictif, circuit breaker, cache | Cache hit + compression automatique |
| **Observability** | `backend/observability/` | Métriques, traces, Prometheus | Visibilité type Datadog |
| **Experiments** | `backend/experiments/` | A/B original vs compressé | Décisions data-driven |
| **Portail web** | `portal/` | Dashboard DSI Next.js | Interface enterprise |
| **SDKs** | `sdk/python/`, `sdk/node/` | Intégration programmatique | Adoption rapide |

**API v2 :** `http://127.0.0.1:8765/api/v2` — headers `X-Tenant-ID`, `X-User-ID`  
**L'API v1 (`/api/*`, `/v1/*`) reste 100% compatible** — zéro régression.

```bash
# Dashboard DSI
curl http://127.0.0.1:8765/api/v2/dashboard -H "X-Tenant-ID: default" -H "X-User-ID: admin"

# Portail Next.js
cd portal && npm install && npm run dev   # → http://localhost:3000
```

## ACE — Adaptive Compression Engine

ACE est le **cerveau économique** de TokenForge : il choisit dynamiquement le
meilleur taux de compression pour chaque requête LLM, en maximisant la marge
nette TokenForge sous contrainte de qualité.

### L'idée en une phrase

> Au lieu d'apprendre quel taux de compression fonctionne (approche bandit classique),
> ACE apprend **la perte d'utilité** causée par chaque taux, et n'explore que quand
> l'information peut changer la décision.

### Les 5 couches

| Couche | Fichier | Ce qu'elle fait | Astuce |
|--------|---------|-----------------|--------|
| **Quality Model** | `models/quality_model.py` | Prédit $P(qualité \mid x, r, s)$ via LightGBM | Pseudo-labels depuis signaux comportementaux |
| **Cell State** | `state.py` | Mémoire $(tenant, cluster, task, length, model, rate) \to g(r,x)$ | LRU 10k, cold-start via embeddings |
| **Exploration KG** | `exploration.py` | Knowledge Gradient : explore seulement si ça peut changer $r^*$ | Jamais de ε-greedy |
| **Attribution** | `attribution.py` | Cause du signal : compression vs LLM vs user vs contexte | Empêche le bandit d'apprendre des hallucinations |
| **Embeddings** | `embeddings.py` | Similarité de comportement face à la compression | MiniLM + SVD, cold-start par k-NN |

### Pourquoi c'est malin

1. **Économie réelle** — $U(r) = savings \cdot TF_{share} - cost_{TF} - risk$ ; si $U \leq 0$, on ne compresse pas
2. **Exploration intelligente** — Knowledge Gradient pur, pas de randomisation. L'exploration a un ROI informationnel
3. **Pas de double-peine** — Attribution bayésienne à 4 causes évite de pénaliser la compression pour les erreurs du LLM
4. **Explicable** — Chaque décision se décompose en utilité par profil → idéal pour le dialogue DSI
5. **Robuste** — Bypass ($r=0$) toujours disponible ; désactivable via `FORGE_ACE_ENABLED=0`

### API ACE

```bash
# Statut et stats globales
curl http://127.0.0.1:8765/api/v2/ace/status -H "X-Tenant-ID: default"

# Expliquer une décision (pour le DSI)
curl "http://127.0.0.1:8765/api/v2/ace/explain?prompt=Reduce+costs+by+20%25+in+Q3&user_id=alice" \
  -H "X-Tenant-ID: default"

# Lister toutes les cellules apprises
curl http://127.0.0.1:8765/api/v2/ace/cells -H "X-Tenant-ID: default"

# Lancer l'entraînement du modèle de qualité
curl http://127.0.0.1:8765/api/v2/ace/train -H "X-Tenant-ID: default"
```

Voir **[docs/FORMALISATION_MATHEMATIQUE.md](./docs/FORMALISATION_MATHEMATIQUE.md)** pour la théorie complète.

```
Détail d'une décision ACE :

Profile      Rate   Quality   Savings     Cost_TF    Risk_USD   Utility    Valid
──────────   ────   ───────   ─────────   ────────   ────────   ────────   ─────
max          0.75   0.9200    $0.00938    $0.00050   $0.00160   $0.00071   Yes
aggressive   0.60   0.9400    $0.00750    $0.00030   $0.00120   $0.00075   Yes
balanced     0.40   0.9500    $0.00500    $0.00010   $0.00100   $0.00040   Yes
light        0.25   0.9800    $0.00313    $0.00005   $0.00040   $0.00049   Yes
safe         0.15   0.9900    $0.00188    $0.00001   $0.00020   $0.00035   Yes
bypass       0.00   1.0000    $0.00000    $0.00000   $0.00000   $0.00000   Yes
                              ─────────────────────────────────────────────
                              ➜ aggressive choisi (U = $0.00075/req)
```

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
git clone https://github.com/m4554y46/TokenForgev2
cd TokenForgev2
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
TokenForgev2/
├── main.js, preload.js         # Electron (desktop legacy)
├── frontend/                   # UI v1 (SPA vanilla JS)
├── portal/                     # Portail enterprise Next.js 14
├── sdk/
│   ├── python/tokenforge_v2/   # SDK Python
│   └── node/                   # SDK Node.js
├── docs/
│   ├── GUIDE_V2_PLATFORM.md        # Guide complet v2
│   ├── FORMALISATION_MATHEMATIQUE.md  # Théorie ACE
│   ├── STRATEGIE_COMPRESSION.md    # Stratégie + soutenance
│   ├── PITCH_JURY.md              # Objections jury
│   └── adr/                       # Architecture Decision Records
├── docker-compose.yml          # PostgreSQL + Redis + Qdrant
├── backend/
│   ├── app.py                  # FastAPI v1 + v2
│   ├── config.py               # Configuration centralisée v2
│   ├── core/                   # DB v2, cache, auth, multi-tenant
│   ├── api/v2/router.py        # API Intelligence Platform
│   ├── memory/                 # Pilier 1 — User/Tenant Memory
│   ├── prompts/                # Pilier 2 — Prompt Analytics
│   ├── finops/                 # Pilier 3 — FinOps & ROI
│   ├── governance/             # Pilier 4 — Policies & Compliance
│   ├── gateway/                # Pilier 5 — Smart Gateway
│   ├── observability/          # Métriques & traces
│   ├── experiments/            # A/B testing
│   ├── middleware/proxy.py     # Proxy OpenAI-compatible (v1)
│   ├── spc/                    # Pipeline SPC 18 phases (v1)
│   └── ...                     # Modules legacy (optimizer, documents…)
└── tests/test_v2_platform.py   # Tests plateforme v2
```

## Architecture

```
Clients (SDK / IDE / Electron / Portail Next.js)
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│           FastAPI (port 8765)                                 │
│  /api/* (v1)  ·  /api/v2/* (enterprise)  ·  /v1/* proxy     │
├───────────────────────────────────────────────────────────────┤
│  Gateway v2 ──► Memory ──► FinOps ──► Governance ──► ACE     │
│       │                                                       │
│       ▼                                                       │
│  SPC Pipeline (18 phases) + Gray Zone LLM (optionnel)        │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
  Providers LLM (OpenAI, Anthropic, Gemini, DeepSeek…)
```

Voir [docs/GUIDE_V2_PLATFORM.md](./docs/GUIDE_V2_PLATFORM.md) pour le détail de chaque module v2.

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

# Tests SPC v1 (149 tests — régression)
python -m unittest backend.spc.tests

# Tests plateforme v2
python -m unittest tests.test_v2_platform

# Tests ACE (42 tests — adaptative compression)
python -m unittest tests.test_ace

# Entraînement ACE (quality model + embeddings)
python -m backend.ace.train

# Portail enterprise
cd portal && npm run dev

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

## Documentation

| Document | Contenu |
|----------|---------|
| [docs/GUIDE_V2_PLATFORM.md](./docs/GUIDE_V2_PLATFORM.md) | **Guide complet v2** — chaque module, API, SDK, déploiement |
| [docs/FORMALISATION_MATHEMATIQUE.md](./docs/FORMALISATION_MATHEMATIQUE.md) | Théorie ACE : quality model, KG, attribution, embeddings |
| [docs/STRATEGIE_COMPRESSION.md](./docs/STRATEGIE_COMPRESSION.md) | Stratégie de compression + préparation soutenance |
| [docs/PITCH_JURY.md](./docs/PITCH_JURY.md) | Objections et réponses pour convaincre un jury |
| [GUIDE_UTILISATION.md](./GUIDE_UTILISATION.md) | Guide utilisateur desktop (v1) |
| [TECHNIQUES_COMPRESSION.md](./TECHNIQUES_COMPRESSION.md) | Pipeline SPC détaillé |
| [SPECS_LLM_GRAY_ZONE.md](./SPECS_LLM_GRAY_ZONE.md) | Couche 2 Gray Zone LLM |
| [docs/adr/](./docs/adr/) | Décisions d'architecture v2 |

## Licence

MIT

---

*Construit avec Electron, FastAPI, PyTorch, et beaucoup de café.*
