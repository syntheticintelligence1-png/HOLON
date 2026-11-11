"""A5: every keccak256 hash-table entry of every M3 record's witness, witnesses or non_vacuity witness (the entries
holon audit oracles' O3 reads, holon.audit.oracles.table_entries), recomputed with Foundry's `cast keccak` (the pinned
CI install's cast, an implementation independent of holon/keccak.py), compared with the recorded word."""
import json, subprocess, sys, glob
from pathlib import Path
sys.path.insert(0, '.')
from holon.audit.oracles import table_entries
cast = sys.argv[1]
n = bad = 0
seen = {}
mism = []
for f in sorted(glob.glob('results/M3/L*.json')):
    rec = json.loads(Path(f).read_text())
    for where, o, k, wd in table_entries(rec):
        if o != 'keccak256':
            mism.append([f, where, o, 'not keccak256'])
            continue
        n += 1
        if k not in seen:
            p = subprocess.run([cast, 'keccak', k], capture_output=True, text=True)
            seen[k] = p.stdout.strip().lower()
        if seen[k] != str(wd).lower():
            bad += 1
            mism.append([f, where, k[:80], wd, seen[k]])
print(json.dumps({"entries": n, "distinct_keys": len(seen), "mismatches": bad, "detail": mism[:20]}, indent=1))
