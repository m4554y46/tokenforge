"""Seed demo data — peuple la base avec des données réalistes pour la démo.

Usage :
    python -m backend.seed_demo          # seed DB with demo data
    python -m backend.seed_demo --reset   # recreate all demo data
"""

import argparse
import hashlib
import logging
import random
from datetime import datetime, timedelta, timezone

from backend.core.database_v2 import execute, query_one, query_all, _param

logger = logging.getLogger(__name__)

TENANT_ID = "demo"
USERS = [
    ("alice", "alice@demo.fr", "admin"),
    ("bob", "bob@demo.fr", "user"),
    ("carole", "carole@demo.fr", "user"),
    ("david", "david@demo.fr", "viewer"),
    ("emma", "emma@demo.fr", "user"),
]

TASK_TYPES = ["factuel", "analytique", "code", "creatif", "resume", "traduction"]
SPECIFICITIES = ["generic", "domain_jargon", "highly_specific"]
LENGTH_BUCKETS = ["short", "medium", "long", "very_long"]
MODELS = ["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet", "claude-3-5-haiku"]
PROFILES = ["bypass", "safe", "light", "balanced", "aggressive", "max"]
RATES = [0.0, 0.15, 0.25, 0.40, 0.60, 0.75]


def _rand_quality(profile: str) -> float:
    base_q = {
        "bypass": 1.0, "safe": 0.95, "light": 0.90,
        "balanced": 0.82, "aggressive": 0.70, "max": 0.55,
    }.get(profile, 0.80)
    noise = random.uniform(-0.08, 0.05)
    return max(0.1, min(1.0, base_q + noise))


def seed_all(reset: bool = False):
    p = _param()

    if reset:
        logger.info("Resetting demo data...")
        for table in ["ace_states", "ace_requests", "ace_sessions",
                       "prompt_events", "budgets", "policies",
                       "policy_audit", "experiments", "user_memory",
                       "tenant_memory"]:
            execute(f"DELETE FROM {table} WHERE tenant_id={p}", (TENANT_ID,))
        execute(f"DELETE FROM users WHERE tenant_id={p}", (TENANT_ID,))
        execute(f"DELETE FROM tenants WHERE id={p}", (TENANT_ID,))

    _seed_tenant()
    _seed_ace_states()
    _seed_ace_requests()
    _seed_prompt_events()
    _seed_budgets()
    _seed_policies()
    _seed_experiments()

    total = query_one(f"SELECT COUNT(*) as c FROM ace_states WHERE tenant_id={p}", (TENANT_ID,))
    reqs = query_one(f"SELECT COUNT(*) as c FROM ace_requests WHERE tenant_id={p}", (TENANT_ID,))
    evts = query_one(f"SELECT COUNT(*) as c FROM prompt_events WHERE tenant_id={p}", (TENANT_ID,))
    logger.info(
        "Seed complete: %d states, %d requests, %d events",
        (total or {}).get("c", 0),
        (reqs or {}).get("c", 0),
        (evts or {}).get("c", 0),
    )


def _seed_tenant():
    p = _param()
    execute(
        f"INSERT OR IGNORE INTO tenants (id, name, created_at, settings_json) "
        f"VALUES ({p},{p},{p},{p})",
        (TENANT_ID, "Démo Corp", "2025-01-15T08:00:00",
         '{"ace_enabled":true,"exploration_allowed":true,"contract_date":"2025-01-15"}'),
    )
    for uid, email, role in USERS:
        execute(
            f"INSERT OR IGNORE INTO users (id, tenant_id, email, roles_json, created_at) "
            f"VALUES ({p},{p},{p},{p},{p})",
            (uid, TENANT_ID, email, f'["{role}"]', "2025-01-15T08:00:00"),
        )


def _seed_ace_states():
    p = _param()
    for _ in range(600):
        rate = random.choice(RATES)
        profile = {0.0: "bypass", 0.15: "safe", 0.25: "light",
                   0.40: "balanced", 0.60: "aggressive", 0.75: "max"}[rate]
        q = _rand_quality(profile)
        n = random.randint(5, 200)
        n_exp = random.randint(0, max(1, n // 10))
        days_ago = random.randint(0, 30)
        ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        execute(
            f"INSERT OR IGNORE INTO ace_states "
            f"(tenant_id, user_cluster, task_type, length_bucket, model, rate, "
            f"quality_sum, n_samples, n_explorations, last_updated) "
            f"VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p})",
            (TENANT_ID, random.randint(0, 9), random.choice(TASK_TYPES),
             random.choice(LENGTH_BUCKETS), random.choice(MODELS),
             rate, round(q * n, 4), n, n_exp, ts),
        )


def _seed_ace_requests():
    p = _param()
    for i in range(2500):
        user_id = random.choice(USERS)[0]
        profile = random.choice(PROFILES)
        rate = {"bypass": 0.0, "safe": 0.15, "light": 0.25,
                "balanced": 0.40, "aggressive": 0.60, "max": 0.75}[profile]
        tokens_orig = random.randint(100, 3000)
        tokens_comp = max(10, int(tokens_orig * (1 - rate)))
        savings = round((tokens_orig - tokens_comp) / tokens_orig * 100, 2)
        days_ago = random.randint(0, 30)
        ts = (datetime.now(timezone.utc) - timedelta(days=days_ago, hours=random.randint(0, 23))).isoformat()
        latency = round(random.uniform(50, 2000), 2)
        was_exp = 1 if random.random() < 0.15 else 0
        execute(
            f"INSERT INTO ace_requests "
            f"(tenant_id, user_id, session_id, prompt_hash, task_type, specificity, "
            f"length_bucket, user_cluster, model, provider, profile_chosen, rate_actual, "
            f"tokens_original, tokens_compressed, savings_percent, latency_ms, "
            f"was_exploration, signals_json, created_at) "
            f"VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})",
            (TENANT_ID, user_id, f"sess_{i:04d}",
             hashlib.md5(f"prompt{i}".encode()).hexdigest(),
             random.choice(TASK_TYPES), random.choice(SPECIFICITIES),
             random.choice(LENGTH_BUCKETS), random.randint(0, 9),
             random.choice(MODELS), "openai",
             profile, rate, tokens_orig, tokens_comp,
             savings, latency, was_exp, "{}", ts),
        )


def _seed_prompt_events():
    p = _param()
    for i in range(3000):
        user_id = random.choice(USERS)[0]
        model = random.choice(MODELS)
        price = {"gpt-4o": 5.0, "gpt-4o-mini": 0.15,
                 "claude-3-5-sonnet": 3.0, "claude-3-5-haiku": 0.25}[model]
        inp = random.randint(100, 4000)
        out = random.randint(50, 2000)
        total = inp + out
        cost = round(total / 1_000_000 * price, 6)
        compressed = 1 if random.random() < 0.6 else 0
        savings = round(random.uniform(10, 60), 2) if compressed else 0
        days_ago = random.randint(0, 30)
        ts = (datetime.now(timezone.utc) - timedelta(days=days_ago, hours=random.randint(0, 23))).isoformat()
        execute(
            f"INSERT INTO prompt_events "
            f"(tenant_id, user_id, prompt_hash, prompt_preview, model, provider, "
            f"input_tokens, output_tokens, cost_usd, compressed, savings_percent, profile, created_at) "
            f"VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})",
            (TENANT_ID, user_id, hashlib.md5(f"evt{i}".encode()).hexdigest(),
             f"Prompt démo #{i}", model, "openai",
             inp, out, cost, compressed, savings,
             random.choice(PROFILES), ts),
        )


def _seed_budgets():
    p = _param()
    execute(
        f"INSERT OR IGNORE INTO budgets "
        f"(tenant_id, scope_type, scope_id, amount_usd, period, spent_usd, alert_threshold, created_at) "
        f"VALUES ({p},{p},{p},{p},{p},{p},{p},{p})",
        (TENANT_ID, "tenant", TENANT_ID, 5000.0, "monthly", 3240.50, 0.80,
         datetime.now(timezone.utc).isoformat()),
    )
    for uid, _, _ in USERS:
        execute(
            f"INSERT OR IGNORE INTO budgets "
            f"(tenant_id, scope_type, scope_id, amount_usd, period, spent_usd, alert_threshold, created_at) "
            f"VALUES ({p},{p},{p},{p},{p},{p},{p},{p})",
            (TENANT_ID, "user", uid, 1000.0, "monthly",
             round(random.uniform(200, 900), 2), 0.80,
             datetime.now(timezone.utc).isoformat()),
        )


def _seed_policies():
    p = _param()
    policies = [
        ("rgpd-security", "Sécurité RGPD", "block",
         '{"rules":["no_pii"]}', 1, "RGPD", "2025-01-15T08:00:00"),
        ("cost-limit", "Limitation coûts", "alert",
         '{"threshold":0.8}', 1, "FINANCE", "2025-01-15T08:00:00"),
        ("model-restrict", "Modèle autorisé", "allow",
         '{"models":["gpt-4o","gpt-4o-mini","claude"]}', 1, "COMPLIANCE", "2025-01-15T08:00:00"),
        ("compression-force", "Compression forcée", "enforce",
         '{"profile":"balanced"}', 0, "COST", "2025-01-15T08:00:00"),
        ("audit-weekly", "Audit hebdomadaire", "audit",
         '{"frequency":"weekly"}', 1, "AUDIT", "2025-01-15T08:00:00"),
    ]
    now = datetime.now(timezone.utc).isoformat()
    for pid, name, rtype, config, enabled, tags, created in policies:
        execute(
            f"INSERT OR IGNORE INTO policies "
            f"(tenant_id, name, rule_type, config_json, enabled, compliance_tags, created_at, updated_at) "
            f"VALUES ({p},{p},{p},{p},{p},{p},{p},{p})",
            (TENANT_ID, name, rtype, config, enabled, tags, created, now),
        )


def _seed_experiments():
    p = _param()
    experiments = [
        ("ACE vs static", "balanced", "industrial", "quality", "active"),
        ("Cache TTL 5min", "cache_300", "cache_60", "latency", "active"),
        ("Modèle qualité v2", "quality_v2", "quality_v1", "quality", "draft"),
    ]
    for name, va, vb, metric, status in experiments:
        execute(
            f"INSERT OR IGNORE INTO experiments "
            f"(tenant_id, name, variant_a, variant_b, metric, status, results_json, created_at) "
            f"VALUES ({p},{p},{p},{p},{p},{p},{p},{p})",
            (TENANT_ID, name, va, vb, metric, status, "{}",
             datetime.now(timezone.utc).isoformat()),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Reset demo data before seeding")
    args = parser.parse_args()
    seed_all(reset=args.reset)
    print("Seed complete. Run `python -m pytest tests/test_ace.py -q` to verify.")
