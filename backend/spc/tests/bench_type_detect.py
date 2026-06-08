"""Benchmark native LLMLingua-2 — fully self-contained, zero llmlingua package dep."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
import tiktoken
from spc.llmlingua2 import auto_compress, detect_text_type, compress_with_llmlingua2

enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

samples = [
    ("Meeting",
     "Speaker 1: Hello everyone and welcome to the meeting. "
     "Speaker 2: Thank you, I would like to discuss the quarterly results. "
     "Speaker 1: Yes, indeed, the numbers show a significant improvement."),
    ("Legal",
     "CONTRAT DE PRESTATION. Article 1 : Le Prestataire doit livrer "
     "avant le 31 decembre 2025. Article 2 : Le Client doit payer "
     "5000 EUR sous 30 jours."),
    ("General",
     "I would like to kindly ask if you could please provide me with "
     "a detailed summary of the key features and benefits of the latest "
     "version of the product."),
    ("Short", "Hello, how are you?"),
]

print("=== auto_compress (multi-engine selector) ===")
for name, text in samples:
    compressed, labels, actual_type = auto_compress(text, profile_rate=0.45)
    orig_t = len(enc.encode(text))
    comp_t = len(enc.encode(compressed))
    pct = (1 - comp_t / orig_t) * 100
    print(f"[{name:10s}] type={actual_type.value:12s}  {orig_t:3d}->{comp_t:3d} tok  {pct:+5.1f}%  "
          f"\"{compressed[:60]}...\"")

print()
print("=== compress_with_llmlingua2 (direct, rate=0.5) ===")
for name, text in samples:
    compressed, labels = compress_with_llmlingua2(text, rate=0.5)
    orig_t = len(enc.encode(text))
    comp_t = len(enc.encode(compressed))
    pct = (1 - comp_t / orig_t) * 100
    print(f"[{name:10s}] {orig_t:3d}->{comp_t:3d} tok  {pct:+5.1f}%  \"{compressed[:60]}...\"")
