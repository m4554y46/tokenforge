import sqlite3
import os
import json
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tokenforge.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS optimization_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_prompt TEXT NOT NULL,
                optimized_prompt TEXT NOT NULL,
                version TEXT NOT NULL,
                original_tokens INTEGER NOT NULL,
                optimized_tokens INTEGER NOT NULL,
                savings_percent REAL NOT NULL,
                target_model TEXT NOT NULL,
                optimizer_model TEXT NOT NULL,
                explanation TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL UNIQUE,
                key_value TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def save_optimization(original, optimized, version, original_tokens,
                      optimized_tokens, savings_percent, target_model,
                      optimizer_model, explanation=""):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO optimization_history
            (original_prompt, optimized_prompt, version, original_tokens,
             optimized_tokens, savings_percent, target_model, optimizer_model,
             explanation, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (original, optimized, version, original_tokens, optimized_tokens,
              savings_percent, target_model, optimizer_model, explanation,
              datetime.now().isoformat()))


def get_history(limit=50):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM optimization_history
            ORDER BY created_at DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def get_stats():
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as total,
                   COALESCE(SUM(original_tokens - optimized_tokens), 0) as tokens_saved,
                   COALESCE(AVG(savings_percent), 0) as avg_savings
            FROM optimization_history
        """)
        totals = dict(cursor.fetchone())

        cursor.execute("""
            SELECT version,
                   COUNT(*) as count,
                   ROUND(AVG(savings_percent), 1) as avg_savings,
                   SUM(original_tokens - optimized_tokens) as tokens_saved
            FROM optimization_history
            GROUP BY version
            ORDER BY count DESC
        """)
        by_mode = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT DATE(created_at) as day,
                   COUNT(*) as count,
                   ROUND(AVG(savings_percent), 1) as avg_savings,
                   SUM(original_tokens - optimized_tokens) as tokens_saved
            FROM optimization_history
            WHERE created_at >= DATE('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY day ASC
        """)
        last_7_days = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT id, version, savings_percent, original_tokens, optimized_tokens,
                   created_at, substr(original_prompt, 1, 80) as original_preview
            FROM optimization_history
            ORDER BY created_at DESC LIMIT 5
        """)
        recent = [dict(r) for r in cursor.fetchall()]

        return {
            "total_optimizations": totals["total"],
            "total_tokens_saved": totals["tokens_saved"],
            "avg_savings_percent": round(totals["avg_savings"], 1),
            "by_mode": by_mode,
            "last_7_days": last_7_days,
            "recent": recent,
        }


def delete_history_entry(entry_id):
    with get_db() as conn:
        conn.cursor().execute("DELETE FROM optimization_history WHERE id = ?", (entry_id,))


def save_api_key(provider, key_value):
    with get_db() as conn:
        now = datetime.now().isoformat()
        conn.cursor().execute("""
            INSERT INTO api_keys (provider, key_value, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(provider) DO UPDATE SET
                key_value = excluded.key_value,
                updated_at = excluded.updated_at
        """, (provider, key_value, now, now))


def get_api_keys():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM api_keys")
        return [dict(row) for row in cursor.fetchall()]


def get_api_key(provider):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM api_keys WHERE provider = ?", (provider,))
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_api_key(provider):
    with get_db() as conn:
        conn.cursor().execute("DELETE FROM api_keys WHERE provider = ?", (provider,))


def save_template(name, category, content):
    with get_db() as conn:
        conn.cursor().execute("""
            INSERT INTO templates (name, category, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (name, category, content, datetime.now().isoformat()))


def get_templates():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM templates ORDER BY category, name")
        return [dict(row) for row in cursor.fetchall()]


def delete_template(template_id):
    with get_db() as conn:
        conn.cursor().execute("DELETE FROM templates WHERE id = ?", (template_id,))
