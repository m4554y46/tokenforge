"""Observability Hub — Prometheus, OpenTelemetry, logs structurés."""

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List

from backend.config import get_settings

logger = logging.getLogger("tokenforge.observability")

_metrics: Dict[str, float] = defaultdict(float)
_counters: Dict[str, int] = defaultdict(int)
_traces: List[Dict] = []
_MAX_TRACES = 1000


class ObservabilityHub:
    """Centralise logs, traces et métriques."""

    def __init__(self):
        self.settings = get_settings()

    def record_request(
        self, endpoint: str, duration_ms: float, status: int = 200,
        tenant_id: str = "", extra: Dict = None,
    ) -> None:
        _counters[f"requests_total{{endpoint={endpoint}}}"] += 1
        dur_key = f"request_duration_ms{{endpoint={endpoint}}}"
        prev = _metrics.get(dur_key, 0)
        _metrics[dur_key] = prev * 0.9 + duration_ms * 0.1  # EMA lissé
        if status >= 400:
            _counters[f"errors_total{{endpoint={endpoint}}}"] += 1
        trace = {
            "endpoint": endpoint, "duration_ms": round(duration_ms, 2),
            "status": status, "tenant_id": tenant_id,
            "timestamp": time.time(), **(extra or {}),
        }
        _traces.append(trace)
        if len(_traces) > _MAX_TRACES:
            _traces.pop(0)
        logger.info("request", extra=trace)

    def record_compression(self, profile: str, savings: float, fallback: bool) -> None:
        _counters["compressions_total"] += 1
        _metrics["last_savings_percent"] = savings
        if fallback:
            _counters["compression_fallbacks_total"] += 1

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "counters": dict(_counters),
            "gauges": dict(_metrics),
            "otel_enabled": self.settings.OTEL_ENABLED,
            "prometheus_enabled": self.settings.PROMETHEUS_ENABLED,
        }

    def get_traces(self, limit: int = 50) -> List[Dict]:
        return _traces[-limit:]

    def prometheus_text(self) -> str:
        def _format_metric(key: str, value: Any, typ: str = "counter") -> str:
            if "{" in key:
                name, labels_raw = key.split("{", 1)
                labels_raw = labels_raw.rstrip("}")
                parts = []
                for pair in labels_raw.split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        if not v.startswith('"'):
                            v = f'"{v}"'
                        parts.append(f'{k}={v}')
                labels = "{" + ",".join(parts) + "}"
                return f"tokenforge_{name}{labels} {v}"
            return f"tokenforge_{key} {v}"

        lines = ["# HELP tokenforge_requests_total Total requests", "# TYPE tokenforge_requests_total counter"]
        for k, v in _counters.items():
            lines.append(_format_metric(k, v, "counter"))
        for k, v in _metrics.items():
            lines.append(_format_metric(k, v, "gauge"))
        return "\n".join(lines) + "\n"
