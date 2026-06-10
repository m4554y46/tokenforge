# Formalisation mathématique — ACE v2 (Adaptive Compression Engine)

> **Idée centrale :** Au lieu d'apprendre quel taux de compression fonctionne
> (approche bandit classique), ACE apprend **la perte d'utilité** causée par
> chaque taux de compression, et maximise la marge économique nette sous
> contrainte de qualité. L'exploration est déclenchée uniquement quand elle
> peut changer la décision future — Knowledge Gradient pur, pas de ε-greedy.

---

## 1. Modèle de qualité (Quality Proxy)

### 1.1 Données observées

Pour chaque requête compressée au taux $r$, on observe :

| Variable | Symbole | Source |
|----------|---------|--------|
| Contexte | $x$ | `features.py` — task, specificity, length, cluster |
| Taux de compression | $r$ | Décision ACE |
| Signaux comportementaux | $s$ | `signals.py` — reformulation, continuation |
| Qualité proxy | $\tilde{q}$ | `QualityModel.predict(x, s)` — LightGBM |
| Pseudo-label | $y$ | `_pseudo_label(s)` — règle heuristique |

### 1.2 Modèle — LightGBM probabiliste

Au lieu d'un Beta-Bernoulli (V1), on utilise **LightGBM** avec Platt scaling :

$$P(\text{qualité préservée} \mid x, r, s) = \sigma\big(f_{LightGBM}(x, r, s)\big)$$

où $\sigma$ est la fonction sigmoïde.

**Pourquoi LightGBM plutôt que Beta-Bernoulli :**

| Aspect | Beta-Bernoulli (V1) | LightGBM (V2) |
|--------|---------------------|---------------|
| Corrélations entre signaux | Ignorées (indépendance) | Naturelles (arbres) |
| Cold-start | Uniforme | Pooling par embeddings |
| Haute dimension (>10 features) | Impossible | Efficace |
| Incertitude | Analytique | Approximative (variance des arbres) |
| Latence | ~0.1 ms | ~3 ms (ONNX) |

**Architecture des features (80–120 dimensions) :**

```
x_encoded = concat[
    one_hot(task_type),       # 8 → 8 dimensions
    one_hot(specificity),     # 3 → 3 dimensions
    one_hot(length_bucket),   # 4 → 4 dimensions
    one_hot(cluster % 20),    # 20 → 20 dimensions
    one_hot(model),           # ~10 → 10 dimensions
    scalar(rate),             # 1 dimension
    scalar(log(token_count)), # 1 dimension
    one_hot(model // rate),   # ~60 dimensions (interactions)
]
```

Avec signaux :

```
x_signal = concat[
    x_encoded,
    scalar(s.quality_proxy),  # 1 dimension
    binary(s.reformulation),  # 1 dimension
    binary(s.continuation),   # 1 dimension
    scalar(s.confidence),     # 1 dimension
]
```

### 1.3 Pseudo-labels pour l'entraînement

Faute de jugement humain, on utilise des règles heuristiques :

```
y = 0.3  si reformulation AND NOT continuation  (échec probable)
y = 0.7  si continuation AND NOT reformulation    (succès probable)
y = 0.5  si aucun signal                           (incertain)
y = 0.9  si reformulation + continuation           (contradictoire)
```

Ces pseudo-labels sont **imparfaits mais suffisants** pour initialiser le modèle.
La calibration se fera avec >500 échantillons annotés manuellement.

### 1.4 Inférence en production

Le modèle entraîné est exporté en **ONNX** (~2 MB, ~3ms inférence CPU).

```python
q = quality_model.predict(features, signals)  # → [0, 1]
```

---

## 2. Cellules d'état (Cell State)

Chaque configuration $(tenant, cluster, task, length, model, rate)$ a une cellule :

$$g(r, x) = \frac{\text{quality\_sum}}{\text{n\_samples}}$$

### 2.1 Cold-start

Quand $n_{samples} < 5$ :

1. **Embeddings de compressibilité** : $g_{cold}(r, x) = \text{pool\_kNN}(x, r)$
2. **Fallback** : $g_{cold}(r, x) = 0.85$ (valeur prudente)

### 2.2 Mise à jour conditionnelle

Une cellule n'est mise à jour que si l'attribution confirme que la compression
est la cause probable du signal (cf. §5). Sinon, le signal est ignoré.

---

## 3. Fonction d'utilité économique

### 3.1 Définition

$$U(r,x) = S(r,x) \cdot TF_{share} - C_{TF}(r) - \big[1 - g(r,x)\big] \cdot C_{fail}$$

| Terme | Symbole | Définition |
|-------|---------|------------|
| Économies brutes | $S(r,x)$ | $N_{tokens} \cdot r \cdot p_{token}$ |
| Part TokenForge | $TF_{share}$ | 30% |
| Coût de calcul | $C_{TF}(r)$ | Selon profil (0–0.0005 $/req) |
| Risque d'échec | $C_{fail}$ | $C_{reformulation} + C_{support} + C_{qualité}$ = $0.02$ $/req |

### 3.2 Bypass (r = 0)

Le bypass est toujours disponible : $U(0, x) = 0$. ACE ne compresse que si
$U(r, x) > 0$ pour au moins un $r > 0$.

### 3.3 Contraintes

La compression est désactivée si :
- $U(r, x) \leq 0$ pour tout $r$ (marge négative)
- $g(r, x) < 0.80$ (qualité trop basse)
- $N_{tokens} < 50$ (prompts trop courts)
- $S(r,x) \cdot (1 - TF_{share}) < 0.001$ \$ (client ne voit pas l'économie)

### 3.4 Décision finale

$$r^* = \arg\max_{r \in R \cup \{0\}} U(r, x)$$

---

## 4. Exploration par Knowledge Gradient

### 4.1 Principe

ACE n'explore jamais par ε-greedy ou Upper Confidence Bound.
L'exploration est un **investissement informationnel** : on explore un taux $r$
uniquement si l'information obtenue peut **changer la décision future**.

Formellement : on explore $r$ si le Knowledge Gradient $KG_j > 0$, c'est-à-dire
si l'information attendue sur $g(r,x)$ peut faire basculer $r^*$ vers une
décision différente.

### 4.2 Formule du Knowledge Gradient

$$KG_j = \sigma_j \cdot \phi\!\left(\frac{\Delta_j}{\sigma_j}\right) + |\Delta_j| \cdot \Phi\!\left(\frac{|\Delta_j|}{\sigma_j}\right) - |\Delta_j|$$

où :
- $\sigma_j$ = incertitude sur $g(r_j, x)$ (écart-type de la cellule)
- $\Delta_j = g(r_j, x) - g(r^*, x)$ = écart entre ce bras et le meilleur bras connu
- $\phi$ = densité de la normale centrée réduite
- $\Phi$ = fonction de répartition de la normale centrée réduite

### 4.3 Interprétation

- Si $\sigma_j \approx 0$ (bras bien connu) → $KG_j \approx 0$ → pas d'exploration
- Si $\Delta_j \gg \sigma_j$ (bras très mauvais) → $KG_j \approx 0$ → pas d'exploration
- Si $\Delta_j \approx 0$ (bras compétitif avec le meilleur, mais incertain) → $KG_j$ maximal

### 4.4 Activation

L'exploration est activée uniquement si :
1. **Âge du contrat ≥ 90 jours** (jamais d'exploration sur les nouveaux clients)
2. **Tenant autorise l'exploration** (opt-in)
3. **$KG_j > 0$** pour au moins un bras alternatif

```python
def pick_exploration_arm(cells, token_count, price_per_token,
                         contract_age_days, tenant_allows_exploration):
    if contract_age_days < 90 or not tenant_allows_exploration:
        return None  # pas d'exploration
    best_rate = argmax U(r, x)
    for rate in cells:
        kg = knowledge_gradient(cells[rate], cells[best_rate])
        if kg > 0:
            return rate  # explore ce bras
    return None
```

---

## 5. Attribution causale

### 5.1 Problème

Un signal de reformulation peut être causé par :
1. **Compression** (le taux $r$ a dégradé la qualité)
2. **Modèle LLM** (hallucination, refus, incompétence)
3. **Utilisateur** (prompt ambigu, mal formulé)
4. **Contexte** (session trop longue, mémoire saturée)

Si on attribue à tort un échec du LLM à la compression, le bandit va
sous-estimer systématiquement la qualité des taux élevés et finir par
toujours choisir le bypass — **TokenForge ne gagne rien**.

### 5.2 Modèle d'attribution

$$P(cause = c \mid s, x) = \frac{score_c}{\sum_{k} score_k}$$

avec :

| Cause | Formule | Intuition |
|-------|---------|-----------|
| Compression | $0.1 \cdot (1 - g(r,x))$ | Proportionnelle à la perte de qualité attendue |
| Modèle | $0.4 \cdot (1 - reliability(model))$ | Pondéré par la fiabilité du LLM |
| Utilisateur | $0.3 \cdot (1 - user\_history\_quality)$ | Pondéré par l'historique utilisateur |
| Contexte | $0.2 \cdot \min(complexité, 0.5) / 0.5$ | Proportionnel à la complexité du prompt |

### 5.3 Règle de mise à jour

```python
def should_update_quality(attribution):
    if attribution.is_compression_failure:
        return True   # mise à jour immédiate
    if attribution.cause == "model" and attribution.confidence > 0.7:
        return False  # ne pas pénaliser la compression
    if attribution.cause == "user" and attribution.confidence > 0.6:
        return False  # ne pas pénaliser la compression
    return True       # cas ambigus → mise à jour prudente
```

---

## 6. Embeddings de compressibilité

### 6.1 Idée

Deux contextes sont similaires s'ils répondent **de la même manière** aux
différents taux de compression. On ne mesure pas la similarité sémantique
mais la **similarité de comportement face à la compression**.

### 6.2 Construction

Soit $M$ la matrice $contextes \times taux$ où $M_{ij} = g(r_j, x_i)$.
On factorise :

$$M \approx U \cdot V^T$$

avec $U \in \mathbb{R}^{n_{contextes} \times d}$, $V \in \mathbb{R}^{n_{taux} \times d}$,
$d = 4$ (4 dimensions latentes).

L'embedding d'un contexte $x_i$ est la ligne $U_i$, et l'embedding d'un taux
$r_j$ est la ligne $V_j$.

### 6.3 Cold-start

Pour un nouveau contexte $x_{new}$ :
1. On calcule son embedding MiniLM $e_{new} \in \mathbb{R}^{384}$
2. On trouve ses $k=5\) plus proches voisins parmi les contextes connus
3. On moyenne leurs $g(r, x)$ :

$$g_{cold}(r, x_{new}) = \frac{1}{k} \sum_{i \in kNN(x_{new})} g(r, x_i)$$

### 6.4 Mise à jour

- Entraînement : toutes les nuits, ou tous les 1000 nouveaux contextes
- Export : $U$ et $V$ sauvegardés en `.npy` (~100 KB)

---

## 7. Boucle d'apprentissage complète

```
Requête API → 1. Extraction features (x)
             2. Lecture cellules (g(r,x))
             3. Calcul utilité (U(r,x))
             4. Exploration KG ?
             5. Décision (r*)
             6. Compression → Réponse LLM
             7. Requête suivante → Détection signaux (s)
             8. Attribution causale
             9. Mise à jour cellule (g conditionnelle)
                ↓ (batch, toutes les nuits)
            10. Entraînement QualityModel + Embeddings
```

**Latence totale :** ~3–5 ms par requête (hors compression elle-même).

---

## 8. Validation et métriques

| Métrique | Cible | Commentaire |
|----------|-------|-------------|
| AUC du quality model | > 0.85 | Sur validation set |
| Taux de reformulation | < 2% | Max 2% des requêtes compressées |
| Taux d'exploration | < 5% | Ratio des requêtes en exploration |
| Marge nette | > 0.001 $/req | Après coût TF + risque |
| Précision d'attribution | > 80% | Sur jeu de calibration |
| ROI client | > 20% | Économies / coût total |

---

## 9. Complexité et coût

| Opération | Temps | Fréquence |
|-----------|-------|-----------|
| Feature extraction | ~0.5 ms | Chaque requête |
| Lecture cellule (LRU) | ~0.1 ms | Chaque requête |
| Quality model (ONNX) | ~3 ms | Chaque mise à jour |
| Knowledge Gradient | ~0.1 ms | Chaque décision |
| Attribution | ~0.05 ms | Chaque signal |
| Entraînement | ~30 s | Toutes les nuits |

**Stockage :** 34,560 cellules × ~16 bytes = ~553 KB (pleine maturité).

---

## 10. Comparaison V1 → V2

| Aspect | V1 (Beta-Bernoulli) | V2 (ACE actuelle) |
|--------|---------------------|-------------------|
| Modèle de qualité | Beta conjugué | LightGBM + ONNX |
| Incertitude | Variance de Beta | Variance des arbres |
| Exploration | UCB | Knowledge Gradient |
| Attribution | Aucune | Bayes à 4 causes |
| Cold-start | Prior uniforme | Embeddings de compressibilité |
| Décision | Score qualité seul | Utilité économique nette |
| Coût d'échec | Churn (non calibré) | Reformulation + support |
