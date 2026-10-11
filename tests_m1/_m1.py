"""Shared helpers for the M1 acceptance tests (state-machine milestone)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from tests._util import ROOT, load_json  # noqa: F401  (frozen M0 helpers: run_holon, copy_repo, validate, run_bend)

SPEC = ROOT / "spec" / "M1"
LAWS = ROOT / "laws" / "M1"


def predictions() -> dict:
    return {x["law_id"]: x for x in load_json(SPEC / "predictions.json")["laws"]}


def law_ids() -> list[str]:
    return sorted(p.stem for p in LAWS.glob("L_*.json"))


def apply_edit(facts: dict, edit: dict) -> dict:
    out = copy.deepcopy(facts)
    parts = edit["pointer"].lstrip("/").split("/")
    cur = out
    for p in parts[:-1]:
        cur = cur[int(p)] if isinstance(cur, list) else cur[p]
    k = parts[-1]
    if isinstance(cur, list):
        cur[int(k)] = copy.deepcopy(edit["value"])
    else:
        assert k in cur, edit["pointer"]
        cur[k] = copy.deepcopy(edit["value"])
    return out


def write_json(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, indent=1))
