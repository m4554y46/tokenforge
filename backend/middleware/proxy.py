"""
TokenForge Proxy — Middleware reseau transparent.

Intercepte les appels a l'API OpenAI, compresse les prompts via le pipeline SPC,
forwarde a l'IA cible, retourne la reponse inchangée.

Usage utilisateur final:
    client = OpenAI(base_url="http://127.0.0.1:8765/v1", api_key="sk-...")
    # ou variable d'env: OPENAI_BASE_URL=http://127.0.0.1:8765/v1
    # Tout le reste est identique au SDK OpenAI standard.
"""

import json
import logging
import os
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

logger = logging.getLogger("forge-proxy")

# ── Configuration ─────────────────────────────────────────
FORGE_PROXY_TIMEOUT = int(os.environ.get("FORGE_PROXY_TIMEOUT", "120"))
FORGE_COMPRESSION_PROFILE = os.environ.get("FORGE_COMPRESSION_PROFILE", "industrial")
FORGE_COMPRESSION_ENABLED = os.environ.get("FORGE_COMPRESSION_ENABLED", "1") == "1"
FORGE_LLM_REFINE = os.environ.get("FORGE_LLM_REFINE", "0") == "1"
FORGE_STATS_ENABLED = os.environ.get("FORGE_STATS_ENABLED", "1") == "1"
FORGE_ACE_ENABLED = os.environ.get("FORGE_ACE_ENABLED", "1") == "1"

# Hop-by-hop headers a ne PAS forwarder
_HOP_BY_HOP = frozenset({
    "host", "connection", "keep-alive", "proxy-authenticate",
    "proxy-authorization", "te", "trailers",
    "transfer-encoding", "upgrade", "content-length",
})

# ── Statistiques ──────────────────────────────────────────
_proxy_stats: Dict[str, Any] = {
    "uptime": time.time(),
    "total_requests": 0,
    "total_tokens_original": 0,
    "total_tokens_compressed": 0,
    "total_fallbacks": 0,
    "total_errors": 0,
    "total_streaming": 0,
}

# Client HTTP singleton pour le forwarding (créé à la première utilisation)
_client: Optional[httpx.AsyncClient] = None

# ── ACE (Adaptive Compression Engine) ──────────────────────
_ace_decider = None
_session_ctx: Dict[str, Dict] = {}  # session_id → last request context

RATE_TO_PROFILE_REV = {
    "bypass": 0.0, "safe": 0.15, "light": 0.25,
    "balanced": 0.40, "aggressive": 0.55, "max": 0.70, "industrial": 0.70,
}


def _get_ace_decider():
    global _ace_decider
    if _ace_decider is None:
        try:
            from backend.ace import Decider
            _ace_decider = Decider()
        except Exception as e:
            logger.info("ACE not available, using static profile: %s", e)
            _ace_decider = False
    return _ace_decider if _ace_decider is not False else None


async def _get_client() -> httpx.AsyncClient:
    """Retourne le client HTTP singleton, le réinitialise si le timeout a changé."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=FORGE_PROXY_TIMEOUT, verify=True)
    return _client


router = APIRouter(prefix="/v1")


# ════════════════════════════════════════════════════════════
#  1. MOTEUR DE COMPRESSION
# ════════════════════════════════════════════════════════════

class _Compressor:
    """Compresseur lazy-initialise avec cache de pipelines par profil."""
    _instance = None
    _spc_cache: Dict[str, Any] = {}

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_spc(self, profile_name: str):
        if profile_name not in self._spc_cache:
            from backend.spc.pipeline import SPC
            from backend.spc.profiles import get_profile
            self._spc_cache[profile_name] = SPC(profile=get_profile(profile_name))
        return self._spc_cache[profile_name]

    def compress(self, text: str, profile_name: str = "") -> Tuple[str, bool, str]:
        """Compresse un prompt. Retourne (texte_compresse, fallback, profile_name_used)."""
        pn = profile_name or FORGE_COMPRESSION_PROFILE

        if not FORGE_COMPRESSION_ENABLED or not text or len(text) < 30:
            return text, False, "bypass"

        if pn == "bypass":
            return text, False, "bypass"

        try:
            spc = self._get_spc(pn)
            result = spc.compile(text)
            compressed = result.compressed

            if result.fallback or result.error:
                return text, True, pn

            from backend.token_counter import count_tokens
            orig_tok = count_tokens(text)
            comp_tok = count_tokens(compressed)
            if comp_tok >= orig_tok * 0.90 or comp_tok >= orig_tok:
                return text, True, pn

            return compressed, False, pn

        except Exception as e:
            logger.warning("Compression failed: %s", e)
            return text, True, pn

_compressor = _Compressor.get


# ════════════════════════════════════════════════════════════
#  2. LOGIQUE DE COMPRESSION DES MESSAGES
# ════════════════════════════════════════════════════════════

def _should_compress_role(role: str) -> bool:
    """Seuls les messages utilisateur sont compresses."""
    return role == "user"


def _compress_messages(messages: List[Dict], profile_name: str = "") -> Tuple[List[Dict], Dict]:
    """Compresse les messages utilisateur dans la conversation.

    Retourne:
        (messages_compresses, stats)
    """
    compressed = []
    stats = {"original_tokens": 0, "compressed_tokens": 0, "fallback": False, "profile_used": profile_name or FORGE_COMPRESSION_PROFILE}

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if _should_compress_role(role) and isinstance(content, str) and content.strip():
            o_tok = len(content.split())
            stats["original_tokens"] += o_tok

            c_text, fb, pn = _compressor().compress(content, profile_name=profile_name)

            c_tok = len(c_text.split())
            stats["compressed_tokens"] += c_tok

            if fb:
                stats["fallback"] = True

            compressed.append({**msg, "content": c_text})
        else:
            compressed.append(msg)

    return compressed, stats


# ════════════════════════════════════════════════════════════
#  3. FORWARDING HTTP VERS L'IA CIBLE
# ════════════════════════════════════════════════════════════

def _filter_headers(headers: dict) -> dict:
    """Supprime les headers hop-by-hop et ceux qu'on ne doit pas forwarder."""
    return {
        k: v for k, v in headers.items()
        if k.lower() not in _HOP_BY_HOP
    }


async def _forward(
    method: str,
    path: str,
    headers: dict,
    body: Optional[bytes] = None,
    stream: bool = False,
) -> httpx.Response:
    """Forwarde une requete vers l'API OpenAI cible."""
    target = os.environ.get("FORGE_TARGET_URL", "https://api.openai.com")
    url = target.rstrip("/") + "/" + path.lstrip("/")

    client = await _get_client()
    req = client.build_request(method, url, headers=headers, content=body)
    return await client.send(req, stream=stream)


def _rewrite_response_headers(headers: dict) -> dict:
    """Nettoie les headers de reponse pour le client."""
    out = {}
    for k, v in headers.items():
        kl = k.lower()
        if kl in _HOP_BY_HOP:
            continue
        # Ne pas exposer les details internes d'OpenAI
        if kl.startswith("x-request-id") or kl == "via":
            continue
        out[k] = v
    # Ajouter CORS pour compatibilite navigateur
    out.setdefault("access-control-allow-origin", "*")
    return out


# ════════════════════════════════════════════════════════════
#  4. ROUTES DU PROXY
# ════════════════════════════════════════════════════════════

def _update_stats(stats: dict):
    """Met a jour les statistiques globales."""
    if not FORGE_STATS_ENABLED:
        return
    _proxy_stats["total_requests"] += 1
    _proxy_stats["total_tokens_original"] += stats.get("original_tokens", 0)
    _proxy_stats["total_tokens_compressed"] += stats.get("compressed_tokens", 0)
    if stats.get("fallback"):
        _proxy_stats["total_fallbacks"] += 1


async def _stream_response(upstream_response: httpx.Response) -> AsyncGenerator[bytes, None]:
    """Relaye les chunks SSE du streaming OpenAI."""
    try:
        async for chunk in upstream_response.aiter_bytes():
            yield chunk
    except Exception as e:
        logger.error("Streaming error: %s", e)
        # Envoyee une erreur SSE standard pour fermer proprement
        yield json.dumps({
            "error": {"message": "Proxy streaming error", "type": "proxy_error"}
        }).encode()


@router.api_route("/chat/completions", methods=["POST", "OPTIONS"])
async def chat_completions(request: Request):
    """Route principale: /v1/chat/completions.

    Accepte les memes parametres que l'API OpenAI.
    Le prompt est compresse silencieusement avant d'etre envoye a l'IA cible.
    """
    # CORS preflight
    if request.method == "OPTIONS":
        return Response(
            status_code=204,
            headers={
                "access-control-allow-origin": "*",
                "access-control-allow-methods": "POST, OPTIONS",
                "access-control-allow-headers": "*",
                "access-control-max-age": "86400",
            }
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}}
        )

    messages = body.get("messages", [])
    stream = body.get("stream", False)
    model = body.get("model", "gpt-4o")

    if not messages:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "Missing messages", "type": "invalid_request_error"}}
        )

    # ── Session & user context ──────────────────────────
    user_id = request.headers.get("x-user-id", "") or "anonymous"
    tenant_id = request.headers.get("x-tenant-id", "default")
    session_id = request.headers.get("x-session-id", "") or uuid.uuid4().hex[:12]

    # ── ACE : détection signaux pour la requête précédente ──
    if session_id in _session_ctx and FORGE_ACE_ENABLED:
        try:
            prev = _session_ctx.get(session_id)
            if prev:
                from backend.ace.signals import detect_signals, update_from_signals
                user_prompt = ""
                for msg in messages:
                    if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                        user_prompt = msg["content"]
                        break
                signal = detect_signals(session_id, user_id, tenant_id, user_prompt)
                if signal.reformulation or signal.continuation:
                    pf = prev.get("features", {})
                    update_from_signals(
                        tenant_id=pf.get("tenant_id", tenant_id),
                        user_cluster=pf.get("user_cluster", 0),
                        task_type=pf.get("task_type", "factuel"),
                        length_bucket=pf.get("length_bucket", "medium"),
                        model=pf.get("model", "gpt-4o"),
                        rate=prev.get("rate", 0.0),
                        signal=signal,
                    )
        except Exception as e:
            logger.warning("ACE signal detection failed: %s", e)

    # ── ACE : choisir le profil de compression ──────────
    start = time.time()
    profile_name = FORGE_COMPRESSION_PROFILE
    was_exploration = False
    ace_decider = _get_ace_decider() if FORGE_ACE_ENABLED else None
    ace_features = None

    if ace_decider is not None:
        try:
            user_prompt = ""
            for msg in messages:
                if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                    user_prompt = msg["content"]
                    break

            from backend.ace.features import extract_features
            token_count = len(user_prompt.split())
            ace_features = extract_features(
                prompt=user_prompt,
                token_count=token_count,
                model=model,
                user_id=user_id,
                tenant_id=tenant_id,
            )
            ace_features["prompt_preview"] = user_prompt[:200]
            ace_features["prompt_text"] = user_prompt

            pn, exp, _ = ace_decider.decide(ace_features)
            profile_name = pn
            was_exploration = exp
        except Exception as e:
            logger.warning("ACE decision failed, using default profile: %s", e)
            profile_name = FORGE_COMPRESSION_PROFILE

    # ── 1. Compression silencieuse ──────────────────────
    compressed_messages, stats = _compress_messages(messages, profile_name=profile_name)
    body["messages"] = compressed_messages
    _update_stats(stats)

    latency_ms = (time.time() - start) * 1000
    savings = 0
    if stats.get("original_tokens", 0) > 0:
        savings = max(0, (stats["original_tokens"] - stats["compressed_tokens"]) / stats["original_tokens"]) * 100

    logger.info(
        "PROXY %s | model=%s | profile=%s | tokens=%d->%d (%.0f%%) | explore=%s | stream=%s | %.1fs",
        request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?"),
        model,
        profile_name,
        stats.get("original_tokens", 0),
        stats.get("compressed_tokens", 0),
        savings,
        was_exploration,
        stream,
        time.time() - start,
    )

    # ── 2. Forward headers + body vers OpenAI ───────────
    headers = _filter_headers(dict(request.headers))
    new_body = json.dumps(body).encode()

    try:
        upstream = await _forward(
            "POST", "/v1/chat/completions",
            headers, new_body, stream=stream
        )
    except httpx.TimeoutException:
        _proxy_stats["total_errors"] += 1
        return JSONResponse(
            status_code=504,
            content={"error": {"message": "Upstream API timeout", "type": "proxy_timeout"}}
        )
    except Exception as e:
        _proxy_stats["total_errors"] += 1
        logger.error("Upstream error: %s", e)
        return JSONResponse(
            status_code=502,
            content={"error": {"message": "Upstream API error", "type": "proxy_error"}}
        )

    # ── 3. Reponse transparente ─────────────────────────
    resp_headers = _rewrite_response_headers(dict(upstream.headers))

    if stream:
        _proxy_stats["total_streaming"] += 1
        return StreamingResponse(
            _stream_response(upstream),
            status_code=upstream.status_code,
            headers=resp_headers,
            media_type=upstream.headers.get("content-type", "text/event-stream"),
        )
    else:
        content = await upstream.aread()

        # ── ACE : enregistrement post-réponse ──────────────
        if ace_decider is not None and ace_features is not None:
            try:
                import hashlib
                prompt_text = ""
                for msg in messages:
                    if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                        prompt_text = msg["content"]
                        break
                prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()[:16]
                response_text = content.decode() if isinstance(content, bytes) else content
                response_hash = hashlib.sha256(str(response_text).encode()).hexdigest()[:16]

                ace_decider.on_response(
                    features=ace_features,
                    profile_chosen=profile_name,
                    tokens_original=stats.get("original_tokens", 0),
                    tokens_compressed=stats.get("compressed_tokens", 0),
                    latency_ms=latency_ms,
                    was_exploration=was_exploration,
                    session_id=session_id,
                    prompt_hash=prompt_hash,
                    response_hash=response_hash,
                    provider=os.environ.get("FORGE_TARGET_URL", "openai").replace("https://", "").split(".")[0],
                )

                _session_ctx[session_id] = {
                    "features": ace_features,
                    "profile": profile_name,
                    "rate": RATE_TO_PROFILE_REV.get(profile_name, 0.0),
                    "prompt_hash": prompt_hash,
                    "response_hash": response_hash,
                }
                if len(_session_ctx) > 5000:
                    _session_ctx.pop(next(iter(_session_ctx)), None)
            except Exception as e:
                logger.warning("ACE post-response recording failed: %s", e)

        return Response(
            content=content,
            status_code=upstream.status_code,
            headers=resp_headers,
            media_type=upstream.headers.get("content-type", "application/json"),
        )


@router.api_route("/completions", methods=["POST", "OPTIONS"])
async def completions(request: Request):
    """Route legacy /v1/completions (moins utilisee mais compatible)."""
    if request.method == "OPTIONS":
        return Response(status_code=204, headers={"access-control-allow-origin": "*"})

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": {"message": "Invalid JSON"}})

    prompt = body.get("prompt", "")
    if isinstance(prompt, str) and prompt.strip():
        c_text, fb, _ = _compressor().compress(prompt)
        body["prompt"] = c_text
        _proxy_stats["total_requests"] += 1
        if fb:
            _proxy_stats["total_fallbacks"] += 1

    headers = _filter_headers(dict(request.headers))
    new_body = json.dumps(body).encode()

    try:
        upstream = await _forward("POST", "/v1/completions", headers, new_body)
        content = await upstream.aread()
        return Response(
            content=content,
            status_code=upstream.status_code,
            headers=_rewrite_response_headers(dict(upstream.headers)),
        )
    except Exception as e:
        _proxy_stats["total_errors"] += 1
        logger.error("Upstream error: %s", e)
        return JSONResponse(status_code=502, content={"error": {"message": "Upstream error"}})


@router.get("/models")
async def list_models(request: Request):
    """Relaye /v1/models vers l'API cible."""
    headers = _filter_headers(dict(request.headers))
    try:
        upstream = await _forward("GET", "/v1/models", headers)
        content = await upstream.aread()
        return Response(
            content=content,
            status_code=upstream.status_code,
            headers=_rewrite_response_headers(dict(upstream.headers)),
        )
    except Exception as e:
        logger.error("Models error: %s", e)
        return JSONResponse(status_code=502, content={"error": {"message": "Upstream error"}})


# ════════════════════════════════════════════════════════════
#  5. STATISTIQUES
# ════════════════════════════════════════════════════════════

@router.get("/proxy/stats")
async def proxy_stats():
    """Statistiques du proxy (interne, non relaye a OpenAI)."""
    elapsed = time.time() - _proxy_stats["uptime"]
    total = _proxy_stats["total_tokens_original"]
    saved = total - _proxy_stats["total_tokens_compressed"]
    return {
        "uptime_seconds": round(elapsed, 1),
        "uptime_human": f"{elapsed/3600:.1f}h" if elapsed > 3600 else f"{elapsed/60:.1f}min",
        "total_requests": _proxy_stats["total_requests"],
        "total_streaming": _proxy_stats["total_streaming"],
        "total_tokens_original": total,
        "total_tokens_compressed": _proxy_stats["total_tokens_compressed"],
        "total_tokens_saved": saved,
        "savings_percent": round(saved / max(total, 1) * 100, 1) if total > 0 else 0,
        "total_fallbacks": _proxy_stats["total_fallbacks"],
        "total_errors": _proxy_stats["total_errors"],
        "compression_profile": FORGE_COMPRESSION_PROFILE,
        "compression_enabled": FORGE_COMPRESSION_ENABLED,
    }
