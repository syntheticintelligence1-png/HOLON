"""A rerun target beside the target it reruns (I50b): `holon target compare --target NAME [--check]`.

A rerun target's description (targets/<name>/target.json) names, in checkout.rerun_of, the target whose committed
result it reruns, and in checkout.contaminated, the label every number of the rerun carries. The comparison report
(results/targets/<name>/comparison.json, holon-rerun-comparison/0.1; rule C1 of the rerun's protocol, the target's
run.sidecar_rules) has one row per metric, {metric, sealed, rerun, contaminated: true}, each value read by the same rule
from the two targets' committed files:

  coverage.statements|extracted|unaccounted|debt_by_kind   gen/targets/<t>/coverage.json, summed over its documents
  diagram.V|E                                             the one diagram under gen/diagrams/<t>/
  gate.<check>                                            results/targets/<t>/gate_report.json (the earlier target's
                                                          checks in its order, then the rerun's new ones)
  derive.status|laws|by_rule_subform                      derive_refusal.json, else gen/targets/<t>/laws/DERIVATION.json
  run.status|by_status                                    run_refusal.json, else records/summary.json
  replay.entries                                          results/targets/<t>/replay.json

A value whose file does not exist is null, never 0. Nothing here names a target. Deterministic: sorted keys.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from . import targets as T

ROOT = Path(__file__).resolve().parents[1]
VERSION = "holon-rerun-comparison/0.1"
HEAD = ("coverage.statements", "coverage.extracted", "coverage.unaccounted", "coverage.debt_by_kind", "diagram.V",
        "diagram.E")
TAIL = ("derive.status", "derive.laws", "derive.by_rule_subform", "run.status", "run.by_status", "replay.entries")


class RerunError(ValueError):
    pass


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _read(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def _counts(xs) -> dict:
    return dict(sorted(Counter(xs).items()))


def metrics(name: str, root: Path) -> dict:
    g, r = Path(root) / "gen" / "targets" / name, Path(root) / "results" / "targets" / name
    out: dict = {}
    cov = _read(g / "coverage.json")
    docs = (cov or {}).get("documents") or []
    out["coverage.statements"] = None if cov is None else sum(d["statements"] for d in docs)
    out["coverage.extracted"] = None if cov is None else sum(d["extracted"] for d in docs)
    out["coverage.unaccounted"] = None if cov is None else sum(len(d["unaccounted"]) for d in docs)
    out["coverage.debt_by_kind"] = None if cov is None else _counts(x["kind"] for d in docs for x in d["debt"])
    dias = sorted((Path(root) / "gen" / "diagrams" / name).glob("*.json"))
    dia = _read(dias[0]) if len(dias) == 1 else None
    out["diagram.V"] = None if dia is None else len(dia["carriers"])
    out["diagram.E"] = None if dia is None else len(dia["edges"])
    gate = _read(r / "gate_report.json") or {}
    out["gate"] = {c: v["passed"] for c, v in (gate.get("checks") or {}).items()}
    ref, der = _read(r / "derive_refusal.json"), _read(g / "laws" / "DERIVATION.json")
    ok = der is not None and ref is None
    out["derive.status"] = f"refused at {ref['step']}" if ref else ("derived" if der is not None else None)
    out["derive.laws"] = len(der["laws"]) if ok else None
    out["derive.by_rule_subform"] = _counts(f"{x['rule']}/{x['subform']}" for x in der["laws"]) if ok else None
    rref, summ = _read(r / "run_refusal.json"), _read(r / "records" / "summary.json")
    if rref:
        out["run.status"] = f"refused at {rref['step']}"
    elif summ:
        out["run.status"] = "decided"
    else:
        out["run.status"] = "no law" if summ == {} else None
    out["run.by_status"] = _counts(summ.values()) if summ else None
    rep = _read(r / "replay.json")
    out["replay.entries"] = None if rep is None else len(rep["laws"])
    return out


def comparison(name: str, root: Path) -> dict:
    t = T.load(name, root)
    co = t.get("checkout") or {}
    base, label = co.get("rerun_of"), co.get("contaminated")
    if not base or not label:
        raise RerunError(f"target {name} is not a rerun target (checkout.rerun_of and checkout.contaminated)")
    T.load(base, root)
    s, r = metrics(base, root), metrics(name, root)
    rows = [{"metric": m, "sealed": s[m], "rerun": r[m], "contaminated": True} for m in HEAD]
    for c in list(s["gate"]) + [c for c in r["gate"] if c not in s["gate"]]:
        rows.append({"metric": f"gate.{c}", "sealed": s["gate"].get(c), "rerun": r["gate"].get(c),
                     "contaminated": True})
    rows += [{"metric": m, "sealed": s[m], "rerun": r[m], "contaminated": True} for m in TAIL]
    return {"comparison_version": VERSION, "label": label, "sealed": base, "rerun": name, "rows": rows,
            "doc": f"every number of the rerun target {name} beside its counterpart in the committed result of {base} "
                   f"(rule C1 of {(t.get('run') or {}).get('sidecar_rules')}); every row is labelled: {label}. The "
                   f"result of {base} is the result of record."}


def path(name: str) -> str:
    return f"results/targets/{name}/comparison.json"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="holon target compare")
    ap.add_argument("--target", required=True)
    ap.add_argument("--root")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root or ROOT).resolve()
    try:
        text = dumps(comparison(a.target, root))
    except (RerunError, T.TargetError) as e:
        print(f"holon target compare: {e}", file=sys.stderr)
        return 2
    p = root / path(a.target)
    if a.check:
        same = p.is_file() and p.read_text(encoding="utf-8") == text
        print(f"holon target compare: {path(a.target)} " + ("is up to date" if same else "differs from a fresh run"))
        return 0 if same else 1
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    print(f"holon target compare: wrote {path(a.target)}")
    return 0
