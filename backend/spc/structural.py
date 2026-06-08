"""Phase 10 — Structural & Logical Compression.

Modes:
  - Structural: decorative rules, heading normalization, whitespace, empty sections
  - Logical: → causal chains (because→∴), conditionals (if→→), contrast (but→↔)
  - Temporal: sequence markers (before→<, after→>)
  - Hierarchy: depth reduction, list flattening
"""

import re
from typing import Dict, List, Set, Tuple

from .parser import Node, NodeType, DocumentTree, parse, flatten

# ═══════════════════════════════════════════════════════════════
# 1. STRUCTURAL — Markup cleanup
# ═══════════════════════════════════════════════════════════════

_HORIZONTAL_RULE = re.compile(r'^[-*_]{3,}\s*$', re.MULTILINE)
_HEADING_DECORATIVE = re.compile(r'^#{1,6}\s+', re.MULTILINE)
_EMPTY_LINES = re.compile(r'\n{3,}')
_TRAILING_WS = re.compile(r'[ \t]+$', re.MULTILINE)


def remove_decorative_rules(text: str) -> str:
    return _HORIZONTAL_RULE.sub('', text)


def normalize_headings(text: str) -> str:
    return _HEADING_DECORATIVE.sub(lambda m: '#' * len(m.group(0).strip()) + ' ', text)


def collapse_whitespace(text: str) -> str:
    text = _EMPTY_LINES.sub('\n\n', text)
    text = _TRAILING_WS.sub('', text)
    return text.strip()


def remove_empty_sections(tree: DocumentTree) -> DocumentTree:
    def _prune(node: Node) -> bool:
        if node.type in (NodeType.SECTION, NodeType.SUBSECTION, NodeType.DOCUMENT):
            node.children = [c for c in node.children if _prune(c)]
            return len(node.children) > 0
        return bool(node.content.strip()) or node.children
    _prune(tree.root)
    return tree


def flatten_lists(tree: DocumentTree) -> DocumentTree:
    def _flatten(node: Node):
        if node.type == NodeType.LIST:
            flat_children = []
            for child in node.children:
                if child.type == NodeType.LIST_ITEM and child.children:
                    _flatten(child)
                    child.content = child.content + '\n' + '\n'.join(
                        extract_text(gc) for gc in child.children if gc.type != NodeType.LIST
                    )
                    child.children = [gc for gc in child.children if gc.type == NodeType.LIST]
                flat_children.append(child)
            node.children = flat_children
        else:
            for child in node.children:
                _flatten(child)
    _flatten(tree.root)
    return tree


def extract_text(node: Node) -> str:
    if node.children:
        return "\n".join(extract_text(c) for c in node.children)
    return node.content


# ═══════════════════════════════════════════════════════════════
# 2. LOGICAL COMPRESSION — Causal chains, conditionals, contrast
# ═══════════════════════════════════════════════════════════════

# Causal: because/since/thus → ∴ (therefore symbol)
_CAUSAL_FORWARD = re.compile(
    r'\b(because|since|as|due\s+to|owing\s+to)\b', re.I
)
_CAUSAL_BACKWARD = re.compile(
    r'\b(therefore|thus|hence|consequently|as\s+a\s+result|'
    r'accordingly|for\s+this\s+reason)\b', re.I
)

# Conditional: if/unless → → (arrow)
_CONDITIONAL = re.compile(
    r'\b(if|provided\s+that|providing\s+that|as\s+long\s+as|'
    r'on\s+condition\s+that|assuming\s+that)\b', re.I
)
_CONDITIONAL_NEG = re.compile(
    r'\b(unless|except\s+when|except\s+if)\b', re.I
)

# Contrast: but/however → ↔
_CONTRAST = re.compile(
    r'\b(however|but|nevertheless|nonetheless|although|though|'
    r'even\s+though|whereas|while|conversely|in\s+contrast)\b', re.I
)

# Addition: moreover/furthermore → +
_ADDITION = re.compile(
    r'\b(moreover|furthermore|in\s+addition|additionally|besides|'
    r'what\s+is\s+more|further|also)\b', re.I
)

# Purpose: in order to → →
_PURPOSE = re.compile(
    r'\b(in\s+order\s+to|so\s+as\s+to|for\s+the\s+purpose\s+of|'
    r'with\s+the\s+aim\s+of)\b', re.I
)

# French equivalents
_FR_CAUSAL_FORWARD = re.compile(
    r'\b(parce\s+que|car|puisque|étant\s+donné\s+que|'
    r'en\s+raison\s+de|grâce\s+à|à\s+cause\s+de)\b', re.I
)
_FR_CAUSAL_BACKWARD = re.compile(
    r'\b(donc|ainsi|par\s+conséquent|en\s+conséquence|'
    r'c\'est\s+pourquoi|de\s+ce\s+fait)\b', re.I
)
_FR_CONDITIONAL = re.compile(
    r'\b(si|à\s+condition\s+que|pourvu\s+que|'
    r'dans\s+l\'hypothèse\s+où|supposé\s+que)\b', re.I
)
_FR_CONDITIONAL_NEG = re.compile(
    r'\b(à\s+moins\s+que|sauf\s+si|excepté\s+si)\b', re.I
)
_FR_CONTRAST = re.compile(
    r'\b(cependant|mais|néanmoins|toutefois|bien\s+que|quoique|'
    r'alors\s+que|tandis\s+que|en\s+revanche|au\s+contraire|'
    r'pourtant|or)\b', re.I
)
_FR_ADDITION = re.compile(
    r'\b(de\s+plus|en\s+outre|par\s+ailleurs|'
    r'de\s+surcroît|également|aussi|en\s+plus)\b', re.I
)
_FR_PURPOSE = re.compile(
    r'\b(afin\s+de|pour\s+que|de\s+sorte\s+que|'
    r'dans\s+le\s+but\s+de|en\s+vue\s+de)\b', re.I
)

# ═══════════════════════════════════════════════════════════════
# 3. TEMPORAL COMPRESSION
# ═══════════════════════════════════════════════════════════════

_TEMPORAL_BEFORE = re.compile(
    r'\b(before|prior\s+to|earlier\s+than|preceding)\b', re.I
)
_TEMPORAL_AFTER = re.compile(
    r'\b(after|following|subsequent\s+to|later\s+than)\b', re.I
)
_TEMPORAL_SIMUL = re.compile(
    r'\b(while|during|meanwhile|simultaneously|at\s+the\s+same\s+time)\b', re.I
)

_FR_TEMPORAL_BEFORE = re.compile(
    r'\b(avant|précédemment|préalablement|antérieurement)\b', re.I
)
_FR_TEMPORAL_AFTER = re.compile(
    r'\b(après|suivant|ultérieurement|postérieurement)\b', re.I
)
_FR_TEMPORAL_SIMUL = re.compile(
    r'\b(pendant|durant|entre-temps|simultanément|en\s+même\s+temps)\b', re.I
)

# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════


def compress_logical(text: str, lang: str = "en") -> str:
    """Apply logical compression — safe English short forms, no math symbols."""
    if lang == "en":
        text = _CAUSAL_FORWARD.sub("as", text)
        text = _CAUSAL_BACKWARD.sub("so", text)
        text = _CONDITIONAL.sub("if", text)
        text = _CONDITIONAL_NEG.sub("unless", text)
        text = _CONTRAST.sub("but", text)
        text = _ADDITION.sub("also", text)
        text = _PURPOSE.sub("to", text)
    else:
        text = _FR_CAUSAL_FORWARD.sub("car", text)
        text = _FR_CAUSAL_BACKWARD.sub("donc", text)
        text = _FR_CONDITIONAL.sub("si", text)
        text = _FR_CONDITIONAL_NEG.sub("sauf si", text)
        text = _FR_CONTRAST.sub("mais", text)
        text = _FR_ADDITION.sub("aussi", text)
        text = _FR_PURPOSE.sub("pour", text)
    return text


def compress_temporal(text: str, lang: str = "en") -> str:
    """Temporal compression — minimal. Just shortens verbose temporal phrases."""
    if lang == "en":
        text = _TEMPORAL_SIMUL.sub("as", text)
    else:
        text = _FR_TEMPORAL_SIMUL.sub("comme", text)
    return text


def compress_structure(text: str) -> str:
    """Apply structural passes only."""
    text = remove_decorative_rules(text)
    text = normalize_headings(text)
    text = collapse_whitespace(text)
    return text


def compress_structure_and_logic(text: str, lang: str = "en",
                                  enable_logical: bool = True,
                                  enable_temporal: bool = True) -> str:
    """Full structural + logical + temporal compression."""
    text = compress_structure(text)
    if enable_logical:
        text = compress_logical(text, lang)
    if enable_temporal:
        text = compress_temporal(text, lang)
    return text
