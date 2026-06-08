import requests, tempfile, os, sys
API = "http://127.0.0.1:8765"

# 1. Optimizer with different categories
cats = ["general", "literary", "scientific", "commercial", "philosophical", "instructional", "financial", "legal", "technical", "nonexistent"]
for cat in cats:
    r = requests.post(f"{API}/api/optimize", json={
        "prompt": "Write a hello world program in Python using requests library",
        "target_model": "gpt-4o",
        "category": cat
    })
    status = "OK" if r.status_code == 200 else f"ERROR {r.status_code}"
    print(f"  Optimize category='{cat}': {status}")
    if r.status_code != 200:
        print(f"    Body: {r.text[:200]}")

# 2. Document compress with different categories
text = "Write a hello world program in Python. The program should use the requests library."
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
    f.write(text)
    fname = f.name

for cat in ["general", "financial", "legal", "nonexistent"]:
    with open(fname, "rb") as f:
        r = requests.post(f"{API}/api/document/compress",
            files={"file": f},
            data={"mode": "light", "category": cat})
    status = "OK" if r.status_code == 200 else f"ERROR {r.status_code}"
    print(f"  Doc compress category='{cat}': {status}")
    if r.status_code != 200:
        print(f"    Body: {r.text[:200]}")
    else:
        d = r.json()
        print(f"    orig={d['original_tokens']} comp={d['compressed_tokens']} savings={d['savings_percent']}%")

os.unlink(fname)

# 3. Compare same text: optimizer vs document (same category)
print("\n--- SAME TEXT COMPARISON ---")
text = """Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed. It focuses on the development of computer programs that can access data and use it to learn for themselves. The process of machine learning is similar to that of data mining, as both involve looking through data to find patterns and adjust program actions accordingly."""
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
    f.write(text)
    fname2 = f.name

# Optimizer Light
r = requests.post(f"{API}/api/optimize", json={
    "prompt": text,
    "target_model": "gpt-4o",
    "category": "scientific"
})
opt = r.json()
orig_tokens = opt["original_tokens"]
print(f"Original tokens: {orig_tokens}")
for v in opt["versions"]:
    print(f"  Optimizer {v['label']}: {v['optimized_tokens']} tokens ({v['savings_percent']}% savings)")

# Document Light
with open(fname2, "rb") as f:
    r = requests.post(f"{API}/api/document/compress",
        files={"file": f},
        data={"mode": "light", "category": "scientific"})
d = r.json()
print(f"  Document Light: {d['compressed_tokens']} tokens ({d['savings_percent']}% savings)")

# Document Aggressive
with open(fname2, "rb") as f:
    r = requests.post(f"{API}/api/document/compress",
        files={"file": f},
        data={"mode": "aggressive", "category": "scientific"})
d = r.json()
print(f"  Document Aggressive: {d['compressed_tokens']} tokens ({d['savings_percent']}% savings)")

os.unlink(fname2)
print("\nAll tests done.")
