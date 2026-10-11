"""Load facts/*.json and compute the facts hash (M0_SPEC section 3-4)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FACTS = "facts/morph_header.json"


def load_facts(path) -> dict:
    return json.loads(Path(path).read_text())


def facts_sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def header_fields(facts: dict) -> list[dict]:
    return facts["types"]["Header"]["fields"]


def widths(facts: dict) -> dict:
    return {f["name"]: f["width"] for f in header_fields(facts)}


def when_ok(when, version: int) -> bool:
    if not when:
        return True
    if "version_ge" in when:
        return version >= when["version_ge"]
    raise ValueError(f"unknown when-condition {when}")
