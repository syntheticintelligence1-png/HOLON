"""A6: each law the A1 driver re-ran on the unmutated target tree (its baseline runs, `holon run --milestone M3 --laws
<id>` from C) against the committed record of that law: status, statement hash and witness sha256 (the driver's
sha256 of json.dumps(witness, sort_keys=True))."""
import glob, hashlib, json, os, sys
root = sys.argv[1]
rows, bad = [], 0
for f in sorted(glob.glob(os.path.join(root, "audit/rounds/M3/round3/a1*.json"))):
    if f.endswith(".timings.json") or "spec" in os.path.basename(f):
        continue
    a = json.load(open(f))
    for lid, b in sorted((a.get("baseline") or {}).get("runs", {}).items()):
        rec = json.load(open(os.path.join(root, "results/M3", lid + ".json")))
        w = rec.get("witness")
        ws = hashlib.sha256(json.dumps(w, sort_keys=True).encode()).hexdigest() if w is not None else None
        same = (b.get("status") == rec.get("status") and b.get("statement_hash") == rec.get("statement_hash")
                and b.get("witness_sha256") == ws)
        bad += not same
        rows.append({"a1": os.path.basename(f), "law": lid, "baseline": b, "committed": {"status": rec.get("status"),
                     "statement_hash": rec.get("statement_hash"), "witness_sha256": ws}, "same": same})
for r in rows:
    print(("SAME " if r["same"] else "DIFF ") + r["a1"] + " " + r["law"] + " " + str(r["baseline"].get("status")))
print(f"{len(rows)} baseline runs, {bad} differ from the committed records")
if len(sys.argv) > 2:
    json.dump(rows, open(sys.argv[2], "w"), indent=1, sort_keys=True)
