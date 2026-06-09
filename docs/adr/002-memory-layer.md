# ADR-002 — Memory Layer

## Statut
Accepté

## Contexte
Réduire tokens et latence en apprenant les habitudes user/tenant.

## Décision
- Profils utilisateur en SQL (`user_memory`)
- Connaissances tenant en SQL (`tenant_memory`) avec validation manuelle
- Embeddings via SentenceTransformers avec fallback hash déterministe
- Index vectoriel Qdrant avec fallback in-memory

## ROI client
- Moins de tokens répétitifs dans les prompts
- Personnalisation automatique (langue, ton, format)
- Terminologie métier injectée sans re-saisie
