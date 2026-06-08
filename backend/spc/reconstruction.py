"""Phase 15 — Reconstruction.

Rebuilds text from IR nodes, reinjects protected spans.
"""

from typing import List, Optional

from .ir import IRDocument, IRNodeType, TextNode, ConstraintNode, RuleNode, ExampleNode, ReferenceNode
from .protection import ProtectedRegistry


def reconstruct(ir: IRDocument, registry: Optional[ProtectedRegistry] = None) -> str:
    """Reconstruct text from IR document. Returns UTF-8 text."""
    parts: List[str] = []

    for node in ir.nodes:
        text = _node_to_text(node)
        if text:
            parts.append(text)

    result = "\n\n".join(parts)

    # Reinject protected spans if registry available
    if registry:
        from .protection import reinject as _reinject
        result = _reinject(result, registry)

    return result


def _node_to_text(node) -> str:
    """Convert a single IR node to text."""
    if isinstance(node, TextNode):
        return node.content

    if isinstance(node, ConstraintNode):
        return _constraint_to_sentence(node)

    if isinstance(node, RuleNode):
        return node.original_text or node.expression

    if isinstance(node, ExampleNode):
        return node.content

    if isinstance(node, ReferenceNode):
        return f"[{node.target}]"

    return ""


def _constraint_to_sentence(node: ConstraintNode) -> str:
    """Convert a ConstraintNode back to a natural language sentence."""
    modal_map = {
        "MUST": "must",
        "MUST_NOT": "must not",
        "SHOULD": "should",
        "SHOULD_NOT": "should not",
        "MAY": "may",
        "FORBIDDEN": "must not",
    }

    modal = modal_map.get(node.modality.value, "must")
    negation = " not" if node.negated and modal == "must" else ""

    conditions = ""
    if node.conditions:
        conditions = f" if {' and '.join(node.conditions)}"

    if node.subject and node.predicate:
        return f"{node.subject} {modal}{negation} {node.predicate}{conditions}."
    elif node.predicate:
        return f"{modal}{negation} {node.predicate}{conditions}."
    else:
        return f"{node.subject} {modal}{negation}{conditions}."
