"""Gray Zone Router — Couche 2 du pipeline SPC.

Résout les 5 zones grises via un petit LLM local (Phi-3-mini / Qwen2.5) :
  1. Ambiguïté sémantique
  2. Protection intelligente (keep/remove contextual)
  3. Validation causale (relations préservées ?)
  4. Registre / Ton
  5. Ré-expansion minimale

Le LLM n'est appelé que si nécessaire (router + cache).
"""

import hashlib
import json
import logging
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

from .llama_cpp import LlamaCpp

logger = logging.getLogger(__name__)


class GrayZone(Enum):
    AMBIGUITY = "ambiguity"
    FINE_PROTECTION = "fine_protection"
    CAUSAL_VALIDATION = "causal_validation"
    REGISTER = "register"
    REEXPANSION = "reexpansion"


ZONE_PROMPTS: Dict[GrayZone, Dict[str, Any]] = {
    GrayZone.AMBIGUITY: {
        "system": (
            "You are an ambiguity resolver for a prompt compression pipeline. "
            "Given a compressed sentence, determine if it has semantic ambiguity. "
            'Reply with exactly one word: "CLEAR" or "AMBIGUOUS".'
        ),
        "prompt": "### Input\n{text}\n\n### Output",
        "max_tokens": 8,
        "temperature": 0.0,
        "stop": ["\n"],
    },
    GrayZone.FINE_PROTECTION: {
        "system": (
            "You are a text classifier for a compression pipeline. "
            "Given a chunk of text, classify each word as KEEP or REMOVE. "
            "KEEP = word carries essential meaning or context. "
            "REMOVE = word can be safely dropped without losing meaning. "
            "Reply as a JSON list of {word, label}."
        ),
        "prompt": "### Input\n{text}\n\n### Output",
        "max_tokens": 256,
        "temperature": 0.1,
        "stop": [],
    },
    GrayZone.CAUSAL_VALIDATION: {
        "system": (
            "You are a quality validator for a text compression system. "
            "Compare original and compressed text. "
            "If the causal/temporal relations in the original are preserved in the compressed version, "
            'reply "PASS". If any relation is inverted or lost, reply "FAIL: {description}". '
            "Be strict but fair: minor word removal is acceptable, meaning inversion is not."
        ),
        "prompt": "### Original\n{original}\n\n### Compressed\n{compressed}\n\n### Output",
        "max_tokens": 64,
        "temperature": 0.0,
        "stop": ["\n"],
    },
    GrayZone.REGISTER: {
        "system": (
            "Classify the register/tone of this text as one of:\n"
            "- FORMAL (professional, polite, administrative)\n"
            "- NEUTRAL (informative, objective)\n"
            "- INFORMAL (casual, conversational)\n"
            "- URGENT (imperative, time-sensitive)\n"
            "- TECHNICAL (jargon, precise)\n"
            "Reply with just the label."
        ),
        "prompt": "### Input\n{text}\n\n### Output",
        "max_tokens": 8,
        "temperature": 0.0,
        "stop": ["\n"],
    },
    GrayZone.REEXPANSION: {
        "system": (
            "You are a text restorer. Given a highly compressed prompt, expand it slightly "
            "to make it grammatically complete and unambiguous, adding at most 20% more tokens. "
            "Preserve all original information. Do NOT add new instructions or content."
        ),
        "prompt": "### Compressed\n{text}\n\n### Output",
        "max_tokens": 512,
        "temperature": 0.2,
        "stop": [],
    },
}


@dataclass
class UserProfile:
    user_id: str = ""
    preferred_register: str = "neutral"
    compression_threshold: float = 0.50
    jargon_words: set = field(default_factory=set)
    history: List[Dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "preferred_register": self.preferred_register,
            "compression_threshold": self.compression_threshold,
            "jargon_words": list(self.jargon_words),
        }


class GrayZoneRouter:
    """Routes compressed text through LLM gray zone resolution."""

    def __init__(self, llm: Optional[LlamaCpp] = None):
        self.llm = llm
        self._cache: OrderedDict = OrderedDict()
        self._cache_max = 1000
        self._cache_ttl = 3600
        self._user_profiles: Dict[str, UserProfile] = {}

    def is_available(self) -> bool:
        return self.llm is not None and self.llm.is_available()

    def should_refine(
        self,
        text: str,
        compression_ratio: float,
        text_type: str = "",
        zone: Optional[GrayZone] = None,
    ) -> bool:
        """Determine if LLM refinement is beneficial."""
        if not self.is_available():
            return False
        if not text or len(text) < 20:
            return False
        ratio = compression_ratio
        if zone == GrayZone.CAUSAL_VALIDATION:
            return ratio >= 0.40
        if zone == GrayZone.REGISTER:
            return True
        if zone == GrayZone.REEXPANSION:
            return ratio >= 0.60
        if zone == GrayZone.AMBIGUITY:
            return ratio >= 0.50 and len(text.split()) > 5
        if zone == GrayZone.FINE_PROTECTION:
            return ratio >= 0.55
        return ratio >= 0.50

    def refine(
        self,
        text: str,
        original: str = "",
        zone: GrayZone = GrayZone.AMBIGUITY,
        user_id: str = "",
        force: bool = False,
    ) -> Tuple[str, dict]:
        """Run LLM refinement for a specific gray zone.

        Returns:
            (refined_text, metadata_dict)
        """
        meta = {"zone": zone.value, "llm_called": False, "error": None}
        if not text:
            return text, meta
        if not self.is_available():
            meta["error"] = "LLM not available"
            return text, meta

        profile = self._user_profiles.get(user_id)
        ratio = self._estimate_ratio(text, original) if original else 0.50
        if not force and not self.should_refine(text, ratio, zone=zone):
            meta["llm_called"] = False
            return text, meta

        cache_key = self._cache_key(text, original, zone, user_id)
        cached = self._get_cache(cache_key)
        if cached is not None:
            meta["cached"] = True
            return cached, meta

        zone_cfg = ZONE_PROMPTS.get(zone)
        if not zone_cfg:
            meta["error"] = f"Unknown zone: {zone}"
            return text, meta

        # Build prompt — utilise le chat template natif du modèle (Phi-3, Qwen2.5, etc.)
        # Sécurité : remplacer les placeholders directement, pas de .format() sur contenu utilisateur
        user_content = zone_cfg["prompt"]
        user_content = user_content.replace("{text}", text)
        user_content = user_content.replace("{original}", original)
        user_content = user_content.replace("{compressed}", text)
        messages = [
            {"role": "system", "content": zone_cfg["system"]},
            {"role": "user", "content": user_content},
        ]
        result = self.llm.chat(
            messages=messages,
            max_tokens=zone_cfg["max_tokens"],
            temperature=zone_cfg["temperature"],
            stop=zone_cfg["stop"],
        )
        if result is None:
            meta["error"] = "LLM returned None"
            return text, meta

        meta["llm_called"] = True
        refined, extra_meta = self._parse_refinement(text, result, zone)
        meta.update(extra_meta)
        self._set_cache(cache_key, refined)
        return refined, meta

    def _parse_refinement(self, text: str, llm_output: str, zone: GrayZone) -> Tuple[str, dict]:
        extra = {}
        if zone == GrayZone.AMBIGUITY:
            extra["classification"] = llm_output.strip()
            return text, extra
        if zone == GrayZone.FINE_PROTECTION:
            return self._apply_fine_protection(text, llm_output), extra
        if zone == GrayZone.CAUSAL_VALIDATION:
            extra["validation"] = llm_output.strip()
            return text, extra
        if zone == GrayZone.REGISTER:
            extra["register"] = llm_output.strip()
            return text, extra
        if zone == GrayZone.REEXPANSION:
            return (llm_output.strip() if len(llm_output) > len(text) * 0.5 else text), extra
        return llm_output.strip(), extra

    def _apply_fine_protection(self, text: str, llm_output: str) -> str:
        """Apply token-level keep/remove labels from LLM output, preserving whitespace."""
        try:
            labels = json.loads(llm_output)
            if isinstance(labels, list):
                remove_words = {item["word"] for item in labels if item.get("label") == "REMOVE"}
                import re
                parts = re.split(r"(\s+)", text)
                kept = [p for p in parts if not p.strip() or p.strip(".,;:!?\"'") not in remove_words]
                return "".join(kept)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        return text

    @staticmethod
    def _estimate_ratio(compressed: str, original: str) -> float:
        o_len = len(original) // 4
        c_len = len(compressed) // 4
        if o_len == 0:
            return 0.0
        return 1.0 - c_len / o_len

    def _cache_key(self, text: str, original: str, zone: GrayZone, user_id: str) -> str:
        raw = f"{text}|{original}|{zone.value}|{user_id}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _get_cache(self, key: str) -> Optional[str]:
        if key in self._cache:
            val, ts = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                self._cache.move_to_end(key)
                return val
            del self._cache[key]
        return None

    def _set_cache(self, key: str, value: str):
        while len(self._cache) >= self._cache_max:
            self._cache.popitem(last=False)
        self._cache[key] = (value, time.time())

    def get_profile(self, user_id: str) -> UserProfile:
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = UserProfile(user_id=user_id)
        return self._user_profiles[user_id]

    def update_profile(self, user_id: str, correction: Dict):
        profile = self.get_profile(user_id)
        profile.history.append(correction)
        if len(profile.history) > 100:
            profile.history = profile.history[-100:]

    def clear_cache(self):
        self._cache.clear()


_router_instance: Optional[GrayZoneRouter] = None


def get_router(llm: Optional[LlamaCpp] = None) -> GrayZoneRouter:
    global _router_instance
    if _router_instance is not None and llm is None:
        return _router_instance
    if _router_instance is None:
        _router_instance = GrayZoneRouter(llm=llm)
    elif llm is not None:
        _router_instance.llm = llm
    return _router_instance
