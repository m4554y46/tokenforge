"""Ensemble Judge — Dawid-Skene consensus multi-juge pour l'évaluation qualité.

Juges disponibles :
- QualityJudge GPT-4o (existante)
- BLEU (n-gram precision)
- ROUGE-L (recall-based)
- Heuristic locale (existing)

Dawid-Skene EM : estime la fiabilité de chaque juge et le consensus.

Références:
- Dawid & Skene (1979). Maximum Likelihood Estimation of Observer Error-Rates.
- Ipeirotis et al. (2010). Quality Management on Amazon Mechanical Turk.
"""

import logging
import math
from typing import Dict, List, Optional, Tuple

from backend.ace.judge import QualityJudge, get_judge

logger = logging.getLogger(__name__)

MAX_EM_ITERATIONS = 20
EM_CONVERGENCE = 1e-4
DEFAULT_JUDGE_RELIABILITY = 0.85

_JUDGE_RELIABILITIES: Dict[str, float] = {
    "gpt4o": 0.90,
    "bleu": 0.75,
    "rouge": 0.70,
    "heuristic": 0.65,
}


def _compute_bleu(reference: str, hypothesis: str) -> float:
    """BLEU-4 simplifié (précision n-gram avec bréveté)."""
    ref_tokens = reference.lower().split()
    hyp_tokens = hypothesis.lower().split()
    if not ref_tokens or not hyp_tokens:
        return 0.0
    # Précision n-gram jusqu'à 4
    scores = []
    for n in range(1, 5):
        ref_ngrams = [tuple(ref_tokens[i:i+n]) for i in range(max(0, len(ref_tokens)-n+1))]
        hyp_ngrams = [tuple(hyp_tokens[i:i+n]) for i in range(max(0, len(hyp_tokens)-n+1))]
        if not ref_ngrams or not hyp_ngrams:
            scores.append(0.0)
            continue
        ref_count = {}
        for ng in ref_ngrams:
            ref_count[ng] = ref_count.get(ng, 0) + 1
        hyp_count = {}
        for ng in hyp_ngrams:
            hyp_count[ng] = hyp_count.get(ng, 0) + 1
        matches = 0
        total_hyp = len(hyp_ngrams)
        for ng, c in hyp_count.items():
            matches += min(c, ref_count.get(ng, 0))
        precision = matches / max(total_hyp, 1)
        scores.append(precision)
    avg_precision = math.exp(sum(math.log(max(s, 1e-10)) for s in scores) / 4.0)
    # Pénalité de bréveté
    brevity = min(1.0, math.exp(1 - len(ref_tokens) / max(len(hyp_tokens), 1)))
    return brevity * avg_precision


def _compute_rouge_l(reference: str, hypothesis: str) -> float:
    """ROUGE-L : F1 basé sur la plus longue sous-séquence commune (LCS)."""
    ref_tokens = reference.lower().split()
    hyp_tokens = hypothesis.lower().split()
    if not ref_tokens or not hyp_tokens:
        return 0.0
    m, n = len(ref_tokens), len(hyp_tokens)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if ref_tokens[i - 1] == hyp_tokens[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs = dp[m][n]
    precision = lcs / max(n, 1)
    recall = lcs / max(m, 1)
    if precision + recall == 0:
        return 0.0
    f1 = 2 * precision * recall / (precision + recall)
    return f1


def _heuristic_judge(response_a: str, response_b: str) -> float:
    """Version allégée du heuristic judge pour le consensus."""
    from backend.ace.judge import _heuristic_evaluate
    result = _heuristic_evaluate(response_a, response_b)
    return result.get("score", 0.5)


class DawidSkeneResult:
    __slots__ = ("consensus_score", "judge_reliabilities", "n_iterations", "converged", "individual_scores")

    def __init__(
        self,
        consensus_score: float = 0.0,
        judge_reliabilities: Optional[Dict[str, float]] = None,
        n_iterations: int = 0,
        converged: bool = False,
        individual_scores: Optional[Dict[str, float]] = None,
    ):
        self.consensus_score = consensus_score
        self.judge_reliabilities = judge_reliabilities or {}
        self.n_iterations = n_iterations
        self.converged = converged
        self.individual_scores = individual_scores or {}

    def to_dict(self) -> Dict:
        return {
            "consensus_score": round(self.consensus_score, 4),
            "judge_reliabilities": {k: round(v, 4) for k, v in self.judge_reliabilities.items()},
            "n_iterations": self.n_iterations,
            "converged": self.converged,
            "individual_scores": {k: round(v, 4) for k, v in self.individual_scores.items()},
        }


class EnsembleJudge:
    """Agrège plusieurs juges via Dawid-Skene EM."""

    def __init__(self, api_key: Optional[str] = None):
        self._gpt4o_judge = QualityJudge(api_key=api_key)
        self._reliabilities: Dict[str, float] = dict(_JUDGE_RELIABILITIES)
        self._n_calls: Dict[str, int] = {}
        self._total_evaluations = 0

    def _run_judges(
        self, prompt: str, response_a: str, response_b: str,
    ) -> Dict[str, float]:
        scores = {}
        # GPT-4o
        try:
            gpt4o_result = self._gpt4o_judge.evaluate(prompt, response_a, response_b)
            scores["gpt4o"] = gpt4o_result.get("score", 0.85)
        except Exception as e:
            logger.warning("GPT-4o judge failed: %s", e)
            scores["gpt4o"] = DEFAULT_JUDGE_RELIABILITY
        # BLEU
        scores["bleu"] = _compute_bleu(response_a, response_b)
        # ROUGE-L
        scores["rouge"] = _compute_rouge_l(response_a, response_b)
        # Heuristic
        scores["heuristic"] = _heuristic_judge(response_a, response_b)

        for name in scores:
            self._n_calls[name] = self._n_calls.get(name, 0) + 1
        self._total_evaluations += 1
        return scores

    def _dawid_skene_em(self, scores: Dict[str, float]) -> Tuple[float, Dict[str, float], int, bool]:
        """Dawid-Skene EM : estime le consensus et les fiabilités.
        
        E-step: estimer la vraie qualité à partir des scores pondérés
        M-step: estimer la fiabilité de chaque juge
        """
        if not scores:
            return 0.5, dict(_JUDGE_RELIABILITIES), 0, False

        consensus = sum(
            scores[k] * self._reliabilities.get(k, DEFAULT_JUDGE_RELIABILITY)
            for k in scores
        ) / sum(max(self._reliabilities.get(k, DEFAULT_JUDGE_RELIABILITY), 0.01) for k in scores)

        converged = False
        iteration = 0

        for iteration in range(1, MAX_EM_ITERATIONS + 1):
            prev_consensus = consensus

            # M-step: mettre à jour les fiabilités
            new_reliabilities = {}
            for name, score in scores.items():
                error = abs(score - consensus)
                reliability = 1.0 - error
                new_reliabilities[name] = max(0.1, min(0.99, reliability))
            new_reliabilities["gpt4o"] = max(
                new_reliabilities.get("gpt4o", DEFAULT_JUDGE_RELIABILITY),
                0.75,
            )

            # E-step: nouveau consensus pondéré
            total_weight = sum(max(new_reliabilities.get(k, 0.1), 0.01) for k in scores)
            consensus = sum(
                scores[k] * new_reliabilities.get(k, DEFAULT_JUDGE_RELIABILITY)
                for k in scores
            ) / max(total_weight, 0.01)

            if abs(consensus - prev_consensus) < EM_CONVERGENCE:
                converged = True
                break

        self._reliabilities = new_reliabilities
        return consensus, new_reliabilities, iteration, converged

    def evaluate(
        self, prompt: str, response_a: str, response_b: str,
    ) -> DawidSkeneResult:
        scores = self._run_judges(prompt, response_a, response_b)
        consensus, reliabilities, n_iter, converged = self._dawid_skene_em(scores)
        return DawidSkeneResult(
            consensus_score=consensus,
            judge_reliabilities=reliabilities,
            n_iterations=n_iter,
            converged=converged,
            individual_scores=scores,
        )

    def get_judge_reliability(self, judge_name: str) -> float:
        return self._reliabilities.get(judge_name, DEFAULT_JUDGE_RELIABILITY)

    def get_stats(self) -> Dict:
        return {
            "total_evaluations": self._total_evaluations,
            "judge_reliabilities": {k: round(v, 4) for k, v in self._reliabilities.items()},
            "n_calls": self._n_calls,
        }


_ensemble_judge_instance: Optional[EnsembleJudge] = None


def get_ensemble_judge(api_key: Optional[str] = None) -> EnsembleJudge:
    global _ensemble_judge_instance
    if _ensemble_judge_instance is None:
        _ensemble_judge_instance = EnsembleJudge(api_key=api_key)
    return _ensemble_judge_instance
