"""Shared helpers for the M4 acceptance tests (tests_m4/), generic across iterations.

They mirror tests_m3/_m3.py: the frozen helpers of tests/_util.py, the M4 predictions file, and small readers. Nothing
here imports holon/: a test that needs a holon module imports it inside the test through holon_module(), so a missing
module fails that test (red), never the import of the file. Helpers specific to one iteration live in that iteration's
own module (tests_m4/_i48.py).
"""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

from tests._util import ROOT, copy_repo, load_json, run_bend, run_holon  # noqa: F401  (frozen helpers)
from tests.reference import mini_schema

SPEC4 = ROOT / "spec" / "M4"
PREDICTIONS4 = SPEC4 / "predictions.json"


def holon_module(name: str):
    """Import a holon module inside a test, so a missing module fails that test (red), not the file."""
    return importlib.import_module(name)


def predictions(it: str) -> dict:
    return load_json(PREDICTIONS4)["iterations"][it]


def validate(instance, schema_path: Path) -> list[str]:
    return mini_schema.errors(instance, load_json(schema_path))


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def file_sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dumps(obj) -> str:
    """The repo's canonical file format: json.dumps(obj, indent=2, sort_keys=True) + newline."""
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"
