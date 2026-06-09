# ADR-003 — FinOps & Governance

## Statut
Accepté

## Contexte
Les DSI ont besoin de visibilité budget, contrôle et conformité.

## Décision
- `prompt_events` comme source de vérité pour tous les coûts
- Budgets par scope (user/team/app/tenant) avec alertes à 80%
- Rule engine synchrone évalué avant chaque routage gateway
- Frameworks RGPD/SOC2/ISO27001 comme checklists configurables

## ROI client
- Prévisions et détection d'anomalies évitent les dépassements
- ROI calculable et présentable au COMEX
- Politiques bloquent les usages à risque avant facturation
