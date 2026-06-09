"""Workflows d'approbation des politiques."""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.core.cache import cache


class ApprovalWorkflow:
    """Gère validation et historique des changements de politique."""

    def submit_for_approval(
        self, tenant_id: str, policy_name: str, change: Dict,
        submitter: str, approvers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        request_id = uuid.uuid4().hex[:12]
        request = {
            "id": request_id, "tenant_id": tenant_id,
            "policy_name": policy_name, "change": change,
            "submitter": submitter, "approvers": approvers or ["admin"],
            "status": "pending", "created_at": datetime.now().isoformat(),
            "history": [{"action": "submitted", "actor": submitter, "at": datetime.now().isoformat()}],
        }
        cache.set(f"approval:{tenant_id}:{request_id}", request, ttl=86400 * 7)
        return request

    def approve(self, tenant_id: str, request_id: str, approver: str) -> Dict[str, Any]:
        key = f"approval:{tenant_id}:{request_id}"
        request = cache.get(key)
        if not request:
            return {"error": "Request not found"}
        request["status"] = "approved"
        request["history"].append({"action": "approved", "actor": approver, "at": datetime.now().isoformat()})
        cache.set(key, request, ttl=86400 * 7)
        return request

    def reject(self, tenant_id: str, request_id: str, approver: str, reason: str = "") -> Dict[str, Any]:
        key = f"approval:{tenant_id}:{request_id}"
        request = cache.get(key)
        if not request:
            return {"error": "Request not found"}
        request["status"] = "rejected"
        request["history"].append({
            "action": "rejected", "actor": approver,
            "reason": reason, "at": datetime.now().isoformat(),
        })
        cache.set(key, request, ttl=86400 * 7)
        return request

    def list_pending(self, tenant_id: str) -> List[Dict]:
        return []
