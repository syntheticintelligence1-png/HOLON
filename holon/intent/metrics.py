"""L10 computed by I54's definition (key I55 design L1, L2, TT, O, Y).

  python -m holon intent metrics [--root DIR] [--check]

writes results/M5/intent/l10_inputs.json (the inputs document of holon.m5.metrics.l10), results/M5/intent/l10.json
(L10, the trivially-true shares beside coverage, the pooled precision, corpus_recall not_measured, and the pinned
truth's sha256), results/M5/intent/obstructions.json and results/M5/intent/sym_route_i.json. This stage, and only
this stage, reads the census and the controls' truth documents.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .common import CONTROLS, LAWS, OUT, ROOT, dumps, load_key, norm, sha256_bytes, sha256_file, write_or_check

CENSUS = "results/M5/l10_census_base.json"
CHECKED = "ALL PROOFS CHECK"


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def records(root: Path) -> list[dict]:
    return [_load(p) for p in sorted((root / OUT / "records").glob("L_intent_*.json"))]


def _atom(a: dict) -> dict:
    return {"id": a["id"], "file": a["file"], "lines": list(a["lines"]), "text": a["text"]}


def _law(r: dict) -> dict:
    return {"law": r["law_id"], "clauses": list(r["clauses"]), "status": r["status"], "evidence": dict(r["evidence"]),
            "review": dict(r["review"]), "control": r["control"]}


def w1(r: dict) -> bool:
    return r["status"] in ("PROVED", "REFUTED") and r["evidence"]["marker"] == CHECKED and r["evidence"]["law_present"]


def w2(r: dict) -> bool:
    return r["review"]["verdict"] == "faithful" and r["review"]["reviewer"] != r["review"]["compiler"]


def meets(a: dict, c: dict) -> bool:
    return a["file"] == c["file"] and a["lines"][0] <= c["lines"][1] and c["lines"][0] <= a["lines"][1]


def compute(root: Path) -> dict:
    from ..m5.common import proportion
    from ..m5.metrics import l10
    census_p, atoms = root / CENSUS, _load(root / OUT / "atoms.json")
    controls = [_load(p) for p in sorted((root / CONTROLS).glob("i_*.json"))]
    recs = records(root)
    inputs = {"census": _load(census_p)["clauses"], "atomized": [_atom(a) for a in atoms["atoms"]],
              "laws": [_law(r) for r in recs], "controls": controls}
    out = {"l10": l10(inputs)}
    target = {a["id"]: a for a in inputs["atomized"]}
    count: dict = {}
    for r in recs:
        count[r["law_id"]] = count.get(r["law_id"], 0) + 1
    cover = [r for r in recs if count[r["law_id"]] == 1 and w1(r) and w2(r) and r["clauses"]
             and all(c in target for c in r["clauses"])
             and any(meets(target[c], k) for c in r["clauses"] for k in inputs["census"])]
    ctl = [r for r in recs if count[r["law_id"]] == 1 and r["control"] is not None and w1(r) and w2(r)]
    tt = lambda r: r["status"] == "PROVED" and r["trivial"]["trivially_true"] is True  # noqa: E731
    out["trivially_true"] = {"covering": proportion(sum(map(tt, cover)), len(cover)),
                             "controls": proportion(sum(map(tt, ctl)), len(ctl))}
    pooled = inputs["atomized"] + [_atom(a) for a in atoms["controls"]]
    out["pooled_precision"] = proportion(sum(any(meets(a, c) for c in inputs["census"]) for a in pooled), len(pooled))
    out["corpus_recall"] = {"label": "not_measured", "reason": "no corpus-truth key exists yet (the lead's condition "
                            "5: corpus truth gets its own key, run before any corpus item is scored)"}
    key = load_key(root)["thresholds"]
    out["census_sha256"] = sha256_file(census_p)
    out["controls_sha256"] = {p: sha256_file(root / p) for p in sorted(key["controls_sha256"])}
    out["inputs_sha256"] = sha256_bytes(dumps(inputs).encode("utf-8"))
    obs = {"controls": sorted(r["law_id"] for r in recs if r["control"] is not None and r["status"] == "REFUTED"
                              and w1(r) and w2(r)),
           "target": sorted(r["law_id"] for r in recs if r["control"] is None and r["status"] == "REFUTED"
                            and w1(r) and w2(r))}
    return {"inputs": inputs, "l10": out, "obstructions": obs, "route": route_i(root, recs)}


def route_i(root: Path, recs: list[dict]) -> dict:
    laws = {p.stem: _load(p) for p in sorted((root / LAWS).glob("L_intent_*.json"))}
    byid = {r["law_id"]: r for r in recs}
    atoms = {a["id"] for a in _load(root / OUT / "atoms.json")["atoms"]}
    out = []
    for fam in ("pi", "tau"):
        doc = _load(root / "results" / "M3" / "sym" / f"{fam}.json")
        for sp in doc["splits"]:
            acts = set(sp["eq"]) | set(sp["break"]) | set(sp["unknown"])
            marks = sorted(lid for lid, lw in laws.items() if fam == "pi" and lw["template"] == "access"
                           and norm(lw["binding"]["name"]) == norm(sp["role"]) and set(lw["actions"]) & acts
                           and lid in byid and byid[lid]["status"] == "PROVED" and w1(byid[lid]) and w2(byid[lid])
                           and all(c in atoms for c in lw["clauses"]))
            if not sp["break"]:
                reason, promoted = "no breaking action: nothing to promote", False
            elif fam != "pi":
                reason, promoted = f"no intent template marks the {fam} family", False
            elif not marks:
                reason, promoted = f"no reviewed PROVED access law names the role {sp['role']}", False
            else:
                reason, promoted = "route (i): a reviewed PROVED intent law marks the family as intended", True
            out.append({"document": doc["document"], "family": fam, "role": sp["role"], "break": sorted(sp["break"]),
                        "promoted": promoted, "reason": reason, "laws": marks})
    return {"route_version": "holon-intent-route-i/0.1", "splits": out}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="holon intent metrics")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = a.root.resolve()
    c = compute(root)
    files = {root / OUT / "l10_inputs.json": dumps(c["inputs"]), root / OUT / "l10.json": dumps(c["l10"]),
             root / OUT / "obstructions.json": dumps(c["obstructions"]),
             root / OUT / "sym_route_i.json": dumps(c["route"])}
    got = write_or_check(files, a.check)
    if a.check:
        for g in got:
            print(f"intent metrics: differs: {g}")
        print(f"intent metrics: {'CHECK OK' if not got else 'CHECK FAILED'}")
        return 1 if got else 0
    l = c["l10"]["l10"]
    print("intent metrics: L10 coverage {numerator}/{denominator}".format(**l["coverage"]),
          f"control_recall {l['control_recall']['numerator']}/{l['control_recall']['denominator']}",
          f"overall {l['overall']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
