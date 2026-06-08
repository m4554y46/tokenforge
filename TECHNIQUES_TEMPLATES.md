# Templates — TokenForge

## Qu'est-ce qu'un template ?

Un **template** est un prompt pré-écrit que vous pouvez sauvegarder et réutiliser.  
Il évite de retaper manuellement les mêmes instructions, structures ou contextes.

Exemple : vous avez un prompt type pour analyser des logs, faire une traduction, ou poser un cahier des charges. Au lieu de le réécrire à chaque fois, vous le sauvegardez comme template et le chargez en 1 clic.

---

## Créer un template

1. **Onglet Optimizer** → écrivez votre prompt dans le champ principal.
2. Cliquez sur **Templates** dans le menu de gauche.
3. Cliquez sur **+ Nouveau**.
4. Remplissez :
   - **Nom** : un titre clair (ex: "Traduction FR→EN technique")
   - **Catégorie** : general / coding / writing / analysis / creative
   - **Contenu** : le texte du template (peut contenir des variables `{sujet}`)
5. Cliquez **Créer**.

> **Raccourci** : depuis l'Optimizer, cliquez sur le bouton **Template** (icône 📋) pour sauvegarder le prompt en cours sans quitter la vue.

---

## Charger un template

Dans l'**Optimizer**, utilisez le menu déroulant **"— Charger un template —"**  
en haut du champ de saisie. La sélection remplace immédiatement le contenu du champ par le template choisi.

---

## Gérer les templates

| Action | Où |
|---|---|
| Créer | Vue Templates → + Nouveau, ou Optimizer → bouton Template |
| Utiliser | Optimizer → menu déroulant "Charger un template" |
| Supprimer | Vue Templates → clic sur la poubelle d'un template |

---

## Anatomie d'un template

```
Analyse les logs suivants et identifie les erreurs critiques.
Contexte : {contexte}
Format de sortie : liste bullet points
```

Les parties entre `{...}` sont des **variables** à remplacer manuellement après chargement.  
Le template est un simple texte — aucune syntaxe spéciale n'est requise.

---

## Bonnes pratiques

1. **Nommez clairement** — "Traduction FR→EN" plutôt que "Template 1"
2. **Utilisez des variables** `{...}` pour les parties changeantes
3. **Catégorisez** pour retrouver facilement
4. **Gardez les templates courts** (< 500 tokens pour un chargement rapide)
5. **Versionnez** : ajoutez la date ou le numéro dans le nom si vous itérez

---

## Fonctionnement interne

Les templates sont stockés dans la base SQLite locale (`tokenforge.db`), table `templates`.  
Ils sont chiffrés au même niveau que les prompts dans l'historique.  
Le chargement via le menu déroulant déclenche :

1. Requête `GET /api/templates` → liste des templates
2. Sélection utilisateur → `loadTemplate()` injecte le contenu dans le textarea
3. Le compteur de tokens se met à jour automatiquement

---

## Questions fréquentes

**Q : Puis-je avoir des templates avec plusieurs parties ?**  
R : Oui, utilisez des séparateurs comme `---` ou `## Section` dans le texte.

**Q : Les templates sont-ils partagés entre plusieurs postes ?**  
R : Non, chaque installation a sa propre base locale. Pas de sync cloud pour l'instant.

**Q : Puis-je exporter mes templates ?**  
R : Pas d'export natif, mais la base `tokenforge.db` est un fichier SQLite standard.

**Q : Que faire si un template ne se charge pas ?**  
R : Vérifiez que le backend est en ligne (`http://127.0.0.1:8765/api/health`).  
Les templates sont chargés via l'API — si le backend est down, le menu reste vide.
