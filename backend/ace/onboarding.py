"""Onboarding ACE — calculateur de ROI interactif pour prospects.

Analyse un prompt saisi par l'utilisateur et projette les économies
potentielles avec chaque profil de compression ACE.

Usage :
    GET /api/v2/ace/onboarding?prompt=...&model=gpt-4o&monthly_requests=100000

Retourne les économies estimées par profil, le taux recommandé,
et une projection financière mensuelle.
"""

import logging
from typing import Any, Dict, Optional

from backend.ace.decider import Decider
from backend.ace.features import extract_features
from backend.ace.sanctuary import max_safe_rate, protected_ratio
from backend.ace.state import (
    PROFILE_COMPUTE_COST, RATES, RATE_TO_PROFILE,
    TF_SHARE, get_failure_cost, get_min_client_savings,
)

logger = logging.getLogger(__name__)


def calculate_onboarding(
    prompt: str,
    model: str = "gpt-4o",
    monthly_requests: int = 100_000,
    tenant_id: str = "onboarding",
) -> Dict[str, Any]:
    """Calcule le ROI potentiel pour un prompt et un volume donné.

    Retourne :
        - prompt_analysis : type de tâche, longueur, ratio protégé
        - sanctuary : taux max autorisé
        - by_profile : chaque profil avec ses économies
        - recommendation : profil recommandé
        - monthly_projection : projection financière mensuelle
    """
    token_count = len(prompt.split())
    if token_count < 1:
        return _empty_result()

    feats = extract_features(
        prompt=prompt, token_count=token_count,
        model=model, user_id="onboarding", tenant_id=tenant_id,
    )
    feats["prompt_text"] = prompt
    feats["prompt_preview"] = prompt[:200]

    decider = Decider(tenant_id=tenant_id)
    price = decider.get_token_price(model)

    sanctuary_max = max_safe_rate(prompt)
    protected = protected_ratio(prompt)

    by_profile = []
    for rate in RATES:
        if rate > sanctuary_max:
            continue

        profile = RATE_TO_PROFILE.get(rate, "bypass")
        tokens_saved_per_req = token_count * rate
        savings_usd_per_req = tokens_saved_per_req * price
        monthly_savings = savings_usd_per_req * monthly_requests
        compute_cost_tf = PROFILE_COMPUTE_COST.get(profile, 0.0)
        monthly_tf_cost = compute_cost_tf * monthly_requests
        net_monthly = monthly_savings - monthly_tf_cost
        net_annual = net_monthly * 12

        by_profile.append({
            "profile": profile,
            "rate": rate,
            "token_count_original": token_count,
            "tokens_saved_per_request": int(tokens_saved_per_req),
            "tokens_after_compression": max(1, token_count - int(tokens_saved_per_req)),
            "savings_usd_per_request": round(savings_usd_per_req, 6),
            "monthly_savings": round(monthly_savings, 2),
            "monthly_tf_cost": round(monthly_tf_cost, 2),
            "net_monthly": round(net_monthly, 2),
            "net_annual": round(net_annual, 2),
            "roi_percent": round(((net_monthly / max(monthly_tf_cost, 0.001)) * 100), 1),
        })

    recommendation = max(by_profile, key=lambda p: p["net_monthly"]) if by_profile else None

    total_annual_savings = 0
    if recommendation:
        total_annual_savings = recommendation["net_annual"]
    min_savings = get_min_client_savings(model)

    return {
        "prompt_analysis": {
            "token_count": token_count,
            "task_type": feats.get("task_type", "unknown"),
            "length_bucket": feats.get("length_bucket", "unknown"),
            "specificity": feats.get("specificity", "generic"),
            "protected_ratio": round(protected, 3),
            "sanctuary_max_rate": sanctuary_max,
        },
        "model": model,
        "token_price_per_1k": round(price * 1000, 6),
        "monthly_requests": monthly_requests,
        "min_client_savings": min_savings,
        "by_profile": by_profile,
        "recommendation": recommendation,
        "annual_projection": {
            "total_savings_gross": round(sum(p["monthly_savings"] for p in by_profile) * 12, 2) if by_profile else 0,
            "total_tf_cost": round(sum(p["monthly_tf_cost"] for p in by_profile) * 12, 2) if by_profile else 0,
            "net_annual_recommended": total_annual_savings,
        },
    }


def _empty_result() -> Dict[str, Any]:
    return {
        "prompt_analysis": {"token_count": 0, "task_type": "unknown",
                            "protected_ratio": 0, "sanctuary_max_rate": 1.0},
        "model": "",
        "by_profile": [],
        "recommendation": None,
        "annual_projection": {"net_annual_recommended": 0},
    }
