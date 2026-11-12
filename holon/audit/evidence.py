"""The counted rounds' evidence, rebuilt from their targets (F-M3-37, audit M3/8; I101; the contract is the docstring of
tests_m3/test_audit_fixes_i101.py, S2).

    python -m holon audit evidence --milestone M --rebuild [--rounds streak|all|n,..] [--only a4|packet] [--root R]
                                   [--work DIR] [--json PATH]

The evidence rule (spec/<M>/lib/audit_evidence.json, holon.audit.rounds evidence_problems) checks each record of a
round that claims to count, header and content. This command checks the two records HOLON's own tools can rebuild from
the round's target commit: a4.json, by `holon audit vacuity --milestone M --round n --check` (holon.audit.vacuity),
and packet.json, by `holon audit hostile --milestone M --round n --check` (holon.audit.hostile's packet). Each reads
target_commit from the committed record, materializes that commit's tree from this repository's history, rebuilds the
record there and compares it with the committed file byte for byte. a1.json and a2.json are not rebuilt:
`holon audit mutation --check` and `hostile-input --check` rerun an auditor's mutants and hostile cases on the real
code, and are never run unattended.

--rounds streak (the default) is the rounds of the milestone's current streak, read from results/<M>/audit_status.json
of the root: the last `streak` counted rounds, on which its converged verdict rests. all is every round whose directory
holds a4.json or packet.json; n,.. names rounds. --root R reads the round records from R (a scratch copy) and the
history from this repository. --json PATH writes {"milestone", "rounds": {n: {record: identical|differs|error}}}.
Exit 0 iff every record checked is identical; 1 if one differs; 2 on an error. Nothing here names a law or a target.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORDS = {"a4": "a4.json", "packet": "packet.json"}


def streak_rounds(root: Path, milestone: str) -> list[int]:
    """The rounds of the milestone's current streak: the last `streak` counted rounds of its audit status."""
    st = json.loads((Path(root) / "results" / milestone / "audit_status.json").read_text(encoding="utf-8"))
    counted = [r["round"] for r in st.get("rounds") or [] if r.get("counted")]
    k = int(st.get("streak") or 0)
    return counted[-k:] if k else []


def all_rounds(root: Path, milestone: str) -> list[int]:
    d = Path(root) / "audit" / "rounds" / milestone
    out = []
    for p in sorted(d.glob("round*")):
        if p.is_dir() and p.name[5:].isdigit() and any((p / f).is_file() for f in RECORDS.values()):
            out.append(int(p.name[5:]))
    return sorted(out)


def rebuild_one(milestone: str, n: int, which: str, path: Path, work: Path) -> tuple[str, str]:
    """(identical|differs|error, the tool's last line) for one record."""
    if not path.is_file():
        return "error", f"{path} does not exist"
    argv = ["--milestone", milestone, "--round", str(n), "--out", str(path), "--check", "--work", str(work)]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            if which == "a4":
                from . import vacuity
                rc = vacuity.main(argv)
            else:
                from . import hostile
                rc = hostile.main(argv)
    except SystemExit as e:   # argparse or a tool's own exit
        rc = e.code if isinstance(e.code, int) else 2
    except Exception as e:    # noqa: BLE001 - reported as an error of this record, never as identical
        rc, buf = 2, io.StringIO(f"{type(e).__name__}: {e}")
    tail = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    return ("identical" if rc == 0 else "differs" if rc == 1 else "error"), (tail[-1] if tail else "")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon audit evidence", description=__doc__.split("\n\n")[0])
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--rebuild", action="store_true", required=True,
                    help="rebuild the rounds' a4.json and packet.json from their targets and compare")
    ap.add_argument("--rounds", default="streak", help="streak (default), all, or a comma-separated list")
    ap.add_argument("--only", choices=sorted(RECORDS), help="rebuild only that record")
    ap.add_argument("--root", default=str(ROOT), help="where the round records are (default: this repository)")
    ap.add_argument("--work", help="a scratch directory to keep (default: a temporary one, removed)")
    ap.add_argument("--json", help="write the outcome document to this path")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    m = a.milestone
    try:
        rounds = (streak_rounds(root, m) if a.rounds == "streak" else all_rounds(root, m) if a.rounds == "all"
                  else sorted({int(x) for x in a.rounds.split(",") if x.strip()}))
    except (OSError, ValueError, KeyError) as e:
        print(f"holon audit evidence: {e}", file=sys.stderr)
        return 2
    if not rounds:
        print(f"holon audit evidence: no round of {m} to rebuild ({a.rounds})", file=sys.stderr)
        return 2
    which = [a.only] if a.only else sorted(RECORDS)
    out: dict = {}
    worst = 0
    with tempfile.TemporaryDirectory(prefix="holon-evidence-") as tmp:
        base = Path(a.work).resolve() if a.work else Path(tmp)
        for n in rounds:
            d = root / "audit" / "rounds" / m / f"round{n}"
            for w in which:
                rel = f"audit/rounds/{m}/round{n}/{RECORDS[w]}"
                wd = base / f"round{n}_{w}"
                verdict, line = rebuild_one(m, n, w, d / RECORDS[w], wd)
                if not a.work:   # each rebuild materializes the target's whole tree: free it before the next
                    shutil.rmtree(wd, ignore_errors=True)
                out.setdefault(str(n), {})[RECORDS[w]] = verdict
                worst = max(worst, {"identical": 0, "differs": 1, "error": 2}[verdict])
                print(f"evidence: {rel}: {verdict}" + (f" ({line})" if verdict != "identical" and line else ""))
    doc = {"milestone": m, "rounds": out, "selection": a.rounds}
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{m}: {sum(len(v) for v in out.values())} record(s) of {len(rounds)} round(s) rebuilt: "
          + ("EVIDENCE OK" if worst == 0 else "EVIDENCE DIFFERS" if worst == 1 else "EVIDENCE ERROR"))
    return worst


if __name__ == "__main__":
    sys.exit(main())
