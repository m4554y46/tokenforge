import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import threading as _threading

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
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


class OptimizeResponse(BaseModel):
    original_tokens: int
    original_cost: float
    versions: list
    source: str = "api"


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


@app.post("/api/optimize", response_model=OptimizeResponse)
def optimize(req: OptimizeRequest):
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    original_tokens = count_tokens(req.prompt, req.target_model)
    target_info = get_model_info(req.target_model)
    original_cost = 0.0
    if target_info:
        original_cost = calculate_cost(req.target_model, original_tokens, original_tokens)

    api_key = None
    provider = req.optimizer_provider
    optimizer_model = req.optimizer_model
    category = req.category

    if provider and optimizer_model:
        key_data = get_api_key(provider)
        if key_data:
            try:
                api_key = decrypt_api_key(key_data["key_value"])
            except Exception:
                api_key = key_data["key_value"]

    result = optimize_prompt(req.prompt, optimizer_model, provider, api_key, category=category)

    if isinstance(result, dict) and "error" in result:
        versions = result.get("fallback", [])
        source = "fallback"
    elif isinstance(result, dict) and "fallback" in result:
        versions = result["fallback"]
        source = "fallback"
    elif api_key and provider:
        versions = result
        source = "api"
    else:
        versions = result
        source = "fallback"

    for v in versions:
        opt_tokens = count_tokens(v.get("prompt", ""), req.target_model)
        v["original_tokens"] = original_tokens
        v["optimized_tokens"] = opt_tokens
        v["savings_percent"] = round(
            ((original_tokens - opt_tokens) / max(original_tokens, 1)) * 100, 1
        )
        v["savings_tokens"] = original_tokens - opt_tokens
        if target_info:
            v["original_cost"] = original_cost
            v["optimized_cost"] = calculate_cost(
                req.target_model, opt_tokens, opt_tokens
            )
        else:
            v["original_cost"] = 0
            v["optimized_cost"] = 0

        try:
            save_optimization(
                original=req.prompt,
                optimized=v.get("prompt", ""),
                version=v.get("label", "Unknown"),
                original_tokens=original_tokens,
                optimized_tokens=opt_tokens,
                savings_percent=v.get("savings_percent", 0),
                target_model=req.target_model,
                optimizer_model=optimizer_model or req.target_model,
                explanation="\n".join(v.get("changes_made", [])),
            )
        except Exception:
            pass

    return OptimizeResponse(
        original_tokens=original_tokens,
        original_cost=original_cost,
        versions=versions,
        source=source,
    )


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
            f"subprocess.run(['taskkill','/F','/PID','{pid}'],shell=True)\n"
            "time.sleep(0.5)\n"
            f"subprocess.Popen([r'{py}','-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8765'],cwd=r'{base}')\n"
        )
        _sp.Popen([sys.executable, '-c', code])

    _threading.Thread(target=_restart, daemon=True).start()
    return {"status": "restarting"}


_frontend_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
