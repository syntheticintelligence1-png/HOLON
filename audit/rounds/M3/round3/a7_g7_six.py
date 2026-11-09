"""A7: the check G7 makes (holon.bend.check_verdict on the record's PROOF.bend, beside holon.bend.check for bend2) for
every decided M3 record whose bendtt kernel entry is not 'checked', on scratch copies of the proof, its LAWS.bend and
every file they import (relative imports followed transitively). usage: g7_six.py ROOT SCRATCH OUT"""
import json, glob, os, re, shutil, sys
from pathlib import Path
root, scratch, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(root))
from holon import bend
IMP = re.compile(r"^import\s+(\.\.?/[^\s]+\.bend)", re.M)
def copy_closure(f: Path, seen: set):
    f = f.resolve()
    if f in seen:
        return
    seen.add(f)
    dst = scratch / f.relative_to(root.resolve())
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(f, dst)
    for rel in IMP.findall(f.read_text()):
        copy_closure((f.parent / rel), seen)
rows = []
for p in sorted(glob.glob(str(root / "results/M3/L*.json"))):
    r = json.load(open(p))
    if r.get("status") not in ("PROVED", "REFUTED"):
        continue
    k = {x["name"]: x["result"] for x in r.get("kernels") or []}
    if k.get("bendtt") == "checked":
        continue
    proof = root / r["artifacts"]["proof"]
    copy_closure(proof, set())
    sp = scratch / proof.resolve().relative_to(root.resolve())
    a, v = bend.check(sp), bend.check_verdict(sp)
    rows.append({"law": Path(p).stem, "status": r["status"], "record_bendtt": k.get("bendtt"),
                 "independence_class": r.get("independence_class"),
                 "bend2": [a.ok, a.first_line], "bendtt": [v.ok, v.first_line, v.out.strip().splitlines()[-1][:160] if v.out.strip() else ""]})
    print(rows[-1]["law"], "bend2", a.ok, "| bendtt", v.ok, v.first_line)
json.dump(rows, open(out, "w"), indent=1, sort_keys=True)
