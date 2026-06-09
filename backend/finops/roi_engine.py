"""Calcul ROI — coût initial vs optimisé vs coût TokenForge."""

from typing import Any, Dict, Optional

from backend.config import get_settings
from backend.core.database_v2 import query_one, _param


class ROIEngine:
    """Démontre la valeur économique de TokenForge au DSI."""

    def __init__(self):
        self.settings = get_settings()

    def calculate(
        self, tenant_id: str, days: int = 30,
        tokenforge_cost_per_1k: Optional[float] = None,
    ) -> Dict[str, Any]:
        from datetime import datetime, timedelta
        p = _param()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        row = query_one(
            f"SELECT SUM(cost_usd) as total_cost, "
            f"SUM(CASE WHEN compressed=1 THEN cost_usd ELSE 0 END) as optimized_cost, "
            f"SUM(input_tokens) as total_tokens, "
            f"AVG(CASE WHEN compressed=1 THEN savings_percent ELSE 0 END) as avg_savings "
            f"FROM prompt_events WHERE tenant_id={p} "
            f"AND created_at >= {p}",
            (tenant_id, cutoff),
        )
        total_cost = (row or {}).get("total_cost") or 0
        optimized_cost = (row or {}).get("optimized_cost") or 0
        total_tokens = (row or {}).get("total_tokens") or 0
        avg_savings = (row or {}).get("avg_savings") or 0

        if optimized_cost > 0 and total_cost > optimized_cost:
            baseline_cost = total_cost
            actual_cost = optimized_cost
        else:
            savings_rate = max(avg_savings, 25) / 100
            baseline_cost = total_cost / (1 - savings_rate) if savings_rate < 1 else total_cost
            actual_cost = total_cost

        savings = max(baseline_cost - actual_cost, 0)
        tf_rate = tokenforge_cost_per_1k or self.settings.TOKENFORGE_COST_PER_1K_TOKENS
        tokenforge_cost = (total_tokens / 1000) * tf_rate
        net_roi = savings - tokenforge_cost
        roi_percent = (net_roi / tokenforge_cost * 100) if tokenforge_cost > 0 else 0

        return {
            "period_days": days,
            "baseline_cost_usd": round(baseline_cost, 2),
            "optimized_cost_usd": round(actual_cost, 2),
            "gross_savings_usd": round(savings, 2),
            "tokenforge_cost_usd": round(tokenforge_cost, 2),
            "net_roi_usd": round(net_roi, 2),
            "roi_percent": round(roi_percent, 1),
            "total_tokens": total_tokens,
            "avg_savings_percent": round(avg_savings, 1),
            "verdict": "positive" if net_roi > 0 else "neutral",
        }
