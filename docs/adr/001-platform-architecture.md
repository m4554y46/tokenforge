# ADR-001 — Architecture TokenForge Intelligence Platform

## Statut
Accepté

## Contexte
TokenForge v1 est un compresseur de prompts desktop (Electron + FastAPI + SPC).
La v2 doit devenir une plateforme enterprise multi-tenant sans régression.

## Décision
- **Conserver** l'API v1 (`/api/*`) et le pipeline SPC inchangés
- **Ajouter** l'API v2 (`/api/v2/*`) pour les capacités enterprise
- **Backend** : FastAPI monolithique modulaire (pas de microservices initiaux)
- **Stockage** : SQLite en dev, PostgreSQL en prod ; Redis/Qdrant optionnels avec fallback mémoire
- **Frontend** : portail Next.js séparé + UI Electron legacy conservée

## Conséquences
- Zéro breaking change pour les clients v1
- Déploiement simplifié (un seul binaire Python)
- Scalabilité horizontale via load balancer + PostgreSQL/Redis partagés
