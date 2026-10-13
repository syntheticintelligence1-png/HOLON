"""Shared helpers for the M3 acceptance tests (tests_m3/), generic across iterations.

They mirror tests_m2/_m2.py: the frozen helpers of tests/_util.py, the M3 predictions file, and small readers of the
committed laws and records. Nothing here imports holon/: a test that needs a holon module imports it inside the test
through holon_module(), so a missing module fails that test (red), never the import of the file. Helpers specific to
one iteration live in that iteration's own module (tests_m3/_i24.py) or test file.
"""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

from tests._util import ROOT, copy_repo, load_json, run_bend, run_holon  # noqa: F401  (frozen helpers)
from tests.reference import mini_schema

SPEC3 = ROOT / "spec" / "M3"
SCHEMAS = ROOT / "spec" / "schemas"
PREDICTIONS3 = SPEC3 / "predictions.json"


def holon_module(name: str):
    """Import a holon module inside a test, so a missing module fails that test (red), not the file."""
    return importlib.import_module(name)


def predictions(it: str) -> dict:
    return load_json(PREDICTIONS3)["iterations"][it]


def item(it: str, pid: str) -> dict:
    p = predictions(it)
    return next(x for x in p["predictions"] + p["regressions"] if x["id"] == pid)


def laws(m: str, root: Path = ROOT) -> dict[str, dict]:
    """laws/<m>/L*.json by law id (holon.ir.LAW_GLOB: L_* and, from IR 0.3, L3_* etc.)."""
    return {p.stem: load_json(p) for p in sorted((root / "laws" / m).glob("L*.json"))}


def records(m: str, root: Path = ROOT) -> dict[str, dict]:
    """results/<m>/L*.json by law id."""
    return {p.stem: load_json(p) for p in sorted((root / "results" / m).glob("L*.json"))}


def validate(instance, schema_path: Path) -> list[str]:
    return mini_schema.errors(instance, load_json(schema_path))


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(obj) -> str:
    return hashlib.sha256(canonical_json(obj)).hexdigest()


def file_sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dumps(obj) -> str:
    """The repo's canonical file format: json.dumps(obj, indent=2, sort_keys=True) + newline."""
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def write_json(p: Path, obj) -> None:
    Path(p).write_text(dumps(obj))
