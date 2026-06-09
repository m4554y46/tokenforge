"""Résumé et compaction de la mémoire longue durée."""

from collections import Counter
from typing import Any, Dict, List

from backend.memory.user_memory_service import UserMemoryService
from backend.memory.tenant_memory_service import TenantMemoryService


class MemorySummarizer:
    """Produit des résumés exploitables pour le dashboard et l'injection prompt."""

    def __init__(self):
        self.user_svc = UserMemoryService()
        self.tenant_svc = TenantMemoryService()

    def summarize_user(self, tenant_id: str, user_id: str) -> Dict[str, Any]:
        profile = self.user_svc.get_profile(tenant_id, user_id)
        prefs = profile.get("preferences", {})
        lines = []
        if prefs.get("language"):
            lines.append(f"Communique en {prefs['language']}")
        if prefs.get("tone"):
            lines.append(f"Préfère un ton {prefs['tone']}")
        if prefs.get("format"):
            lines.append(f"Format favori: {prefs['format']}")
        if prefs.get("favorite_model"):
            lines.append(f"Modèle favori: {prefs['favorite_model']}")
        constraints = prefs.get("constraints", [])
        if constraints:
            lines.append(f"Contraintes: {', '.join(constraints[:5])}")
        return {
            "summary": ". ".join(lines) if lines else "Profil en cours d'apprentissage",
            "preference_count": len(prefs),
            "profile": profile,
        }

    def summarize_tenant(self, tenant_id: str) -> Dict[str, Any]:
        knowledge = self.tenant_svc.list_all(tenant_id)
        by_category = Counter(k["category"] for k in knowledge)
        validated = sum(1 for k in knowledge if k.get("validated"))
        top_terms = [k["term"] for k in knowledge[:20]]
        return {
            "total_terms": len(knowledge),
            "validated_count": validated,
            "by_category": dict(by_category),
            "top_terms": top_terms,
            "summary": f"{len(knowledge)} termes métier, {validated} validés",
        }

    def compact_profile(self, tenant_id: str, user_id: str, max_keys: int = 20) -> Dict[str, Any]:
        profile = self.user_svc.get_profile(tenant_id, user_id)
        prefs = profile.get("preferences", {})
        if len(prefs) > max_keys:
            sorted_keys = sorted(prefs.keys(), key=lambda k: prefs[k].get("confidence", 0) if isinstance(prefs[k], dict) else 1, reverse=True)
            trimmed = {k: prefs[k] for k in sorted_keys[:max_keys]}
            for k, v in trimmed.items():
                val = v["value"] if isinstance(v, dict) else v
                self.user_svc.set_preference(tenant_id, user_id, k, val)
            return {"compacted": True, "removed": len(prefs) - max_keys}
        return {"compacted": False}
