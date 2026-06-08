"""Example Reduction — Example clustering and deduplication.

Clusters similar examples (using MinHash overlap) and keeps
representative examples, reducing redundancy while preserving coverage.
"""

import re
import hashlib
from typing import List, Tuple, Dict, Set, Optional
from dataclasses import dataclass, field

from .dedup import minhash_signature, jaccard_similarity, _shingle


@dataclass
class Example:
    text: str
    embeddings: Optional[List[float]] = None
    tags: Set[str] = field(default_factory=set)
    original_index: int = 0


@dataclass
class ExampleCluster:
    examples: List[Example] = field(default_factory=list)
    centroid_text: str = ""
    tags: Set[str] = field(default_factory=set)


def extract_examples(text: str) -> List[Example]:
    """Extract example sentences/blocks from text.

    Recognizes:
      - "For example:", "e.g.", "such as" patterns
      - Bullet list items
      - Numbered examples
      - Code blocks
      - Quoted examples
    """
    lines = text.split('\n')
    examples = []
    in_example_block = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Lines explicitly starting with example indicators
        if re.search(r'\b(for\s+example|for\s+instance|e\.g\.|such\s+as|'
                     r'example:|examples:)\b', stripped, re.I):
            in_example_block = True
            after_marker = re.split(
                r'\b(for\s+example|for\s+instance|e\.g\.|such\s+as|'
                r'example:|examples:)\s*',
                stripped, flags=re.I
            )
            if len(after_marker) > 2 and after_marker[2].strip():
                examples.append(Example(text=after_marker[2].strip(), original_index=i))
            continue

        if in_example_block and stripped and not stripped.startswith('#'):
            examples.append(Example(text=stripped, original_index=i))
        else:
            in_example_block = False

    return examples


def cluster_examples(
    examples: List[Example],
    threshold: float = 0.7,
    max_examples: int = 3
) -> List[Example]:
    """Cluster similar examples, keep up to `max_examples` representative ones.

    Uses MinHash similarity on 3-word shingles.
    """
    if len(examples) <= max_examples:
        return examples

    # Compute signatures
    sigs = []
    for ex in examples:
        shingles = _shingle(ex.text, k=3)
        from .dedup import _HASH_FUNCS, _NUM_HASHES
        sig = minhash_signature(shingles, _HASH_FUNCS)
        sigs.append(sig)

    # Greedy clustering
    clusters: List[ExampleCluster] = []
    assigned = [False] * len(examples)

    for i in range(len(examples)):
        if assigned[i]:
            continue
        cluster = ExampleCluster()
        cluster.examples.append(examples[i])
        cluster.tags.update(examples[i].tags)
        assigned[i] = True

        for j in range(i + 1, len(examples)):
            if assigned[j]:
                continue
            sim = jaccard_similarity(sigs[i], sigs[j])
            if sim >= threshold:
                cluster.examples.append(examples[j])
                cluster.tags.update(examples[j].tags)
                assigned[j] = True

        clusters.append(cluster)

    # Pick representative from each cluster (first by position)
    reduced = []
    for cluster in clusters:
        reduced.append(cluster.examples[0])
        if len(reduced) >= max_examples:
            break

    return reduced


def reduce_examples(text: str, max_examples: int = 3, threshold: float = 0.7) -> str:
    """Extract, cluster, and reduce examples in text.

    Returns text with redundant examples removed.
    """
    examples = extract_examples(text)
    if not examples:
        return text

    reduced = cluster_examples(examples, threshold=threshold, max_examples=max_examples)

    # If reduction happened, replace examples in text
    if len(reduced) < len(examples):
        lines = text.split('\n')
        kept_indices = {ex.original_index for ex in reduced}
        new_lines = []
        for i, line in enumerate(lines):
            # Check if this line is an example line we should filter
            is_example = any(ex.original_index == i for ex in examples)
            if is_example and i not in kept_indices and "PROTECTED_" not in line:
                continue  # skip redundant example (but keep if it contains protected spans)
            new_lines.append(line)
        return '\n'.join(new_lines)

    return text
