from typing import List

from backend.core.database_v2 import get_db, _param


ACE_TABLES_SQL = {
    "ace_states": """CREATE TABLE IF NOT EXISTS ace_states (
        tenant_id TEXT NOT NULL,
        user_cluster INTEGER NOT NULL,
        task_type TEXT NOT NULL,
        length_bucket TEXT NOT NULL,
        model TEXT NOT NULL,
        rate REAL NOT NULL,
        quality_sum REAL NOT NULL DEFAULT 0,
        n_samples REAL NOT NULL DEFAULT 0,
        n_explorations INTEGER NOT NULL DEFAULT 0,
        last_updated TEXT NOT NULL,
        PRIMARY KEY (tenant_id, user_cluster, task_type, length_bucket, model, rate)
    )""",
    "ace_requests": """CREATE TABLE IF NOT EXISTS ace_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        user_id TEXT,
        session_id TEXT,
        prompt_hash TEXT NOT NULL,
        task_type TEXT NOT NULL,
        specificity TEXT NOT NULL,
        length_bucket TEXT NOT NULL,
        user_cluster INTEGER NOT NULL,
        model TEXT NOT NULL,
        provider TEXT,
        profile_chosen TEXT NOT NULL,
        rate_actual REAL,
        tokens_original INTEGER NOT NULL,
        tokens_compressed INTEGER NOT NULL,
        savings_percent REAL NOT NULL,
        latency_ms REAL NOT NULL DEFAULT 0,
        was_exploration INTEGER NOT NULL DEFAULT 0,
        signals_json TEXT NOT NULL DEFAULT '{}',
        attribution TEXT,
        pif_headroom REAL,
        integrity_passed INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    )""",
    "ace_sessions": """CREATE TABLE IF NOT EXISTS ace_sessions (
        session_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        user_id TEXT,
        prompt_hash TEXT NOT NULL,
        prompt_preview TEXT,
        response_hash TEXT,
        profile_chosen TEXT,
        created_at TEXT NOT NULL,
        PRIMARY KEY (session_id, prompt_hash)
    )""",
    "calibration_samples": """CREATE TABLE IF NOT EXISTS calibration_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        prompt_hash TEXT NOT NULL,
        task_type TEXT NOT NULL,
        specificity TEXT NOT NULL,
        length_bucket TEXT NOT NULL,
        user_cluster INTEGER NOT NULL,
        model TEXT NOT NULL,
        token_count INTEGER NOT NULL,
        pif_headroom REAL,
        features_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    "drift_events": """CREATE TABLE IF NOT EXISTS drift_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mmd_value REAL NOT NULL,
        p_value REAL NOT NULL,
        n_production INTEGER NOT NULL,
        n_calibration INTEGER NOT NULL,
        tenant_id TEXT,
        created_at TEXT NOT NULL
    )""",
    "oracle_evaluations": """CREATE TABLE IF NOT EXISTS oracle_evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER,
        passed INTEGER NOT NULL,
        score REAL NOT NULL,
        dimensions_json TEXT,
        failure_dimensions TEXT,
        created_at TEXT NOT NULL
    )""",
}


def init_ace_tables() -> None:
    from backend.core.database_v2 import get_db, _param
    with get_db() as conn:
        cur = conn.cursor()
        for name, sql in ACE_TABLES_SQL.items():
            cur.execute(sql)
    from backend.core.cache import cache
    cache.set("ace_tables_initialized", "1", 86400)

    # Migrations pour colonnes ajoutées
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE ace_requests ADD COLUMN pif_headroom REAL")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE ace_requests ADD COLUMN integrity_passed INTEGER NOT NULL DEFAULT 1")
    except Exception:
        pass
