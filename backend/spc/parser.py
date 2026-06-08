"""Phase 3 — Structural Parsing.

Builds a DocumentTree with node types:
Section, Subsection, Paragraph, List, Table, CodeBlock, Quote, Reference.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional


class NodeType(Enum):
    DOCUMENT = auto()
    SECTION = auto()
    SUBSECTION = auto()
    PARAGRAPH = auto()
    LIST = auto()
    LIST_ITEM = auto()
    TABLE = auto()
    CODE_BLOCK = auto()
    QUOTE = auto()
    REFERENCE = auto()
    HORIZONTAL_RULE = auto()
    RAW_TEXT = auto()


@dataclass
class Node:
    type: NodeType
    content: str = ""
    children: List[Node] = field(default_factory=list)
    level: int = 0
    metadata: dict = field(default_factory=dict)

    def add_child(self, child: Node):
        self.children.append(child)

    def to_text(self, depth: int = 0) -> str:
        prefix = "  " * depth
        result = f"{prefix}[{self.type.name}]"
        if self.content:
            result += f": {self.content[:60]}"
        result += "\n"
        for c in self.children:
            result += c.to_text(depth + 1)
        return result


@dataclass
class DocumentTree:
    root: Node
    metadata: dict = field(default_factory=dict)

    def to_text(self) -> str:
        return self.root.to_text()


# Markdown / plain text section headings
_HEADING = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
_SETEXT_H1 = re.compile(r'^(.+)\n=+\s*$', re.MULTILINE)
_SETEXT_H2 = re.compile(r'^(.+)\n-+\s*$', re.MULTILINE)
_LIST_ITEM = re.compile(r'^(\s*)[-*+]\s+(.+)$', re.MULTILINE)
_ORDERED_LIST = re.compile(r'^(\s*)\d+[.)]\s+(.+)$', re.MULTILINE)
_QUOTE = re.compile(r'^>\s*(.+)$', re.MULTILINE)
_TABLE_ROW = re.compile(r'^\|.+\|$', re.MULTILINE)
_HORIZONTAL = re.compile(r'^(?:[-*_]){3,}\s*$', re.MULTILINE)
_CODE_FENCE_RESIDUAL = re.compile(r'^```[\w]*$|^~~~[\w]*$', re.MULTILINE)
_REFERENCE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')


def parse(text: str) -> DocumentTree:
    """Build a DocumentTree from plain text / Markdown input."""
    root = Node(type=NodeType.DOCUMENT, content="")
    lines = text.split("\n")
    i = 0
    n = len(lines)

    current_section: Optional[Node] = root
    current_subsection: Optional[Node] = None
    in_code_block = False
    in_table = False
    table_rows: List[str] = []

    while i < n:
        line = lines[i]

        # Code fence boundaries
        if _CODE_FENCE_RESIDUAL.match(line) or line.strip().startswith("```") or line.strip().startswith("~~~"):
            if not in_code_block:
                in_code_block = True
                code_lines = [line]
                i += 1
                while i < n and not (lines[i].strip().startswith("```") or lines[i].strip().startswith("~~~")):
                    code_lines.append(lines[i])
                    i += 1
                if i < n:
                    code_lines.append(lines[i])
                node = Node(type=NodeType.CODE_BLOCK, content="\n".join(code_lines))
                _add_to_section(node, current_section, current_subsection)
                in_code_block = False
                i += 1
                continue
            else:
                in_code_block = False
                i += 1
                continue

        if in_code_block:
            i += 1
            continue

        # Section headings
        hm = _HEADING.match(line)
        if hm:
            level = len(hm.group(1))
            title = hm.group(2).strip()
            node = Node(type=NodeType.SECTION if level <= 2 else NodeType.SUBSECTION,
                        content=title, level=level)
            if level == 1:
                root.add_child(node)
                current_section = node
                current_subsection = None
            elif level == 2:
                if current_section:
                    current_section.add_child(node)
                else:
                    root.add_child(node)
                current_subsection = node
            else:
                if current_subsection:
                    current_subsection.add_child(node)
                elif current_section:
                    current_section.add_child(node)
                else:
                    root.add_child(node)
            i += 1
            continue

        # Setext headings (handled after)
        setext_h1 = _SETEXT_H1.match(line)
        if setext_h1 and i + 1 < n:
            title = setext_h1.group(1).strip()
            node = Node(type=NodeType.SECTION, content=title, level=1)
            root.add_child(node)
            current_section = node
            current_subsection = None
            i += 2
            continue

        setext_h2 = _SETEXT_H2.match(line)
        if setext_h2 and i + 1 < n:
            title = setext_h2.group(1).strip()
            node = Node(type=NodeType.SECTION, content=title, level=2)
            if current_section:
                current_section.add_child(node)
            else:
                root.add_child(node)
            current_subsection = node
            i += 2
            continue

        # Horizontal rules
        if _HORIZONTAL.match(line):
            node = Node(type=NodeType.HORIZONTAL_RULE, content=line.strip())
            _add_to_section(node, current_section, current_subsection)
            i += 1
            continue

        # Quotes
        qm = _QUOTE.match(line)
        if qm:
            quote_lines = [qm.group(1)]
            i += 1
            while i < n and _QUOTE.match(lines[i]):
                quote_lines.append(_QUOTE.match(lines[i]).group(1))
                i += 1
            node = Node(type=NodeType.QUOTE, content="\n".join(quote_lines))
            _add_to_section(node, current_section, current_subsection)
            continue

        # Table rows
        if _TABLE_ROW.match(line):
            table_rows.append(line)
            in_table = True
            i += 1
            continue
        elif in_table:
            # End of table
            node = Node(type=NodeType.TABLE, content="\n".join(table_rows))
            _add_to_section(node, current_section, current_subsection)
            table_rows.clear()
            in_table = False
            continue

        # List items
        lm = _LIST_ITEM.match(line)
        if lm:
            indent = len(lm.group(1))
            items = [(indent, lm.group(2))]
            i += 1
            while i < n:
                lm2 = _LIST_ITEM.match(lines[i])
                om2 = _ORDERED_LIST.match(lines[i])
                if lm2 and len(lm2.group(1)) == indent:
                    items.append((indent, lm2.group(2)))
                    i += 1
                elif om2 and len(om2.group(1)) == indent:
                    items.append((indent, om2.group(2)))
                    i += 1
                else:
                    break
            list_content = "\n".join([item[1] for item in items])
            list_node = Node(type=NodeType.LIST, content=list_content)
            for _, item_text in items:
                list_node.add_child(Node(type=NodeType.LIST_ITEM, content=item_text))
            _add_to_section(list_node, current_section, current_subsection)
            continue

        om = _ORDERED_LIST.match(line)
        if om:
            items = [(len(om.group(1)), om.group(2))]
            i += 1
            while i < n:
                om2 = _ORDERED_LIST.match(lines[i])
                lm2 = _LIST_ITEM.match(lines[i])
                if om2:
                    items.append((len(om2.group(1)), om2.group(2)))
                    i += 1
                elif lm2:
                    items.append((len(lm2.group(1)), lm2.group(2)))
                    i += 1
                else:
                    break
            list_content = "\n".join([item[1] for item in items])
            list_node = Node(type=NodeType.LIST, content=list_content)
            for _, item_text in items:
                list_node.add_child(Node(type=NodeType.LIST_ITEM, content=item_text))
            _add_to_section(list_node, current_section, current_subsection)
            continue

        # Empty line
        if not line.strip():
            i += 1
            continue

        # Regular paragraph
        para_lines = [line]
        i += 1
        while i < n and lines[i].strip():
            para_lines.append(lines[i])
            i += 1
        para_node = Node(type=NodeType.PARAGRAPH, content="\n".join(para_lines))
        _add_to_section(para_node, current_section, current_subsection)

    return DocumentTree(root=root)


def _add_to_section(node: Node, section: Optional[Node], subsection: Optional[Node]):
    if subsection:
        subsection.add_child(node)
    elif section:
        section.add_child(node)


def flatten(tree: DocumentTree) -> List[Node]:
    """Flatten the tree to a list of leaf nodes in order."""
    result: List[Node] = []

    def _walk(n: Node):
        if n.children:
            for c in n.children:
                _walk(c)
        else:
            result.append(n)

    _walk(tree.root)
    return result


def extract_text(node: Node) -> str:
    """Recursively extract plain text from a node."""
    if node.children:
        return "\n".join(extract_text(c) for c in node.children)
    return node.content
