"""Phase 5 — Constraint & Modality Extraction.

Full deontic, epistemic, and dynamic modality detection (EN + FR).
Includes hedging, certainty, discourse markers, conditionals, temporals, purpose.
"""

import re
from typing import Tuple, Optional, List

from .ir import Modality

# ═══════════════════════════════════════════════════════════════
# 1. DEONTIC MODALITIES (MUST, SHOULD, MAY, MUST_NOT, ...)
# ═══════════════════════════════════════════════════════════════

# ── English ───────────────────────────────────────────────────
_EN_MUST = re.compile(
    r'\b(must|shall|required|is\s+required\s+to|are\s+required\s+to|'
    r'needs?\s+to|has?\s+to|have\s+to|obligated|mandatory|compulsory|'
    r'it\s+is\s+necessary|it\s+is\s+mandatory|'
    r'it\s+is\s+compulsory|requisite)\b', re.I
)
_EN_MUST_NOT = re.compile(
    r'\b(must\s+not|shall\s+not|mustn\'t|shan\'t|'
    r'is\s+prohibited|are\s+prohibited|may\s+not|'
    r'is\s+forbidden|are\s+forbidden)\b', re.I
)
_EN_FORBIDDEN = re.compile(
    r'\b(forbidden|prohibited|not\s+allowed|disallowed|banned|'
    r'not\s+permitted|expressly\s+forbidden|strictly\s+prohibited)\b', re.I
)
_EN_SHOULD = re.compile(
    r'\b(should|recommended|ought\s+to|suggested|'
    r'it\s+is\s+advisable|it\s+is\s+recommended|'
    r'best\s+practice|it\s+is\s+preferable|'
    r'ideally|it\s+is\s+suggested|we\s+recommend)\b', re.I
)
_EN_SHOULD_NOT = re.compile(
    r'\b(should\s+not|shouldn\'t|not\s+recommended|discouraged|'
    r'not\s+advisable|it\s+is\s+not\s+recommended|'
    r'best\s+to\s+avoid|it\s+is\s+discouraged)\b', re.I
)
_EN_MAY = re.compile(
    r'\b(may|optional|optionally|permitted|allowed|'
    r'it\s+is\s+possible\s+to|it\s+is\s+permissible|'
    r'feel\s+free\s+to|at\s+your\s+discretion|'
    r'you\s+may|one\s+may|is\s+allowed\s+to)\b', re.I
)

# ── French ────────────────────────────────────────────────────
_FR_MUST = re.compile(
    r'\b(doit|doivent|devez|devons|il\s+faut|il\s+faudra|'
    r'il\s+est\s+nécessaire|il\s+est\s+obligatoire|'
    r'il\s+est\s+impératif|exigé|obligatoire|impératif|'
    r'tenu\s+de|sont\s+tenus|est\s+tenu|'
    r'strictement\s+nécessaire|incontournable|'
    r'indispensable|impérieux)\b', re.I
)
_FR_MUST_NOT = re.compile(
    r'\b(ne\s+doit\s+pas|ne\s+doivent\s+pas|ne\s+devez\s+pas|ne\s+devons\s+pas|'
    r'il\s+ne\s+faut\s+pas|interdit\s+de|défendu\s+de|prohibé|'
    r'il\s+est\s+interdit\s+de|il\s+est\s+défendu\s+de)\b', re.I
)
_FR_FORBIDDEN = re.compile(
    r'\b(interdit|défendu|prohibé|pas\s+autorisé|non\s+autorisé|banni|'
    r'strictement\s+interdit|formellement\s+interdit|'
    r'entièrement\s+défendu|illicite)\b', re.I
)
_FR_SHOULD = re.compile(
    r'\b(devrait|devraient|devriez|devrions|'
    r'il\s+est\s+recommandé|il\s+est\s+conseillé|'
    r'il\s+est\s+souhaitable|il\s+vaudrait\s+mieux|'
    r'mieux\s+vaut|préférable|il\s+est\s+préférable|'
    r'bonne\s+pratique|il\s+est\s+suggéré|'
    r'nous\s+recommandons|il\s+convient\s+de)\b', re.I
)
_FR_SHOULD_NOT = re.compile(
    r'\b(ne\s+devrait\s+pas|ne\s+devraient\s+pas|ne\s+devriez\s+pas|'
    r'il\s+n\'est\s+pas\s+recommandé|déconseillé|déconseillée|'
    r'il\s+est\s+déconseillé|pas\s+conseillé|'
    r'il\s+convient\s+d\'éviter|mieux\s+vaut\s+éviter)\b', re.I
)
_FR_MAY = re.compile(
    r'\b(peut|peuvent|pouvez|pouvons|'
    r'il\s+est\s+possible|facultatif|facultative|'
    r'optionnel|optionnelle|il\s+est\s+permis|'
    r'autorisé|il\s+est\s+autorisé|'
    r'vous\s+pouvez|libre\s+à\s+vous|'
    r'à\s+votre\s+discrétion|n\'hésitez\s+pas)\b', re.I
)

# ═══════════════════════════════════════════════════════════════
# 2. EPISTEMIC & HEDGING (certainty, speculation, hedging)
# ═══════════════════════════════════════════════════════════════

_EN_CERTAIN = re.compile(
    r'\b(certainly|definitely|undoubtedly|without\s+doubt|'
    r'indisputably|unquestionably|beyond\s+question|'
    r'invariably|always|never\s+fails|absolutely)\b', re.I
)
_EN_SPECULATIVE = re.compile(
    r'\b(maybe|perhaps|possibly|might|could\s+be|'
    r'it\s+is\s+possible\s+that|it\s+might\s+be|'
    r'presumably|potentially|conceivably|'
    r'there\s+is\s+a\s+chance|one\s+might|'
    r'it\s+could\s+be\s+that)\b', re.I
)
_EN_HEDGE = re.compile(
    r'\b(sort\s+of|kind\s+of|somewhat|rather|quite|'
    r'more\s+or\s+less|essentially|basically|'
    r'generally|in\s+general|for\s+the\s+most\s+part|'
    r'mostly|largely|roughly|approximately|about|'
    r'in\s+a\s+way|to\s+some\s+extent|up\s+to\s+a\s+point|'
    r'arguably|tends\s+to|as\s+it\s+were)\b', re.I
)
_FR_CERTAIN = re.compile(
    r'\b(certainement|indubitablement|sans\s+doute|'
    r'incontestablement|incontestable|absolument|'
    r'invariablement|toujours|ne\s+rate\s+jamais|'
    r'assurément|inéluctablement)\b', re.I
)
_FR_SPECULATIVE = re.compile(
    r'\b(peut-être|peut\s+être|possiblement|pourrait|'
    r'il\s+est\s+possible\s+que|il\s+se\s+pourrait|'
    r'probablement|hypothétique|hypothétiquement|'
    r'potentiellement|il\s+y\s+a\s+une\s+chance|'
    r'vraisemblablement|on\s+pourrait|'
    r'il\s+se\s+peut|susceptible\s+de)\b', re.I
)
_FR_HEDGE = re.compile(
    r'\b(plus\s+ou\s+moins|en\s+quelque\s+sorte|quelque\s+peu|'
    r'assez|plutôt|essentiellement|fondamentalement|'
    r'en\s+général|généralement|globalement|'
    r'pour\s+l\'essentiel|la\s+plupart|largement|'
    r'à\s+peu\s+près|environ|jusqu\'à\s+un\s+certain\s+point|'
    r'approximativement|tend\s+à|dans\s+une\s+certaine\s+mesure)\b', re.I
)

# ═══════════════════════════════════════════════════════════════
# 3. DISCOURSE MARKERS (logical relations between sentences)
# ═══════════════════════════════════════════════════════════════

_EN_DISCOURSE = {
    "cause": re.compile(
        r'\b(because|since|as|due\s+to|owing\s+to|'
        r'as\s+a\s+result\s+of|resulting\s+from|'
        r'caused\s+by|stemming\s+from)\b', re.I
    ),
    "consequence": re.compile(
        r'\b(therefore|thus|hence|consequently|'
        r'as\s+a\s+result|as\s+a\s+consequence|'
        r'accordingly|for\s+this\s+reason|'
        r'that\s+is\s+why|which\s+is\s+why|'
        r'leading\s+to|resulting\s+in)\b', re.I
    ),
    "contrast": re.compile(
        r'\b(however|but|nevertheless|nonetheless|'
        r'although|though|even\s+though|despite|'
        r'in\s+spite\s+of|whereas|while|'
        r'on\s+the\s+other\s+hand|conversely|'
        r'in\s+contrast|alternatively|yet|still|'
        r'all\s+the\s+same|having\s+said\s+that)\b', re.I
    ),
    "condition": re.compile(
        r'\b(if|unless|provided\s+that|providing\s+that|'
        r'as\s+long\s+as|on\s+condition\s+that|'
        r'in\s+case|in\s+the\s+event\s+that|'
        r'should|were\s+to|assuming\s+that|'
        r'given\s+that|whether|depending\s+on)\b', re.I
    ),
    "purpose": re.compile(
        r'\b(in\s+order\s+to|so\s+that|so\s+as\s+to|'
        r'for\s+the\s+purpose\s+of|with\s+the\s+aim\s+of|'
        r'aimed\s+at|designed\s+to|intended\s+to|'
        r'in\s+an\s+effort\s+to|as\s+a\s+means\s+to)\b', re.I
    ),
    "addition": re.compile(
        r'\b(moreover|furthermore|in\s+addition|'
        r'additionally|besides|also|what\s+is\s+more|'
        r'not\s+only|as\s+well\s+as|along\s+with|'
        r'further|likewise|similarly)\b', re.I
    ),
    "exemplification": re.compile(
        r'\b(for\s+example|for\s+instance|such\s+as|'
        r'e\.g\.|i\.e\.|namely|that\s+is|'
        r'including|like|in\s+particular|'
        r'particularly|specifically|notably)\b', re.I
    ),
    "summary": re.compile(
        r'\b(in\s+summary|to\s+summarize|in\s+conclusion|'
        r'overall|to\s+conclude|in\s+short|'
        r'briefly|in\s+brief|summing\s+up|'
        r'all\s+in\s+all|ultimately)\b', re.I
    ),
    "temporal": re.compile(
        r'\b(before|after|while|during|when|'
        r'as\s+soon\s+as|once|until|since|'
        r'prior\s+to|subsequently|afterwards|'
        r'meanwhile|at\s+the\s+same\s+time|'
        r'firstly|secondly|finally|then|next|'
        r'previously|earlier|later|eventually)\b', re.I
    ),
}

_FR_DISCOURSE = {
    "cause": re.compile(
        r'\b(parce\s+que|car|puisque|étant\s+donné\s+que|'
        r'en\s+raison\s+de|grâce\s+à|à\s+cause\s+de|'
        r'du\s+fait\s+de|dû\s+à|résultant\s+de)\b', re.I
    ),
    "consequence": re.compile(
        r'\b(donc|ainsi|par\s+conséquent|en\s+conséquence|'
        r'c\'est\s+pourquoi|par\s+suite|'
        r'de\s+ce\s+fait|ce\s+qui\s+explique|'
        r'ce\s+qui\s+conduit\s+à|d\'où)\b', re.I
    ),
    "contrast": re.compile(
        r'\b(cependant|mais|néanmoins|toutefois|'
        r'bien\s+que|quoique|malgré|en\s+dépit\s+de|'
        r'alors\s+que|tandis\s+que|en\s+revanche|'
        r'au\s+contraire|par\s+contre|à\s+l\'inverse|'
        r'pourtant|or|d\'un\s+autre\s+côté)\b', re.I
    ),
    "condition": re.compile(
        r'\b(si|à\s+condition\s+que|pourvu\s+que|'
        r'à\s+moins\s+que|en\s+cas\s+de|'
        r'dans\s+l\'hypothèse\s+où|supposé\s+que|'
        r'à\s+supposer\s+que|en\s+admettant\s+que|'
        r'suivant\s+que|selon\s+que)\b', re.I
    ),
    "purpose": re.compile(
        r'\b(afin\s+de|pour\s+que|de\s+sorte\s+que|'
        r'dans\s+le\s+but\s+de|en\s+vue\s+de|'
        r'ayant\s+pour\s+but\s+de|destiné\s+à|'
        r'conçu\s+pour|dans\s+l\'intention\s+de)\b', re.I
    ),
    "addition": re.compile(
        r'\b(de\s+plus|en\s+outre|par\s+ailleurs|'
        r'de\s+surcroît|en\s+supplément|'
        r'également|aussi|non\s+seulement|'
        r'ainsi\s+que|de\s+même|en\s+plus)\b', re.I
    ),
    "exemplification": re.compile(
        r'\b(par\s+exemple|comme|tels\s+que|'
        r'notamment|en\s+particulier|'
        r'à\s+savoir|c\'est-à-dire|'
        r'y\s+compris|particulièrement|'
        r'spécifiquement|entre\s+autres)\b', re.I
    ),
    "summary": re.compile(
        r'\b(en\s+résumé|pour\s+résumer|en\s+conclusion|'
        r'globalement|pour\s+conclure|en\s+bref|'
        r'brièvement|somme\s+toute|en\s+définitive|'
        r'finalement|au\s+final|en\s+un\s+mot)\b', re.I
    ),
    "temporal": re.compile(
        r'\b(avant|après|pendant|durant|lorsque|'
        r'quand|dès\s+que|une\s+fois\s+que|'
        r'jusqu\'à\s+ce\s+que|depuis\s+que|'
        r'préalablement|ultérieurement|'
        r'entre-temps|en\s+même\s+temps\s+que|'
        r'premièrement|deuxièmement|enfin|'
        r'ensuite|précédemment|plus\s+tard|'
        r'finalement|d\'abord)\b', re.I
    ),
}

# ═══════════════════════════════════════════════════════════════
# 4. TEMPORAL & CONDITIONAL CONSTRAINT MODIFIERS
# ═══════════════════════════════════════════════════════════════

_EN_TEMPORAL = re.compile(
    r'\b(always|never|sometimes|often|rarely|'
    r'at\s+all\s+times|at\s+no\s+time|'
    r'whenever|every\s+time|'
    r'as\s+soon\s+as|immediately|'
    r'within|before|after|during|prior\s+to)\b', re.I
)
_FR_TEMPORAL = re.compile(
    r'\b(toujours|jamais|parfois|souvent|rarement|'
    r'à\s+tout\s+moment|chaque\s+fois\s+que|'
    r'dès\s+que|immédiatement|'
    r'avant|après|pendant|durant|préalablement)\b', re.I
)

# ═══════════════════════════════════════════════════════════════
# 5. NEGATION (shared with negation.py, kept for backward compat)
# ═══════════════════════════════════════════════════════════════

_NEGATION = re.compile(
    r'\b('
    r'not|never|no|without|except|unless|'
    r'ne|pas|plus|jamais|rien|personne|aucun|aucune|'
    r'nul|nulle|ni|sans|sauf'
    r')\b', re.I
)

# ── Modality patterns for cleanup ─────────────────────────────
_MODALITY_CLEANUP = [
    _EN_MUST, _EN_MUST_NOT, _EN_FORBIDDEN,
    _EN_SHOULD, _EN_SHOULD_NOT, _EN_MAY,
    _FR_MUST, _FR_MUST_NOT, _FR_FORBIDDEN,
    _FR_SHOULD, _FR_SHOULD_NOT, _FR_MAY,
    _EN_SPECULATIVE, _EN_HEDGE,
    _FR_SPECULATIVE, _FR_HEDGE,
]


# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════

def detect_modality(sentence: str, lang: str = "en") -> Tuple[Modality, bool]:
    """Detect the modality of a sentence. Supports 'en' and 'fr'. Returns (modality, is_negated)."""
    patterns_en = [
        (_EN_FORBIDDEN, Modality.FORBIDDEN, True),
        (_EN_MUST_NOT, Modality.MUST_NOT, True),
        (_EN_MUST, Modality.MUST, None),
        (_EN_SHOULD_NOT, Modality.SHOULD_NOT, True),
        (_EN_SHOULD, Modality.SHOULD, None),
        (_EN_MAY, Modality.MAY, None),
    ]
    patterns_fr = [
        (_FR_MUST_NOT, Modality.MUST_NOT, True),
        (_FR_FORBIDDEN, Modality.FORBIDDEN, True),
        (_FR_MUST, Modality.MUST, None),
        (_FR_SHOULD_NOT, Modality.SHOULD_NOT, True),
        (_FR_SHOULD, Modality.SHOULD, None),
        (_FR_MAY, Modality.MAY, None),
    ]
    patterns = patterns_en + patterns_fr if lang == "en" else patterns_fr + patterns_en

    for pat, mod, forced_neg in patterns:
        if pat.search(sentence):
            if forced_neg is not None:
                return mod, forced_neg
            negated = bool(_NEGATION.search(sentence))
            return mod, negated

    return Modality.MUST, False


def detect_epistemic(sentence: str, lang: str = "en") -> str:
    """Detect epistemic stance: 'certain', 'speculative', 'hedged', or ''."""
    if lang == "en":
        if _EN_CERTAIN.search(sentence):
            return "certain"
        if _EN_SPECULATIVE.search(sentence):
            return "speculative"
        if _EN_HEDGE.search(sentence):
            return "hedged"
    else:
        if _FR_CERTAIN.search(sentence):
            return "certain"
        if _FR_SPECULATIVE.search(sentence):
            return "speculative"
        if _FR_HEDGE.search(sentence):
            return "hedged"
    return ""


def detect_discourse(sentence: str, lang: str = "en") -> List[Tuple[str, str]]:
    """Detect discourse markers. Returns list of (relation_type, marker_text)."""
    markers = _EN_DISCOURSE if lang == "en" else _FR_DISCOURSE
    results = []
    for rel_type, pattern in markers.items():
        m = pattern.search(sentence)
        if m:
            results.append((rel_type, m.group(0)))
    return results


def extract_subject_predicate(sentence: str, modality: Modality, lang: str = "en") -> Tuple[str, str]:
    """Extract subject and predicate from a constraint sentence."""
    cleaned = sentence
    for pat in _MODALITY_CLEANUP:
        cleaned = pat.sub("", cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = re.sub(r'^[,\s]+|[,\s]+$', '', cleaned)

    parts = cleaned.split(None, 1) if cleaned else ("", "")
    subject = parts[0].strip() if parts else ""
    predicate = parts[1].strip() if len(parts) > 1 else ""
    return subject, predicate


def extract_constraints(text: str, lang: str = "en") -> list:
    """Extract all constraint sentences from text.

    Returns list of (modality, subject, predicate, negated, original_sentence,
                     epistemic, discourse, temporal_modifier).
    """
    constraints = []
    sentences = re.split(r'(?<=[.!?])\s+', text)

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        modality, negated = detect_modality(sent, lang=lang)
        subject, predicate = extract_subject_predicate(sent, modality, lang=lang)
        epistemic = detect_epistemic(sent, lang=lang)
        discourse = detect_discourse(sent, lang=lang)
        constraints.append((
            modality, subject, predicate, negated, sent,
            epistemic, discourse,
        ))

    return constraints
