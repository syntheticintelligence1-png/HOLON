"""holon CLI.

  python -m holon run  --milestone M0 [--facts PATH] [--out DIR] [--gen-dir DIR] [--no-registry]
  python -m holon gate --milestone M0 [--root DIR] [--report PATH]
  python -m holon replay --morph PATH [--forge F] [--solc S] [--work DIR]
  python -m holon layout FN VERSION [--facts PATH]      (layout algebra, for humans)
"""
from __future__ import annotations

import argparse
import json
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="drive every frozen law to PROVED / REFUTED / UNKNOWN")
    r.add_argument("--milestone", default="M0")
    r.add_argument("--facts")
    r.add_argument("--out")
    r.add_argument("--gen-dir")
    r.add_argument("--no-registry", action="store_true")
    g = sub.add_parser("gate", help="re-check everything from scratch (G1-G5, G7, G11, GENV, canaries)")
    g.add_argument("--milestone", default="M0")
    g.add_argument("--root")
    g.add_argument("--report")
    rp = sub.add_parser("replay", help="replay REFUTED witnesses on the real Go and Solidity code")
    rp.add_argument("--milestone", default="M0")
    rp.add_argument("--morph", required=True, help="morph-l2/morph checkout at the facts' commit")
    rp.add_argument("--forge")
    rp.add_argument("--solc", help="path to a solc 0.8.24 binary (forge --use)")
    rp.add_argument("--work")
    rp.add_argument("--corpus", type=int, default=60, help="M1: random refinement traces")
    lay = sub.add_parser("layout", help="print the symbolic byte layout of an encoder")
    lay.add_argument("fn")
    lay.add_argument("version", type=int)
    lay.add_argument("--facts", default="facts/morph_header.json")
    so = sub.add_parser("sorts", help="M3: infer sort assignments, generate sorted facts, Bend sort types and the M3 registry")
    so.add_argument("--root")
    ase = sub.add_parser("assemble", help="M2: assemble a facts document purely from the extractors")
    ase.add_argument("--milestone", default="M0")
    ase.add_argument("--morph", required=True)
    ase.add_argument("--solc")
    ase.add_argument("--out", required=True)
    ase.add_argument("--coverage")
    mu = sub.add_parser("mutate", help="M2 A1: apply spec mutants, re-extract, compare law statuses")
    mu.add_argument("--mutants", default="spec/M2/mutants.json")
    mu.add_argument("--morph", required=True)
    mu.add_argument("--only")
    mu.add_argument("--work")
    mu.add_argument("--solc")
    mu.add_argument("--out", default="replay/M2/mutation/report.json")
    a = ap.parse_args(argv)
    if a.cmd == "sorts":
        from .sorts.pipeline import run_sorts
        run_sorts(a.root)
        return 0
    if a.cmd == "assemble":
        from .assemble.header import assemble, write_docs
        from pathlib import Path
        doc, cov = assemble(Path(a.morph), Path(a.solc) if a.solc else None)
        write_docs(doc, cov, Path(a.out),
                   Path(a.coverage) if a.coverage else Path("spec/M2/coverage/assemble_header.json"))
        print(f"wrote {a.out} ({len(doc['functions'])} functions)")
        return 0
    if a.cmd == "mutate":
        from .mutate.runner import run_mutants
        from pathlib import Path
        return run_mutants(Path(a.mutants), Path(a.morph), a.only.split(",") if a.only else None,
                           Path(a.work) if a.work else None,
                           Path(a.solc) if a.solc else None, Path(a.out))
    if a.cmd == "run":
        from .pipeline import main_run
        return main_run(a)
    if a.cmd == "gate":
        from .gate import main_gate
        return main_gate(a)
    if a.cmd == "replay":
        from .replay import main_replay
        return main_replay(a)
    if a.cmd == "layout":
        from . import facts, layout
        for i, c in enumerate(layout.layout(facts.load(a.facts), a.fn, a.version)):
            print(i, json.dumps(c))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
