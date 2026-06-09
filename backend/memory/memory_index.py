"""Index vectoriel — Qdrant ou fallback mémoire."""

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from backend.config import get_settings
from backend.memory.memory_embeddings import cosine_similarity, deserialize_embedding, serialize_embedding

_qdrant_client = None
_lock = threading.Lock()


@dataclass
class MemoryEntry:
    id: str
    tenant_id: str
    owner_type: str
    owner_id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


class InMemoryIndex:
    """Index vectoriel en mémoire pour dev/tests."""

    def __init__(self):
        self._entries: Dict[str, MemoryEntry] = {}
        self._lock = threading.Lock()

    def upsert(self, entry: MemoryEntry) -> str:
        with self._lock:
            self._entries[entry.id] = entry
            return entry.id

    def search(
        self, query_vec: List[float], tenant_id: str,
        owner_type: Optional[str] = None, owner_id: Optional[str] = None,
        top_k: int = 5, min_score: float = 0.3,
    ) -> List[Tuple[MemoryEntry, float]]:
        results = []
        with self._lock:
            for entry in self._entries.values():
                if entry.tenant_id != tenant_id:
                    continue
                if owner_type and entry.owner_type != owner_type:
                    continue
                if owner_id and entry.owner_id != owner_id:
                    continue
                score = cosine_similarity(query_vec, entry.embedding)
                if score >= min_score:
                    results.append((entry, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def delete(self, entry_id: str) -> bool:
        with self._lock:
            return self._entries.pop(entry_id, None) is not None

    def list_by_owner(self, tenant_id: str, owner_type: str, owner_id: str) -> List[MemoryEntry]:
        with self._lock:
            return [
                e for e in self._entries.values()
                if e.tenant_id == tenant_id and e.owner_type == owner_type and e.owner_id == owner_id
            ]


_memory_index = InMemoryIndex()


def _get_qdrant():
    global _qdrant_client
    if _qdrant_client is not None:
        return _qdrant_client
    settings = get_settings()
    with _lock:
        if _qdrant_client is not None:
            return _qdrant_client
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
            client = QdrantClient(url=settings.QDRANT_URL)
            collections = [c.name for c in client.get_collections().collections]
            if settings.QDRANT_COLLECTION not in collections:
                client.create_collection(
                    collection_name=settings.QDRANT_COLLECTION,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                )
            _qdrant_client = client
            return client
        except Exception:
            return None


class MemoryIndex:
    """Abstraction index — Qdrant ou mémoire."""

    def upsert(self, entry: MemoryEntry) -> str:
        client = _get_qdrant()
        if client:
            try:
                from qdrant_client.models import PointStruct
                client.upsert(
                    collection_name=get_settings().QDRANT_COLLECTION,
                    points=[PointStruct(
                        id=entry.id, vector=entry.embedding,
                        payload={
                            "tenant_id": entry.tenant_id,
                            "owner_type": entry.owner_type,
                            "owner_id": entry.owner_id,
                            "content": entry.content,
                            **entry.metadata,
                        },
                    )],
                )
                return entry.id
            except Exception:
                pass
        return _memory_index.upsert(entry)

    def search(self, query_vec, tenant_id, owner_type=None, owner_id=None, top_k=5, min_score=0.3):
        client = _get_qdrant()
        if client:
            try:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                must = [FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))]
                if owner_type:
                    must.append(FieldCondition(key="owner_type", match=MatchValue(value=owner_type)))
                if owner_id:
                    must.append(FieldCondition(key="owner_id", match=MatchValue(value=owner_id)))
                hits = client.search(
                    collection_name=get_settings().QDRANT_COLLECTION,
                    query_vector=query_vec, limit=top_k,
                    query_filter=Filter(must=must),
                )
                results = []
                for hit in hits:
                    if hit.score < min_score:
                        continue
                    entry = MemoryEntry(
                        id=str(hit.id), tenant_id=tenant_id,
                        owner_type=hit.payload.get("owner_type", ""),
                        owner_id=hit.payload.get("owner_id", ""),
                        content=hit.payload.get("content", ""),
                        embedding=hit.vector or query_vec,
                        metadata={k: v for k, v in hit.payload.items()
                                  if k not in ("tenant_id", "owner_type", "owner_id", "content")},
                    )
                    results.append((entry, hit.score))
                return results
            except Exception:
                pass
        return _memory_index.search(query_vec, tenant_id, owner_type, owner_id, top_k, min_score)

    def delete(self, entry_id: str) -> bool:
        client = _get_qdrant()
        if client:
            try:
                client.delete(collection_name=get_settings().QDRANT_COLLECTION, points_selector=[entry_id])
                return True
            except Exception:
                pass
        return _memory_index.delete(entry_id)

    def list_by_owner(self, tenant_id: str, owner_type: str, owner_id: str) -> List[MemoryEntry]:
        return _memory_index.list_by_owner(tenant_id, owner_type, owner_id)


memory_index = MemoryIndex()
