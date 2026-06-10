"""Compression-Behavior Embeddings.

Factorise la matrice (contexte × taux → qualité) pour apprendre
des embeddings de compressibilité utilisés pour le cold start.
"""

import logging
import os
import pickle
from typing import Dict, List, Optional, Tuple

import numpy as np

from backend.ace.state import RATES, read_cell
from backend.core.database_v2 import _param, query_all

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 4
CACHE_PATH = os.path.join(os.path.dirname(__file__), "_models", "embeddings.pkl")


class CompressionEmbeddings:
    def __init__(self):
        self._U: Optional[np.ndarray] = None
        self._V: Optional[np.ndarray] = None
        self._context_labels: List[str] = []
        self._rate_labels: List[float] = []
        self._loaded = False

    def is_available(self) -> bool:
        if not self._loaded:
            self._try_load()
        return self._U is not None

    def _try_load(self) -> None:
        try:
            if os.path.exists(CACHE_PATH):
                with open(CACHE_PATH, "rb") as f:
                    data = pickle.load(f)
                self._U = data["U"]
                self._V = data["V"]
                self._context_labels = data["context_labels"]
                self._rate_labels = data["rate_labels"]
                self._loaded = True
                logger.info("Embeddings loaded (%d contexts, dim=%d)", len(self._context_labels), self._U.shape[1])
        except Exception as e:
            logger.warning("Failed to load embeddings: %s", e)

    def fit(self, min_contexts: int = 50) -> bool:
        contexts = self._load_contexts()
        if len(contexts) < min_contexts:
            logger.info("Not enough contexts for embeddings (%d < %d)", len(contexts), min_contexts)
            return False
        M_rows = []
        labels = []
        for ctx_id, ctx_data in contexts.items():
            row = []
            for rate in RATES:
                row.append(ctx_data.get(rate, 0.5))
            M_rows.append(row)
            labels.append(ctx_id)
        M = np.array(M_rows, dtype=np.float32)
        n_rows, n_cols = M.shape
        U_full, S, Vt = np.linalg.svd(M, full_matrices=False)
        d = min(EMBEDDING_DIM, n_rows, n_cols)
        U = U_full[:, :d] * np.sqrt(S[:d])
        V = Vt[:d, :].T * np.sqrt(S[:d])
        self._U = U
        self._V = V
        self._context_labels = labels
        self._rate_labels = RATES.copy()
        self._save()
        logger.info("Embeddings fitted: %d contexts → dim=%d", len(labels), d)
        return True

    def _load_contexts(self) -> Dict[str, Dict[float, float]]:
        p = _param()
        rows = query_all(
            f"SELECT tenant_id, user_cluster, task_type, length_bucket, model, "
            f"rate, quality_sum, n_samples FROM ace_states WHERE n_samples > 3",
        )
        contexts: Dict[str, Dict[float, float]] = {}
        for row in rows:
            key = f"{row['tenant_id']}|{row['user_cluster']}|{row['task_type']}|{row['length_bucket']}|{row['model']}"
            rate = row["rate"]
            q = row["quality_sum"] / row["n_samples"] if row["n_samples"] > 0 else 0.5
            if key not in contexts:
                contexts[key] = {r: 0.5 for r in RATES}
            contexts[key][rate] = q
        return contexts

    def _save(self) -> None:
        try:
            with open(CACHE_PATH, "wb") as f:
                pickle.dump({
                    "U": self._U,
                    "V": self._V,
                    "context_labels": self._context_labels,
                    "rate_labels": self._rate_labels,
                }, f)
        except Exception as e:
            logger.warning("Failed to save embeddings: %s", e)

    def get_embedding(self, context_key: str) -> Optional[np.ndarray]:
        if self._U is None:
            return None
        if context_key in self._context_labels:
            idx = self._context_labels.index(context_key)
            return self._U[idx]
        return None

    def find_similar_contexts(self, context_key: str, k: int = 5) -> List[Tuple[str, float]]:
        if self._U is None:
            return []
        if context_key in self._context_labels:
            idx = self._context_labels.index(context_key)
            vec = self._U[idx]
        else:
            vec = np.zeros(self._U.shape[1], dtype=np.float32)
        sims = []
        for i, label in enumerate(self._context_labels):
            if label == context_key:
                continue
            dot = np.dot(vec, self._U[i])
            norm = np.linalg.norm(vec) * np.linalg.norm(self._U[i])
            sim = float(dot / norm) if norm > 0 else 0.0
            sims.append((label, sim))
        sims.sort(key=lambda x: -x[1])
        return sims[:k]

    def cold_start_quality(self, features: Dict, rate: float) -> Optional[float]:
        tenant_id = features.get("tenant_id", "default")
        uc = features.get("user_cluster", 0)
        tt = features.get("task_type", "factuel")
        lb = features.get("length_bucket", "medium")
        model = features.get("model", "gpt-4o")
        key = f"{tenant_id}|{uc}|{tt}|{lb}|{model}"
        similar = self.find_similar_contexts(key, k=5)
        if not similar:
            return None
        total_w = 0.0
        total_q = 0.0
        for ctx_key, sim in similar:
            w = max(sim, 0.0)
            ctx_parts = ctx_key.split("|")
            if len(ctx_parts) == 5:
                ctx_tenant, ctx_uc, ctx_tt, ctx_lb, ctx_model = ctx_parts
                try:
                    cell = read_cell(ctx_tenant, int(ctx_uc), ctx_tt, ctx_lb, ctx_model, rate)
                    q = cell.expected_quality
                    total_q += w * q
                    total_w += w
                except Exception:
                    continue
        if total_w > 0:
            return total_q / total_w
        return None


_embeddings_instance: Optional[CompressionEmbeddings] = None


def get_embeddings() -> CompressionEmbeddings:
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = CompressionEmbeddings()
    return _embeddings_instance
