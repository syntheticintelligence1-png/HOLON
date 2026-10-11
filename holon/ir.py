"""Law IR (holon-ir/0.1): canonical JSON, statement hashes, loading (M0_SPEC section 3)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .facts import ROOT

HASHED_KEYS = ("ir_version", "law_id", "rule", "facts_sha256", "statement")


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def statement_hash(law: dict) -> str:
    core = {k: law[k] for k in HASHED_KEYS}
    return "sha256:" + hashlib.sha256(canonical_json(core)).hexdigest()


def load_laws(milestone: str = "M0", root=None) -> list[dict]:
    root = Path(root) if root else ROOT
    out = []
    for p in sorted((root / "laws" / milestone).glob("L_*.json")):
        out.append(json.loads(p.read_text()))
    return out


def load_registry(milestone: str = "M0", root=None) -> dict:
    root = Path(root) if root else ROOT
    return json.loads((root / "laws" / milestone / "REGISTRY.json").read_text())
