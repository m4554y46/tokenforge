"""Circuit breaker — retry, timeout, fallback."""

import time
from enum import Enum
from typing import Any, Callable, Dict, Optional


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Protège les appels provider contre les cascades d'erreurs."""

    def __init__(
        self, name: str, failure_threshold: int = 5,
        recovery_timeout: float = 30.0, half_open_max: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._last_failure = 0.0
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def allow_request(self) -> bool:
        s = self._state
        if s == CircuitState.CLOSED:
            return True
        if s == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.half_open_max
        if s == CircuitState.OPEN and time.time() - self._last_failure >= self.recovery_timeout:
            self._state = CircuitState.HALF_OPEN
            self._half_open_calls = 0
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        self._last_failure = time.time()
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
        elif self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN

    def call(self, fn: Callable, fallback: Optional[Callable] = None, *args, **kwargs) -> Any:
        if not self.allow_request():
            if fallback:
                return fallback(*args, **kwargs)
            raise RuntimeError(f"Circuit {self.name} is OPEN")
        try:
            if self.state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
            result = fn(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            if fallback:
                return fallback(*args, **kwargs)
            raise

    def status(self) -> Dict[str, Any]:
        return {
            "name": self.name, "state": self._state.value,
            "failures": self._failures,
        }
