"""Registre des coûts multi-provider."""

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.models import calculate_cost, get_model_info
from backend.core.database_v2 import query_all, execute, _param
from backend.token_counter import count_tokens

PROVIDER_MODELS = {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o1", "o3-mini"],
    "anthropic": ["claude-sonnet-4", "claude-opus-4", "claude-haiku-3.5"],
    "google": ["gemini-2.5-pro", "gemini-2.0-flash"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "mistral": ["mistral-large", "mistral-small"],
    "internal": ["vllm-local", "tgi-local"],
}


class CostRegistry:
    """Enregistre et agrège les coûts LLM par tenant."""

    def record_event(
        self, tenant_id: str, user_id: str, prompt: str, model: str,
        input_tokens: Optional[int] = None, output_tokens: int = 0,
        compressed: bool = False, savings_percent: float = 0, profile: str = "",
    ) -> Dict[str, Any]:
        info = get_model_info(model)
        provider = info["provider"] if info else "unknown"
        if input_tokens is None:
            input_tokens = count_tokens(prompt, model)
        cost = calculate_cost(model, input_tokens, output_tokens) if info else 0.0
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        p = _param()
        now = datetime.now().isoformat()
        execute(
            f"INSERT INTO prompt_events (tenant_id, user_id, prompt_hash, prompt_preview, model, provider, "
            f"input_tokens, output_tokens, cost_usd, compressed, savings_percent, profile, created_at) "
            f"VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})",
            (tenant_id, user_id, prompt_hash, prompt[:200], model, provider,
             input_tokens, output_tokens, cost, int(compressed), savings_percent, profile, now),
        )
        return {
            "prompt_hash": prompt_hash, "cost_usd": cost,
            "input_tokens": input_tokens, "provider": provider,
        }

    def get_cost_summary(self, tenant_id: str, days: int = 30) -> Dict[str, Any]:
        p = _param()
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = query_all(
            f"SELECT provider, model, SUM(cost_usd) as total_cost, SUM(input_tokens) as total_input, "
            f"COUNT(*) as requests, AVG(savings_percent) as avg_savings "
            f"FROM prompt_events WHERE tenant_id={p} "
            f"AND created_at >= {p} "
            f"GROUP BY provider, model ORDER BY total_cost DESC",
            (tenant_id, cutoff),
        )
        total = sum(r["total_cost"] or 0 for r in rows)
        total_tokens = sum(r["total_input"] or 0 for r in rows)
        total_requests = sum(r["requests"] or 0 for r in rows)
        return {
            "total_cost_usd": round(total, 4),
            "total_tokens": total_tokens,
            "total_requests": total_requests,
            "cost_per_token": round(total / total_tokens, 6) if total_tokens else 0,
            "avg_cost_per_request": round(total / total_requests, 4) if total_requests else 0,
            "by_model": rows,
            "period_days": days,
        }

    def get_top_costly_prompts(self, tenant_id: str, limit: int = 10) -> List[Dict]:
        p = _param()
        return query_all(
            f"SELECT prompt_hash, prompt_preview, SUM(cost_usd) as total_cost, COUNT(*) as uses "
            f"FROM prompt_events WHERE tenant_id={p} GROUP BY prompt_hash ORDER BY total_cost DESC LIMIT {p}",
            (tenant_id, limit),
        )

    def get_cost_trend(self, tenant_id: str, days: int = 30) -> List[Dict]:
        p = _param()
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        return query_all(
            f"SELECT SUBSTR(created_at,1,10) as day, SUM(cost_usd) as cost, "
            f"SUM(input_tokens) as tokens, COUNT(*) as requests "
            f"FROM prompt_events WHERE tenant_id={p} AND created_at>={p} "
            f"GROUP BY day ORDER BY day",
            (tenant_id, cutoff),
        )

    def get_top_users(self, tenant_id: str, limit: int = 5, days: int = 30) -> List[Dict]:
        p = _param()
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        return query_all(
            f"SELECT user_id, SUM(cost_usd) as total_cost, SUM(input_tokens) as total_tokens, "
            f"COUNT(*) as requests, AVG(savings_percent) as avg_savings "
            f"FROM prompt_events WHERE tenant_id={p} AND created_at>={p} "
            f"GROUP BY user_id ORDER BY total_cost DESC LIMIT {p}",
            (tenant_id, cutoff, limit),
        )

    def get_provider_efficiency(self, tenant_id: str, days: int = 30) -> List[Dict]:
        p = _param()
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        return query_all(
            f"SELECT provider, SUM(cost_usd) as total_cost, SUM(input_tokens) as total_tokens, "
            f"COUNT(*) as requests FROM prompt_events WHERE tenant_id={p} AND created_at>={p} "
            f"GROUP BY provider ORDER BY total_cost DESC",
            (tenant_id, cutoff),
        )

    def list_providers(self) -> Dict[str, List[str]]:
        return PROVIDER_MODELS
