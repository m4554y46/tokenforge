"""Prévisions de coûts — mensuelles, trimestrielles, annuelles."""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from backend.core.database_v2 import query_all, _param


class ForecastEngine:
    """Projette les dépenses LLM à partir de l'historique."""

    def _daily_costs(self, tenant_id: str, days: int = 90) -> List[Dict]:
        p = _param()
        return query_all(
            f"SELECT DATE(created_at) as day, SUM(cost_usd) as cost, COUNT(*) as requests "
            f"FROM prompt_events WHERE tenant_id={p} "
            f"AND created_at >= datetime('now', '-' || {p} || ' days') "
            f"GROUP BY DATE(created_at) ORDER BY day",
            (tenant_id, str(days)),
        )

    def forecast(self, tenant_id: str, horizon: str = "monthly") -> Dict[str, Any]:
        days_map = {"monthly": 30, "quarterly": 90, "annual": 365}
        horizon_days = days_map.get(horizon, 30)
        daily = self._daily_costs(tenant_id, min(horizon_days, 90))
        if not daily:
            return {"horizon": horizon, "projected_usd": 0, "confidence": "low", "daily_avg": 0}
        costs = [d["cost"] or 0 for d in daily]
        daily_avg = sum(costs) / len(costs)
        projected = daily_avg * horizon_days
        trend = 0.0
        if len(costs) >= 7:
            recent = sum(costs[-7:]) / 7
            older = sum(costs[:7]) / min(7, len(costs))
            trend = (recent - older) / older if older else 0
        adjusted = projected * (1 + trend * 0.5)
        return {
            "horizon": horizon,
            "projected_usd": round(adjusted, 2),
            "daily_avg_usd": round(daily_avg, 4),
            "trend_percent": round(trend * 100, 1),
            "confidence": "high" if len(daily) >= 14 else "medium" if len(daily) >= 7 else "low",
            "data_points": len(daily),
        }

    def forecast_all(self, tenant_id: str) -> Dict[str, Dict]:
        return {
            "monthly": self.forecast(tenant_id, "monthly"),
            "quarterly": self.forecast(tenant_id, "quarterly"),
            "annual": self.forecast(tenant_id, "annual"),
        }
