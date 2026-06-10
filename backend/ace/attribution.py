"""Attribution Engine — détermine la cause d'un échec qualité.

Sépare les échecs dus à la compression de ceux dus au LLM,
à l'utilisateur ou au contexte. Critique pour ne pas apprendre du bruit.
"""

import logging
from typing import Dict, Optional

from backend.ace.state import RATES

logger = logging.getLogger(__name__)

CAUSES = ["compression", "model", "user", "context"]

HIGH_COMPRESSION_THRESHOLD = 0.40
COMPLEXITY_THRESHOLD = 0.6


class AttributionResult:
    cause: str = "unknown"
    confidence: float = 0.0
    details: Dict = {}

    @property
    def is_compression_failure(self) -> bool:
        return self.cause == "compression" and self.confidence > 0.5


def _estimate_model_reliability(model: str) -> float:
    reliable = {"gpt-4o": 0.95, "claude-3.5-sonnet": 0.93, "gemini-1.5-pro": 0.90}
    unreliable = {"gpt-3.5-turbo": 0.75, "gemini-1.5-flash": 0.80}
    model_lower = model.lower()
    for k, v in reliable.items():
        if k in model_lower:
            return v
    for k, v in unreliable.items():
        if k in model_lower:
            return v
    return 0.85


def _estimate_prompt_complexity(features: Dict) -> float:
    score = 0.0
    specificity = features.get("specificity", "generic")
    if specificity == "entity_rich":
        score += 0.4
    elif specificity == "domain_jargon":
        score += 0.2
    task = features.get("task_type", "factuel")
    if task in ["creatif", "brainstorming", "instruction"]:
        score += 0.2
    length = features.get("length_bucket", "medium")
    if length in ["long", "very_long"]:
        score += 0.2
    return min(score, 1.0)


def _estimate_user_history_quality(features: Dict) -> float:
    return 0.5


def attribute(
    features: Dict,
    rate: float,
    signals: Dict,
) -> AttributionResult:
    result = AttributionResult()
    reformulation = signals.get("reformulation", False)
    continuation = signals.get("continuation", False)
    if not reformulation and continuation:
        result.cause = "user"
        result.confidence = 0.4
        result.details = {"reason": "continuation detected, likely acceptable"}
        return result
    if not reformulation:
        result.cause = "user"
        result.confidence = 0.3
        result.details = {"reason": "no negative signal"}
        return result
    model_reliability = _estimate_model_reliability(features.get("model", ""))
    prompt_complexity = _estimate_prompt_complexity(features)
    user_quality = _estimate_user_history_quality(features)
    is_high_compression = rate >= HIGH_COMPRESSION_THRESHOLD
    scores = {}
    scores["compression"] = 0.6 if is_high_compression else 0.1
    if prompt_complexity > COMPLEXITY_THRESHOLD:
        scores["model"] = 0.7 * (1.0 - model_reliability)
    else:
        scores["model"] = 0.4 * (1.0 - model_reliability)
    scores["user"] = 0.3 * (1.0 - user_quality)
    scores["context"] = 0.2 * (min(prompt_complexity, 0.5) / 0.5)
    total = sum(scores.values())
    if total <= 0:
        result.cause = "unknown"
        result.confidence = 0.0
        return result
    for k in scores:
        scores[k] /= total
    best_cause = max(scores, key=scores.get)
    best_score = scores[best_cause]
    result.cause = best_cause
    result.confidence = best_score
    result.details = {"scores": {k: round(v, 3) for k, v in scores.items()}, "is_high_compression": is_high_compression}
    return result


def should_update_quality(attribution: AttributionResult) -> bool:
    if attribution.is_compression_failure:
        return True
    if attribution.cause == "model" and attribution.confidence > 0.7:
        return False
    if attribution.cause == "user" and attribution.confidence > 0.6:
        return False
    return True
