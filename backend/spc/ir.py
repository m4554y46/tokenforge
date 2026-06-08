"""Phase 4 — Intermediate Representation (IR).

Enhanced schema with discourse relations, certainty, hedging,
epistemic stance, and richer edge types.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any, Union


class IRNodeType(str, Enum):
    TEXT = "TextNode"
    CONSTRAINT = "ConstraintNode"
    RULE = "RuleNode"
    EXAMPLE = "ExampleNode"
    REFERENCE = "ReferenceNode"
    DISCOURSE = "DiscourseNode"


class Modality(str, Enum):
    MUST = "MUST"
    MUST_NOT = "MUST_NOT"
    SHOULD = "SHOULD"
    SHOULD_NOT = "SHOULD_NOT"
    MAY = "MAY"
    FORBIDDEN = "FORBIDDEN"


class Certainty(str, Enum):
    CERTAIN = "certain"
    SPECULATIVE = "speculative"
    HEDGED = "hedged"
    NEUTRAL = "neutral"


@dataclass
class Edge:
    from_id: str
    to_id: str
    relation: str  # "depends_on", "contradicts", "supports", "example_of",
                    # "causes", "entails", "conditions", "contrasts",
                    # "elaborates", "summarizes", "sequences"


@dataclass
class ProtectedRef:
    id: str
    original: str
    type: str


@dataclass
class IRNode:
    id: str
    type: IRNodeType
    source_span: Optional[List[int]] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d


@dataclass
class TextNode(IRNode):
    content: str = ""
    is_protected: bool = False
    certainty: Certainty = Certainty.NEUTRAL
    discourse_markers: List[str] = field(default_factory=list)

    def __init__(self, id: str, content: str = "", is_protected: bool = False,
                 certainty: Certainty = Certainty.NEUTRAL,
                 discourse_markers: Optional[List[str]] = None,
                 source_span: Optional[List[int]] = None):
        super().__init__(id=id, type=IRNodeType.TEXT, source_span=source_span)
        self.content = content
        self.is_protected = is_protected
        self.certainty = certainty
        self.discourse_markers = discourse_markers or []


@dataclass
class ConstraintNode(IRNode):
    modality: Modality = Modality.MUST
    subject: str = ""
    predicate: str = ""
    negated: bool = False
    conditions: List[str] = field(default_factory=list)
    certainty: Certainty = Certainty.NEUTRAL
    discourse_relation: str = ""

    def __init__(self, id: str, modality: Modality = Modality.MUST,
                 subject: str = "", predicate: str = "", negated: bool = False,
                 conditions: Optional[List[str]] = None,
                 certainty: Certainty = Certainty.NEUTRAL,
                 discourse_relation: str = "",
                 source_span: Optional[List[int]] = None):
        super().__init__(id=id, type=IRNodeType.CONSTRAINT, source_span=source_span)
        self.modality = modality
        self.subject = subject
        self.predicate = predicate
        self.negated = negated
        self.conditions = conditions or []
        self.certainty = certainty
        self.discourse_relation = discourse_relation


@dataclass
class RuleNode(IRNode):
    expression: str = ""
    original_text: str = ""

    def __init__(self, id: str, expression: str = "", original_text: str = "",
                 source_span: Optional[List[int]] = None):
        super().__init__(id=id, type=IRNodeType.RULE, source_span=source_span)
        self.expression = expression
        self.original_text = original_text


@dataclass
class ExampleNode(IRNode):
    content: str = ""
    covers: List[str] = field(default_factory=list)

    def __init__(self, id: str, content: str = "", covers: Optional[List[str]] = None,
                 source_span: Optional[List[int]] = None):
        super().__init__(id=id, type=IRNodeType.EXAMPLE, source_span=source_span)
        self.content = content
        self.covers = covers or []


@dataclass
class ReferenceNode(IRNode):
    target: str = ""
    reference_type: str = "section"

    def __init__(self, id: str, target: str = "", reference_type: str = "section",
                 source_span: Optional[List[int]] = None):
        super().__init__(id=id, type=IRNodeType.REFERENCE, source_span=source_span)
        self.target = target
        self.reference_type = reference_type


@dataclass
class DiscourseNode(IRNode):
    relation: str = ""
    marker: str = ""
    anchor_id: str = ""
    target_id: str = ""

    def __init__(self, id: str, relation: str = "", marker: str = "",
                 anchor_id: str = "", target_id: str = "",
                 source_span: Optional[List[int]] = None):
        super().__init__(id=id, type=IRNodeType.DISCOURSE, source_span=source_span)
        self.relation = relation
        self.marker = marker
        self.anchor_id = anchor_id
        self.target_id = target_id


@dataclass
class IRDocument:
    version: str = "2.0"
    language: str = "en"
    nodes: List[IRNode] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    protected_refs: List[ProtectedRef] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    _node_counter: int = 0

    def add_node(self, node: IRNode):
        self.nodes.append(node)

    def add_edge(self, from_id: str, to_id: str, relation: str = "depends_on"):
        self.edges.append(Edge(from_id=from_id, to_id=to_id, relation=relation))

    def add_protected_ref(self, pid: str, original: str, ptype: str):
        self.protected_refs.append(ProtectedRef(id=pid, original=original, type=ptype))

    def next_id(self) -> str:
        self._node_counter += 1
        return f"node_{self._node_counter}"

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "language": self.language,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [asdict(e) for e in self.edges],
            "protected_refs": [asdict(r) for r in self.protected_refs],
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        import json
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> IRDocument:
        doc = cls(version=data.get("version", "2.0"), language=data.get("language", "en"))
        for nd in data.get("nodes", []):
            nt = nd["type"]
            if nt == "TextNode":
                node = TextNode(**{k: v for k, v in nd.items() if k != "type"})
            elif nt == "ConstraintNode":
                d = {k: v for k, v in nd.items() if k != "type"}
                if isinstance(d.get("modality"), str):
                    d["modality"] = Modality(d["modality"])
                if isinstance(d.get("certainty"), str):
                    d["certainty"] = Certainty(d["certainty"])
                node = ConstraintNode(**d)
            elif nt == "RuleNode":
                node = RuleNode(**{k: v for k, v in nd.items() if k != "type"})
            elif nt == "ExampleNode":
                node = ExampleNode(**{k: v for k, v in nd.items() if k != "type"})
            elif nt == "ReferenceNode":
                node = ReferenceNode(**{k: v for k, v in nd.items() if k != "type"})
            elif nt == "DiscourseNode":
                node = DiscourseNode(**{k: v for k, v in nd.items() if k != "type"})
            else:
                continue
            doc.nodes.append(node)
        for ed in data.get("edges", []):
            doc.edges.append(Edge(**ed))
        for rd in data.get("protected_refs", []):
            doc.protected_refs.append(ProtectedRef(**rd))
        doc.metadata = data.get("metadata", {})
        return doc

    def get_nodes_by_type(self, ntype: IRNodeType) -> List[IRNode]:
        return [n for n in self.nodes if n.type == ntype]

    def count_constraints(self) -> int:
        return len(self.get_nodes_by_type(IRNodeType.CONSTRAINT))
