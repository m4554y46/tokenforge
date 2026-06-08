"""SPC — Semantic Prompt Compiler v2.0.

A local, rule-based semantic compiler that compresses human text
into a denser representation while preserving operational meaning.
Industrial-grade: 6 profiles, 23+ span protection types, discourse analysis,
logical/temporal compression, near-dedup, example reduction.
"""

from .pipeline import SPC
from .profiles import Profile, SAFE, LIGHT, BALANCED, AGGRESSIVE, MAX, INDUSTRIAL
from .ir import (
    IRDocument, IRNode, ConstraintNode, RuleNode, TextNode,
    ReferenceNode, ExampleNode, DiscourseNode,
    Modality, Certainty, Edge
)
from .negation import NegationSpan
from .llmlingua2 import (
    compress_with_llmlingua2,
    compress_json_block,
    get_token_labels,
    reset_model,
    auto_compress,
    detect_text_type,
    TextType,
    CompressionStrategy,
)

__all__ = [
    "SPC",
    "Profile", "SAFE", "LIGHT", "BALANCED", "AGGRESSIVE", "MAX", "INDUSTRIAL",
    "IRDocument", "IRNode", "ConstraintNode", "RuleNode", "TextNode",
    "ReferenceNode", "ExampleNode", "DiscourseNode",
    "Modality", "Certainty", "Edge",
    "NegationSpan",
    "compress_with_llmlingua2",
    "compress_json_block",
    "get_token_labels",
    "reset_model",
    "auto_compress",
    "detect_text_type",
    "TextType",
    "CompressionStrategy",
]
