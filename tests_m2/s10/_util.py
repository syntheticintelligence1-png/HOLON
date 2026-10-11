"""Shared helpers for S10 tests."""

import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECORDS = REPO / "spec" / "M2" / "refuter"
COVERAGE = REPO / "spec" / "M2" / "coverage" / "refuter.json"
FACTS = REPO / "facts" / "morph_header.json"


def load_laws(milestone):
    out = []
    for p in sorted((REPO / "laws" / milestone).glob("L_*.json")):
        out.append(json.loads(p.read_text()))
    return out


def record(lid):
    return json.loads((RECORDS / f"{lid}.json").read_text())


def expected(law):
    p = REPO / "results" / law.get("milestone", "") / f"{law['law_id']}.json"
    return json.loads(p.read_text())["status"] if p.exists() else None


def env_ready():
    return shutil.which("bend") and shutil.which("node")
