"""A5: every hash-table entry in results/M3/L*.json (witness, witnesses, non_vacuity.witness), under any key
("hashes" objects, which O3 reads, and "table" lists of [preimage, word] pairs, which it does not), checked against
the real Keccak-256 of foundry's `cast keccak` (independent of holon/keccak.py)."""
import json, glob, os, subprocess, sys, collections
root = sys.argv[1]
cast = sys.argv[2]
entries = []   # (law, where, keytype, preimage, word)
def walk(x, law, where, path):
    if isinstance(x, dict):
        for k, v in x.items():
            if k == "hashes" and isinstance(v, dict):
                for o, lst in v.items():
                    for e in lst if isinstance(lst, list) else []:
                        entries.append((law, where, f"hashes.{o}", e[0], e[1]))
            elif k == "table" and isinstance(v, list):
                for e in v:
                    if isinstance(e, list) and len(e) == 2 and all(isinstance(s, str) and s.startswith("0x") for s in e):
                        entries.append((law, where, "table", e[0], e[1]))
                    else:
                        entries.append((law, where, "table?", json.dumps(e)[:80], None))
            else:
                walk(v, law, where, path + [k])
    elif isinstance(x, list):
        for v in x:
            walk(v, law, where, path)
for f in sorted(glob.glob(os.path.join(root, "results/M3/L*.json"))):
    rec = json.load(open(f))
    law = os.path.basename(f)[:-5]
    walk(rec.get("witness"), law, "witness", [])
    walk(rec.get("witnesses"), law, "witnesses", [])
    walk((rec.get("non_vacuity") or {}).get("witness"), law, "non_vacuity", [])
kinds = collections.Counter(e[2] for e in entries)
print("entries by key:", dict(kinds))
print("laws with 'table' entries:", len({e[0] for e in entries if e[2] == "table"}))
uniq = sorted({e[3] for e in entries if e[4] is not None})
print("distinct preimages:", len(uniq))
real = {}
for i in range(0, len(uniq), 50):
    batch = uniq[i:i+50]
    for pre in batch:
        out = subprocess.run([cast, "keccak", pre], capture_output=True, text=True)
        real[pre] = out.stdout.strip().lower()
bad = [e for e in entries if e[4] is not None and int(real[e[3]], 16) != int(e[4], 16)]
print("mismatches vs cast keccak:", len(bad))
for e in bad[:20]:
    print("  MISMATCH", e[0], e[1], e[2], e[3][:80], "word", e[4], "real", real[e[3]])
odd = [e for e in entries if e[4] is None]
print("unparsed table items:", len(odd))
for e in odd[:5]: print("  ", e)
json.dump({"entries": len(entries), "by_key": dict(kinds), "distinct_preimages": len(uniq),
           "laws_with_table": sorted({e[0] for e in entries if e[2] == "table"}),
           "mismatches": [list(e) + [real.get(e[3])] for e in bad]},
          open(sys.argv[3], "w"), indent=1, sort_keys=True)
