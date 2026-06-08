"""Execution Profiles for SPC.

Six industrial-grade profiles with granular phase control.
"""

from dataclasses import dataclass, field
from typing import Set


@dataclass
class Profile:
    name: str
    phases: Set[str] = field(default_factory=set)
    enabled: bool = True
    description: str = ""
    target_reduction: str = ""
    min_tokens: int = 0  # minimum input tokens to activate
    max_tokens: int = 100000  # maximum input tokens


SAFE = Profile(
    name="safe",
    phases={
        "ingestion", "protection", "parsing", "ir_basic",
        "constraint", "negation", "exact_dedup", "structural",
        "reconstruction", "validation", "metrics",
    },
    description="Protection + exact dedup + structural cleanup. Zero semantic loss. Base: rule-based only.",
    target_reduction="10-20%",
)

LIGHT = Profile(
    name="light",
    phases={
        "ingestion", "protection", "parsing", "ir_basic",
        "constraint", "negation", "exact_dedup", "discourse",
        "structural", "reconstruction", "validation", "metrics",
    },
    description="+ Discourse relation tagging. Light logical compression. Base: rule-based only.",
    target_reduction="15-25%",
)

BALANCED = Profile(
    name="balanced",
    phases={
        "ingestion", "protection", "parsing", "ir_full",
        "constraint", "negation", "exact_dedup", "near_dedup",
        "discourse",
        "structural", "lexical", "logical",
        "reconstruction", "validation", "metrics",
    },
    description="+ Near dedup (MinHash 0.85), discourse, lexical + logical compression. Base: rule-based only.",
    target_reduction="25-40%",
)

AGGRESSIVE = Profile(
    name="aggressive",
    phases={
        "ingestion", "protection", "parsing", "ir_full",
        "constraint", "negation", "exact_dedup", "near_dedup",
        "discourse",
        "structural", "lexical", "logical", "temporal",
        "example_reduction", "llmlingua2",
        "reconstruction", "validation", "metrics",
    },
    description="+ Lexical, example reduction, temporal, full logical + neural (KOMPRESS ⤑ LLMLingua-2 fallback).",
    target_reduction="40-60%",
)

MAX = Profile(
    name="max",
    phases={
        "ingestion", "protection", "parsing", "ir_full",
        "constraint", "negation", "exact_dedup", "near_dedup",
        "discourse",
        "structural", "lexical", "logical", "temporal",
        "example_reduction", "llmlingua2",
        "reconstruction", "validation", "metrics",
    },
    description="+ All rule-based + neural token compression (KOMPRESS ⤑ LLMLingua-2 fallback).",
    target_reduction="45-75%",
)

INDUSTRIAL = Profile(
    name="industrial",
    phases={
        "ingestion", "protection", "parsing", "ir_full",
        "constraint", "negation", "exact_dedup", "near_dedup",
        "discourse",
        "structural", "lexical", "logical", "temporal",
        "example_reduction", "llmlingua2",
        "reconstruction", "validation", "metrics",
    },
    description="Production-grade: all compression + neural (KOMPRESS ⤑ LLMLingua-2 fallback).",
    target_reduction="45-75%",
    min_tokens=50,
)

PROFILES = {
    "safe": SAFE,
    "light": LIGHT,
    "balanced": BALANCED,
    "aggressive": AGGRESSIVE,
    "max": MAX,
    "industrial": INDUSTRIAL,
}


def get_profile(name: str) -> Profile:
    """Get profile by name, fallback to SAFE."""
    return PROFILES.get(name.lower(), SAFE)
