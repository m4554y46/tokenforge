"""
Seed ACE avec donnees d'entrainement synthetiques.

Genere 600+ requetes ACE avec signaux pour entrainer le modele de qualite,
puis lance l'entrainement (LightGBM → ONNX).

Utilisation: python -m backend.ace.train_seed
"""

import json
import logging
import os
import sys
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FORGE_ACE_ENABLED"] = "1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ace-seed")

random.seed(42)

# ── Configuration du modele de qualite ──
# On simule que plus le taux de compression est eleve, plus le risque de
# reformulation est grand. Le modele devra apprendre cette relation.

TASK_TYPES = ["code","analytique","creatif","factuel","traduction","resume","brainstorming","instruction"]
SPECIFICITIES = ["generic","domain_jargon","entity_rich"]
LENGTH_BUCKETS = ["short","medium","long","very_long"]
RATES = [0.0, 0.15, 0.25, 0.40, 0.55, 0.70]
MODELS = ["gpt-4o", "gpt-4o-mini", "claude-3.5-sonnet"]
PROVIDERS = ["openai", "anthropic"]

TENANT_ID = "seed-tenant"


def _signal_probability(rate: float, task_type: str) -> dict:
    """Simule la probabilite de signaux selon le taux et la tache.

    Regles:
    - Taux bas (0.15) → copie frequente (qualite preservee)
    - Taux haut (0.70) → reformulation plus frequente
    - Code → plus de reformulations qu'analytique
    - Factuel → plus de thumbs_up
    """
    base_reform = rate * 0.3
    base_copy = 0.5 - rate * 0.4
    base_cont = 0.1 + rate * 0.1
    base_thumbs = 0.3 + (1.0 - rate) * 0.2
    base_task_ok = 0.7 - rate * 0.3

    if task_type == "code":
        base_reform *= 1.3
        base_task_ok *= 0.7
    elif task_type == "factuel":
        base_reform *= 0.5
        base_thumbs *= 1.3
        base_task_ok *= 1.2
    elif task_type == "traduction":
        base_copy *= 0.8
        base_reform *= 1.1
    elif task_type == "creatif":
        base_thumbs *= 0.7
        base_cont *= 1.3

    return {
        "copy": 1 if random.random() < base_copy else 0,
        "continuation": 1 if random.random() < base_cont else 0,
        "reformulation": 1 if random.random() < base_reform else 0,
        "thumbs_up": 1 if random.random() < base_thumbs else 0,
        "task_success": 1 if random.random() < base_task_ok else 0,
    }


def seed_training_data(n: int = 600):
    from backend.core.database_v2 import _param, execute, init_v2_db
    from backend.ace.state import _now

    init_v2_db()

    inserted = 0
    profiles = {0.0: "bypass", 0.15: "safe", 0.25: "light", 0.40: "balanced", 0.55: "aggressive", 0.70: "max"}

    for i in range(n):
        task = random.choice(TASK_TYPES)
        spec = random.choice(SPECIFICITIES)
        lb = random.choice(LENGTH_BUCKETS)
        rate = random.choice(RATES)
        model = random.choice(MODELS)
        provider = random.choice(PROVIDERS)
        cluster = random.randint(0, 19)

        # Plus le prompt est long, plus le taux reel tend vers le taux nominal
        tok_orig = random.randint(200, 4000)
        noise = random.uniform(0.85, 1.0)
        rate_actual = round(rate * noise, 4)

        latency = random.gauss(500, 200)
        savings = round((tok_orig - int(tok_orig * (1 - rate_actual))) / tok_orig * 100, 2)

        signals = _signal_probability(rate, task)
        signals_json = json.dumps(signals)

        p = _param()
        try:
            execute(
                f"INSERT INTO ace_requests "
                f"(tenant_id, user_id, session_id, prompt_hash, task_type, specificity, "
                f"length_bucket, user_cluster, model, provider, profile_chosen, rate_actual, "
                f"tokens_original, tokens_compressed, savings_percent, latency_ms, "
                f"was_exploration, signals_json, created_at) "
                f"VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})",
                (
                    TENANT_ID, f"user_{cluster}", f"syn_{i:04d}", f"h{i:04x}",
                    task, spec, lb, cluster, model, provider,
                    profiles[rate], rate_actual,
                    tok_orig, int(tok_orig * (1 - rate_actual)),
                    savings, round(latency, 2),
                    1 if random.random() < 0.05 else 0,
                    signals_json, _now(),
                ),
            )
            inserted += 1
        except Exception as e:
            logger.warning("Insert %d failed: %s", i, e)

    logger.info("Inserted %d synthetic training rows", inserted)
    return inserted


def train():
    from backend.ace.train import train_quality, export_onnx

    logger.info("Training quality model...")
    ok = train_quality(min_samples=100)
    if ok:
        logger.info("Quality model trained OK, exporting ONNX...")
        onnx_path = export_onnx()
        if onnx_path:
            logger.info("ONNX exported to %s", onnx_path)
        else:
            logger.warning("ONNX export failed")
    else:
        logger.warning("Quality model training failed")

    # Also train embeddings
    from backend.ace.train import train_embeddings
    logger.info("Training embeddings...")
    emb_ok = train_embeddings(min_contexts=20)
    logger.info("Embeddings training: %s", emb_ok)

    return ok


if __name__ == "__main__":
    n = seed_training_data(600)
    if n >= 100:
        train()
    else:
        logger.error("Not enough rows seeded (%d)", n)
