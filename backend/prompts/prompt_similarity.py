"""Moteur de similarité — doublons, variantes, clusters."""

import hashlib
import re
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from backend.memory.memory_embeddings import cosine_similarity, embed_text
from backend.prompts.prompt_inventory import PromptInventory


class PromptSimilarityEngine:
    """Identifie doublons et clusters de prompts."""

    def __init__(self):
        self.inventory = PromptInventory()

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.lower().strip())

    def find_exact_duplicates(self, prompts: List[str]) -> List[Dict]:
        groups: Dict[str, List[int]] = defaultdict(list)
        for i, p in enumerate(prompts):
            groups[self._normalize(p)].append(i)
        return [
            {"normalized": k, "indices": v, "count": len(v)}
            for k, v in groups.items() if len(v) > 1
        ]

    def find_similar_pairs(
        self, prompts: List[str], threshold: float = 0.85,
    ) -> List[Dict]:
        if len(prompts) > 50:
            prompts = prompts[:50]
        embeddings = [embed_text(p[:1500]) for p in prompts]
        pairs = []
        for i in range(len(prompts)):
            for j in range(i + 1, len(prompts)):
                score = cosine_similarity(embeddings[i], embeddings[j])
                if score >= threshold:
                    pairs.append({
                        "index_a": i, "index_b": j, "similarity": round(score, 3),
                        "preview_a": prompts[i][:100], "preview_b": prompts[j][:100],
                    })
        pairs.sort(key=lambda x: x["similarity"], reverse=True)
        return pairs

    def cluster(self, prompts: List[str], threshold: float = 0.75) -> List[Dict]:
        if not prompts:
            return []
        embeddings = [embed_text(p[:1500]) for p in prompts[:30]]
        assigned = [-1] * len(embeddings)
        cluster_id = 0
        for i in range(len(embeddings)):
            if assigned[i] >= 0:
                continue
            assigned[i] = cluster_id
            for j in range(i + 1, len(embeddings)):
                if assigned[j] < 0 and cosine_similarity(embeddings[i], embeddings[j]) >= threshold:
                    assigned[j] = cluster_id
            cluster_id += 1
        clusters: Dict[int, List] = defaultdict(list)
        for idx, cid in enumerate(assigned):
            clusters[cid].append({"index": idx, "preview": prompts[idx][:80]})
        return [{"cluster_id": k, "size": len(v), "prompts": v} for k, v in clusters.items() if len(v) > 1]

    def analyze_tenant(self, tenant_id: str) -> Dict[str, Any]:
        prompts_data = self.inventory.list_prompts(tenant_id, 30, "frequency")
        previews = [p.get("preview", "") for p in prompts_data if p.get("preview")]
        return {
            "duplicates": self.find_exact_duplicates(previews),
            "similar_pairs": self.find_similar_pairs(previews),
            "clusters": self.cluster(previews),
        }
