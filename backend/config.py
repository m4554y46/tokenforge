"""TokenForge Intelligence Platform — configuration centralisée."""

import os
from functools import lru_cache
from typing import Optional


class Settings:
    APP_NAME = "TokenForge Intelligence Platform"
    APP_VERSION = "2.0.0"
    API_V1_PREFIX = "/api"
    API_V2_PREFIX = "/api/v2"

    # Base de données — SQLite par défaut, PostgreSQL en production
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "tokenforge_v2.db"),
    )
    USE_POSTGRES: bool = DATABASE_URL.startswith("postgresql")

    # Redis — fallback mémoire si absent
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")

    # Qdrant — fallback mémoire si absent
    QDRANT_URL: Optional[str] = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "tokenforge_memory")

    # Auth
    JWT_SECRET: str = os.getenv("JWT_SECRET", "tokenforge-dev-secret-change-in-prod")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
    OAUTH2_ENABLED: bool = os.getenv("OAUTH2_ENABLED", "0") == "1"
    OIDC_ISSUER: Optional[str] = os.getenv("OIDC_ISSUER")

    # Multi-tenant
    DEFAULT_TENANT_ID: str = os.getenv("DEFAULT_TENANT_ID", "default")
    TENANT_HEADER = "X-Tenant-ID"
    USER_HEADER = "X-User-ID"

    # Gateway
    FORGE_PROXY_TIMEOUT = int(os.getenv("FORGE_PROXY_TIMEOUT", "120"))
    FORGE_COMPRESSION_PROFILE = os.getenv("FORGE_COMPRESSION_PROFILE", "industrial")
    FORGE_COMPRESSION_ENABLED = os.getenv("FORGE_COMPRESSION_ENABLED", "1") == "1"
    FORGE_TARGET_URL = os.getenv("FORGE_TARGET_URL", "https://api.openai.com")

    # Observability
    OTEL_ENABLED = os.getenv("OTEL_ENABLED", "0") == "1"
    OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "tokenforge-v2")
    PROMETHEUS_ENABLED = os.getenv("PROMETHEUS_ENABLED", "1") == "1"

    # FinOps
    TOKENFORGE_COST_PER_1K_TOKENS = float(os.getenv("TOKENFORGE_COST_PER_1K", "0.002"))

    # Memory
    MEMORY_EMBEDDING_MODEL = os.getenv("MEMORY_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    MEMORY_MAX_ENTRIES = int(os.getenv("MEMORY_MAX_ENTRIES", "10000"))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    default_secret = "tokenforge-dev-secret-change-in-prod"
    if settings.JWT_SECRET == default_secret:
        import warnings
        warnings.warn(
            f"JWT_SECRET is using the default value. "
            f"Set JWT_SECRET environment variable in production! "
            f"Default secret: {default_secret}",
            RuntimeWarning,
            stacklevel=2,
        )
    return settings
