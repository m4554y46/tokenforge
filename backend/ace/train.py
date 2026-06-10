"""Pipeline d'entraînement ACE — qualité, embeddings, exploration.

Exécution : python -m backend.ace.train
Planifié : toutes les nuits (cron) ou après N nouvelles requêtes.
"""

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ace-train")


def train_all(min_samples: int = 500) -> bool:
    from backend.core.database_v2 import init_v2_db
    init_v2_db()

    ok = True
    quality_ok = train_quality(min_samples)
    if not quality_ok:
        logger.warning("Quality model training skipped or failed")
        ok = False
    embedding_ok = train_embeddings(min_contexts=50)
    if not embedding_ok:
        logger.warning("Embedding training skipped or failed")
        ok = False
    if quality_ok:
        export_ok = export_onnx()
        if not export_ok:
            logger.warning("ONNX export skipped or failed")
    logger.info("Training pipeline complete (quality=%s, embeddings=%s)", quality_ok, embedding_ok)
    return ok


def train_quality(min_samples: int = 500) -> bool:
    from backend.ace.models.quality_model import get_model
    model = get_model()
    return model.train(min_samples=min_samples)


def train_embeddings(min_contexts: int = 50) -> bool:
    from backend.ace.embeddings import get_embeddings
    emb = get_embeddings()
    return emb.fit(min_contexts=min_contexts)


def export_onnx() -> bool:
    from backend.ace.models.quality_model import get_model
    model = get_model()
    path = model.export_onnx()
    return path is not None


if __name__ == "__main__":
    success = train_all()
    sys.exit(0 if success else 1)
