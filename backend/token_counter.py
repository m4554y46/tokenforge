import tiktoken
import re


ENCODING_CACHE = {}


def _get_encoding(model):
    if model in ENCODING_CACHE:
        return ENCODING_CACHE[model]
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    ENCODING_CACHE[model] = encoding
    return encoding


def count_tokens_openai(text, model="gpt-4o"):
    try:
        encoding = _get_encoding(model)
        return len(encoding.encode(text))
    except Exception:
        return count_tokens_approximate(text)


def count_tokens_anthropic(text, model=None):
    approx = len(text) // 3.5
    claude_mult = 1.1
    return max(1, int(approx * claude_mult))


def count_tokens_google(text, model=None):
    approx = len(text) // 4
    return max(1, int(approx))


def count_tokens_mistral(text, model=None):
    try:
        encoding = _get_encoding("gpt-4o")
        return len(encoding.encode(text))
    except Exception:
        return count_tokens_approximate(text)


def count_tokens_approximate(text):
    if not text:
        return 0
    text = text.strip()
    words = len(re.findall(r"\b\w+\b", text))
    punct = len(re.findall(r"[^\w\s]", text))
    return max(1, int(words * 1.3 + punct * 0.5))


PROVIDER_COUNTERS = {
    "openai": count_tokens_openai,
    "anthropic": count_tokens_anthropic,
    "google": count_tokens_google,
    "mistral": count_tokens_mistral,
    "meta": count_tokens_openai,
}


def count_tokens(text, model="gpt-4o"):
    from backend.models import get_model_info

    model_info = get_model_info(model)
    if model_info:
        provider = model_info["provider"]
        counter = PROVIDER_COUNTERS.get(provider, count_tokens_approximate)
        return counter(text, model)
    return count_tokens_approximate(text)
