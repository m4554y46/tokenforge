"""LLMLingua-2 native implementation — fully self-contained.

No dependency on the `llmlingua` package. Uses only:
  - transformers (model + tokenizer)
  - torch (inference)
  - numpy (percentile calculations)
  - tiktoken (GPT token count for threshold calibration)

All engines reimplemented from the LLMLingua-2 paper:
  - TokenClassificationCompressor: core keep/remove token classifier
  - NativeJsonCompressor: JSON-aware value compression
  - AutoDetect: text-type detection + engine selection
"""

import copy
import json
import logging
import math
import os as _os
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import tiktoken
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoConfig,
    AutoModelForTokenClassification,
    AutoTokenizer,
)

logger = logging.getLogger(__name__)


# ── Text type detection ───────────────────────────────────────

class TextType(Enum):
    CODE = "code"
    JSON = "json"
    MEETING = "meeting"
    LEGAL = "legal"
    GENERAL = "general"
    SHORT = "short"
    MULTILINGUAL = "multi"


class CompressionStrategy(Enum):
    STANDARD = "standard"
    STRUCTURED = "structured"
    SKIP = "skip"


_MEETING_RE = re.compile(r'(?:Speaker|Participant|Agent)\s*\d+\s*:', re.I)
_LEGAL_RE = re.compile(
    r'\b(?:Article|Section|Clause|CONTRAT|CONVENU|IL\s+A\s+ÉTÉ\s+CONVENU|\d+\.\s+(?:Objet|Prestation|Confidentialité))',
    re.I,
)
_CODE_SIGNAL = re.compile(r'(?:def |class |function |import |from |public\s+(?:class|void|int|string))', re.I)
_SPEAKER_LINE = re.compile(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*:\s+', re.MULTILINE)


def detect_text_type(text: str, lang: str = "en", fmt: str = "txt") -> TextType:
    if not text or len(text.strip()) < 50:
        return TextType.SHORT
    if fmt == "code" or _CODE_SIGNAL.search(text):
        return TextType.CODE
    if fmt == "json":
        return TextType.JSON
    if _MEETING_RE.search(text):
        return TextType.MEETING
    if _LEGAL_RE.search(text):
        return TextType.LEGAL
    if lang and lang != "en":
        return TextType.MULTILINGUAL
    return TextType.GENERAL


# ── Model registry ────────────────────────────────────────────

_MODELS_DIR = _os.path.join(_os.path.dirname(__file__), "models")

MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "xlm-roberta-large": {
        "model_name": "microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
        "local_path": _os.path.join(_MODELS_DIR, "xlm-roberta-large"),
        "quality": 5,
        "multilingual": True,
        "size_gb": 2.2,
    },
    "bert-base-multilingual": {
        "model_name": "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
        "local_path": _os.path.join(_MODELS_DIR, "bert-base-multilingual"),
        "quality": 4,
        "multilingual": True,
        "size_gb": 0.4,
    },
}

TYPE_MODEL_MAP: Dict[TextType, Optional[str]] = {
    TextType.MEETING: "xlm-roberta-large",
    TextType.LEGAL: "xlm-roberta-large",
    TextType.GENERAL: "xlm-roberta-large",
    TextType.MULTILINGUAL: "xlm-roberta-large",
    TextType.JSON: "xlm-roberta-large",
    TextType.CODE: None,
    TextType.SHORT: None,
}

TYPE_STRATEGY_MAP: Dict[TextType, CompressionStrategy] = {
    TextType.CODE: CompressionStrategy.SKIP,
    TextType.JSON: CompressionStrategy.STRUCTURED,
    TextType.SHORT: CompressionStrategy.SKIP,
    TextType.MEETING: CompressionStrategy.STANDARD,
    TextType.LEGAL: CompressionStrategy.STANDARD,
    TextType.GENERAL: CompressionStrategy.STANDARD,
    TextType.MULTILINGUAL: CompressionStrategy.STANDARD,
}

TYPE_PARAMS: Dict[TextType, Dict[str, Any]] = {
    TextType.MEETING: {
        "rate": 0.40,
        "chunk_end_tokens": [".", "\n", "!", "?"],
        "force_reserve_digit": False,
    },
    TextType.LEGAL: {
        "rate": 0.50,
        "chunk_end_tokens": [".", "\n", ";"],
        "force_reserve_digit": True,
    },
    TextType.GENERAL: {
        "rate": 0.50,
        "chunk_end_tokens": [".", "\n", "!", "?"],
        "force_reserve_digit": True,
    },
    TextType.MULTILINGUAL: {
        "rate": 0.50,
        "chunk_end_tokens": [".", "\n", "!", "?"],
        "force_reserve_digit": True,
    },
    TextType.JSON: {
        "rate": 0.50,
        "chunk_end_tokens": [".", "\n"],
        "force_reserve_digit": True,
    },
}

MODALITY_TOKENS: List[str] = [
    "must", "shall", "should", "may", "might", "will", "would",
    "can", "could", "need", "required", "mandatory", "optional",
    "doit", "devoir", "faut", "nécessaire", "obligatoire",
    "peut", "pourrait", "not", "no", "never", "without",
    "tous", "chaque", "any", "every", "all",
]


# ── Native model loader (module-level singleton cache) ────────

_loaded_models: Dict[str, Dict[str, Any]] = {}
_oai_tokenizer = None


def _get_oai_tokenizer():
    global _oai_tokenizer
    if _oai_tokenizer is None:
        _oai_tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")
    return _oai_tokenizer


def _get_model_and_tokenizer(
    model_key: str,
    device: str = "cpu",
    max_batch_size: int = 50,
    max_force_token: int = 100,
) -> Optional[Dict[str, Any]]:
    if model_key in _loaded_models:
        return _loaded_models[model_key]

    config_entry = MODEL_REGISTRY.get(model_key)
    if config_entry is None:
        return None

    model_name = config_entry["model_name"]
    local_path = config_entry.get("local_path", "")

    # Prefer local path for offline-first loading
    model_source = local_path if (local_path and _os.path.isdir(local_path) and
                                  _os.path.isfile(_os.path.join(local_path, "model.safetensors"))) else model_name
    use_local_only = (model_source == local_path)

    try:
        hf_config = AutoConfig.from_pretrained(
            model_source, local_files_only=use_local_only
        )
        tokenizer = AutoTokenizer.from_pretrained(
            model_source, local_files_only=use_local_only
        )
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token_id = tokenizer.eos_token_id

        added_tokens = [f"[K{i}]" for i in range(max_force_token)]
        tokenizer.add_special_tokens(
            {"additional_special_tokens": added_tokens}
        )

        model = AutoModelForTokenClassification.from_pretrained(
            model_source,
            config=hf_config,
            torch_dtype=torch.float32,
            ignore_mismatched_sizes=True,
            local_files_only=use_local_only,
        )
        model.resize_token_embeddings(len(tokenizer))
        model.eval()
        model.to(device)

        special_tokens = set(
            v for k, v in tokenizer.special_tokens_map.items()
            if k != "additional_special_tokens"
        )

        entry = {
            "model": model,
            "tokenizer": tokenizer,
            "special_tokens": special_tokens,
            "device": device,
            "max_batch_size": max_batch_size,
            "max_seq_len": min(hf_config.max_position_embeddings, 512),
            "model_name": model_name,
            "max_force_token": max_force_token,
        }
        _loaded_models[model_key] = entry
        logger.info(
            "Loaded native model '%s': %s (device=%s)",
            model_key, model_name, device,
        )
        return entry
    except Exception as e:
        logger.warning("Failed to load native model '%s': %s", model_key, e)
        return None


def reset_model(model_key: Optional[str] = None):
    global _loaded_models
    if model_key:
        _loaded_models.pop(model_key, None)
    else:
        _loaded_models.clear()


# ── Token/word helpers (model-agnostic) ───────────────────────

def _is_xlm_roberta(model_key: str) -> bool:
    return "xlm-roberta" in model_key


def _is_begin_of_new_word(token: str, model_key: str, force_tokens: set) -> bool:
    if _is_xlm_roberta(model_key):
        if token in string_punctuation or token in force_tokens:
            return True
        return token.startswith("▁")
    else:
        if token.lstrip("##") in force_tokens:
            return True
        return not token.startswith("##")


string_punctuation = set('.,;:!?"\'()[]{}<>/\\@#$%^&*~`|_-+=')


def _get_pure_token(token: str, model_key: str) -> str:
    if _is_xlm_roberta(model_key):
        return token.lstrip("▁")
    return token.lstrip("##")


def _replace_added_token(token: str) -> str:
    return token.strip("▁")


def _merge_token_to_word(
    tokens: List[str],
    token_probs: List[float],
    model_key: str,
    force_tokens: set,
    force_reserve_digit: bool,
    special_tokens: Optional[set] = None,
) -> Tuple[List[str], List[List[float]], List[List[float]]]:
    words: List[str] = []
    word_probs: List[List[float]] = []
    word_probs_no_force: List[List[float]] = []
    special = special_tokens or set()

    for token, prob in zip(tokens, token_probs):
        if token in special:
            continue
        pure = _get_pure_token(token, model_key)
        prob_no_force = prob
        if pure in force_tokens:
            prob = 1.0
        if _is_begin_of_new_word(token, model_key, force_tokens):
            words.append(_replace_added_token(token))
            entry_prob = 1.0 if (force_reserve_digit and bool(re.search(r"\d", token))) else prob
            word_probs.append([entry_prob])
            word_probs_no_force.append([prob_no_force])
        else:
            if not words:
                continue
            entry_prob = 1.0 if (force_reserve_digit and bool(re.search(r"\d", token))) else prob
            word_probs[-1].append(entry_prob)
            word_probs_no_force[-1].append(prob_no_force)
            words[-1] += pure

    return words, word_probs, word_probs_no_force


def _token_prob_to_word_prob(token_probs: List[List[float]], convert_mode: str = "mean") -> List[float]:
    if convert_mode == "mean":
        return [sum(p) / len(p) for p in token_probs]
    elif convert_mode == "first":
        return [p[0] for p in token_probs]
    raise NotImplementedError(f"Unknown convert_mode: {convert_mode}")


# ── Chunking ──────────────────────────────────────────────────

def _chunk_context(
    text: str,
    tokenizer: Any,
    max_len: int,
    chunk_end_tokens: Optional[List[str]] = None,
) -> List[str]:
    if chunk_end_tokens is None:
        chunk_end_tokens = [".", "\n"]
    chunk_end_set = set(chunk_end_tokens)

    max_chunk_len = max_len - 2
    origin_tokens = tokenizer.tokenize(text)
    n = len(origin_tokens)
    chunks: List[str] = []
    st = 0
    while st < n:
        if st + max_chunk_len > n - 1:
            chunk = tokenizer.convert_tokens_to_string(origin_tokens[st:n])
            chunks.append(chunk)
            break
        ed = st + max_chunk_len
        for j in range(ed - st):
            if origin_tokens[ed - j] in chunk_end_set:
                ed = ed - j
                break
        chunk = tokenizer.convert_tokens_to_string(origin_tokens[st: ed + 1])
        chunks.append(chunk)
        st = ed + 1
    return chunks


# ── Token classification dataset ──────────────────────────────

class _TokenClfDataset(Dataset):
    def __init__(self, texts: List[str], tokenizer: Any, max_len: int, model_key: str):
        self.texts = texts
        self.tokenizer = tokenizer
        self.max_len = max_len
        if _is_xlm_roberta(model_key):
            self.cls_token = "<s>"
            self.sep_token = "</s>"
            self.pad_token = "<pad>"
        else:
            self.cls_token = "[CLS]"
            self.sep_token = "[SEP]"
            self.pad_token = "[PAD]"

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, index: int) -> Dict[str, torch.Tensor]:
        text = self.texts[index]
        tokenized = self.tokenizer.tokenize(text)
        tokenized = [self.cls_token] + tokenized + [self.sep_token]
        if len(tokenized) > self.max_len:
            tokenized = tokenized[: self.max_len]
        else:
            tokenized = tokenized + [self.pad_token] * (self.max_len - len(tokenized))
        attn_mask = [1 if tok != self.pad_token else 0 for tok in tokenized]
        ids = self.tokenizer.convert_tokens_to_ids(tokenized)
        return {
            "ids": torch.tensor(ids, dtype=torch.long),
            "mask": torch.tensor(attn_mask, dtype=torch.long),
        }


# ── Core compression algorithm ────────────────────────────────

def _compress_chunks(
    chunk_list: List[str],
    model: torch.nn.Module,
    tokenizer: Any,
    device: str,
    max_seq_len: int,
    max_batch_size: int,
    model_key: str,
    reduce_rate: float,
    force_tokens: List[str],
    force_reserve_digit: bool,
    drop_consecutive: bool,
    return_word_label: bool,
    special_tokens: Optional[set] = None,
) -> Tuple[List[str], Optional[List[List[str]]], Optional[List[List[int]]]]:
    if reduce_rate <= 0:
        words_out = []
        labels_out = []
        for c in chunk_list:
            ws = re.findall(r"\b\w+\b|[<>=/!@#$%^&*()?\":{}|\\`~;_+-]", c)
            words_out.append(ws)
            labels_out.append([1] * len(ws))
        return chunk_list, words_out, labels_out

    dataset = _TokenClfDataset(chunk_list, tokenizer, max_seq_len, model_key)
    dataloader = DataLoader(dataset, batch_size=max_batch_size, shuffle=False, drop_last=False)
    force_set = set(force_tokens)

    compressed_chunks: List[str] = []
    word_list: List[List[str]] = []
    word_label_list: List[List[int]] = []

    with torch.no_grad():
        for batch in dataloader:
            ids = batch["ids"].to(device, dtype=torch.long)
            mask = batch["mask"].to(device, dtype=torch.long) == 1

            outputs = model(input_ids=ids, attention_mask=mask)
            logits = outputs.logits
            probs = F.softmax(logits, dim=-1)

            for j in range(ids.shape[0]):
                chunk_probs = probs[j, :, 1]
                chunk_ids = ids[j]
                chunk_mask = mask[j]

                active_probs = torch.masked_select(chunk_probs, chunk_mask)
                active_ids = torch.masked_select(chunk_ids, chunk_mask)

                tokens = tokenizer.convert_ids_to_tokens(active_ids.squeeze().tolist())
                token_probs = [float(p) for p in active_probs.cpu().numpy()]

                words, valid_token_probs, _ = _merge_token_to_word(
                    tokens=tokens,
                    token_probs=token_probs,
                    model_key=model_key,
                    force_tokens=force_set,
                    force_reserve_digit=force_reserve_digit,
                    special_tokens=special_tokens,
                )
                # Build clean words for force-token matching (strip ▁ for XLM-RoBERTa)
                if _is_xlm_roberta(model_key):
                    clean_words: List[str] = [w.lstrip("▁") for w in words]
                    _match_in_force = lambda w: w in force_set or w.lstrip("▁") in force_set
                else:
                    clean_words = list(words)
                    _match_in_force = lambda w: w in force_set

                word_probs = _token_prob_to_word_prob(valid_token_probs, convert_mode="mean")

                # Post-merge force-token enforcement (handles multi-token words)
                for i, cw in enumerate(clean_words):
                    if cw in force_set:
                        word_probs[i] = 1.0

                if drop_consecutive:
                    threshold_dc = np.percentile(word_probs, int(100 * reduce_rate))
                    is_between = False
                    prev = None
                    for i, (cw, wp) in enumerate(zip(clean_words, word_probs)):
                        if cw in force_set:
                            if is_between:
                                is_between = False
                            elif not is_between and cw == prev:
                                word_probs[i] = 0.0
                            prev = cw
                        else:
                            is_between |= wp > threshold_dc

                oai = _get_oai_tokenizer()
                new_token_probs = []
                for cw, wp in zip(clean_words, word_probs):
                    nt = len(oai.encode(cw))
                    new_token_probs.extend([wp] * nt)

                threshold = np.percentile(new_token_probs, int(100 * reduce_rate + 1))

                keep_words: List[str] = []
                word_labels: List[int] = []
                _last_cw: Optional[str] = None
                for word, cw, wp in zip(words, clean_words, word_probs):
                    if wp > threshold or (threshold == 1.0 and wp == threshold):
                        is_consecutive = (
                            drop_consecutive
                            and cw in force_set
                            and _last_cw is not None
                            and cw == _last_cw
                        )
                        if is_consecutive:
                            word_labels.append(0)
                        else:
                            keep_words.append(word)
                            word_labels.append(1)
                            _last_cw = cw if cw in force_set else None
                    else:
                        word_labels.append(0)

                keep_str = tokenizer.convert_tokens_to_string(keep_words)
                for i in range(len(words)):
                    if _is_xlm_roberta(model_key):
                        words[i] = words[i].lstrip("▁")

                compressed_chunks.append(keep_str)
                word_list.append(words[:])
                word_label_list.append(word_labels[:])

    return compressed_chunks, word_list, word_label_list


# ── Public API: standard LLMLingua-2 compression ──────────────

def compress_with_llmlingua2(
    text: str,
    rate: float = 0.5,
    force_tokens: Optional[List[str]] = None,
    force_reserve_digit: bool = True,
    drop_consecutive: bool = False,
    chunk_end_tokens: Optional[List[str]] = None,
    return_word_label: bool = False,
    model_key: str = "xlm-roberta-large",
) -> Tuple[str, Optional[Dict]]:
    """Compress text using native LLMLingua-2 token classification engine.

    Args:
        text: Input text to compress.
        rate: Target compression rate (ratio of tokens to keep, e.g. 0.5 = 50%).
        force_tokens: Tokens that must be preserved.
        force_reserve_digit: Preserve tokens containing digits.
        drop_consecutive: Avoid consecutive duplicate force_tokens.
        chunk_end_tokens: Tokens that mark chunk boundaries.
        return_word_label: Return word-level keep/remove labels.
        model_key: Which model to use ("xlm-roberta-large" or "bert-base-multilingual").

    Returns:
        Tuple of (compressed_text, optional_labels_dict).
    """
    entry = _get_model_and_tokenizer(model_key)
    if entry is None:
        return text, None

    model = entry["model"]
    tokenizer = entry["tokenizer"]
    device = entry["device"]
    max_seq_len = entry["max_seq_len"]
    max_batch_size = entry["max_batch_size"]
    model_name = entry["model_name"]

    force_tokens = force_tokens or []
    chunk_end_tokens = chunk_end_tokens or [".", "\n"]

    protected_ids = re.findall(r"PROTECTED_\d+", text)
    all_force = list(set(force_tokens + protected_ids))

    # Replace multi-word force tokens with [Ki] placeholders (added to tokenizer vocab)
    _ft_replacements: Dict[str, str] = {}
    modified_text = text
    _ft_counter = 0
    max_ft = entry.get("max_force_token", 100)
    for ft in list(all_force):
        if len(tokenizer.tokenize(ft)) != 1:
            if _ft_counter >= max_ft:
                break
            placeholder = f"[K{_ft_counter}]"
            _ft_counter += 1
            modified_text = modified_text.replace(ft, placeholder)
            _ft_replacements[placeholder] = ft
            all_force.remove(ft)
            all_force.append(placeholder)
    all_force = list(set(all_force))

    try:
        reduce_rate = max(0.0, 1.0 - rate)

        chunks = _chunk_context(modified_text, tokenizer, max_seq_len, chunk_end_tokens)
        context_chunked = [[c] for c in chunks]

        flat_chunks = [c for group in context_chunked for c in group]

        compressed_chunks, word_list, word_label_list = _compress_chunks(
            chunk_list=flat_chunks,
            model=model,
            tokenizer=tokenizer,
            device=device,
            max_seq_len=max_seq_len,
            max_batch_size=max_batch_size,
            model_key=model_key,
            reduce_rate=reduce_rate,
            force_tokens=all_force,
            force_reserve_digit=force_reserve_digit,
            drop_consecutive=drop_consecutive,
            return_word_label=return_word_label,
            special_tokens=entry.get("special_tokens"),
        )

        compressed_text = "".join(compressed_chunks)
        # Restore original multi-word force tokens
        for placeholder, original in _ft_replacements.items():
            compressed_text = compressed_text.replace(placeholder, original)

        oai = _get_oai_tokenizer()
        n_orig = len(oai.encode(text))
        n_comp = len(oai.encode(compressed_text))
        saving = (n_orig - n_comp) * 0.06 / 1000
        ratio = 1 if n_comp == 0 else n_orig / n_comp

        result: Dict[str, Any] = {
            "compressed_prompt": compressed_text,
            "origin_tokens": n_orig,
            "compressed_tokens": n_comp,
            "ratio": f"{ratio:.1f}x",
            "rate": f"{1 / ratio * 100:.1f}%",
            "saving": f", Saving ${saving:.1f} in GPT-4.",
        }

        labels = None
        if return_word_label:
            words_flat: List[str] = []
            labels_flat: List[int] = []
            for wl, ll in zip(word_list, word_label_list):
                words_flat.extend(wl)
                labels_flat.extend(ll)
            labeled = "\t\t|\t\t".join(
                f"{w} {lbl}" for w, lbl in zip(words_flat, labels_flat)
            )
            result["fn_labeled_original_prompt"] = labeled
            labels = {
                "raw": labeled,
                "origin_tokens": n_orig,
                "compressed_tokens": n_comp,
                "ratio": result["ratio"],
            }

        return compressed_text, labels

    except Exception as e:
        logger.error("Native LLMLingua-2 compression failed: %s", e)
        return text, None


# ── JSON structured compression ───────────────────────────────

def compress_json_block(
    text: str,
    rate: float = 0.5,
    model_key: str = "xlm-roberta-large",
) -> str:
    """Compress JSON blocks by compressing long string values."""
    json_pattern = re.compile(r"\{[^{}]*\}")

    def _match(m: re.Match) -> str:
        block = m.group(0)
        try:
            data = json.loads(block)
            if not isinstance(data, dict):
                return block
            compressed = {}
            for k, v in data.items():
                if isinstance(v, str) and len(v) > 20:
                    compressed_v, _ = compress_with_llmlingua2(
                        text=v,
                        rate=rate,
                        model_key=model_key,
                    )
                    compressed[k] = compressed_v
                else:
                    compressed[k] = v
            return json.dumps(compressed, ensure_ascii=False)
        except (json.JSONDecodeError, Exception):
            return block

    return json_pattern.sub(_match, text)


# ── Auto-detect + compress (entry point for pipeline) ─────────

def auto_compress(
    text: str,
    lang: str = "en",
    fmt: str = "txt",
    profile_rate: float = 0.50,
    force_tokens: Optional[List[str]] = None,
    return_word_label: bool = False,
) -> Tuple[str, Optional[Dict], TextType]:
    text_type = detect_text_type(text, lang, fmt)
    strategy = TYPE_STRATEGY_MAP.get(text_type, CompressionStrategy.SKIP)
    model_key = TYPE_MODEL_MAP.get(text_type)

    # Semantic chunk pre-filter for very long texts (>1024 tokens)
    if len(text) > 4096 and text_type in (TextType.GENERAL, TextType.MEETING, TextType.MULTILINGUAL):
        try:
            from .chunk_semantic import compress_with_semantic_chunking
            _filtered, _ = compress_with_semantic_chunking(
                text, threshold=0.20, chunk_size=384
            )
            if 0.3 < len(_filtered) / len(text) < 0.95:
                text = _filtered
        except Exception:
            pass

    if strategy == CompressionStrategy.SKIP or model_key is None:
        return text, None, text_type

    # Try KOMPRESS first (faster, 8192 context, content-adaptive)
    try:
        from .kompress import is_kompress_available, compress_with_kompress

        if is_kompress_available():
            oai = _get_oai_tokenizer()
            n_tokens = len(oai.encode(text))
            # Prefer KOMPRESS for long texts (>512 tokens) or verbose types
            text_type_for_kompress = text_type in (
                TextType.MEETING, TextType.GENERAL, TextType.MULTILINGUAL
            )
            if n_tokens > 512 or text_type_for_kompress:
                threshold = max(0.25, min(0.75, 1.05 - profile_rate))
                compressed, _ = compress_with_kompress(text, threshold=threshold)
                if len(compressed) < len(text) * 0.85:
                    return compressed, None, text_type
    except Exception:
        pass

    # Fallback: LLMLingua-2 native compressor
    params = dict(TYPE_PARAMS.get(text_type, {}))
    params["rate"] = profile_rate
    params["return_word_label"] = return_word_label

    if force_tokens:
        all_force = list(set(force_tokens + MODALITY_TOKENS))
    else:
        all_force = list(MODALITY_TOKENS)

    if strategy == CompressionStrategy.STRUCTURED:
        result = compress_json_block(text, rate=params["rate"], model_key=model_key)
        return result, None, text_type

    compressed, labels = compress_with_llmlingua2(
        text=text,
        rate=params["rate"],
        force_tokens=all_force,
        force_reserve_digit=params.get("force_reserve_digit", True),
        chunk_end_tokens=params.get("chunk_end_tokens", [".", "\n"]),
        return_word_label=params.get("return_word_label", False),
        model_key=model_key,
    )
    return compressed, labels, text_type


# ── Convenience wrappers ──────────────────────────────────────

def get_token_labels(
    text: str,
    lang: str = "en",
    fmt: str = "txt",
    rate: float = 0.5,
) -> Optional[Dict]:
    _, labels, _ = auto_compress(
        text, lang=lang, fmt=fmt,
        profile_rate=rate, return_word_label=True,
    )
    return labels
