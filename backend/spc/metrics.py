"""Phase 17+18 — Token Analysis & Performance Measurement.

Uses tiktoken for GPT-4 token counting by default.
"""

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TokenMetrics:
    input_tokens: int = 0
    output_tokens: int = 0
    input_chars: int = 0
    output_chars: int = 0
    reduction_ratio: float = 0.0
    estimated_cost_savings: float = 0.0
    cost_per_1k_tokens: float = 0.0
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "input_chars": self.input_chars,
            "output_chars": self.output_chars,
            "reduction_ratio": round(self.reduction_ratio, 4),
            "estimated_cost_savings": round(self.estimated_cost_savings, 6),
            "cost_per_1k_tokens": self.cost_per_1k_tokens,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens using tiktoken. Falls back to len//4 if not available."""
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except (ImportError, KeyError):
        # Fallback: approximate 4 chars per token
        return max(1, len(text) // 4)


def measure(text: str, compressed: str, cost_per_1k: float = 0.0) -> TokenMetrics:
    """Compute token metrics between original and compressed text."""
    input_tok = count_tokens(text)
    output_tok = count_tokens(compressed)
    input_chars = len(text)
    output_chars = len(compressed)

    reduction = 1.0 - (output_tok / max(1, input_tok))
    savings = (input_tok - output_tok) / 1000 * cost_per_1k if cost_per_1k > 0 else 0.0

    return TokenMetrics(
        input_tokens=input_tok,
        output_tokens=output_tok,
        input_chars=input_chars,
        output_chars=output_chars,
        reduction_ratio=reduction,
        estimated_cost_savings=savings,
        cost_per_1k_tokens=cost_per_1k,
    )


class Timer:
    """Simple performance timer."""

    def __init__(self):
        self.start: float = 0.0
        self.elapsed: float = 0.0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed = (time.perf_counter() - self.start) * 1000  # ms

    def ms(self) -> float:
        return round(self.elapsed, 2)
