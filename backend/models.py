MODELS = {
    "gpt-4o": {
        "provider": "openai",
        "input_price_per_1k": 0.0025,
        "output_price_per_1k": 0.01,
        "context_window": 128000,
        "family": "GPT-4o",
    },
    "gpt-4o-mini": {
        "provider": "openai",
        "input_price_per_1k": 0.00015,
        "output_price_per_1k": 0.0006,
        "context_window": 128000,
        "family": "GPT-4o Mini",
    },
    "gpt-4-turbo": {
        "provider": "openai",
        "input_price_per_1k": 0.01,
        "output_price_per_1k": 0.03,
        "context_window": 128000,
        "family": "GPT-4 Turbo",
    },
    "gpt-3.5-turbo": {
        "provider": "openai",
        "input_price_per_1k": 0.0005,
        "output_price_per_1k": 0.0015,
        "context_window": 16385,
        "family": "GPT-3.5 Turbo",
    },
    "claude-3-opus-20240229": {
        "provider": "anthropic",
        "input_price_per_1k": 0.015,
        "output_price_per_1k": 0.075,
        "context_window": 200000,
        "family": "Claude 3 Opus",
    },
    "claude-3-sonnet-20240229": {
        "provider": "anthropic",
        "input_price_per_1k": 0.003,
        "output_price_per_1k": 0.015,
        "context_window": 200000,
        "family": "Claude 3 Sonnet",
    },
    "claude-3-haiku-20240307": {
        "provider": "anthropic",
        "input_price_per_1k": 0.00025,
        "output_price_per_1k": 0.00125,
        "context_window": 200000,
        "family": "Claude 3 Haiku",
    },
    "claude-3-5-sonnet-20241022": {
        "provider": "anthropic",
        "input_price_per_1k": 0.003,
        "output_price_per_1k": 0.015,
        "context_window": 200000,
        "family": "Claude 3.5 Sonnet",
    },
    "claude-4-sonnet": {
        "provider": "anthropic",
        "input_price_per_1k": 0.003,
        "output_price_per_1k": 0.015,
        "context_window": 200000,
        "family": "Claude 4 Sonnet",
    },
    "gemini-2.0-flash": {
        "provider": "google",
        "input_price_per_1k": 0.0001,
        "output_price_per_1k": 0.0004,
        "context_window": 1048576,
        "family": "Gemini 2.0 Flash",
    },
    "gemini-2.5-pro": {
        "provider": "google",
        "input_price_per_1k": 0.00125,
        "output_price_per_1k": 0.005,
        "context_window": 1048576,
        "family": "Gemini 2.5 Pro",
    },
    "mistral-large-2407": {
        "provider": "mistral",
        "input_price_per_1k": 0.002,
        "output_price_per_1k": 0.006,
        "context_window": 128000,
        "family": "Mistral Large",
    },
    "llama-3.1-70b": {
        "provider": "meta",
        "input_price_per_1k": 0.00059,
        "output_price_per_1k": 0.00079,
        "context_window": 128000,
        "family": "Llama 3.1 70B",
    },
}

OPTIMIZER_MODELS = {
    "openai": {
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "label": "OpenAI",
    },
    "anthropic": {
        "models": [
            "claude-3-5-sonnet-20241022",
            "claude-4-sonnet",
            "claude-3-opus-20240229",
        ],
        "label": "Anthropic",
    },
    "google": {
        "models": ["gemini-2.5-pro", "gemini-2.0-flash"],
        "label": "Google",
    },
}


def get_model_info(model_id):
    return MODELS.get(model_id)


def calculate_cost(model_id, input_tokens, output_tokens=0):
    model = get_model_info(model_id)
    if not model:
        return None
    input_cost = (input_tokens / 1000) * model["input_price_per_1k"]
    output_cost = (output_tokens / 1000) * model["output_price_per_1k"]
    return round(input_cost + output_cost, 6)
