"""Quality Model — LightGBM probabiliste pour P(quality|r, x, signals)."""

import json
import logging
import os
import pickle
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.core.database_v2 import _param, query_all

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "_models")
os.makedirs(MODEL_DIR, exist_ok=True)

TASK_TYPES = ["code", "analytique", "creatif", "factuel", "traduction", "resume", "brainstorming", "instruction"]
SPECIFICITIES = ["generic", "domain_jargon", "entity_rich"]
LENGTH_BUCKETS = ["short", "medium", "long", "very_long"]
RATES = [0.0, 0.15, 0.25, 0.40, 0.55, 0.70]
SIGNAL_KEYS = ["copy", "continuation", "reformulation", "thumbs_up", "task_success"]

N_FEATURES = (
    len(TASK_TYPES) + len(SPECIFICITIES) + len(LENGTH_BUCKETS) + len(SIGNAL_KEYS)
    + 2 + 4
)


def _pseudo_label(signals: Dict) -> float:
    s = signals or {}
    copy = s.get("copy", 0) or s.get("copied", 0)
    cont = s.get("continuation", 0)
    reform = s.get("reformulation", 0)
    thumbs = s.get("thumbs_up", 0)
    task_ok = s.get("task_success", 0)
    if task_ok == 1 or (copy == 1 and cont == 1):
        return 1.0
    if thumbs == 1:
        return 0.95
    if copy == 1:
        return 0.85
    if cont == 1 and not reform:
        return 0.75
    if not reform and not cont and not copy:
        return 0.50
    if reform == 1:
        return 0.20
    return 0.50


def _encode_features(
    task_type: str, specificity: str, length_bucket: str,
    user_cluster: int, model: str, rate: float,
    prompt_length: int = 0,
) -> np.ndarray:
    feat = np.zeros(N_FEATURES, dtype=np.float32)
    idx = 0
    for t in TASK_TYPES:
        if t == task_type:
            feat[idx] = 1.0
        idx += 1
    for s in SPECIFICITIES:
        if s == specificity:
            feat[idx] = 1.0
        idx += 1
    for lb in LENGTH_BUCKETS:
        if lb == length_bucket:
            feat[idx] = 1.0
        idx += 1
    feat[idx] = float(user_cluster) / 20.0
    idx += 1
    model_hash = abs(hash(model)) % 100 / 100.0
    feat[idx] = model_hash
    idx += 1
    feat[idx] = rate
    idx += 1
    feat[idx] = min(prompt_length / 2000.0, 1.0)
    idx += 1
    return feat


def _encode_features_with_signals(
    task_type: str, specificity: str, length_bucket: str,
    user_cluster: int, model: str, rate: float,
    signals: Dict, prompt_length: int = 0,
) -> np.ndarray:
    feat = np.zeros(N_FEATURES + len(SIGNAL_KEYS) + 2, dtype=np.float32)
    base = _encode_features(task_type, specificity, length_bucket, user_cluster, model, rate, prompt_length)
    feat[:N_FEATURES] = base
    s = signals or {}
    idx = N_FEATURES
    for sk in SIGNAL_KEYS:
        val = s.get(sk, 0)
        if isinstance(val, bool):
            val = 1.0 if val else 0.0
        elif isinstance(val, (int, float)):
            val = min(float(val), 1.0)
        feat[idx] = val
        idx += 1
    copy = feat[N_FEATURES]
    cont = feat[N_FEATURES + 1]
    reform = feat[N_FEATURES + 2]
    feat[idx] = 1.0 if (copy > 0.5 and cont > 0.5) else 0.0
    idx += 1
    feat[idx] = 1.0 if (reform > 0.5 and copy < 0.5) else 0.0
    idx += 1
    return feat


class QualityModel:
    def __init__(self):
        self._model: Any = None
        self._model_path = os.path.join(MODEL_DIR, "quality_model.pkl")
        self._loaded = False

    def is_available(self) -> bool:
        if not self._loaded:
            self._try_load()
        return self._model is not None

    def _try_load(self) -> None:
        try:
            if os.path.exists(self._model_path):
                with open(self._model_path, "rb") as f:
                    self._model = pickle.load(f)
                self._loaded = True
                logger.info("Quality model loaded from %s", self._model_path)
            else:
                logger.info("No quality model found at %s", self._model_path)
        except Exception as e:
            logger.warning("Failed to load quality model: %s", e)
            self._model = None
            self._loaded = True

    def predict(self, features: Dict, signals: Optional[Dict] = None) -> float:
        x = _encode_features_with_signals(
            features.get("task_type", "factuel"),
            features.get("specificity", "generic"),
            features.get("length_bucket", "medium"),
            features.get("user_cluster", 0),
            features.get("model", "gpt-4o"),
            features.get("rate", 0.0),
            signals or {},
            features.get("token_count", 0),
        )
        if self._model is not None:
            pred = self._model.predict(x.reshape(1, -1))[0]
            return max(0.0, min(1.0, float(pred)))
        return 0.5

    def train(self, min_samples: int = 500) -> bool:
        data = self._load_training_data(min_samples)
        if data is None:
            logger.info("Not enough training data (%d needed)", min_samples)
            return False
        X, y = data
        return self._fit(X, y)

    def _load_training_data(self, min_samples: int) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        import json as _json
        p = _param()
        rows = query_all(
            f"SELECT task_type, specificity, length_bucket, user_cluster, model, "
            f"rate_actual, signals_json, tokens_original FROM ace_requests "
            f"WHERE signals_json IS NOT NULL AND signals_json != '{{}}' "
            f"AND rate_actual IS NOT NULL",
        )
        if len(rows) < min_samples:
            return None
        X_list = []
        y_list = []
        for row in rows:
            try:
                signals = _json.loads(row.get("signals_json", "{}") or "{}")
                if not signals:
                    continue
                rate = row.get("rate_actual", 0.0) or 0.0
                feats = _encode_features_with_signals(
                    row.get("task_type", "factuel"),
                    row.get("specificity", "generic"),
                    row.get("length_bucket", "medium"),
                    row.get("user_cluster", 0),
                    row.get("model", "gpt-4o"),
                    rate,
                    signals,
                    row.get("tokens_original", 0),
                )
                label = _pseudo_label(signals)
                X_list.append(feats)
                y_list.append(label)
            except Exception:
                continue
        if len(X_list) < min_samples:
            return None
        return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32)

    def _fit(self, X: np.ndarray, y: np.ndarray) -> bool:
        try:
            import lightgbm as lgb
            model = lgb.LGBMRegressor(
                n_estimators=200,
                max_depth=4,
                learning_rate=0.05,
                min_child_samples=20,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.01,
                reg_lambda=0.01,
                random_state=42,
                verbose=-1,
            )
            model.fit(X, y)
            self._model = model
            with open(self._model_path, "wb") as f:
                pickle.dump(model, f)
            logger.info("Quality model trained on %d samples, saved to %s", len(y), self._model_path)
            return True
        except Exception as e:
            logger.error("Quality model training failed: %s", e)
            return False

    def export_onnx(self, path: Optional[str] = None) -> Optional[str]:
        if self._model is None:
            logger.warning("Cannot export ONNX: no model")
            return None
        try:
            import onnxmltools
            from onnxconverter_common import FloatTensorType
            n_features = N_FEATURES + len(SIGNAL_KEYS) + 2
            onnx_model = onnxmltools.convert_lightgbm(
                self._model, initial_types=[("float_input", FloatTensorType([None, n_features]))]
            )
            out_path = path or os.path.join(MODEL_DIR, "quality_model.onnx")
            with open(out_path, "wb") as f:
                f.write(onnx_model.SerializeToString())
            logger.info("ONNX model exported to %s", out_path)
            return out_path
        except ImportError:
            logger.warning("onnxmltools not installed, keeping pickle format")
            return None
        except Exception as e:
            logger.warning("ONNX export failed: %s", e)
            return None

    def predict_batch(self, features_batch: List[Dict]) -> List[float]:
        if self._model is None:
            return [0.5] * len(features_batch)
        X = np.array([
            _encode_features(
                f.get("task_type", "factuel"),
                f.get("specificity", "generic"),
                f.get("length_bucket", "medium"),
                f.get("user_cluster", 0),
                f.get("model", "gpt-4o"),
                f.get("rate", 0.0),
                f.get("token_count", 0),
            )
            for f in features_batch
        ], dtype=np.float32)
        preds = self._model.predict(X)
        return [max(0.0, min(1.0, float(p))) for p in preds]


_model_instance: Optional[QualityModel] = None


def get_model() -> QualityModel:
    global _model_instance
    if _model_instance is None:
        _model_instance = QualityModel()
    return _model_instance
