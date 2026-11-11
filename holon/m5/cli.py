"""python -m holon m5 <command> (I54):

  prereg   [--root DIR] [--check]   spec/M5/preregistration.json from the key I54 (holon.m5.definitions)
  controls [--root DIR] [--check]   spec/M5/controls/ (holon.m5.controls)
  census   [--root DIR] [--check]   results/M5/l10_census_base.json (holon.m5.census)
  metrics  --base [--root DIR] [--check]          results/M5/definitions_base.json: L6 and L9 over the base commit's
                                                  records with no game, module or intent record, and L10's census size
  metrics  --inputs FILE [--out FILE]             {"L6", "L9", "L10"} of an inputs document (holon.m5.metrics)
  env      [--root DIR] [--check]   I57: gen/M5/env/, laws/M5/ENV.json, results/M5/L_env_*.json and
                                    results/M5/env/sensitivity.json (holon.m5.env)
  l9       [--root DIR] [--check]   I57: results/M5/l9_I57.json, L9 by I54's definition (holon.m5.env)

Exit 0 written or unchanged, 1 a --check difference, 2 a usage error or a missing input.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import census, controls, definitions, env, metrics
from .common import ROOT, dumps


def base_metrics(root: Path) -> dict:
    c = definitions.base_commit(root)
    cls = definitions.classification(root)
    recs = definitions.records_at(root, c, ("M2", "M3"))
    dep = sorted(r["law_id"] for r in recs if metrics.environment_premises(r, cls))
    pop = definitions.findings(definitions.records_at(root, c, ("M3",)))
    cen = json.loads(census.path(root).read_text(encoding="utf-8"))
    return {"L6": metrics.l6({"population": pop, "expect": {}, "records": [], "controls": controls.all_games(),
                              "corpus_truth": None, "corpus_expect": {}}),
            "L9": metrics.l9({"records": recs, "classification": cls, "modules": [], "observation_sets": [],
                              "sensitivity": [], "base_dependent": dep}),
            "L10": {"census": len(cen["clauses"])}, "base_commit": c}


def _report(probs_or_done: list[str], check: bool, what: str) -> int:
    if check:
        for p in probs_or_done:
            print(f"m5 {what}: {p}")
        print(f"m5 {what}: {'CHECK OK' if not probs_or_done else 'CHECK FAILED'}")
        return 1 if probs_or_done else 0
    for p in probs_or_done:
        print(f"m5 {what}: wrote {p}")
    print(f"m5 {what}: {len(probs_or_done)} file(s) written")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="holon m5", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("command", choices=["prereg", "controls", "census", "metrics", "env", "l9"])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--base", action="store_true")
    ap.add_argument("--inputs", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    root = a.root.resolve()
    try:
        if a.command == "prereg":
            return _report(definitions.write(root, a.check), a.check, "prereg")
        if a.command == "controls":
            return _report(controls.write(root, a.check), a.check, "controls")
        if a.command == "census":
            return _report(census.write(root, a.check), a.check, "census")
        if a.command in ("env", "l9"):
            return _report(env.write(root, a.check, a.command), a.check, a.command)
        if a.base:
            p = root / "results" / "M5" / "definitions_base.json"
            text = dumps(base_metrics(root))
            have = p.read_text(encoding="utf-8") if p.is_file() else None
            if a.check:
                return _report([] if have == text else [f"{p.relative_to(root)}: differs"], True, "metrics")
            if have != text:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
                return _report([p.relative_to(root).as_posix()], False, "metrics")
            return _report([], False, "metrics")
        if a.inputs is None:
            ap.error("metrics needs --base or --inputs FILE")
        inp = json.loads(a.inputs.read_text(encoding="utf-8"))
        fns = {"L6": metrics.l6, "L9": metrics.l9, "L10": metrics.l10}
        out = {k: fns[k](inp[k]) for k in sorted(inp) if k in fns}
        text = dumps(out)
        if a.out:
            a.out.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 0
    except FileNotFoundError as e:
        print(f"m5 {a.command}: {e}", file=sys.stderr)
        return 2
