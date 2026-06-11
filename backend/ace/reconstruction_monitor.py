"""Reconstruction Monitor — sépare factual_loss (compression) de novelty_gain (LLM).

Analyse les différences entre le prompt/réponse original et compressé pour
déterminer si la qualité perçue est due à la compression ou au LLM.

Références:
- Factual vs creative divergence (Narayan et al., 2023)
- Information extraction for compression quality (TokenForge internal)
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

FACTUAL_PATTERNS = {
    "dates": re.compile(r'\b\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\b|\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b'),
    "numbers": re.compile(r'\b\d+(?:[.,]\d+)?\s*(?:%|€|\$|£|M|k|K|millions?|milliards?)\b|\b\d[\d,]*\d\b'),
    "emails": re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.]+\b'),
    "urls": re.compile(r'https?://\S+'),
    "entities": re.compile(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'),
}

NOVELTY_PATTERNS = re.compile(
    r'\b(en outre|par ailleurs|de plus|cependant|toutefois|'
    r'especially|notably|importantly|furthermore|moreover|additionally|'
    r'in addition|on the other hand|in contrast|similarly)\b',
    re.IGNORECASE,
)


class ReconstructionResult:
    __slots__ = (
        "factual_loss", "novelty_gain", "reconstruction_score",
        "is_acceptable", "details",
    )

    def __init__(
        self,
        factual_loss: float = 0.0,
        novelty_gain: float = 0.0,
        reconstruction_score: float = 1.0,
        is_acceptable: bool = True,
        details: Optional[Dict] = None,
    ):
        self.factual_loss = factual_loss
        self.novelty_gain = novelty_gain
        self.reconstruction_score = reconstruction_score
        self.is_acceptable = is_acceptable
        self.details = details or {}

    def to_dict(self) -> Dict:
        return {
            "factual_loss": round(self.factual_loss, 4),
            "novelty_gain": round(self.novelty_gain, 4),
            "reconstruction_score": round(self.reconstruction_score, 4),
            "is_acceptable": self.is_acceptable,
            "details": self.details,
        }


def _extract_factual_elements(text: str) -> Dict[str, Set[str]]:
    result: Dict[str, Set[str]] = {}
    for name, pattern in FACTUAL_PATTERNS.items():
        matches = set(pattern.findall(text))
        if matches:
            result[name] = matches
    return result


def _compute_factual_loss(prompt_original: str, prompt_compressed: str) -> Tuple[float, Dict]:
    """Mesure la perte d'éléments factuels entre le prompt original et compressé."""
    orig = _extract_factual_elements(prompt_original)
    comp = _extract_factual_elements(prompt_compressed)

    total_orig = sum(len(v) for v in orig.values())
    if total_orig == 0:
        return 0.0, {"note": "aucun élément factuel dans l'original"}

    lost = 0
    details = {}
    for cat, values in orig.items():
        comp_values = comp.get(cat, set())
        n_lost = len(values - comp_values)
        if n_lost > 0:
            details[cat] = {"original": n_lost, "perdu": n_lost}
            lost += n_lost

    loss_ratio = lost / max(total_orig, 1)
    return loss_ratio, {"total_factual": total_orig, "perdu": lost, "par_categorie": details}


def _compute_novelty_gain(response_compressed: str) -> float:
    """Mesure le gain de nouveauté dans la réponse compressée."""
    if not response_compressed:
        return 0.0
    matches = NOVELTY_PATTERNS.findall(response_compressed)
    n_transitions = len(matches)
    total_tokens = len(response_compressed.split())
    if total_tokens == 0:
        return 0.0
    gain = min(1.0, n_transitions / max(total_tokens * 0.1, 1))
    return gain


def analyze(
    original_prompt: str,
    compressed_prompt: str,
    original_response: str = "",
    compressed_response: str = "",
) -> ReconstructionResult:
    factual_loss, factual_details = _compute_factual_loss(original_prompt, compressed_prompt)
    novelty_gain = _compute_novelty_gain(compressed_response)
    reconstruction_score = max(0.0, 1.0 - factual_loss)
    is_acceptable = factual_loss <= 0.15
    return ReconstructionResult(
        factual_loss=factual_loss,
        novelty_gain=novelty_gain,
        reconstruction_score=reconstruction_score,
        is_acceptable=is_acceptable,
        details={
            "factual": factual_details,
            "novelty": {"gain": round(novelty_gain, 4)},
        },
    )


def should_retry(result: ReconstructionResult) -> bool:
    return result.factual_loss > 0.15 and result.novelty_gain < result.factual_loss
