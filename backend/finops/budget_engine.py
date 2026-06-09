"""Moteur de budgets — user, équipe, application, tenant."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.core.database_v2 import query_all, query_one, execute, _param
from backend.finops.cost_registry import CostRegistry


class BudgetEngine:
    """Gère budgets et alertes de dépassement."""

    SCOPES = ("user", "team", "application", "tenant")

    def __init__(self):
        self.cost_registry = CostRegistry()

    def set_budget(
        self, tenant_id: str, scope_type: str, scope_id: str,
        amount_usd: float, period: str = "monthly", alert_threshold: float = 0.8,
    ) -> Dict[str, Any]:
        p = _param()
        now = datetime.now().isoformat()
        execute(
            f"INSERT OR REPLACE INTO budgets (tenant_id, scope_type, scope_id, amount_usd, period, spent_usd, alert_threshold, created_at) "
            f"VALUES ({p},{p},{p},{p},{p},0,{p},{p})",
            (tenant_id, scope_type, scope_id, amount_usd, period, alert_threshold, now),
        )
        return {"scope_type": scope_type, "scope_id": scope_id, "amount_usd": amount_usd, "period": period}

    def get_budgets(self, tenant_id: str) -> List[Dict]:
        p = _param()
        return query_all(f"SELECT * FROM budgets WHERE tenant_id={p}", (tenant_id,))

    def check_budget(self, tenant_id: str, scope_type: str, scope_id: str, additional_cost: float = 0) -> Dict[str, Any]:
        p = _param()
        budget = query_one(
            f"SELECT * FROM budgets WHERE tenant_id={p} AND scope_type={p} AND scope_id={p}",
            (tenant_id, scope_type, scope_id),
        )
        if not budget:
            return {"allowed": True, "reason": "no_budget"}
        spent = (budget["spent_usd"] or 0) + additional_cost
        limit = budget["amount_usd"]
        utilization = spent / limit if limit else 0
        alert = utilization >= budget.get("alert_threshold", 0.8)
        return {
            "allowed": spent <= limit,
            "spent_usd": round(spent, 4),
            "limit_usd": limit,
            "utilization": round(utilization, 3),
            "alert": alert,
        }

    def increment_spent(self, tenant_id: str, scope_type: str, scope_id: str, amount: float) -> None:
        p = _param()
        execute(
            f"UPDATE budgets SET spent_usd = spent_usd + {p} WHERE tenant_id={p} AND scope_type={p} AND scope_id={p}",
            (amount, tenant_id, scope_type, scope_id),
        )

    def get_alerts(self, tenant_id: str) -> List[Dict]:
        budgets = self.get_budgets(tenant_id)
        alerts = []
        for b in budgets:
            util = (b["spent_usd"] or 0) / b["amount_usd"] if b["amount_usd"] else 0
            if util >= b.get("alert_threshold", 0.8):
                alerts.append({
                    "scope_type": b["scope_type"], "scope_id": b["scope_id"],
                    "utilization": round(util, 3), "spent": b["spent_usd"], "limit": b["amount_usd"],
                })
        return alerts
