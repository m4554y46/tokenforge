"""SPC — Semantic Prompt Compiler Pipeline.

Orchestrates all phases: ingestion → protection → parse → IR → constraints
→ negation → dedup → discourse → structural → logical → temporal
→ example reduction → reconstruction → validation → metrics.
v2.0 — Industrial-grade semantic compiler.
"""

import sys
import logging
from dataclasses import dataclass
from typing import Optional, List

from .ingestion import ingest, CanonicalDocument, sniff_format, detect_language, EXTENSION_MAP
from .protection import protect, reinject, ProtectedRegistry
from .parser import parse, DocumentTree, flatten
from .ir import IRDocument, IRNodeType, TextNode, ConstraintNode, DiscourseNode, Modality, Certainty
from .constraint import extract_constraints, detect_epistemic, detect_discourse
from .negation import has_negation, mark_negated, unmark_negated, resolve_scope, consolidate_negations
from .dedup import dedup_exact, dedup_near
from .discourse import detect_discourse_relations, DiscourseSpan
from .structural import compress_structure, compress_logical, compress_temporal
from .lexical import compress_lexical
from .example_reducer import reduce_examples
from .chunk_semantic import compress_with_semantic_chunking
from .quality import validate_quality as validate_quality_fn
from .llmlingua2 import auto_compress, compress_with_llmlingua2, compress_json_block, get_token_labels, TextType
from .reconstruction import reconstruct
from .validator import validate_all, ValidationResult
from .metrics import measure, Timer, TokenMetrics
from .profiles import Profile, get_profile, SAFE, LIGHT, BALANCED, AGGRESSIVE, MAX, INDUSTRIAL

logger = logging.getLogger(__name__)


@dataclass
class SPCResult:
    original: str = ""
    compressed: str = ""
    ir: Optional[IRDocument] = None
    metrics: Optional[TokenMetrics] = None
    validation: Optional[ValidationResult] = None
    profile: str = "safe"
    fallback: bool = False
    error: Optional[str] = None
    intermediate: Optional[dict] = None  # debug info


class SPC:
    """Semantic Prompt Compiler — main entry point. v2.0"""

    def __init__(self, profile: Profile = None, cost_per_1k: float = 0.0):
        self.profile = profile or SAFE
        self.cost_per_1k = cost_per_1k
        self.registry = ProtectedRegistry()
        self.ir = IRDocument()
        self._lang = "en"
        self._intermediate = {}

    def compile(self, text: str, source_path: Optional[str] = None,
                lang: Optional[str] = None) -> SPCResult:
        """Run the full SPC pipeline on input text."""
        timer = Timer()
        result = SPCResult(original=text, profile=self.profile.name)

        try:
            with timer:
                phases = self.profile.phases
                current = text

                # ── Phase 1: Ingestion ──────────────────────────────
                if "ingestion" in phases:
                    doc = ingest(current, source_path)
                    current = doc.text
                    self._lang = doc.language
                    self._intermediate["detected_format"] = doc.detected_format
                else:
                    self._lang = detect_language(current)
                    self._intermediate["detected_format"] = sniff_format(current)

                # Override language if specified
                if lang:
                    self._lang = lang

                self._intermediate["lang"] = self._lang

                # ── Phase 2: Protection ─────────────────────────────
                if "protection" in phases:
                    self.registry.reset()
                    current = protect(current, self.registry)
                    self._intermediate["protected"] = current
                    self._intermediate["protected_count"] = len(self.registry)

                # ── Phase 3: Semantic chunk filter ──────────────────
                if "semantic_chunk" in phases and self.profile.name in ("aggressive", "max", "industrial"):
                    _thresholds = {"aggressive": 0.25, "max": 0.20, "industrial": 0.15}
                    _thresh = _thresholds.get(self.profile.name, 0.25)
                    current, chunk_meta = compress_with_semantic_chunking(
                        current,
                        threshold=_thresh,
                        chunk_size=384,
                    )
                    self._intermediate["semantic_chunk"] = chunk_meta

                # ── Phase 4-5: Parsing + IR building ────────────────
                if "parsing" in phases:
                    tree = parse(current)
                    self.ir = self._build_ir(tree, current)
                else:
                    self.ir = IRDocument()
                    self.ir.add_node(TextNode(id="node_1", content=current))
                self.ir.language = self._lang

                # ── Phase 5: Constraint extraction ──────────────────
                if "constraint" in phases:
                    self._extract_and_integrate_constraints(current, self._lang)

                # ── Phase 6: Negation marking ───────────────────────
                if "negation" in phases:
                    # Resolve negation scopes for metadata
                    neg_spans = resolve_scope(current, self._lang)
                    # Consolidate double negations
                    if self.profile.name in ("aggressive", "max", "industrial"):
                        current = consolidate_negations(current, self._lang)
                    # Protect remaining negations
                    current = mark_negated(current)
                    self._intermediate["negation_spans"] = len(neg_spans)

                # ── Phase 7: Exact dedup ────────────────────────────
                if "exact_dedup" in phases:
                    current = self._run_exact_dedup(current)

                # ── Phase 8: Near dedup ─────────────────────────────
                if "near_dedup" in phases and len(current) > 200:
                    current = self._run_near_dedup(current)

                # ── Phase 9: Discourse extraction ───────────────────
                if "discourse" in phases:
                    self._extract_discourse(current)

                # ── Phase 10: Structural ────────────────────────────
                if "structural" in phases:
                    current = compress_structure(current)

                # ── Phase 11: Lexical compression ───────────────────
                if "lexical" in phases:
                    current = compress_lexical(current, self._lang)

                # ── Phase 12: Logical compression ───────────────────
                if "logical" in phases:
                    current = compress_logical(current, self._lang)

                # ── Phase 13: Temporal compression ──────────────────
                if "temporal" in phases:
                    current = compress_temporal(current, self._lang)

                # ── Phase 13: Example reduction ─────────────────────
                if "example_reduction" in phases:
                    current = reduce_examples(current, max_examples=3)

                # ── Phase 14: LLMLingua neural compression (auto-detect engine) ──
                if "llmlingua2" in phases:
                    _rates = {"aggressive": 0.55, "max": 0.45, "industrial": 0.40}
                    _llm_rate = _rates.get(self.profile.name, 0.5)
                    _fmt = self._intermediate.get("detected_format", "txt")
                    _current, _labels, _type = auto_compress(
                        text=current,
                        lang=self._lang,
                        fmt=_fmt,
                        profile_rate=_llm_rate,
                        force_tokens=["\n"],
                        return_word_label=False,
                    )
                    if _labels:
                        self._intermediate["llmlingua2"] = _labels
                    self._intermediate["llmlingua2_type"] = _type.value
                    if _current:
                        current = _current

                # ── Remove negation markers ─────────────────────────
                current = unmark_negated(current)

                # ── Reinject protected spans ────────────────────────
                current = reinject(current, self.registry)

                result.compressed = current
                result.ir = self.ir

                # ── Phase 15: Validation ────────────────────────────
                if "validation" in phases:
                    vresult = validate_all(text, current, self.ir, self.registry)
                    result.validation = vresult
                    if not vresult.passed:
                        logger.warning(f"Validation warnings: {vresult.errors}")
                        # Re-inject any missing protected spans to salvage output
                        current = reinject(current, self.registry)
                        result.compressed = current
                        result.fallback = True

                # ── Phase 17: Quality validation ─────────────────────
                if "quality" in phases:
                    quality_result = validate_quality_fn(
                        text, result.compressed, self.registry,
                        min_similarity=0.55 if self.profile.name == "industrial" else 0.60,
                    )
                    self._intermediate["quality"] = quality_result
                    if not quality_result["passed"]:
                        logger.warning("Quality check: %s", "; ".join(quality_result["errors"]))
                        result.fallback = True

                # ── Phase 18-19: Metrics ────────────────────────────
                if "metrics" in phases:
                    result.metrics = measure(text, result.compressed, self.cost_per_1k)
                    result.metrics.elapsed_ms = timer.ms()

                result.intermediate = self._intermediate if self._intermediate else None

        except Exception as e:
            logger.error(f"SPC pipeline error: {e}", exc_info=True)
            result.compressed = text
            result.fallback = True
            result.error = str(e)
            if "metrics" in phases:
                result.metrics = measure(text, text, self.cost_per_1k)
                result.metrics.elapsed_ms = timer.ms()

        return result

    def _build_ir(self, tree: DocumentTree, text: str) -> IRDocument:
        """Build IRDocument from a DocumentTree."""
        ir = IRDocument()
        ir.metadata["input_tokens"] = len(text) // 4
        ir.metadata["detected_format"] = sniff_format(text)

        nodes = flatten(tree)
        for i, node in enumerate(nodes):
            content = node.content.strip()
            if not content:
                continue
            nid = ir.next_id()
            span = [text.find(content[:20]), text.find(content[:20]) + len(content)]
            if span[0] < 0:
                span = [0, len(content)]
            ir.add_node(TextNode(id=nid, content=content, source_span=span))

        return ir

    def _extract_and_integrate_constraints(self, text: str, lang: str = "en"):
        """Extract constraints from text and add them to the IR."""
        lang = getattr(self, '_lang', lang)
        constraints = extract_constraints(text, lang=lang)
        for (modality, subject, predicate, negated, original_sent,
             epistemic, discourse_markers) in constraints:
            nid = self.ir.next_id()
            certainty = Certainty.NEUTRAL
            if epistemic == "certain":
                certainty = Certainty.CERTAIN
            elif epistemic == "speculative":
                certainty = Certainty.SPECULATIVE
            elif epistemic == "hedged":
                certainty = Certainty.HEDGED

            disc_rel = discourse_markers[0][0] if discourse_markers else ""

            node = ConstraintNode(
                id=nid,
                modality=modality,
                subject=subject,
                predicate=predicate,
                negated=negated,
                certainty=certainty,
                discourse_relation=disc_rel,
            )
            self.ir.add_node(node)

        self.ir.metadata["detected_constraints"] = len(constraints)

    def _extract_discourse(self, text: str):
        """Extract discourse relations and add to IR."""
        sentences = [s.strip() for s in text.replace('\n', ' ').split('.') if s.strip()]
        spans = detect_discourse_relations(sentences, self._lang)

        for span in spans:
            nid = self.ir.next_id()
            anchor_id = f"sent_{span.anchor_sentence}"
            target_id = f"sent_{span.target_sentence}" if span.target_sentence is not None else ""
            node = DiscourseNode(
                id=nid,
                relation=span.relation,
                marker=span.marker,
                anchor_id=anchor_id,
                target_id=target_id,
            )
            self.ir.add_node(node)

        self.ir.metadata["detected_discourse"] = len(spans)

    def _apply_negation_protection(self, text: str) -> str:
        return mark_negated(text)

    def _run_exact_dedup(self, text: str) -> str:
        paragraphs = text.split("\n\n")
        deduped, counts = dedup_exact(paragraphs)
        self._intermediate["exact_dedup_removed"] = len(paragraphs) - len(deduped)
        return "\n\n".join(deduped)

    def _run_near_dedup(self, text: str) -> str:
        paragraphs = text.split("\n\n")
        if len(paragraphs) < 5:
            return text
        # Preserve paragraphs containing PROTECTED_ IDs (must not be removed)
        kept_set = {i for i, p in enumerate(paragraphs) if "PROTECTED_" in p}
        idx_to_pos = {}
        texts_to_dedup = []
        for i, p in enumerate(paragraphs):
            if i not in kept_set:
                idx_to_pos[i] = len(texts_to_dedup)
                texts_to_dedup.append(p)
        if len(texts_to_dedup) < 5:
            return text
        deduped_texts, dups = dedup_near(texts_to_dedup, threshold=0.85)
        result = []
        for i in range(len(paragraphs)):
            if i in kept_set:
                result.append(paragraphs[i])
            elif i in idx_to_pos:
                pos = idx_to_pos[i]
                if pos < len(deduped_texts):
                    result.append(deduped_texts[pos])
        self._intermediate["near_dedup_removed"] = len(texts_to_dedup) - len(deduped_texts)
        self._intermediate["near_dedup_pairs"] = len(dups)
        return "\n\n".join(result)

    def reset(self):
        self.registry = ProtectedRegistry()
        self.ir = IRDocument()
        self._intermediate = {}
