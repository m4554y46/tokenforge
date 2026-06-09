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

# Client HTTP singleton pour le forwarding
_client = httpx.AsyncClient(timeout=FORGE_PROXY_TIMEOUT, verify=True)


async def _get_client() -> httpx.AsyncClient:
    """Retourne le client HTTP singleton, le réinitialise si le timeout a changé."""
    global _client
    return _client


router = APIRouter(prefix="/v1")


# ════════════════════════════════════════════════════════════
#  1. MOTEUR DE COMPRESSION
# ════════════════════════════════════════════════════════════

class _Compressor:
    """Compresseur lazy-initialise avec cache de pipeline."""
    _instance = None
    _spc = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def compress(self, text: str) -> Tuple[str, bool, str]:
        """Compresse un prompt. Retourne (texte_compresse, fallback, profile_name)."""
        if not FORGE_COMPRESSION_ENABLED or not text or len(text) < 30:
            return text, False, "bypass"

        try:
            if self._spc is None:
                from backend.spc.pipeline import SPC
                from backend.spc.profiles import get_profile
                profile = get_profile(FORGE_COMPRESSION_PROFILE)
                self._spc = SPC(profile=profile)

            result = self._spc.compile(text)
            compressed = result.compressed

            # Quality gate : si fallback, on garde l'original
            if result.fallback or result.error:
                return text, True, FORGE_COMPRESSION_PROFILE

            # Verifier que le compresse est strictement plus court
            if len(compressed) >= len(text) * 0.90:
                return text, True, FORGE_COMPRESSION_PROFILE

            return compressed, False, FORGE_COMPRESSION_PROFILE

        except Exception as e:
            logger.warning("Compression failed: %s", e)
            return text, True, "error"

_compressor = _Compressor.get


# ════════════════════════════════════════════════════════════
#  2. LOGIQUE DE COMPRESSION DES MESSAGES
# ════════════════════════════════════════════════════════════

def _should_compress_role(role: str) -> bool:
    """Seuls les messages utilisateur sont compresses."""
    return role == "user"


def _compress_messages(messages: List[Dict]) -> Tuple[List[Dict], Dict]:
    """Compresse les messages utilisateur dans la conversation.

    Retourne:
        (messages_compresses, stats)
    """
    compressed = []
    stats = {"original_tokens": 0, "compressed_tokens": 0, "fallback": False}

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if _should_compress_role(role) and isinstance(content, str) and content.strip():
            o_tok = len(content.split())
            stats["original_tokens"] += o_tok

            c_text, fb, profile_name = _compressor().compress(content)

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

    if not messages:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "Missing messages", "type": "invalid_request_error"}}
        )

    # ── 1. Compression silencieuse ──────────────────────
    start = time.time()
    compressed_messages, stats = _compress_messages(messages)
    body["messages"] = compressed_messages
    _update_stats(stats)

    savings = 0
    if stats.get("original_tokens", 0) > 0:
        savings = max(0, (stats["original_tokens"] - stats["compressed_tokens"]) / stats["original_tokens"]) * 100

    logger.info(
        "PROXY %s | model=%s | tokens=%d->%d (%.0f%%) | stream=%s | %.1fs",
        request.client.host if request.client else "?",
        body.get("model", "?"),
        stats.get("original_tokens", 0),
        stats.get("compressed_tokens", 0),
        savings,
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
