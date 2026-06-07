import json
import re
import os
import requests
import google.generativeai as genai
from typing import List, Dict, Optional, Tuple
from backend.token_counter import count_tokens

OPTIMIZER_SYSTEM_PROMPT = """You are PromptCompress, an expert prompt optimization engine..."""

_EN_SENTENCE_SPLIT_ABBREVS = ["Mr.", "Dr.", "M.", "Mme.", "i.e.", "e.g.", "cf."]

CATEGORIES = ["general", "literary", "scientific", "commercial", "philosophical", "instructional"]

# Category-specific tool words: which words to KEEP (excluded from stop list) vs general
CATEGORY_KEEP_WORDS_FR = {
    "literary": {"je", "tu", "il", "elle", "nous", "vous", "ils", "mon", "ton",
                 "son", "mes", "tes", "ses", "sa", "notre", "votre", "leur",
                 "mais", "donc", "et", "car", "ni", "ou", "parce", "comme",
                 "quand", "lorsque", "si", "puis", "alors", "pourtant", "cependant"},
    "philosophical": {"donc", "car", "mais", "or", "ni", "parce", "puisque",
                      "alors", "donc", "en effet", "cependant", "néanmoins",
                      "toutefois", "pourtant", "si", "donc", "ainsi"},
    "instructional": {"si", "quand", "lorsque", "chaque", "quelque", "plusieurs",
                      "entre", "depuis", "pendant", "avant", "après"},
    "scientific": set(),  # keep general defaults
    "commercial": set(),
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
    "scientific": set(),
    "commercial": set(),
}

# Category-specific balanced compression configs
CATEGORY_ABBREV_CONFIG = {
    "general": True,
    "literary": False,  # No abbrevs in literary
    "scientific": True,
    "commercial": True,
    "philosophical": False,  # No abbrevs in philosophical (keep formal tone)
    "instructional": True,
}

CATEGORY_CONNECTOR_REMOVE = {
    "general": True,
    "literary": False,  # Keep connectors for flow
    "scientific": True,
    "commercial": True,
    "philosophical": False,  # Keep connectors for logic
    "instructional": False,  # Keep connectors for sequence
}


class OptiTokenOptimizer:
    def __init__(self):
        # --- Langue ---
        self.fr_stop_words = {
            "bonjour", "merci", "s'il vous plaît", "je", "vous", "nous",
            "c'est", "j'ai", "très", "vraiment", "pour", "avec", "cette",
            "cet", "ces", "mon", "ton", "son", "mes", "tes", "ses",
            "nos", "vos", "leurs", "mais", "donc", "car", "ni", "où",
            "dans", "sur", "sous", "entre", "pendant", "depuis", "désormais",
            "aujourd'hui", "bien", "mal", "peu", "beaucoup", "trop",
            "aussi", "ensuite", "puis", "enfin", "alors", "pourtant",
            "cependant", "toutefois", "néanmoins", "certes", "plutôt",
            "surtout", "notamment", "c'est-à-dire", "c'est pourquoi",
            "faire", "fais", "fait", "fallait", "faut",
            "veux", "peux", "dois", "sais", "connais",
        }
        self.en_stop_words = set()
        # --- Tool words (aggressive stop words) ---
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
            "has", "have", "had", "do", "does", "did", "will", "would", "shall",
            "should", "can", "could", "may", "might", "must",
            "to", "of", "in", "for", "on", "at", "by", "with", "from", "as",
            "this", "that", "these", "it", "its", "my", "your", "our", "their",
            "me", "him", "her", "us", "them", "i", "you", "we", "he", "she",
            "they", "not", "no", "but", "or", "if", "so", "than",
            "just", "also", "very", "really", "quite", "highly", "extremely",
            "absolutely", "totally", "about", "which", "what", "when", "where",
            "who", "how", "why", "there", "each", "every", "some", "any", "all",
            "both", "few", "many", "much", "several", "here", "now", "then",
            "still", "already", "yet", "only", "well", "even", "too",
            "more", "most", "little", "lot", "lots",
            "such", "own", "same", "another",
            "everything", "nothing", "something",
            "always", "never", "often", "sometimes",
            "am", "are", "is", "was", "were", "being", "been",
            "have", "has", "had", "having", "do", "does", "did", "doing",
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
            "able", "need", "want", "like", "would",
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
        # Template variables: ${...}, {{...}}, {simple_var}
        text = re.sub(r'\$\{[^}]+\}', lambda m: add_to_sanctuary(m, "TEMPLATE_DOLLAR"), text)
        text = re.sub(r'\{\{[^}]+\}\}', lambda m: add_to_sanctuary(m, "TEMPLATE_DOUBLE"), text)
        text = re.sub(r'\{[a-zA-Z_][a-zA-Z0-9_]*\}', lambda m: add_to_sanctuary(m, "TEMPLATE_SINGLE"), text)
        json_pat = r'\{(?:[^{}]|\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})*\}'
        text = re.sub(json_pat, lambda m: add_to_sanctuary(m, "JSON_OBJECT"), text)
        text = re.sub(r"https?://[^\s]+", lambda m: add_to_sanctuary(m, "URL"), text)
        unit_pat = r'\b\d+\s*(mg|g|kg|mL|L|°C|°F|V|Hz|km/h|mph|%|px|em|rem|ms|GHz|MHz|GB|MB|TB)\b|\b\d+\s*[cC]\b|\b\d+\s*colonnes\b|\b\d+\s*fois\b'
        text = re.sub(unit_pat, lambda m: add_to_sanctuary(m, "UNIT"), text)

        return text, sanctuary

    def _sanctuary_reinject(self, text: str, sanctuary: dict) -> str:
        for token, original in reversed(list(sanctuary.items())):
            text = text.replace(token, original)
        return text

    # --- PRE-PROCESSING ---
    def _is_french(self, text: str) -> bool:
        words = set(re.findall(r'\b\w+\b', text.lower()))
        score = len(words.intersection(self.fr_stop_words))
        return score >= 2

    def _apply_cancellation_filter(self, sentences: List[str], is_fr: bool) -> List[str]:
        triggers = self.cancellation_triggers_fr if is_fr else self.cancellation_triggers_en
        cleaned = []
        for sentence in sentences:
            matched = False
            for trigger in triggers:
                if re.search(r'\b' + trigger + r'\b', sentence.lower()):
                    if cleaned:
                        cleaned.pop()
                    parts = re.split(r'\b' + trigger + r'\b', sentence, flags=re.I)
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

        # Scientific: tech terms, numbers, units, formulas
        if re.search(r'\b(algorithm|function|api|json|api|database|server|protocol|syntax|compiler|debug|temperature|voltage|frequency|data|analysis|hypothesis|experiment|study|methodology|calculate|compute|measure)\b', t):
            scores["scientific"] += 3
        if re.search(r'\b\d+\.\d+|\b\d+\s*(mg|g|kg|ml|l|°c|°f|v|hz|ghz|mhz|gb|mb|tb|%|px)\b', t, re.I):
            scores["scientific"] += 2
        if re.search(r'\b(define|implement|configure|parse|validate|optimize|benchmark)\b', t):
            scores["scientific"] += 1

        # Literary: narrative, dialog, metaphor, style words
        if re.search(r'\b(metaphor|narrative|story|poem|chapter|character|plot|scene|dialogue|atmosphere|mood|tone|voice|style|imagine|once upon|fairy tale|novel|essay)\b', t):
            scores["literary"] += 3
        if re.search(r'\b(feel|felt|emotion|passion|dream|wonder|beautiful|sad|joy|hope|remember|forget)\b', t):
            scores["literary"] += 2

        # Commercial: marketing, sales, business language
        if re.search(r'\b(buy|sell|purchase|discount|offer|promo|save|price|cost|revenue|profit|market|campaign|brand|customer|client|audience|convert|lead|sales|roi|cta|landing|funnel)\b', t):
            scores["commercial"] += 3
        if re.search(r'\b(unique|exclusive|limited|guaranteed|proven|results|growth|scalable|solution|value)\b', t):
            scores["commercial"] += 2

        # Philosophical: abstract reasoning
        if re.search(r'\b(therefore|hence|thus|since|because|if.*then|premise|conclusion|argument|logic|reason|essence|existence|cause|effect|nature|reality|truth|knowledge|consciousness|paradox|dialectic|categorical|imperative)\b', t):
            scores["philosophical"] += 3
        if re.search(r'\b(think|believe|consider|reflect|contemplate|analyze|examine|question|ponder|conceive)\b', t):
            scores["philosophical"] += 2

        # Instructional: steps, procedures, instructions
        if re.search(r'\b(step|first|second|then|next|finally|procedure|instruction|guide|tutorial|how to|follow|repeat|sequence|phase|stage)\b', t):
            scores["instructional"] += 3
        if re.search(r'\b(click|select|choose|enter|type|press|open|close|install|setup|configure|create new|navigate|scroll|drag|drop)\b', t):
            scores["instructional"] += 2

        # Short text heuristic: if too short for reliable detection, default to general
        if len(t.split()) < 10:
            return "general"

        best = max(scores, key=lambda k: scores[k])
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
            if is_fr:
                text = re.sub(r"\b(car|donc|ensuite|puis|alors|pourtant|cependant|toutefois|d'ailleurs|en effet)\b", '', text, flags=re.I)
            else:
                text = re.sub(r'\b(therefore|however|nevertheless|furthermore|moreover|additionally|consequently)\b', '', text, flags=re.I)

        # Abbreviations: category-aware
        if CATEGORY_ABBREV_CONFIG.get(category, True):
            abbrevs_en = {
                "information": "info", "management": "mgmt", "approximately": "~",
                "background": "bg", "with": "w/", "without": "w/o",
                "introduction": "intro", "demonstration": "demo",
                "organization": "org", "technology": "tech",
                "documentation": "docs", "limited": "ltd",
            }
            if is_fr:
                text = re.sub(r'\bet\b', '&', text, flags=re.I)
                text = re.sub(r'\bpar exemple\b', 'ex', text, flags=re.I)
            else:
                text = re.sub(r'\band\b', '&', text, flags=re.I)
                for k, v in abbrevs_en.items():
                    text = re.sub(r'\b' + k + r'\b', v, text, flags=re.I)

        return re.sub(r'\s+', ' ', text).strip()

    def _compress_sentence_aggressive(self, text: str, is_fr: bool, category: str = "general") -> str:
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

    # --- MAIN OPTIMIZE ---
    def optimize(self, raw_prompt: str, category: str = None) -> Dict[str, dict]:
        original = raw_prompt.strip()

        # Phase 1: Sanctuary
        protected, sanctuary = self._sanctuary_extract(original)

        # Phase 2: Langue & Nettoyage
        is_fr = self._is_french(protected)
        processed = self._purge_meta_discourse(protected, is_fr)

        # Phase 3: Split, refine, annulation, dédup
        raw_sentences = self._split_sentences(processed)
        refined = self._refine_sentences(raw_sentences, is_fr)
        after_cancel = self._apply_cancellation_filter(refined, is_fr)
        final = self._anti_redundancy_filter(after_cancel)

        # Phase 4: Classification
        classified = {k: [] for k in ('role', 'task', 'output_format', 'constraint', 'structure_item', 'context', 'greeting', 'closing', 'uncertain')}
        for s in final:
            label = self._classify_sentence(s, is_fr)
            if label in classified:
                classified[label].append(s)

        # Phase 5: Catégorie (auto-detect if not provided)
        if category is None:
            category = self._detect_category(original, is_fr)

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
        # Choose shorter: sections or inline; fallback to light if still longer
        sectioned = "\n\n".join(b for b, _ in blocks)
        inlined = " | ".join(i for _, i in blocks)
        balanced_prompt = sectioned if len(sectioned) <= len(inlined) else inlined
        if len(balanced_prompt) > len(light_prompt) and inlined != light_prompt:
            balanced_prompt = light_prompt
        balanced_prompt = self._sanctuary_reinject(balanced_prompt, sanctuary)

        # --- AGGRESSIVE ---
        lines = []
        if classified['role']:
            lines.append(f"Role: {self._compress_sentence_aggressive(' '.join(classified['role']), is_fr, category)}")
        if classified['task']:
            lines.append(f"Task: {self._compress_sentence_aggressive(' '.join(classified['task']), is_fr, category)}")
        specs = classified['constraint'] + classified['output_format'] + classified['structure_item']
        if specs:
            lines.append("Specs:")
            for spec in specs:
                cs = self._compress_sentence_aggressive(spec, is_fr, category)
                if cs.strip():
                    lines.append(f"  * {cs}")
        aggressive_prompt = "\n".join(lines)
        aggressive_prompt = self._sanctuary_reinject(aggressive_prompt, sanctuary)

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
                "description": "Style télégraphique ultra-dense, suppression complète des mots-outils non structurels.",
                "prompt": aggressive_prompt,
            },
        }


# --- WRAPPER API COMPATIBLE AVEC app.py ---
def optimize_locally(prompt: str, category: str = None) -> list:
    opt = OptiTokenOptimizer()
    result = opt.optimize(prompt, category=category)
    changes_light = [{"type": "light_clean", "description": "Nettoyage conversationnel"}]
    changes_balanced = [{"type": "balanced_restruct", "description": "Restructuration par blocs + compression"}]
    changes_aggressive = [{"type": "aggressive_telegraphic", "description": "Compression télégraphique ultra-dense"}]
    return [
        {**result["light"], "changes_made": changes_light},
        {**result["balanced"], "changes_made": changes_balanced},
        {**result["aggressive"], "changes_made": changes_aggressive},
    ]


def optimize_prompt(prompt: str, optimizer_model: str = None, provider: str = None, api_key: str = None, category: str = None) -> list:
    if api_key and provider == "openai":
        try:
            return _optimize_with_openai(prompt, optimizer_model, api_key)
        except Exception as e:
            result = optimize_locally(prompt, category=category)
            return result if isinstance(result, list) else [{"label": "Light", "prompt": prompt, "changes_made": [], "description": str(e)}]

    if api_key and provider == "anthropic":
        try:
            return _optimize_with_anthropic(prompt, optimizer_model, api_key)
        except Exception as e:
            result = optimize_locally(prompt, category=category)
            return result if isinstance(result, list) else [{"label": "Light", "prompt": prompt, "changes_made": [], "description": str(e)}]

    if api_key and provider == "google":
        try:
            return _optimize_with_google(prompt, optimizer_model, api_key)
        except Exception as e:
            result = optimize_locally(prompt, category=category)
            return result if isinstance(result, list) else [{"label": "Light", "prompt": prompt, "changes_made": [], "description": str(e)}]

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
