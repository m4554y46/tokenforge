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
def finops_roi(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _roi.calculate(ctx.tenant_id)


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


# ── Governance ────────────────────────────────────────

@router.get("/governance/policies")
def list_policies(ctx: TenantContext = Depends(resolve_tenant_context)):
    return _rules.list_policies(ctx.tenant_id)


@router.post("/governance/policies")
def create_policy(req: PolicyRequest, ctx: TenantContext = Depends(resolve_tenant_context)):
    return _rules.create_policy(ctx.tenant_id, req.name, req.rule_type, req.config, req.compliance_tags, ctx.user_id)


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


# ── Dashboard ─────────────────────────────────────────

@router.get("/dashboard")
def executive_dashboard(ctx: TenantContext = Depends(resolve_tenant_context)):
    return {
        "finops": _costs.get_cost_summary(ctx.tenant_id),
        "roi": _roi.calculate(ctx.tenant_id),
        "prompts": _prompts.dashboard_stats(ctx.tenant_id),
        "budget_alerts": _budgets.get_alerts(ctx.tenant_id),
        "anomalies": _anomaly.scan(ctx.tenant_id),
        "cache": _cache_gov.stats(),
        "user_summary": _summarizer.summarize_user(ctx.tenant_id, ctx.user_id),
        "tenant_summary": _summarizer.summarize_tenant(ctx.tenant_id),
    }
