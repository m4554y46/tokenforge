"""Génération d'embeddings pour la couche mémoire."""

import hashlib
import json
import threading
from typing import List, Optional

import numpy as np

from backend.config import get_settings

_model = None
_lock = threading.Lock()
_DIM = 384


def _hash_embedding(text: str, dim: int = _DIM) -> List[float]:
    """Fallback déterministe sans modèle — stable et rapide."""
    h = hashlib.sha256(text.encode()).digest()
    rng = np.random.default_rng(int.from_bytes(h[:8], "big"))
    vec = rng.standard_normal(dim).astype(np.float32)
    vec /= np.linalg.norm(vec) + 1e-9
    return vec.tolist()


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        try:
            from sentence_transformers import SentenceTransformer
            settings = get_settings()
            _model = SentenceTransformer(settings.MEMORY_EMBEDDING_MODEL)
            return _model
        except Exception:
            return None


def embed_text(text: str) -> List[float]:
    model = _get_model()
    if model is None:
        return _hash_embedding(text)
    try:
        vec = model.encode(text, normalize_embeddings=True)
        return vec.tolist()
    except Exception:
        return _hash_embedding(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    model = _get_model()
    if model is None:
        return [_hash_embedding(t) for t in texts]
    try:
        vecs = model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vecs]
    except Exception:
        return [_hash_embedding(t) for t in texts]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = (np.linalg.norm(va) * np.linalg.norm(vb)) + 1e-9
    return float(np.dot(va, vb) / denom)


def serialize_embedding(vec: List[float]) -> str:
    return json.dumps(vec)


def deserialize_embedding(raw: str) -> List[float]:
    return json.loads(raw)
