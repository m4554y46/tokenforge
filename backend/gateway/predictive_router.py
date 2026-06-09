"""Routeur prédictif — cache, compression, bypass, provider."""

import hashlib
from typing import Any, Dict, Optional

from backend.core.cache import cache
from backend.gateway.cache_governor import CacheGovernor
from backend.governance.rule_engine import RuleEngine


class PredictiveRouter:
    """Décide la stratégie optimale pour chaque requête LLM."""

    def __init__(self):
        self.cache_governor = CacheGovernor()
        self.rule_engine = RuleEngine()

    def _prompt_key(self, text: str, model: str) -> str:
        h = hashlib.sha256(f"{model}:{text}".encode()).hexdigest()[:24]
        return f"llm_response:{h}"

    def route(
        self, tenant_id: str, user_id: str, prompt: str,
        model: str, provider: str = "", tokens: int = 0,
    ) -> Dict[str, Any]:
        policy = self.rule_engine.evaluate(tenant_id, model, provider, user_id, tokens)
        if not policy["allowed"]:
            return {"action": "deny", "reason": policy["decisions"], "policy": policy}

        cache_key = self._prompt_key(prompt, model)
        if policy.get("force_cache") or self.cache_governor.should_use_cache(prompt, model):
            cached = cache.get(cache_key)
            if cached:
                return {"action": "cache_hit", "cached_response": cached, "savings_percent": 100}

        if policy.get("force_compression") or len(prompt) > 200:
            profile = "industrial" if len(prompt) > 2000 else "balanced"
            return {
                "action": "compress", "profile": profile,
                "policy": policy, "cache_key": cache_key,
            }

        if len(prompt) < 50:
            return {"action": "bypass", "reason": "prompt_too_short", "policy": policy}

        return {"action": "compress", "profile": "balanced", "policy": policy, "cache_key": cache_key}

    def store_response(self, cache_key: str, response: Any, ttl: int = 3600) -> None:
        cache.set(cache_key, response, ttl)
        self.cache_governor.record_hit(cache_key)
