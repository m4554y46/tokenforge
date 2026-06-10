"""Knowledge Gradient exploration policy pour ACE.

KGⱼ = σⱼ·φ(Δⱼ/σⱼ) + |Δⱼ|·Φ(|Δⱼ|/σⱼ) - |Δⱼ|

où Δⱼ = μⱼ - maxᵢ≠ⱼ μᵢ, μⱼ = E[quality | rⱼ], σⱼ² = Var[quality | rⱼ]
"""

import math
from typing import Dict, List, Optional, Tuple

from backend.ace.state import FAILURE_COST, TF_SHARE, TOKEN_PRICE, PROFILE_COMPUTE_COST, RATE_TO_PROFILE, RATES

_COST_OF_EXPLORATION = 0.0001
_MIN_CONTRACT_AGE_DAYS = 90


def normal_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def knowledge_gradient(mean_j: float, var_j: float, other_means: List[float]) -> float:
    if var_j <= 0:
        return 0.0
    sigma_j = math.sqrt(var_j)
    best_other = max(other_means) if other_means else 0.0
    delta = mean_j - best_other
    abs_delta = abs(delta)
    ratio = abs_delta / sigma_j if sigma_j > 0 else float("inf")
    kg = sigma_j * normal_pdf(ratio) + abs_delta * normal_cdf(ratio) - abs_delta
    return max(kg, 0.0)


def should_explore(
    rate: float,
    expected_quality: float,
    variance: float,
    cells: Dict[float, "CellState"],
    token_count: int,
    price_per_token: float,
    contract_age_days: int = 999,
    tenant_allows_exploration: bool = True,
) -> Tuple[bool, float]:
    if not tenant_allows_exploration:
        return False, 0.0
    if contract_age_days < _MIN_CONTRACT_AGE_DAYS:
        return False, 0.0
    if variance <= 0:
        return False, 0.0
    other_means = []
    for r, c in cells.items():
        if abs(r - rate) > 0.001:
            other_means.append(c.expected_quality)
    kg = knowledge_gradient(expected_quality, variance, other_means)
    if kg <= 0:
        return False, 0.0
    quality_gain = kg * (1.0 - expected_quality)
    savings = token_count * rate * price_per_token * quality_gain * TF_SHARE
    risk = FAILURE_COST * 0.5
    cost = _COST_OF_EXPLORATION
    net = savings - cost - risk
    if net > 0:
        return True, kg
    return False, kg


def pick_exploration_arm(
    cells: Dict[float, "CellState"],
    token_count: int,
    price_per_token: float,
    contract_age_days: int = 999,
    tenant_allows_exploration: bool = True,
) -> Optional[float]:
    best_rate = None
    best_kg = 0.0
    for rate, cell in cells.items():
        if rate == 0.0:
            continue
        if cell.n_samples < 2:
            continue
        explore, kg = should_explore(
            rate, cell.expected_quality, cell.variance,
            cells, token_count, price_per_token,
            contract_age_days, tenant_allows_exploration,
        )
        if explore and kg > best_kg:
            best_kg = kg
            best_rate = rate
    if best_rate is not None and best_kg > 0.01:
        return best_rate
    return None
