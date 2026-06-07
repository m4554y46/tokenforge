# TokenForge - AI Prompt Optimizer & Token Saver

**Optimisez vos prompts LLM, réduisez vos coûts jusqu'à 70%+.**

TokenForge est une application desktop qui analyse, optimise et simule les coûts de vos prompts pour les modèles de langage (LLMs). Elle tourne entièrement en local et peut utiliser des LLMs externes puissants (Claude, GPT-4o, Gemini) pour une optimisation avancée.

## Fonctionnalités

- **Calcul précis du nombre de tokens** avant envoi (support OpenAI, Claude, Gemini, Mistral, Meta)
- **Optimisation automatique** avec 3 niveaux : Light, Balanced, Agressive
- **Optimisation via IA externe** : utilisez Claude 4, GPT-4o ou Gemini 2.5 Pro pour optimiser vos prompts
- **Optimisation locale** : fallback intégré sans clé API
- **Simulateur de coûts** : comparez le coût d'un prompt sur tous les modèles
- **Historique complet** : toutes les optimisations sont stockées localement (SQLite)
- **Templates** : créez et réutilisez des prompts
- **Interface dark mode** : design moderne, professionnel
- **100% local** : vos données restent sur votre machine

## Prérequis

- **Node.js 18+** ([nodejs.org](https://nodejs.org))
- **Python 3.11+** ([python.org](https://python.org))
- **pip** (inclus avec Python)

## Installation rapide

### 1. Cloner le projet

```bash
git clone <votre-repo>
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

### 4. Lancer en mode développement

```bash
npm start
```

## Structure du projet

```
tokenforge/
├── main.js                 # Point d'entrée Electron
├── preload.js              # Bridge Electron sécurisé
├── package.json            # Configuration Node/Electron
├── requirements.txt        # Dépendances Python
├── .env.example           # Exemple de configuration
├── build.bat              # Script build Windows
├── build.sh               # Script build Unix
├── backend/
│   ├── app.py             # API FastAPI
│   ├── token_counter.py   # Compteur de tokens
│   ├── prompt_optimizer.py # Optimiseur de prompts
│   ├── models.py          # Définitions des modèles
│   ├── database.py        # SQLite (historique, clés, templates)
│   └── utils.py           # Chiffrement des clés
├── frontend/
│   ├── index.html         # Interface utilisateur
│   ├── style.css          # Styles (dark mode)
│   └── renderer.js        # Logique frontend
└── assets/                # Icônes et ressources
```

## Utilisation

### Optimisation de prompts

1. Lancez l'application
2. Collez votre prompt dans la zone de texte
3. Sélectionnez le **modèle cible** (GPT-4o, Claude, Gemini, etc.)
4. Choisissez l'**optimiseur** :
   - *Optimisation locale* (gratuit, basique)
   - *OpenAI / Anthropic / Google* (nécessite une clé API)
5. Cliquez sur **Optimiser**
6. Comparez les 3 versions proposées
7. Copiez ou utilisez la version choisie

### Configuration des clés API

Les clés API sont nécessaires pour utiliser l'optimisation via LLM externe. Vous pouvez les configurer :
- Depuis l'onglet **API Keys** dans l'application
- Directement depuis l'écran d'optimisation en sélectionnant un fournisseur

Les clés sont chiffrées et stockées localement (chiffrement AES via `cryptography`).

## Build pour production

### Windows (.exe)

```bash
build.bat
```

### macOS (.dmg)

```bash
chmod +x build.sh
./build.sh
```

### Linux (.AppImage / .deb)

```bash
chmod +x build.sh
./build.sh
```

Les packages de distribution seront créés dans le dossier `dist/`.

## Développement

### Architecture technique

```
┌─────────────────────────────────────────────┐
│               Electron (Node.js)             │
│  ┌─────────────┐       ┌──────────────────┐ │
│  │  main.js     │       │  frontend/       │ │
│  │  (process)   │◄─────►│  index.html      │ │
│  │              │  IPC  │  renderer.js     │ │
│  │              │       │  style.css       │ │
│  └──────┬───────┘       └────────┬─────────┘ │
│         │                        │           │
│         │  spawn                 │ HTTP      │
│         ▼                        ▼           │
│  ┌─────────────────────────────────────────┐ │
│  │         Python FastAPI (port 8765)       │ │
│  │  ┌──────────┐ ┌──────────┐ ┌─────────┐ │ │
│  │  │ token_   │ │prompt_   │ │database │ │ │
│  │  │ counter  │ │optimizer │ │(SQLite) │ │ │
│  │  └──────────┘ └──────────┘ └─────────┘ │ │
│  └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### Commandes utiles

```bash
# Lancer le backend seul (debug)
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765 --reload

# Lancer l'app Electron en mode dev
npm start

# Build Electron sans rebuild
npx electron-builder --win --x64 --publish=never
```

## Extensions futures

- **Port vers Tauri** : version plus légère (Rust + webview) sans Electron
- **Proxy API** : agrégation et routage intelligent entre les fournisseurs
- **Batch optimization** : optimiser plusieurs fichiers en lots
- **Plugins community** : système de plugins pour ajouter des modèles
- **Export formats** : JSON, CSV, Markdown
- **Intégration IDE** : plugin VSCode, JetBrains
- **Mode CLI** : outil en ligne de commande pour CI/CD
- **Cache intelligent** : mise en cache des résultats d'optimisation
- **Analyse comparative** : benchmark de différents modèles d'optimisation

## Licence

MIT

---

*Construit avec Electron, FastAPI, et beaucoup de café.*
