"""Récupération contextuelle de la mémoire user/tenant."""

from typing import Any, Dict, List, Optional

from backend.memory.memory_embeddings import embed_text
from backend.memory.memory_index import MemoryIndex, memory_index
from backend.memory.user_memory_service import UserMemoryService
from backend.memory.tenant_memory_service import TenantMemoryService


class MemoryRetriever:
    """Assemble le contexte mémoire pour enrichir les prompts."""

    def __init__(
        self,
        index: Optional[MemoryIndex] = None,
        user_svc: Optional[UserMemoryService] = None,
        tenant_svc: Optional[TenantMemoryService] = None,
    ):
        self.index = index or memory_index
        self.user_svc = user_svc or UserMemoryService()
        self.tenant_svc = tenant_svc or TenantMemoryService()

    def retrieve_for_prompt(
        self, tenant_id: str, user_id: str, prompt: str, top_k: int = 5,
    ) -> Dict[str, Any]:
        user_profile = self.user_svc.get_profile(tenant_id, user_id)
        tenant_knowledge = self.tenant_svc.get_validated_knowledge(tenant_id)
        query_vec = embed_text(prompt)
        semantic_hits = self.index.search(
            query_vec, tenant_id, top_k=top_k, min_score=0.25,
        )
        context_lines = []
        if user_profile.get("preferences"):
            prefs = user_profile["preferences"]
            if prefs.get("language"):
                val = prefs["language"]["value"] if isinstance(prefs["language"], dict) else prefs["language"]
                context_lines.append(f"Langue préférée: {val}")
            if prefs.get("tone"):
                val = prefs["tone"]["value"] if isinstance(prefs["tone"], dict) else prefs["tone"]
                context_lines.append(f"Ton: {val}")
            if prefs.get("format"):
                val = prefs["format"]["value"] if isinstance(prefs["format"], dict) else prefs["format"]
                context_lines.append(f"Format: {val}")
            if prefs.get("style"):
                val = prefs["style"]["value"] if isinstance(prefs["style"], dict) else prefs["style"]
                context_lines.append(f"Style: {val}")
        for item in tenant_knowledge[:10]:
            context_lines.append(f"Terme métier [{item['category']}]: {item['term']} — {item.get('definition', '')}")
        for entry, score in semantic_hits:
            context_lines.append(f"[{entry.owner_type}:{score:.2f}] {entry.content[:200]}")
        return {
            "user_profile": user_profile,
            "tenant_knowledge_count": len(tenant_knowledge),
            "semantic_hits": [
                {"content": e.content, "score": round(s, 3), "owner_type": e.owner_type}
                for e, s in semantic_hits
            ],
            "context_prefix": "\n".join(context_lines),
            "cache_hint": len(semantic_hits) > 0,
        }

    def estimate_token_savings(self, context: Dict[str, Any]) -> int:
        """Estime les tokens économisés grâce au cache/contexte réutilisé."""
        hits = len(context.get("semantic_hits", []))
        return hits * 50
