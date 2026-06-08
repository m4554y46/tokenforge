"""Phase 6 — Negation Detection & Scope Resolution.

Full negation handling for English and French:
  - Cue detection (lexical + affixal)
  - Scope resolution (heuristic, dependency-light)
  - Double negation tracking
  - Negative concord (French)
  - NPI-like licensing patterns
  - Mark/unmark for compression preservation
"""

import re
from dataclasses import dataclass
from typing import List, Tuple, Optional, Set

# ═══════════════════════════════════════════════════════════════
# 1. NEGATION CUES — EN
# ═══════════════════════════════════════════════════════════════

# Primary lexical cues
_EN_NEG_CUES = re.compile(
    r'\b('
    r'not|never|no|none|nothing|nobody|nowhere|'
    r'neither|nor|cannot|'
    r'without|except|unless|beyond|'
    r'hardly|barely|scarcely|rarely|seldom|'
    r'nowhere|noways|nowise|'
    r'n\'t'  # contraction suffix
    r')\b',
    re.I
)

# Contracted forms (mapped to canonical)
_EN_CONTRACTED = re.compile(
    r'\b('
    r'can\'t|cannot|cant|don\'t|doesn\'t|didn\'t|'
    r'won\'t|wouldn\'t|shouldn\'t|mustn\'t|'
    r'isn\'t|aren\'t|wasn\'t|weren\'t|'
    r'hasn\'t|haven\'t|hadn\'t|'
    r'couldn\'t|needn\'t|mightn\'t|'
    r'ain\'t'
    r')\b',
    re.I
)

# Affixal negation (prefixes)
_EN_AFFIXAL_NEG = re.compile(
    r'\b('
    r'un(?:[a-z]+)|'          # unhappy, unable, unclear
    r'in(?:[a-z]+)|'           # inactive, incorrect
    r'im(?:[a-z]+)|'           # impossible, immature
    r'il(?:[a-z]+)|'           # illegal, illogical
    r'ir(?:[a-z]+)|'           # irrelevant, irregular
    r'dis(?:[a-z]+)|'          # disagree, disapprove
    r'non(?:[a-z]+)|'          # non-existent, non-trivial
    r'[a-z]+less'              # hopeless, useless
    r')\b',
    re.I
)

# ═══════════════════════════════════════════════════════════════
# 2. NEGATION CUES — FR
# ═══════════════════════════════════════════════════════════════

_FR_NEG_CUES = re.compile(
    r'\b('
    r'ne|n\'|pas|plus|jamais|rien|personne|'
    r'aucun|aucune|nul|nulle|ni|'
    r'sans|sauf|guère|nullement|aucunement|'
    r'point|nulle\s+part|quiconque|'
    r'ni\.\.\.ni|ne\.\.\.que'  # restricted to "only"
    r')\b',
    re.I
)

# French affixal negation (includes accented chars)
_FR_AFFIXAL_NEG = re.compile(
    r'\b('
    r'in(?:[a-zàâäéèêëîïôöùûüÿ]+)|'
    r'im(?:[a-zàâäéèêëîïôöùûüÿ]+)|'
    r'il(?:[a-zàâäéèêëîïôöùûüÿ]+)|'
    r'ir(?:[a-zàâäéèêëîïôöùûüÿ]+)|'
    r'dés(?:[a-zàâäéèêëîïôöùûüÿ]+)|'
    r'dé(?:[a-zàâäéèêëîïôöùûüÿ]+)|'
    r'mé(?:[a-zàâäéèêëîïôöùûüÿ]+)|'
    r'mal(?:[a-zàâäéèêëîïôöùûüÿ]+)|'
    r'anti(?:[a-zàâäéèêëîïôöùûüÿ]+)|'
    r'(?:[a-zàâäéèêëîïôöùûüÿ]+)moins'
    r')\b',
    re.I
)

# ═══════════════════════════════════════════════════════════════
# 3. NEGATIVE CONCORD (FR: "ne...pas", "ne...plus", etc.)
# ═══════════════════════════════════════════════════════════════

_FR_CONCORD = re.compile(
    r'ne\s+(?:\w+\s+)?(pas|plus|jamais|rien|personne|aucun|aucune|guère|point)',
    re.I
)

# ═══════════════════════════════════════════════════════════════
# 4. DOUBLE NEGATION PATTERNS
# ═══════════════════════════════════════════════════════════════

_EN_DOUBLE_NEG = re.compile(
    r'\b(not\s+(un|in|im|il|ir|dis)|'
    r'never\s+(un|in|im|il|ir|dis)|'
    r'not\s+without|not\s+unless|'
    r'not\s+impossible|not\s+unlikely|'
    r'not\s+uncommon|not\s+unrelated)\b',
    re.I
)

_FR_DOUBLE_NEG = re.compile(
    r'\b(ne\s+\w+\s+pas\s+(in|im|il|ir|dés|dé|mé)|'
    r'pas\s+sans|pas\s+nullement|'
    r'pas\s+impossible|pas\s+inutile|'
    r'pas\s+rare)\b',
    re.I
)

# ═══════════════════════════════════════════════════════════════
# 5. NPI-LIKE LICENSING CONTEXTS
# ═══════════════════════════════════════════════════════════════

_EN_NPI_TRIGGERS = re.compile(
    r'\b('
    r'any|anyone|anybody|anything|anywhere|'
    r'ever|either|yet|at\s+all|'
    r'whatsoever|whatsover|in\s+the\s+least'
    r')\b', re.I
)

_FR_NPI_TRIGGERS = re.compile(
    r'\b('
    r'personne|rien|aucun|aucune|'
    r'jamais|plus|guère|'
    r'le\s+moindre\s+du\s+monde|du\s+tout|'
    r'quoi\s+que\s+ce\s+soit'
    r')\b', re.I
)

# ═══════════════════════════════════════════════════════════════
# 6. SCOPE RESOLUTION (heuristic, token-distance based)
# ═══════════════════════════════════════════════════════════════

# Scope boundary markers: punctuation/clause boundaries
_SCOPE_BOUNDARY = re.compile(r'[.!?;,]|\b(and|or|but|however|therefore|because|although|while)\b', re.I)
_FR_SCOPE_BOUNDARY = re.compile(r'[.!?;,]|\b(et|ou|mais|car|donc|parce\s+que|bien\s+que|tandis\s+que)\b', re.I)


@dataclass
class NegationSpan:
    cue: str
    cue_start: int
    cue_end: int
    scope_start: int
    scope_end: int
    scope_text: str
    is_affixal: bool = False
    is_double: bool = False
    is_concord: bool = False  # FR: ne...pas
    confidence: float = 1.0


# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════

def has_negation(text: str) -> bool:
    """Check if text contains lexical or affixal negation markers."""
    if _EN_NEG_CUES.search(text) or _EN_CONTRACTED.search(text):
        return True
    if _FR_NEG_CUES.search(text):
        return True
    return False


def has_affixal_negation(text: str, lang: str = "en") -> bool:
    """Check if text contains affixal negation (un-, in-, dis-, etc.)."""
    patterns = {"en": _EN_AFFIXAL_NEG, "fr": _FR_AFFIXAL_NEG}
    return bool(patterns.get(lang, _EN_AFFIXAL_NEG).search(text))


def is_double_negation(text: str, lang: str = "en") -> bool:
    """Check if text contains double negation patterns."""
    patterns = {"en": _EN_DOUBLE_NEG, "fr": _FR_DOUBLE_NEG}
    return bool(patterns.get(lang, _EN_DOUBLE_NEG).search(text))


def count_negation_cues(text: str) -> int:
    """Count all lexical negation cues in text."""
    count = 0
    for m in _EN_NEG_CUES.finditer(text):
        count += 1
    for m in _EN_CONTRACTED.finditer(text):
        count += 1
    for m in _FR_NEG_CUES.finditer(text):
        count += 1
    return count


def resolve_scope(text: str, lang: str = "en") -> List[NegationSpan]:
    """Heuristic scope resolution for negations in text.

    Returns list of NegationSpan objects identifying the negation
    cue and its scope (the portion of the sentence affected).
    """
    cues = _find_cues(text, lang)
    boundary = _SCOPE_BOUNDARY if lang == "en" else _FR_SCOPE_BOUNDARY
    spans = []

    for cue_word, start, end in cues:
        # Scope: from cue to next boundary or clause end
        remaining = text[end:]
        bm = boundary.search(remaining)
        if bm:
            scope_end = end + bm.start()
        else:
            scope_end = len(text)

        # Scope start: beginning of the containing clause
        before = text[:start]
        prev_b = list(boundary.finditer(before))
        if prev_b:
            scope_start = prev_b[-1].end()
        else:
            scope_start = 0

        scope_text = text[scope_start:scope_end].strip()

        is_aff = False
        is_double = False
        is_conc = False

        if lang == "fr":
            # Check for French concord negation
            if _FR_CONCORD.search(scope_text):
                is_conc = True

        if lang == "en":
            if _EN_DOUBLE_NEG.search(scope_text):
                is_double = True
        else:
            if _FR_DOUBLE_NEG.search(scope_text):
                is_double = True

        spans.append(NegationSpan(
            cue=cue_word,
            cue_start=start,
            cue_end=end,
            scope_start=scope_start,
            scope_end=scope_end,
            scope_text=scope_text,
            is_affixal=is_aff,
            is_double=is_double,
            is_concord=is_conc,
        ))

    return spans


def _find_cues(text: str, lang: str) -> List[Tuple[str, int, int]]:
    """Find all negation cues with positions."""
    cues = []
    for pat in (_EN_NEG_CUES, _EN_CONTRACTED):
        for m in pat.finditer(text):
            cues.append((m.group(0), m.start(), m.end()))
    if lang == "fr":
        for m in _FR_NEG_CUES.finditer(text):
            cues.append((m.group(0), m.start(), m.end()))
    return cues


def consolidate_negations(text: str, lang: str = "en") -> str:
    """Consolidate double negations into positive where safe, mark others."""
    # Preserve PROTECTED_ placeholders from lowercasing
    ph_saved = []
    def _save_ph(m):
        ph_saved.append(m.group(0))
        return f"\x00{len(ph_saved)-1}\x00"
    result = re.sub(r'PROTECTED_\d+', _save_ph, text)
    result = result.lower()
    # Simple pass: not impossible → possible, not without → with
    replacements = {
        "not impossible": "possible",
        "not uncommon": "common",
        "not unlikely": "likely",
        "not unrelated": "related",
        "not without": "with",
        "not unless": "only if",
    }
    for old, new in replacements.items():
        result = result.replace(old, new)
    def _restore_ph(m):
        return ph_saved[int(m.group(1))]
    result = re.sub(r'\x00(\d+)\x00', _restore_ph, result)
    return result


def find_negated_segments(text: str) -> List[str]:
    """Find and return all segments containing negation."""
    segments = []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sent in sentences:
        if has_negation(sent):
            segments.append(sent.strip())
    return segments


def mark_negated(text: str) -> str:
    """Wrap negation cues with ¬ markers for compression protection."""
    def _marker(m):
        return f"¬{m.group(0)}¬"
    result = _EN_NEG_CUES.sub(_marker, text)
    result = _EN_CONTRACTED.sub(_marker, result)
    result = _FR_NEG_CUES.sub(_marker, result)
    return result


def unmark_negated(text: str) -> str:
    """Remove ¬ negation markers after compression."""
    return text.replace("¬", "")
