"""holon CLI.

  python -m holon run  --milestone M0 [--facts PATH] [--out DIR] [--gen-dir DIR] [--no-registry]
  python -m holon gate --milestone M0 [--root DIR] [--report PATH] [--checks G6,G9]
  python -m holon audit prereg --milestone M2 [--root DIR]
  python -m holon bind --milestone M1 [--accept-change REASON]
  python -m holon oracle zero-blob [--morph PATH]
  python -m holon checker-upgrade --to FINGERPRINT [--bend-cmd CMD] [--milestones M0,M1] [--out PATH]
  python -m holon replay --morph PATH [--forge F] [--solc S] [--work DIR]
  python -m holon layout FN VERSION [--facts PATH]      (layout algebra, for humans)
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
    g.add_argument("--checks", help="comma-separated subset to run after GENV (the report is marked partial)")
    bd = sub.add_parser("bind", help="bind each law to the kernel form of the definitions it reaches (spec/bindings)")
    bd.add_argument("--milestone", default="M0")
    bd.add_argument("--root")
    bd.add_argument("--accept-change", help="reason for changing an existing binding (logged in spec/bindings/changes.jsonl)")
    orc = sub.add_parser("oracle", help="oracle checks: `oracle zero-blob --morph PATH` (D2, results/M2/hypotheses.json)")
    orc.add_argument("which", choices=["zero-blob"])
    orc.add_argument("rest", nargs=argparse.REMAINDER)
    cu = sub.add_parser("checker-upgrade", help="re-run gates and runs under a candidate checker; report every diff")
    cu.add_argument("rest", nargs=argparse.REMAINDER)
    au = sub.add_parser("audit", help="audits: `audit prereg --milestone M2` checks preregistration order")
    au.add_argument("what", choices=["prereg"])
    au.add_argument("rest", nargs=argparse.REMAINDER)
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
        from .oracles import zero_blob
        return zero_blob.main(a.rest)
    if a.cmd == "checker-upgrade":
        from . import checker_upgrade
        return checker_upgrade.main(a.rest)
    if a.cmd == "audit":
        from .audit import prereg
        return prereg.main(a.rest)
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
