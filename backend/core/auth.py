"""Auth OAuth2/OIDC + RBAC simplifié."""

import hashlib
import hmac
import json
import time
from typing import List, Optional

from fastapi import Depends, HTTPException, Header
from pydantic import BaseModel

from backend.config import get_settings
from backend.core.tenant import TenantContext, resolve_tenant_context


class TokenPayload(BaseModel):
    sub: str
    tenant_id: str
    roles: List[str] = ["user"]
    exp: float


def create_access_token(user_id: str, tenant_id: str, roles: Optional[List[str]] = None) -> str:
    settings = get_settings()
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "roles": roles or ["user"],
        "exp": time.time() + settings.JWT_EXPIRE_MINUTES * 60,
    }
    body = json.dumps(payload, separators=(",", ":"))
    sig = hmac.new(settings.JWT_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_token(token: str) -> TokenPayload:
    settings = get_settings()
    try:
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(settings.JWT_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("Invalid signature")
        payload = json.loads(body)
        if payload.get("exp", 0) < time.time():
            raise ValueError("Token expired")
        return TokenPayload(**payload)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


def require_role(*roles: str):
    async def checker(
        ctx: TenantContext = Depends(resolve_tenant_context),
        authorization: Optional[str] = Header(None),
    ) -> TenantContext:
        if authorization and authorization.startswith("Bearer "):
            token = verify_token(authorization[7:])
            if roles and not any(r in token.roles for r in roles):
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            ctx.roles = token.roles
        return ctx
    return checker
