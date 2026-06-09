"""Service mémoire tenant — terminologie et connaissances métier."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.core.database_v2 import query_all, execute, _param


class TenantMemoryService:
    """Gère la base de connaissances par entreprise."""

    CATEGORIES = ("acronym", "terminology", "document_type", "template", "policy")

    def add_term(
        self, tenant_id: str, category: str, term: str,
        definition: str = "", source: str = "inferred", metadata: Optional[Dict] = None,
    ) -> None:
        p = _param()
        now = datetime.now().isoformat()
        execute(
            f"INSERT OR REPLACE INTO tenant_memory (tenant_id, category, term, definition, validated, metadata_json, updated_at) "
            f"VALUES ({p}, {p}, {p}, {p}, 0, {p}, {p})",
            (tenant_id, category, term, definition, json.dumps(metadata or {}), now),
        )

    def validate_term(self, tenant_id: str, category: str, term: str, validated: bool = True) -> int:
        p = _param()
        return execute(
            f"UPDATE tenant_memory SET validated={1 if validated else 0}, updated_at={p} "
            f"WHERE tenant_id={p} AND category={p} AND term={p}",
            (datetime.now().isoformat(), tenant_id, category, term),
        )

    def correct_term(self, tenant_id: str, category: str, term: str, definition: str) -> int:
        p = _param()
        return execute(
            f"UPDATE tenant_memory SET definition={p}, validated=1, updated_at={p} "
            f"WHERE tenant_id={p} AND category={p} AND term={p}",
            (definition, datetime.now().isoformat(), tenant_id, category, term),
        )

    def delete_term(self, tenant_id: str, category: str, term: str) -> int:
        p = _param()
        return execute(
            f"DELETE FROM tenant_memory WHERE tenant_id={p} AND category={p} AND term={p}",
            (tenant_id, category, term),
        )

    def list_all(self, tenant_id: str, category: Optional[str] = None) -> List[Dict]:
        p = _param()
        if category:
            return query_all(
                f"SELECT * FROM tenant_memory WHERE tenant_id={p} AND category={p} ORDER BY term",
                (tenant_id, category),
            )
        return query_all(
            f"SELECT * FROM tenant_memory WHERE tenant_id={p} ORDER BY category, term",
            (tenant_id,),
        )

    def get_validated_knowledge(self, tenant_id: str) -> List[Dict]:
        p = _param()
        return query_all(
            f"SELECT category, term, definition FROM tenant_memory WHERE tenant_id={p} AND validated=1",
            (tenant_id,),
        )

    def search_terms(self, tenant_id: str, query: str) -> List[Dict]:
        p = _param()
        return query_all(
            f"SELECT * FROM tenant_memory WHERE tenant_id={p} AND (term LIKE {p} OR definition LIKE {p})",
            (tenant_id, f"%{query}%", f"%{query}%"),
        )
