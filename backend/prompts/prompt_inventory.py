"""Inventaire des prompts — fréquence, coût, compressibilité."""

import hashlib
from typing import Any, Dict, List, Optional

from backend.core.database_v2 import query_all, _param
from backend.token_counter import count_tokens


class PromptInventory:
    """Catalogue analytique de tous les prompts observés."""

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def list_prompts(self, tenant_id: str, limit: int = 100, sort: str = "cost") -> List[Dict]:
        p = _param()
        order = {
            "cost": "total_cost DESC",
            "frequency": "count DESC",
            "savings": "avg_savings DESC",
        }.get(sort, "total_cost DESC")
        return query_all(
            f"SELECT prompt_hash, MAX(prompt_preview) as preview, COUNT(*) as count, "
            f"SUM(cost_usd) as total_cost, AVG(savings_percent) as avg_savings, "
            f"SUM(input_tokens) as total_tokens, MAX(model) as last_model "
            f"FROM prompt_events WHERE tenant_id={p} "
            f"GROUP BY prompt_hash ORDER BY {order} LIMIT {p}",
            (tenant_id, limit),
        )

    def top_prompts(self, tenant_id: str, n: int = 10) -> Dict[str, List]:
        return {
            "most_used": self.list_prompts(tenant_id, n, "frequency"),
            "most_expensive": self.list_prompts(tenant_id, n, "cost"),
            "most_compressible": self.list_prompts(tenant_id, n, "savings"),
        }

    def estimate_compressibility(self, text: str, profile: str = "balanced") -> Dict[str, Any]:
        original = count_tokens(text, "gpt-4o")
        try:
            from backend.spc.pipeline import SPC
            from backend.spc.profiles import get_profile
            spc = SPC(profile=get_profile(profile))
            result = spc.compile(text)
            compressed = count_tokens(result.compressed, "gpt-4o")
            savings = round((1 - compressed / max(original, 1)) * 100, 1)
            return {
                "original_tokens": original, "compressed_tokens": compressed,
                "savings_percent": savings, "compressible": savings > 10,
                "profile": profile, "fallback": result.fallback,
            }
        except Exception as exc:
            return {"original_tokens": original, "compressible": False, "error": str(exc)}

    def dashboard_stats(self, tenant_id: str) -> Dict[str, Any]:
        p = _param()
        row = query_all(
            f"SELECT COUNT(DISTINCT prompt_hash) as unique_prompts, COUNT(*) as total_calls, "
            f"SUM(cost_usd) as total_cost, AVG(savings_percent) as avg_savings "
            f"FROM prompt_events WHERE tenant_id={p}",
            (tenant_id,),
        )
        return dict(row[0]) if row else {}
