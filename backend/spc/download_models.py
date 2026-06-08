"""Download all models into local backend/spc/models/ directory.
Run once before shipping:
    python backend/spc/download_models.py

This makes the app fully offline — zero HuggingFace hub dependency at runtime."""
import os, sys, argparse

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

MODELS = {
    # ── LLMLingua-2 (token classification compressors) ────────
    "xlm-roberta-large": {
        "repo_id": "microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
        "size_gb": 2.2,
        "type": "compress",
    },
    "bert-base-multilingual": {
        "repo_id": "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
        "size_gb": 0.4,
        "type": "compress",
    },
    # ── KOMPRESS (ModernBERT token compressor) ─────────────────
    "kompress-base": {
        "repo_id": "chopratejas/kompress-base",
        "size_gb": 0.6,
        "type": "compress",
    },
    # ── French language model (base for future fine-tuning) ────
    "camembert-base": {
        "repo_id": "almanach/camembert-base",
        "size_gb": 0.4,
        "type": "lm",
    },
    # ── ModernBERT backbone (8192 ctx, KOMPRESS parent) ───────
    "modernbert-base": {
        "repo_id": "answerdotai/ModernBERT-base",
        "size_gb": 0.6,
        "type": "backbone",
    },
}


def _dir_size_mb(path: str) -> float:
    total = 0
    for dp, _, fn in os.walk(path):
        for f in fn:
            total += os.path.getsize(os.path.join(dp, f))
    return total / 1e6


def download_model(model_key: str, force: bool = False) -> str:
    from huggingface_hub import snapshot_download

    info = MODELS[model_key]
    repo_id = info["repo_id"]
    dest = os.path.join(MODELS_DIR, model_key)
    has_weights = (
        os.path.isfile(os.path.join(dest, "model.safetensors"))
        or os.path.isfile(os.path.join(dest, "pytorch_model.bin"))
    )

    if os.path.isdir(dest) and has_weights and not force:
        print(f"  OK {model_key} already downloaded ({_dir_size_mb(dest):.0f} MB)")
        return dest

    print(f"\n  Downloading {repo_id} ({info['size_gb']:.1f} GB, type={info['type']})...")
    print(f"  -> {dest}")
    os.makedirs(dest, exist_ok=True)

    snapshot_download(repo_id, local_dir=dest)

    print(f"  OK {model_key} downloaded ({_dir_size_mb(dest):.0f} MB)")
    return dest


def main():
    parser = argparse.ArgumentParser(description="Download all models for SPC")
    parser.add_argument("--force", action="store_true", help="Force re-download")
    parser.add_argument(
        "--model",
        choices=list(MODELS.keys()),
        help="Specific model (default: all)",
    )
    args = parser.parse_args()

    print("=== Downloading models ===")
    os.makedirs(MODELS_DIR, exist_ok=True)

    models_to_dl = [args.model] if args.model else MODELS
    for key in models_to_dl:
        try:
            download_model(key, force=args.force)
        except Exception as e:
            print(f"  X Failed for {key}: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
