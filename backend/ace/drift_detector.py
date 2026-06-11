"""Drift Detector — détection de drift distributionnel via Maximum Mean Discrepancy (MMD).

Compare le set de calibration (entraînement) aux échantillons de production
via un test MMD avec noyau RBF. Si MMD > seuil, drift détecté.

Références:
- Gretton et al. (2012). A Kernel Two-Sample Test.
- Rabanser et al. (2019). Failing Loudly: An Empirical Study of Methods for Detecting Dataset Shift.
"""

import logging
import math
import statistics
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MMD_THRESHOLD = 0.05  # seuil MMD pour déclencher une alerte
WINDOW_SIZE = 100      # nombre d'échantillons de production pour le test
RBF_SIGMA = 1.0        # paramètre du noyau RBF
N_PERMUTATIONS = 500   # nombre de permutations pour la p-value


class DriftResult:
    __slots__ = ("drift_detected", "mmd_value", "p_value", "window_size", "n_calibration")

    def __init__(
        self,
        drift_detected: bool = False,
        mmd_value: float = 0.0,
        p_value: float = 1.0,
        window_size: int = 0,
        n_calibration: int = 0,
    ):
        self.drift_detected = drift_detected
        self.mmd_value = mmd_value
        self.p_value = p_value
        self.window_size = window_size
        self.n_calibration = n_calibration

    def to_dict(self) -> Dict:
        return {
            "drift_detected": self.drift_detected,
            "mmd_value": round(self.mmd_value, 6),
            "p_value": round(self.p_value, 6),
            "window_size": self.window_size,
            "n_calibration": self.n_calibration,
        }


def _features_to_vector(features: Dict) -> List[float]:
    """Convertit un dict de features en vecteur pour MMD."""
    vec = []
    vec.append(_task_type_to_float(features.get("task_type", "factuel")))
    vec.append(_specificity_to_float(features.get("specificity", "generic")))
    vec.append(_length_bucket_to_float(features.get("length_bucket", "medium")))
    vec.append(float(features.get("token_count", 0)))
    vec.append(float(features.get("user_cluster", 0)))
    return vec


def _task_type_to_float(task_type: str) -> float:
    mapping = {
        "factuel": 0.0, "resume": 0.1, "traduction": 0.2,
        "brainstorming": 0.3, "general": 0.4, "analytique": 0.5,
        "creatif": 0.6, "instruction": 0.7, "code": 0.8,
    }
    return mapping.get(task_type, 0.0)


def _specificity_to_float(specificity: str) -> float:
    mapping = {"generic": 0.0, "domain_jargon": 0.5, "entity_rich": 1.0}
    return mapping.get(specificity, 0.0)


def _length_bucket_to_float(length: str) -> float:
    mapping = {"short": 0.0, "medium": 0.33, "long": 0.66, "very_long": 1.0}
    return mapping.get(length, 0.0)


def _rbf_kernel(x: List[float], y: List[float], sigma: float = RBF_SIGMA) -> float:
    if not x or not y:
        return 0.0
    min_len = min(len(x), len(y))
    sq_dist = sum((x[i] - y[i]) ** 2 for i in range(min_len))
    return math.exp(-sq_dist / (2.0 * sigma * sigma))


def _compute_mmd(X: List[List[float]], Y: List[List[float]]) -> float:
    """MMD unbiased estimate: MMD² = Kxx + Kyy - 2Kxy."""
    if not X or not Y:
        return 0.0
    n = len(X)
    m = len(Y)

    kxx = 0.0
    for i in range(n):
        for j in range(n):
            if i != j:
                kxx += _rbf_kernel(X[i], X[j])
    kxx /= n * (n - 1) if n > 1 else 1

    kyy = 0.0
    for i in range(m):
        for j in range(m):
            if i != j:
                kyy += _rbf_kernel(Y[i], Y[j])
    kyy /= m * (m - 1) if m > 1 else 1

    kxy = 0.0
    for i in range(n):
        for j in range(m):
            kxy += _rbf_kernel(X[i], Y[j])
    kxy /= n * m if n * m > 0 else 1

    mmd = kxx + kyy - 2.0 * kxy
    return max(0.0, mmd)


def _permutation_test(X: List[List[float]], Y: List[List[float]], n_perm: int = N_PERMUTATIONS) -> float:
    """Test de permutation pour obtenir la p-value du MMD."""
    combined = X + Y
    n = len(X)
    mmd_observed = _compute_mmd(X, Y)
    count_extreme = 0
    for _ in range(n_perm):
        import random
        random.shuffle(combined)
        perm_x = combined[:n]
        perm_y = combined[n:]
        mmd_perm = _compute_mmd(perm_x, perm_y)
        if mmd_perm >= mmd_observed:
            count_extreme += 1
    return (count_extreme + 1) / (n_perm + 1)


class DriftDetector:
    """Détecteur de drift basé sur MMD avec fenêtre glissante."""

    def __init__(self, threshold: float = MMD_THRESHOLD, window_size: int = WINDOW_SIZE):
        self._threshold = threshold
        self._window_size = window_size
        self._production_window: Deque[List[float]] = deque(maxlen=window_size)
        self._calibration_set: List[List[float]] = []
        self._drift_history: List[DriftResult] = []
        self._n_samples = 0

    def set_calibration(self, calibration_features: List[Dict]) -> None:
        self._calibration_set = [_features_to_vector(f) for f in calibration_features]
        logger.info("DriftDetector: calibration set with %d samples", len(self._calibration_set))

    def record_sample(self, features: Dict) -> None:
        vec = _features_to_vector(features)
        self._production_window.append(vec)
        self._n_samples += 1

    def detect(self) -> Optional[DriftResult]:
        if not self._calibration_set or len(self._production_window) < 10:
            return None
        prod_list = list(self._production_window)
        mmd = _compute_mmd(self._calibration_set, prod_list)
        p_value = _permutation_test(self._calibration_set, prod_list)
        drift_result = DriftResult(
            drift_detected=mmd > self._threshold,
            mmd_value=mmd,
            p_value=p_value,
            window_size=len(prod_list),
            n_calibration=len(self._calibration_set),
        )
        if drift_result.drift_detected:
            logger.warning(
                "Drift detected: MMD=%.4f, p=%.4f (threshold=%.4f)",
                mmd, p_value, self._threshold,
            )
            self._drift_history.append(drift_result)
        return drift_result

    def get_status(self) -> DriftResult:
        result = self.detect()
        if result is None:
            return DriftResult(
                drift_detected=False,
                mmd_value=0.0,
                p_value=1.0,
                window_size=len(self._production_window),
                n_calibration=len(self._calibration_set),
            )
        return result

    def get_drift_history(self) -> List[DriftResult]:
        return list(self._drift_history)

    def reset_production_window(self) -> None:
        self._production_window.clear()

    @property
    def n_samples(self) -> int:
        return self._n_samples


_drift_detector_instance: Optional[DriftDetector] = None


def get_drift_detector() -> DriftDetector:
    global _drift_detector_instance
    if _drift_detector_instance is None:
        _drift_detector_instance = DriftDetector()
    return _drift_detector_instance
