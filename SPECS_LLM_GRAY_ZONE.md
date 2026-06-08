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
@app.post("/api/llm/refine")
async def llm_refine(request: LLMRefineRequest):
    """Route pour appel LLM zone grise."""
    result = await run_llm_refine(
        text=request.text,
        zone=request.zone,  # "ambiguity" | "protection" | "validation" | "register" | "restore"
        model=request.model,  # "phi3" | "qwen25"
    )
    return {"result": result, "zone": request.zone}
```

### Frontend (`renderer.js`)
- Nouveau toggle "LLM Refine" dans les options avancées
- Badge "LLM" sur les résultats qui ont passé par un LLM
- Indicateur de coût LLM (tokens consommés)

### Cache
- Les résultats LLM sont mis en cache (hash du chunk + zone) pour éviter les appels redondants
- TTL: 1 heure

---

## État Actuel
- ✅ Pipeline SPC 18 phases opérationnel
- ✅ KOMPRESS + LLMLingua-2 natif
- ✅ 5 modes UI (Light → Industrial)
- ✅ Barre progression temps réel
- ✅ Semantic chunk filter (Stage 3)
- ✅ Quality validation (Stage 2)
- ⬜ Implémentation LLM gray zone (cette spec)
- ⬜ Intégration Phi-3-mini via llama.cpp
- ⬜ Tests d'intégration gray zone
