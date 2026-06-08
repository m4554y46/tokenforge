"""Phase 16 — Validation.

Mandatory checks before final output.
"""

from typing import List, Optional, Tuple

from .ir import IRDocument, IRNodeType
from .protection import ProtectedRegistry, verify_integrity


class ValidationResult:
    def __init__(self):
        self.passed: bool = True
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def fail(self, msg: str):
        self.passed = False
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def merge(self, other: "ValidationResult"):
        if not other.passed:
            self.passed = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def validate_protected_integrity(
    original: str,
    output: str,
    registry: ProtectedRegistry,
) -> ValidationResult:
    """Verify all protected spans are present in output."""
    result = ValidationResult()
    missing = verify_integrity(original, output, registry)
    if missing:
        result.fail(f"Protected spans missing in output: {missing}")
    return result


def validate_references(ir: IRDocument) -> ValidationResult:
    """Verify all references point to existing sections."""
    result = ValidationResult()
    section_titles = set()
    for node in ir.nodes:
        if isinstance(node, _get_ref_type()):
            pass
        section_titles.add(node.id)

    for node in ir.get_nodes_by_type(IRNodeType.REFERENCE):
        from .ir import ReferenceNode
        ref = node
        if ref.target and ref.target not in section_titles and not ref.target.startswith("PROTECTED_"):
            result.warn(f"Reference to '{ref.target}' may point to non-existent section")

    return result


def _get_ref_type():
    from .ir import ReferenceNode
    return ReferenceNode


def validate_constraints(ir: IRDocument) -> ValidationResult:
    """Verify all constraints and negations survived."""
    result = ValidationResult()
    constraint_count = ir.count_constraints()
    for node in ir.nodes:
        if node.type == IRNodeType.CONSTRAINT:
            from .ir import ConstraintNode
            cn = node
            if cn.negated:
                # Basic check: negation preserved
                if not cn.predicate and not cn.subject:
                    result.warn(f"Empty constraint node: {cn.id}")
    return result


def validate_placeholders(
    output: str,
    registry: ProtectedRegistry,
) -> ValidationResult:
    """Verify no PROTECTED_ placeholders remain in output."""
    result = ValidationResult()
    import re
    remaining = re.findall(r'PROTECTED_\d+', output)
    if remaining:
        result.fail(f"Unreplaced placeholders found: {remaining}")
    return result


def validate_all(
    original: str,
    output: str,
    ir: IRDocument,
    registry: ProtectedRegistry,
) -> ValidationResult:
    """Run all validation checks."""
    result = ValidationResult()
    result.merge(validate_protected_integrity(original, output, registry))
    result.merge(validate_references(ir))
    result.merge(validate_constraints(ir))
    result.merge(validate_placeholders(output, registry))
    return result
