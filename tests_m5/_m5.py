"""Shared helpers for the M5 acceptance tests (tests_m5/), generic across iterations.

They mirror tests_m4/_m4.py: the frozen helpers of tests/_util.py, the M5 predictions file, small readers, and a
read-only view of a commit's tree through git (base populations are read from the base commit, so a later change to
results/ does not move them). Nothing here imports holon/: a test that needs a holon module imports it inside the test
through holon_module(), so a missing module fails that test (red), never the import of the file. Helpers specific to
one iteration live in that iteration's own module (tests_m5/_i54.py).
"""
from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
from pathlib import Path

from tests._util import ROOT, load_json, run_holon  # noqa: F401  (frozen helpers)
from tests.reference import mini_schema

SPEC5 = ROOT / "spec" / "M5"
PREDICTIONS5 = SPEC5 / "predictions.json"


def holon_module(name: str):
    """Import a holon module inside a test, so a missing module fails that test (red), not the file."""
    return importlib.import_module(name)


def predictions(it: str) -> dict:
    return load_json(PREDICTIONS5)["iterations"][it]


def validate(instance, schema: dict) -> list[str]:
    return mini_schema.errors(instance, schema)


def file_sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(*args: str, cwd: Path = ROOT, data: bytes | None = None) -> bytes:
    """A read-only git command; a missing repository or history raises (the tests fail, never skip)."""
    r = subprocess.run(["git", *args], cwd=cwd, input=data, capture_output=True, check=True)
    return r.stdout


def tree_files(commit: str, prefix: str, cwd: Path = ROOT) -> list[str]:
    out = git("ls-tree", "-r", "--name-only", commit, "--", prefix, cwd=cwd).decode()
    return sorted(p for p in out.split("\n") if p)


def blobs(commit: str, paths: list[str], cwd: Path = ROOT) -> dict[str, bytes]:
    """{path: bytes} of paths at commit, one `git cat-file --batch` call; a missing path maps to None."""
    if not paths:
        return {}
    raw = git("cat-file", "--batch", cwd=cwd, data="".join(f"{commit}:{p}\n" for p in paths).encode())
    out, i = {}, 0
    for p in paths:
        nl = raw.index(b"\n", i)
        head = raw[i:nl].decode()
        if head.endswith(" missing"):
            out[p], i = None, nl + 1
            continue
        size = int(head.split()[2])
        out[p] = raw[nl + 1:nl + 1 + size]
        i = nl + 1 + size + 1
    return out


def dumps(obj) -> str:
    """The repo's canonical file format: json.dumps(obj, indent=2, sort_keys=True) + newline."""
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"
