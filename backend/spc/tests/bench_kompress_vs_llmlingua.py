"""Benchmark: KOMPRESS vs LLMLingua-2 — quality + compression ratio per text type."""
import os, sys, textwrap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import tiktoken
from spc.llmlingua2 import detect_text_type, compress_with_llmlingua2
from spc.kompress import compress_with_kompress, is_kompress_available

enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

SAMPLES = {
    "Meeting": textwrap.dedent("""\
        Speaker 1: Good morning everyone, let's start the quarterly review meeting.
        Speaker 2: Thank you John, I have the financial report ready for presentation.
        Speaker 1: Excellent, could you please walk us through the key highlights?
        Speaker 2: Of course. Revenue increased by 15 percent to reach 2.3 million dollars.
        Speaker 1: That is great news. What about our operating expenses this quarter?
        Speaker 2: Operating expenses increased by 8 percent due to new hires in engineering.
        Speaker 1: I understand. Do you have a breakdown of the engineering costs?
        Speaker 2: Yes, the main drivers were salaries for the 12 new developers we onboarded.
    """).strip(),
    "Legal": textwrap.dedent("""\
        INTELLECTUAL PROPERTY ASSIGNMENT AGREEMENT
        This Agreement is made on June 1, 2026 between Acme Corp and John Smith.
        WHEREAS, John Smith has developed certain software inventions;
        WHEREAS, Acme Corp desires to acquire all rights to such inventions;
        NOW THEREFORE, the parties agree as follows:
        1. John Smith hereby assigns all right, title and interest in the Software.
        2. Acme Corp shall pay a one-time fee of $50,000 within 30 days of execution.
        3. This Agreement shall be governed by the laws of the State of Delaware.
        4. Any dispute shall be resolved through binding arbitration in Wilmington.
        IN WITNESS WHEREOF, the parties have executed this Agreement as of the date above.
    """).strip(),
    "Scientific": textwrap.dedent("""\
        Abstract: We propose a novel deep learning architecture for protein structure prediction.
        The model, termed ProteinNet-3D, combines a transformer encoder with a graph neural network
        to capture both sequential and structural dependencies. Our approach achieves a TM-score
        of 0.89 on the CASP15 benchmark, outperforming the previous state-of-the-art by 12.3 percent.
        We train on a dataset of 450,000 protein structures from the Protein Data Bank.
        The model uses 12 attention heads and 768 hidden dimensions with a total of 86 million parameters.
    """).strip(),
    "Finance": textwrap.dedent("""\
        QUARTERLY EARNINGS REPORT Q2 2026
        Revenue: $12,847,000 (up 23.4% YoY)
        Gross Profit: $8,214,000 (margin 63.9%)
        Operating Income: $3,891,000 (up 18.7% YoY)
        Net Income: $2,945,000 (EPS $0.42)
        Cash and Equivalents: $24,567,000
        Total Assets: $67,891,000
        Total Liabilities: $31,234,000
        Shareholders' Equity: $36,657,000
        The Board recommends a dividend of $0.15 per share payable on August 15.
    """).strip(),
    "Code": textwrap.dedent("""\
        def fibonacci(n: int) -> int:
            if n <= 0:
                raise ValueError("n must be positive")
            if n == 1 or n == 2:
                return 1
            a, b = 1, 1
            for _ in range(3, n + 1):
                a, b = b, a + b
            return b
    """).strip(),
    "Multilingual": textwrap.dedent("""\
        Bonjour, je voudrais confirmer ma reservation pour le vol AF1234
        a destination de Paris le 15 juillet. Mon numero de dossier est XYZ789.
        Could you also check if a vegetarian meal is available?
        Merci beaucoup pour votre aide precieuse.
    """).strip(),
}

print(f"{'Type':<16} {'Engine':<14} {'Orig':>6} {'Comp':>6} {'Red%':>7} {'Time':>7}")
print("=" * 58)

for cat_name, text in SAMPLES.items():
    orig_t = len(enc.encode(text))
    t = detect_text_type(text)

    # LLMLingua-2
    import time
    t0 = time.time()
    c1, _ = compress_with_llmlingua2(text, rate=0.50)
    t1 = time.time() - t0
    ct1 = len(enc.encode(c1))
    pct1 = (1 - ct1 / orig_t) * 100

    print(f"{cat_name:<16} {'LLMLingua-2':<14} {orig_t:>6} {ct1:>6} {pct1:>6.1f}% {t1*1000:>5.0f}ms")

    # KOMPRESS
    if is_kompress_available():
        t0 = time.time()
        c2, _ = compress_with_kompress(text, threshold=0.50)
        t2 = time.time() - t0
        ct2 = len(enc.encode(c2))
        pct2 = (1 - ct2 / orig_t) * 100
        print(f"{'':<16} {'KOMPRESS':<14} {orig_t:>6} {ct2:>6} {pct2:>6.1f}% {t2*1000:>5.0f}ms")

    # Best pick
    if is_kompress_available():
        best = "KOMPRESS" if ct2 <= ct1 else "LLMLingua-2"
    else:
        best = "LLMLingua-2"
    print(f"{'':<16} {'<< '+best:>22}")
    print()
