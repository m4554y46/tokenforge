# Guide d'utilisation complet de TokenForge

> *Un outil desktop pour analyser, optimiser et économiser sur vos prompts pour IA*

---

## Sommaire

1. [Qu'est-ce que TokenForge ?](#1-quest-ce-que-tokenforge)
2. [Installation pas à pas](#2-installation-pas-à-pas)
3. [Premier lancement](#3-premier-lancement)
4. [Interface expliquée](#4-interface-expliquée)
5. [Scénarios de test](#5-scénarios-de-test)
6. [Architecture du projet](#6-architecture-du-projet)
7. [Détail des modules](#7-détail-des-modules)
8. [FAQ](#8-faq)
9. [TokenForge v2 — Plateforme Enterprise](#9-tokenforge-v2--plateforme-enterprise)

---

## 1. Qu'est-ce que TokenForge ?

TokenForge est une application **desktop** (qui tourne sur votre PC) qui vous aide à **réduire le coût des appels aux IA** (ChatGPT, Claude, Gemini, etc.).

**Le problème :** Chaque fois que vous envoyez un prompt à une IA, vous payez en fonction du nombre de "tokens" (morceaux de mots). Un prompt trop long = facture plus élevée.

**La solution :** TokenForge analyse votre prompt et le réécrit de façon plus concise, souvent en gardant le même sens mais avec 30 à 70% de tokens en moins. Moins de tokens = économies.

### Ce que l'application fait concrètement :

- Ça compte le nombre de tokens d'un prompt **avant** de l'envoyer à une IA
- Ça réécrit le prompt en 3 versions optimisées (plus courtes)
- Ça calcule combien vous allez économiser
- Ça simule le coût d'un prompt sur tous les modèles (GPT-4o, Claude, Gemini...)
- Ça garde un historique de toutes vos optimisations

---

## 2. Installation pas à pas

### Prérequis (ce qu'il faut avoir installé sur votre PC)

- **Node.js 18+** → téléchargez-le sur https://nodejs.org (version LTS recommandée)
- **Python 3.11+** → téléchargez-le sur https://python.org (cochez "Add Python to PATH" pendant l'installation)

Pour vérifier si vous les avez déjà, ouvrez un terminal (PowerShell sur Windows) et tapez :
```
node --version
python --version
```
Si des numéros s'affichent, vous êtes prêt.

### Étape 1 : Placer le projet

Dézippez ou copiez le dossier `tokenforge` à un endroit de votre choix (par exemple `C:\Users\VotreNom\tokenforge`).

### Étape 2 : Installer les dépendances Python

Ouvrez un terminal dans le dossier tokenforge et tapez :

```
pip install -r requirements.txt
```

*Cette commande télécharge et installe les bibliothèques Python nécessaires (FastAPI, tiktoken, etc.).*

### Étape 3 : Installer les dépendances Node.js

Toujours dans le même dossier, tapez :

```
npm install
```

*Cette commande télécharge et installe Electron et les outils de build.*

### Étape 4 : Lancer l'application

```
npm start
```

**Ce qui va se passer :**
1. Le terminal va lancer le backend Python (un serveur local)
2. Une fenêtre TokenForge va s'ouvrir
3. En bas à gauche de l'interface, le statut doit passer à "Backend prêt" avec un point vert

> **⚠️ Premier lancement :** Windows Defender peut bloquer le backend Python. Cliquez sur "Autoriser" si une alerte apparaît.

### Arrêter l'application

Fermez simplement la fenêtre TokenForge. Le backend Python s'arrêtera automatiquement.

---

## 3. Premier lancement

Quand vous lancez l'application pour la première fois, voici ce que vous voyez :

```
┌─────────────────────────────────────────────────────────┐
│  ⚡ TokenForge                      ─ □ ×              │
├─────────────┬───────────────────────────────────────────┤
│             │  Optimizer                               │
│  ⚡ Optimizer│  Optimisez vos prompts et réduisez vos   │
│  $ Simulateur│  coûts                                   │
│  🕗 Historique│ ┌──────────────────┬────────────────────┐│
│  🔑 API Keys │ │ Prompt original  │ Résultats          ││
│  📋 Templates│ │ [Modèle cible ▼]  │ [En attente]      ││
│             │ │ [Optimisé par ▼]  │                    ││
│  Backend prêt│ │ ┌──────────────┐ │  ⚡ Prêt à          ││
│  v1.0.0     │ │ │ Collez votre │ │  optimiser          ││
│             │ │ │ prompt ici...│ │                    ││
│             │ │ └──────────────┘ │                    ││
│             │ │ Tokens: 0  Coût: │                    ││
│             │ │ [⚡ Optimiser]   │                    ││
│             └─────────────────────┴────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

---

## 4. Interface expliquée

### Barre latérale gauche (5 onglets)

| Onglet | Icône | À quoi ça sert |
|--------|-------|----------------|
| **Optimizer** | ⚡ | L'écran principal pour optimiser vos prompts |
| **Simulateur** | $ | Comparer le coût d'un prompt sur tous les modèles |
| **Historique** | 🕗 | Retrouver toutes vos optimisations passées |
| **API Keys** | 🔑 | Configurer vos clés pour les optimisations avancées |
| **Templates** | 📋 | Créer et réutiliser des prompts types |

### Écran Optimizer (le principal)

#### Zone "Prompt original"
- **Modèle cible** : Choisissez quel modèle IA vous allez utiliser (GPT-4o, Claude, etc.). Cela permet de compter les tokens et calculer les coûts avec les bonnes règles.
- **Optimisé par** : C'est le moteur qui va réécrire votre prompt. Lisez la section [5. Scénarios de test](#5-scénarios-de-test) pour comprendre les options.
- **Zone de texte** : Collez ou écrivez votre prompt ici.
- **Compteur** : En dessous, vous voyez en temps réel le nombre de tokens et le coût estimé.
- **Bouton "Optimiser"** : Lance l'optimisation.

#### Zone "Résultats"
Après optimisation, vous voyez 3 propositions :

| Version | Effet | Icône |
|---------|-------|-------|
| **Light** 💙 | ~10-15% d'économie, modification légère | Bleu |
| **Balanced** 💚 | ~30-50% d'économie, bon équilibre (recommandé) | Vert |
| **Agressive** 🧡 | ~50-70%+ d'économie, très compressé | Orange |

Chaque version affiche :
- Le nombre de tokens après optimisation
- Le % d'économie
- Le coût estimé
- La liste des modifications effectuées
- Les boutons **Copier** (dans le presse-papier) et **Utiliser cette version** (remet le résultat dans la zone d'édition)

---

## 5. Scénarios de test

### SCÉNARIO A : Test rapide sans clé API (recommandé pour commencer)

**But :** Tester l'application immédiatement, gratuitement.

1. Lancez l'application (voir section 2)
2. Sélectionnez **"Modèle cible"** → `gpt-4o`
3. Laissez **"Optimisé par"** sur `Optimisation locale (gratuit)`
4. Collez ce prompt d'exemple dans la zone de texte :
   ```
   I would like you to please write a very detailed analysis of the impact that artificial intelligence is having on modern healthcare and medicine in the 21st century. Please include information about diagnostics, treatment planning, and patient care. Thank you for your help with this task. I really appreciate your assistance with this comprehensive analysis.
   ```
5. Cliquez sur **⚡ Optimiser**
6. Résultat attendu : vous voyez 3 versions avec des économies de ~15-30%

### SCÉNARIO B : Réécriture intelligente via LLM local (Couche 3)

**But :** Depuis la v2, les profils Aggressive/Max/Industrial utilisent un
**Local LLM Rewriter** (Qwen2.5-1.5B en GGUF, ~1 Go) qui réécrit les phrases entières
de façon condensée mais fluide — au lieu de supprimer des tokens un par un comme KOMPRESS.

> **Prérequis :** Avoir un modèle `.gguf` dans `backend/spc/models/` (voir section [Installation](#2-installation-pas-à-pas)).

1. Lancez l'application — le modèle est détecté automatiquement
2. Sélectionnez un mode Aggressive, Max ou Industrial
3. Cliquez sur **⚡ Optimiser**
4. Résultat : le texte condensé est fluide et grammatical — comparable aux outils web (toolszone)
5. Si aucun modèle `.gguf` n'est détecté, KOMPRESS est utilisé en fallback transparent

**Fonctionnement :** Temperature 0.0, prompt anti-hallucination strict, 100% local,
zéro appel réseau, zéro coût API. Les gates contractuelles (Reconstruction Monitor, Oracle)
restent actives derrière pour valider la qualité.

### SCÉNARIO C : Test du simulateur de coûts

**But :** Voir combien coûte un prompt selon le modèle utilisé.

1. Allez dans l'onglet **Simulateur** (barre latérale)
2. Collez un prompt (même que ci-dessus par exemple)
3. Cliquez sur **$ Calculer**
4. Résultat : un tableau comparatif avec tous les modèles et leurs coûts

### SCÉNARIO D : Optimisation via un vrai LLM (avec clé API)

**But :** Utiliser un modèle IA puissant pour optimiser vos prompts. **Résultats bien meilleurs.**

> **⚠️ Cette méthode consomme des tokens sur votre compte API.** Comptez ~1000-2000 tokens par optimisation.

1. Allez dans l'onglet **API Keys**
2. Entrez une clé API :
   - **OpenAI** : Allez sur https://platform.openai.com/api-keys, créez une clé, collez-la
   - **Anthropic (Claude)** : Allez sur https://console.anthropic.com/, créez une clé
   - **Google (Gemini)** : Allez sur https://aistudio.google.com/apikey, créez une clé
3. Cliquez sur **Sauver** pour chaque clé ajoutée
4. Retournez dans l'onglet **Optimizer**
5. Dans **"Optimisé par"**, choisissez votre fournisseur (OpenAI, Anthropic ou Google)
6. Un nouveau menu apparaît : choisissez le modèle d'optimisation (GPT-4o, Claude 4 Sonnet, etc.)
7. L'interface vous confirme que la clé est bien configurée
8. Cliquez sur **⚡ Optimiser**
9. Résultat attendu : économies de **40-70%**, modifications beaucoup plus intelligentes

### SCÉNARIO E : Tester l'historique

**But :** Voir que toutes vos optimisations sont sauvegardées.

Après quelques optimisations (scénarios A ou C), allez dans l'onglet **Historique**.
Vous voyez la liste de toutes les optimisations avec la date, le modèle, le % d'économie.
Vous pouvez **Charger** un résultat ou le **Supprimer**.

### SCÉNARIO E : Créer et utiliser un template

**But :** Sauvegarder un prompt récurrent pour le réutiliser.

1. Allez dans l'onglet **Templates**
2. Cliquez sur **+ Nouveau**
3. Donnez un nom (ex: "Analyse de code") et une catégorie (ex: "Coding")
4. Écrivez un prompt type dans la zone de contenu
5. Cliquez sur **Créer**
6. Pour utiliser le template : retournez dans **Optimizer**, le template apparaît dans la liste déroulante en haut de la zone de texte

---

## 6. Architecture du projet

TokenForge est composé de **deux programmes qui tournent ensemble** :

```
┌─────────────────────────────────────────────────────────┐
│                    VOTRE ORDINATEUR                      │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐│
│  │                  ELECTRON (Node.js)                  ││
│  │                                                      ││
│  │  ┌──────────────┐    ┌──────────────────────────┐   ││
│  │  │  main.js     │───►│  Interface utilisateur   │   ││
│  │  │  (processus  │    │  - index.html            │   ││
│  │  │   principal) │    │  - style.css             │   ││
│  │  │              │    │  - renderer.js           │   ││
│  │  └──────┬───────┘    └───────────┬──────────────┘   ││
│  │         │                        │                   ││
│  │         │    Démarre             │ Appels HTTP       ││
│  │         │    le backend          │ (localhost:8765)  ││
│  └─────────┼────────────────────────┼───────────────────┘│
│            │                        │                     │
│            ▼                        ▼                     │
│  ┌─────────────────────────────────────────────────────┐│
│  │                  PYTHON (FastAPI)                    ││
│  │                                                      ││
│  │  Serveur local qui tourne sur http://127.0.0.1:8765 ││
│  │                                                      ││
│  │  Reçoit les requêtes de l'interface et répond       ││
│  │                                                      ││
│  │  ┌──────────┐ ┌──────────┐ ┌────────────┐          ││
│  │  │token_    │ │prompt_   │ │database.py │          ││
│  │  │counter.py│ │optimizer │ │(SQLite)    │          ││
│  │  └──────────┘ └──────────┘ └────────────┘          ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### Communication entre les deux

1. **Au démarrage :** main.js (Electron) lance le serveur Python automatiquement
2. **Pendant l'utilisation :** L'interface (renderer.js) envoie des requêtes HTTP au serveur Python
3. **Quand on ferme :** Electron arrête proprement le serveur Python

### Schéma de données

```
Fichier tokenforge.db (SQLite, stocké à la racine)
├── optimization_history → Historique des optimisations
├── api_keys → Clés API (chiffrées)
└── templates → Templates utilisateur
```

---

## 7. Détail des modules

### Fichiers de configuration (à la racine)

| Fichier | Rôle |
|---------|------|
| `package.json` | Configuration de l'application Electron (nom, version, dépendances, build) |
| `requirements.txt` | Liste des bibliothèques Python nécessaires |
| `.env.example` | Exemple de fichier d'environnement (optionnel) |
| `main.js` | Point d'entrée de l'application : crée la fenêtre, lance le backend Python |
| `preload.js` | Pont de sécurité entre l'interface et le système (IPC) |
| `build.bat` | Script pour construire un fichier .exe (Windows) |
| `build.sh` | Script pour construire un fichier .dmg (Mac) ou .AppImage (Linux) |

### Backend Python (`backend/`)

| Fichier | Que fait-il ? |
|---------|---------------|
| **`app.py`** | **Le serveur.** C'est un serveur web (FastAPI) qui écoute les requêtes de l'interface. Il définit tous les "points d'entrée" (URLs) comme `/api/count-tokens`, `/api/optimize`, etc. C'est le chef d'orchestre. |
| **`token_counter.py`** | **Le compteur.** Pour les modèles OpenAI, il utilise `tiktoken` (la bibliothèque officielle d'OpenAI) pour compter précisément. Pour les autres modèles (Claude, Gemini, Mistral), il utilise des approximations basées sur le nombre de caractères. |
| **`prompt_optimizer.py`** | **L'optimiseur.** C'est le cœur. Il peut : (1) appeler une API externe (OpenAI, Anthropic, Google) avec un "meta-prompt" très sophistiqué qui dit à l'IA comment compresser, ou (2) utiliser un algorithme local plus simple. Il renvoie toujours 3 versions. |
| **`models.py`** | **Le catalogue.** Liste de 13 modèles avec leurs prix officiels par token (prix d'entrée et de sortie), leur taille de fenêtre de contexte, et leur famille. |
| **`database.py`** | **La mémoire.** Gère la base de données SQLite. Stocke l'historique des optimisations, les clés API (chiffrées), et les templates. Crée les tables automatiquement au premier démarrage. |
| **`utils.py`** | **Les outils.** Contient les fonctions de chiffrement/déchiffrement des clés API (AES-256) et un utilitaire pour masquer les clés dans l'interface. |
| **`__init__.py`** | Fichier vide qui indique à Python que `backend/` est un module. |

### Frontend (`frontend/`)

| Fichier | Que fait-il ? |
|---------|---------------|
| **`index.html`** | **La structure.** Définit tous les écrans de l'interface : barre latérale, zone d'optimisation, résultats, historique, etc. C'est le squelette. |
| **`style.css`** | **Le design.** 950 lignes de styles qui donnent l'apparence : thème sombre, couleurs vert/bleu, animations, mise en page responsive, barre de défilement personnalisée. |
| **`renderer.js`** | **La logique.** ~680 lignes de JavaScript qui gèrent : l'appel à l'API backend, l'affichage des résultats, la navigation entre les onglets, la sauvegarde des clés, l'historique, etc. |

---

## 8. FAQ

### Puis-je utiliser TokenForge sans connexion Internet ?

Oui, partiellement :
- L'**optimisation locale** fonctionne hors ligne
- Le **compteur de tokens** fonctionne hors ligne
- Le **simulateur de coûts** fonctionne hors ligne
- L'**optimisation via LLM externe** nécessite Internet
- Les **clés API** sont stockées localement

### L'application est-elle gratuite ?

L'application elle-même est gratuite et open-source. Si vous utilisez l'optimisation locale, tout est gratuit. Si vous utilisez l'optimisation via API (OpenAI, Anthropic, Google), vous payez les tokens consommés à votre fournisseur d'IA.

### Mes données sont-elles privées ?

Oui. Tout est local :
- Les prompts ne quittent pas votre machine (sauf si vous utilisez l'optimisation via API externe)
- Les clés API sont chiffrées en local
- L'historique est stocké dans un fichier SQLite sur votre disque

### Combien coûte une optimisation via API ?

Comptez environ 1000 à 2000 tokens par optimisation. Exemples :
- Avec GPT-4o : ~$0.003 à $0.006 par optimisation
- Avec Claude 3.5 Sonnet : ~$0.004 à $0.008 par optimisation
- Avec Gemini 2.5 Pro : ~$0.002 à $0.004 par optimisation

### L'optimisation change-t-elle le sens de mon prompt ?

L'optimiseur est conçu pour **préserver le sens et les contraintes critiques**. Les modifications portent sur :
- La suppression de mots inutiles ("please", "I would like you to...")
- La restructuration pour plus de clarté
- La compression des instructions verbeuses

### Pourquoi l'optimisation locale donne-t-elle moins de réduction ?

L'optimisation locale utilise des règles de remplacement de texte (recherche/remplacement de phrases verbeuses). Elle ne comprend pas vraiment le sens du prompt. L'optimisation via API utilise un vrai modèle d'IA qui comprend le sens et peut réécrire intelligemment.

### Que faire si l'application ne se lance pas ?

1. Vérifiez que Python 3.11+ est installé : `python --version`
2. Vérifiez que Node.js 18+ est installé : `node --version`
3. Réinstallez les dépendances : `pip install -r requirements.txt` puis `npm install`
4. Vérifiez qu'aucun autre programme n'utilise le port 8765
5. Ouvrez un ticket avec le message d'erreur

### Comment créer un .exE ?

Exécutez :
```
build.bat    # Windows
```
ou
```
./build.sh   # Mac/Linux
```
Le fichier .exe sera dans le dossier `dist/`.

---

---

## 9. TokenForge v2 — Plateforme Enterprise

> Guide complet : [docs/GUIDE_V2_PLATFORM.md](./docs/GUIDE_V2_PLATFORM.md)

À partir de la v2, TokenForge devient une **plateforme enterprise** en plus de l'application desktop. Tout le contenu des sections 1 à 8 (desktop, SPC, optimisation) reste valable.

### Qui utilise quoi ?

| Profil | Interface recommandée |
|--------|----------------------|
| Utilisateur final | Electron (`npm start`) ou `http://127.0.0.1:8765/` |
| DSI / FinOps | Portail Next.js (`cd portal && npm run dev`) |
| Développeur / intégration | API v2 ou SDK Python/Node |
| Proxy transparent | SDK OpenAI → `base_url=http://127.0.0.1:8765/v1` |

### Portail web (Next.js)

```bash
# Terminal 1 — backend
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765

# Terminal 2 — portail
cd portal
npm install
npm run dev
```

Ouvrez **http://localhost:3000** — modules disponibles :

| Page | Ce que vous y faites |
|------|----------------------|
| **Dashboard** | Vue exécutive : coûts, ROI, alertes budget |
| **Prompt Analytics** | Prompts les plus coûteux et doublons |
| **FinOps** | Budgets, prévisions, économies |
| **Governance** | Politiques (ex. interdire un modèle pour RH) |
| **Memory Center** | Préférences utilisateur + terminologie métier |
| **Experiments** | Tests A/B compression vs original |

### API v2 — premiers appels

Toutes les routes v2 utilisent les headers :
- `X-Tenant-ID` : identifiant entreprise (ex. `default`)
- `X-User-ID` : identifiant utilisateur (ex. `alice`)

**Dashboard DSI :**
```bash
curl http://127.0.0.1:8765/api/v2/dashboard \
  -H "X-Tenant-ID: default" -H "X-User-ID: admin"
```

**Configurer les préférences utilisateur :**
```bash
curl -X PUT http://127.0.0.1:8765/api/v2/memory/user/profile \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: default" -H "X-User-ID: alice" \
  -d '{"updates": {"language": "fr", "tone": "professional", "format": "table"}}'
```

**Voir le ROI :**
```bash
curl http://127.0.0.1:8765/api/v2/finops/roi \
  -H "X-Tenant-ID: default" -H "X-User-ID: admin"
```

**Créer une politique de gouvernance :**
```bash
curl -X POST http://127.0.0.1:8765/api/v2/governance/policies \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: default" \
  -d '{"name": "Interdire GPT-5", "rule_type": "deny_model", "config": {"models": ["gpt-5"]}}'
```

### SDK Python

```python
from tokenforge_v2 import TokenForgeClient

client = TokenForgeClient(tenant_id="default", user_id="alice")
print(client.dashboard())      # Vue DSI
print(client.finops_roi())     # ROI net
client.close()
```

### Ce que chaque pilier v2 apporte

| Pilier | Bénéfice concret |
|--------|------------------|
| **Memory** | L'IA se souvient que vous voulez du français, ton pro, format tableau |
| **Prompt Analytics** | Vous voyez quels prompts coûtent le plus cher |
| **FinOps** | Budgets, alertes, prévisions, ROI prouvable |
| **Governance** | Bloquez des modèles ou forcez la compression par équipe |
| **Smart Gateway** | Cache + compression automatiques sur chaque appel |
| **ACE** | Bandit contextuel + 6 gates contractuelles (PIF, Entropy Gate, Integrity Gate, Oracle, Ensemble Judge, Drift Detector) — compression adaptative avec garanties qualité |
| **Observability** | Métriques Prometheus pour Grafana |
| **Experiments** | Comparez original vs compressé avec des données |

### Déploiement production

```bash
docker-compose up -d
```

Lance PostgreSQL, Redis, Qdrant et l'API. Voir `.env.example` pour la configuration.

### Documentation complémentaire

- [README.md](./README.md) — Vue d'ensemble v1 + v2
- [README_V2.md](./README_V2.md) — Index rapide des modules v2
- [docs/GUIDE_V2_PLATFORM.md](./docs/GUIDE_V2_PLATFORM.md) — Référence complète
- [docs/adr/](./docs/adr/) — Décisions d'architecture

---

> **En résumé :** Lancez `npm start`, collez un prompt, cliquez sur "Optimiser". 
> Pour des meilleurs résultats, ajoutez une clé API (onglet API Keys) et utilisez l'optimisation via IA.
> Pour la plateforme enterprise (DSI, FinOps), utilisez le portail Next.js ou l'API v2 — section 9 ci-dessus.
