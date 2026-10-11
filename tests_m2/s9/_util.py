"""Shared helpers for S9 tests."""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from holon import bend, ir  # noqa: E402


def load_json(p) -> dict:
    return json.loads(Path(p).read_text())


class StubGate:
    """A Gate-shaped stub: the attributes/methods the record-gate checks use."""

    def __init__(self, root, m="M1", results=None):
        self.root, self.m = Path(root), m
        self.results = Path(results) if results else self.root / "results" / m
        self.cfg = bend.config(self.root)
        self.checks = {}

    def records(self) -> dict:
        out = {}
        for law in ir.load_laws_any(self.m, self.root):
            p = self.results / f"{law['law_id']}.json"
            out[law["law_id"]] = load_json(p) if p.exists() else None
        return out


def m1_law(lid: str) -> dict:
    return load_json(REPO / "laws" / "M1" / f"{lid}.json")


def m1_record(lid: str) -> dict:
    return load_json(REPO / "results" / "M1" / f"{lid}.json")
