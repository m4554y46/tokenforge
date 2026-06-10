"""ACE Decision Engine — choisit le profil de compression optimal."""

import logging
from typing import Dict, List, Optional, Tuple

from backend.ace.features import extract_features
from backend.ace.sanctuary import max_safe_rate
from backend.ace.state import (
    CellState, FAILURE_COST, TF_SHARE, TOKEN_PRICE as TF_DEFAULT_PRICE,
    PROFILE_COMPUTE_COST, RATES, RATE_TO_PROFILE,
    read_cells_for_context, write_cell, record_request, record_session,
    get_failure_cost, get_min_client_savings,
)
from backend.ace.signals import detect_signals, SignalResult

logger = logging.getLogger(__name__)

MIN_QUALITY_THRESHOLD = 0.80
COLD_START_QUALITY = 0.85


class Decider:
    def __init__(self, tenant_id: str = "default"):
        self.tenant_id = tenant_id
        self._quality_model = None
        self._embeddings = None

    def _lazy_load_model(self):
        if self._quality_model is None:
            try:
                from backend.ace.models.quality_model import get_model
                self._quality_model = get_model()
            except Exception as e:
                logger.debug("Quality model not available: %s", e)
                self._quality_model = False
        return self._quality_model if self._quality_model is not False else None

    def _lazy_load_embeddings(self):
        if self._embeddings is None:
            try:
                from backend.ace.embeddings import get_embeddings
                self._embeddings = get_embeddings()
            except Exception as e:
                logger.debug("Embeddings not available: %s", e)
                self._embeddings = False
        return self._embeddings if self._embeddings is not False else None

    def get_token_price(self, model: str) -> float:
        prices = {
            "gpt-4o": 0.000005,
            "gpt-4o-mini": 0.0000015,
            "claude-3.5-sonnet": 0.000003,
            "claude-3-haiku": 0.00000025,
            "gemini-1.5-pro": 0.00000125,
            "gemini-1.5-flash": 0.000000075,
            "gpt-4": 0.00001,
            "gpt-3.5-turbo": 0.0000005,
        }
        return prices.get(model.lower(), TF_DEFAULT_PRICE)

    def _get_quality(self, cell: CellState, features: Dict, rate: float) -> float:
        if cell.n_samples >= 5:
            return cell.expected_quality
        emb = self._lazy_load_embeddings()
        if emb is not None and emb.is_available():
            cs_q = emb.cold_start_quality(features, rate)
            if cs_q is not None:
                return cs_q
        return COLD_START_QUALITY

    def compute_utility(
        self, rate: float, token_count: int, price_per_token: float,
        cell: CellState, features: Dict,
    ) -> float:
        if rate == 0.0:
            return 0.0
        savings = token_count * rate * price_per_token
        cost_tf = PROFILE_COMPUTE_COST.get(RATE_TO_PROFILE.get(rate, "bypass"), 0.0)
        quality = self._get_quality(cell, features, rate)
        task_type = features.get("task_type", "factuel")
        failure_cost = get_failure_cost(task_type)
        risk = (1.0 - quality) * failure_cost
        return savings * TF_SHARE - cost_tf - risk

    def is_valid(self, rate: float, utility: float, token_count: int,
                 price_per_token: float, cell: CellState, features: Dict) -> bool:
        if rate == 0.0:
            return True
        if utility <= 0:
            return False
        quality = self._get_quality(cell, features, rate)
        if quality < MIN_QUALITY_THRESHOLD:
            return False
        model = features.get("model", "gpt-4o")
        savings = token_count * rate * price_per_token
        if savings * (1 - TF_SHARE) < get_min_client_savings(model):
            return False
        return True

    def decide(
        self,
        features: Dict,
        force_profile: Optional[str] = None,
        contract_age_days: int = 999,
        tenant_allows_exploration: bool = True,
    ) -> Tuple[str, bool, Optional[float]]:
        if force_profile:
            return force_profile, False, None

        tenant_id = features.get("tenant_id", self.tenant_id)
        user_cluster = features["user_cluster"]
        task_type = features["task_type"]
        length_bucket = features["length_bucket"]
        model = features["model"]
        token_count = features.get("token_count", 0)

        if token_count < 50:
            return "bypass", False, 0.0

        # ── Sanctuary : plafonner le taux max selon le contenu protégé ──
        prompt_full = features.get("prompt_text") or features.get("prompt_preview", "")
        sanctuary_max_rate = max_safe_rate(prompt_full) if prompt_full else 1.0
        logger.debug("Sanctuary max_rate=%.2f for task=%s", sanctuary_max_rate, task_type)

        cells = read_cells_for_context(
            tenant_id, user_cluster, task_type, length_bucket, model,
        )
        price = self.get_token_price(model)

        alternatives = []
        for rate in RATES:
            if rate > sanctuary_max_rate:
                continue  # Sanctuary interdit ce taux
            cell = cells.get(rate)
            if cell is None:
                continue
            u = self.compute_utility(rate, token_count, price, cell, features)
            alternatives.append((rate, u, cell))

        valid = [(r, u, c) for r, u, c in alternatives
                 if self.is_valid(r, u, token_count, price, c, features)]

        if not valid:
            return "bypass", False, 0.0

        best_rate, best_utility, best_cell = max(valid, key=lambda x: x[1])

        explore, chosen_rate = self._explore_or_exploit(
            best_rate, best_cell, cells, token_count, price,
            contract_age_days, tenant_allows_exploration,
        )
        if explore:
            chosen_cell = cells.get(chosen_rate)
            if chosen_cell:
                chosen_cell.n_explorations += 1
                write_cell(chosen_cell)
            return RATE_TO_PROFILE[chosen_rate], True, chosen_rate

        return RATE_TO_PROFILE[best_rate], False, best_rate

    def _explore_or_exploit(
        self, best_rate: float, best_cell: CellState,
        cells: Dict[float, CellState],
        token_count: int, price: float,
        contract_age_days: int, tenant_allows_exploration: bool,
    ) -> Tuple[bool, float]:
        try:
            from backend.ace.exploration import pick_exploration_arm
            arm = pick_exploration_arm(
                cells, token_count, price,
                contract_age_days, tenant_allows_exploration,
            )
            if arm is not None:
                return True, arm
        except Exception as e:
            logger.debug("KG exploration failed, fallback to exploit: %s", e)
        return False, best_rate

    def on_response(
        self,
        features: Dict,
        profile_chosen: str,
        tokens_original: int,
        tokens_compressed: int,
        latency_ms: float,
        was_exploration: bool,
        session_id: str,
        prompt_hash: str,
        response_hash: str,
        provider: str = "",
    ) -> None:
        rate_actual = 0.0
        if tokens_original > 0:
            rate_actual = 1.0 - (tokens_compressed / tokens_original)

        try:
            record_request(
                tenant_id=features["tenant_id"],
                user_id=features.get("user_id", ""),
                session_id=session_id,
                prompt_hash=prompt_hash,
                task_type=features["task_type"],
                specificity=features["specificity"],
                length_bucket=features["length_bucket"],
                user_cluster=features["user_cluster"],
                model=features["model"],
                provider=provider,
                profile_chosen=profile_chosen,
                rate_actual=round(rate_actual, 4),
                tokens_original=tokens_original,
                tokens_compressed=tokens_compressed,
                latency_ms=latency_ms,
                was_exploration=was_exploration,
            )
        except Exception as e:
            logger.warning("ACE record_request failed: %s", e)

        try:
            record_session(
                session_id=session_id,
                tenant_id=features["tenant_id"],
                user_id=features.get("user_id", ""),
                prompt_hash=prompt_hash,
                prompt_preview=features.get("prompt_preview", ""),
                response_hash=response_hash,
                profile_chosen=profile_chosen,
            )
        except Exception as e:
            logger.warning("ACE record_session failed: %s", e)

    def on_next_request(
        self,
        session_id: str,
        user_id: str,
        tenant_id: str,
        current_prompt: str,
        previous_features: Dict,
        previous_rate: float,
    ) -> None:
        try:
            signal = detect_signals(session_id, user_id, tenant_id, current_prompt)
            if not (signal.reformulation or signal.continuation):
                return
            from backend.ace.attribution import attribute, should_update_quality
            att = attribute(previous_features, previous_rate, signal.to_dict())
            if not should_update_quality(att):
                logger.debug("Attribution skipped update: cause=%s conf=%.2f", att.cause, att.confidence)
                return
            self._update_cell_quality(previous_features, previous_rate, signal)
        except Exception as e:
            logger.warning("ACE signal processing failed: %s", e)

    def _update_cell_quality(
        self, features: Dict, rate: float, signal: SignalResult,
    ) -> None:
        q_model = self._lazy_load_model()
        if q_model is not None and q_model.is_available():
            q = q_model.predict(features, signal.to_dict())
            w = signal.quality_proxy
        else:
            q = signal.quality_proxy
            w = 0.3

        cell = read_cell(
            features.get("tenant_id", self.tenant_id),
            features.get("user_cluster", 0),
            features.get("task_type", "factuel"),
            features.get("length_bucket", "medium"),
            features.get("model", "gpt-4o"),
            rate,
        )

        if signal.reformulation:
            delta = -abs(1.0 - q) * w
        else:
            delta = q * w

        cell.quality_sum += delta
        cell.n_samples += w
        write_cell(cell)
