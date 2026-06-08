"""Quality Validation — Stage 2 of enterprise compression pipeline.

Validates compressed output against original using:
1. Cosine similarity (embedding-based) if embedder available
2. Token ratio check
3. Critical content preservation heuristics
4. Protected span integrity
"""

import re
import logging
import numpy as np
from typing import Optional, Tuple

from .chunk_semantic import _embed, _get_embedder

logger = logging.getLogger(__name__)

_MIN_SIMILARITY_THRESHOLD = 0.60


def cosine_similarity(text_a: str, text_b: str) -> float:
    """Compute cosine similarity between two texts via MiniLM embeddings."""
    embedder, tokenizer = _get_embedder()
    if embedder is None:
        return 1.0
    emb = _embed([text_a, text_b])
    a, b = emb[0], emb[1]
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _critical_content_preserved(original: str, compressed: str) -> Tuple[bool, list]:
    """Check for preserved critical patterns: URLs, emails, code blocks, JSON."""
    critical_patterns = {
        "url": r"https?://[^\s,)}]+",
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "json_obj": r'\{[^}]+"[^}]+"[^}]*\}',
        "json_arr": r'\[[^\]]+"[^\]]*\]',
        "code_inline": r"`[^`]+`",
        "code_block": r"```.*?```",
    }
    missing = []
    for label, pattern in critical_patterns.items():
        orig_hits = set(re.findall(pattern, original, re.DOTALL))
        comp_hits = set(re.findall(pattern, compressed, re.DOTALL))
        for hit in orig_hits:
            if hit not in comp_hits and len(hit) > 5:
                missing.append((label, hit[:80]))
    return len(missing) == 0, missing


def _protected_span_integrity(compressed: str, registry=None) -> Tuple[bool, list]:
    """Verify that protected spans (PROTECTED_ markers) remain intact."""
    protected_pat = re.compile(r"PROTECTED_\d+")
    if registry:
        from .protection import ProtectedRegistry
        if isinstance(registry, ProtectedRegistry):
            for protected in registry.items():
                key = protected.id
                if key not in compressed:
                    return False, [key]
    return True, []


def _token_ratio_valid(original: str, compressed: str, max_ratio: float = 2.0) -> Tuple[bool, float]:
    """Validate compressed is not longer than original (within tolerance)."""
    if not original or not compressed:
        return False, 0.0
    o_len = len(original) // 4
    c_len = len(compressed) // 4
    if o_len == 0:
        return True, 1.0
    ratio = c_len / max(o_len, 1)
    return ratio <= max_ratio, ratio


def validate_quality(
    original: str,
    compressed: str,
    registry=None,
    min_similarity: float = _MIN_SIMILARITY_THRESHOLD,
) -> dict:
    """Run all quality checks and return a result dict.

    Returns:
        {
            "passed": bool,
            "cosine_similarity": float,
            "token_ratio": float,
            "critical_missing": list,
            "protected_missing": list,
            "errors": list[str],
        }
    """
    errors = []
    sim = cosine_similarity(original, compressed)

    if sim < min_similarity:
        errors.append(f"Cosine similarity below threshold: {sim:.3f} < {min_similarity:.3f}")

    ratio_valid, ratio = _token_ratio_valid(original, compressed)
    if not ratio_valid:
        errors.append(f"Token ratio {ratio:.2f}x exceeds maximum")

    crit_ok, crit_missing = _critical_content_preserved(original, compressed)
    if not crit_ok:
        labels = [m[0] for m in crit_missing[:5]]
        errors.append(f"Missing critical content: {', '.join(labels)}")

    prot_ok, prot_missing = _protected_span_integrity(compressed, registry)
    if not prot_ok:
        errors.append(f"Missing {len(prot_missing)} protected spans")

    return {
        "passed": len(errors) == 0,
        "cosine_similarity": round(sim, 4),
        "token_ratio": round(ratio, 3),
        "critical_missing": crit_missing[:10],
        "protected_missing": prot_missing[:10],
        "errors": errors,
    }
