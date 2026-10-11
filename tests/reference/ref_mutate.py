"""Apply a mutation from predictions/M0_mutations.json to a facts document (frozen oracle)."""
from __future__ import annotations

import copy


def _walk(doc, parts):
    cur = doc
    for p in parts:
        cur = cur[int(p)] if isinstance(cur, list) else cur[p]
    return cur


def apply(facts: dict, edit: dict) -> dict:
    out = copy.deepcopy(facts)
    parts = [p.replace("~1", "/").replace("~0", "~") for p in edit["pointer"].lstrip("/").split("/")]
    if edit.get("op") == "remove_last":
        target = _walk(out, parts)
        assert isinstance(target, list) and target
        target.pop()
        return out
    parent = _walk(out, parts[:-1])
    key = parts[-1]
    if isinstance(parent, list):
        parent[int(key)] = copy.deepcopy(edit["value"])
    else:
        assert key in parent, f"pointer {edit['pointer']} does not exist"
        parent[key] = copy.deepcopy(edit["value"])
    return out
