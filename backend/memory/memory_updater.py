"""Mise à jour incrémentale de la mémoire depuis les interactions."""

import re
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from backend.memory.memory_embeddings import embed_text, serialize_embedding
from backend.memory.memory_index import MemoryEntry, memory_index
from backend.memory.user_memory_service import UserMemoryService
from backend.memory.tenant_memory_service import TenantMemoryService
from backend.core.database_v2 import execute, _param


class MemoryUpdater:
    """Apprend des interactions LLM pour enrichir user/tenant memory."""

    LANG_PATTERNS = {
        "fr": re.compile(r"\b(français|french|en français)\b", re.I),
        "en": re.compile(r"\b(english|anglais|in english)\b", re.I),
    }
    TONE_PATTERNS = {
        "professional": re.compile(r"\b(professionnel|professional|formel)\b", re.I),
        "casual": re.compile(r"\b(casual|décontracté|informel)\b", re.I),
        "consultant": re.compile(r"\b(consultant|executive summary)\b", re.I),
    }
    FORMAT_PATTERNS = {
        "table": re.compile(r"\b(tableau|table|markdown table)\b", re.I),
        "bullet": re.compile(r"\b(liste|bullet|puces)\b", re.I),
        "short": re.compile(r"\b(court|concis|brief|short)\b", re.I),
    }

    def __init__(self):
        self.user_svc = UserMemoryService()
        self.tenant_svc = TenantMemoryService()

    def learn_from_interaction(
        self, tenant_id: str, user_id: str, prompt: str,
        model: str = "", response: str = "", metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        updates = []
        for lang, pat in self.LANG_PATTERNS.items():
            if pat.search(prompt):
                self.user_svc.set_preference(tenant_id, user_id, "language", lang)
                updates.append(f"language={lang}")
        for tone, pat in self.TONE_PATTERNS.items():
            if pat.search(prompt):
                self.user_svc.set_preference(tenant_id, user_id, "tone", tone)
                updates.append(f"tone={tone}")
        for fmt, pat in self.FORMAT_PATTERNS.items():
            if pat.search(prompt):
                self.user_svc.set_preference(tenant_id, user_id, "format", fmt)
                updates.append(f"format={fmt}")
        if model:
            self.user_svc.set_preference(tenant_id, user_id, "favorite_model", model)
            updates.append(f"model={model}")
        acronyms = re.findall(r"\b[A-Z]{2,6}\b", prompt)
        for acr in set(acronyms[:5]):
                self.tenant_svc.add_term(tenant_id, "acronym", acr, source="inferred")
                updates.append(f"term:{acr}")
        entry_id = str(uuid.uuid4())
        vec = embed_text(prompt[:2000])
        memory_index.upsert(MemoryEntry(
            id=entry_id, tenant_id=tenant_id, owner_type="interaction",
            owner_id=user_id, content=prompt[:2000], embedding=vec,
            metadata={"model": model, **(metadata or {})},
        ))
        p = _param()
        execute(
            f"INSERT INTO memory_embeddings (tenant_id, owner_type, owner_id, content, embedding_json, metadata_json, created_at) "
            f"VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})",
            (tenant_id, "interaction", user_id, prompt[:2000],
             serialize_embedding(vec), "{}", datetime.now().isoformat()),
        )
        return {"updates": updates, "embedding_id": entry_id}
