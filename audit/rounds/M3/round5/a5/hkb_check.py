"""Check every literal hash-table entry (HKB{key, w_of_limbs(limbs)}) in the Bend files under the given roots
against the real Keccak-256, computed by Foundry's `cast keccak` (an implementation independent of HOLON).
Usage: python3 -I hkb_check.py <cast> <root> [<root> ...]"""
import re, sys, subprocess, json, os
cast = sys.argv[1]
roots = sys.argv[2:]
ent = re.compile(r"HKB\{\s*(Nil\{\}|\[[0-9,\s]*\])\s*,\s*[A-Za-z_]*\.?w_of_limbs\(\[([0-9,\s]+)\]\)\s*\}")
seen = {}
files = []
for root in roots:
    for d, _, fs in os.walk(root):
        for f in fs:
            if f.endswith(".bend"):
                files.append(os.path.join(d, f))
files.sort()
per_file = {}
for p in files:
    t = open(p).read()
    if "HKB{" not in t:
        continue
    n = 0
    for m in ent.finditer(t):
        k = m.group(1)
        key = b"" if k.startswith("Nil") else bytes(int(x) for x in k.strip("[]").split(",") if x.strip())
        limbs = [int(x) for x in m.group(2).split(",")]
        if len(limbs) != 8:
            print("ODD LIMBS", p, limbs); continue
        w = sum(l << (32 * i) for i, l in enumerate(limbs))
        seen.setdefault((key, w), set()).add(p)
        n += 1
    per_file[p] = (t.count("HKB{"), n)
unparsed = {p: v for p, v in per_file.items() if v[0] != v[1]}
keys = sorted({k for k, _ in seen})
real = {}
for k in keys:
    out = subprocess.run([cast, "keccak", "0x" + k.hex()], capture_output=True, text=True, check=True).stdout.strip()
    real[k] = int(out, 16)
bad = [(k.hex(), hex(w), sorted(ps)[:3]) for (k, w), ps in sorted(seen.items()) if real[k] != w]
print(json.dumps({"files_with_entries": len(per_file), "entries": sum(v[1] for v in per_file.values()),
                  "distinct_pairs": len(seen), "distinct_keys": len(keys),
                  "unparsed_files": {p: v for p, v in sorted(unparsed.items())}, "mismatches": bad}, indent=1))
