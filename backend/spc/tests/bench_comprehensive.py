"""Comprehensive benchmark — all profiles × all categories.
Tests that compression actually reduces prompts in real-world conditions."""
import os, sys, json, textwrap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import tiktoken
from spc.pipeline import SPC
from spc.profiles import LIGHT, BALANCED, AGGRESSIVE, MAX, INDUSTRIAL
from spc.metrics import count_tokens

enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

spc_light = SPC(profile=LIGHT)
spc_balanced = SPC(profile=BALANCED)
spc_aggressive = SPC(profile=AGGRESSIVE)
spc_max = SPC(profile=MAX)
spc_industrial = SPC(profile=INDUSTRIAL)

SAMPLES = {
    "Meeting": textwrap.dedent("""\
        John: Good morning team, let's start the meeting.
        Sarah: Hi John, I've prepared the quarterly financial report.
        John: Great, could you walk us through the key numbers?
        Sarah: Sure, revenue increased by 15% this quarter to $2.3 million.
        John: What about our operating expenses?
        Sarah: They went up 8% due to the new hires in engineering.
        John: Okay, and what's our plan for next quarter?
        Sarah: We're planning to launch two new products and expand into the European market.
    """).strip(),

    "Legal": textwrap.dedent("""\
        INTELLECTUAL PROPERTY ASSIGNMENT AGREEMENT
        This Agreement is made on June 1, 2026 between Acme Corp and John Smith.
        WHEREAS, John Smith has developed certain software inventions;
        WHEREAS, Acme Corp desires to acquire all rights to such inventions.
        NOW THEREFORE, the parties agree as follows:
        1. John Smith hereby assigns all right, title and interest in the Software.
        2. Acme Corp shall pay a one-time fee of $50,000 within 30 days.
        3. This Agreement shall be governed by the laws of the State of Delaware.
        4. Any dispute shall be resolved through binding arbitration in Wilmington.
        IN WITNESS WHEREOF, the parties have executed this Agreement as of the date above.
    """).strip(),

    "Finance": textwrap.dedent("""\
        QUARTERLY EARNINGS REPORT — Q2 2026
        Revenue: $12,847,000 (up 23.4% YoY)
        Gross Profit: $8,214,000 (margin 63.9%)
        Operating Income: $3,891,000 (up 18.7% YoY)
        Net Income: $2,945,000 (EPS $0.42)
        Cash and Equivalents: $24,567,000
        Total Assets: $67,891,000
        Total Liabilities: $31,234,000
        Shareholders' Equity: $36,657,000
        The Board recommends a dividend of $0.15 per share payable on August 15.
        The company repurchased 1.2 million shares during the quarter at an average price of $34.50.
    """).strip(),

    "Scientific": textwrap.dedent("""\
        Abstract: We propose a novel deep learning architecture for protein structure prediction.
        The model, termed ProteinNet-3D, combines a transformer encoder with a graph neural network
        to capture both sequential and structural dependencies. Our approach achieves a TM-score
        of 0.89 on the CASP15 benchmark, outperforming the previous state-of-the-art by 12.3%.
        We train on a dataset of 450,000 protein structures from the Protein Data Bank.
        The model uses 12 attention heads and 768 hidden dimensions with a total of 86 million
        parameters. Training requires approximately 720 GPU hours on NVIDIA A100 hardware.
        We evaluate on three independent test sets and demonstrate consistent improvement across
        all metrics including RMSD, lDDT, and GDT-TS. Furthermore, we show that the learned
        representations transfer well to downstream tasks such as protein-protein interaction
        prediction and binding site identification.
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

        def is_prime(n: int) -> bool:
            if n < 2:
                return False
            for i in range(2, int(n ** 0.5) + 1):
                if n % i == 0:
                    return False
            return True

        # Generate first 20 Fibonacci numbers that are also prime
        fib_primes = []
        i = 1
        while len(fib_primes) < 20:
            f = fibonacci(i)
            if is_prime(f):
                fib_primes.append(f)
            i += 1
        print(fib_primes)
    """).strip(),

    "JSON": json.dumps({
        "users": [
            {"id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin", "permissions": ["read", "write", "delete"]},
            {"id": 2, "name": "Bob", "email": "bob@example.com", "role": "editor", "permissions": ["read", "write"]},
            {"id": 3, "name": "Charlie", "email": "charlie@example.com", "role": "viewer", "permissions": ["read"]}
        ],
        "config": {
            "siteName": "MyApp",
            "version": "2.1.0",
            "debug": False,
            "maxConnections": 100,
            "timeout": 30000,
            "features": {"darkMode": True, "betaAPI": False, "analytics": True}
        },
        "pagination": {"page": 1, "perPage": 50, "total": 3}
    }, indent=2),

    "Multilingual": textwrap.dedent("""\
        Bonjour, je voudrais confirmer ma réservation pour le vol AF1234
        à destination de Paris le 15 juillet. Mon numéro de dossier est XYZ789.
        Pourriez-vous également vérifier si un repas végétarien est disponible?
        Merci beaucoup pour votre aide.
        Hello, I would like to confirm my booking for flight AF1234 to Paris on July 15.
        My reference number is XYZ789. Could you also check if a vegetarian meal is available?
        Thank you very much for your help.
    """).strip(),

    "Short": "Hello, how are you?",

    "DataTemplate": textwrap.dedent("""\
        [CONTEXT]
        The user is a software engineer at a mid-sized tech company.
        They are building a microservices architecture using Kubernetes and Docker.
        Their team has 8 members and they use Scrum with 2-week sprints.

        [GOAL]
        Generate a detailed system design document for a new payment processing service.
        The service must handle 1000 transactions per second with 99.99% uptime.
        It should support credit cards, PayPal, and cryptocurrency payments.

        [OUTPUT_FORMAT]
        {
          "title": "...",
          "architecture": "...",
          "components": ["..."],
          "dataFlow": "...",
          "security": "...",
          "deployment": "..."
        }

        [CONSTRAINTS]
        - Must use existing PostgreSQL database
        - Must integrate with Stripe API
        - Must comply with PCI-DSS standards
        - Budget: $50,000 for infrastructure
    """).strip(),
}

PROFILES = [
    ("Light",    spc_light),
    ("Balanced", spc_balanced),
    ("Agressive", spc_aggressive),  # NB: typo in profile name
    ("Max",      spc_max),
    ("Industrial", spc_industrial),
]

def measure(text: str, result: str) -> dict:
    orig = len(enc.encode(text))
    comp = len(enc.encode(result))
    ratio = comp / orig if orig > 0 else 1.0
    pct = (1 - ratio) * 100
    return {
        "orig_tokens": orig,
        "comp_tokens": comp,
        "ratio": round(ratio, 4),
        "reduction_pct": round(pct, 1),
        "preserves": "COMPRESSED" if comp < orig else ("NO_CHANGE" if comp == orig else "INFLATED"),
    }

print("=" * 110)
print(f"{'Category':<16} {'Profile':<12} {'Orig':>6} {'Comp':>6} {'Red%':>6} {'Status':<14} Previews")
print("=" * 110)

failures = []

for cat_name, sample_text in SAMPLES.items():
    for prof_name, spc_instance in PROFILES:
        text = sample_text
        tag = f"[{cat_name}] {prof_name}"
        try:
            result = spc_instance.compile(text)
            compressed = result.compressed if result.compressed else text

            m = measure(text, compressed)
            status = m["preserves"]
            reduction = m["reduction_pct"]
            preview = compressed[:60].replace("\n", "\\n").strip()

            flag = ""
            if status == "INFLATED":
                flag = " !! INFLATED"
                failures.append(tag)
            elif status == "NO_CHANGE":
                flag = " !! NO_CHANGE"
                failures.append(tag)

            print(f"{cat_name:<16} {prof_name:<12} {m['orig_tokens']:>6} {m['comp_tokens']:>6} "
                  f"{reduction:>6.1f}% {status:<14} {preview}")

        except Exception as e:
            print(f"{cat_name:<16} {prof_name:<12} {'ERR':>6} {'':>6} {'':>6} {'ERROR':<14} {e}")
            failures.append(tag)

    print()

print("=" * 110)

if failures:
    print(f"\n!! {len(failures)} profile/category combinations flagged:")
    for f in failures:
        print(f"  - {f}")
else:
    print("\nALL profiles x ALL categories - compression successful, zero inflation.")
