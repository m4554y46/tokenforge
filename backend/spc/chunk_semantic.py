"""Semantic Chunk Filter — Stage 3 of enterprise compression pipeline.

Splits text into semantic chunks, embeds locally via MiniLM,
scores by cosine similarity to task intent, drops low-relevance chunks.
"""

import re
import logging
import numpy as np
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import torch
    from transformers import AutoModel, AutoTokenizer

    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

_EMBEDDER = None
_EMB_TOKENIZER = None
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def _get_embedder():
    global _EMBEDDER, _EMB_TOKENIZER
    if _EMBEDDER is None and _TORCH_AVAILABLE:
        try:
            _EMB_TOKENIZER = AutoTokenizer.from_pretrained(_MODEL_NAME)
            _EMBEDDER = AutoModel.from_pretrained(_MODEL_NAME)
            _EMBEDDER.eval()
            _EMBEDDER.requires_grad_(False)
            logger.info("Loaded MiniLM embedder: %s", _MODEL_NAME)
        except Exception as exc:
            logger.warning("Failed to load MiniLM embedder: %s", exc)
    return _EMBEDDER, _EMB_TOKENIZER


def _mean_pooling(token_embeddings, attention_mask):
    token_embeddings = token_embeddings * attention_mask.unsqueeze(-1)
    return token_embeddings.sum(1) / attention_mask.sum(1, keepdim=True)


def _embed(texts: List[str]) -> np.ndarray:
    model, tokenizer = _get_embedder()
    if model is None or tokenizer is None:
        return np.ones((len(texts), 384))
    inputs = tokenizer(
        texts, padding=True, truncation=True, max_length=256, return_tensors="pt"
    )
    with torch.no_grad():
        outputs = model(**inputs)
    embeddings = _mean_pooling(outputs.last_hidden_state, inputs["attention_mask"])
    return embeddings.cpu().numpy()


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_norm = a / np.linalg.norm(a, axis=1, keepdims=True)
    b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
    return a_norm @ b_norm.T


class RecursiveCharacterTextSplitter:
    """Recursive text splitter (langchain-compatible semantics, zero dependency)."""

    def __init__(
        self,
        chunk_size: int = 256,
        chunk_overlap: int = 20,
        separators: Optional[List[str]] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", "? ", "! ", " "]

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []
        chunks = self._split(text, self.separators)
        return self._merge(chunks)

    def _split(self, text: str, separators: List[str]) -> List[str]:
        if not separators:
            return [text[i : i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]
        sep = separators[0]
        parts = text.split(sep) if sep != " " else text.split()
        if sep == " ":
            parts = [p + " " for p in parts[:-1]] + [parts[-1]] if len(parts) > 1 else parts
        rest = separators[1:]
        result = []
        for part in parts:
            if len(part) > self.chunk_size and rest:
                result.extend(self._split(part, rest))
            else:
                result.append(part)
        return result

    def _merge(self, chunks: List[str]) -> List[str]:
        merged = []
        current = ""
        for c in chunks:
            if not c.strip():
                continue
            if len(current) + len(c) <= self.chunk_size:
                current = (current + " " + c).strip()
            else:
                if current:
                    merged.append(current)
                current = c
        if current:
            merged.append(current)
        return merged if merged else chunks


def score_chunks(
    chunks: List[str], task_intent: str = ""
) -> List[float]:
    if not chunks:
        return []
    if not task_intent:
        return [1.0] * len(chunks)
    emb_chunks = _embed(chunks)
    emb_task = _embed([task_intent])
    sim = cosine_similarity(emb_chunks, emb_task).flatten()
    return [float(s) for s in sim]


def filter_chunks(
    chunks: List[str],
    scores: List[float],
    threshold: float = 0.30,
    min_keep: int = 1,
) -> Tuple[List[str], List[float], List[float]]:
    kept_chunks, kept_scores, kept_orig = [], [], []
    dropped = []
    for c, s in zip(chunks, scores):
        if s >= threshold:
            kept_chunks.append(c)
            kept_scores.append(s)
        else:
            dropped.append((c, s))
    if not kept_chunks:
        best = max(zip(chunks, scores), key=lambda x: x[1])
        kept_chunks = [best[0]]
        kept_scores = [best[1]]
    return kept_chunks, kept_scores, [s for _, s in dropped]


def estimate_task_intent(text: str) -> str:
    """Extract the most likely task intent from a prompt.

    Heuristic: first sentence containing a question word or imperative verb,
    or the first paragraph if no clear intent is found.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:5]:
        lower = line.lower()
        if any(w in lower for w in ["what", "how", "why", "which", "who",
                                      "summarize", "explain", "analyze",
                                      "generate", "create", "write",
                                      "translate", "classify", "extract"]):
            return line[:300]
    return lines[0][:300] if lines else ""


def compress_with_semantic_chunking(
    text: str,
    task_intent: Optional[str] = None,
    threshold: float = 0.30,
    chunk_size: int = 256,
) -> Tuple[str, dict]:
    """Run Stage 3: chunk → embed → score → filter → rebuild.

    Returns:
        (compressed_text, metadata_dict)
    """
    meta = {"original_length": len(text), "chunks_total": 0, "chunks_kept": 0,
            "dropped_ratio": 0.0, "embedder_available": _EMBEDDER is not None}

    if not text:
        return text, meta

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=20)
    chunks = splitter.split_text(text)
    meta["chunks_total"] = len(chunks)

    if len(chunks) <= 1:
        meta["chunks_kept"] = len(chunks)
        return text, meta

    intent = task_intent or estimate_task_intent(text)
    scores = score_chunks(chunks, intent)
    kept, kept_scores, dropped_scores = filter_chunks(chunks, scores, threshold=threshold)

    meta["chunks_kept"] = len(kept)
    meta["dropped_ratio"] = round(1.0 - len(kept) / max(len(chunks), 1), 3)
    meta["avg_score_kept"] = round(float(np.mean(kept_scores)), 3) if kept_scores else 0.0
    meta["avg_score_dropped"] = round(float(np.mean(dropped_scores)), 3) if dropped_scores else 0.0

    compressed = " ".join(kept)
    return compressed, meta
