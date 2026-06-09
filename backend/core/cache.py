"""Cache Redis avec fallback mémoire LRU."""

import json
import threading
import time
from collections import OrderedDict
from typing import Any, Optional

from backend.config import get_settings

_redis_client = None
_redis_lock = threading.Lock()


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    settings = get_settings()
    if not settings.REDIS_URL:
        return None
    with _redis_lock:
        if _redis_client is not None:
            return _redis_client
        try:
            import redis
            _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            _redis_client.ping()
            return _redis_client
        except Exception:
            return None


class MemoryCache:
    """LRU cache en mémoire avec TTL."""

    def __init__(self, max_size: int = 5000):
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires = entry
            if expires and time.time() > expires:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        with self._lock:
            expires = time.time() + ttl if ttl else 0
            self._store[key] = (value, expires)
            self._store.move_to_end(key)
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def incr(self, key: str, amount: int = 1) -> int:
        with self._lock:
            entry = self._store.get(key)
            val = (entry[0] if entry else 0) + amount
            self._store[key] = (val, 0)
            return val


_memory_cache = MemoryCache()


class CacheService:
    """Abstraction cache — Redis ou mémoire."""

    def get(self, key: str) -> Optional[Any]:
        r = _get_redis()
        if r:
            try:
                raw = r.get(key)
                return json.loads(raw) if raw else None
            except Exception:
                pass
        return _memory_cache.get(key)

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        r = _get_redis()
        if r:
            try:
                r.setex(key, ttl, json.dumps(value, default=str))
                return
            except Exception:
                pass
        _memory_cache.set(key, value, ttl)

    def delete(self, key: str) -> None:
        r = _get_redis()
        if r:
            try:
                r.delete(key)
            except Exception:
                pass
        _memory_cache.delete(key)

    def incr(self, key: str, amount: int = 1) -> int:
        r = _get_redis()
        if r:
            try:
                return r.incrby(key, amount)
            except Exception:
                pass
        return _memory_cache.incr(key, amount)


cache = CacheService()
