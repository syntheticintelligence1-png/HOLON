"""I100's round-6 addition (scope_amendment, spec/M3/amendments/I100.jsonl): the lead's triage of M3 audit round 6,
relayed by the coordinator on 2026-11-11 after the prereg (011778b2) and before any I100 build result, files F-M3-22
as a duplicate of F-M3-10. Its mutant go_getter_batchindex (round 6's A1 spec, on the round 6 branch until it lands
via #133) joins round 3's m05-m08 in I100's mutation predictions (I100-P10, TestRound6 of
tests_m3/test_par_record_i100.py). The run is tests_m3/_i100.py's mutation run on a one-mutant spec made from that
entry. Like _i100.py it imports nothing from holon/ or tools/.

    python -m tests_m3._i100r6 --work DIR [--root R]     docs/iterations/I100/mutations_round6.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from tests_m3 import _i100 as I

SOURCE = "audit/rounds/M3/round6/a1_spec.json"
SOURCE_COMMIT = "ef39bed5897aa7e8a0a147cb369f190a9e6e3fcc"   # origin/claude/brave-wright-2c5d0o-audit-m3-r6
MUTANT = "go_getter_batchindex"
# sha256 of the entry's json.dumps(sort_keys=True)
MUTANT_SHA256 = "43283661a4840d99ebd335a1304d2bfe07242289230de8a90825db76b96f7095"
OUT_NAME = "mutations_round6.json"


def _canon(m: dict) -> str:
    return hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest()


def source_spec(root) -> dict:
    """Round 6's A1 spec: the committed file when the tree has it (after #133 lands), else the file at SOURCE_COMMIT."""
    p = Path(root) / SOURCE
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    out = subprocess.run(["git", "-C", str(root), "show", f"{SOURCE_COMMIT}:{SOURCE}"], capture_output=True, text=True,
                         check=True).stdout
    return json.loads(out)


def spec(root) -> dict:
    """The one-mutant spec: round 6's go_getter_batchindex entry as it is, with round 6's milestone and budget."""
    s = source_spec(root)
    m = [x for x in s["mutations"] if x.get("id") == MUTANT]
    if len(m) != 1:
        raise ValueError(f"{SOURCE} holds {len(m)} entries {MUTANT}")
    return {"spec_version": s["spec_version"], "milestone": s["milestone"], "budget": s["budget"], "mutations": m,
            "note": f"I100: the entry {MUTANT} of {SOURCE} (round 6), alone"}


def run(root, work: Path) -> dict:
    """As _i100.run_mutation, for the one-mutant spec under work (round 6)."""
    root, work = Path(root), Path(work)
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    sp = spec(root)
    m = sp["mutations"][0]
    (work / "spec.json").write_text(I.dumps(sp), encoding="utf-8")
    head = I.git(root, "rev-parse", "HEAD").strip()
    rc, txt = I.holon(root, ["audit", "mutation", "--milestone", "M3", "--round", "6", "--spec", work / "spec.json",
                             "--target", head, "--out", work / "a1.json", "--work", work / "w", "--keep-trees",
                             "--max-law-runs", "0"])
    res = {"mutant": MUTANT, "source": SOURCE, "source_commit": SOURCE_COMMIT, "mutant_sha256": _canon(m),
           "target": head, "driver": {"exit": rc}}
    tree = work / "w" / "m" / MUTANT / "tree"
    try:
        if (work / "a1.json").is_file():
            r = json.loads((work / "a1.json").read_text(encoding="utf-8"))["mutations"][0]
            der = r.get("derivation") or {}
            res["driver"].update(verdict=r.get("verdict"), why=r.get("why"), added=der.get("added"),
                                 dropped=der.get("dropped"), statement_changed=der.get("statement_changed"))
        if not (tree / I.BASIS).is_file():
            res["verdict"] = ["not_evaluated"]
            res["detail"] = "no par_record basis in the mutant's tree: " + txt[-600:].replace(str(work), "<work>")
            return res
        base, mut = I._instances(I.load(root, I.BASIS)), I._instances(I.load(tree, I.BASIS))
        res["instances"] = {f"{e}|{f}|v{v}": x for (e, f, v), x in sorted(mut.items())}
        res["changed"] = sorted(f"{e}|{f}|v{v}" for (e, f, v) in base if mut.get((e, f, v)) != base[(e, f, v)])
        res["dropped"] = sorted(f"{e}|{f}|v{v}" for (e, f, v) in base if (e, f, v) not in mut)
        res["obstructed"] = sorted(f"{e}|{f}|v{v}" for (e, f, v), x in mut.items() if x["missing"])
        keep = None
        for p in sorted((tree / "laws" / "M3").glob("L_par_rt_*.json")):
            lw = json.loads(p.read_text(encoding="utf-8"))
            old = root / "laws" / "M3" / p.name
            if lw.get("subform") == "round_trip" and lw.get("facts", "").startswith(I.CODEC_DIR + "/") \
                    and old.is_file() and json.loads(old.read_text(encoding="utf-8"))["statement"] == lw["statement"]:
                keep = p.stem
                break
        rc1, _ = I.holon(tree, ["run", "--milestone", "M3", "--laws", keep], tree=tree) if keep else (None, "")
        res["model_refresh"] = {"law": keep, "exit": rc1}
        recs = sorted(x["law"] for x in mut.values() if x["law"])
        rc2, _ = (I.holon(tree, ["run", "--milestone", "M3", "--laws", ",".join(recs)], tree=tree) if recs
                  else (None, ""))
        st = {}
        for lid in recs:
            rp = tree / "results" / "M3" / f"{lid}.json"
            r = json.loads(rp.read_text(encoding="utf-8")) if rp.is_file() else {}
            st[lid] = {"status": r.get("status"), "failing_conjunct": r.get("failing_conjunct"),
                       "statement_hash": r.get("statement_hash")}
        res["record_runs"] = {"exit": rc2, "laws": st}
        rc3, t3 = I.holon(tree, ["backtest", "--milestone", "M3", "--out", work / "backtest.json"], tree=tree)
        bt = json.loads((work / "backtest.json").read_text(encoding="utf-8")) if (work / "backtest.json").is_file() \
            else None
        res["backtest"] = {"exit": rc3, **(I._table(bt) or {"detail": t3[-600:].replace(str(work), "<work>")})}
        v = []
        if res["obstructed"]:
            v.append("obstructed")
        if any(x["status"] == "REFUTED" for x in st.values()) or any(
                s == "REFUTED" for r in (res["backtest"].get("rows") or {}).values() for _, s in r["bridges"]):
            v.append("refuted")
        if res["dropped"]:
            v.append("dropped")
        if not v:
            v = ["not_caught"] if rc == 0 and rc3 == 0 and bt is not None else ["not_evaluated"]
        res["verdict"] = v
        res["caught"] = bool({"obstructed", "refuted"} & set(v))
        return res
    finally:
        shutil.rmtree(work / "w", ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tests_m3._i100r6")
    ap.add_argument("--root", default=str(I.ROOT))
    ap.add_argument("--work", required=True)
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    out = root / I.OUT
    out.mkdir(parents=True, exist_ok=True)
    doc = {"document": "i100_mutations_round6", "key": I.KEY, "mutants": {MUTANT: run(root, Path(a.work))}}
    (out / OUT_NAME).write_text(I.dumps(doc), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
