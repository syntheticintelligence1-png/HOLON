#!/usr/bin/env python3
"""Freeze manifest for HOLON's protected files.

    python tools/freeze.py check   # anyone: verify FROZEN.sha256 (exit 1 on any drift)
    python tools/freeze.py write   # HUMAN ONLY: re-freeze after reviewing a change
    python tools/freeze.py digest  # print the manifest's own sha256 (pin this in prompts)

Protected = every file under FROZEN_ROOTS. A file added under a frozen root
(e.g. a tests/conftest.py) is drift too, not only an edited one.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "FROZEN.sha256"
FROZEN_ROOTS = [
    "AGENTS.md",
    "tools/freeze.py",
    "docs/M0_SPEC.md",
    "docs/BEND_PRIMER.md",
    "facts",
    "laws/M0",
    "predictions",
    "schemas",
    "tests",
    "bend/probes",
    "laws/A3",
    "spec/M2/A3/build_laws.py",
    "spec/M2/A3/sample_mutants.py",
    "spec/M2/A3/mutants.json",
]
SKIP_PARTS = {"__pycache__", ".pytest_cache"}


def frozen_files() -> list[str]:
    out = []
    for r in FROZEN_ROOTS:
        p = ROOT / r
        if p.is_file():
            out.append(r)
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and not (SKIP_PARTS & set(f.relative_to(ROOT).parts)) and f.suffix != ".pyc":
                    out.append(f.relative_to(ROOT).as_posix())
        else:
            out.append(r)  # missing root: reported by check
    return sorted(set(out))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write() -> None:
    lines = [f"{sha(ROOT / f)}  {f}" for f in frozen_files()]
    MANIFEST.write_text("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} entries; manifest digest {sha(MANIFEST)}")


def check() -> list[str]:
    if not MANIFEST.exists():
        return ["FROZEN.sha256 is missing"]
    listed = {}
    for line in MANIFEST.read_text().splitlines():
        if line.strip():
            h, f = line.split("  ", 1)
            listed[f] = h
    problems = []
    for f, h in sorted(listed.items()):
        p = ROOT / f
        if not p.is_file():
            problems.append(f"missing: {f}")
        elif sha(p) != h:
            problems.append(f"modified: {f}")
    for f in frozen_files():
        if f not in listed and (ROOT / f).exists():
            problems.append(f"unlisted file under a frozen root: {f}")
    return problems


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "write":
        write()
    elif cmd == "digest":
        print(sha(MANIFEST))
    else:
        probs = check()
        for p in probs:
            print(p)
        print("FROZEN OK" if not probs else f"FROZEN DRIFT ({len(probs)})")
        sys.exit(1 if probs else 0)
