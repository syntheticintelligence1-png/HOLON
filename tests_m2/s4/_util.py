"""Shared helpers for S4 tests."""

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXTRACTED = REPO / "spec" / "M2" / "extracted"
COVERAGE = REPO / "spec" / "M2" / "coverage"
MORPH = Path(os.environ.get("HOLON_MORPH", Path.home() / ".holon" / "morph"))


def load(name):
    return json.loads((EXTRACTED / name).read_text())


def morph_available():
    return MORPH.is_dir() and (MORPH / "common" / "batch" / "batch_header.go").exists()
