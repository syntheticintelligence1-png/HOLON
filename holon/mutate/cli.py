"""`python -m holon mutate ...` (I61). Exit 0 ok; 1 --check found a difference; 2 refused, nothing written.

    python -m holon mutate list                         the catalog recomputed from the pinned checkout, as JSON
    python -m holon mutate sheet [--out PATH] [--check]  the diff sheet
    python -m holon mutate project [--documents DIR] [--out PATH] [--check]
    python -m holon mutate replay --i16 [--tree DIR]
    python -m holon mutate gate [--check]
    python -m holon mutate run --milestone M2 [--only A001,...] [--control C1,...] [--baseline-only] [--work DIR]
                               [--jobs N] [--no-carry] [--dry-run] [--check]
    python -m holon mutate rate [--check]
"""
from __future__ import annotations

import sys

COMMANDS = ("list", "sheet", "project", "replay", "gate", "run", "rate")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv[0] not in COMMANDS:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd in ("list", "sheet"):
        from . import operators
        return operators.main(cmd, rest)
    if cmd == "project":
        from . import project
        return project.main(rest)
    if cmd == "replay":
        from . import replay
        return replay.main(rest)
    from . import run
    return run.main(cmd, rest)
