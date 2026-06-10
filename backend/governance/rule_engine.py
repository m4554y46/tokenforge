"""Moteur de règles — gouvernance des appels LLM."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.core.database_v2 import query_all, query_one, execute, _param


class RuleEngine:
    """Évalue et applique les politiques par tenant."""

    RULE_TYPES = (
        "deny_model", "limit_provider", "force_compression",
        "force_cache", "max_tokens", "require_approval",
    )

    def create_policy(
        self, tenant_id: str, name: str, rule_type: str,
        config: Dict, compliance_tags: str = "", actor: str = "system",
    ) -> Dict[str, Any]:
        p = _param()
        now = datetime.now().isoformat()
        execute(
            f"INSERT INTO policies (tenant_id, name, rule_type, config_json, enabled, compliance_tags, created_at, updated_at) "
            f"VALUES ({p},{p},{p},{p},1,{p},{p},{p})",
            (tenant_id, name, rule_type, json.dumps(config), compliance_tags, now, now),
        )
        self._audit(tenant_id, None, "create", actor, {"name": name, "rule_type": rule_type})
        return {"name": name, "rule_type": rule_type, "config": config}

    def list_policies(self, tenant_id: str) -> List[Dict]:
        p = _param()
        rows = query_all(f"SELECT * FROM policies WHERE tenant_id={p} ORDER BY created_at DESC", (tenant_id,))
        for r in rows:
            r["config"] = json.loads(r.get("config_json", "{}"))
        return rows

    def evaluate(
        self, tenant_id: str, model: str, provider: str = "",
        user_id: str = "", tokens: int = 0,
    ) -> Dict[str, Any]:
        policies = [p for p in self.list_policies(tenant_id) if p.get("enabled")]
        decisions = []
        allowed = True
        force_compression = False
        force_cache = False
        for pol in policies:
            cfg = pol.get("config", {})
            rt = pol["rule_type"]
            if rt == "deny_model" and model in cfg.get("models", []):
                allowed = False
                decisions.append({"policy": pol["name"], "action": "deny", "reason": f"Modèle {model} interdit"})
            elif rt == "limit_provider" and provider in cfg.get("providers", []):
                if cfg.get("action") == "deny":
                    allowed = False
                    decisions.append({"policy": pol["name"], "action": "deny", "reason": f"Provider {provider} limité"})
            elif rt == "force_compression":
                force_compression = True
                decisions.append({"policy": pol["name"], "action": "force_compression"})
            elif rt == "force_cache":
                force_cache = True
                decisions.append({"policy": pol["name"], "action": "force_cache"})
            elif rt == "max_tokens" and tokens > cfg.get("limit", 100000):
                allowed = False
                decisions.append({"policy": pol["name"], "action": "deny", "reason": "Limite tokens dépassée"})
        return {
            "allowed": allowed, "decisions": decisions,
            "force_compression": force_compression, "force_cache": force_cache,
        }

    def set_policy_enabled(self, tenant_id: str, policy_id: int, enabled: bool, actor: str = "system") -> Dict[str, Any]:
        p = _param()
        now = datetime.now().isoformat()
        execute(
            f"UPDATE policies SET enabled={p}, updated_at={p} WHERE tenant_id={p} AND id={p}",
            (int(enabled), now, tenant_id, policy_id),
        )
        action_label = "enable" if enabled else "disable"
        self._audit(tenant_id, policy_id, action_label, actor, {"policy_id": policy_id})
        return {"id": policy_id, "enabled": enabled}

    def _audit(self, tenant_id: str, policy_id: Optional[int], action: str, actor: str, details: Dict) -> None:
        p = _param()
        execute(
            f"INSERT INTO policy_audit (tenant_id, policy_id, action, actor, details_json, created_at) "
            f"VALUES ({p},{p},{p},{p},{p},{p})",
            (tenant_id, policy_id, action, actor, json.dumps(details), datetime.now().isoformat()),
        )

    def get_audit_log(self, tenant_id: str, limit: int = 50) -> List[Dict]:
        p = _param()
        return query_all(
            f"SELECT * FROM policy_audit WHERE tenant_id={p} ORDER BY created_at DESC LIMIT {p}",
            (tenant_id, limit),
        )
