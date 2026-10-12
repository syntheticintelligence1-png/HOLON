"""holon CLI.

  python -m holon run  --milestone M0 [--facts PATH] [--out DIR] [--gen-dir DIR] [--no-registry] [--core import|paste]
  python -m holon gate --milestone M0 [--root DIR] [--report PATH] [--checks G6,G9]
  python -m holon audit prereg --milestone M2 [--root DIR]
  python -m holon audit status [--json] [--root DIR]
  python -m holon audit regress --from A --to B [--json] [--root DIR]
  python -m holon bind --milestone M1 [--accept-change REASON]
  python -m holon oracle zero-blob [--morph PATH]
  python -m holon oracle check --milestone M2 [--root DIR]   (oracle sidecar hypotheses: A4, G11V; I12)
  python -m holon checker-upgrade --to FINGERPRINT [--bend-cmd CMD] [--milestones M0,M1] [--out PATH]
  python -m holon replay [--milestone M] [--morph PATH] [--forge F] [--solc S] [--work DIR] [--write-pins]
  python -m holon lean --milestone M0 [--json] [--jobs N]   (Lean 4 second kernel, I9)
  python -m holon layout FN VERSION [--facts PATH]      (layout algebra, for humans)
  python -m holon diagram --milestone M2 [--out DIR] [--root DIR]   (one diagram per fact document)
  python -m holon sorts [--milestone M2] [--root DIR] [--out DIR] [--facts PATH ...]   (refined sorts, I13)
  python -m holon native --milestone M0 [--out PATH]    (native C model, results/M2/native.json, I16)
  python -m holon refine --milestone M0 [--edges E1,E2] [--out DIR] [--morph PATH] [--work DIR] [--fix C ..]
  python -m holon metrics --milestone M [--root DIR]    (results/<M>/metrics.json, I16)
"""
from __future__ import annotations

import argparse
import json
import sys


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ["checker-upgrade"]:  # its flags go to holon.checker_upgrade unparsed
        from . import checker_upgrade
        return checker_upgrade.main(argv[1:])
    if argv[:1] == ["lean"]:  # likewise for holon.lean
        from . import lean
        return lean.main(argv[1:])
    if argv[:1] == ["sorts"]:  # likewise for holon.sorts
        from . import sorts
        return sorts.main(argv[1:])
    if argv[:1] == ["native"]:  # likewise for holon.model_native
        from . import model_native
        return model_native.main(argv[1:])
    ap = argparse.ArgumentParser(prog="holon")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="drive every frozen law to PROVED / REFUTED / UNKNOWN")
    r.add_argument("--milestone", default="M0")
    r.add_argument("--facts")
    r.add_argument("--out")
    r.add_argument("--gen-dir")
    r.add_argument("--no-registry", action="store_true")
    r.add_argument("--core", choices=["import", "paste"], default="import",
                   help="M2+ milestones: import the core library (default) or paste it into each proof (baseline)")
    g = sub.add_parser("gate", help="re-check everything from scratch (G1-G5, G7, G11, GENV, canaries)")
    g.add_argument("--milestone", default="M0")
    g.add_argument("--root")
    g.add_argument("--report")
    g.add_argument("--checks", help="comma-separated subset to run after GENV (the report is marked partial)")
    bd = sub.add_parser("bind", help="bind each law to the kernel form of the definitions it reaches (spec/bindings)")
    bd.add_argument("--milestone", default="M0")
    bd.add_argument("--root")
    bd.add_argument("--accept-change", help="reason for changing an existing binding (logged in spec/bindings/changes.jsonl)")
    orc = sub.add_parser("oracle", help="oracle checks: `oracle zero-blob --morph PATH` (D2), `oracle check --milestone M2` "
                                        "(the oracle sidecar's hypotheses, I12); both write results/M2/hypotheses.json")
    orc.add_argument("which", choices=["zero-blob", "check"])
    orc.add_argument("rest", nargs=argparse.REMAINDER)
    cu = sub.add_parser("checker-upgrade", help="re-run gates and runs under a candidate checker; report every diff")
    cu.add_argument("rest", nargs=argparse.REMAINDER)
    au = sub.add_parser("audit", help="audits: `audit prereg --milestone M2` checks preregistration order; "
                                      "`audit status` summarises the adversarial audit findings; "
                                      "`audit regress --from A --to B` reports statement-hash changes and when each "
                                      "law, result and prediction was first committed (A3)")
    au.add_argument("what", choices=["prereg", "status", "regress"])
    au.add_argument("rest", nargs=argparse.REMAINDER)
    rp = sub.add_parser("replay", help="replay REFUTED witnesses on the real Go and Solidity code")
    rp.add_argument("--milestone", default="M0")
    rp.add_argument("--morph", help="morph-l2/morph checkout at the facts' commit (default: config replay.morph)")
    rp.add_argument("--forge", help="forge binary (default: config replay.forge); its sha256 must match the pin")
    rp.add_argument("--solc", help="solc 0.8.24 binary for forge --use (default: config replay.solc), pinned likewise")
    rp.add_argument("--work")
    rp.add_argument("--corpus", type=int, default=300, help="M1: random refinement traces (seeded)")
    rp.add_argument("--write-pins", action="store_true",
                    help="write the toolchain's current sha256 values into config/holon.json replay.* (a human "
                         "should review that change); without it, a missing or different pin refuses to run")
    ln = sub.add_parser("lean", help="Lean 4 second kernel (M0): regenerate gen/<m>/lean and check every file")
    ln.add_argument("rest", nargs=argparse.REMAINDER)
    lay = sub.add_parser("layout", help="print the symbolic byte layout of an encoder")
    lay.add_argument("fn")
    lay.add_argument("version", type=int)
    lay.add_argument("--facts", default="facts/morph_header.json")
    dg = sub.add_parser("diagram", help="build the protocol diagram of every fact document (gen/<M>/diagram)")
    dg.add_argument("--milestone", default="M2")
    dg.add_argument("--out", help="output directory (default: <root>/gen/<milestone>/diagram)")
    dg.add_argument("--root", help="repository root holding the fact documents (default: this checkout)")
    nt = sub.add_parser("native", help="build the native C model and record results/M2/native.json (I16)")
    nt.add_argument("rest", nargs=argparse.REMAINDER)
    rf = sub.add_parser("refine", help="per-edge refinement records against each edge's own implementation (I16)")
    rf.add_argument("--milestone", default="M0")
    rf.add_argument("--edges", help="comma-separated subset of the refined edges (default: all, plus cross_edge.json "
                                    "and spec/M2/disagreements.json)")
    rf.add_argument("--out", help="output directory for the records (default: results/M2/refinement)")
    rf.add_argument("--morph", help="morph checkout at the facts' commit (default: config replay.morph)")
    rf.add_argument("--work", help="scratch directory for the harness workspaces (default: a temporary directory)")
    rf.add_argument("--fix", action="append", help="a fix commit (40 lowercase hex) this run measures; repeatable")
    mt = sub.add_parser("metrics", help="write results/<M>/metrics.json and metrics_timing.json (I16)")
    mt.add_argument("--milestone", default="M0")
    mt.add_argument("--root")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        from .pipeline import main_run
        return main_run(a)
    if a.cmd == "gate":
        from .gate import main_gate
        return main_gate(a)
    if a.cmd == "bind":
        from .bindings import main_bind
        return main_bind(a)
    if a.cmd == "oracle":
        if a.which == "check":
            from . import oracle_check
            return oracle_check.main(a.rest)
        from .oracles import zero_blob
        return zero_blob.main(a.rest)
    if a.cmd == "checker-upgrade":
        from . import checker_upgrade
        return checker_upgrade.main(a.rest)
    if a.cmd == "audit":
        if a.what == "status":
            from .audit import status
            return status.main(a.rest)
        if a.what == "regress":
            from .audit import regress
            return regress.main(a.rest)
        from .audit import prereg
        return prereg.main(a.rest)
    if a.cmd == "replay":
        from .replay import main_replay
        return main_replay(a)
    if a.cmd == "refine":
        from .refinement import main_refine
        return main_refine(a)
    if a.cmd == "metrics":
        from .metrics import main_metrics
        return main_metrics(a)
    if a.cmd == "diagram":
        from . import diagram
        return diagram.run(a.milestone, a.out, a.root)
    if a.cmd == "layout":
        from . import facts, layout
        for i, c in enumerate(layout.layout(facts.load(a.facts), a.fn, a.version)):
            print(i, json.dumps(c))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
