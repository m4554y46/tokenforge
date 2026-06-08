"""Phase 1 — Ingestion.

Detects encoding, normalizes Unicode, detects format, produces CanonicalDocument.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CanonicalDocument:
    text: str
    language: str = "en"
    detected_format: str = "txt"
    source_path: Optional[str] = None
    encoding: str = "utf-8"
    metadata: dict = field(default_factory=dict)


# Format detection by extension
EXTENSION_MAP = {
    ".txt": "txt",
    ".md": "markdown",
    ".markdown": "markdown",
    ".html": "html",
    ".htm": "html",
    ".xml": "xml",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".csv": "csv",
    ".rtf": "rtf",
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".java": "code",
    ".cpp": "code",
    ".c": "code",
    ".h": "code",
    ".sql": "code",
    ".sh": "code",
    ".bat": "code",
    ".ps1": "code",
}


def sniff_format(text: str) -> str:
    """Content-based format sniffing when extension is unknown."""
    t = text.strip()
    if not t:
        return "txt"
    if t.startswith("<?xml") or t.startswith("<html") or re.match(r'<\w+[^>]*>', t, re.I):
        return "html" if t.startswith("<html") else "xml"
    if t.startswith("{") or t.startswith("["):
        try:
            import json
            json.loads(t)
            return "json"
        except (json.JSONDecodeError, ValueError):
            pass
    if t.startswith("---") and ":" in t[:200]:
        return "yaml"
    lines = t.split("\n")
    if len(lines) > 2 and re.match(r'^[-\w\s]+$', lines[0]) and re.match(r'^[-|=]+\s*$', lines[1]):
        return "csv"
    return "txt"


def detect_encoding(data: bytes) -> str:
    """Detect text encoding. Falls back to utf-8."""
    import codecs
    for enc in ("utf-8", "utf-16", "latin-1", "cp1252"):
        try:
            data.decode(enc)
            return enc if enc != "utf-8" else "utf-8"
        except (UnicodeDecodeError, LookupError):
            continue
    return "utf-8"


def normalize(text: str, form: str = "NFC") -> str:
    """Normalize Unicode form."""
    import unicodedata
    return unicodedata.normalize(form, text)


# Language detection heuristics
_FR_SENTINELS = re.compile(
    r'\b(je|tu|il|elle|nous|vous|ils|elles|le|la|les|un|une|des|'
    r'ce|cet|cette|ces|mon|ton|son|ma|ta|sa|mes|tes|ses|'
    r'du|au|aux|dans|pour|avec|sur|chez|entre|sans|'
    r'doit|doivent|devrait|pourrait|faudrait|'
    r'ne\s+pas|ne\s+plus|ne\s+jamais)\b',
    re.I
)
_EN_SENTINELS = re.compile(
    r'\b(the|a|an|this|that|these|those|my|your|his|her|its|our|their|'
    r'must|shall|should|would|could|might|may|'
    r'not|never|no)\b',
    re.I
)


def detect_language(text: str) -> str:
    """Detect 'fr' or 'en' based on sentinel word frequency."""
    fr_hits = len(_FR_SENTINELS.findall(text))
    en_hits = len(_EN_SENTINELS.findall(text))
    if fr_hits > en_hits and fr_hits > 1:
        return "fr"
    return "en"


def ingest(source: str, source_path: Optional[str] = None) -> CanonicalDocument:
    """Main entry: ingest text or file path into CanonicalDocument."""
    text: str
    encoding = "utf-8"
    detected_format = "txt"

    if source_path and os.path.isfile(source):
        with open(source, "rb") as f:
            raw = f.read()
        encoding = detect_encoding(raw)
        text = raw.decode(encoding)
        ext = os.path.splitext(source)[1].lower()
        detected_format = EXTENSION_MAP.get(ext, sniff_format(text))
    else:
        text = source
        detected_format = sniff_format(text)

    text = normalize(text, "NFC")
    lang = detect_language(text)
    return CanonicalDocument(
        text=text,
        language=lang,
        detected_format=detected_format,
        source_path=source_path or source,
        encoding=encoding,
    )
