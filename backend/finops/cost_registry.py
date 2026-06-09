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
        rows = query_all(
            f"SELECT provider, model, SUM(cost_usd) as total_cost, SUM(input_tokens) as total_input, "
            f"COUNT(*) as requests, AVG(savings_percent) as avg_savings "
            f"FROM prompt_events WHERE tenant_id={p} "
            f"AND created_at >= datetime('now', '-' || {p} || ' days') "
            f"GROUP BY provider, model ORDER BY total_cost DESC",
            (tenant_id, str(days)),
        )
        total = sum(r["total_cost"] or 0 for r in rows)
        return {"total_cost_usd": round(total, 4), "by_model": rows, "period_days": days}

    def get_top_costly_prompts(self, tenant_id: str, limit: int = 10) -> List[Dict]:
        p = _param()
        return query_all(
            f"SELECT prompt_hash, prompt_preview, SUM(cost_usd) as total_cost, COUNT(*) as uses "
            f"FROM prompt_events WHERE tenant_id={p} GROUP BY prompt_hash ORDER BY total_cost DESC LIMIT {p}",
            (tenant_id, limit),
        )

    def list_providers(self) -> Dict[str, List[str]]:
        return PROVIDER_MODELS
