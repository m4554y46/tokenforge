import requests, tempfile, os, sys
API = "http://127.0.0.1:8765"

# Test 1: All categories work in optimizer
cats = ["general", "literary", "scientific", "commercial", "philosophical", "instructional", "legal", "financial", "technical", "administrative", "academic"]
print("=== Optimizer categories ===")
errors = 0
for cat in cats:
    r = requests.post(f"{API}/api/optimize", json={
        "prompt": "Write a machine learning algorithm that analyzes financial data for legal compliance",
        "target_model": "gpt-4o",
        "category": cat
    })
    ok = "OK" if r.status_code == 200 else f"ERR {r.status_code}"
    if r.status_code != 200:
        errors += 1
        print(f"  {cat:20s} {ok}")
    else:
        d = r.json()
        s = d["versions"][0]["savings_percent"]
        print(f"  {cat:20s} {ok}  Light savings: {s}%")
print(f"  Errors: {errors}")

# Test 2: Mode consistency - same text in optimizer vs document
text = "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed. It focuses on the development of computer programs that can access data and use it to learn for themselves."

print("\n=== Mode consistency ===")
r = requests.post(f"{API}/api/optimize", json={
    "prompt": text,
    "target_model": "gpt-4o",
    "category": "scientific"
})
opt = r.json()
orig_tokens = opt["original_tokens"]
print(f"Original: {orig_tokens} tokens")
for v in opt["versions"]:
    lb = (v["label"] or "").strip()
    print(f"  Optimizer {lb:12s} {v['optimized_tokens']} tokens ({v['savings_percent']}%)")

with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
    f.write(text)
    fname = f.name

for mode in ["light", "balanced", "aggressive"]:
    with open(fname, "rb") as f:
        r = requests.post(f"{API}/api/document/compress",
            files={"file": f},
            data={"mode": mode, "category": "scientific"})
    d = r.json()
    print(f"  Document {mode:12s} {d['compressed_tokens']} tokens ({d['savings_percent']}%)  mode={d['mode']}")

os.unlink(fname)

# Test 3: Category auto-detection
print("\n=== Category detection ===")
texts = {
    "legal": "The party shall indemnify and hold harmless the other party from any breach of contract obligations",
    "financial": "The company reported strong revenue growth with EBITDA margins improving across all segments",
    "technical": "The API specification defines the protocol architecture with high throughput and low latency",
    "academic": "This paper presents a novel methodology with peer-reviewed citations from leading journals",
}
for expected_cat, sample in texts.items():
    r = requests.post(f"{API}/api/optimize", json={
        "prompt": sample,
        "target_model": "gpt-4o",
    })
    detected = r.json().get("category", "?")
    match = "MATCH" if detected == expected_cat else f"MISMATCH (got {detected})"
    print(f"  {expected_cat:15s} {match}")

print("\n=== Document formats endpoint registers ===")
r = requests.get(f"{API}/api/document/formats")
print(f"  Registers: {r.json().get('registers', [])}")

print("\nDone!")
