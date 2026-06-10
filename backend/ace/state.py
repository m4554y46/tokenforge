import threading
import time
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.core.database_v2 import _param, execute, query_all, query_one

N_CLUSTERS = 20
LENGTH_BUCKETS = ["short", "medium", "long", "very_long"]
TASK_TYPES = ["code", "analytique", "creatif", "factuel", "traduction", "resume", "brainstorming", "instruction"]
RATES = [0.0, 0.15, 0.25, 0.40, 0.55, 0.70]
DEFAULT_MODEL = "gpt-4o"

FAILURE_COST = 0.01  # fallback global si pas de correspondance tache
TF_SHARE = 0.20
TOKEN_PRICE = 0.000005

MIN_CLIENT_SAVINGS = 0.001  # fallback global

# Seuil minimum d'économies pour que le client voie la différence.
# Proportionnel au prix du modèle : un modèle 3× moins cher nécessite
# 3× plus de tokens pour atteindre le même seuil.
MIN_CLIENT_SAVINGS_BY_MODEL = {
    "gpt-4o":            0.0010,
    "gpt-4o-mini":       0.0003,
    "claude-3.5-sonnet": 0.0006,
    "claude-3-haiku":    0.00005,
    "gemini-1.5-pro":    0.00025,
    "gemini-1.5-flash":  0.000015,
    "gpt-4":             0.0020,
    "gpt-3.5-turbo":     0.0001,
}


def get_min_client_savings(model: str) -> float:
    """Seuil d'économies minimum pour que le client perçoive un bénéfice.

    Proportionnel au prix du modèle : un modèle plus cher économise plus
    par token compressé, donc le seuil peut être plus haut.
    """
    return MIN_CLIENT_SAVINGS_BY_MODEL.get(model.lower(), MIN_CLIENT_SAVINGS)

# Coût d'échec par type de tâche — une compression ratée n'a pas le même
# impact selon ce qu'on comprime. Factuel = cheap (reposer la question),
# code = cher (bug en prod).
FAILURE_COST_BY_TASK = {
    "factuel":      0.002,   # fait reposer la question, coût quasi nul
    "resume":       0.003,   # re-résumé rapide
    "traduction":   0.005,   # vérifiable par l'utilisateur
    "brainstorming":0.005,   # créatif, perte acceptable
    "general":      0.008,   # tâche mixte, coût moyen
    "analytique":   0.008,   # analyse, perte partielle
    "creatif":      0.010,   # subjectif, peut décevoir
    "instruction":  0.015,   # instructions complexes, risque d'échec
    "code":         0.025,   # bug = cher
}


def get_failure_cost(task_type: str) -> float:
    """Renvoie le FAILURE_COST adapté au type de tâche.

    Permet à ACE d'être moins conservateur pour les tâches simples
    (factuel, resume) et plus prudent pour le code ou les instructions.
    """
    return FAILURE_COST_BY_TASK.get(task_type, FAILURE_COST)

PROFILE_COMPUTE_COST = {
    "bypass": 0.0,
    "safe": 0.000005,
    "light": 0.000010,
    "balanced": 0.000020,
    "aggressive": 0.000035,
    "max": 0.000050,
}

RATE_TO_PROFILE = {
    0.0: "bypass",
    0.15: "safe",
    0.25: "light",
    0.40: "balanced",
    0.55: "aggressive",
    0.70: "max",
}

TENANT_DEFAULTS: Dict[str, float] = {}
_cache: OrderedDict = OrderedDict()
_cache_max = 10000
_cache_ttl = 300
_lock = threading.Lock()


def _cell_key(
    tenant_id: str, user_cluster: int, task_type: str,
    length_bucket: str, model: str, rate: float,
) -> str:
    return f"{tenant_id}|{user_cluster}|{task_type}|{length_bucket}|{model}|{rate}"


def _now() -> str:
    return datetime.now().isoformat()


class CellState:
    __slots__ = (
        "tenant_id", "user_cluster", "task_type", "length_bucket",
        "model", "rate", "quality_sum", "n_samples", "n_explorations",
        "last_updated",
    )

    def __init__(
        self, tenant_id: str = "default", user_cluster: int = 0,
        task_type: str = "factuel", length_bucket: str = "medium",
        model: str = "gpt-4o", rate: float = 0.0,
        quality_sum: float = 0.0, n_samples: float = 0.0,
        n_explorations: int = 0, last_updated: str = "",
    ):
        self.tenant_id = tenant_id
        self.user_cluster = user_cluster
        self.task_type = task_type
        self.length_bucket = length_bucket
        self.model = model
        self.rate = rate
        self.quality_sum = quality_sum
        self.n_samples = n_samples
        self.n_explorations = n_explorations
        self.last_updated = last_updated or _now()

    @property
    def expected_quality(self) -> float:
        if self.n_samples < 1:
            return _get_tenant_default(self.tenant_id, self.rate)
        return self.quality_sum / self.n_samples

    @property
    def variance(self) -> float:
        if self.n_samples < 2:
            return 1.0
        p = self.expected_quality
        return p * (1.0 - p) / self.n_samples

    @property
    def profile_name(self) -> str:
        return RATE_TO_PROFILE.get(self.rate, "bypass")

    def to_dict(self) -> Dict:
        return {
            "tenant_id": self.tenant_id,
            "user_cluster": self.user_cluster,
            "task_type": self.task_type,
            "length_bucket": self.length_bucket,
            "model": self.model,
            "rate": self.rate,
            "expected_quality": round(self.expected_quality, 4),
            "variance": round(self.variance, 6),
            "n_samples": self.n_samples,
            "n_explorations": self.n_explorations,
            "profile": self.profile_name,
        }


def _get_tenant_default(tenant_id: str, rate: float) -> float:
    if rate == 0.0:
        return 1.0
    key = (tenant_id, rate)
    if key in TENANT_DEFAULTS:
        return TENANT_DEFAULTS[key]
    p = _param()
    row = query_one(
        f"SELECT AVG(quality_sum / NULLIF(n_samples, 0)) as avg_q "
        f"FROM ace_states WHERE tenant_id={p} AND rate={p} AND n_samples > 5",
        (tenant_id, rate),
    )
    val = (row["avg_q"] if row and row["avg_q"] else 0.85)
    TENANT_DEFAULTS[key] = val
    return val


def _from_row(row: Dict) -> CellState:
    return CellState(
        tenant_id=row["tenant_id"],
        user_cluster=row["user_cluster"],
        task_type=row["task_type"],
        length_bucket=row["length_bucket"],
        model=row["model"],
        rate=row["rate"],
        quality_sum=row["quality_sum"],
        n_samples=row["n_samples"],
        n_explorations=row.get("n_explorations", 0),
        last_updated=row.get("last_updated", ""),
    )


def read_cell(
    tenant_id: str, user_cluster: int, task_type: str,
    length_bucket: str, model: str, rate: float,
) -> CellState:
    key = _cell_key(tenant_id, user_cluster, task_type, length_bucket, model, rate)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    p = _param()
    row = query_one(
        f"SELECT * FROM ace_states WHERE "
        f"tenant_id={p} AND user_cluster={p} AND task_type={p} "
        f"AND length_bucket={p} AND model={p} AND rate={p}",
        (tenant_id, user_cluster, task_type, length_bucket, model, rate),
    )
    if row:
        state = _from_row(row)
    else:
        state = CellState(
            tenant_id=tenant_id, user_cluster=user_cluster,
            task_type=task_type, length_bucket=length_bucket,
            model=model, rate=rate,
        )
    with _lock:
        _cache[key] = state
        while len(_cache) > _cache_max:
            _cache.popitem(last=False)
    return state


def read_cells_for_context(
    tenant_id: str, user_cluster: int, task_type: str,
    length_bucket: str, model: str,
) -> Dict[float, CellState]:
    result: Dict[float, CellState] = {}
    for rate in RATES:
        result[rate] = read_cell(tenant_id, user_cluster, task_type, length_bucket, model, rate)
    return result


def write_cell(state: CellState) -> None:
    state.last_updated = _now()
    key = _cell_key(
        state.tenant_id, state.user_cluster, state.task_type,
        state.length_bucket, state.model, state.rate,
    )
    with _lock:
        _cache[key] = state
    p = _param()
    execute(
        f"INSERT OR REPLACE INTO ace_states "
        f"(tenant_id, user_cluster, task_type, length_bucket, model, rate, "
        f"quality_sum, n_samples, n_explorations, last_updated) "
        f"VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p})",
        (
            state.tenant_id, state.user_cluster, state.task_type,
            state.length_bucket, state.model, state.rate,
            state.quality_sum, state.n_samples, state.n_explorations,
            state.last_updated,
        ),
    )


def record_request(
    tenant_id: str, user_id: str, session_id: str, prompt_hash: str,
    task_type: str, specificity: str, length_bucket: str,
    user_cluster: int, model: str, provider: str,
    profile_chosen: str, rate_actual: Optional[float],
    tokens_original: int, tokens_compressed: int,
    latency_ms: float, was_exploration: bool,
) -> None:
    savings = 0
    if tokens_original > 0:
        savings = (tokens_original - tokens_compressed) / tokens_original * 100
    p = _param()
    execute(
        f"INSERT INTO ace_requests "
        f"(tenant_id, user_id, session_id, prompt_hash, task_type, specificity, "
        f"length_bucket, user_cluster, model, provider, profile_chosen, rate_actual, "
        f"tokens_original, tokens_compressed, savings_percent, latency_ms, "
        f"was_exploration, signals_json, created_at) "
        f"VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},'{{}}',{p})",
        (
            tenant_id, user_id, session_id, prompt_hash, task_type,
            specificity, length_bucket, user_cluster, model, provider or "",
            profile_chosen, rate_actual,
            tokens_original, tokens_compressed, round(savings, 2),
            round(latency_ms, 2), 1 if was_exploration else 0,
            _now(),
        ),
    )


def record_session(
    session_id: str, tenant_id: str, user_id: str,
    prompt_hash: str, prompt_preview: str, response_hash: str,
    profile_chosen: str,
) -> None:
    p = _param()
    execute(
        f"INSERT OR REPLACE INTO ace_sessions "
        f"(session_id, tenant_id, user_id, prompt_hash, prompt_preview, "
        f"response_hash, profile_chosen, created_at) "
        f"VALUES ({p},{p},{p},{p},{p},{p},{p},{p})",
        (
            session_id, tenant_id, user_id, prompt_hash,
            prompt_preview[:200], response_hash or "",
            profile_chosen, _now(),
        ),
    )
