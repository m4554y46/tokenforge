"""Dashboard qualité ACE — agrégation des métriques de compression.

Interroge la base de données ACE et produit des statistiques agrégées
par tenant, profil de compression, type de tâche, et période.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from backend.ace.state import RATE_TO_PROFILE, TF_SHARE
from backend.core.database_v2 import query_all, query_one, _param

logger = logging.getLogger(__name__)


def _q(sql: str, params: tuple = ()):
    p = _param()
    return query_all(sql.replace("?", p), params)


def _safe_quality(val) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def get_dashboard_data(
    tenant_id: str,
    days: int = 7,
) -> Dict[str, Any]:
    """Aggrège les métriques qualité ACE pour un tenant sur N jours."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # --- Stats générales depuis ace_states ---
    rows = _q("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN (quality_sum / NULLIF(n_samples, 0)) >= 0.7 THEN 1 ELSE 0 END) as good,
               SUM(CASE WHEN (quality_sum / NULLIF(n_samples, 0)) < 0.3 AND n_samples > 0 THEN 1 ELSE 0 END) as poor,
               AVG(quality_sum / NULLIF(n_samples, 0)) as avg_quality,
               AVG(rate) as avg_rate
        FROM ace_states
        WHERE tenant_id = ? AND last_updated >= ?
    """, (tenant_id, since))
    general = rows[0] if rows else {}
    total = general.get("total", 0) or 0

    # --- Ventilation par profil ---
    by_profile_rows = _q("""
        SELECT rate, AVG(quality_sum / NULLIF(n_samples, 0)) as q,
               COUNT(*) as n
        FROM ace_states
        WHERE tenant_id = ? AND last_updated >= ?
        GROUP BY rate
        ORDER BY rate
    """, (tenant_id, since))
    by_profile = []
    for row in by_profile_rows:
        r = float(row["rate"])
        profile = RATE_TO_PROFILE.get(r, f"r={r}")
        by_profile.append({
            "profile": profile,
            "rate": r,
            "avg_quality": _safe_quality(row["q"]),
            "count": row["n"],
        })

    # --- Ventilation par type de tâche ---
    by_task_rows = _q("""
        SELECT task_type,
               AVG(quality_sum / NULLIF(n_samples, 0)) as q,
               AVG(rate) as r,
               COUNT(*) as n,
               SUM(CASE WHEN (quality_sum / NULLIF(n_samples, 0)) >= 0.7 THEN 1 ELSE 0 END) as good_count
        FROM ace_states
        WHERE tenant_id = ? AND last_updated >= ?
        GROUP BY task_type
        ORDER BY n DESC
    """, (tenant_id, since))
    by_task = []
    for row in by_task_rows:
        n = row["n"]
        by_task.append({
            "task_type": row["task_type"],
            "avg_quality": _safe_quality(row["q"]),
            "avg_rate": float(row["r"]) if row["r"] else 0,
            "count": n,
            "good_ratio": round(row["good_count"] / n, 3) if n else 0,
        })

    # --- Économies estimées depuis ace_requests ---
    savings_rows = _q("""
        SELECT SUM(tokens_original - tokens_compressed) as total_saved,
               COUNT(*) as req_count,
               AVG(savings_percent) as avg_savings_pct
        FROM ace_requests
        WHERE tenant_id = ? AND created_at >= ?
    """, (tenant_id, since))
    sr = savings_rows[0] if savings_rows else {}
    total_tokens_saved = sr.get("total_saved", 0) or 0
    req_count = sr.get("req_count", 0) or 0
    avg_savings_pct = round(float(sr.get("avg_savings_pct", 0) or 0), 2)
    client_price = 5.0 / 1_000_000
    estimated_savings_usd = round(total_tokens_saved * client_price * TF_SHARE, 2)

    # --- Alertes ---
    alerts = []

    low_q_rows = _q("""
        SELECT rate, AVG(quality_sum / NULLIF(n_samples, 0)) as q,
               COUNT(*) as n
        FROM ace_states
        WHERE tenant_id = ? AND last_updated >= ?
        GROUP BY rate
        HAVING q < 0.5
        ORDER BY q ASC
    """, (tenant_id, since))
    for row in low_q_rows:
        r = float(row["rate"])
        profile = RATE_TO_PROFILE.get(r, f"r={r}")
        q_val = _safe_quality(row["q"])
        alerts.append({
            "type": "low_quality",
            "severity": "warning",
            "profile": profile,
            "avg_quality": q_val,
            "message": f"Le profil {profile} a une qualité moyenne de {q_val:.2f} "
                       f"(basée sur {row['n']} échantillons)",
        })

    bypass_rows = _q("""
        SELECT COUNT(*) as n
        FROM ace_requests
        WHERE tenant_id = ? AND created_at >= ? AND rate_actual = 0
    """, (tenant_id, since))
    bypass_count = (bypass_rows[0]["n"] if bypass_rows else 0) or 0
    if req_count > 0:
        bypass_ratio = bypass_count / req_count
        if bypass_ratio > 0.5:
            alerts.append({
                "type": "high_bypass_ratio",
                "severity": "info",
                "profile": "bypass",
                "avg_quality": 1.0,
                "message": f"{bypass_ratio:.0%} des requêtes sont des bypass — "
                           "les marges pourraient être sous-optimales",
            })

    for t in by_task:
        if t["avg_quality"] < 0.4 and t["count"] >= 3:
            alerts.append({
                "type": "degraded_task",
                "severity": "warning",
                "task_type": t["task_type"],
                "avg_quality": t["avg_quality"],
                "message": f"La tâche '{t['task_type']}' a une qualité moyenne de "
                           f"{t['avg_quality']:.2f} ({t['count']} échantillons)",
            })

    return {
        "tenant_id": tenant_id,
        "period_days": days,
        "summary": {
            "total_cells": total,
            "good_quality_cells": general.get("good", 0) or 0,
            "poor_quality_cells": general.get("poor", 0) or 0,
            "good_quality_ratio": round((general.get("good", 0) or 0) / max(total, 1), 3),
            "avg_quality": round(_safe_quality(general.get("avg_quality")), 3),
            "avg_compression_rate": round(float(general.get("avg_rate", 0) or 0), 3),
            "total_requests": req_count,
            "total_tokens_saved": total_tokens_saved or 0,
            "avg_savings_percent": avg_savings_pct,
            "estimated_savings_usd": estimated_savings_usd,
        },
        "by_profile": by_profile,
        "by_task_type": by_task,
        "alerts": alerts,
    }
