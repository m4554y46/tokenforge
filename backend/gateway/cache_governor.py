"""Cache Governor — maximise le cache hit rate."""

import hashlib
from collections import Counter
from typing import Any, Dict

from backend.core.cache import cache


class CacheGovernor:
    """Gouverne la stratégie de cache pour maximiser le ROI."""

    def __init__(self):
        self._hit_counter: Counter = Counter()

    def should_use_cache(self, prompt: str, model: str) -> bool:
        if len(prompt) < 30:
            return False
        key = self._freq_key(prompt, model)
        freq = cache.get(key) or 0
        return freq >= 2 or len(prompt) > 500

    def record_request(self, prompt: str, model: str) -> None:
        key = self._freq_key(prompt, model)
        cache.incr(key, 1)

    def record_hit(self, cache_key: str) -> None:
        self._hit_counter[cache_key] += 1
        cache.incr("cache:total_hits")

    def stats(self) -> Dict[str, Any]:
        total_hits = cache.get("cache:total_hits") or 0
        return {
            "total_hits": total_hits,
            "top_keys": self._hit_counter.most_common(10),
        }

    def _freq_key(self, prompt: str, model: str) -> str:
        h = hashlib.sha256(prompt[:500].encode()).hexdigest()[:16]
        return f"prompt_freq:{model}:{h}"
