"""Couche persistance v2 — SQLite (dev) ou PostgreSQL (prod)."""

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

from backend.config import get_settings

_lock = threading.Lock()
_initialized = False


def _sqlite_path() -> str:
    settings = get_settings()
    if settings.USE_POSTGRES:
        return ""
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "")
    return url


@contextmanager
def get_db() -> Generator[Any, None, None]:
    settings = get_settings()
    if settings.USE_POSTGRES:
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            conn = psycopg2.connect(settings.DATABASE_URL, cursor_factory=RealDictCursor)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        except ImportError:
            raise RuntimeError("psycopg2 required for PostgreSQL")
    else:
        conn = sqlite3.connect(_sqlite_path())
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _param(style: str = "sqlite") -> str:
    return "%s" if get_settings().USE_POSTGRES else "?"


def init_v2_db() -> None:
    global _initialized
    with _lock:
        if _initialized:
            return
        p = _param()
        with get_db() as conn:
            cur = conn.cursor()
            tables = [
                f"""CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    created_at TEXT NOT NULL, settings_json TEXT DEFAULT '{{}}'
                )""",
                f"""CREATE TABLE IF NOT EXISTS users (
                    id TEXT NOT NULL, tenant_id TEXT NOT NULL,
                    email TEXT, roles_json TEXT DEFAULT '["user"]',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, id)
                )""",
                f"""CREATE TABLE IF NOT EXISTS user_memory (
                    id INTEGER PRIMARY KEY {"AUTOINCREMENT" if not get_settings().USE_POSTGRES else ""},
                    tenant_id TEXT NOT NULL, user_id TEXT NOT NULL,
                    key TEXT NOT NULL, value_json TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0, source TEXT DEFAULT 'inferred',
                    updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id, user_id, key)
                )""",
                f"""CREATE TABLE IF NOT EXISTS tenant_memory (
                    id INTEGER PRIMARY KEY {"AUTOINCREMENT" if not get_settings().USE_POSTGRES else ""},
                    tenant_id TEXT NOT NULL, category TEXT NOT NULL,
                    term TEXT NOT NULL, definition TEXT,
                    validated INTEGER DEFAULT 0, metadata_json TEXT DEFAULT '{{}}',
                    updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id, category, term)
                )""",
                f"""CREATE TABLE IF NOT EXISTS prompt_events (
                    id INTEGER PRIMARY KEY {"AUTOINCREMENT" if not get_settings().USE_POSTGRES else ""},
                    tenant_id TEXT NOT NULL, user_id TEXT,
                    prompt_hash TEXT NOT NULL, prompt_preview TEXT,
                    model TEXT, provider TEXT,
                    input_tokens INTEGER, output_tokens INTEGER,
                    cost_usd REAL, compressed INTEGER DEFAULT 0,
                    savings_percent REAL DEFAULT 0,
                    profile TEXT, created_at TEXT NOT NULL
                )""",
                f"""CREATE TABLE IF NOT EXISTS budgets (
                    id INTEGER PRIMARY KEY {"AUTOINCREMENT" if not get_settings().USE_POSTGRES else ""},
                    tenant_id TEXT NOT NULL, scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL, amount_usd REAL NOT NULL,
                    period TEXT NOT NULL, spent_usd REAL DEFAULT 0,
                    alert_threshold REAL DEFAULT 0.8,
                    created_at TEXT NOT NULL,
                    UNIQUE(tenant_id, scope_type, scope_id, period)
                )""",
                f"""CREATE TABLE IF NOT EXISTS policies (
                    id INTEGER PRIMARY KEY {"AUTOINCREMENT" if not get_settings().USE_POSTGRES else ""},
                    tenant_id TEXT NOT NULL, name TEXT NOT NULL,
                    rule_type TEXT NOT NULL, config_json TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1, compliance_tags TEXT DEFAULT '',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )""",
                f"""CREATE TABLE IF NOT EXISTS policy_audit (
                    id INTEGER PRIMARY KEY {"AUTOINCREMENT" if not get_settings().USE_POSTGRES else ""},
                    tenant_id TEXT NOT NULL, policy_id INTEGER,
                    action TEXT NOT NULL, actor TEXT, details_json TEXT,
                    created_at TEXT NOT NULL
                )""",
                f"""CREATE TABLE IF NOT EXISTS experiments (
                    id INTEGER PRIMARY KEY {"AUTOINCREMENT" if not get_settings().USE_POSTGRES else ""},
                    tenant_id TEXT NOT NULL, name TEXT NOT NULL,
                    variant_a TEXT NOT NULL, variant_b TEXT NOT NULL,
                    metric TEXT DEFAULT 'cost', status TEXT DEFAULT 'active',
                    results_json TEXT DEFAULT '{{}}', created_at TEXT NOT NULL
                )""",
                f"""CREATE TABLE IF NOT EXISTS memory_embeddings (
                    id INTEGER PRIMARY KEY {"AUTOINCREMENT" if not get_settings().USE_POSTGRES else ""},
                    tenant_id TEXT NOT NULL, owner_type TEXT NOT NULL,
                    owner_id TEXT NOT NULL, content TEXT NOT NULL,
                    embedding_json TEXT, metadata_json TEXT DEFAULT '{{}}',
                    created_at TEXT NOT NULL
                )""",
            ]
            for sql in tables:
                cur.execute(sql)
            now = datetime.now().isoformat()
            if get_settings().USE_POSTGRES:
                cur.execute(
                    f"INSERT INTO tenants (id, name, created_at) VALUES ({p}, {p}, {p}) ON CONFLICT DO NOTHING",
                    ("default", "Default Tenant", now),
                )
            else:
                cur.execute(
                    f"INSERT OR IGNORE INTO tenants (id, name, created_at) VALUES ({p}, {p}, {p})",
                    ("default", "Default Tenant", now),
                )
        _initialized = True


def upsert_row(table: str, data: Dict[str, Any], conflict_cols: List[str]) -> None:
    p = _param()
    cols = list(data.keys())
    placeholders = ", ".join([p] * len(cols))
    col_names = ", ".join(cols)
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c not in conflict_cols)
    sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
    if get_settings().USE_POSTGRES:
        sql += f" ON CONFLICT ({', '.join(conflict_cols)}) DO UPDATE SET {updates}"
    else:
        sql = sql.replace("INSERT INTO", "INSERT OR REPLACE INTO")
    with get_db() as conn:
        conn.cursor().execute(sql, list(data.values()))


def query_all(sql: str, params: tuple = ()) -> List[Dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        if get_settings().USE_POSTGRES:
            return [dict(r) for r in rows]
        return [dict(row) for row in rows]


def query_one(sql: str, params: tuple = ()) -> Optional[Dict]:
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple = ()) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.rowcount
