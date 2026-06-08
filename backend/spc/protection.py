"""Phase 2 — Protection.

Replaces protected spans with placeholders PROTECTED_{id}.
23+ span types: code, JSON, URLs, emails, dates, currencies, units,
legal refs, UUIDs, hashes, paths, placeholders, quotes, HTML/XML tags,
semver, IP addresses, hex colors, math notation, chemical formulas,
coordinates, percentages, time ranges, social media handles, HTML entities.
"""

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ProtectedItem:
    id: str
    original: str
    span: tuple
    type: str


class ProtectedRegistry:
    """Tracks all protected spans and their originals."""

    def __init__(self):
        self._items: List[ProtectedItem] = []
        self._counter: int = 0

    def add(self, original: str, span: tuple, ptype: str) -> str:
        self._counter += 1
        pid = f"PROTECTED_{self._counter}"
        self._items.append(ProtectedItem(id=pid, original=original, span=span, type=ptype))
        return pid

    def get(self, pid: str) -> Optional[ProtectedItem]:
        for item in self._items:
            if item.id == pid:
                return item
        return None

    def items(self) -> List[ProtectedItem]:
        return list(self._items)

    def reset(self):
        self._items.clear()
        self._counter = 0

    def __len__(self) -> int:
        return len(self._items)


# ── 1. Code blocks ───────────────────────────────────────────
_CODE_FENCE = re.compile(
    r'(```[\w]*\n.*?\n```|~~~[\w]*\n.*?\n~~~)',
    re.DOTALL
)
_INLINE_CODE = re.compile(r'`[^`\n]+`')

# ── 2. JSON / data structures ────────────────────────────────
_JSON_BLOCK = re.compile(
    r'\{(?:[^{}]|(?:\{[^{}]{0,500}\})){0,500}\}'
)
_YAML_BLOCK = re.compile(r'^---\n.*?\n---', re.MULTILINE | re.DOTALL)
_XML_TAG = re.compile(r'<[^>]+>[^<]*</[^>]+>|<[^>]+/>')

# ── 3. URLs + URIs ───────────────────────────────────────────
_URL = re.compile(r'https?://[^\s<>"\'(){}]+(?<![.,;!?)\]}>])', re.I)
_SEMI_URL = re.compile(r'www\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[^\s<>"\'(){}]*', re.I)

# ── 4. Emails ────────────────────────────────────────────────
_EMAIL = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

# ── 5. Dates + times ─────────────────────────────────────────
_DATE = re.compile(
    r'\b\d{4}-\d{2}-\d{2}\b'
    r'|\b\d{2}/\d{2}/\d{4}\b'
    r'|\b\d{2}\s+[A-Z][a-z]+\s+\d{4}\b'
    r'|\b[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}\b',
    re.I
)
_TIME = re.compile(r'\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\b')
_TIME_RANGE = re.compile(
    r'\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\s*[-–to]{1,3}\s*\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\b'
)
_ISO_DATETIME = re.compile(
    r'\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b'
)

# ── 6. Currencies ────────────────────────────────────────────
_CURRENCY = re.compile(
    r'[\$€£¥₩₽₹₿]\s*\d+(?:[.,]\d+)*(?:\s+(?:USD|EUR|GBP|JPY|CHF|KRW|RUB|INR|BTC))?'
    r'|\b\d+(?:[.,]\d+)*\s*(?:USD|EUR|GBP|JPY|CHF|KRW|RUB|INR|BTC)\b'
)

# ── 7. Units ─────────────────────────────────────────────────
_UNIT = re.compile(
    r'\b\d+(?:\.\d+)?\s*(?:mg|g|kg|ml|l|cl|dl|cm|m|km|'
    r'mm|µm|nm|°[CF]|°[cf]|°C|°F|K|'
    r'V|W|A|Hz|GHz|MHz|kWh|'
    r'mph|km/h|m/s|nmi|kn|'
    r'%|‰|‱|'
    r'px|em|rem|vw|vh|dpi|ppi|'
    r'ms|s|min|h|d|wk|mo|yr|'
    r'GB|MB|TB|kb|mb|gb|tb|'
    r'bps|kbps|mbps|gbps|'
    r'kl|hl|daL|nL|pL|'
    r'mol|M|mM|µM|nM|'
    r'Pa|kPa|MPa|atm|bar|psi|'
    r'N|J|kJ|cal|kcal|eV|'
    r'Bq|Gy|Sv|kat)\b',
    re.I
)

# ── 8. Legal references ──────────────────────────────────────
_LEGAL_REF = re.compile(
    r'\b(?:'
    r'Article|Section|Clause|Paragraph|Part|Title|'
    r'Chapter|Subclause|Subsection|Appendix|Schedule|'
    r'Chapitre|Annexe|Paragraphe|Alinéa|Titre'
    r')\s+\d+(?:\.\d+)*(?:\.\d+)*\b',
    re.I
)

# ── 9. UUIDs ─────────────────────────────────────────────────
_UUID = re.compile(
    r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',
    re.I
)

# ── 10. Hashes ───────────────────────────────────────────────
_HASH = re.compile(r'\b[0-9a-f]{32,64}\b', re.I)
_SHA = re.compile(r'\b(sha[0-9]+:)?[0-9a-f]{40,128}\b', re.I)

# ── 11. File paths ───────────────────────────────────────────
_FILE_PATH = re.compile(
    r'(?:/[^\s/]+){2,}(?:\.[a-zA-Z0-9]+)?'
    r'|(?:[A-Za-z]:(?:\\[^\s\\]+){2,}(?:\.[a-zA-Z0-9]+)?)',
    re.I
)

# ── 12. Placeholders ─────────────────────────────────────────
_PLACEHOLDER = re.compile(
    r'\{\{[^}]+\}\}|\{\w+\}|%[sd]|<\s*\w+\s*/?>|<%\s*\w+\s*%>'
)

# ── 13. Quoted strings ───────────────────────────────────────
_QUOTED = re.compile(
    r'"(?:[^"\\]|\\.)*"'
    r'|(?<!\w)\'(?:[^\'\\]|\\.)*\'(?!\w)'
    r'|«(?:[^»]|\\.)*»'
    r'|「(?:[^」]|\\.)*」'
)

# ── 14. Semantic versioning ──────────────────────────────────
_SEMVER = re.compile(
    r'\bv?\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?(?:\+[a-zA-Z0-9.]+)?\b'
)

# ── 15. IP addresses ─────────────────────────────────────────
_IPV4 = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
_IPV6 = re.compile(
    r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b'
    r'|(?:[0-9a-fA-F]{1,4}:){1,7}:'
    r'|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}'
    r'|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}'
    r'|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}'
    r'|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}'
    r'|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}'
    r'|[0-9a-fA-F]{1,4}:(?::[0-9a-fA-F]{1,4}){1,6}'
    r'|:(?::[0-9a-fA-F]{1,4}){1,7}'
    r'|::'
)
_PORT = re.compile(r':\d{2,5}(?=[\s,;)\]}.!?:;]|$)')

# ── 16. Hex colors ───────────────────────────────────────────
_HEX_COLOR = re.compile(r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?\b')

# ── 17. Mathematical notation ────────────────────────────────
_MATH_EXPR = re.compile(
    r'\b[a-zA-Z]\s*[=<>≈≠≤≥±∓×÷∑∏∫∂∇√∞∧∨⊕⊗]\s*[a-zA-Z0-9]'
    r'|\\\(.*?\\\)|\\\[.*?\\\]'
    r'|\$[^$]+\$'
    r'|\$\$[^$]+\$\$'
)

# ── 18. Chemical formulas ────────────────────────────────────
_CHEMICAL = re.compile(
    r'\b(?:'
    r'H2O|CO2|O2|N2|NaCl|C6H12O6|CH4|NH3|H2SO4|HCl|'
    r'NaOH|C2H5OH|C3H8|C8H18|'
    r'(?=[A-Za-z]*\d)[A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*'
    r')\b'
)

# ── 19. Coordinates ──────────────────────────────────────────
_COORDS = re.compile(
    r'\b(-?\d+\.?\d*)\s*[°˚]\s*\d{1,2}\'\s*\d{1,2}(?:\.\d+)?\"?\s*[NSEWO]?\b'
    r'|\b(-?\d+\.\d+),\s*(-?\d+\.\d+)\b'
)

# ── 20. Percentages ──────────────────────────────────────────
_PERCENT = re.compile(r'\b\d+(?:\.\d+)?\s*%\b')

# ── 21. Social media handles ─────────────────────────────────
_SOCIAL = re.compile(r'@[a-zA-Z0-9_]{1,15}\b')

# ── 22. HTML entities ────────────────────────────────────────
_HTML_ENTITY = re.compile(r'&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;')

# ── 23. Telephone numbers ────────────────────────────────────
_PHONE = re.compile(
    r'(?:(?:\+?\d{1,3}[-. ]?)?\(?\d{2,4}\)?[-. ]?\d{2,4}[-. ]?\d{2,4})(?!\d)'
)

# ── Master pattern list (order matters: larger spans first) ──
_PROTECT_PATTERNS = [
    ("code", _CODE_FENCE),
    ("yaml", _YAML_BLOCK),
    ("json", _JSON_BLOCK),
    ("xml", _XML_TAG),
    ("math", _MATH_EXPR),
    ("quoted", _QUOTED),
    ("inline_code", _INLINE_CODE),
    ("url", _URL),
    ("semi_url", _SEMI_URL),
    ("iso_datetime", _ISO_DATETIME),
    ("time_range", _TIME_RANGE),
    ("date", _DATE),
    ("time", _TIME),
    ("email", _EMAIL),
    ("phone", _PHONE),
    ("social", _SOCIAL),
    ("currency", _CURRENCY),
    ("unit", _UNIT),
    ("legal_ref", _LEGAL_REF),
    ("ipv4", _IPV4),
    ("ipv6", _IPV6),
    ("port", _PORT),
    ("semver", _SEMVER),
    ("uuid", _UUID),
    ("hash", _HASH),
    ("hex_color", _HEX_COLOR),
    ("chemical", _CHEMICAL),
    ("coords", _COORDS),
    ("percent", _PERCENT),
    ("path", _FILE_PATH),
    ("html_entity", _HTML_ENTITY),
    ("placeholder", _PLACEHOLDER),
]


def protect(text: str, registry: ProtectedRegistry) -> str:
    """Replace all protected spans with placeholders. Returns protected text."""
    result = text
    for ptype, pattern in _PROTECT_PATTERNS:
        result = _protect_spans(result, pattern, ptype, registry)
    return result


def _protect_spans(text: str, pattern: re.Pattern, ptype: str, registry: ProtectedRegistry) -> str:
    """Replace all matches of pattern with placeholders."""
    def _replacer(m):
        pid = registry.add(m.group(0), (m.start(), m.end()), ptype)
        return pid
    return pattern.sub(_replacer, text)


def reinject(text: str, registry: ProtectedRegistry) -> str:
    """Restore all protected placeholders with their original values.
    Replaces in reverse-numeric order to avoid partial ID collisions (e.g. PROTECTED_1 matching inside PROTECTED_10)."""
    items = sorted(registry.items(), key=lambda x: int(x.id.split("_")[1]), reverse=True)
    for item in items:
        text = text.replace(item.id, item.original)
    return text


def verify_integrity(original: str, reconstructed: str, registry: ProtectedRegistry) -> List[str]:
    """Verify all protected spans survived. Returns list of missing span PIDs."""
    missing = []
    for item in registry.items():
        if item.original not in reconstructed:
            missing.append(item.id)
    return missing
