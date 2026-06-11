"""Quality Oracle — évaluation AND-logique de la qualité de compression.

Chaque dimension (exactitude, complétude, cohérence, fidélité, style)
doit passer son seuil individuellement. Pas de moyenne — pas de gaming.

Références:
- Multi-task learning with AND-logic (Syed et al., 2023)
- Contract theory for LLM compression (TokenForge internal)
"""

import logging
from typing import Dict, List, Optional, Tuple

from backend.ace.judge import QualityJudge, get_judge

logger = logging.getLogger(__name__)

# Seuils AND par dimension
DIMENSION_THRESHOLDS = {
    "exactitude": 0.80,
    "completude": 0.75,
    "coherence": 0.70,
    "fidelite": 0.85,
    "style": 0.60,
}

DIMENSION_ORDER = ["exactitude", "completude", "coherence", "fidelite", "style"]


class OracleResult:
    __slots__ = ("passed", "dimensions", "score", "failure_dimensions", "details")

    def __init__(
        self,
        passed: bool = False,
        dimensions: Optional[Dict[str, float]] = None,
        score: float = 0.0,
        failure_dimensions: Optional[List[str]] = None,
        details: Optional[Dict] = None,
    ):
        self.passed = passed
        self.dimensions = dimensions or {}
        self.score = score
        self.failure_dimensions = failure_dimensions or []
        self.details = details or {}

    def to_dict(self) -> Dict:
        return {
            "passed": self.passed,
            "dimensions": self.dimensions,
            "score": round(self.score, 4),
            "failure_dimensions": self.failure_dimensions,
        }


def _translate_dimensions(judge_details: Dict) -> Dict[str, float]:
    """Traduit les noms de dimensions du QualityJudge vers l'Oracle."""
    mapping = {
        "exactitude": "exactitude",
        "completude": "completude",
        "coherence": "coherence",
        "fidelite": "fidelite",
        "style": "style",
        "justification": None,
    }
    result = {}
    for k, v in judge_details.items():
        target = mapping.get(k)
        if target is not None:
            if isinstance(v, (int, float)):
                result[target] = float(v)
            elif isinstance(v, str) and v.replace(".", "").isdigit():
                result[target] = float(v) / 100.0
    return result


def evaluate(
    prompt: str,
    response_a: str,
    response_b: str,
    judge: Optional[QualityJudge] = None,
) -> OracleResult:
    """Évalue la qualité avec AND-logic.
    
    Toutes les dimensions doivent passer leur seuil pour que
    le résultat soit considéré comme 'passed' (contract-compliant).
    """
    j = judge or get_judge()
    try:
        j_result = j.evaluate(prompt, response_a, response_b)
    except Exception as e:
        logger.warning("QualityJudge failed in Oracle: %s", e)
        return OracleResult(
            passed=False,
            dimensions={},
            score=0.0,
            failure_dimensions=["judge_error"],
            details={"error": str(e)},
        )

    judge_score = j_result.get("score", 0.85)
    judge_details = j_result.get("details", {})

    dims = _translate_dimensions(judge_details)
    dims["score"] = judge_score

    failure = []
    for dim, threshold in DIMENSION_THRESHOLDS.items():
        val = dims.get(dim, judge_score)
        dims[dim] = val
        if val < threshold:
            failure.append(dim)

    if not failure:
        oracle_score = 1.0
        passed = True
    else:
        oracle_score = min(dims.get(d, judge_score)
                          for d in DIMENSION_ORDER)
        passed = False

    return OracleResult(
        passed=passed,
        dimensions=dims,
        score=oracle_score,
        failure_dimensions=failure,
        details=j_result,
    )


def is_contract_compliant(result: OracleResult) -> bool:
    return result.passed
