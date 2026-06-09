"""Comparateur de prompts — diff, impact coût et qualité."""

import difflib
from typing import Any, Dict

from backend.models import calculate_cost
from backend.token_counter import count_tokens


class PromptDiffExplorer:
    """Compare deux prompts et quantifie l'impact."""

    def compare(self, prompt_a: str, prompt_b: str, model: str = "gpt-4o") -> Dict[str, Any]:
        tokens_a = count_tokens(prompt_a, model)
        tokens_b = count_tokens(prompt_b, model)
        cost_a = calculate_cost(model, tokens_a, int(tokens_a * 0.3))
        cost_b = calculate_cost(model, tokens_b, int(tokens_b * 0.3))
        diff_lines = list(difflib.unified_diff(
            prompt_a.splitlines(), prompt_b.splitlines(),
            lineterm="", fromfile="Prompt A", tofile="Prompt B",
        ))
        token_delta = tokens_b - tokens_a
        cost_delta = cost_b - cost_a
        return {
            "tokens_a": tokens_a, "tokens_b": tokens_b,
            "token_delta": token_delta,
            "token_delta_percent": round(token_delta / max(tokens_a, 1) * 100, 1),
            "cost_a_usd": round(cost_a, 6), "cost_b_usd": round(cost_b, 6),
            "cost_delta_usd": round(cost_delta, 6),
            "diff": diff_lines[:100],
            "diff_line_count": len(diff_lines),
            "quality_impact": self._assess_quality_impact(prompt_a, prompt_b),
        }

    def _assess_quality_impact(self, a: str, b: str) -> Dict[str, Any]:
        len_ratio = len(b) / max(len(a), 1)
        risk = "low"
        if len_ratio < 0.5:
            risk = "high"
        elif len_ratio < 0.75:
            risk = "medium"
        removed_keywords = set(a.lower().split()) - set(b.lower().split())
        critical = {"not", "never", "must", "required", "pas", "jamais", "obligatoire"}
        lost_critical = critical & removed_keywords
        if lost_critical:
            risk = "high"
        return {
            "length_ratio": round(len_ratio, 2),
            "risk_level": risk,
            "lost_critical_words": list(lost_critical),
        }
