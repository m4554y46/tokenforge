"""Signal detection for ACE — reformulation, continuation, and behavioral proxies."""

import hashlib
import time
import threading
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

from backend.core.database_v2 import _param, query_one, execute


_REFORMULATION_WINDOW = 30
_CONTINUATION_WINDOW = 60
_SIMILARITY_THRESHOLD = 0.65

_session_buffer: OrderedDict = OrderedDict()
_session_buffer_max = 5000
_buffer_lock = threading.Lock()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _token_overlap(a: str, b: str) -> float:
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _merge_signals(existing: Dict, new: Dict) -> Dict:
    merged = dict(existing)
    for k, v in new.items():
        if k in merged:
            if isinstance(merged[k], (int, float)) and isinstance(v, (int, float)):
                merged[k] = merged[k] or v
            else:
                merged[k] = v
        else:
            merged[k] = v
    return merged


class SignalResult:
    reformulation: bool = False
    continuation: bool = False
    similarity_score: float = 0.0
    time_since_last: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "reformulation": self.reformulation,
            "continuation": self.continuation,
            "similarity_score": round(self.similarity_score, 4),
            "time_since_last": round(self.time_since_last, 2),
        }

    @property
    def quality_proxy(self) -> float:
        if self.reformulation:
            return 0.2
        if self.continuation:
            return 0.85
        return 0.5


def detect_signals(
    session_id: str,
    user_id: str,
    tenant_id: str,
    current_prompt: str,
    current_hash: str = "",
) -> SignalResult:
    result = SignalResult()
    if not session_id or not current_prompt:
        return result

    prompt_hash = current_hash or _hash_text(current_prompt)
    now = time.time()

    with _buffer_lock:
        prev = _session_buffer.get(session_id)

    if prev is None:
        with _buffer_lock:
            _session_buffer[session_id] = {
                "prompt": current_prompt,
                "prompt_hash": prompt_hash,
                "timestamp": now,
            }
            while len(_session_buffer) > _session_buffer_max:
                _session_buffer.popitem(last=False)
        return result

    prev_prompt = prev.get("prompt", "")
    prev_timestamp = prev.get("timestamp", now)
    time_diff = now - prev_timestamp
    similarity = _token_overlap(current_prompt, prev_prompt)

    result.similarity_score = similarity
    result.time_since_last = time_diff

    with _buffer_lock:
        _session_buffer[session_id] = {
            "prompt": current_prompt,
            "prompt_hash": prompt_hash,
            "timestamp": now,
        }

    if similarity >= _SIMILARITY_THRESHOLD and time_diff <= _REFORMULATION_WINDOW:
        result.reformulation = True
    elif time_diff <= _CONTINUATION_WINDOW:
        result.continuation = True

    return result


def update_from_signals(
    tenant_id: str,
    user_cluster: int,
    task_type: str,
    length_bucket: str,
    model: str,
    rate: float,
    signal: SignalResult,
    weight_override: Optional[float] = None,
) -> float:
    q = signal.quality_proxy
    w = weight_override if weight_override is not None else _compute_weight(signal)

    if w <= 0:
        return 0.0

    from backend.ace.state import read_cell, write_cell
    cell = read_cell(tenant_id, user_cluster, task_type, length_bucket, model, rate)

    if signal.reformulation:
        cell.quality_sum -= w * (1.0 - q)
        cell.n_samples += w
    elif signal.continuation:
        cell.quality_sum += w * q
        cell.n_samples += w
    else:
        half = w * 0.5
        cell.quality_sum += half * 0.5
        cell.n_samples += half

    write_cell(cell)
    return w


def _compute_weight(signal: SignalResult) -> float:
    if signal.reformulation:
        sim_penalty = max(0.0, 1.0 - signal.similarity_score)
        time_quality = max(0.0, 1.0 - signal.time_since_last / _REFORMULATION_WINDOW)
        return 0.6 * (0.5 + 0.5 * sim_penalty) * (0.5 + 0.5 * time_quality)
    if signal.continuation:
        time_quality = max(0.0, 1.0 - signal.time_since_last / _CONTINUATION_WINDOW)
        return 0.4 * (0.5 + 0.5 * time_quality)
    return 0.1


def get_pending_signals(
    session_id: str,
    user_id: str,
    tenant_id: str,
    current_prompt: str,
    previous_request_id: Optional[int] = None,
) -> Optional[SignalResult]:
    if previous_request_id is not None:
        p = _param()
        row = query_one(
            f"SELECT signals_json FROM ace_requests WHERE id={p}",
            (previous_request_id,),
        )
        if row and row.get("signals_json", "{}") != "{}":
            import json
            existing = json.loads(row["signals_json"])
            if existing.get("reformulation") or existing.get("continuation"):
                return None
    return detect_signals(session_id, user_id, tenant_id, current_prompt)


def update_signals_for_previous(
    session_id: str,
    tenant_id: str,
    user_cluster: int,
    task_type: str,
    length_bucket: str,
    model: str,
    rate: float,
) -> None:
    p = _param()
    rows = query_all(
        f"SELECT id, prompt_hash, signals_json, prompt_preview FROM ace_requests "
        f"WHERE session_id={p} AND tenant_id={p} AND signals_json='{{}}' "
        f"ORDER BY id DESC LIMIT 3",
        (session_id, tenant_id),
    )
    from backend.core.database_v2 import query_all as qa
    recent = qa(
        f"SELECT id, prompt_hash, signals_json FROM ace_requests "
        f"WHERE session_id={p} AND tenant_id={p} AND signals_json!='{{}}' "
        f"ORDER BY id DESC LIMIT 1",
        (session_id, tenant_id),
    )
    if not rows or not recent:
        return

    for row in rows:
        if row["signals_json"] and row["signals_json"] != "{}":
            continue
        import json
        cur_signals = json.loads(row["signals_json"] or "{}")
        if cur_signals.get("reformulation") or cur_signals.get("continuation"):
            continue
        break
    else:
        return

    prev_prompt_hash = rows[0]["prompt_hash"]
    if not rows[0].get("prompt_preview"):
        return
    prev_prompt = rows[0]["prompt_preview"]

    cur_id = rows[0]["id"]
    sr = SignalResult()
    prev_json = json.loads(recent[0].get("signals_json", "{}")) if recent else {}
    if prev_json.get("reformulation"):
        sr.reformulation = True
    elif prev_json.get("continuation"):
        sr.continuation = True

    if sr.reformulation or sr.continuation:
        update_from_signals(
            tenant_id, user_cluster, task_type,
            length_bucket, model, rate, sr,
        )
        if cur_signals is None or cur_signals == {}:
            cur_signals = sr.to_dict()
            p2 = _param()
            execute(
                f"UPDATE ace_requests SET signals_json={p2} WHERE id={p2}",
                (json.dumps(cur_signals), cur_id),
            )


from backend.core.database_v2 import query_all
