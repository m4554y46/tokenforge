# ADR 004 — ACE Phase 2-3 : Gates contractuelles & cascade UCB

**Date :** 11 juin 2026  
**Statut :** Implémenté  
**Contexte :** Audit théorique de l'architecture ACE révélant 12 trous de garantie (juin 2026)

## Décision

Ajouter 6 gates contractuelles au pipeline ACE et remplacer la cascade
linéaire par une cascade UCB non-monotone.

### Modules créés

| Module | Fichier | Rôle | Justification |
|--------|---------|------|---------------|
| **PIF** | `pif.py` | Prompt Information Footprint — entropie + redondance → headroom | Nécessité d'exemption contractuelle pour les prompts incompressibles (littérature : Shannon entropy, MDL) |
| **Integrity Gate** | `integrity_gate.py` | Entropy Gate (quenching dynamique) + Integrity Gate (post-check 4 vérifications) | Remplacer le 15% fixe par un seuil adaptatif ; détecter sorties vides/tronquées |
| **Quality Oracle** | `oracle.py` | Évaluation AND-logic : 5 dimensions seuillées indépendamment | Empêcher le gaming par moyenne — contrat respecté dimension par dimension |
| **Ensemble Judge** | `ensemble_judge.py` | Dawid-Skene EM : consensus multi-juge (GPT-4o, BLEU, ROUGE, heuristic) | Robustesse contre les juges aberrants — applis crowdsourcing (Dawid & Skene, 1979) |
| **Drift Detector** | `drift_detector.py` | MMD test avec noyau RBF, permutation test | Détecter la violation d'échangeabilité en production (Gretton et al., 2012) |
| **Reconstruction Monitor** | `reconstruction_monitor.py` | factual_loss (compression) vs novelty_gain (LLM) | Séparer les artefacts de compression de la créativité LLM |

### Modifications

| Fichier | Modification | Raison |
|---------|-------------|--------|
| `decider.py` | Cascade UCB non-monotone (tri par UCB décroissant) | 10-15% des prompts où "moins agressif" = meilleur — UCB explore l'incertain |
| `kompress.py` | Entropy Gate remplace le 15% fixe | Floor adaptatif basé sur l'entropie du prompt |
| `proxy.py` | Pipeline complet PIF → UCB → Integrity → Oracle | Intégration de toutes les gates dans l'ordre |
| `tables.py` | 3 nouvelles tables (calibration_samples, drift_events, oracle_evaluations) | Persistance des données de calibrage et surveillance |
| `state.py` | pif_headroom, integrity_passed dans ace_requests | Traçabilité contractuelle |

### Pipeline résultant

```
PIF (headroom < 5% → bypass)
  → Sanctuary (contenu protégé → plafonnement)
    → UCB Cascade (tri par UCB décroissant)
      → Compression SPC + Entropy Gate (quenching)
        → Integrity Gate (validation post-check)
          → Forward LLM
            → Reconstruction Monitor (factual_loss)
              → Oracle (AND-logic 5 dimensions)
                → Dawid-Skene consensus + Drift sample
```

### Références

- Dawid & Skene (1979). *Maximum Likelihood Estimation of Observer Error-Rates.*
- Gretton et al. (2012). *A Kernel Two-Sample Test.*
- Ipeirotis et al. (2010). *Quality Management on Amazon Mechanical Turk.*
- Shannon (1948). *A Mathematical Theory of Communication.*
- Delétang et al. (2023). *Language Modeling is Compression.*
