"""I119 (b): the exact affected counts per milestone (HUMAN_ANSWERS Q95), from the vault's (b) re-derivation.

  python tools/i119_rederive_counts.py --vault DIR [--out results/M6/I119/rederive.json]

Inputs (all in the vault, outside the repository): redecide/g1_wt_<M>.json (gate G1 on (b)'s tree, M0-M2) and
exact_affected_M3_all.json (M3: a decided law is affected when its decision trace reads an input (b) newly changes,
config/holon.json's pre-existing drift aside; when its statement changes; or when its declared facts document is one
(b)'s re-derivation changes). Written: per-milestone results (identical, or the count of affected decided laws,
PROVED and REFUTED together, Q56/Q89), and the sha256 of the affected list (I107's canonical bundle form). No law id.
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True)
    ap.add_argument("--out", default="results/M6/I119/rederive.json")
    a = ap.parse_args()
    v = Path(a.vault)
    out = {"rederive_version": "holon-i119-rederive/0.1", "milestones": {}}
    for m in ("M0", "M1", "M2"):
        g = json.loads((v / "redecide" / f"g1_wt_{m}.json").read_text())["checks"]["G1"]
        d = g["detail"]
        only_doc = (not g["passed"] and "records differ: []" in d and "differs: []" in d
                    and "M2 outputs differ from their regeneration: ['spec/M2/facts/morph_batch.go.extracted.json']" in d)
        out["milestones"][m] = {"g1_passed": g["passed"],
                                "result": "identical" if g["passed"] else (
                                    "identical but the re-extracted Go document (committed with (b))" if only_doc
                                    else "differs"),
                                "affected_decided_laws": 0 if (g["passed"] or only_doc) else None}
    aff = json.loads((v / "exact_affected_M3_all.json").read_text())
    dec = sorted(k for k, x in aff.items() if x["status"] in ("PROVED", "REFUTED"))
    out["milestones"]["M3"] = {"result": "affected", "affected_decided_laws": len(dec),
                               "affected_unknown_laws": sum(1 for x in aff.values() if x["status"] == "UNKNOWN"),
                               "undetermined_decided_laws": 0}
    bd = v / "bundle_rederive"
    if bd.exists():
        shutil.rmtree(bd)
    bd.mkdir()
    (bd / "affected_M3.json").write_text(json.dumps(sorted(aff), indent=1) + "\n")
    files = sorted(p for p in bd.rglob("*") if p.is_file())
    lines = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(bd).as_posix()}\n" for p in files)
    out["affected_bundle_sha256"] = hashlib.sha256(lines.encode()).hexdigest()
    (ROOT / a.out).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out["milestones"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
