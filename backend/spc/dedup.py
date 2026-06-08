"""Phase 7 — Deduplication.

Two levels:
  - Exact: SHA256 hash → removes byte-identical blocks
  - Near: MinHash + Jaccard similarity → merges near-duplicate blocks
"""

import hashlib
import struct
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════
# 1. EXACT DEDUP
# ═══════════════════════════════════════════════════════════════


def hash_block(text: str) -> str:
    """Return SHA256 hex digest of text block (normalized whitespace)."""
    normalized = ' '.join(text.split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def dedup_exact(blocks: List[str]) -> Tuple[List[str], Dict[str, int]]:
    """Remove exact duplicates from a list of text blocks.

    Returns:
        (deduplicated_blocks, hash_count_map)
    """
    seen: Dict[str, Tuple[str, int]] = {}
    order: List[str] = []

    for block in blocks:
        h = hash_block(block)
        if h in seen:
            _text, count = seen[h]
            seen[h] = (_text, count + 1)
        else:
            seen[h] = (block, 1)
            order.append(h)

    result = []
    hash_counts: Dict[str, int] = {}
    for h in order:
        text, count = seen[h]
        result.append(text)
        hash_counts[h] = count

    return result, hash_counts


def find_duplicate_regions(text: str, min_block_len: int = 50) -> Dict[str, List[Tuple[int, int]]]:
    """Find regions of repeated text."""
    from .parser import flatten, parse
    tree = parse(text)
    blocks = []
    block_spans: Dict[str, List[Tuple[int, int]]] = {}

    for node in flatten(tree):
        content = node.content.strip()
        if len(content) < min_block_len:
            continue
        h = hash_block(content)
        if h not in block_spans:
            block_spans[h] = []
        start = text.find(content[:20])
        block_spans[h].append((start, start + len(content)))

    return {h: spans for h, spans in block_spans.items() if len(spans) > 1}


# ═══════════════════════════════════════════════════════════════
# 2. NEAR-DEDUP — MinHash + Jaccard
# ═══════════════════════════════════════════════════════════════

# Number of hash functions for MinHash signature
_NUM_HASHES = 64


def _generate_hash_funcs(count: int) -> List[callable]:
    """Generate `count` random hash functions using universal hashing."""
    import random
    random.seed(42)
    funcs = []
    for _ in range(count):
        a = random.randint(1, 2**31 - 1)
        b = random.randint(0, 2**31 - 1)
        def _make_hash(aa, bb):
            def _h(x):
                # Use Python's built-in hash with different seeds
                return (aa * hash(x) + bb) & 0xFFFFFFFF
            return _h
        funcs.append(_make_hash(a, b))
    return funcs


_HASH_FUNCS = _generate_hash_funcs(_NUM_HASHES)


def _shingle(text: str, k: int = 3) -> Set[str]:
    """Generate k-shingles from text."""
    words = text.split()
    if len(words) < k:
        return {text}
    return {' '.join(words[i:i+k]) for i in range(len(words) - k + 1)}


def minhash_signature(shingles: Set[str], hash_funcs: List[callable]) -> List[int]:
    """Compute MinHash signature for a set of shingles."""
    sig = [float('inf')] * len(hash_funcs)
    for shingle in shingles:
        hvals = [f(shingle) for f in hash_funcs]
        for i, hv in enumerate(hvals):
            if hv < sig[i]:
                sig[i] = hv
    return sig


def jaccard_similarity(sig_a: List[int], sig_b: List[int]) -> float:
    """Estimate Jaccard similarity from MinHash signatures."""
    if len(sig_a) != len(sig_b):
        return 0.0
    matches = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
    return matches / len(sig_a)


@dataclass
class NearDuplicate:
    index_a: int
    index_b: int
    similarity: float
    text_a: str
    text_b: str


def dedup_near(blocks: List[str], threshold: float = 0.85) -> Tuple[List[str], List[NearDuplicate]]:
    """Remove near-duplicate blocks using MinHash + Jaccard.

    Args:
        blocks: list of text blocks
        threshold: similarity threshold (0.0-1.0) above which blocks are merged

    Returns:
        (deduplicated_blocks, duplicate_pairs_found)
    """
    if len(blocks) < 2:
        return blocks, []

    # Compute signatures
    signatures = []
    for block in blocks:
        shingles = _shingle(block)
        sig = minhash_signature(shingles, _HASH_FUNCS)
        signatures.append(sig)

    # Find near-duplicates
    keep = [True] * len(blocks)
    duplicates = []

    for i in range(len(blocks)):
        if not keep[i]:
            continue
        for j in range(i + 1, len(blocks)):
            if not keep[j]:
                continue
            sim = jaccard_similarity(signatures[i], signatures[j])
            if sim >= threshold:
                keep[j] = False
                duplicates.append(NearDuplicate(
                    index_a=i, index_b=j,
                    similarity=sim,
                    text_a=blocks[i][:100],
                    text_b=blocks[j][:100],
                ))

    result = [blocks[i] for i in range(len(blocks)) if keep[i]]
    return result, duplicates
