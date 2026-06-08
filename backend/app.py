import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import threading as _threading
import time as _time
import uuid as _uuid
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict
from backend.token_counter import count_tokens
from backend.prompt_optimizer import optimize_prompt
from backend.models import MODELS, OPTIMIZER_MODELS, calculate_cost, get_model_info
from backend.database import (
    init_db,
    save_optimization,
    get_history,
    get_stats,
    delete_history_entry,
    save_api_key,
    get_api_keys,
    get_api_key,
    delete_api_key,
    save_template,
    get_templates,
    delete_template,
)
from backend.utils import encrypt_api_key, decrypt_api_key, mask_api_key
from backend.document_router import router as document_router

app = FastAPI(title="TokenForge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CountRequest(BaseModel):
    text: str
    model: str = "gpt-4o"


class CountResponse(BaseModel):
    tokens: int
    model: str


class OptimizeRequest(BaseModel):
    prompt: str
    target_model: str = "gpt-4o"
    optimizer_provider: Optional[str] = None
    optimizer_model: Optional[str] = None
    category: Optional[str] = None
    refine_with_llm: bool = False


class LLMRefineRequest(BaseModel):
    text: str
    original: str = ""
    zone: str = "causal_validation"
    user_id: str = ""


class LLMStatusResponse(BaseModel):
    available: bool
    model: Optional[str] = None
    backend: Optional[str] = None


class OptimizeResponse(BaseModel):
    original_tokens: int
    original_cost: float
    versions: list
    source: str = "api"
    category: Optional[str] = None


class SaveKeyRequest(BaseModel):
    provider: str
    key: str


class SimulateRequest(BaseModel):
    prompt: str
    models: List[str]


class TemplateRequest(BaseModel):
    name: str
    category: str = "general"
    content: str


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/count-tokens", response_model=CountResponse)
def count(req: CountRequest):
    tokens = count_tokens(req.text, req.model)
    return CountResponse(tokens=tokens, model=req.model)


# ── Optimisation session store (memory) ──────────────────────────
_tasks: Dict[str, dict] = {}

def _run_optimize_task(session_id: str, req: OptimizeRequest):
    """Run optimization in a background thread with progress tracking."""
    logger = logging.getLogger(__name__)
    try:
        def on_progress(phase: str, progress: int):
            _tasks[session_id].update({
                "progress": progress,
                "phase": phase,
                "elapsed": _time.time() - _tasks[session_id]["start_time"],
            })

        _tasks[session_id].update({"phase": "counting", "progress": 1})
        original_tokens = count_tokens(req.prompt, req.target_model)
        target_info = get_model_info(req.target_model)
        original_cost = 0.0
        if target_info:
            output_ratio = 0.3
            output_tokens = max(int(original_tokens * output_ratio), 1)
            original_cost = calculate_cost(req.target_model, original_tokens, output_tokens)

        api_key = None
        provider = req.optimizer_provider
        optimizer_model = req.optimizer_model
        category = req.category

        if provider and optimizer_model:
            key_data = get_api_key(provider)
            if key_data:
                try:
                    api_key = decrypt_api_key(key_data["key_value"])
                except (ValueError, Exception):
                    api_key = key_data["key_value"]

        # Run optimization with progress callbacks
        from backend.prompt_optimizer import OptiTokenOptimizer
        opt = OptiTokenOptimizer()
        result = opt.optimize(
            req.prompt, category=category, spc_enabled=True,
            progress_callback=on_progress, refine_with_llm=req.refine_with_llm,
        )
        _meta = result.pop("_meta", {})

        # Build versions (same logic as before)
        versions = []
        changes_map = {
            "light": [{"type": "light_clean", "description": "Nettoyage conversationnel"}],
            "balanced": [{"type": "balanced_restruct", "description": "Restructuration par blocs + compression"}],
            "aggressive": [{"type": "spc_aggressive", "description": "Compression télégraphique sur base SPC protégée"}],
            "max": [{"type": "spc_max", "description": "SPC MAX: all rule-based + KOMPRESS neural"}],
            "industrial": [{"type": "spc_industrial", "description": "SPC INDUSTRIAL: production-grade KOMPRESS + full rules"}],
        }
        for key, changes in changes_map.items():
            entry = result.get(key)
            if not entry:
                continue
            opt_tokens = count_tokens(entry.get("prompt", ""), req.target_model)
            savings = round(((original_tokens - opt_tokens) / max(original_tokens, 1)) * 100, 1)
            entry["original_tokens"] = original_tokens
            entry["optimized_tokens"] = opt_tokens
            entry["savings_percent"] = savings
            entry["savings_tokens"] = original_tokens - opt_tokens
            entry["original_cost"] = original_cost
            entry["optimized_cost"] = calculate_cost(
                req.target_model, opt_tokens, max(int(opt_tokens * 0.3), 1)
            ) if target_info else 0
            entry["changes_made"] = changes
            versions.append(entry)

            try:
                save_optimization(
                    original=req.prompt,
                    optimized=entry.get("prompt", ""),
                    version=entry.get("label", "Unknown"),
                    original_tokens=original_tokens,
                    optimized_tokens=opt_tokens,
                    savings_percent=savings,
                    target_model=req.target_model,
                    optimizer_model=optimizer_model or req.target_model,
                    explanation="\n".join(c.get("description", str(c)) for c in changes),
                )
            except Exception as exc:
                logger.warning("Failed to save history: %s", exc)

        _tasks[session_id].update({
            "progress": 100,
            "phase": "complete",
            "elapsed": _time.time() - _tasks[session_id]["start_time"],
            "result": {
                "original_tokens": original_tokens,
                "original_cost": original_cost,
                "versions": versions,
                "source": "api" if (api_key and provider) else "fallback",
                "category": _meta.get("category", category or "general"),
            },
        })
    except Exception as exc:
        logger.error("Optimization task failed: %s", exc)
        _tasks[session_id].update({
            "progress": -1, "phase": "error", "error": str(exc),
        })


@app.post("/api/optimize")
async def optimize(req: OptimizeRequest):
    """Start optimization in background and return session ID."""
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    session_id = _uuid.uuid4().hex[:8]
    _tasks[session_id] = {
        "progress": 0, "phase": "queued", "start_time": _time.time(), "elapsed": 0,
    }
    _threading.Thread(
        target=_run_optimize_task, args=(session_id, req), daemon=True
    ).start()
    return {"session_id": session_id}


@app.get("/api/progress/{session_id}")
def get_progress(session_id: str):
    """Poll progress of an optimization task."""
    task = _tasks.get(session_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ── LLM Refine routes (Couche 2: Gray Zone) ────────────────────


@app.post("/api/llm/refine")
async def llm_refine(req: LLMRefineRequest):
    """Refine compressed text through gray zone LLM."""
    try:
        from .spc.gray_zone import GrayZoneRouter, GrayZone
        from .spc.llama_cpp import LlamaCpp

        zone_map = {
            "ambiguity": GrayZone.AMBIGUITY,
            "fine_protection": GrayZone.FINE_PROTECTION,
            "causal_validation": GrayZone.CAUSAL_VALIDATION,
            "register": GrayZone.REGISTER,
            "reexpansion": GrayZone.REEXPANSION,
        }
        zone = zone_map.get(req.zone, GrayZone.CAUSAL_VALIDATION)
        llm = LlamaCpp()
        router = GrayZoneRouter(llm=llm)
        if not router.is_available():
            return {"refined": req.text, "zone": req.zone, "llm_available": False}
        refined, meta = router.refine(
            text=req.text,
            original=req.original,
            zone=zone,
            user_id=req.user_id,
            force=True,
        )
        return {"refined": refined, "zone": req.zone, "meta": meta, "llm_available": True}
    except Exception as exc:
        logger.warning("LLM refine failed: %s", exc)
        return {"refined": req.text, "zone": req.zone, "error": str(exc)}


@app.get("/api/llm/status")
def llm_status():
    """Check if local LLM is available for gray zone refinement."""
    try:
        from .spc.llama_cpp import LlamaCpp
        llm = LlamaCpp()
        return {"available": llm.is_available(), "model": llm.model_path}
    except Exception as exc:
        return {"available": False, "error": str(exc)}


# ── Legacy /api/optimize-sync (kept for backward compat) ──────


@app.get("/api/models")
def list_models():
    return {"models": MODELS, "optimizer_models": OPTIMIZER_MODELS}


@app.get("/api/model/{model_id}")
def model_info(model_id: str):
    info = get_model_info(model_id)
    if not info:
        raise HTTPException(status_code=404, detail="Model not found")
    return info


@app.post("/api/simulate-cost")
def simulate_cost(req: SimulateRequest):
    input_tokens = count_tokens(req.prompt, "gpt-4o")
    results = []
    for model_id in req.models:
        info = get_model_info(model_id)
        if not info:
            continue
        cost = calculate_cost(model_id, input_tokens, input_tokens)
        results.append({
            "model": model_id,
            "family": info["family"],
            "provider": info["provider"],
            "input_tokens": input_tokens,
            "output_tokens": input_tokens,
            "total_tokens": input_tokens * 2,
            "cost": cost,
            "context_window": info["context_window"],
        })
    return {"results": results}


@app.get("/api/history")
def history(limit: int = 50):
    return get_history(limit)


@app.get("/api/stats")
def stats():
    return get_stats()


@app.delete("/api/history/{entry_id}")
def delete_history(entry_id: int):
    delete_history_entry(entry_id)
    return {"status": "deleted"}


@app.post("/api/keys")
def save_key(req: SaveKeyRequest):
    encrypted = encrypt_api_key(req.key)
    save_api_key(req.provider, encrypted)
    return {"status": "saved", "provider": req.provider}


@app.get("/api/keys")
def list_keys():
    keys = get_api_keys()
    masked = []
    for k in keys:
        try:
            decrypted = decrypt_api_key(k["key_value"])
            masked_key = mask_api_key(decrypted)
        except Exception:
            masked_key = "****"
        masked.append({
            "id": k["id"],
            "provider": k["provider"],
            "key_masked": masked_key,
            "created_at": k["created_at"],
            "updated_at": k["updated_at"],
        })
    return masked


@app.get("/api/keys/{provider}")
def get_key(provider: str):
    key_data = get_api_key(provider)
    if not key_data:
        raise HTTPException(status_code=404, detail="Key not found")
    try:
        decrypted = decrypt_api_key(key_data["key_value"])
    except Exception:
        decrypted = key_data["key_value"]
    return {
        "provider": provider,
        "key_masked": mask_api_key(decrypted),
        "has_key": True,
    }


@app.delete("/api/keys/{provider}")
def remove_key(provider: str):
    delete_api_key(provider)
    return {"status": "deleted"}


@app.post("/api/templates")
def create_template(req: TemplateRequest):
    save_template(req.name, req.category, req.content)
    return {"status": "created"}


@app.get("/api/templates")
def list_templates():
    return get_templates()


@app.delete("/api/templates/{template_id}")
def remove_template(template_id: int):
    delete_template(template_id)
    return {"status": "deleted"}


@app.post("/api/restart")
def restart_api():
    def _restart():
        import subprocess as _sp
        pid = str(os.getpid())
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        py = sys.executable.replace("\\", "\\\\")
        code = (
            "import subprocess,time,os\n"
            f"time.sleep(0.5)\n"
            f"subprocess.run(['taskkill','/F','/PID','{pid}'])\n"
            "time.sleep(0.5)\n"
            f"subprocess.Popen([r'{py}','-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8765'],cwd=r'{base}')\n"
        )
        _sp.Popen([sys.executable, '-c', code])

    _threading.Thread(target=_restart, daemon=True).start()
    return {"status": "restarting"}


app.include_router(document_router)

_frontend_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
