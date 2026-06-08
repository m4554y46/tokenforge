import json
import re
import os
import requests
import google.generativeai as genai
from typing import List, Dict, Optional, Tuple
from backend.token_counter import count_tokens

OPTIMIZER_SYSTEM_PROMPT = """You are PromptCompress, an expert prompt optimization engine..."""

_EN_SENTENCE_SPLIT_ABBREVS = ["Mr.", "Dr.", "M.", "Mme.", "i.e.", "e.g.", "cf."]

CATEGORIES = [
    "general", "literary", "scientific", "commercial",
    "philosophical", "instructional",
    "legal", "financial", "technical", "administrative", "academic",
]

# Category-specific tool words: which words to KEEP (excluded from stop list) vs general
CATEGORY_KEEP_WORDS_FR = {
    "literary": {"je", "tu", "il", "elle", "nous", "vous", "ils", "mon", "ton",
                 "son", "mes", "tes", "ses", "sa", "notre", "votre", "leur",
                 "mais", "donc", "et", "car", "ni", "ou", "parce", "comme",
                 "quand", "lorsque", "si", "puis", "alors", "pourtant", "cependant"},
    "philosophical": {"donc", "car", "mais", "or", "ni", "parce", "puisque",
                      "alors", "en effet", "cependant", "néanmoins",
                      "toutefois", "pourtant", "si", "ainsi"},
    "instructional": {"si", "quand", "lorsque", "chaque", "quelque", "plusieurs",
                      "entre", "depuis", "pendant", "avant", "après"},
    "legal": {"ledit", "ladite", "lesdits", "lesdites", "auxdites", "auxdits",
              "nonobstant", "conformément", "vertu", "dudit", "dite", "dit",
              "sauf", "hormis", "notamment", "ou", "ni"},
    "academic": {"cependant", "néanmoins", "toutefois", "donc", "car", "or",
                 "notamment", "notons", "soulignons", "observons"},
    "scientific": set(),
    "commercial": set(),
    "financial": set(),
    "technical": set(),
    "administrative": set(),
}
CATEGORY_KEEP_WORDS_EN = {
    "literary": {"i", "you", "he", "she", "we", "they", "my", "your", "his",
                 "her", "our", "their", "but", "so", "and", "or", "nor",
                 "because", "as", "when", "while", "though", "although",
                 "then", "yet", "for", "if"},
    "philosophical": {"therefore", "hence", "thus", "so", "because", "since",
                      "if", "then", "however", "nevertheless", "nonetheless",
                      "consequently", "accordingly", "furthermore", "moreover"},
    "instructional": {"if", "when", "then", "each", "every", "some", "any",
                      "between", "during", "after", "before", "while"},
    "legal": {"shall", "pursuant", "notwithstanding", "whereas", "hereby",
              "thereof", "therein", "wherein", "herein", "hereinafter",
              "aforementioned", "aforesaid", "such", "said", "any"},
    "academic": {"however", "therefore", "thus", "furthermore", "moreover",
                 "nevertheless", "nonetheless", "consequently", "accordingly"},
    "scientific": set(),
    "commercial": set(),
    "financial": set(),
    "technical": set(),
    "administrative": set(),
}

# Category-specific balanced compression configs
CATEGORY_ABBREV_CONFIG = {
    "general": True,
    "literary": False,
    "scientific": True,
    "commercial": True,
    "philosophical": False,
    "instructional": True,
    "legal": False,
    "financial": True,
    "technical": True,
    "administrative": True,
    "academic": False,
}

CATEGORY_CONNECTOR_REMOVE = {
    "general": True,
    "literary": False,
    "scientific": True,
    "commercial": True,
    "philosophical": False,
    "instructional": False,
    "legal": False,
    "financial": True,
    "technical": True,
    "administrative": True,
    "academic": False,
}


class OptiTokenOptimizer:
    def __init__(self):
        # --- Precompiled patterns (performance + security) ---
        self._JSON_PAT = re.compile(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}')
        self._UNIT_PAT = re.compile(
            r'\b\d+\s*(?:mg|g|kg|mL|L|°C|°F|V|Hz|km/h|mph|%|px|em|rem|ms|GHz|MHz|GB|MB|TB)\b'
            r'|\b\d+\s*[cC]\b|\b\d+\s*colonnes\b|\b\d+\s*fois\b'
        )
        self._FILLERS_PAT = re.compile(r'\b(basically|literally|actually|really|quite|just|vraiment|très|trop|bref|wesh|tkt)\b', re.I)
        self._CONNECTOR_REMOVE_FR = re.compile(r"\b(car|donc|ensuite|puis|alors|pourtant|cependant|toutefois|d'ailleurs|en effet)\b", re.I)
        self._CONNECTOR_REMOVE_EN = re.compile(r'\b(therefore|however|nevertheless|furthermore|moreover|additionally|consequently)\b', re.I)
        self._SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')
        self._MARKDOWN_TABLE_SEP = re.compile(r'\|.*---.*\|')
        self._ABBREV_EN_PAT = re.compile(
            r'\b(?:information|management|approximately|background|with|without|'
            r'introduction|demonstration|organization|technology|documentation|limited)\b', re.I
        )
        self._ABBREV_EN_MAP = {
            "information": "info", "management": "mgmt", "approximately": "~",
            "background": "bg", "with": "w/", "without": "w/o",
            "introduction": "intro", "demonstration": "demo",
            "organization": "org", "technology": "tech",
            "documentation": "docs", "limited": "ltd",
        }

        # --- Stop words ---
        self.tool_words_fr = {
            "le", "la", "les", "un", "une", "des", "de", "du", "est", "sont",
            "était", "étaient", "ai", "as", "avons", "avez", "ont", "être", "été",
            "au", "aux", "ce", "cet", "cette", "ces", "mon", "ton", "son",
            "mes", "tes", "ses", "nos", "vos", "leurs", "je", "tu", "il",
            "elle", "ils", "elles", "me", "te", "se", "leur",
            "ne", "pas", "plus", "mais", "ou", "et", "donc", "car", "ni",
            "dans", "sur", "sous", "avec", "sans", "pour", "par", "chez",
            "entre", "pendant", "depuis", "vers", "y", "en",
            "très", "vraiment", "aujourd'hui", "aussi", "encore", "déjà",
            "peut-être", "plutôt", "surtout", "notamment",
            "alors", "bien", "mal", "peu", "beaucoup",
            "que", "qui", "quoi", "dont", "où",
            "est-ce", "c'est", "cet", "nous", "vous", "ils", "elles",
            "suis", "es", "etes", "sommes", "etes",
            "fait", "faire", "fais", "font",
            "peux", "peut", "pouvons", "peuvent", "pouvez",
            "veux", "veut", "voulons", "veulent", "voulez",
            "dois", "doit", "devons", "doivent", "devez",
            "sais", "sait", "savons", "savent", "savez",
            "rien", "personne", "jamais", "toujours",
            "chaque", "quelque", "plusieurs",
            "car", "comme", "lorsque", "quand", "si",
            "parce", "puisque",
            "leur", "eux", "moi", "toi", "soi",
        }
        self.tool_words_en = {
            "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
            "has", "have", "had", "do", "does", "did", "doing", "having",
            "will", "would", "shall", "should", "can", "could", "may", "might", "must",
            "to", "of", "in", "for", "on", "at", "by", "with", "from", "as",
            "this", "that", "these", "it", "its", "my", "your", "our", "their",
            "me", "him", "her", "us", "them", "i", "you", "we", "he", "she",
            "they", "not", "no", "but", "or", "if", "so", "than",
            "just", "also", "very", "really", "quite", "highly", "extremely",
            "absolutely", "totally", "about", "which", "what", "when", "where",
            "who", "how", "why", "there", "each", "every", "some", "any", "all",
            "both", "few", "many", "much", "several", "here", "now", "then",
            "still", "already", "yet", "only", "well", "even", "too",
            "more", "most", "little", "lot", "lots", "am",
            "such", "own", "same", "another",
            "everything", "nothing", "something",
            "always", "never", "often", "sometimes",
            "i'm", "you're", "he's", "she's", "it's", "we're", "they're",
            "i've", "you've", "we've", "they've",
            "i'll", "you'll", "he'll", "she'll", "it'll", "we'll", "they'll",
            "i'd", "you'd", "he'd", "she'd", "we'd", "they'd",
            "can't", "won't", "don't", "doesn't", "didn't", "isn't", "aren't",
            "wasn't", "weren't", "haven't", "hasn't", "hadn't",
            "wouldn't", "couldn't", "shouldn't", "mustn't",
            "thats", "dont", "cant", "wont", "youre", "its", "theres",
            "whats", "whos", "wheres",
            "please", "thank",
            "able", "need", "want", "like",
        }
        # --- Cancellation triggers ---
        self.cancellation_triggers_fr = [
            "en fait non", "oublie ça", "oubliez ça", "finalement non",
            "au temps pour moi", "non finalement", "annule ça", "ignore ça",
            "laisse tomber", "j'oubliais", "ah oui j'oubliais",
        ]
        self.cancellation_triggers_en = [
            "actually no", "forget that", "forget it", "never mind",
            "scratch that", "on second thought", "wait no", "cancel that",
            "ignore that", "strike that",
        ]
        # --- Meta-discourse patterns (removal) ---
        self.meta_discourse_patterns_fr = [
            (r"\bJe vous écris car\b", ""), (r"\bJe vous écris parce que\b", ""),
            (r"\bSachez que\b", ""), (r"\bVoici mon prompt\b", ""),
            (r"\bVoici ma demande\b", ""), (r"\bVoici ce que je veux\b", ""),
            (r"\bJe voudrais que vous\b", ""), (r"\bJ'aimerais que vous\b", ""),
            (r"\bPourriez-vous\b", ""), (r"\bPouvez-vous\b", ""),
            (r"\bJ'aurais besoin que vous\b", ""),
            (r"\bS'il vous plaît\b", ""), (r"\bs'il vous plaît\b", ""),
            (r"\bMerci (?:beaucoup |infiniment |d'avance |)de?[^.!?]*[.!?]?", ""),
            (r"\bJe vous remercie[^.!?]*[.!?]?", ""),
            (r"\bJe compte sur vous[^.!?]*[.!?]?", ""),
            (r"\bj'espère que vous allez bien\b", ""),
            (r"\bj'espère que vous\b", ""),
            (r"\bj'ai hâte[^.!?]*[.!?]?", ""),
            (r"\bImaginez que vous êtes\b", ""),
            (r"\bImagine que tu es\b", ""),
            (r"\bJe m'égare\b", ""),
            (r"\brevenons à nos moutons\b", ""),
            (r"\bJ'attends votre réponse[^.!?]*[.!?]?", ""),
        ]
        self.meta_discourse_patterns_en = [
            (r"\bI hope you are doing well\b", ""),
            (r"\bI hope this message finds you well\b", ""),
            (r"\bI am writing to\b", ""),
            (r"\bHere is my request\b", ""),
            (r"\bHere is what I need\b", ""),
            (r"\bI would like you to\b", ""),
            (r"\bI want you to\b", ""),
            (r"\bCould you please\b", ""), (r"\bCould you\b", ""),
            (r"\bCan you please\b", ""), (r"\bI need you to\b", ""),
            (r"\bPlease\b", ""), (r"\bplease\b", ""),
            (r"\bThank you[^.!?]*[.!?]?", ""), (r"\bthanks[^.!?]*[.!?]?", ""),
            (r"\bI appreciate[^.!?]*[.!?]?", ""),
            (r"\bKindly\b", ""),
            (r"\bImagine you are\b", ""),
            (r"\bImagine you're\b", ""),
            (r"\bI'm reaching out\b", ""),
            (r"\bI am reaching out\b", ""),
            (r"\bI can't wait[^.!?]*[.!?]?", ""),
            (r"\bI look forward[^.!?]*[.!?]?", ""),
        ]
        # --- Classification patterns ---
        self.greeting_pats = re.compile(
            r'^(bonjour|salut|coucou|hello|hi|hey|dear|cher)\b', re.I
        )
        self.closing_pats = re.compile(
            r'^(merci|(dans l.)attente|bien (à vous|cordialement)|cordialement|'
            r'best regards|regards|sincerely|thanks|thank you)', re.I
        )
        self.role_pats = re.compile(
            r'(agis\s+comme\s+(?:un|une|)\s*|agissez\s+comme\s+(?:un|une|)\s*|'
            r'(?:je\s+)?cherche\s+(?:un|une)\s*|'
            r'(?:tu es|vous êtes|vous etes)\s+(?:un|une)\s*|'
            r'(?:mets-toi|mettez-vous)\s+(?:dans\s+)?(?:la\s+)?peau\s+'
            r'|act as (?:a|an)\s*'
            r'|you are (?:a|an)\s*'
            r'|i need (?:a|an|someone)\s*)',
            re.I
        )
        self.output_pats = re.compile(
            r'(r[ée]ponds?(?:-moi)?\s+(?:sous|uniquement|en)\s+'
            r'(?:forme\s+(?:de\s+)?)?'
            r'(?:tableau|json|liste|bullet\s*points|xml|markdown|'
            r'(?:deux|trois|2|3)\s*(?:colonnes|lignes))'
            r'|réponds[^.]*(?:tableau|json|liste|xml|markdown)'
            r'|format[^.]*(?:json|xml|tableau|table|markdown)'
            r'|output[^.]*(?:json|xml|table|markdown)'
            r'|sous forme de\s+(?:tableau|json|liste))', re.I
        )
        self.constraint_pats = re.compile(
            r'(ne\s+(?:d[ée]passe|doit|pas)|'
            r'(?:ne|n\')\s*(?:dépasse|dépasser|doit|doivent|pas)|'
            r'ne pas[^.]*$|'
            r'do not\s|'
            r'(?:strictement|obligatoirement|impérativement|absolument|'
            r'très\s+important|attention|important[:\s])|'
            r'(?:must\s+|required|mandatory|essential|critical)|'
            r'(?:exactement|ni\s+plus\s+ni\s+moins|exactly)\s+\d+|'
            r'(?:limite?|maximum|minimum|max|min)\b)', re.I
        )
        self.negation_patterns = re.compile(
            r'(ne\s+(?:pas|plus|jamais|rien|personne)|'
            r"n'[a-z]+\s+pas\s+|"
            r'do not |does not |did not |must not |should not |'
            r'without |avoid |never |except |unless |only\s+if\s+not)',
            re.I
        )
        self.strong_verbs_fr = re.compile(
            r'\b(écris|ecris|écrivez|ecrivez|crée|cree|créez|creez|'
            r'génère|genere|générez|generez|développe|developpe|développez|developpez|'
            r'construis|construisez|conçois|concois|concevez|'
            r'produis|produisez|prépare|prepare|préparez|preparez|'
            r'rédige|redige|rédigez|redigez|compose|composez|'
            r'analyse|analysez|résume|resume|résumez|resumez|'
            r'définis|definis|définissez|definissez|'
            r'extrais|extrayez|traduis|traduisez|convertis|convertissez|'
            r'implémente|implemente|implémentez|implementez|'
            r'configure|configurez|déploie|deploie|déployez|deployez|'
            r'optimise|optimisez|utilise|utilisez|'
            r'fais|fait|faire|donne|donnez|fournis|fournissez|'
            r'liste|listez|décris|decris|décrivez|decrivez|explique|expliquez)\b', re.I
        )
        self.strong_verbs_en = re.compile(
            r'\b(write|create|generate|develop|build|design|produce|make|'
            r'prepare|draft|compose|analyze|summarize|outline|define|identify|'
            r'extract|translate|convert|implement|configure|deploy|optimize|refactor|'
            r'tell|give|provide|list|describe|explain|review|check|test|'
            r'recommend|propose|find|search|calculate|use)\b', re.I
        )
        self.task_general_pats = re.compile(
            r'(j[ae]?\s*(?:veux|dois|voudrais|aimerais|ai besoin|cherche)\s+(?:que\s+)?'
            r'(?:vous|tu|on)\s+|'
            r'i\s+(?:need|want|would\s+like)\s+(?:you|the)\s+|'
            r'(?:le|mon|notre)\s*(?:projet|objectif|but|t[âa]che)\s+(?:consiste|est)\s+'
            r'|(?:the|my|our)\s*(?:project|task|goal|objective)\s+(?:involves|is)\s+)', re.I
        )
        self.narrative_digression_pats = re.compile(
            r'(mon\s+cousin|sa\s+soeur|son\s+frère|mon\s+ami|'
            r'l\w+\s+(?:autre\s+)?jour\s+(?:je\s+)?parlais|'
            r'je\s+m\'égare|je\s+m\'egare|'
            r'revenons\s+à\s+nos\s+moutons|'
            r'(?:bon\s+)?bref\s+|'
            r'au\s+dela\s+de\s+cette\s+(?:histoire|anecdote)|'
            r'pour\s+la\s+petite\s+histoire)', re.I
        )

        self.en_sentence_split_abbrevs = _EN_SENTENCE_SPLIT_ABBREVS

    # --- SANCTUARY ---
    def _sanctuary_extract(self, text: str) -> Tuple[str, dict]:
        sanctuary = {}
        counter = [0]
        def token_prefix(): return f"__S{chr(65+counter[0]//26)}{chr(65+counter[0]%26)}__"
        def add_to_sanctuary(m, label):
            token = token_prefix()
            counter[0] += 1
            sanctuary[token] = m.group(0)
            return token

        text = re.sub(r"`[^`\n]+`", lambda m: add_to_sanctuary(m, "INLINE_CODE"), text)
        text = re.sub(r"\$\$[\s\S]*?\$\$", lambda m: add_to_sanctuary(m, "LATEX_BLOCK"), text)
        text = re.sub(r"\$[^$\n]+\$", lambda m: add_to_sanctuary(m, "LATEX_INLINE"), text)
        text = re.sub(r'\$\{[^}]+\}', lambda m: add_to_sanctuary(m, "TEMPLATE_DOLLAR"), text)
        text = re.sub(r'\{\{[^}]+\}\}', lambda m: add_to_sanctuary(m, "TEMPLATE_DOUBLE"), text)
        text = re.sub(r'\{[a-zA-Z_][a-zA-Z0-9_]*\}', lambda m: add_to_sanctuary(m, "TEMPLATE_SINGLE"), text)
        # Safe bounded JSON: max 4 levels, no catastrophic backtracking
        text = re.sub(self._JSON_PAT, lambda m: add_to_sanctuary(m, "JSON_OBJECT"), text)
        text = re.sub(r"https?://[^\s]+", lambda m: add_to_sanctuary(m, "URL"), text)
        text = re.sub(self._UNIT_PAT, lambda m: add_to_sanctuary(m, "UNIT"), text)

        return text, sanctuary

    def _sanctuary_reinject(self, text: str, sanctuary: dict) -> str:
        for token, original in reversed(list(sanctuary.items())):
            text = text.replace(token, original)
        return text

    # --- PRE-PROCESSING ---
    def _is_french(self, text: str) -> bool:
        words = set(re.findall(r'\b\w+\b', text.lower()))
        score = len(words.intersection(self.tool_words_fr))
        return score >= 2

    def _apply_cancellation_filter(self, sentences: List[str], is_fr: bool) -> List[str]:
        triggers = self.cancellation_triggers_fr if is_fr else self.cancellation_triggers_en
        cleaned = []
        for sentence in sentences:
            matched = False
            for trigger in triggers:
                pat = re.compile(r'\b' + re.escape(trigger) + r'\b', re.I)
                if pat.search(sentence):
                    if cleaned:
                        cleaned.pop()
                    parts = pat.split(sentence, maxsplit=1)
                    if parts[0].strip():
                        cleaned.append(parts[0].strip())
                    matched = True
                    break
            if not matched:
                cleaned.append(sentence)
        return cleaned

    def _purge_meta_discourse(self, text: str, is_fr: bool) -> str:
        patterns = self.meta_discourse_patterns_fr if is_fr else self.meta_discourse_patterns_en
        for pat, repl in patterns:
            text = re.sub(pat, repl, text, flags=re.I)
        return text

    def _anti_redundancy_filter(self, sentences: List[str]) -> List[str]:
        if not sentences:
            return []
        kept = [sentences[0]]
        for cur in sentences[1:]:
            s1 = set(re.findall(r'\b\w+\b', kept[-1].lower()))
            s2 = set(re.findall(r'\b\w+\b', cur.lower()))
            if not s1 or not s2:
                kept.append(cur); continue
            jaccard = len(s1.intersection(s2)) / len(s1.union(s2))
            if jaccard <= 0.6:
                kept.append(cur)
        return kept

    # --- SPLIT & CLASSIFICATION ---
    def _split_sentences(self, text: str) -> List[str]:
        for abb in self.en_sentence_split_abbrevs:
            text = text.replace(abb, abb.replace(".", "\x00"))
        raw = re.split(r'(?<=[.!?])\s+', text)
        sentences = []
        for s in raw:
            s = s.replace("\x00", ".")
            if ":" in s and re.search(r'\b\d+\.', s):
                sub = re.split(r'(?=\b\d+\.)', s)
                sentences.extend(p.strip() for p in sub if p.strip())
            elif s.strip():
                sentences.append(s.strip())
        return sentences

    def _refine_sentences(self, sentences: List[str], is_fr: bool) -> List[str]:
        """Split multi-label sentences at logical boundaries (role/task/constraint transitions)."""
        refined = []
        split_pats_en = re.compile(
            r'(?:,\s*)?(?:and|but|while|where|with|that)\s+'
            r'(?=(?:you\s+)?(?:must|should|need|will|can|have\s+to|are\s+to)\s+)',
            re.I
        )
        split_pats_fr = re.compile(
            r'(?:,\s*)?(?:et|mais|où|avec|que|qui)\s+'
            r'(?=(?:vous\s+)?(?:devez|devriez|pouvez|devez|allez|êtes\s+tenu|ne\s+doit|ne\s+pouvez|ne\s+pas)\s+)',
            re.I
        )
        for s in sentences:
            label = self._classify_sentence(s, is_fr)
            if label == 'context':
                # Try to split compound context sentences
                pat = split_pats_fr if is_fr else split_pats_en
                parts = pat.split(s)
                if len(parts) > 1:
                    for p in parts:
                        p = p.strip().rstrip(',')
                        if p:
                            refined.append(p)
                    continue
            refined.append(s)
        return refined

    def _classify_sentence(self, sentence: str, is_fr: bool) -> str:
        sl = sentence.lower()
        if re.search(self.greeting_pats, sl): return 'greeting'
        if re.search(self.closing_pats, sl): return 'closing'
        if re.search(self.role_pats, sl): return 'role'
        if re.search(self.output_pats, sl): return 'output_format'
        if re.search(self.constraint_pats, sl): return 'constraint'
        verbs = self.strong_verbs_fr if is_fr else self.strong_verbs_en
        if re.search(verbs, sl):
            if re.search(self.negation_patterns, sl):
                return 'constraint'
            return 'task'
        if re.search(self.task_general_pats, sl): return 'task'
        if re.search(r'^(\s*[-*+•]|\s*\d+\.)', sentence): return 'structure_item'
        if re.search(self.narrative_digression_pats, sl): return 'uncertain'
        return 'context'

    # --- COMPRESSION STRATÉGIES ---
    def _clean_light_text(self, text: str, is_fr: bool) -> str:
        text = re.sub(r'!{2,}', '!', text)
        text = re.sub(r'\?{2,}', '?', text)
        fillers = r'\b(basically|literally|actually|really|quite|just|vraiment|très|trop|bref|wesh|tkt)\b'
        text = re.sub(fillers, '', text, flags=re.I)
        return re.sub(r'\s+', ' ', text).strip()

    def _detect_category(self, text: str, is_fr: bool) -> str:
        t = text.lower()
        scores = {c: 0 for c in CATEGORIES}

        def _count(pattern: str, weight: int = 3) -> int:
            return len(re.findall(pattern, t, re.I)) * weight

        # Scientific: tech terms, numbers, units, formulas
        scores["scientific"] += _count(r'\b(algorithm|function|api|json|database|server|protocol|syntax|compiler|debug|temperature|voltage|frequency|data|analysis|hypothesis|experiment|study|methodology|calculate|compute|measure|calibration|specimen|protocol|laboratory)\b', 3)
        scores["scientific"] += _count(r'\b\d+\.\d+\b|\b\d+\s*(mg|g|kg|ml|l|°[cCfF]|v|hz|ghz|mhz|gb|mb|tb|%|px)\b', 2)
        scores["scientific"] += _count(r'\b(define|implement|configure|parse|validate|optimize|benchmark)\b', 1)

        # Literary: narrative, dialog, metaphor, style words
        scores["literary"] += _count(r'\b(metaphor|narrative|story|poem|chapter|character|plot|scene|dialogue|atmosphere|mood|tone|voice|style|imagine|fairy\s+tale|novel|essay|protagonist|verse|prose|fiction)\b', 3)
        scores["literary"] += _count(r'\b(feel|felt|emotion|passion|dream|wonder|beautiful|sad|joy|hope|remember|forget)\b', 2)

        # Commercial: marketing, sales, business language
        scores["commercial"] += _count(r'\b(buy|sell|purchase|discount|offer|promo|save|price|cost|revenue|profit|market|campaign|brand|customer|client|audience|convert|lead|sales|roi|cta|landing|funnel|promotion|loyalty|acquisition)\b', 3)
        scores["commercial"] += _count(r'\b(unique|exclusive|limited|guaranteed|proven|results|growth|scalable|solution|value)\b', 2)

        # Philosophical: abstract reasoning
        scores["philosophical"] += _count(r'\b(therefore|hence|thus|since|because|premise|conclusion|argument|logic|reason|essence|existence|cause|effect|nature|reality|truth|knowledge|consciousness|paradox|dialectic|categorical|imperative)\b', 3)
        scores["philosophical"] += _count(r'\b(think|believe|consider|reflect|contemplate|examine|question|ponder|conceive)\b', 2)

        # Instructional: how-to, steps, tutorials, guides
        scores["instructional"] += _count(r'\b(step|steps|how\s+to|tutorial|guide|instructions|first|second|next|then|finally|begin|start|end|repeat|while|procedure|follow)\b', 3)
        scores["instructional"] += _count(r'\b(method|approach|technique|process|workflow)\b', 2)

        # Legal: contract, clause, liability, legal terms
        scores["legal"] += _count(r'\b(contract|agreement|clause|party|obligation|liability|indemnify|termination|breach|warrant|governing\s*law|jurisdiction|arbitration|confidentiality|hereby|notwithstanding|pursuant|thereof|therein|wherein)\b', 3)
        scores["legal"] += _count(r'\b(shall|indemnification|dispute|enforceable|covenant|representation|warranty)\b', 2)

        # Financial: revenue, profit, asset, fiscal terms
        scores["financial"] += _count(r'\b(revenue|profit|loss|asset|liability|equity|depreciation|amortization|dividend|shareholder|fiscal|audit|budget|forecast|margin|earnings|ebitda)\b', 3)
        scores["financial"] += _count(r'\b(investment|capital|expense|tax|valuation|liquidity|solvency|interest)\b', 2)

        # Technical: specification, architecture, protocol, deployment
        scores["technical"] += _count(r'\b(specification|requirement|architecture|interface|protocol|implementation|deployment|configuration|parameter|threshold|throughput|latency|bandwidth|redundancy|scalability|deploy)\b', 3)
        scores["technical"] += _count(r'\b(endpoint|middleware|cache|proxy|pipeline|orchestration|container|microservice)\b', 2)

        # Administrative: policy, procedure, regulation, compliance
        scores["administrative"] += _count(r'\b(policy|procedure|regulation|compliance|guideline|directive|memorandum|circular|submission|approval|authorization|certification|standard)\b', 3)
        scores["administrative"] += _count(r'\b(governance|oversight|mandate|statutory|regulatory|enforcement|reporting)\b', 2)

        # Academic: paper, publication, citation, thesis
        scores["academic"] += _count(r'\b(paper|publication|citations?|references?|bibliography|abstract|introduction|thesis|dissertation|peer[-\s]review|journals?|conference)\b', 3)
        scores["academic"] += _count(r'\b(academic|scholar|curriculum|pedagogy|syllabus|lecture|seminar|methodology)\b', 2)

        best = max(scores, key=scores.get)
        return best if scores[best] >= 2 else "general"

    def _compress_sentence_balanced(self, text: str, is_fr: bool, category: str = "general") -> str:
        fillers = r'\b(basically|literally|actually|really|quite|just|vraiment|tres|trop|bref|wesh|tkt)\b'
        text = re.sub(fillers, '', text, flags=re.I)
        text = re.sub(r'!{2,}', '!', text)
        text = re.sub(r'\?{2,}', '?', text)

        # Framing removal (universal)
        framing_pats = [
            r"\b(what i want you to do is to|what i need is|your task is to|the goal is to|your job is to|the objective is to)\b",
            r"\b(ce que je veux que vous fassiez|votre tache consiste a|l'objectif est de|le but est de|la tache est de)\b",
            r"\b(imagine que tu es|imaginez que vous etes|imagine you are|imagine you're)\b",
            r"\b(je voudrais que vous me|j'aimerais que tu|je voudrais que tu|j'aimerais que vous)\b",
            r"\b(il faut que vous|il faut que tu|i need you to|i want you to)\b",
            r"\b(i think|i believe|i feel|i guess|i suppose|maybe|perhaps|probably)\b",
            r"\b(je pense|je crois|je trouve|peut-etre|probablement)\b",
        ]
        for pat in framing_pats:
            text = re.sub(pat, '', text, flags=re.I)

        # Connectors: category-aware
        if CATEGORY_CONNECTOR_REMOVE.get(category, True):
            text = self._CONNECTOR_REMOVE_FR.sub('', text) if is_fr else self._CONNECTOR_REMOVE_EN.sub('', text)

        # Abbreviations: category-aware (single alternation pass)
        if CATEGORY_ABBREV_CONFIG.get(category, True):
            if is_fr:
                text = re.sub(r'\bet\b', '&', text, flags=re.I)
                text = re.sub(r'\bpar exemple\b', 'ex', text, flags=re.I)
            else:
                text = re.sub(r'\band\b', '&', text, flags=re.I)
                text = self._ABBREV_EN_PAT.sub(lambda m: self._ABBREV_EN_MAP.get(m.group(0).lower(), m.group(0)), text)

        return re.sub(r'\s+', ' ', text).strip()

    def _compress_sentence_aggressive(self, text: str, is_fr: bool, category: str = "general") -> str:
        negation_keep = {"ne","pas","ni","rien","jamais","personne","aucun","aucune",
                         "not","no","nor","never","neither","none","nobody","nothing","nowhere"}
        words = text.split()
        compressed = []
        # Category-specific tool words: remove keep-words from stop list
        keep_fr = CATEGORY_KEEP_WORDS_FR.get(category, set())
        keep_en = CATEGORY_KEEP_WORDS_EN.get(category, set())

        for w in words:
            clean_w = re.sub(r'[^\w]', '', w.lower())
            if "__" in w:
                compressed.append(w)
                continue
            if clean_w in keep_fr or clean_w in keep_en:
                compressed.append(w)
                continue
            # Preserve negation words to avoid flipping meaning
            if clean_w in negation_keep:
                compressed.append(w)
                continue
            stop = self.tool_words_fr if is_fr else self.tool_words_en
            if clean_w not in stop or clean_w in (keep_fr if is_fr else keep_en):
                compressed.append(w)
        result = " ".join(compressed)

        bpe_en = {
            "leads to": "->", "results in": "->", "produces": "->",
            "yields": "->", "gives": "->",
            "is defined as": "=", "is equal to": "=",
            "is equivalent to": "==", "is composed of": ":",
            "consists of": ":", "contains": ":",
            "and": "&", "between": "-",
        }
        bpe_fr = {
            "mène à": "->", "amène à": "->", "conduit à": "->",
            "produit": "->", "donne": "->",
            "est défini comme": "=", "est égal à": "=",
            "est équivalent à": "==", "est composé de": ":",
            "se compose de": ":", "contient": ":",
            "et": "&", "entre": "-",
        }
        bpe = bpe_fr if is_fr else bpe_en
        for k, v in bpe.items():
            result = re.sub(r'\b' + k + r'\b', v, result, flags=re.I)

        return result

    def _original_aggressive(self, classified: dict, is_fr: bool, category: str) -> str:
        lignes = []
        if classified['role']:
            lignes.append(f"Role: {self._compress_sentence_aggressive(' '.join(classified['role']), is_fr, category)}")
        if classified['task']:
            lignes.append(f"Task: {self._compress_sentence_aggressive(' '.join(classified['task']), is_fr, category)}")
        specs = classified['constraint'] + classified['output_format'] + classified['structure_item']
        if specs:
            lignes.append("Specs:")
            for spec in specs:
                cs = self._compress_sentence_aggressive(spec, is_fr, category)
                if cs.strip():
                    lignes.append(f"  * {cs}")
        return "\n".join(lignes)

    # --- MAIN OPTIMIZE ---
    def optimize(self, raw_prompt: str, category: str = None, spc_enabled: bool = True,
                 progress_callback=None, refine_with_llm: bool = False) -> Dict[str, dict]:
        original = raw_prompt.strip()
        if progress_callback:
            progress_callback("sanctuary", 3)

        # Phase 1: Sanctuary
        protected, sanctuary = self._sanctuary_extract(original)
        if progress_callback:
            progress_callback("language", 8)

        # Phase 2: Langue & Nettoyage
        is_fr = self._is_french(protected)
        processed = self._purge_meta_discourse(protected, is_fr)
        if progress_callback:
            progress_callback("parsing", 15)

        # Phase 3: Split, refine, annulation, dédup
        raw_sentences = self._split_sentences(processed)
        refined = self._refine_sentences(raw_sentences, is_fr)
        after_cancel = self._apply_cancellation_filter(refined, is_fr)
        final = self._anti_redundancy_filter(after_cancel)
        if progress_callback:
            progress_callback("classification", 22)

        # Phase 4: Classification
        classified = {k: [] for k in ('role', 'task', 'output_format', 'constraint', 'structure_item', 'context', 'greeting', 'closing', 'uncertain')}
        for s in final:
            label = self._classify_sentence(s, is_fr)
            if label in classified:
                classified[label].append(s)
        if progress_callback:
            progress_callback("category", 27)

        # Phase 5: Catégorie (auto-detect if not provided)
        if category is None:
            category = self._detect_category(original, is_fr)
        if progress_callback:
            progress_callback("light", 35)

        # --- LIGHT (original order, exclude greeting/closing/uncertain per spec) ---
        skip_labels = {'greeting', 'closing', 'uncertain'}
        light_sentences = []
        for s in final:
            label = self._classify_sentence(s, is_fr)
            if label in skip_labels:
                continue
            light_sentences.append(self._clean_light_text(s, is_fr))
        light_prompt = " ".join(light_sentences)
        light_prompt = self._sanctuary_reinject(light_prompt, sanctuary)
        if progress_callback:
            progress_callback("balanced", 45)

        # --- BALANCED ---
        def _nonempty(ls):
            return [x for x in ls if x.strip()]
        blocks = []
        header_map = {'role':'Role','task':'Task','context':'Context','constraint':'Constraints','output_format':'Output Format'}
        for key, header in header_map.items():
            if key in ('constraint',):
                combined = _nonempty(classified.get('constraint',[]) + classified.get('structure_item',[]))
                if not combined:
                    continue
                compressed = [f"- {self._compress_sentence_balanced(c, is_fr, category)}" for c in combined]
                blocks.append((f"## {header}\n" + "\n".join(compressed), " ".join(compressed)))
            elif key == 'structure_item':
                continue
            else:
                raw = _nonempty(classified.get(key,[]))
                if not raw:
                    continue
                inline = self._compress_sentence_balanced(' '.join(raw), is_fr, category)
                blocks.append((f"## {header}\n{inline}", inline))
        sectioned = "\n\n".join(b for b, _ in blocks)
        inlined = " | ".join(i for _, i in blocks)
        balanced_prompt = sectioned if len(sectioned) <= len(inlined) else inlined
        if len(balanced_prompt) > len(light_prompt) and inlined != light_prompt:
            balanced_prompt = light_prompt
        balanced_prompt = self._sanctuary_reinject(balanced_prompt, sanctuary)
        if progress_callback:
            progress_callback("spc_base", 55)

        # --- SPC BASE (protection sémantique post-syntaxique) ---
        spc_base = ""
        if spc_enabled:
            try:
                from .spc.pipeline import SPC as SemanticCompiler
                from .spc.profiles import SAFE as SPC_SAFE
                clean_parts = []
                for key in ('role', 'task', 'context', 'constraint', 'output_format'):
                    items = classified.get(key, [])
                    if items:
                        clean_parts.append(" ".join(items))
                clean_text = " ".join(clean_parts) if clean_parts else " ".join(final)
                if len(clean_text.strip()) > 50:
                    sv = SemanticCompiler(profile=SPC_SAFE)
                    sr = sv.compile(clean_text)
                    spc_base = sr.compressed
            except Exception as exc:
                spc_base = ""
                logging.warning("SPC layer failed: %s", exc)
        spc_base = self._sanctuary_reinject(spc_base, sanctuary) if spc_base else ""

        # --- POST-SPC: Balanced enrichi par SPC (si dispo) ---
        if spc_base:
            balanced_prompt = spc_base

        if progress_callback:
            progress_callback("aggressive", 60)

        # --- AGGRESSIVE : SPC Aggressive pipeline (semantic_chunk + neural + rules) ---
        aggressive_prompt = ""
        if spc_enabled and len(clean_text.strip()) > 50:
            try:
                from .spc.pipeline import SPC as SPCCompiler
                from .spc.profiles import AGGRESSIVE as SPC_AGGRESSIVE

                cagg = SPCCompiler(profile=SPC_AGGRESSIVE)
                ragg = cagg.compile(clean_text)
                aggressive_prompt = ragg.compressed
            except Exception as exc:
                logging.warning("SPC aggressive pipeline failed: %s", exc)

        # Fallback: stop-word removal si pipeline SPC indisponible
        if not aggressive_prompt:
            if spc_base:
                agg_sentences = self._split_sentences(spc_base) if len(spc_base) > 0 else final
                compressed_sents = [self._compress_sentence_aggressive(s, is_fr, category) for s in agg_sentences if s.strip()]
                aggressive_prompt = "\n".join(compressed_sents) if compressed_sents else self._compress_sentence_aggressive(spc_base, is_fr, category)
            else:
                aggressive_prompt = self._original_aggressive(classified, is_fr, category)
        aggressive_prompt = self._sanctuary_reinject(aggressive_prompt, sanctuary)

        if progress_callback:
            progress_callback("max_industrial", 75)

        # --- MAX / INDUSTRIAL : SPC natif (KOMPRESS neural + semantic_chunk + rules) ---
        max_prompt = ""
        industrial_prompt = ""
        if spc_enabled and len(clean_text.strip()) > 50:
            try:
                from .spc.pipeline import SPC as SPCCompiler
                from .spc.profiles import MAX as SPC_MAX, INDUSTRIAL as SPC_INDUSTRIAL

                cmax = SPCCompiler(profile=SPC_MAX)
                rmax = cmax.compile(clean_text)
                max_prompt = rmax.compressed

                cind = SPCCompiler(profile=SPC_INDUSTRIAL)
                rind = cind.compile(clean_text)
                industrial_prompt = rind.compressed
            except Exception as exc:
                logging.warning("SPC max/industrial failed: %s", exc)
        max_prompt = self._sanctuary_reinject(max_prompt, sanctuary) if max_prompt else ""
        industrial_prompt = self._sanctuary_reinject(industrial_prompt, sanctuary) if industrial_prompt else ""

        if progress_callback:
            progress_callback("saving", 95)

        # --- Couche 2 : Gray Zone Refine (optionnel, post-processing LLM local) ---
        if refine_with_llm:
            try:
                from .spc.gray_zone import GrayZoneRouter, GrayZone
                from .spc.llama_cpp import LlamaCpp

                _llm = LlamaCpp()
                _router = GrayZoneRouter(llm=_llm)
                if _router.is_available():
                    for _mode_key, _txt in (
                        ("aggressive", aggressive_prompt),
                        ("max", max_prompt),
                        ("industrial", industrial_prompt),
                    ):
                        if _txt and len(_txt) > 30:
                            _refined, _meta = _router.refine(
                                text=_txt,
                                original=original,
                                zone=GrayZone.CAUSAL_VALIDATION,
                            )
                            if _meta.get("llm_called") and _refined:
                                if _mode_key == "aggressive":
                                    aggressive_prompt = _refined
                                elif _mode_key == "max":
                                    max_prompt = _refined
                                else:
                                    industrial_prompt = _refined
            except Exception as exc:
                logging.warning("Gray zone refine failed: %s", exc)

        return {
            "light": {
                "label": "Light",
                "description": "Retrait du bruit conversationnel, intégrité grammaticale.",
                "prompt": light_prompt,
            },
            "balanced": {
                "label": "Balanced",
                "description": "Restructuration logique, suppression des digressions narratives, compression sémantique.",
                "prompt": balanced_prompt,
            },
            "aggressive": {
                "label": "Agressive",
                "description": "Style télégraphique ultra-dense sur base SPC — préserve contraintes et négations.",
                "prompt": aggressive_prompt,
            },
            "max": {
                "label": "Max",
                "description": "SPC profile MAX: all rule-based + KOMPRESS neural token compression.",
                "prompt": max_prompt or aggressive_prompt,
            },
            "industrial": {
                "label": "Industrial",
                "description": "SPC profile INDUSTRIAL: production-grade KOMPRESS neural + full rule-based compression.",
                "prompt": industrial_prompt or aggressive_prompt,
            },
            "_meta": {
                "category": category,
            },
        }


# --- WRAPPER API COMPATIBLE AVEC app.py ---
def optimize_locally(prompt: str, category: str = None, spc_enabled: bool = True, refine_with_llm: bool = False) -> dict:
    opt = OptiTokenOptimizer()
    result = opt.optimize(prompt, category=category, spc_enabled=spc_enabled, refine_with_llm=refine_with_llm)
    _meta = result.pop("_meta", {})
    changes_light = [{"type": "light_clean", "description": "Nettoyage conversationnel"}]
    changes_balanced = [{"type": "balanced_restruct", "description": "Restructuration par blocs + compression"}]
    changes_aggressive = [{"type": "spc_aggressive", "description": "SPC AGGRESSIVE: semantic chunk + KOMPRESS neural + rules"}]
    changes_max = [{"type": "spc_max", "description": "SPC MAX: all rule-based + KOMPRESS neural + semantic chunk filter"}]
    changes_industrial = [{"type": "spc_industrial", "description": "SPC INDUSTRIAL: production-grade KOMPRESS + full rules + quality validation"}]
    return {
        "versions": [
            {**result["light"], "changes_made": changes_light},
            {**result["balanced"], "changes_made": changes_balanced},
            {**result["aggressive"], "changes_made": changes_aggressive},
            {**result["max"], "changes_made": changes_max},
            {**result["industrial"], "changes_made": changes_industrial},
        ],
        "category": _meta.get("category", category or "general"),
    }


def optimize_prompt(prompt: str, optimizer_model: str = None, provider: str = None, api_key: str = None, category: str = None) -> dict:
    if api_key and provider == "openai":
        try:
            result = _optimize_with_openai(prompt, optimizer_model, api_key)
            return {"versions": result, "category": category or "general"}
        except Exception as e:
            return optimize_locally(prompt, category=category)

    if api_key and provider == "anthropic":
        try:
            result = _optimize_with_anthropic(prompt, optimizer_model, api_key)
            return {"versions": result, "category": category or "general"}
        except Exception as e:
            return optimize_locally(prompt, category=category)

    if api_key and provider == "google":
        try:
            result = _optimize_with_google(prompt, optimizer_model, api_key)
            return {"versions": result, "category": category or "general"}
        except Exception as e:
            return optimize_locally(prompt, category=category)

    return optimize_locally(prompt, category=category)


def _optimize_with_openai(prompt: str, model: str, api_key: str) -> list:
    import openai
    openai.api_key = api_key
    resp = openai.chat.completions.create(
        model=model or "gpt-4",
        messages=[
            {"role": "system", "content": OPTIMIZER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    return _parse_api_response(resp.choices[0].message.content, prompt)


def _optimize_with_anthropic(prompt: str, model: str, api_key: str) -> list:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model or "claude-3-5-sonnet-20241022",
        max_tokens=4096,
        system=OPTIMIZER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_api_response(resp.content[0].text, prompt)


def _optimize_with_google(prompt: str, model: str, api_key: str) -> list:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    gmodel = genai.GenerativeModel(model or "gemini-pro")
    resp = gmodel.generate_content(
        contents=prompt,
        generation_config={"temperature": 0.3},
    )
    return _parse_api_response(resp.text, prompt)


def _parse_api_response(text: str, original: str) -> list:
    try:
        data = json.loads(text)
        versions = data.get("versions", [])
        if isinstance(versions, list) and len(versions) >= 3:
            return versions
    except (json.JSONDecodeError, AttributeError):
        pass
    # Fallback direct
    return optimize_locally(original)


if __name__ == "__main__":
    opt = OptiTokenOptimizer()
    crash = """
    Bonjour cher assistant IA, j'espere que vous allez tres bien aujourd'hui.
    Imaginez que vous etes un expert en marketing digital.
    Je voudrais que vous me redigiez une campagne d'emailing pour le "Miaou-Ecolo 3000".
    Cependant, faites tres attention: vous devez me repondre sous forme de tableau a deux colonnes.
    Le ton doit etre humoristique mais professionnel.
    Vous devez obligatoirement inclure exactement trois fois le mot "croquette".
    Merci infiniment d'avance pour votre aide!
    """
    results = opt.optimize(crash)
    for mode, data in results.items():
        print(f"\n=================== MODE {data['label'].upper()} ===================")
        print(data['prompt'])
