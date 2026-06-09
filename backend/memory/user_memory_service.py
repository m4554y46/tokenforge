"""Service mémoire utilisateur — préférences et habitudes."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.core.database_v2 import query_all, query_one, execute, _param


class UserMemoryService:
    """Gère le profil mémoire par utilisateur."""

    DEFAULT_KEYS = ("language", "tone", "format", "style", "favorite_model", "constraints")

    def get_profile(self, tenant_id: str, user_id: str) -> Dict[str, Any]:
        p = _param()
        rows = query_all(
            f"SELECT key, value_json, confidence, source, updated_at FROM user_memory "
            f"WHERE tenant_id={p} AND user_id={p} ORDER BY updated_at DESC",
            (tenant_id, user_id),
        )
        preferences = {}
        for row in rows:
            try:
                val = json.loads(row["value_json"])
            except (json.JSONDecodeError, TypeError):
                val = row["value_json"]
            preferences[row["key"]] = {
                "value": val, "confidence": row["confidence"],
                "source": row["source"], "updated_at": row["updated_at"],
            }
        return {"tenant_id": tenant_id, "user_id": user_id, "preferences": preferences}

    def set_preference(
        self, tenant_id: str, user_id: str, key: str, value: Any,
        confidence: float = 1.0, source: str = "inferred",
    ) -> None:
        p = _param()
        now = datetime.now().isoformat()
        execute(
            f"INSERT OR REPLACE INTO user_memory (tenant_id, user_id, key, value_json, confidence, source, updated_at) "
            f"VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})",
            (tenant_id, user_id, key, json.dumps(value), confidence, source, now),
        )

    def update_profile(self, tenant_id: str, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in updates.items():
            self.set_preference(tenant_id, user_id, key, value, source="manual")
        return self.get_profile(tenant_id, user_id)

    def export_profile(self, tenant_id: str, user_id: str) -> Dict[str, Any]:
        profile = self.get_profile(tenant_id, user_id)
        profile["exported_at"] = datetime.now().isoformat()
        return profile

    def delete_profile(self, tenant_id: str, user_id: str) -> int:
        p = _param()
        return execute(
            f"DELETE FROM user_memory WHERE tenant_id={p} AND user_id={p}",
            (tenant_id, user_id),
        )

    def add_constraint(self, tenant_id: str, user_id: str, constraint: str) -> None:
        profile = self.get_profile(tenant_id, user_id)
        constraints = profile.get("preferences", {}).get("constraints", {}).get("value", [])
        if not isinstance(constraints, list):
            constraints = []
        if constraint not in constraints:
            constraints.append(constraint)
        self.set_preference(tenant_id, user_id, "constraints", constraints)
