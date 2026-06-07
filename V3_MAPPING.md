# V3 Mapping — de l'idéal au réalisable offline

## Principe

Le spec ChatGPT V3 est juste sur le fond mais surestime ce qu'on peut détecter sans LLM.
Je filtre ce qui est *réellement implémentable* en offline déterministe, et je propose une évolution concrète du code V1.

---

## 1. IR enrichie (P6)

### V1 actuelle
```python
role_s, task_s, context_s, constraint_s, output_s, structure_s  # listes de strings
```

### V3 cible — réalisable offline
```python
{
  "tasks": [{"text": "...", "mutations": [], "source_idx": 0}],
  "roles": [{"text": "...", "mutations": [], "source_idx": 1}],
  "audiences": [{"text": "beginners", "source_idx": 2}],
  "tones": ["cynical", "friendly", "academic", "formal"],       # keywords détectables
  "languages": ["en", "fr"],                                     # is_french() déjà fait
  "formats": ["JSON", "CSV", "4 steps", "TikTok script"],       # output_format étendu
  "outputs": [{"spec": "Return only JSON", "source_idx": 3}],
  "constraints": [{"text": "no emojis", "exceptions": ["🚀"], "source_idx": 4}],
  "exceptions": [{"base": "no emojis", "allowed": "🚀"}],
  "conditionals": [{"if": "result > 100", "then": "do X", "else": "do Y", "source_idx": 5}],
  "terminology": [{"term": "X", "must_use": True}],
  "examples": [{"input": "...", "output": "...", "source_idx": 6}],
  "context": [{"text": "...", "importance": 0.7, "source_idx": 7}],
  "mutations": [{"attr": "constraints.count", "old": 100, "new": 200, "marker": "finalement"}],
  "history": [],      # stocke les versions précédentes des attributs mutés
  "warnings": [],     # conflits non résolus, doutes
  "sanctuary": []     # déjà fait
}
```

**Ce qui est nouveau et faisable :**
- `exceptions` : extraites via patterns `(sauf|except|mais|but) (🚀|X)` depuis une clause
- `conditionals` : extraites via `(if|si|when|lorsque|si jamais).*(then|alors).*`
- `tones` : mots-clés (cynique, formel, friendly, drôle, sérieux, bienveillant, pédagogique, technique) extraits des phrases ROLE/CONTEXT
- `terminology` : patterns `(toujours|always) dire X`, `(jamais|never) dire Y`
- `formats` : enrichi avec `(N )?étapes?`, `(N )?steps?`, `tableau`, `article`, `script`, `email`, `slide`
- `mutations` : chaînage des overrides pour garder la trace

---

## 2. Segmentation atomique (P2)

### Problème V1
`split_sentences` coupe sur `(?<=[.!?])\s+` → rate les listes, les `:`, les overrides intra-phrase.

### Solution offline
Un tokenizer à 2 passes :

**Passe 1 — Sanctuary d'abord** (déjà fait)
**Passe 2 — Fragmentation logique**

```python
def fragment(text):
    # 1. Split sur les retours ligne + numéros de liste
    fragments = split_on_list_markers(text)   # "1. item\n2. item" → ["1. item", "2. item"]
    
    # 2. Split sur . ! ? avec protection abréviations (déjà fait)
    fragments = split_sentences(fragments)
    
    # 3. Split sur ":" si suivi d'une énumération
    fragments = split_colon_enum(fragments)   # "format: 1. item 2. item" → ["format:", "1. item", "2. item"]
    
    # 4. Split sur les overrides intra-phrase
    fragments = split_override_clauses(fragments)  # "écris 5 mais en fait 10" → ["écris 5", "mais en fait 10"]
    
    # Résultat : une clause = une intention
    return fragments
```

**Détection override intra-phrase :**
Le marqueur d'override est cherché DANS la phrase après le split sur `. ! ?`.
Si trouvé → couper la phrase en 2 au niveau du marqueur.

```python
OVERRIDE_MARKERS = [
    r'\b(mais\s+en\s+fait\s+non|mais\s+en\s+fait|en\s+fait\s+non)\b',
    r'\b(oublie|oubliez)\s+(ça|ca|cela)\b',
    r'\bnon\s+(en\s+fait|finalement)\b',
    r'\bfinalement\s+non\b',
    r'\battends?[,]\s*(non|en\s+fait)\b',
    r'\bplut[ôo]t\b',
    r'\bscratch\s+that\b',
    r'\bactually\s+no\b',
    r'\bno\s+wait\b',
    r'\bcancel\s+that\b',
    r'\bstrike\s+that\b',
]
```

---

## 3. Résolution des overrides (P4) — version offline

### Principe
Une override modifie un **attribut spécifique**, pas toute la clause.
On track l'état courant de chaque attribut.

```python
class MutationTracker:
    def __init__(self):
        self.state = {}   # attr_name → current_value
        self.history = [] # liste de mutations
    
    def apply_override(self, attr, old_val, new_val, marker, source):
        # Vérifier si la mutation concerne vraiment le même attribut
        if attr in self.state and self.state[attr] != new_val:
            self.history.append({
                "attr": attr, "old": old_val, "new": new_val,
                "marker": marker, "source": source
            })
            self.state[attr] = new_val
            return True
        return False
    
    def resolve(self, ir):
        for mutation in self.history:
            attr = mutation["attr"]
            ir[attr] = mutation["new"]
        return ir
```

### Exemple
```
Input: "10 emails. Actually 5."
→ Clause 1: tasks=[{text: "write emails", count: 10}]
→ Clause 2: mutation {attr: "tasks[0].count", old: 10, new: 5}
→ Résultat: tasks=[{text: "write emails", count: 5}]
```

### Cas partiel vs total
```python
OVERRIDE_TYPES = {
    "replace_value": [r"\d+", r"(N )?étapes?", r"(N )?steps?"],  # chiffre nouveau remplace ancien
    "add_exception": [r"(sauf|except|but|mais)"],                 # ajoute une exception
    "cancel_attribute": [r"(annule|ignore|oublie)"],              # supprime un attribut
    "clarify": [r"(plus précisément|more precisely)"],            # affine sans remplacer
}
```

---

## 4. Détection des conflits (P5) — version offline

### Règle
Un conflit existe ssi **deux valeurs incompatibles portent sur le même attribut**.

```python
def detect_conflicts(ir):
    conflicts = []
    
    for attr in ["formats", "outputs", "languages", "tones"]:
        values = set()
        for item in ir.get(attr, []):
            val = item if isinstance(item, str) else item.get("text", "")
            if val in values:
                conflicts.append({"attr": attr, "values": list(values | {val}), "type": "duplicate"})
            values.add(val)
    
    # Vérifier formats incompatibles
    fmt = set(ir.get("formats", []))
    if "JSON" in fmt and "CSV" in fmt:
        conflicts.append({"attr": "formats", "values": ["JSON", "CSV"], "type": "contradiction"})
    if "table" in fmt and "paragraph" in fmt:
        conflicts.append({"attr": "formats", "values": ["table", "paragraph"], "type": "contradiction"})
    
    # Vérifier langues
    lang = set(ir.get("languages", []))
    if len(lang) > 1:
        conflicts.append({"attr": "languages", "values": list(lang), "type": "contradiction"})
    
    # Vérifier contraintes numériques
    nums = extract_numeric_limits(ir)
    for key, values in nums.items():
        if len(values) > 1:
            unique = set(values)
            if len(unique) > 1:
                conflicts.append({"attr": key, "values": list(unique), "type": "limit_change"})
    
    return conflicts
```

**Ce qu'on ne peut PAS faire offline :**
- Détecter que `"Python (serpent)"` ≠ `"Python (langage)"` — pas de WSD
- Distinguer alternative vs contradiction : `"JSON ou CSV, au choix"` vs `"JSON, pas CSV"` — besoin de modaux

**Fallback :** en cas de conflit non résoluble, stocker les deux valeurs et ajouter un warning.

---

## 5. Scoring d'importance contextuel (P8)

### V1 : poids par type
```python
TASK = 100, CONSTRAINT = 95, ... CONTEXT = 40, NOISE = 0
```

### V3 offline : scoring multi-facteurs
```python
def compute_importance(clause, type_label):
    score = BASE_SCORES[type_label]  # 100 → 0
    
    # Facteurs de pondération (cumulatifs)
    if has_numbers(clause.text):
        score += 10      # les chiffres sont importants
    if has_units(clause.text):
        score += 10      # unités aussi
    if has_technical_terms(clause.text):
        score += 5       # termes techniques (médical, légal, scientifique)
    if has_conditionals(clause.text):
        score += 15      # "si X alors Y" → critique à comprendre
    if has_exceptions(clause.text):
        score += 15      # "sauf si" → modifie une règle
    if has_mutation_marker(clause.text):
        score += 10      # "finalement" → instruction corrective
    if has_named_entities(clause.text):
        score += 5       # noms propres, marques, produits
    
    # Pénalités
    if is_pure_filler(clause.text):
        score -= 20
    if is_hedging(clause.text):
        score -= 15      # "je pense que", "peut-être"
    if is_duplicate(clause, previous_clauses):
        score -= 30
    
    return max(0, min(100, score))
```

### Seuils de décision
```python
if score >= 80:  DO_NOT_REMOVE
if 50 <= score < 80:  COMPRESS_FORM_ONLY
if 20 <= score < 50:  COMPRESS_OR_MERGE
if score < 20:  REMOVE_IF_REDUNDANT
```

---

## 6. Validation + Feedback Loop (P7 + feedback)

### Checks réalisables offline
```python
def validate_ir(ir):
    warnings = []
    
    if not ir["tasks"]:
        warnings.append({"severity": "high", "msg": "No task detected", "action": "KEEP_ORIGINAL"})
    
    if len(ir["languages"]) > 1:
        if not resolve_language_conflict(ir):
            warnings.append({"severity": "medium", "msg": "Language conflict", "action": "KEEP_BOTH"})
    
    # Vérifier que les exceptions ont une base
    for exc in ir["exceptions"]:
        if exc["base"] not in [c["text"] for c in ir["constraints"]]:
            warnings.append({"severity": "low", "msg": f"Orphan exception: {exc}", "action": "ATTACH_TO_NEAREST"})
    
    # Vérifier les overrides orphelins
    for mutation in ir["mutations"]:
        if not find_target_attribute(ir, mutation["attr"]):
            warnings.append({"severity": "medium", "msg": f"Orphan override: {mutation}", "action": "STRIP_OVERRIDE"})
    
    # Vocabulaire à utiliser
    for term in ir.get("terminology", []):
        if term.get("must_use") and term["term"] not in flatten(ir.values()):
            warnings.append({"severity": "low", "msg": f"Required term '{term}' missing", "action": "INJECT"})
    
    # Confiance globale
    confidence = compute_global_confidence(ir)
    if confidence < 0.5:
        return {"action": "FALLBACK_ORIGINAL", "warnings": warnings}
    
    return {"action": "COMPRESS", "warnings": warnings}
```

### Feedback loop
```python
def compress_with_validation(prompt):
    for attempt in range(3):
        fragments = fragment(prompt)
        ir = build_ir(fragments)
        validation = validate_ir(ir)
        
        if validation["action"] == "FALLBACK_ORIGINAL":
            return {"light": prompt, "balanced": prompt, "aggressive": prompt}
        
        if not validation["warnings"]:
            break  # IR validé
        
        # Corriger les warnings et retenter
        prompt = apply_corrections(ir, validation["warnings"])
    
    # Compression finale
    return generate_versions(ir)
```

---

## 7. Exceptions et Conditionnels

### Patterns offline pour les exceptions
```python
EXCEPTION_PATTERNS_EN = [
    r'(sauf|except|but|excluding|other than|aside from)\s+(.+)',
    r'(no|not|never|without)\s+(.+)\s+(sauf|except|but|unless)\s+(.+)',
    r'(allowed|fine|okay|autorisé|permis)\s*(:|,)?\s*(.+)',
]
```

### Patterns offline pour les conditionnels
```python
CONDITIONAL_PATTERNS_EN_FR = [
    r'(if|si|when|lorsque|whenever)\s+(.+?)\s*(then|alors)\s*(.+)',
    r'(if|si)\s+(.+?)\s*[,:]\s*(.+?)\s*(otherwise|sinon|else)\s*(.+)',
    r'(en fonction de|depending on|according to)\s+(.+)',
]
```

---

## 8. Plan d'implémentation (par ordre de priorité)

### Phase 1 — IR enrichie (effort: moyen, impact: fort)
- [ ] Étendre le schéma IR avec `exceptions`, `conditionals`, `terminology`, `tones`, `languages`, `mutations`, `history`, `warnings`
- [ ] Refactor `build_structured_prompt` → `build_ir` qui retourne un dict structuré
- [ ] Ajouter l'extraction des formats étendus (N steps, article, script, email, slide, etc.)
- [ ] Ajouter l'extraction de la tonalité depuis les phrases ROLE/CONTEXT

### Phase 2 — Fragmentation atomique (effort: moyen, impact: fort)
- [ ] Ajouter `split_colon_enum(fragments)` → coupe `:` + énumération
- [ ] Ajouter `split_override_clauses(fragments)` → coupe sur les overrides intra-phrase
- [ ] Ajouter `split_list_markers(text)` → coupe `1.\n2.\n` en clauses distinctes
- [ ] Protéger les abréviations correctement (`i.e.`, `e.g.`, `v2.0.1`, `M.`, `Mme.`, `3.14`)

### Phase 3 — Mutation/Override tracker (effort: moyen, impact: fort)
- [ ] Implémenter `MutationTracker` avec mapping attribut → valeur
- [ ] Extraire les attributs modifiables des clauses (count, format, tone, language, constraint value)
- [ ] Appliquer les mutations à l'IR avant compression (pas comme un filtre de phrases séparé)

### Phase 4 — Scoring contextuel (effort: faible, impact: moyen)
- [ ] Remplacer les poids statiques par `compute_importance(clause, type)`
- [ ] Ajouter les détections : nombres, unités, termes techniques, conditionnels, exceptions, mutations, entités nommées
- [ ] Ajouter les pénalités : filler, hedging, duplicat

### Phase 5 — Validation + feedback loop (effort: moyen, impact: moyen)
- [ ] Implémenter `validate_ir(ir)` avec tous les checks offline possibles
- [ ] Implémenter la boucle de correction (max 3 tentatives)
- [ ] Ajouter le fallback "original" quand la confiance est trop basse

### Phase 6 — Compression basée sur l'IR (effort: faible, impact: élevé si phases 1-5 faites)
- [ ] Light : ne touche qu'aux clauses avec importance < 20 + greetings/closings
- [ ] Balanced : compresse forme des clauses avec importance < 80, garde fond des clauses >= 80
- [ ] Aggressive : génère vue canonique depuis l'IR (abandonne la prose)

---

## 9. Exemple concret V1 → V3

### Input
```
write 5 emails for beginners. Actually make it 10. No emojis except 🚀. If the reader is a CEO then keep it formal. Tone: friendly. In French.
```

### V1 actuelle
```python
task_s   = ["write 5 emails for beginners."]
context_s = ["Actually make it 10.", "No emojis except 🚀.",
             "If the reader is a CEO then keep it formal.",
             "Tone: friendly.", "In French."]
# → "Actually make it 10" et "No emojis except 🚀" en contexte, pas en contrainte.
# → Les overrides (Actually, unless) sont perdus dans le contexte.
```

### V3 offline
```json
{
  "tasks": [{"text": "write emails for beginners", "count": 10}],
  "audiences": ["beginners"],
  "formats": ["email"],
  "constraints": [{"text": "no emojis", "exceptions": ["🚀"]}],
  "conditionals": [{"if": "reader is a CEO", "then": "keep it formal"}],
  "tones": ["friendly"],
  "languages": ["fr"],
  "mutations": [
    {"attr": "tasks[0].count", "old": 5, "new": 10, "marker": "actually"}
  ],
  "warnings": []
}
```

### Output Light (inchangé vs V1)
```
Write 10 emails for beginners. No emojis except 🚀. If the reader is a CEO then keep it formal. Tone: friendly. In French.
```

### Output Balanced (V3 — structuré)
```
Task: write 10 emails for beginners
Tone: friendly
Language: French
Constraints: no emojis (except 🚀)
Conditional: if reader is CEO → formal
```

### Output Aggressive (V3 — canonique)
```
TASK: emails(10) → beginners
TONE: friendly
LANG: fr
CONSTRAINTS: emojis=no (🚀 except)
COND: CEO → formal
```

---

## 10. Cas limites V3 offline

| Cas | Traitement |
|-----|------------|
| `"écris 10. Non 5."` | Mutation sur count: 10→5. IR stocke les deux, version finale = 5 |
| `"JSON ou CSV"` | Pas de conflit — "ou" indique une alternative. Stocker les deux formats |
| `"pas d'émojis sauf 🚀"` | Exception extraite: base="pas d'émojis", allowed="🚀" |
| `"si > 100 alors X"` | Conditionnel extrait. else manquant → stocker None |
| `"Python est un serpent... en Python"` | Pas de détection offline → les deux en contexte. Warning ajouté |
| `"oublie ça, je veux dire..."` | Override partiel: annule la phrase précédente exactement |
| `"finally" en anglais` | Ambigu: peut être "enfin" (override) ou "finalement" (conclusion). Si suivi d'un nombre → override |
| `"Make it beautiful. Actually no, make it efficient."` | Mutation sur l'attribut de qualité (beautiful→efficient) |
| `"v2.0.1 a corrigé le bug"` | Split protégé: "v2.0.1" est une unité atomique |
| `"3 emails. 3 étapes."` | Le nombre 3 apparaît deux fois pour des attributs différents (count vs format). Pas de conflit |

---

## 11. Résumé des changements dans le code

### Fichiers à modifier
```
backend/prompt_optimizer.py  → refactor le pipeline, ajouter IR, override tracker, scoring
backend/models.py            → ajouter les nouveaux types IR si nécessaire
benchmark_test.py            → nouveaux tests pour les cas V3
```

### Fonctions V1 à conserver
- `_sanctuary_extract` / `_sanctuary_reinject` → P0 + P10 (inchangé)
- `_is_french` → P3 language detection
- `_apply_cancellation_filter` → intégré dans MutationTracker
- `_extract_role_title`, `_extract_target`, `_extract_product`, `_extract_task_action` → P3 extraction
- `_compress_sentence`, `_compress_context`, `_compress_constraints` → P7 compression (à adapter)
- `_clean_light_text`, `_universal_filler_patterns` → P1 normalize

### Fonctions V1 à supprimer / remplacer
- `_split_sentences` → remplacé par `fragment()` (P2)
- `_classify_sentence` → remplacé par `tag_clause()` (P3) avec plus de types
- `_build_structured_prompt` → remplacé par `build_ir()` (P6) + `generate_versions()` (P8-P9)
- `_anti_redundancy_filter` → intégré dans le scoring (score -= 30 si duplicate)
- `_purge_meta_discourse` → intégré dans P1 normalize (toujours utile)

### Nouvelles fonctions à écrire
- `fragment(text)` → P2 segmentation atomique
- `tag_clause(clause)` → P3 tagging enrichi (17 types)
- `extract_exceptions(text)` → exceptions
- `extract_conditionals(text)` → conditionnels
- `extract_format(text)` → formats étendus
- `extract_tones(text)` → ton
- `extract_numbers_limits(text)` → valeurs numériques par attribut
- `MutationTracker` → classe de suivi des mutations
- `detect_conflicts(ir)` → P5
- `compute_importance(clause, type)` → scoring multi-facteurs
- `validate_ir(ir)` → P7
- `apply_corrections(ir, warnings)` → feedback loop
- `generate_versions(ir)` → P8-P9 (remplace `optimize_locally`)
- `compress_with_validation(prompt)` → entry point avec feedback loop

---

## 12. Décisions d'architecture

1. **Les blocs Sanctuary sont extraits en premier** (P0) — inchangé, fonctionne bien.
2. **La fragmentation atomique (P2) remplace le sentence split** — plus robuste pour listes et overrides.
3. **Le tagging (P3) utilise 17 types au lieu de 9** — meilleure granularité pour la compression.
4. **Les mutations (P4) sont trackées par attribut, pas par phrase** — permet des overrides partiels.
5. **Les conflits (P5) sont détectés au niveau attribut, pas type** — évite les faux positifs.
6. **Le scoring (P8) est contextuel, pas statique** — une clause contextuelle avec des nombres peut être plus importante qu'une clause task sans contenu.
7. **La validation (P7) peut forcer un fallback** — si la confiance est trop basse, on retourne le prompt original plutôt que de le massacrer.
8. **La boucle de feedback permet 3 tentatives** — si la validation échoue, on retage/reconstruit avec les corrections.
9. **L'IR est la source de vérité pour la compression** — on ne compresse jamais le texte original, on régénère depuis l'IR.
