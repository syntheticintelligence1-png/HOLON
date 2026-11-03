"""I95's scorer row, the binding row (spec/M3/lib/blind_rerun_i95.json, comparison.binding_row). It writes
audit/blind/I95/binding.json from the blind tree and the lead at the pack commit, with the prereg instrument's
tests_m3/_i95.binding_rows:

    python -m tests_m3.i95_binding_row --tree <blind tree> --commit <P> [--out audit/blind/I95/binding.json]

The document stems are those of the typed-sorts sidecar's documents at <P> (spec/M3/lib/sort_types.json, "documents":
each file name without its .json suffix). Each row is {"document", "blind", "lead", "equal"}: the two records' sha256.
The row is reported beside the classes and is not counted in blind_agreement. It imports nothing from holon/ or tools/.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from tests_m3 import _i95 as I

ROOT = Path(__file__).resolve().parents[1]


def stems(root: Path, commit: str) -> list[str]:
    r = subprocess.run(["git", "-C", str(root), "show", f"{commit}:spec/M3/lib/sort_types.json"], capture_output=True,
                       check=True)
    docs = json.loads(r.stdout).get("documents") or []
    return sorted(Path(d).name[: -len(".json")] if d.endswith(".json") else Path(d).name for d in docs)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tests_m3.i95_binding_row")
    ap.add_argument("--tree", required=True, help="the blind tree (W at the session's end, or its runner copy)")
    ap.add_argument("--commit", required=True, help="the pack commit <P>")
    ap.add_argument("--out", default=f"{I.OUT}/binding.json")
    a = ap.parse_args(argv)
    rows = I.binding_rows(Path(a.tree), ROOT, a.commit, stems(ROOT, a.commit))
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"binding row: {sum(r['equal'] for r in rows)} of {len(rows)} equal; written to {a.out}")
    return 0 if rows and all(r["equal"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
