import math
import re
from typing import Dict, List, Optional, Tuple

TASK_KEYWORDS: Dict[str, List[str]] = {
    "code": [
        "write a function", "implement", "def ", "class ", "import ",
        "code", "programming", "python", "javascript", "bug", "error",
        "compile", "syntax", "algorithm", "refactor", "debug", "test",
        "function", "method", "variable", "api", "endpoint", "route",
        "database", "query", "sql", "git", "commit", "deploy", "docker",
        "écris une fonction", "implémente", "code", "programmation",
        "algorithme", "refactorise", "débug", "test", "fonction",
    ],
    "analytique": [
        "analyse", "analyser", "compare", "comparer", "différence",
        "tendances", "données", "data", "statistics", "statistiques",
        "metrics", "kpi", "dashboard", "reporting", "insight",
        "correlation", "regression", "trend", "forecast", "chart",
        "graphique", "tableau", "indicateur", "performance", "analyse",
        "analyze", "comparison", "difference", "trend", "metric",
    ],
    "creatif": [
        "write a story", "poem", "creative", "imagine", "design",
        "créatif", "créative", "histoire", "poème", "art",
        "concept", "inspiration", "brand", "slogan", "tagline",
        "script", "dialogue", "narrative", "story", "novel",
        "écris une histoire", "poème", "créatif", "imagine",
    ],
    "factuel": [
        "what is", "who is", "when did", "where is", "definition",
        "define", "explain", "qu'est-ce que", "définition", "expliquer",
        "fact", "information", "describe", "tell me about",
        "what does", "how does", "why is", "explain", "define",
        "qu'est-ce", "défini", "explique", "décris",
    ],
    "traduction": [
        "translate", "traduis", "traduction", "translation",
        "in english", "in french", "en anglais", "en français",
        "translate to", "traduire en", "convert to",
    ],
    "resume": [
        "summarize", "summary", "résumé", "résume", "synthèse",
        "synthétise", "tl;dr", "en résumé", "key points", "main ideas",
        "executive summary", "recap", "abstract", "condense",
        "résume", "synthétise", "points clés", "idées principales",
    ],
    "brainstorming": [
        "brainstorm", "ideas", "suggest", "recommend", "propose",
        "idées", "suggère", "recommande", "propose", "options",
        "alternatives", "possibilities", "what are some", "list of",
        "give me ideas", "help me think", "suggestion",
        "brainstorming", "idées", "suggère", "recommande",
    ],
    "instruction": [
        "how to", "steps", "step by step", "guide", "tutorial",
        "instructions", "procedure", "process", "workflow", "setup",
        "configuration", "install", "deploy", "command", "run",
        "execute", "how do i", "steps to", "guide me",
        "comment faire", "étapes", "guide", "tutoriel", "procédure",
        "installation", "configuration", "commande",
    ],
}

DOMAIN_JARGON_PATTERNS: Dict[str, List[str]] = {
    "legal": [
        "hereby", "whereas", "pursuant", "notwithstanding", "aforesaid",
        "hereinafter", "thereof", "therein", "herein", "parties",
        "agreement", "indemnify", "liability", "warrant", "breach",
        "ci-après", "nonobstant", "conformément", "ledit", "ladite",
        "dudit", "aux termes", "parties", "indemniser", "garantie",
    ],
    "medical": [
        "diagnosis", "prognosis", "symptom", "treatment", "therapy",
        "patient", "clinical", "pathology", "etiology", "contraindication",
        "diagnostic", "pronostic", "symptôme", "traitement", "thérapie",
        "patient", "clinique", "pathologie", "contre-indication",
    ],
    "financial": [
        "revenue", "ebitda", "amortization", "depreciation", "equity",
        "dividend", "yield", "derivative", "futures", "arbitrage",
        "hedge", "portfolio", "asset", "liability", "balance sheet",
        "chiffre d'affaires", "ebitda", "amortissement", "dépréciation",
        "capitaux propres", "dividende", "dérivé", "arbitrage",
        "portefeuille", "actif", "passif", "bilan",
    ],
    "technical": [
        "docker", "kubernetes", "container", "microservice", "api",
        "rest", "graphql", "websocket", "tcp", "http", "https",
        "ssl", "tls", "encryption", "authentication", "authorization",
        "middleware", "database", "cache", "queue", "event-driven",
        "serverless", "cloud", "aws", "azure", "gcp", "devops",
        "ci/cd", "pipeline", "monitoring", "observability", "latency",
        "throughput", "concurrency", "parallel", "distributed",
    ],
}


SPECIFICITY_KEYWORDS: Dict[str, float] = {}
for domain, terms in DOMAIN_JARGON_PATTERNS.items():
    for term in terms:
        SPECIFICITY_KEYWORDS[term.lower()] = 1.0


def _word_boundary(kw: str) -> str:
    escaped = re.escape(kw)
    return rf'(?<!\w){escaped}(?!\w)'


def classify_task(prompt: str) -> str:
    if not prompt or not prompt.strip():
        return "factuel"

    scores: Dict[str, int] = {}
    for task, keywords in TASK_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if re.search(_word_boundary(kw), prompt, re.IGNORECASE):
                score += 1
        if score > 0:
            scores[task] = score

    if not scores:
        return "factuel"

    best = max(scores, key=scores.get)
    return best


def estimate_specificity(prompt: str) -> str:
    if not prompt or not prompt.strip():
        return "generic"

    domain_term_count = 0
    for term in SPECIFICITY_KEYWORDS:
        if re.search(_word_boundary(term), prompt, re.IGNORECASE):
            domain_term_count += 1

    entity_count = len(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', prompt))
    number_count = len(re.findall(r'\b\d+\b', prompt))

    if domain_term_count >= 3 or (domain_term_count >= 1 and entity_count >= 3):
        return "entity_rich"
    if domain_term_count >= 1 or entity_count >= 2:
        return "domain_jargon"
    return "generic"


def estimate_length_bucket(token_count: int, model: str = "") -> str:
    if token_count < 50:
        return "short"
    elif token_count < 500:
        return "medium"
    elif token_count < 2000:
        return "long"
    else:
        return "very_long"


def get_user_cluster(user_id: Optional[str], n_clusters: int = 20) -> int:
    if not user_id:
        return 0
    h = hash(user_id) % n_clusters
    return abs(h)


def extract_features(
    prompt: str,
    token_count: int,
    model: str = "",
    user_id: Optional[str] = None,
    tenant_id: str = "default",
) -> Dict:
    task = classify_task(prompt)
    specificity = estimate_specificity(prompt)
    length_bucket = estimate_length_bucket(token_count, model)
    user_cluster = get_user_cluster(user_id)

    return {
        "task_type": task,
        "specificity": specificity,
        "length_bucket": length_bucket,
        "user_cluster": user_cluster,
        "user_id": user_id or "",
        "tenant_id": tenant_id,
        "model": model or "gpt-4o",
        "token_count": token_count,
    }
