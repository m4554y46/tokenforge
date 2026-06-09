"""Résumé et compaction de la mémoire longue durée."""

from collections import Counter
from typing import Any, Dict, List

from backend.core.database_v2 import execute, _param
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
            val = prefs["language"]["value"] if isinstance(prefs["language"], dict) else prefs["language"]
            lines.append(f"Communique en {val}")
        if prefs.get("tone"):
            val = prefs["tone"]["value"] if isinstance(prefs["tone"], dict) else prefs["tone"]
            lines.append(f"Préfère un ton {val}")
        if prefs.get("format"):
            val = prefs["format"]["value"] if isinstance(prefs["format"], dict) else prefs["format"]
            lines.append(f"Format favori: {val}")
        if prefs.get("favorite_model"):
            val = prefs["favorite_model"]["value"] if isinstance(prefs["favorite_model"], dict) else prefs["favorite_model"]
            lines.append(f"Modèle favori: {val}")
        constraints = prefs.get("constraints", {})
        if isinstance(constraints, dict):
            vals = constraints.get("value", [])
        elif isinstance(constraints, list):
            vals = constraints
        else:
            vals = []
        if vals:
            lines.append(f"Contraintes: {', '.join(str(v) for v in vals[:5])}")
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
            keep_keys = set(sorted_keys[:max_keys])
            drop_keys = set(prefs.keys()) - keep_keys
            for k in keep_keys:
                v = prefs[k]
                val = v["value"] if isinstance(v, dict) else v
                self.user_svc.set_preference(tenant_id, user_id, k, val)
            for k in drop_keys:
                p = _param()
                execute(
                    f"DELETE FROM user_memory WHERE tenant_id={p} AND user_id={p} AND key={p}",
                    (tenant_id, user_id, k),
                )
            return {"compacted": True, "removed": len(prefs) - max_keys}
        return {"compacted": False}
