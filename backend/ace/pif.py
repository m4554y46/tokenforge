"""Prompt Information Footprint — estime la compressibilité théorique avant compression.

PIF = entropie_normalisée * (1 - redondance) - pénalité_contenu_protégé
Headroom = 1.0 - PIF  # plus headroom est élevé, plus le prompt est compressible

Références:
- Shannon, C. E. (1948). A Mathematical Theory of Communication.
- Delétang et al. (2023). Language Modeling is Compression.
"""

import math
import re
from typing import Dict, List, Optional, Tuple

from backend.ace.sanctuary import protected_ratio

NGRAM_ORDER = 4
MIN_HEADROOM_FOR_BYPASS = 0.05
ENTROPY_FLOOR = 0.1


class PIFResult:
    __slots__ = (
        "headroom", "entropy", "redundancy", "protected_ratio",
        "num_tokens", "is_compressible", "explanation",
    )

    def __init__(
        self,
        headroom: float = 0.0,
        entropy: float = 0.0,
        redundancy: float = 0.0,
        protected_ratio: float = 0.0,
        num_tokens: int = 0,
        is_compressible: bool = False,
        explanation: str = "",
    ):
        self.headroom = headroom
        self.entropy = entropy
        self.redundancy = redundancy
        self.protected_ratio = protected_ratio
        self.num_tokens = num_tokens
        self.is_compressible = is_compressible
        self.explanation = explanation

    def to_dict(self) -> Dict:
        return {
            "headroom": round(self.headroom, 4),
            "entropy": round(self.entropy, 4),
            "redundancy": round(self.redundancy, 4),
            "protected_ratio": round(self.protected_ratio, 4),
            "num_tokens": self.num_tokens,
            "is_compressible": self.is_compressible,
            "explanation": self.explanation,
        }


def _tokenize(text: str) -> List[str]:
    return re.findall(r'\S+', text.lower())


def _ngrams(tokens: List[str], n: int) -> List[Tuple[str, ...]]:
    if not tokens or len(tokens) < n:
        return [tuple(tokens)]
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def _empirical_entropy(tokens: List[str]) -> float:
    if not tokens:
        return 0.0
    n = min(NGRAM_ORDER, max(1, len(tokens) - 1))
    ngrams = _ngrams(tokens, n)
    if not ngrams:
        return 0.0
    total = len(ngrams)
    freq: Dict[Tuple[str, ...], int] = {}
    for ng in ngrams:
        freq[ng] = freq.get(ng, 0) + 1
    entropy = 0.0
    for count in freq.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    entropy /= math.log2(max(total, 2))
    return max(ENTROPY_FLOOR, min(1.0, entropy))


def _redundancy_score(tokens: List[str]) -> float:
    if not tokens:
        return 1.0
    n_types = len(set(tokens))
    n_tokens = len(tokens)
    expected_types = n_tokens ** 0.5
    ttr_ratio = n_types / max(expected_types, 1)
    redundancy = 1.0 - min(1.0, ttr_ratio / 3.0)
    return max(0.0, min(1.0, redundancy))


def _estimate_headroom(entropy: float, redundancy: float, protected: float) -> float:
    pif = entropy * (1.0 - redundancy) + protected * 0.5
    pif = max(0.0, min(1.0, pif))
    return 1.0 - pif


def compute_footprint(prompt: str) -> PIFResult:
    tokens = _tokenize(prompt)
    num_tokens = len(tokens)

    if num_tokens == 0:
        return PIFResult(
            headroom=0.0, entropy=0.0, redundancy=1.0,
            protected_ratio=0.0, num_tokens=0,
            is_compressible=False, explanation="Prompt vide",
        )

    entropy = _empirical_entropy(tokens)
    redundancy = _redundancy_score(tokens)
    protected = protected_ratio(prompt)
    headroom = _estimate_headroom(entropy, redundancy, protected)

    is_compressible = headroom >= MIN_HEADROOM_FOR_BYPASS
    parts = []
    if entropy > 0.8:
        parts.append(f"entropie élevée ({entropy:.2f})")
    if redundancy > 0.5:
        parts.append(f"redondant ({redundancy:.2f})")
    if protected > 0.1:
        parts.append(f"contenu protégé ({protected:.1%})")
    expl = "Compressible" if is_compressible else "Incompressible"
    if parts:
        expl += f" : {', '.join(parts)}. Headroom={headroom:.1%}"
    else:
        expl += f". Headroom={headroom:.1%}"

    return PIFResult(
        headroom=headroom, entropy=entropy, redundancy=redundancy,
        protected_ratio=protected, num_tokens=num_tokens,
        is_compressible=is_compressible, explanation=expl,
    )


def is_incompressible(pif_result: PIFResult, min_headroom: float = MIN_HEADROOM_FOR_BYPASS) -> bool:
    return pif_result.headroom < min_headroom
