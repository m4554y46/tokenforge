"""Discourse Relation Extraction.

Identifies inter-sentence discourse relations (cause-effect, contrast,
condition, elaboration, temporal, exemplification, etc.)
and builds a discourse graph from the IR.
"""

import re
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, field


class DiscourseRelation(str):
    """Discourse relation types."""
    CAUSE = "cause"
    CONSEQUENCE = "consequence"
    CONTRAST = "contrast"
    CONDITION = "condition"
    CONCESSION = "concession"
    PURPOSE = "purpose"
    ADDITION = "addition"
    EXEMPLIFICATION = "exemplification"
    SUMMARY = "summary"
    TEMPORAL = "temporal"
    ELABORATION = "elaboration"
    SEQUENCE = "sequence"
    CONJUNCTION = "conjunction"
    DISJUNCTION = "disjunction"


@dataclass
class DiscourseSpan:
    relation: str
    marker: str
    anchor_sentence: int  # sentence index (0-based)
    target_sentence: Optional[int] = None  # sentence index, or None for presentational


@dataclass
class DiscourseGraph:
    """Graph of discourse relations between IR nodes."""
    edges: List[Tuple[str, str, str]] = field(default_factory=list)  # (from_id, to_id, relation)


# ── English discourse patterns ───────────────────────────────
_EN_DISCOURSE_PATTERNS: Dict[str, List[str]] = {
    DiscourseRelation.CAUSE: [
        r'\b(because|since)\s+.+',
        r'\b(as)\s+.+',
        r'\bdue\s+to\b',
        r'\bowing\s+to\b',
        r'\bas\s+a\s+result\s+of\b',
    ],
    DiscourseRelation.CONSEQUENCE: [
        r'\b(therefore|thus|hence|consequently)\b',
        r'\bas\s+a\s+result\b',
        r'\bas\s+a\s+consequence\b',
        r'\baccordingly\b',
        r'\bfor\s+this\s+reason\b',
        r'\bthat\s+is\s+why\b',
        r'\bleading\s+to\b',
        r'\bwhich\s+(?:is\s+)?why\b',
    ],
    DiscourseRelation.CONTRAST: [
        r'\b(however|nevertheless|nonetheless)\b',
        r'\bbut\b',
        r'\b(although|though|even\s+though)\b',
        r'\bdespite\b',
        r'\bin\s+spite\s+of\b',
        r'\bwhereas\b',
        r'\bwhile\b',
        r'\bon\s+the\s+other\s+hand\b',
        r'\bconversely\b',
        r'\bin\s+contrast\b',
        r'\b(yet|still)\b',
    ],
    DiscourseRelation.CONDITION: [
        r'\bif\b',
        r'\b(provided|providing)\s+that\b',
        r'\bas\s+long\s+as\b',
        r'\bon\s+condition\s+that\b',
        r'\bunless\b',
        r'\bin\s+case\b',
        r'\bin\s+the\s+event\s+that\b',
    ],
    DiscourseRelation.CONCESSION: [
        r'\b(although|though|even\s+though)\b',
        r'\bdespite\s+the\s+fact\s+that\b',
        r'\bin\s+spite\s+of\b',
        r'\bwhile\s+it\s+is\s+true\b',
        r'\badmittedly\b',
    ],
    DiscourseRelation.PURPOSE: [
        r'\bin\s+order\s+to\b',
        r'\bso\s+that\b',
        r'\bso\s+as\s+to\b',
        r'\bfor\s+the\s+purpose\s+of\b',
        r'\bwith\s+the\s+aim\s+of\b',
        r'\bdesigned\s+to\b',
        r'\bintended\s+to\b',
    ],
    DiscourseRelation.ADDITION: [
        r'\b(moreover|furthermore)\b',
        r'\bin\s+addition\b',
        r'\badditionally\b',
        r'\bbesides\b',
        r'\bwhat\s+is\s+more\b',
        r'\bnot\s+only\b',
        r'\bas\s+well\s+as\b',
        r'\bfurther\b',
        r'\blikewise\b',
        r'\bsimilarly\b',
        r'\balso\b',
    ],
    DiscourseRelation.EXEMPLIFICATION: [
        r'\bfor\s+example\b',
        r'\bfor\s+instance\b',
        r'\bsuch\s+as\b',
        r'\be\.g\.\b',
        r'\bi\.e\.\b',
        r'\bnamely\b',
        r'\bthat\s+is\b',
        r'\bin\s+particular\b',
        r'\bparticularly\b',
        r'\bspecifically\b',
        r'\bnotably\b',
    ],
    DiscourseRelation.SUMMARY: [
        r'\bin\s+summary\b',
        r'\bto\s+summarize\b',
        r'\bin\s+conclusion\b',
        r'\boverall\b',
        r'\bto\s+conclude\b',
        r'\bin\s+short\b',
        r'\bbriefly\b',
        r'\bin\s+brief\b',
        r'\bsumming\s+up\b',
        r'\bultimately\b',
    ],
    DiscourseRelation.TEMPORAL: [
        r'\b(before|after)\b',
        r'\b(while|during)\b',
        r'\bwhen\b',
        r'\bas\s+soon\s+as\b',
        r'\bonce\b',
        r'\buntil\b',
        r'\bsince\b',
        r'\bprior\s+to\b',
        r'\bsubsequently\b',
        r'\bafterwards\b',
        r'\bmeanwhile\b',
        r'\bat\s+the\s+same\s+time\b',
        r'\b(firstly|secondly|finally)\b',
        r'\bthen\b',
        r'\bnext\b',
    ],
    DiscourseRelation.ELABORATION: [
        r'\bin\s+other\s+words\b',
        r'\bto\s+put\s+it\s+another\s+way\b',
        r'\bmore\s+specifically\b',
        r'\bto\s+be\s+more\s+precise\b',
        r'\bin\s+particular\b',
    ],
    DiscourseRelation.DISJUNCTION: [
        r'\b(or|either|alternatively)\b',
    ],
    DiscourseRelation.CONJUNCTION: [
        r'\b(and|both|as\s+well\s+as)\b',
        r'\bnot\s+only\s+.*\s+but\s+also\b',
    ],
}


# Precompiled patterns (compiled once at module load)
_EN_PATTERNS_COMPILED = {
    rel: [re.compile(p, re.I) for p in pats]
    for rel, pats in _EN_DISCOURSE_PATTERNS.items()
}


def detect_discourse_relations(
    sentences: List[str],
    lang: str = "en"
) -> List[DiscourseSpan]:
    """Detect discourse relations between consecutive/related sentences.

    Args:
        sentences: list of sentence strings
        lang: 'en' or 'fr'

    Returns:
        list of DiscourseSpan objects
    """
    patterns = _EN_PATTERNS_COMPILED  # precompiled at module load
    spans = []

    for i, sent in enumerate(sentences):
        for relation, pat_list in patterns.items():
            for pat in pat_list:
                m = pat.search(sent)
                if m:
                    # Determine target: next sentence for forward-looking,
                    # previous for backward-looking
                    if relation in ("cause", "condition", "purpose", "temporal"):
                        target = i + 1 if i + 1 < len(sentences) else None
                    elif relation in ("consequence", "summary"):
                        target = i - 1 if i > 0 else None
                    else:
                        target = None  # presentational or ambiguous

                    spans.append(DiscourseSpan(
                        relation=relation,
                        marker=m.group(0),
                        anchor_sentence=i,
                        target_sentence=target,
                    ))
                    break  # first match per sentence per relation type

    return spans


def build_discourse_graph(
    ir_nodes: List,
    sentences: List[str],
    spans: List[DiscourseSpan],
) -> DiscourseGraph:
    """Build a discourse graph connecting IR nodes."""
    graph = DiscourseGraph()

    for span in spans:
        # Map sentence indices to node IDs
        from_node = f"sent_{span.anchor_sentence}"
        if span.target_sentence is not None:
            to_node = f"sent_{span.target_sentence}"
            graph.edges.append((from_node, to_node, span.relation))

    return graph
