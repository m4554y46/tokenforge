"""Contexte multi-tenant — isolation par tenant et utilisateur."""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException

from backend.config import get_settings

_tenant_ctx: ContextVar[str] = ContextVar("tenant_id", default="default")
_user_ctx: ContextVar[str] = ContextVar("user_id", default="anonymous")


@dataclass
class TenantContext:
    tenant_id: str
    user_id: str
    roles: list[str]


def get_tenant_id() -> str:
    return _tenant_ctx.get()


def get_user_id() -> str:
    return _user_ctx.get()


def set_context(tenant_id: str, user_id: str) -> None:
    _tenant_ctx.set(tenant_id)
    _user_ctx.set(user_id)


async def resolve_tenant_context(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
) -> TenantContext:
    settings = get_settings()
    tenant_id = x_tenant_id or settings.DEFAULT_TENANT_ID
    user_id = x_user_id or "anonymous"
    if not tenant_id or len(tenant_id) > 128:
        raise HTTPException(status_code=400, detail="Invalid tenant ID")
    set_context(tenant_id, user_id)
    return TenantContext(tenant_id=tenant_id, user_id=user_id, roles=["user"])
