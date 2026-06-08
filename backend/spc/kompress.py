"""KOMPRESS — ModernBERT token compressor (native, no headroom dependency).

Model: chopratejas/kompress-base (150M params, 8192 ctx, 600 MB)
Native reimplementation: ModernBert backbone + token head + 1D span CNN.

Loads weights from local path or HuggingFace hub fallback.
"""
import os as _os
import logging
from typing import Optional, List, Tuple

import torch
import torch.nn as nn
from transformers import (
    AutoTokenizer,
    PreTrainedTokenizerFast,
)
from transformers.models.modernbert.modeling_modernbert import (
    ModernBertModel,
    ModernBertConfig,
)

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────

_MODELS_DIR = _os.path.join(_os.path.dirname(__file__), "models")
HF_REPO = "chopratejas/kompress-base"

# ── Model definition ─────────────────────────────────────────

class KompressModel(nn.Module):
    """KOMPRESS token compressor — ModernBERT + dual head.

    Architecture matches chopratejas/kompress-base state dict exactly.
    """

    def __init__(self, config: ModernBertConfig):
        super().__init__()
        self.encoder = ModernBertModel(config)
        self.token_head = nn.Linear(config.hidden_size, 2, bias=True)
        self.span_conv = nn.Sequential(
            nn.Conv1d(config.hidden_size, 256, kernel_size=5, padding=2),
            nn.GELU(),
            nn.Conv1d(256, 1, kernel_size=3, padding=1),
        )

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        hidden = self.encoder(
            input_ids,
            attention_mask=attention_mask,
        ).last_hidden_state  # (B, S, H)

        # Token classification head: [drop_logit, keep_logit]
        token_logits = self.token_head(hidden)  # (B, S, 2)

        # 1D span CNN: positive score for important regions
        span_scores = self.span_conv(hidden.transpose(1, 2))  # (B, 1, S)

        # Add span bias to "keep" logit, then softmax
        token_logits[:, :, 1] = token_logits[:, :, 1] + span_scores.squeeze(1)
        probs = torch.softmax(token_logits, dim=-1)  # (B, S, 2)

        # P(keep) per token
        return probs[:, :, 1]


# ── Loader (singleton cache) ─────────────────────────────────

_kompress_cache: dict = {}
_kompress_tokenizer_cache: dict = {}


def _resolve_model_path() -> Tuple[str, bool]:
    """Return (model_source, local_only) — prefer local path."""
    local = _os.path.join(_MODELS_DIR, "kompress-base")
    safetensors = _os.path.join(local, "model.safetensors")
    if _os.path.isdir(local) and _os.path.isfile(safetensors):
        return local, True
    return HF_REPO, False


def load_kompress(
    device: str = "cpu",
    force_reload: bool = False,
) -> Tuple[KompressModel, PreTrainedTokenizerFast]:
    """Load KOMPRESS model + ModernBERT tokenizer (singleton)."""
    key = f"kompress:{device}"
    if not force_reload and key in _kompress_cache:
        return _kompress_cache[key], _kompress_tokenizer_cache[key]

    model_source, local_only = _resolve_model_path()
    logger.info(
        "Loading KOMPRESS from %s (local_only=%s, device=%s)",
        model_source, local_only, device,
    )

    config = ModernBertConfig.from_pretrained(
        model_source, local_files_only=local_only,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        model_source, local_files_only=local_only,
    )

    model = KompressModel(config)
    state = _load_state(model_source)
    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing:
        logger.warning("KOMPRESS missing keys: %s", missing)
    if unexpected:
        logger.warning("KOMPRESS unexpected keys: %s", unexpected)

    model.eval()
    model.to(device)

    _kompress_cache[key] = model
    _kompress_tokenizer_cache[key] = tokenizer
    return model, tokenizer


def _load_state(model_source: str) -> dict:
    """Load safetensors state dict."""
    from safetensors.torch import load_file as _load_safe
    safetensors_path = _os.path.join(model_source, "model.safetensors")
    if _os.path.isfile(safetensors_path):
        return _load_safe(safetensors_path, device="cpu")
    # Fallback: try loading with transformers
    from transformers import AutoModel
    dummy = AutoModel.from_pretrained(model_source, trust_remote_code=True)
    return dummy.state_dict()


def reset_kompress():
    _kompress_cache.clear()
    _kompress_tokenizer_cache.clear()


# ── Compression engine ──────────────────────────────────────

def compress_with_kompress(
    text: str,
    threshold: float = 0.5,
    max_length: int = 8192,
    device: str = "cpu",
) -> Tuple[str, List[float]]:
    model, tokenizer = load_kompress(device=device)

    enc = tokenizer(
        text,
        return_tensors="pt",
        max_length=max_length,
        truncation=True,
        padding=False,
    )
    input_ids = enc["input_ids"].to(device)
    attention_mask = enc.get("attention_mask", torch.ones_like(input_ids)).to(device)

    with torch.no_grad():
        scores = model(input_ids, attention_mask=attention_mask)  # (1, S)

    scores_np = scores[0].cpu().numpy().tolist()
    score_tensor = scores[0]  # (S,)

    # Dual strategy: absolute threshold + percentile floor
    # absolute: drop tokens with score < threshold
    # percentile: always drop bottom 15% to guarantee minimum compression
    pct_floor = float(torch.quantile(score_tensor, 0.15))
    effective_threshold = max(threshold, pct_floor)
    keep_mask = score_tensor >= effective_threshold  # (S,)

    kept_ids = input_ids[0][keep_mask]
    compressed = tokenizer.decode(kept_ids, skip_special_tokens=True)

    return compressed, scores_np


def is_kompress_available() -> bool:
    """Check if KOMPRESS model is available locally."""
    local = _os.path.join(_MODELS_DIR, "kompress-base")
    safetensors = _os.path.join(local, "model.safetensors")
    return _os.path.isdir(local) and _os.path.isfile(safetensors)


def auto_compress(
    text: str,
    threshold: float = 0.5,
    min_tokens: int = 50,
) -> Tuple[str, Optional[List[float]], str]:
    """Auto-detect best compressor: KOMPRESS for long texts, fallback for short.

    Returns:
        (compressed_text, scores_or_None, engine_name)
    """
    import tiktoken
    enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
    token_count = len(enc.encode(text))

    if token_count < min_tokens:
        return text, None, "skip"

    if is_kompress_available():
        compressed, scores = compress_with_kompress(text, threshold=threshold)
        return compressed, scores, "kompress"

    return text, None, "unavailable"
