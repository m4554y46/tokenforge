"""API v2 — TokenForge Intelligence Platform."""

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from backend.config import get_settings
from backend.core.auth import create_access_token
from backend.core.tenant import TenantContext, resolve_tenant_context
from backend.core.database_v2 import init_v2_db
from backend.memory.user_memory_service import UserMemoryService
from backend.memory.tenant_memory_service import TenantMemoryService
from backend.memory.memory_retriever import MemoryRetriever
from backend.memory.memory_updater import MemoryUpdater
from backend.memory.memory_summarizer import MemorySummarizer
from backend.prompts.prompt_inventory import PromptInventory
from backend.prompts.prompt_similarity import PromptSimilarityEngine
from backend.prompts.prompt_diff import PromptDiffExplorer
from backend.prompts.prompt_explainability import PromptExplainability
from backend.finops.cost_registry import CostRegistry
from backend.finops.budget_engine import BudgetEngine
from backend.finops.forecast_engine import ForecastEngine
from backend.finops.anomaly_detection import AnomalyDetector
from backend.finops.roi_engine import ROIEngine
from backend.governance.rule_engine import RuleEngine
from backend.governance.compliance import ComplianceManager
from backend.governance.approval_workflows import ApprovalWorkflow
from backend.gateway.predictive_router import PredictiveRouter
from backend.gateway.circuit_breaker import CircuitBreaker
from backend.gateway.cache_governor import CacheGovernor
from backend.observability.hub import ObservabilityHub
from backend.experiments.experiment_manager import ExperimentManager

router = APIRouter(prefix="/api/v2", tags=["v2"])

_user_mem = UserMemoryService()
_tenant_mem = TenantMemoryService()
_retriever = MemoryRetriever()
_updater = MemoryUpdater()
_summarizer = MemorySummarizer()
_prompts = PromptInventory()
_similarity = PromptSimilarityEngine()
_diff = PromptDiffExplorer()
_explain = PromptExplainability()
_costs = CostRegistry()
_budgets = BudgetEngine()
_forecast = ForecastEngine()
_anomaly = AnomalyDetector()
_roi = ROIEngine()
_rules = RuleEngine()
_compliance = ComplianceManager()
_approvals = ApprovalWorkflow()
_router = PredictiveRouter()
_breaker = CircuitBreaker("default")
_cache_gov = CacheGovernor()
_obs = ObservabilityHub()
_experiments = ExperimentManager()


class ProfileUpdate(BaseModel):
    updates: Dict[str, Any]


class TermRequest(BaseModel):
    category: str
    term: str
    definition: str = ""


class BudgetRequest(BaseModel):
    scope_type: str
    scope_id: str
    amount_usd: float
    period: str = "monthly"
    alert_threshold: float = 0.8


class PolicyRequest(BaseModel):
    name: str
    rule_type: str
    config: Dict[str, Any]
    compliance_tags: str = ""


class DiffRequest(BaseModel):
    prompt_a: str
    prompt_b: str
    model: str = "gpt-4o"


class ExplainRequest(BaseModel):
    original_tokens: int
    optimized_tokens: int
    profile: str
    fallback: bool = False


class RouteRequest(BaseModel):
    prompt: str
    model: str
    provider: str = ""
    tokens: int = 0


class ExperimentRequest(BaseModel):
    name: str
    variant_a: str
    variant_b: str
    metric: str = "cost"


class LearnRequest(BaseModel):
    prompt: str
    model: str = ""
    response: str = ""


class TokenRequest(BaseModel):
    user_id: str
    tenant_id: str = "default"


@router.get("/health")
def v2_health():
    s = get_settings()
    return {"status": "ok", "version": s.APP_VERSION, "platform": s.APP_NAME}


@router.post("/auth/token")
def issue_token(req: TokenRequest):
    return {"access_token": create_access_token(req.user_id, req.tenant_id), "token_type": "bearer"}


# ── Memory ──────────────────────────────────────────────

@router.get("/memory/user/profile")
def get_user_profile(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _user_mem.get_profile(ctx.tenant_id, ctx.user_id)


@router.put("/memory/user/profile")
def update_user_profile(req: ProfileUpdate, ctx: TenantContext = Depends(resolve_tenant_context)):
    return _user_mem.update_profile(ctx.tenant_id, ctx.user_id, req.updates)


@router.get("/memory/user/export")
def export_user_profile(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _user_mem.export_profile(ctx.tenant_id, ctx.user_id)


@router.delete("/memory/user/profile")
def delete_user_profile(ctx: TenantContext = Depends(resolve_tenant_context)):
    deleted = _user_mem.delete_profile(ctx.tenant_id, ctx.user_id)
    return {"deleted": deleted}


@router.get("/memory/user/summary")
def user_memory_summary(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _summarizer.summarize_user(ctx.tenant_id, ctx.user_id)


@router.get("/memory/tenant/knowledge")
def tenant_knowledge(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _tenant_mem.list_all(ctx.tenant_id)


@router.post("/memory/tenant/terms")
def add_tenant_term(req: TermRequest, ctx: TenantContext = Depends(resolve_tenant_context)):
    _tenant_mem.add_term(ctx.tenant_id, req.category, req.term, req.definition, source="manual")
    return {"status": "added"}


@router.put("/memory/tenant/terms/{category}/{term}/validate")
def validate_term(category: str, term: str, ctx: TenantContext = Depends(resolve_tenant_context)):
    _tenant_mem.validate_term(ctx.tenant_id, category, term)
    return {"status": "validated"}


@router.put("/memory/tenant/terms/{category}/{term}")
def correct_term(category: str, term: str, req: TermRequest, ctx: TenantContext = Depends(resolve_tenant_context)):
    _tenant_mem.correct_term(ctx.tenant_id, category, term, req.definition)
    return {"status": "corrected"}


@router.delete("/memory/tenant/terms/{category}/{term}")
def delete_term(category: str, term: str, ctx: TenantContext = Depends(resolve_tenant_context)):
    _tenant_mem.delete_term(ctx.tenant_id, category, term)
    return {"status": "deleted"}


@router.get("/memory/tenant/summary")
def tenant_summary(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _summarizer.summarize_tenant(ctx.tenant_id)


@router.post("/memory/learn")
def learn_from_interaction(req: LearnRequest, ctx: TenantContext = Depends(resolve_tenant_context)):
    return _updater.learn_from_interaction(ctx.tenant_id, ctx.user_id, req.prompt, req.model, req.response)


@router.post("/memory/retrieve")
def retrieve_memory(req: LearnRequest, ctx: TenantContext = Depends(resolve_tenant_context)):
    return _retriever.retrieve_for_prompt(ctx.tenant_id, ctx.user_id, req.prompt)


# ── Prompt Analytics ──────────────────────────────────

@router.get("/prompts/inventory")
def prompt_inventory(ctx: TenantContext = Depends(resolve_tenant_context), limit: int = 50):
    return _prompts.list_prompts(ctx.tenant_id, limit)


@router.get("/prompts/top")
def top_prompts(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _prompts.top_prompts(ctx.tenant_id)


@router.get("/prompts/similarity")
def prompt_similarity(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _similarity.analyze_tenant(ctx.tenant_id)


@router.post("/prompts/diff")
def prompt_diff(req: DiffRequest):
    return _diff.compare(req.prompt_a, req.prompt_b, req.model)


@router.post("/prompts/explain")
def explain_optimization(req: ExplainRequest):
    return _explain.explain_optimization(
        req.original_tokens, req.optimized_tokens, req.profile, req.fallback,
    )


@router.get("/prompts/dashboard")
def prompts_dashboard(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _prompts.dashboard_stats(ctx.tenant_id)


# ── FinOps ────────────────────────────────────────────

@router.get("/finops/summary")
def finops_summary(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _costs.get_cost_summary(ctx.tenant_id)


@router.get("/finops/forecast")
def finops_forecast(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _forecast.forecast_all(ctx.tenant_id)


@router.get("/finops/roi")
def finops_roi(ctx: TenantContext = Depends(resolve_tenant_context), savings_rate: Optional[float] = None):
    return _roi.calculate(ctx.tenant_id, assumed_savings_rate=savings_rate)


@router.get("/finops/anomalies")
def finops_anomalies(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _anomaly.scan(ctx.tenant_id)


@router.get("/finops/budgets")
def list_budgets(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _budgets.get_budgets(ctx.tenant_id)


@router.post("/finops/budgets")
def set_budget(req: BudgetRequest, ctx: TenantContext = Depends(resolve_tenant_context)):
    return _budgets.set_budget(ctx.tenant_id, req.scope_type, req.scope_id, req.amount_usd, req.period, req.alert_threshold)


@router.get("/finops/alerts")
def budget_alerts(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _budgets.get_alerts(ctx.tenant_id)


@router.get("/finops/top-prompts")
def finops_top_prompts(ctx: TenantContext = Depends(resolve_tenant_context), limit: int = 10):
    return _costs.get_top_costly_prompts(ctx.tenant_id, limit)


@router.get("/finops/providers")
def finops_providers():
    return _costs.list_providers()


@router.get("/finops/trend")
def finops_trend(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _costs.get_cost_trend(ctx.tenant_id)


@router.get("/finops/top-users")
def finops_top_users(ctx: TenantContext = Depends(resolve_tenant_context), limit: int = 5):
    return _costs.get_top_users(ctx.tenant_id, limit)


@router.get("/finops/provider-efficiency")
def finops_provider_efficiency(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _costs.get_provider_efficiency(ctx.tenant_id)


# ── Governance ────────────────────────────────────────

@router.get("/governance/policies")
def list_policies(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _rules.list_policies(ctx.tenant_id)


@router.post("/governance/policies")
def create_policy(req: PolicyRequest, ctx: TenantContext = Depends(resolve_tenant_context)):
    return _rules.create_policy(ctx.tenant_id, req.name, req.rule_type, req.config, req.compliance_tags, ctx.user_id)


@router.put("/governance/policies/{policy_id}/toggle")
def toggle_policy(policy_id: int, ctx: TenantContext = Depends(resolve_tenant_context)):
    policy = _rules.list_policies(ctx.tenant_id)
    match = [p for p in policy if p.get("id") == policy_id]
    if not match:
        raise HTTPException(404, "Politique introuvable")
    current = bool(match[0].get("enabled", False))
    return _rules.set_policy_enabled(ctx.tenant_id, policy_id, not current, ctx.user_id)


@router.post("/governance/evaluate")
def evaluate_policy(req: RouteRequest, ctx: TenantContext = Depends(resolve_tenant_context)):
    return _rules.evaluate(ctx.tenant_id, req.model, req.provider, ctx.user_id, req.tokens)


@router.get("/governance/audit")
def audit_log(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _rules.get_audit_log(ctx.tenant_id)


@router.get("/governance/compliance")
def compliance_check(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _compliance.check_compliance({"compliance_tags": ["RGPD"], "data_residency": "EU", "audit_trail": True})


@router.get("/governance/compliance/frameworks")
def compliance_frameworks():
    return _compliance.list_frameworks()


# ── Gateway ───────────────────────────────────────────

@router.post("/gateway/route")
def gateway_route(req: RouteRequest, ctx: TenantContext = Depends(resolve_tenant_context)):
    start = time.time()
    result = _router.route(ctx.tenant_id, ctx.user_id, req.prompt, req.model, req.provider, req.tokens)
    _obs.record_request("/gateway/route", (time.time() - start) * 1000, tenant_id=ctx.tenant_id)
    return result


@router.get("/gateway/circuit-breaker")
def circuit_status():
    return _breaker.status()


@router.get("/gateway/cache")
def cache_stats():
    return _cache_gov.stats()


# ── Observability ─────────────────────────────────────

@router.get("/observability/metrics")
def metrics():
    return _obs.get_metrics()


@router.get("/observability/traces")
def traces(limit: int = 50):
    return _obs.get_traces(limit)


@router.get("/observability/prometheus", response_class=PlainTextResponse)
def prometheus():
    return _obs.prometheus_text()


# ── Experiments ───────────────────────────────────────

@router.get("/experiments")
def list_experiments(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _experiments.list_experiments(ctx.tenant_id)


@router.post("/experiments")
def create_experiment(req: ExperimentRequest, ctx: TenantContext = Depends(resolve_tenant_context)):
    return _experiments.create(ctx.tenant_id, req.name, req.variant_a, req.variant_b, req.metric)


# ── ACE Dashboard ────────────────────────────────────

@router.get("/ace/status")
def ace_status(ctx: TenantContext = Depends(resolve_tenant_context)):
    from backend.ace.state import RATES
    from backend.core.database_v2 import query_one, _param
    p = _param()
    total = query_one(
        f"SELECT COUNT(*) as c FROM ace_states WHERE tenant_id={p}",
        (ctx.tenant_id,),
    )
    requests = query_one(
        f"SELECT COUNT(*) as c, SUM(savings_percent) as total_savings, "
        f"AVG(savings_percent) as avg_savings, "
        f"SUM(was_exploration) as explorations "
        f"FROM ace_requests WHERE tenant_id={p}",
        (ctx.tenant_id,),
    )
    from backend.ace.models.quality_model import get_model
    qm = get_model()
    from backend.ace.embeddings import get_embeddings
    emb = get_embeddings()
    return {
        "enabled": True,
        "cells_total": (total or {}).get("c", 0) or 0,
        "requests_total": (requests or {}).get("c", 0) or 0,
        "avg_savings_percent": round((requests or {}).get("avg_savings", 0) or 0, 2),
        "explorations_total": (requests or {}).get("explorations", 0) or 0,
        "quality_model_available": qm.is_available(),
        "embeddings_available": emb.is_available(),
        "rates": RATES,
    }


@router.get("/ace/cells")
def ace_cells(ctx: TenantContext = Depends(resolve_tenant_context),
              task_type: Optional[str] = None, min_samples: int = 3):
    from backend.core.database_v2 import query_all, _param
    params = [ctx.tenant_id]
    sql = (
        "SELECT user_cluster, task_type, length_bucket, model, rate, "
        "quality_sum, n_samples, n_explorations FROM ace_states "
        f"WHERE tenant_id={_param()} AND n_samples >= {_param()}"
    )
    params.append(min_samples)
    if task_type:
        sql += f" AND task_type={_param()}"
        params.append(task_type)
    rows = query_all(sql, tuple(params))
    return [
        {
            "cell": f"{r['user_cluster']}|{r['task_type']}|{r['length_bucket']}|{r['model']}|{r['rate']}",
            "expected_quality": round(r["quality_sum"] / r["n_samples"], 4) if r["n_samples"] > 0 else 0.5,
            "n_samples": r["n_samples"],
            "n_explorations": r["n_explorations"],
            "rate": r["rate"],
        }
        for r in rows
    ]


@router.get("/ace/train")
def ace_train(ctx: TenantContext = Depends(resolve_tenant_context)):
    from backend.ace.train import train_all
    ok = train_all(min_samples=50)
    return {"trained": ok}


@router.get("/ace/explain")
def ace_explain(ctx: TenantContext = Depends(resolve_tenant_context),
                prompt: str = "", user_id: str = ""):
    from backend.ace.decider import Decider
    from backend.ace.features import extract_features
    from backend.ace.state import (
        RATES, read_cells_for_context, PROFILE_COMPUTE_COST, RATE_TO_PROFILE,
        TF_SHARE, FAILURE_COST,
    )
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt required")
    d = Decider(tenant_id=ctx.tenant_id)
    price = d.get_token_price("gpt-4o")
    token_count = len(prompt.split())
    feats = extract_features(prompt, token_count, model="gpt-4o", user_id=user_id, tenant_id=ctx.tenant_id)
    cells = read_cells_for_context(
        ctx.tenant_id, feats["user_cluster"], feats["task_type"],
        feats["length_bucket"], "gpt-4o",
    )
    explanations = []
    for rate in RATES:
        cell = cells.get(rate)
        if cell is None:
            continue
        profile = RATE_TO_PROFILE.get(rate, "bypass")
        savings = token_count * rate * price
        cost_tf = PROFILE_COMPUTE_COST.get(profile, 0.0)
        quality = cell.expected_quality
        risk = (1.0 - quality) * FAILURE_COST
        u = d.compute_utility(rate, token_count, price, cell, feats)
        explanations.append({
            "profile": profile,
            "rate": rate,
            "expected_quality": round(quality, 4),
            "n_samples": cell.n_samples,
            "savings_usd": round(savings, 6),
            "cost_tf": round(cost_tf, 6),
            "risk_usd": round(risk, 6),
            "utility": round(u, 8),
            "valid": d.is_valid(rate, u, token_count, price, cell, feats),
        })
    explanations.sort(key=lambda x: -x["utility"])
    return {
        "features": feats,
        "token_count": token_count,
        "token_price": price,
        "explanations": explanations,
        "recommendation": explanations[0] if explanations else None,
    }


@router.get("/ace/quality-dashboard")
def ace_quality_dashboard(ctx: TenantContext = Depends(resolve_tenant_context), days: int = 7):
    from backend.ace.dashboard import get_dashboard_data
    return get_dashboard_data(ctx.tenant_id, days=days)


@router.get("/ace/onboarding")
def ace_onboarding(prompt: str = "", model: str = "gpt-4o",
                   monthly_requests: int = 100_000):
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt required")
    from backend.ace.onboarding import calculate_onboarding
    return calculate_onboarding(prompt=prompt, model=model,
                                monthly_requests=monthly_requests)


# ── Dashboard ─────────────────────────────────────────

@router.get("/dashboard")
def executive_dashboard(ctx: TenantContext = Depends(resolve_tenant_context), savings_rate: Optional[float] = None):
    cost_summary = _costs.get_cost_summary(ctx.tenant_id)
    prev_summary = _costs.get_cost_summary(ctx.tenant_id, days=60)
    prev_cost = prev_summary.get("total_cost_usd", 0)
    curr_cost = cost_summary.get("total_cost_usd", 0)
    policies = _rules.list_policies(ctx.tenant_id)
    experiments = _experiments.list_experiments(ctx.tenant_id)
    by_model = cost_summary.get("by_model", [])
    providers: Dict[str, float] = {}
    models_str: Dict[str, float] = {}
    for row in by_model:
        p = row.get("provider", "unknown")
        providers[p] = providers.get(p, 0) + (row.get("total_cost") or 0)
        m = row.get("model", "unknown")
        models_str[m] = models_str.get(m, 0) + (row.get("total_cost") or 0)
    roi_data = _roi.calculate(ctx.tenant_id, assumed_savings_rate=savings_rate)
    top_users_list = _costs.get_top_users(ctx.tenant_id)
    provider_eff = _costs.get_provider_efficiency(ctx.tenant_id)
    cost_trend = _costs.get_cost_trend(ctx.tenant_id)
    return {
        "finops": cost_summary,
        "roi": roi_data,
        "prompts": _prompts.dashboard_stats(ctx.tenant_id),
        "budget_alerts": _budgets.get_alerts(ctx.tenant_id),
        "anomalies": _anomaly.scan(ctx.tenant_id),
        "cache": _cache_gov.stats(),
        "user_summary": _summarizer.summarize_user(ctx.tenant_id, ctx.user_id),
        "tenant_summary": _summarizer.summarize_tenant(ctx.tenant_id),
        "governance": {
            "total_policies": len(policies),
            "active_policies": sum(1 for p in policies if p.get("enabled")),
            "policies": policies,
        },
        "experiments": {
            "total": len(experiments),
            "active": sum(1 for e in experiments if e.get("status") == "active"),
            "active_experiments": [e for e in experiments if e.get("status") == "active"],
        },
        "cost_breakdown": {
            "by_provider": dict(sorted(providers.items(), key=lambda x: -x[1])),
            "by_model": dict(sorted(models_str.items(), key=lambda x: -x[1])),
        },
        "compression": {
            "rate_used": roi_data.get("assumed_rate", 50) / 100,
            "savings_avg": roi_data.get("avg_savings_percent", 0),
            "ace_enabled": True,
            "ace_detail": {
                "api": "/api/v2/ace/status",
                "explain": "/api/v2/ace/explain",
                "cells": "/api/v2/ace/cells",
            },
            "note": "Taux de compression ACE. Ajustable via ?savings_rate=. Détails ACE : /api/v2/ace/status",
        },
        "trend": {
            "daily": cost_trend,
            "total_prev_period": round(prev_cost - curr_cost, 2),
            "prev_period_cost": round(prev_cost, 2),
        },
        "top_users": top_users_list,
        "provider_efficiency": [
            {
                "provider": r["provider"],
                "total_cost": round(r["total_cost"] or 0, 4),
                "total_tokens": r["total_tokens"] or 0,
                "requests": r["requests"] or 0,
                "cost_per_token": round((r["total_cost"] or 0) / (r["total_tokens"] or 1), 6),
            }
            for r in provider_eff
        ],
    }
