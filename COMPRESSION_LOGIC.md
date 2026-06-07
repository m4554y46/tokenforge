# Logique de compression du Prompt Optimizer (OptiToken)

## 1. Pipeline global

prompt brut
  → [Sanctuary] extraction des blocs proteges (code, LaTeX, JSON, URLs, unites)
  → [Pre-processing] rollback + purge meta-discours
  → [Sentence Split] decoupage en phrases
  → [Anti-redundancy] dedup par similarite Jaccard
  → [Classification] chaque phrase recoit un标签 : greeting, closing, role, task, context, constraint, output_format, structure_item, uncertain
  → [Section Builder] 3 versions (Light / Balanced / Aggressive) assemblees differemment
  → [Post-processing] nettoyage liste numerique, BPE compact, reinjection Sanctuary
  → [Output] 3 dictionnaires {label, description, prompt, changes_made}

---

## 2. Sanctuary (sanctuary_extract / sanctuary_reinject)

### But
Isoler les contenus techniques pour que les règles de compression ne les abîment pas.

### Extraction (dans l'ordre)
1. ```code blocks```  →  __CODE_BLOCK_0__
2. `inline code`      →  __INLINE_CODE_0__
3. $$latex block$$    →  __LATEX_BLOCK_0__
4. $latex inline$     →  __LATEX_INLINE_0__
5. {JSON objects}     →  __JSON_OBJECT_0__      (⚠️ greedy match [\s\S]*? sur les premier { et dernier }, peut mal matcher des objects imbriqués)
6. URLs               →  __URL_0__
7. Unités physiques   →  __UNIT_0__              (pattern: \b\d+\s*(mg|g|kg|mL|L|°C|°F|V|Hz|km/h|mph|%|px|em|rem|ms|GHz|MHz|GB|MB|TB)\b)

### Réinjection
Remplacer chaque token __XXX_N__ par sa valeur originale DANS L'ORDRE après toute la compression.

### Faiblesse
- Les objets JSON sont capturés par `\{[\s\S]*?\}` qui ne gère PAS les `{` imbriqués → `{a: {b: 1}}` matche `{a: {b: 1}` ou `{b: 1}}`.
- L'unité standalone "°C" (sans nombre devant) ou "C" seul (Celsius sans symbole degré) n'est pas capturée.
- Les patterns LaTeX `\$[^$\n]+\$` ratent les formules multi-lignes.

---

## 3. Pre-processing

### 3a. Filtre d'annulation (apply_cancellation_filter)

Détecte les marqueurs de rétro-annulation dans le texte :
  EN: actually no, forget that/it, never mind, scratch that, on second thought, wait no, cancel that, ignore that, strike that
  FR: en fait non, oublie ça/oubliez ça, finalement non, au temps pour moi, non finalement, annule ça, ignore ça, laisse tomber, ms oublie, mais oublie, j'oubliais, ah oui j'oubliais

Algorithme :
1. Découper en phrases (split sur `(?<=[.!?])\s+`)
2. Pour chaque phrase :
   Si cancelle → pop la phrase PRÉCÉDENTE (rollback) ET supprimer le texte AVANT le marqueur dans la phrase courante
3. Nettoie les mots de liaison résiduels après le marqueur (attends, bon)

### 3b. Purge du meta-discours (purge_meta_discourse)

Deux listes (EN + FR) de ~50 patterns chacun, appliqués par re.sub séquentiellement.

EN patterns (exemples) : I'm reaching out / I hope you are doing well / please / thank you / basically / actually / by the way / you know / I think / in my opinion / the thing is / well, / so, / okay, / oh, / ah, / here is the thing / when it comes to / in terms of / in fact / to be honest / by the way

FR patterns (exemples) : compte sur toi / ça va être une tuerie / merci / écoute / voilà / donc / en fait / au fait / bref / dis-moi / je trouve que / je pense que / je crois que

⚠️ Ordre d'application critique : certains patterns retirent des mots que d'autres patterns cherchent ensuite (ex: \bplease\b enlève "please" avant que \bread everything carefully\b ne cherche "read everything..." au début de la phrase → le "please" était le seul mot avant "read", du coup le pattern plus large rate sa cible).

### 3c. Anti-redondance (anti_redundancy_filter)

Similarité Jaccard entre phrases consécutives :
  jaccard = len(intersection(s1, s2)) / len(union(s1, s2))
Si jaccard > 0.6 → la phrase suivante est un doublon et supprimée.

---

## 4. Sentence split (split_sentences)

Découpage sur `(?<=[.!?])\s+`. Protège les abréviations (Mr., Dr., M., Mme., etc.) en remplaçant temporairement leurs points par un caractère nul avant split.

⚠️ Ne gère PAS les listes numérotées avec `:` → ex: "voici la liste : 1. item 2. item" devient une seule phrase à cause du pré-traitement `:\n` → `.\n`.

---

## 5. Classification (classify_sentence)

### Ordre de priorité (premier match gagne) :

1. **greeting** — salutations (hello, hi, dear, bonjour, salut, I hope, I'm reaching out, etc.)
2. **closing** — formules de politesse finale (thank you, merci, cordialement, sincerely, best regards, looking forward, hâte, etc.)
3. **role** — définition de rôle (act as, you are a, as a, en tant que, tu es un, vous êtes un, je cherche un, j'ai besoin d'un, mets-toi dans la peau, agis comme, incarne, etc.)
4. **output_format** — spécification de format (output, return, give me, provide, format, as JSON, no commentary, sortie, fournissez, etc.)
5. **constraint** — contraintes (must, should, required, important, do not, avoid, ensure, only, exactly, doit, devrait, ne pas, etc.)
6. **task** (via Correctif 3) — verbe d'action fort SANS négation → task, AVEC négation → constraint
7. **task** (via task_pats) — patterns de tâche (write, create, generate, I need you to, I want you to, could you, please, objective, project involves, etc.)
8. **structure_item** — éléments de liste ( - mot chiffre: , - item, 1. item)
9. **context** — tout ce qui n'a matché aucun des labels ci-dessus

### Correctif 3 — Verbes d'action métiers (strong_verbs)
Liste prioritaire de ~30 verbes impératifs EN / ~40 FR.
Si un verbe fort est trouvé SANS mot de négation → 'task'
Si un verbe fort est trouvé AVEC négation dans la phrase → 'constraint'

### Correctif 2 — Négation globale (has_global_negation)
Vérifie la présence de mots de négation (without, not, never, avoid, sans, ne pas, n', etc.) DANS TOUTE la phrase.
Utilisé pour surclasser 'task' en 'constraint' quand un verbe fort est associé à une négation.

### Weaknesses
- `\bplease\b` est dans task_pats → toute phrase avec "please" devient 'task'
- "give me" est dans output_pats MAIS aussi "give" est dans task_pats → ordre d'application décide
- Les mots d'action implicites ("need", "use", "help") ne sont PAS dans strong_verbs → pas de classification 'task' pour les phrases avec ces verbes
- La négation est vérifiée par substring simple (`nw in text_lower`) → `n'` dans négation FR matche aussi "j'n" dans "j'n'utilise" (overmatch)
- Les adverbes de restriction ("only", "just") sont dans constraint_pats → classifications parfois trop larges

---

## 6. Section Builder (build_structured_prompt)

### Principe général
role_s, task_s, context_s, constraint_s, output_s, structure_s, greeting_s, closing_s sont calculés une fois.
greeting_s et closing_s sont TOUJOURS exclus des sections.
Les phrases `uncertain` sont ignorées.

### 6a. Light mode
```
pruned = join(non_structure)  # tout sauf greeting, closing, uncertain, constraint, output_format
+ output_s si présent
+ structure_s si présent
apply polite patterns
apply clean_light_text (fillers, slang, repeat punct)
clean whitespace
```

Stratégie : minimaliste. Enlève juste les blablas et les formules de politesse.
Compression cible : 15-30% (actuellement 35-68% sur les tests — trop pour un "light", probablement parce que les phrases de contexte sont nombreuses et que la suppression des salutations fait une grosse différence).

### 6b. Balanced mode
```
sections = []
Role   → compress_sentence(join(role_s), 'balanced')
Task   → compress_sentence(join(task_s), 'balanced')
Target → compress_context(compress_sentence(target, 'balanced'))
Product → brut
Context → compress_context(compress_sentence(join(context_s), 'balanced'))
Structure → compress_sentence(each, 'balanced') → bullet
Constraints → for each: compress_sentence + compress_context
            → puis compress_constraints(combined)
            → "Avoid:" prefix si négation
Output → compress_sentence(join(output_s), 'aggressive')
```

Compression intra-section :
1. **compress_sentence(..., 'balanced')** : contractions (I'm, don't), abbreviations (info, tech, mgmt), task framing removal ("what I want you to do is" → ""), subject stripping (I have to → "", This is a → ""), trailing padding ("for me", "please"), articles/light verbs in context-target (a, an, the, is, are, was, were removed by compress_context)
2. **compress_context** : articles (a, an, the), light verbs (is, are, was, were, has, have), possessives (our, my, your, their), relative pronouns (who, which), subject restart (I, We, You, He, She, It, They → removal after period)
3. **compress_constraints** : "The first email should serve to X" → "Email 1: X", ordinal→number mapping

### 6c. Aggressive mode
```
Lines:
  Role: titre_seul
  Task: verbe + objet + for Product
  Target: motsclefs
  Structure: bullets
  Constraints: "Avoid:" prefix si negatif, sinon "- constraint"
  Output: "- spec"
```

Tout le texte passe par compress_sentence(..., 'aggressive') qui :
1. Applique les patterns light + balanced
2. Supprime TOUS les mots-outils (a, an, the, is, are, was, were, be, been, have, has, had, do, does, did, will, would, shall, should, can, could, may, might, must, to, of, in, for, on, at, by, with, from, as, this, that, these, it, its, my, your, our, their, me, him, her, us, them, I, you, we, he, she, they, not, no, but, or, if, so, than, just, also, very, really, quite, about, which, what, when, where, who, how, why, there, each, every, some, any, all, both, few, many, much, several, here, now, then, still, already, yet, only, well, even, too, more, most, little, lot, lots, such, being, having, own, same, another, everything, nothing, something, always, never, often, sometimes, quite, pretty, fairly, rather, qualified, skilled, talented, experienced + équivalents FR)
3. BPE compact : leads to → ->, results in → ->, is defined as → =, between → -, and → &

---

## 7. compress_sentence — détail par niveau

### Patterns light (tous niveaux)
- Suppression des formules de politesse : I would like you to, I want you to, Could you please, I need you to, Please, Thank you, I appreciate
- Simplifications : In order to → To, Due to the fact that → Because, A lot of → many, As well as → and, Is able to → can
- Équivalents FR : Je voudrais que vous, J'aimerais que vous, Pourriez-vous, S'il vous plaît, Merci

### Patterns balanced (en plus)
- Contractions : I'm, don't, it's, can't, won't, there's, that's...
- Abréviations : because→bc, and→&, example→eg, approximately→~, introduction→intro, information→info, management→mgmt, something→sth, someone→sb, without→w/o, regarding→re:, limited→ltd
- Task framing removal : "what I want you to do is to" → "", "what I need is" → "", "your task is to" → "", "the goal is to" → "", "my job is to" → ""
- Subject stripping before verbs : "I have to" → "", "We need to" → "", "I would like to" → ""
- Sentence start stripping : "This is a/the " → "", "It is a/the " → "", "There is/are a/the " → ""
- Trailing padding : "for me" / "for us" / "please" en fin de ligne
- Residual framing : "what do is to" → "" (quand light patterns ont stripé "I want you to" de "what I want you to do is to", il reste "what do is to" → nettoyé)
- Compress "that" as connector : "that is" → "is"
- FR : "ce que je veux" → "", "je dois/veux" → "", "j'ai besoin de/d'" → "", "il faut que" → "", "c'est un/une" → ""

### Patterns aggressive (en plus)
- Suppression de TOUS les mots-outils (50+ mots EN, 40+ mots FR)
- BPE : leads to → ->, results in → ->, is defined as → =, between → -, and → &
- FR : le/la/les/un/une/des/du/de supprimés

---

## 8. Compress_context (utilisé sur Context, Target, Constraints en Balanced)

Supprime les cadres de phrase dans les sections descriptives :
- Sujets en début de phrase : "I/We/You/He/She/It/They " après ". " ou en tout début
- Possessifs : my, your, our, their, his, her, its
- Existential : there is/are, this is, these are, that is
- Light verbs : is, are, was, were, has, have, had, been
- Articles : a, an, the
- Relatifs : who, which is/are, that is/are
- FR : mon/ma/mes/ton/ta/tes..., c'est/c'était/il y a, le/la/les/un/une/des..., est/sont/était/étaient...
- Conversions : "is known as/called/named" → " = "

---

## 9. Compress_constraints (utilisé sur Constraints en Balanced)

"the first email should" → "Email 1:"
"the second email must" → "Email 2:"
"the third email should" → "Email 3:"
Même pattern pour 4th, 5th, et équivalents FR (première, deuxième, troisième...)

---

## 10. BPE Compact (appliqué en post-processing)

### Balanced
- and → &
- for example → eg
- such as → eg
- that is → ie
- in other words → ie
- pertaining to → re:

### Aggressive (tout ce que fait Balanced +)
- leads to → ->
- results in → ->
- produces → ->
- yields → ->
- gives → ->
- is defined as → =
- is equal to → =
- is equivalent to → ==
- is composed of → :
- consists of → :
- contains → :
- between → -

---

## 11. Clean Light Text (appliqué sur Light complet + sur Balanced et Aggressive via compress_sentence)

- Suppression ponctuation répétée : !!! → !, ... → ., ?? → ?
- Suppression des fillers : basically, literally, actually, very, really, quite, just, simply (EN) + vraiment, très, trop, bien, wesh, tkt, mdr, stp, svp (FR)
- Déduplication de mots consécutifs : "the the" → "the"

---

## 12. Split_negated_sentence

Détecte les frontières de négation pour les phrases classées 'constraint' :
  triggers EN : without, rather than, other than, except, instead of
  triggers FR : sans, plutôt que, autre que, sauf, au lieu de

Si un trigger est trouvé → la phrase est coupée en 2 parties :
  task_part → va dans extra_tasks (section Task)
  constraint_part → va dans constraint_s avec préfixe "Avoid:"

---

## 13. Détection de langue (is_french)

Compte les occurrences de ~50 mots français dans le texte.
Si score ≥ 2 → français.

Mots-clés : les articles (le, la, les), pronoms (je, tu, il, elle, nous, vous, ils, elles), verbes (avoir, être, faire, falloir, pouvoir), connecteurs (mais, donc, car, ni, où, parce que, pourtant), marqueurs (wesh, tkt, mdr, stp, svp, bg)

---

## 14. Limitations et faiblesses connues

### Classification
- `\bplease\b` dans task_pats → toute occurrence de "please" (même dans "please note" ou "if you please") force 'task'
- "give me" dans output_pats ET "give" dans task_pats → conflit selon l'ordre
- `\bonly\b` dans constraint_pats → "the only thing" devient 'constraint'
- Les énumérations avec ":" ne sont pas bien splittées (ex: "Voici la liste : 1. item 2. item" → une seule phrase)
- Les verbes faibles (use, help, need, want sans I want you to exact) ne sont pas dans strong_verbs → ratent task
- `\bhave\b` dans aggressive removals → supprime le verbe "have" même dans "have to" ou "must have"

### Sanctuary
- JSON imbriqué non géré `{a: {b: 1}}`
- Unités sans nombre devant non capturées ("°C" seul)
- LaTeX multi-lignes raté par `[^$\\n]+`
- Ordre des patterns : JSON `{...}` peut matcher AVANT `$...$` si un $ est dans un contexte `{...}`

### Section Building
- Aggressive ignore context_s quand task_s existe → perte d'info contextuelle importante
- Balanced construit Target via extraction regex, pas via les phrases classifiées → peut extraire des cibles fausses
- Pas de section ## Why ou ## Goal → le contexte est tout mélangé dans ## Context
- Les phrases 'uncertain' sont simplement ignorées (aucun fallback)

### Filtre d'annulation
- Basé sur split `(?<=[.!?])\s+` → rate les annulations intra-phrase avec des virgules
- Le rollback pop la phrase précédente entière, même si seule une partie devait être annulée

### Anti-redondance
- Jaccard sur l'ensemble des mots → deux phrases longues avec peu de mots communs mais même sens ne sont pas détectées
- Threshold fixe à 0.6 → trop bas pour phrases avec stop words communs, trop haut pour phrases techniques avec vocabulaire partagé

### Général
- Pas de gestion des majuscules après suppression en début de section → "write an email" au lieu de "Write an email" dans ## Task
- Les nombres ordinaux ne sont pas normalisés ("first" → "1" seulement dans compress_constraints, pas ailleurs)
- Le pipeline est déterministe (pas d'IA) → sensible à l'ordre exact des patterns
- La purge FR/EN est appliquée AVANT la détection de langue → si le texte commence par des mots anglais puis devient français, la purge EN s'applique d'abord
- Les tokens Sanctuary (__CODE_BLOCK_0__) peuvent être abîmés par des patterns de compression s'ils contiennent des mots-outils (ex: un token avec "to" dans le nom → \bto\b aggressive match)

---

## 15. Métriques de compression actuelles

Test 1 (email séquence EN, 356 mots) :
  Light: 114 mots (68.0%) → trop compressé pour "Light", probablement OK
  Balanced: 243 mots (31.7%) → correct
  Aggressive: 118 mots (66.9%) → attendu

Test 2 (stream FR, 284 mots) :
  Light: 217 mots (23.6%) → plausible pour "Light"
  Balanced: 234 mots (17.6%) → faible (peu de framing à enlever dans un stream of consciousness)
  Aggressive: 98 mots (65.5%) → OK

Test 3 (pièges FR, 283 mots) :
  Light: 176 mots (37.8%) → OK
  Balanced: 197 mots (30.4%) → OK (annulations + restructuration)
  Aggressive: 73 mots (74.2%) → OK

Target idéal (Gemini) : Light ~70%, Balanced ~35-40%, Aggressive ~65%
→ Light et Aggressive tiennent les cibles. Balanced est en dessous sur les prompts à forte densité d'instructions (email sequence: 31% au lieu de 35-40%).
