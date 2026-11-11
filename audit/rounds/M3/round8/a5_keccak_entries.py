"""Round 8 (M3), A5: every keccak256 entry the M3 result records carry, for an independent re-hash.

    python audit/rounds/M3/round8/a5_keccak_entries.py hashes|tables > entries.txt

hashes  every {"hashes": {"keccak256": [[key, word], ..]}} object anywhere in a record (what O3 reads);
tables  every "table": [[key, word], ..] list anywhere in a record (the DISCH and bundle witnesses' hash tables, which
        O3 does not read).
Prints "<key> <word>" per entry, deduplicated, sorted. Reads results/M3/L*.json only.
"""
import json
import sys
from pathlib import Path

mode = sys.argv[1]
out = set()


def walk(x):
    if isinstance(x, dict):
        for k, v in x.items():
            if mode == "hashes" and k == "hashes" and isinstance(v, dict):
                for pair in v.get("keccak256") or []:
                    if isinstance(pair, list) and len(pair) == 2:
                        out.add((pair[0], pair[1]))
            if mode == "tables" and k == "table" and isinstance(v, list):
                for pair in v:
                    if isinstance(pair, list) and len(pair) == 2 and all(isinstance(p, str) for p in pair):
                        out.add((pair[0], pair[1]))
            walk(v)
    elif isinstance(x, list):
        for v in x:
            walk(v)


for p in sorted(Path("results/M3").glob("L*.json")):
    walk(json.loads(p.read_text()))
for k, w in sorted(out):
    print(k, w)
