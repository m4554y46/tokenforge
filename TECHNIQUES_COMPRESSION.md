# Techniques de Compression de Prompts — TokenForge

Ce document détaille l'ensemble des techniques de compression utilisées par l'optimiseur local de TokenForge pour réduire le nombre de tokens d'un prompt tout en préservant son sens, sa syntaxe technique, et ses instructions comportementales.

---

## 1. Architecture Sanctuary (Extract → Compress → Reinject)

Principe fondamental : avant toute compression, on extrait les blocs qui **ne doivent jamais être modifiés**, on compresse le reste, puis on réinjecte.

**Blocs protégés :**
- Blocs de code (``` ... ``` et `inline code`)
- JSON/XML/HTML
- URLs
- LaTeX math (`$...$`, `$$...$$`)
- Unités (10km, 5GB, 100ms, etc.)
- Nombres, versions (v2.3.1), abréviations (e.g., i.e., vs.)

Implémentation : `_sanctuary_extract()` → remplace chaque bloc par un token unique `§PROTECTED_0§`, `§PROTECTED_1§`, etc. Après compression, `_sanctuary_reinject()` replace les tokens par les originaux.

---

## 2. Purge du Meta-Discours

Supprime les phrases d'introduction, de transition, et de conclusion qui n'ajoutent pas d'instruction utile.

**Patterns anglais (~40) :**
```
"please feel free to", "I would like you to", "your task is to",
"the goal is to", "if you have any questions", "don't hesitate to",
"thank you for", "I hope this helps", "let me know if",
"please note that", "it is important to note that", etc.
```

**Patterns français (~50) :**
```
"n'hésitez pas à", "je vous remercie", "merci de bien vouloir",
"je souhaite que vous", "votre mission est de", "le but est de",
"si vous avez des questions", "en vous remerciant", "cordialement",
"je vous prie de", "dans le cadre de", "afin de vous aider", etc.
```

La purge s'exécute **avant** la fragmentation en phrases, pour éviter que ces segments ne persistent dans des sections classifiées.

---

## 3. Détection de Langue (FR/EN)

Détection binaire avant toute transformation :
- Basée sur un ensemble de tokens discriminants français (`je`, `tu`, `vous`, `nous`, `pour`, `dans`, `avec`, `sur`, `pas`, `une`, `cet`, `cette`, `ces`, `mon`, `ton`, `son`, `mais`, `donc`, `quand`, `bien`, `merci`, `écris`, `non`, `oui`, `être`, `avoir`, etc.)
- Seuil ≥ 5 tokens français → `is_fr = True`
- Exécutée **avant** le filtre d'annulation (pour éviter que l'annulation ne supprime les rares mots français d'un court prompt FR)

---

## 4. Filtre d'Annulation (MutationTracker)

Détecte les marqueurs de rétro-annulation et supprime la phrase qui précède.

**Marqueurs anglais :** `actually`, `actually no`, `actually no,`, `actually, no,`, `wait, no`, `actually wait`, `on second thought`, `instead,`, `rather,`, `correction:`, `revised:`, `update:`, `new instruction:`, `actually, make that`, `no, wait`, `actually, cancel`, `actually never mind`, `actually, let me rephrase`, `actually, i meant`, `actually, change that`, `actually, instead`, `actually, on second thought`, `wait, actually`, `actually, i take that back`, `actually, i change`, `actually, i revise`, `actually, i correct`, `scratch that`

**Marqueurs français :** `non`, `non,`, `non mais`, `non en fait`, `en fait non`, `finalement non`, `en fait`, `finalement`, `ou plutôt`, `plutôt`, `correction:`, `révisé:`, `mise à jour:`, `nouvelle instruction:`, `en fait, annule`, `en fait, je change`, `en fait, je reprends`, `en fait, finalement`, `en fait, plutôt`, `en fait, je corrige`, `en fait, je modifie`, `en fait, je préfère`, `annule ça`, `oublie ça`, `laisse tomber`, `rectification:`, `au final`

Fonctionnement : `_apply_cancellation_filter()` supprime la phrase immédiatement avant le marqueur, puis nettoie le marqueur et les mots de liaison qui suivent.

**MutationTracker** (`_merge_override`) : quand l'annulation introduit une nouvelle valeur, elle est mergée avec l'originale. Si le override contient un verbe fort (`"make it 5"`), il est conservé tel quel. Sinon, le nom/nombre est extrait et substitué.

---

## 5. Fragmentation Atomique

Découpe le prompt en phrases individuelles pour un traitement granulaire.

**Algorithme :**
- Split sur `(?<=\.)(?<!\d\.)\s+` : point suivi d'espace, **sauf** si le point est précédé d'un chiffre (protège `1.`, `2.` dans les listes)
- Protection des abréviations (`Mr.`, `Dr.`, `vs.`, `e.g.`, `i.e.`, `etc.`, `Mme.`, `M.`)
- Protection des versions (`v2.3.1`, `3.14`, `2.0`)
- Protection des nombres décimaux (`3.14`)
- `_split_list_enumeration` : éclate `"a) x b) y"` en phrases séparées
- `_split_numbered_list` : éclate `"1. x 2. y"` en phrases séparées
- `_split_intra_override` : détecte les phrases avec "actually"/"non" internes pour les séparer avant analyse

---

## 6. Classification par Type de Contenu

Chaque phrase est classifiée pour décider comment la traiter :

| Classe | Description | Détection |
|--------|-------------|-----------|
| **Task** | L'action principale demandée | Verbes d'action impératifs (`write`, `create`, `generate`, `analyze`, etc.) |
| **Role** | Le rôle à adopter | Marqueurs de rôle (`act as`, `you are a`, `tu es un`, `agis comme`, `incarne`) |
| **Target** | Le public cible | Marqueurs d'audience (`target audience`, `for beginners`, `destiné à`) |
| **Context** | Informations contextuelles | Tout ce qui ne correspond pas aux autres classes |
| **Constraints** | Règles et limites | Négations, verbes forts avec négation (`do not`, `ne...pas`), mots-clés (`avoid`, `except`, `ensure`) |
| **Output** | Format de sortie | Indications de format (`respond in`, `output as`, `format:`, `réponds en`) |
| **Structure** | Structure du document | Indications structurelles (`using sections`, `organize as`, `structure`) |
| **Tone** | Ton | Adjectifs de ton (`friendly`, `professional`, `formal`, `casual`) |
| **Format** | Format | Indicateurs de format (`markdown`, `json`, `bullet points`) |
| **Exceptions** | Exceptions | Marqueurs d'exception (`except`, `unless`, `sauf`, `do not include`) |
| **Conditionals** | Conditions | Marqueurs conditionnels (`if`, `when`, `si`, `lorsque`) |
| **Ranking** | Classement | Instructions de classement/priorité |

L'ordre de détection est critique : les verbes d'action métier (~30 verbes forts) sont vérifiés **avant** tout pattern de tâche.

---

## 7. Filtre Anti-Redondance

Supprime les phrases dupliquées ou quasi-identiques :
- Similarité Jaccard sur les mots (>60%)
- Les phrases redondantes sont marquées et ignorées lors de la construction du prompt structuré

---

## 8. Modes de Compression

### 8.1 Light (Légère)

**Opérations :**
1. Purge des salutations et formules de politesse
2. Réorganisation structurelle (fusion de phrases similaires)
3. Filtrage des phrases à faible score d'importance (< 20)

**Résultat :** Prompt nettoyé, structure conservée, ~20-55% de réduction.

### 8.2 Balanced (Équilibrée)

**Pipeline complet par section :**

1. `_compress_sentence()` sur chaque phrase :
   - Suppression des fillers (mots vides : `very`, `really`, `quite`, `just`, `basically`, `actually`, `literally`, `très`, `vraiment`, `assez`, `juste`, `simplement`, `quelque peu`)
   - Suppression du hedging (`maybe`, `perhaps`, `possibly`, `probably`, `unlikely`, `potentially`, `peut-être`, `probablement`, `éventuellement`, `potentiellement`)
   - Abréviations : `you are → you're`, `do not → don't`, `it is → it's`
   - French : `vous êtes → vous êtes`, `ce n'est pas → ce n'est pas`

2. `_compress_context()` sur toutes les sections (sans gate de score depuis Phase 6) :
   - Pronoms sujets : `I`, `you`, `we`, `they` → supprimés en début de segment
   - Déterminants possessifs : `your`, `my`, `our`, `their` → supprimés
   - Articles : `the`, `a`, `an` → supprimés
   - Verbes légers : `is`, `are`, `was`, `were`, `be`, `been`, `being` → supprimés
   - Pronoms relatifs : `that`, `which`, `who`, `whom`, `whose` → supprimés
   - French : `je`, `tu`, `il`, `elle`, `nous`, `vous`, `ils`, `elles`, `mon`, `ton`, `son`, `ma`, `ta`, `sa`, `mes`, `tes`, `ses`, `nos`, `vos`, `leurs`, `le`, `la`, `les`, `un`, `une`, `des`, `ce`, `cet`, `cette`, `ces` → supprimés

3. `_compress_constraints()` :
   - `"The first email should be friendly"` → `"Email 1: friendly"`
   - `"Le premier email doit être amical"` → `"Email 1: amical"`

4. `_extract_task_action()` pour concision (comme Aggressive) :
   - `"Your task is to write an email"` → `"Write email"` (EN)
   - `"Votre mission est d'écrire un email"` → `"Écrire email"` (FR)

5. Fusion Info : Tone + Format + Exceptions fusionnés en une seule ligne `## Info`

6. Déduplication IR : Target supprimé si déjà présent dans Task ; sections Constraints/Output ignorées si le contenu est juste un mot-clé IR

### 8.3 Aggressive (Agressive)

**Opérations :**
- Même pipeline que Balanced, plus :
- Format télégraphique : `## Task` → `Task:`
- Suppression de tous les articles, pronoms, auxiliaires
- Raccourcissement de mots (>6 caractères, ≥10 occurrences) :
  - `professional → pro`, `configuration → config`, `information → info`
  - `additional → extra`, `application → app`, `communication → comms`
  - `development → dev`, `documentation → docs`, `experience → exp`
  - `optimization → opt`, `implementation → impl`, `management → mgmt`
  - `organisation → org`, `representative → rep`, `administration → admin`
- BPE compact : `->`, `=` pour liens ; `&` listes ; `eg`, `ie`, `re:` marqueurs
- Suppression des verbes de contrainte (`must`, `should`, `need to`, `have to`, `required to`)
- Targets, tones, formats fusionnés sur une seule ligne

---

## 9. Score Contextuel (Importance Scoring)

Chaque phrase reçoit un score d'importance de 0 à 100 :

| Facteur | Bonus |
|---------|-------|
| Base | 50 |
| + Nombres | +10 |
| + Unités | +10 |
| + Termes techniques | +8 |
| + Entités nommées | +5 |
| + Marqueurs de mutation | +10 |
| + Verbe fort | +5 |
| − Fillers | −20 |
| − Hedging | −15 |
| − Redondance | −30 |

Le score est stocké dans `ir["scores"]` et utilisé dans :
- Light : filtre les phrases avec score < 20
- Balanced/Aggressive : le score est stocké mais n'affecte plus la compression depuis Phase 6

---

## 10. Validation + Boucle de Rétroaction

`validate_ir()` vérifie l'intégrité de l'IR :
- Au moins une phrase classée `task` doit exister
- `total_tokens` doit être cohérent
- Si invalide → `_apply_corrections()` tente de reclassifier

**Boucle de rétroaction :** max 2 tentatives de correction. Si toujours invalide → `FALLBACK` (texte protégé original).

---

## 11. BPE (Byte Pair Encoding) Compact

Mappings de mots vers des formes plus courtes :

| Original | Compact |
|----------|---------|
| `because` | `bc` |
| `please` | `pls` |
| `about` | `re` |
| `example` | `eg` |
| `that is` | `ie` |
| `therefore` | `so` |
| `however` | `but` |
| `furthermore` | `also` |
| `additionally` | `plus` |
| `regarding` | `re:` |
| `and` | `&` |
| `to` | `→` ou supprimé |
| `becomes` | `=` |
| `leads to` | `→` |

Aggressive seulement : `and → &`, `to → →`, `becomes → =`

---

## 12. IR Enrichie (Phase 1)

Avant la construction du prompt final, une représentation intermédiaire (IR) est construite :

```python
ir = {
    "tone": [...],      # extraits de ton
    "formats": [...],   # formats de sortie
    "exceptions": [...], # règles d'exclusion
    "conditionals": [...], # conditions
    "scores": {...},     # scores d'importance par phrase
    "task_action": ...,  # action principale extraite
    "target": ...,       # audience cible
    "num_requirements": int, # nombre de requêtes numériques
}
```

Cette IR permet au mode Balanced de générer des sections `## Info`, `## Target`, `## Output` enrichies qui documentent les métadonnées du prompt.

---

## 13. Protection des Mots-courts (Faux-positifs Filler)

`_is_pure_filler()` : une phrase de ≤3 mots contenant `.`, `:`, `;`, `!`, `?` n'est jamais classée comme filler — protège les titres et les listes courtes.

---

## 14. Nettoyage des Espaces

`_clean_whitespace()` utilise `[ \t]` (espaces horizontaux uniquement), jamais `\s` — préserve les `\n\n` entre les `## Section` headers.

---

## 15. Pipeline Complet (Ordre d'Exécution)

```
1. Sanctuary Extract
2. Détection de langue (is_fr)
3. Filtre d'annulation (cancellation filter + MutationTracker)
4. Purge du meta-discours
5. Filtre anti-redondance
6. Fragmentation atomique (sentence split)
7. Classification phrase par phrase
8. Construction de l'IR enrichie + scoring
9. Compression par mode (Light/Balanced/Aggressive)
10. Validation + boucle de rétroaction
11. Construction du prompt structuré
12. Sanctuary Reinject
13. Nettoyage des espaces
```

Chaque étape est indépendante et peut être activée/désactivée par mode.

---

## Performances Observées

| Test | Mots | Light | Balanced | Aggressive |
|------|------|-------|----------|------------|
| Email EN (356w) | 356 | −55.9% | −29.2%* | −66.9% |
| Prompt court P1 (15w) | 15 | −20% | −66.7% | −70% |
| Prompt moyen P3 (26w) | 26 | −46.2% | −3.8% | −34.6% |
| Prompt long P4 (181w) | 181 | −17.7% | **+13.8%** | −43.1% |

*Le mode Balanced inclut les sections IR enrichies qui ajoutent des tokens — pour les prompts >50 mots, cette surcharge est compensée par la compression contextuelle.

---

*Document généré le 05/06/2026 — TokenForge v1.0.0*
