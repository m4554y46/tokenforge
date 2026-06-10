"""Sanctuary — détection de contenu protégé.

Identifie les blocs de code, JSON, LaTeX, YAML, tableaux markdown
dans un prompt, et plafonne le taux de compression maximal autorisé
pour éviter la corruption du contenu structuré.
"""

import logging
import re
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Seuils : plus le contenu protégé est présent, plus le taux max est bas
PROTECTED_RATIO_CAPS = [
    (0.30, 0.15),   # > 30 % protégé → seulement safe(0.15)
    (0.15, 0.25),   # > 15 % protégé → light(0.25)
    (0.05, 0.40),   # > 5 % protégé → balanced(0.40)
]

MAX_SAFE_PROFILE = 0.15

# Patterns de blocs protégés — ordre important : on matche les plus longs d'abord
_PROTECTED_PATTERNS = [
    # Blocs de code fencés (```python\n...\n```)
    ("fenced_code", re.compile(r"```[\w]*\n.*?\n```", re.DOTALL)),
    # LaTeX display math ($$...$$)
    ("latex_display", re.compile(r"\$\$.*?\$\$", re.DOTALL)),
    # LaTeX inline math ($...$)
    ("latex_inline", re.compile(r"(?<!\$)\$(?!\$).*?(?<!\$)\$(?!\$)", re.DOTALL)),
    # YAML front matter (---\n...\n---)
    ("yaml_front", re.compile(r"^---\n.*?\n---", re.DOTALL | re.MULTILINE)),
    # Tableaux markdown (lignes avec | et ---)
    ("markdown_table", re.compile(r"^.*\|.*\n\|[-| ]+\|\n(?:.*\|.*\n)*", re.MULTILINE)),
    # Blocs XML/HTML
    ("xml_block", re.compile(r"<[^>]+>.*?</[^>]+>", re.DOTALL)),
    # JSON blocks (lignes commençant par { ou [ avec indentation structurée)
    ("json_block", re.compile(r"^[ \t]*[{[]\n(?:[ \t]*[\[\]{}]|.*:.*\n)*[ \t]*[}\]]", re.MULTILINE)),
]


def detect_protected_blocks(text: str) -> List[Tuple[str, int, int]]:
    """Détecte tous les blocs protégés dans le texte.

    Retourne une liste de (type, start, end) triée par position.
    Les blocs qui se chevauchent sont fusionnés.
    """
    raw: List[Tuple[int, int, str]] = []
    for label, pat in _PROTECTED_PATTERNS:
        for m in pat.finditer(text):
            raw.append((m.start(), m.end(), label))

    # Trier par position
    raw.sort(key=lambda x: x[0])

    # Fusionner les blocs qui se chevauchent ou se touchent
    merged: List[Tuple[str, int, int]] = []
    for start, end, label in raw:
        if merged and start <= merged[-1][2]:
            # Fusion : étendre le dernier bloc si nécessaire
            last_label, last_start, last_end = merged[-1]
            if end > last_end:
                merged[-1] = (last_label, last_start, end)
        else:
            merged.append((label, start, end))

    return merged


def protected_ratio(text: str) -> float:
    """Fraction du texte qui est dans des blocs protégés (0.0 à 1.0)."""
    if not text:
        return 0.0
    blocks = detect_protected_blocks(text)
    if not blocks:
        return 0.0
    protected_chars = sum(end - start for _, start, end in blocks)
    return protected_chars / len(text)


def max_safe_rate(text: str) -> float:
    """Taux de compression maximal autorisé pour ce prompt.

    Plus il y a de contenu protégé, plus le taux maximum est bas.
    """
    ratio = protected_ratio(text)
    for threshold, capped_rate in PROTECTED_RATIO_CAPS:
        if ratio >= threshold:
            logger.debug("Sanctuary: ratio=%.2f >= %.2f → rate capped at %.2f",
                         ratio, threshold, capped_rate)
            return capped_rate
    return 1.0  # pas de limite


def max_safe_profile_name(text: str) -> str:
    """Nom du profil maximal autorisé par Sanctuary."""
    from backend.ace.state import RATE_TO_PROFILE
    rate = max_safe_rate(text)
    # Trouver le profil correspondant au taux max
    best_profile = "bypass"
    best_rate = 0.0
    for r, prof in RATE_TO_PROFILE.items():
        if r <= rate and r >= best_rate:
            best_rate = r
            best_profile = prof
    return best_profile
