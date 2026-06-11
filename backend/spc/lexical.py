"""Phase 11 — Lexical Compression.

Safe word & phrase-level compression for English and French:
- Verbose phrase → compact equivalent
- Fluff word removal  
- Polite expression simplification
- Redundancy removal
"""

import re

__all__ = [
    "compress_lexical",
    "remove_fluff",
    "simplify_polite",
    "shorten_phrases",
]

# ═══════════════════════════════════════════════════════════════
# ENGLISH VERBOSE PHRASE → SHORT EQUIVALENT MAP
# ═══════════════════════════════════════════════════════════════

_EN_PHRASE_MAP = [
    # Causal / logical
    (re.compile(r"\bdue\s+to\s+the\s+fact\s+that\b", re.I), "since"),
    (re.compile(r"\bin\s+spite\s+of\s+the\s+fact\s+that\b", re.I), "although"),
    (re.compile(r"\bin\s+the\s+event\s+that\b", re.I), "if"),
    (re.compile(r"\bin\s+order\s+to\b", re.I), "to"),
    (re.compile(r"\bfor\s+the\s+purpose\s+of\b", re.I), "to"),
    (re.compile(r"\bas\s+a\s+result\s+of\b", re.I), "because"),
    (re.compile(r"\bas\s+a\s+consequence\b", re.I), "so"),
    (re.compile(r"\bin\s+light\s+of\b", re.I), "given"),
    (re.compile(r"\bon\s+the\s+basis\s+of\b", re.I), "by"),
    (re.compile(r"\bby\s+means\s+of\b", re.I), "via"),
    (re.compile(r"\bin\s+accordance\s+with\b", re.I), "per"),
    (re.compile(r"\bin\s+line\s+with\b", re.I), "per"),
    (re.compile(r"\bprovided\s+that\b", re.I), "if"),
    (re.compile(r"\bassuming\s+that\b", re.I), "if"),
    (re.compile(r"\bon\s+condition\s+that\b", re.I), "if"),
    # Reference / topic
    (re.compile(r"\bwith\s+regard\s+to\b", re.I), "regarding"),
    (re.compile(r"\bin\s+relation\s+to\b", re.I), "about"),
    (re.compile(r"\bwith\s+respect\s+to\b", re.I), "re"),
    (re.compile(r"\bwith\s+reference\s+to\b", re.I), "re"),
    (re.compile(r"\bin\s+the\s+context\s+of\b", re.I), "in"),
    (re.compile(r"\bwhen\s+it\s+comes\s+to\b", re.I), "for"),
    (re.compile(r"\bon\s+behalf\s+of\b", re.I), "for"),
    (re.compile(r"\bon\s+the\s+topic\s+of\b", re.I), "on"),
    (re.compile(r"\bwith\s+regards?\s+to\b", re.I), "about"),
    (re.compile(r"\bin\s+terms\s+of\b", re.I), "in"),
    # Time
    (re.compile(r"\bat\s+this\s+point\s+in\s+time\b", re.I), "now"),
    (re.compile(r"\bat\s+the\s+present\s+time\b", re.I), "now"),
    (re.compile(r"\bat\s+this\s+time\b", re.I), "now"),
    (re.compile(r"\bin\s+the\s+near\s+future\b", re.I), "soon"),
    (re.compile(r"\bin\s+the\s+meantime\b", re.I), "meanwhile"),
    (re.compile(r"\bprior\s+to\b", re.I), "before"),
    (re.compile(r"\bsubsequent\s+to\b", re.I), "after"),
    (re.compile(r"\bprevious\s+to\b", re.I), "before"),
    (re.compile(r"\bfollowing\s+which\b", re.I), "then"),
    # Quantity / degree
    (re.compile(r"\ba\s+sufficient\s+number\s+of\b", re.I), "enough"),
    (re.compile(r"\ba\s+large\s+number\s+of\b", re.I), "many"),
    (re.compile(r"\ba\s+small\s+number\s+of\b", re.I), "few"),
    (re.compile(r"\ba\s+significant\s+number\s+of\b", re.I), "many"),
    (re.compile(r"\ba\s+great\s+deal\s+of\b", re.I), "much"),
    (re.compile(r"\ba\s+lot\s+of\b", re.I), "many"),
    (re.compile(r"\bthe\s+majority\s+of\b", re.I), "most"),
    (re.compile(r"\ba\s+significant\s+amount\s+of\b", re.I), "much"),
    (re.compile(r"\bin\s+close\s+proximity\s+to\b", re.I), "near"),
    (re.compile(r"\bin\s+the\s+vicinity\s+of\b", re.I), "near"),
    (re.compile(r"\bin\s+excess\s+of\b", re.I), "over"),
    # Frequency / manner
    (re.compile(r"\bon\s+a\s+regular\s+basis\b", re.I), "regularly"),
    (re.compile(r"\bin\s+a\s+timely\s+manner\b", re.I), "promptly"),
    (re.compile(r"\bin\s+a\s+similar\s+vein\b", re.I), "similarly"),
    (re.compile(r"\bas\s+per\s+usual\b", re.I), "usually"),
    # Ability / modality
    (re.compile(r"\bhas\s+the\s+ability\s+to\b", re.I), "can"),
    (re.compile(r"\bis\s+able\s+to\b", re.I), "can"),
    (re.compile(r"\bis\s+capable\s+of\b", re.I), "can"),
    (re.compile(r"\bhas\s+the\s+capacity\s+to\b", re.I), "can"),
    # Exclusion / inclusion
    (re.compile(r"\bwith\s+the\s+exception\s+of\b", re.I), "except"),
    (re.compile(r"\bin\s+the\s+absence\s+of\b", re.I), "without"),
    (re.compile(r"\bas\s+well\s+as\b", re.I), "and"),
    (re.compile(r"\bin\s+addition\s+to\b", re.I), "plus"),
    # Question / reference
    (re.compile(r"\bthe\s+question\s+as\s+to\s+whether\b", re.I), "whether"),
    (re.compile(r"\bin\s+the\s+case\s+of\b", re.I), "for"),
    (re.compile(r"\bin\s+regards?\s+to\b", re.I), "re"),
    (re.compile(r"\bas\s+far\s+as\b", re.I), "for"),
]

# Common abbreviation substitutions
_EN_ABBREV_MAP = [
    (re.compile(r"\bfor\s+example\b", re.I), "e.g."),
    (re.compile(r"\bfor\s+instance\b", re.I), "e.g."),
    (re.compile(r"\bthat\s+is\b", re.I), "i.e."),
    (re.compile(r"\bin\s+other\s+words\b", re.I), "i.e."),
    (re.compile(r"\bsuch\s+as\b", re.I), "like"),
    (re.compile(r"\bin\s+particular\b", re.I), "notably"),
    (re.compile(r"\bespecially\b", re.I), "esp."),
    (re.compile(r"\bparticularly\b", re.I), "esp."),
]

# Redundant word pairs
_EN_REDUNDANT_MAP = [
    (re.compile(r"\bwhether\s+or\s+not\b", re.I), "whether"),
    (re.compile(r"\beach\s+and\s+every\b", re.I), "each"),
    (re.compile(r"\bfirst\s+and\s+foremost\b", re.I), "first"),
    (re.compile(r"\bany\s+and\s+all\b", re.I), "all"),
    (re.compile(r"\bbasic\s+essentials?\b", re.I), "essentials"),
    (re.compile(r"\bnull\s+and\s+void\b", re.I), "void"),
]

# Fluff words (single words removable without meaning loss in prompts)
_EN_FLUFF = re.compile(
    r"\b(basically|actually|literally|essentially|virtually|"
    r"practically|relatively|fundamentally|"
    r"quite|rather|somewhat|really|very)\b",
    re.I,
)

# Polite / meta phrases removable from LLM prompts
_EN_POLITE_MAP = [
    (re.compile(r"\bplease\s+", re.I), ""),
    (re.compile(r"\bI\s+(would\s+)?like\s+(you\s+)?to\b", re.I), ""),
    (re.compile(r"\b(could|would)\s+you\s+(please\s+)?", re.I), ""),
    (re.compile(r"\bthank\s+you\s+(in\s+advance\s+)?(for\s+(your\s+)?(help|assistance|time))?\b", re.I), ""),
    (re.compile(r"\bI\s+(would\s+)?(really\s+)?appreciate\s+(it\s+)?(if\s+)?(you\s+(could|would)\s+)?\b", re.I), ""),
    (re.compile(r"\bI\s+need\s+you\s+to\b", re.I), ""),
    (re.compile(r"\bI\s+want\s+you\s+to\b", re.I), ""),
    # Meta annotations (safe to remove in instruction context)
    (re.compile(r"\bpay\s+(close|special|particular)?\s*attention\s+to\b", re.I), "focus on"),
]

# Instruction compression — shorten common prompt directives
_EN_INSTRUCTION_MAP = [
    (re.compile(r"\byou\s+(should|must|need\s+to|are\s+(required|expected)\s+to)\s+", re.I), ""),
    (re.compile(r"\byour\s+(task|job|goal)\s+is\s+to\b", re.I), ""),
    (re.compile(r"\bthe\s+(task|goal|objective)\s+is\s+to\b", re.I), ""),
    (re.compile(r"\bI\s+would\s+like\s+you\s+to\s+", re.I), ""),
    (re.compile(r"\bI'm\s+looking\s+for\s+", re.I), ""),
    (re.compile(r"\bI\s+am\s+looking\s+for\s+", re.I), ""),
    (re.compile(r"\b(please\s+)?provide\s+me\s+with\b", re.I), "provide"),
    (re.compile(r"\bgive\s+me\b", re.I), "show"),
    (re.compile(r"\btell\s+me\b", re.I), ""),
]

# ═══════════════════════════════════════════════════════════════
# FRENCH VERBOSE PHRASE → SHORT EQUIVALENT MAP
# ═══════════════════════════════════════════════════════════════

_FR_PHRASE_MAP = [
    (re.compile(r"\bdue\s+to\s+the\s+fact\s+that\b", re.I), "since"),
]

_FR_POLITE_MAP = [
    (re.compile(r"\bs\'il\s+vous\s+plaît\b", re.I), ""),
    (re.compile(r"\bje\s+(voudrais|souhaiterais)\s+que\s+vous\b", re.I), ""),
    (re.compile(r"\bmerci\s+(d\'avance\s+)?\b", re.I), ""),
    (re.compile(r"\bpouvez-vous\s+", re.I), ""),
    (re.compile(r"\bpourriez-vous\s+", re.I), ""),
]

_FR_REDUNDANT_MAP = [
    (re.compile(r"\banticiper\s+d\'avance\b", re.I), "anticiper"),
    (re.compile(r"\bprévoir\s+à\s+l\'avance\b", re.I), "prévoir"),
    (re.compile(r"\bprévoir\s+par\s+avance\b", re.I), "prévoir"),
    (re.compile(r"\bmonter\s+en\s+haut\b", re.I), "monter"),
    (re.compile(r"\bdescendre\s+en\s+bas\b", re.I), "descendre"),
    (re.compile(r"\bcollaborer\s+ensemble\b", re.I), "collaborer"),
    (re.compile(r"\brépéter\s+à\s+nouveau\b", re.I), "répéter"),
    (re.compile(r"\bplus\s+mieux\b", re.I), "mieux"),
    (re.compile(r"\baujourd\'hui\s+de\s+ce\s+jour\b", re.I), "aujourd'hui"),
    (re.compile(r"\bpréavis\s+d\'avance\b", re.I), "préavis"),
]

# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════


def shorten_phrases(text: str, lang: str = "en") -> str:
    """Replace verbose phrases with shorter equivalents."""
    maps = _EN_PHRASE_MAP + _EN_REDUNDANT_MAP + _EN_ABBREV_MAP
    if lang == "fr":
        maps += _FR_REDUNDANT_MAP
    for pattern, replacement in maps:
        text = pattern.sub(replacement, text)
    return text


def remove_fluff(text: str) -> str:
    """Remove fluff / filler words that add no semantic value."""
    return _EN_FLUFF.sub("", text)


def simplify_polite(text: str, lang: str = "en") -> str:
    """Remove polite / meta phrases unnecessary for LLMs."""
    maps = _EN_POLITE_MAP + _EN_INSTRUCTION_MAP
    if lang == "fr":
        maps += _FR_POLITE_MAP
    for pattern, replacement in maps:
        text = pattern.sub(replacement, text)
    return text


def compress_lexical(text: str, lang: str = "en") -> str:
    """Full lexical compression: phrases → short, remove fluff, simplify polite."""
    text = shorten_phrases(text, lang)
    text = remove_fluff(text)
    text = simplify_polite(text, lang)
    # Clean up double spaces left by removals
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()
