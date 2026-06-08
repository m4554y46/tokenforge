# LLM Gray Zone — Specs pour Petit Modèle Local

## Objectif
Coupler un petit LLM local (<2B params, ~6-8GB RAM, CPU + GPU light) pour traiter les **zones grises** que le pipeline SPC ne peut pas résoudre par règles seules.

## Zones Grises Identifiées

### 1. Ambiguïté Sémantique
- **Problème** : Deux phrases structurellement identiques mais sens opposé (ex: "Tous sauf X" vs "Tous, sauf X" — la virgule change tout).
- **Pipeline rate** : Rules ne peuvent pas lever l'ambiguïté.
- **Solution LLM** : Demander au LLM de trancher en 1-2 tokens ("INCLUDE" / "EXCLUDE").

### 2. Compression Contextuelle Fine
- **Problème** : KOMPRESS supprime des tokens à l'échelle locale, mais ne comprend pas quand un mot anodin porte une charge implicite cruciale (ex: "négligemment" dans un récit).
- **Pipeline rate** : Le token head de KOMPRESS n'a pas de vue pragmatique.
- **Solution LLM** : Classifier chaque chunk comme "compressible" ou "protégé" via prompting.

### 3. Hallucination après Compression
- **Problème** : La compression peut inverser le sens d'une relation causale.
  - Original : "X n'était pas présent, donc Y est parti."
  - Comprimé (mal) : "X absent → Y parti" (perte de l'aspect temporel).
- **Pipeline rate** : Les règles de négation + temporal catch 80%, pas 100%.
- **Solution LLM** : Valider que les relations causales/temporelles sont préservées.

### 4. Détection de Registre / Ton
- **Problème** : "Could you please" vs "Give me" — même sens, registre différent.
- **Pipeline rate** : Actuellement, le lexical compressor uniformise.
- **Solution LLM** : Taguer le registre en entrée (5 labels) et le préserver en sortie.

### 5. Restauration de Contexte Elliptique
- **Problème** : Après compression agressive, le texte peut devenir télégraphique et ambigu.
  - Comprimé : "user wants feature X. deadline Friday."
  - Sens original : "Le client demande la fonctionnalité X, et il nous faut la livrer pour vendredi."
- **Pipeline rate** : Aucun mécanisme de reconstruction sémantique après compression.
- **Solution LLM** : Ré-expansion minimale du texte compressé avant livraison.

---

## Architecture Proposée

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│  SPC Output  │───▶│ Gray Zone    │───▶│ Validated     │
│  (comprimé)   │    │  LLM Refine  │    │  Output       │
└─────────────┘    └──────────────┘    └──────────────┘
                           │
                    ┌──────┴──────┐
                    │  Router     │
                    │  (6 задач)  │
                    └─────────────┘
```

Le LLM est appelé uniquement si :
1. Le score de confiance du pipeline est < 0.85
2. La compression ratio > 50% (mode Aggressive+)
3. Le type de texte est GENERAL ou MEETING (haute ambiguïté)

---

## Modèles Recommandés

| Modèle | Paramètres | RAM (CPU) | RAM (GPU 4-bit) | Avantage |
|---|---|---|---|---|
| **Phi-3-mini-4k-instruct** | 3.8B | ~8GB | ~2.5GB | Meilleur rapport qualité/taille, instruct fine-tuned |
| **Qwen2.5-1.5B-Instruct** | 1.5B | ~4GB | ~1.2GB | Très léger, bon en anglais, instruct |
| **Llama-3.2-1B-Instruct** | 1B | ~3GB | ~0.8GB | Ultra-léger, vocab limité |
| **SmolLM2-1.7B-Instruct** | 1.7B | ~4GB | ~1.2GB | Spécialisé instruction following |

**Recommandation** : Phi-3-mini (priorité) ou Qwen2.5-1.5B (fallback si RAM < 6GB).

---

## Prompts par Zone Grise

### Zone 1 — Désambiguïsation
```
### Instruction
You are an ambiguity resolver for a prompt compression pipeline.
Given a compressed sentence, determine if it has semantic ambiguity.
Reply with exactly one word: "CLEAR" or "AMBIGUOUS".

### Input
{compressed_sentence}

### Output
```

### Zone 2 — Protection Intelligente
```
### Instruction
Given a chunk of text, classify each word as KEEP or REMOVE.
KEEP = word carries essential meaning or context.
REMOVE = word can be safely dropped without losing meaning.
Reply as a JSON list of {word, label}.

### Input
{chunk}

### Output
```

### Zone 3 — Validation Causale
```
### Instruction
Compare original and compressed text.
If the causal/temporal relations in the original are preserved in the compressed version, reply "PASS".
If any relation is inverted or lost, reply "FAIL: {description}".

### Original
{original}

### Compressed
{compressed}

### Output
```

### Zone 4 — Registre
```
### Instruction
Classify the register/tone of this text as one of:
- FORMAL (professional, polite)
- NEUTRAL (informative, objective)
- INFORMAL (casual, conversational)
- URGENT (imperative, time-sensitive)
- TECHNICAL (jargon, precise)

Reply with just the label.

### Input
{text}

### Output
```

### Zone 5 — Ré-expansion
```
### Instruction
You are a text restorer. Given a highly compressed prompt, expand it slightly
to make it grammatically complete and unambiguous, adding at most 20% more tokens.
Preserve all original information. Do NOT add new instructions.

### Input
{compressed}

### Output
```

---

## Intégration Technique

### Backend (`app.py`)
```python
_llm_instance = None
_llm_lock = _threading.Lock()

def _get_llm():
    global _llm_instance
    if _llm_instance is None:
        with _llm_lock:
            if _llm_instance is None:
                from backend.spc.llama_cpp import LlamaCpp
                _llm_instance = LlamaCpp()
    return _llm_instance

@app.get("/api/llm/status")
def llm_status():
    """Vérifie la présence du fichier .gguf sans charger le modèle."""
    llm = _get_llm()
    return {"available": os.path.isfile(llm.model_path or ""), "model": llm.model_path}

@app.post("/api/llm/refine")
async def llm_refine(req: LLMRefineRequest):
    """Route pour appel LLM zone grise."""
    zone = zone_map.get(req.zone, GrayZone.CAUSAL_VALIDATION)
    llm = _get_llm()
    router = GrayZoneRouter(llm=llm)
    refined, meta = router.refine(text=req.text, original=req.original, zone=zone, force=True)
    return {"refined": refined, "zone": req.zone, "meta": meta, "llm_available": True}
```

### Gray Zone Router (`backend/spc/gray_zone.py`)
```python
class GrayZoneRouter:
    def __init__(self, llm: Optional[LlamaCpp] = None):
        self.llm = llm
        self._cache: OrderedDict = OrderedDict()  # LRU 1000 entrées, TTL 1h
        self._user_profiles: Dict[str, UserProfile] = {}

    def refine(self, text, original, zone, force=False):
        zone_cfg = ZONE_PROMPTS[zone]
        # Format ChatML pour compatibilité Phi-3
        prompt = (
            "<|system|>\n" + zone_cfg["system"] + "<|end|>\n"
            "<|user|>\n" + user_content + "<|end|>\n"
            "<|assistant|>\n"
        )
        result = self.llm.generate(prompt=prompt, ...)
        ...
```

### LlamaCpp Wrapper (`backend/spc/llama_cpp.py`)
```python
class LlamaCpp:
    def __init__(self, model_path=None, n_ctx=4096, n_threads=4):
        self.model_path = model_path or self._find_model()
        ...

    def generate(self, prompt, max_tokens, temperature, stop):
        """Génération avec cache LRU."""
        ...

    def chat(self, messages, max_tokens, temperature, stop):
        """Chat completion via create_chat_completion, fallback raw generation."""
        ...
```

### Frontend (`renderer.js`)
- Toggle "Affinage LLM local" (id: `refineLlmToggle`) dans les options avancées
- `checkLlmStatus()` appelé périodiquement via `setInterval(checkBackendStatus, 10000)`
- Badge `LLM` sur les résultats passés par la Couche 2
- Champ `refine_with_llm` envoyé dans la requête `POST /api/optimize`

### Cache
- Cache LRU 1000 entrées avec TTL 1h
- Clé = hash MD5(text + original + zone.value + user_id)
- Cache partagé entre appels API et optimisation batch

---

## État Actuel
- ✅ Pipeline SPC 18 phases opérationnel
- ✅ KOMPRESS + LLMLingua-2 natif
- ✅ 5 modes UI (Light → Industrial)
- ✅ Barre progression temps réel
- ✅ Semantic chunk filter (Stage 3)
- ✅ Quality validation (Stage 2)
- ✅ **Implémentation LLM gray zone activée** — Phi-3-mini-4k-instruct Q4_K_M (~2.4 GB) téléchargé et fonctionnel
- ✅ **Intégration Phi-3-mini via llama-cpp-python** (singleton thread-safe, cache LRU)
- ✅ **5 zones grises opérationnelles** — tests unitaires validés

### Détails d'implémentation

**Modèle :** `phi-3-mini-4k-instruct-q4.gguf` (Q4_K_M) dans `backend/spc/models/`
- `llama-cpp-python` v0.3.28 (pre-built wheel, CPU seulement)
- Contexte : 4096 tokens (n_ctx=4096)
- Inférence CPU, ~2.5 GB RAM

**Architecture :**
- `LlamaCpp` wrapper avec deux backends : python bindings (prioritaire) → subprocess `llama-cli` (fallback)
- Singleton `_get_llm()` dans `app.py` — lazy-loaded, thread-safe (verrouillage)
- `GrayZoneRouter` avec cache LRU 1000 entrées, TTL 1h
- Prompts formatés en ChatML (`<|system|>` / `<|user|>` / `<|assistant|>`) pour compatibilité Phi-3

**Endpoints :**
- `GET /api/llm/status` — vérifie l'existence du fichier `.gguf` (ne charge pas le modèle)
- `POST /api/llm/refine` — exécute une inférence sur une zone grise spécifique

**Frontend :**
- Toggle "Affinage LLM local" dans les options avancées
- Badge `LLM` sur les résultats passés par la Couche 2
- `checkLlmStatus()` appelé périodiquement pour afficher le statut en temps réel

**Fichiers modifiés pour l'activation :**
| Fichier | Changement |
|---|---|
| `backend/app.py` | Singleton `_get_llm()`, endpoints LLM, passage de l'instance partagée |
| `backend/spc/llama_cpp.py` | n_ctx=4096, méthode `chat()`, cache LRU |
| `backend/spc/gray_zone.py` | ChatML template, `compressed` variable dans les prompts |
| `backend/prompt_optimizer.py` | Paramètre `_llm_instance` partagé |
| `frontend/renderer.js` | `refine_with_llm` dans la requête, badge LLM |
| `frontend/index.html` | Toggle "Affinage LLM local" |
| `frontend/style.css` | Styles `.badge-llm`, `.llm-toggle-row` |
| `requirements.txt` | `llama-cpp-python` ajouté |
