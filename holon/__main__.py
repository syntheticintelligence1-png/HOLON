"""HOLON CLI: `python -m holon run|gate --milestone M0 ...`."""
from __future__ import annotations

import argparse
import sys


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="holon")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="run the pipeline (M0_SPEC section 6)")
    pr.add_argument("--milestone", required=True)
    pr.add_argument("--facts", default=None)
    pr.add_argument("--out", default=None)
    pr.add_argument("--gen-dir", default=None)
    pr.add_argument("--no-registry", action="store_true")

    pg = sub.add_parser("gate", help="run the gate (M0_SPEC section 7)")
    pg.add_argument("--milestone", required=True)
    pg.add_argument("--root", default=None)
    pg.add_argument("--report", default=None)

    pp = sub.add_parser("replay", help="fold the replay report into result records (M0_SPEC 8)")
    pp.add_argument("--milestone", required=True)
    pp.add_argument("--report", default=None)
    pp.add_argument("--out", default=None)

    args = p.parse_args(argv)
    if args.cmd == "run":
        from . import run
        return run.main(args)
    if args.cmd == "gate":
        from . import gate
        return gate.main(args)
    if args.cmd == "replay":
        from . import replay
        return replay.main(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
