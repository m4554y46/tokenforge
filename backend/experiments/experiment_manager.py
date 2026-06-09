"""Experiment Manager — A/B testing compression et providers."""

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.core.database_v2 import query_all, query_one, execute, _param


class ExperimentManager:
    """Compare original vs compressé ou provider A vs B."""

    def create(
        self, tenant_id: str, name: str, variant_a: str, variant_b: str,
        metric: str = "cost",
    ) -> Dict[str, Any]:
        p = _param()
        now = datetime.now().isoformat()
        execute(
            f"INSERT INTO experiments (tenant_id, name, variant_a, variant_b, metric, status, results_json, created_at) "
            f"VALUES ({p},{p},{p},{p},{p},'active','{{}}',{p})",
            (tenant_id, name, variant_a, variant_b, metric, now),
        )
        return {"name": name, "variant_a": variant_a, "variant_b": variant_b, "metric": metric}

    def list_experiments(self, tenant_id: str) -> List[Dict]:
        p = _param()
        rows = query_all(f"SELECT * FROM experiments WHERE tenant_id={p} ORDER BY created_at DESC", (tenant_id,))
        for r in rows:
            r["results"] = json.loads(r.get("results_json", "{}"))
        return rows

    def assign_variant(self, experiment_id: int, user_id: str) -> str:
        exp = self._get(experiment_id)
        if not exp:
            return "a"
        digest = hashlib.sha256(f"{experiment_id}:{user_id}".encode()).hexdigest()
        seed = int(digest[:8], 16) % 100
        return exp["variant_a"] if seed < 50 else exp["variant_b"]

    def record_result(
        self, experiment_id: int, variant: str,
        cost: float = 0, quality_score: float = 0, tokens: int = 0,
    ) -> Dict[str, Any]:
        exp = self._get(experiment_id)
        if not exp:
            return {"error": "not found"}
        results = json.loads(exp.get("results_json", "{}"))
        key = variant
        if key not in results:
            results[key] = {"samples": 0, "total_cost": 0, "total_quality": 0, "total_tokens": 0}
        results[key]["samples"] += 1
        results[key]["total_cost"] += cost
        results[key]["total_quality"] += quality_score
        results[key]["total_tokens"] += tokens
        p = _param()
        execute(
            f"UPDATE experiments SET results_json={p} WHERE id={p}",
            (json.dumps(results), experiment_id),
        )
        return self._analyze(results, exp.get("metric", "cost"))

    def _get(self, experiment_id: int) -> Optional[Dict]:
        p = _param()
        return query_one(f"SELECT * FROM experiments WHERE id={p}", (experiment_id,))

    def get_variant_name(self, experiment_id: int, user_id: str) -> str:
        exp = self._get(experiment_id)
        if not exp:
            return ""
        digest = hashlib.sha256(f"{experiment_id}:{user_id}".encode()).hexdigest()
        seed = int(digest[:8], 16) % 100
        return exp["variant_a"] if seed < 50 else exp["variant_b"]

    def _analyze(self, results: Dict, metric: str) -> Dict[str, Any]:
        analysis = {}
        for variant, data in results.items():
            n = data["samples"]
            if n == 0:
                continue
            analysis[variant] = {
                "samples": n,
                "avg_cost": round(data["total_cost"] / n, 6),
                "avg_quality": round(data["total_quality"] / n, 3),
                "avg_tokens": round(data["total_tokens"] / n, 1),
            }
        winner = None
        if len(analysis) == 2:
            keys = list(analysis.keys())
            if metric == "cost":
                winner = keys[0] if analysis[keys[0]]["avg_cost"] < analysis[keys[1]]["avg_cost"] else keys[1]
            elif metric == "quality":
                winner = keys[0] if analysis[keys[0]]["avg_quality"] > analysis[keys[1]]["avg_quality"] else keys[1]
        return {"variants": analysis, "winner": winner, "metric": metric}
