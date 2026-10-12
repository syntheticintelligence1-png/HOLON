"""Re-run the p_ir03_import_depth probe and compare with RESULT.json (audit F-M2-17).

    python bend/notes/p_ir03_import_depth/run.py [--write]

For every proofs/**/PROOF.bend: the exit code and first line of `bend PROOF.bend` and of `bend PROOF.bend --verdict`,
run from the file's own directory with the pinned checker (config/holon.json bend.cmd). --write records them in
RESULT.json; without it, prints them and exits 1 when they differ from RESULT.json. tests_m2/test_bend_notes.py
re-runs it.
"""
from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def bend_cmd() -> list[str]:
    cfg = json.loads((ROOT / "config" / "holon.json").read_text())
    cmd = cfg["bend"]["cmd"]
    return shlex.split(cmd) if isinstance(cmd, str) else list(cmd)


def first(out: str) -> str:
    lines = [x for x in out.strip().splitlines() if x.strip()]
    keep = [x for x in lines if x.startswith(("ALL PROOFS CHECK", "SOME PROOFS FAIL", "Error"))]
    return (keep or lines or [""])[0][:160]


def verdicts() -> dict:
    out = {}
    for p in sorted((HERE / "proofs").rglob("PROOF.bend")):
        rel = p.relative_to(HERE).as_posix()
        row = {}
        for mode, extra in (("bend", []), ("verdict", ["--verdict"])):
            r = subprocess.run(bend_cmd() + [p.name] + extra, cwd=p.parent, capture_output=True, text=True, timeout=300)
            text = r.stdout + r.stderr
            lines = text.splitlines()
            errs = []
            for i, x in enumerate(lines):
                if x.lstrip().startswith("Error"):
                    tail = [y.strip() for y in lines[i + 1:i + 3] if y.lstrip().startswith("- ")]
                    errs.append(" ".join([x.strip()] + tail)[:200])
            row[mode] = {"exit": r.returncode, "first": first(text), "errors": errs[:2]}
        out[rel] = row
    return out


def main(argv: list[str]) -> int:
    got = verdicts()
    if "--write" in argv:
        (HERE / "RESULT.json").write_text(json.dumps(got, indent=2, sort_keys=True) + "\n")
        return 0
    want = json.loads((HERE / "RESULT.json").read_text())
    print(json.dumps(got, indent=2, sort_keys=True))
    return 0 if got == want else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
