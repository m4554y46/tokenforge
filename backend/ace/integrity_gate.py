"""Integrity Gate — détection et prévention des sorties de compression pathologiques.

Fonctions:
- estimate_safe_threshold(prompt) → seuil adaptatif pour kompress.py
- validate_compression(original, compressed) → 4 vérifications post-compression
- quenching_threshold(prompt) → floor dynamique remplaçant le 15% fixe

Références:
- Entropy rate estimation (Cover & Thomas, 2006)
- Minimum Description Length (Rissanen, 1978)
"""

import math
import re
from typing import Dict, List, Optional, Tuple

from backend.ace.sanctuary import protected_ratio

MIN_COMPRESSED_RATIO = 0.15
ENTROPY_COLLAPSE_RATIO = 0.20
STRUCTURAL_PATTERNS = [
    (re.compile(r'```[\w]*\n.*?\n```', re.DOTALL), "code_fence"),
    (re.compile(r'{[\s\S]*?}', re.DOTALL), "json_block"),
    (re.compile(r'\$\$[\s\S]*?\$\$', re.DOTALL), "latex_display"),
    (re.compile(r'---[\s\S]*?---'), "yaml_frontmatter"),
    (re.compile(r'\|[^\n]+\|[^\n]+\|'), "markdown_table"),
]

MAX_STRUCTURE_RATIO = 0.50


def _tokenize(text: str) -> List[str]:
    return re.findall(r'\S+', text.lower())


def _ngram_entropy(tokens: List[str], n: int = 3) -> float:
    if not tokens:
        return 0.0
    n = min(n, max(1, len(tokens) - 1))
    ngrams = [tuple(tokens[i:i + n]) for i in range(max(0, len(tokens) - n + 1))]
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
    return max(0.1, min(1.0, entropy))


class IntegrityResult:
    __slots__ = ("passed", "checks", "failure_reason")

    def __init__(self, passed: bool = True, checks: Optional[Dict] = None, failure_reason: str = ""):
        self.passed = passed
        self.checks = checks or {}
        self.failure_reason = failure_reason

    def to_dict(self) -> Dict:
        return {
            "passed": self.passed,
            "checks": self.checks,
            "failure_reason": self.failure_reason,
        }


def estimate_safe_threshold(prompt: str) -> float:
    """Retourne un seuil adaptatif basé sur l'entropie et la redondance.
    
    Plus le prompt est redondant (entropie basse), plus on peut être
    agressif (threshold bas). Plus le prompt est dense, plus on doit
    être conservateur (threshold haut).
    """
    tokens = _tokenize(prompt)
    if not tokens:
        return 0.5
    entropy = _ngram_entropy(tokens)
    protected = protected_ratio(prompt)
    base = 0.5
    if entropy < 0.4:
        factor = 0.6
    elif entropy < 0.6:
        factor = 0.8
    else:
        factor = 1.0
    protected_penalty = protected * 0.3
    threshold = base * factor + protected_penalty
    return max(0.15, min(0.95, threshold))


def validate_compression(original: str, compressed: str) -> IntegrityResult:
    """4 vérifications post-compression.
    
    1. Token ratio: compressed ne doit pas être vide (> 15% de l'original)
    2. Entropy collapse: l'entropie du compressed ne doit pas chuter < 20%
    3. Structure integrity: code fences / JSON / YAML préservés
    4. Non-empty: pas de sortie vide ou < 3 caractères
    """
    checks = {}
    all_passed = True

    o_tokens = _tokenize(original)
    c_tokens = _tokenize(compressed)

    # 1. Token ratio
    ratio = len(c_tokens) / max(len(o_tokens), 1)
    checks["token_ratio"] = round(ratio, 4)
    if ratio < MIN_COMPRESSED_RATIO:
        all_passed = False

    # 2. Entropy collapse
    if c_tokens:
        o_entropy = _ngram_entropy(o_tokens)
        c_entropy = _ngram_entropy(c_tokens)
        checks["entropy_original"] = round(o_entropy, 4)
        checks["entropy_compressed"] = round(c_entropy, 4)
        if o_entropy > 0 and c_entropy / o_entropy < ENTROPY_COLLAPSE_RATIO:
            all_passed = False
            checks["entropy_collapse"] = True
        else:
            checks["entropy_collapse"] = False
    else:
        checks["entropy_compressed"] = 0.0
        checks["entropy_collapse"] = True
        all_passed = False

    # 3. Structure integrity
    struct_failures = []
    if o_tokens and c_tokens:
        for pattern, name in STRUCTURAL_PATTERNS:
            o_has = bool(pattern.search(original))
            c_has = bool(pattern.search(compressed))
            if o_has and not c_has:
                struct_failures.append(name)
    checks["structure_failures"] = struct_failures
    if struct_failures:
        all_passed = False

    # 4. Non-empty
    is_empty = len(compressed.strip()) < 3
    checks["is_empty"] = is_empty
    if is_empty:
        all_passed = False

    failure_reason = ""
    if not all_passed:
        reasons = []
        if ratio < MIN_COMPRESSED_RATIO:
            reasons.append(f"token_ratio={ratio:.2f} < {MIN_COMPRESSED_RATIO}")
        if checks.get("entropy_collapse"):
            reasons.append("entropy collapse")
        if struct_failures:
            reasons.append(f"structure perdue: {','.join(struct_failures)}")
        if is_empty:
            reasons.append("sortie vide")
        failure_reason = "; ".join(reasons)

    return IntegrityResult(passed=all_passed, checks=checks, failure_reason=failure_reason)


def quenching_threshold(prompt: str) -> float:
    """Floor dynamique pour kompress.py, basé sur l'entropie du prompt.
    
    Remplace le 15% fixe. Plus le prompt est dense (entropie élevée),
    plus le floor est haut → moins de compression agressive.
    """
    tokens = _tokenize(prompt)
    if not tokens:
        return 0.15
    entropy = _ngram_entropy(tokens)
    protected = protected_ratio(prompt)
    # Ajustement: entropie élevée → floor haut (conserver l'info)
    floor = 0.10 + entropy * 0.20 + protected * 0.15
    return max(0.05, min(0.50, floor))
