"""Détection d'anomalies de coût."""

import statistics
from typing import Any, Dict, List

from backend.core.database_v2 import query_all, _param


class AnomalyDetector:
    """Détecte explosions de coût et dérives comportementales."""

    def detect_cost_spikes(self, tenant_id: str, z_threshold: float = 2.5) -> List[Dict]:
        from datetime import datetime, timedelta
        p = _param()
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        daily = query_all(
            f"SELECT SUBSTR(created_at, 1, 10) as day, SUM(cost_usd) as cost FROM prompt_events "
            f"WHERE tenant_id={p} AND created_at >= {p} "
            f"GROUP BY day ORDER BY day",
            (tenant_id, cutoff),
        )
        if len(daily) < 5:
            return []
        costs = [float(d["cost"] or 0) for d in daily]
        mean = sum(costs) / len(costs)
        variance = sum((c - mean) ** 2 for c in costs) / len(costs)
        stdev = variance ** 0.5 if variance else 0
        anomalies = []
        for d, cost in zip(daily, costs):
            if stdev > 0:
                z = (cost - mean) / stdev
                if z >= z_threshold:
                    anomalies.append({
                        "day": d["day"], "cost_usd": cost,
                        "z_score": round(z, 2), "type": "cost_spike",
                        "severity": "critical" if z >= 3.5 else "warning",
                    })
        return anomalies

    def detect_user_drift(self, tenant_id: str, multiplier: float = 3.0) -> List[Dict]:
        from datetime import datetime, timedelta
        p = _param()
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        users = query_all(
            f"SELECT user_id, SUM(cost_usd) as total, COUNT(*) as requests "
            f"FROM prompt_events WHERE tenant_id={p} AND created_at >= {p} "
            f"GROUP BY user_id",
            (tenant_id, cutoff),
        )
        if len(users) < 2:
            return []
        totals = [u["total"] or 0 for u in users]
        median = statistics.median(totals)
        drifts = []
        for u in users:
            if median > 0 and (u["total"] or 0) > median * multiplier:
                drifts.append({
                    "user_id": u["user_id"], "cost_usd": u["total"],
                    "requests": u["requests"], "type": "user_drift",
                    "ratio_vs_median": round((u["total"] or 0) / median, 1),
                })
        return drifts

    def scan(self, tenant_id: str) -> Dict[str, Any]:
        spikes = self.detect_cost_spikes(tenant_id)
        drifts = self.detect_user_drift(tenant_id)
        return {
            "anomalies": spikes + drifts,
            "spike_count": len(spikes),
            "drift_count": len(drifts),
            "status": "alert" if spikes or drifts else "normal",
        }
