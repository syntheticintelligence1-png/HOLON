"""I104 helpers (role inference): the role items a sidecar assigns, compared by the facts they name, never by role
names (a hand role's name is a human's word; an inferred one is generated).

A role item is a tuple:
  ("link", sol_document, sol_reader, sol_value, go_document, go_reader, go_value)   one per link role
  ("go_ops", document, carrier)                                                    one per Go-op component
  ("go_laws_document", document)                                                   the gox sidecar's Go document
  ("recompute", go_document, go_function, sol_document, action, store)             one per recompute function
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "M6" / "I104"
LINK_READERS = ("edge", "function", "constant", "global")


def load(p):
    return json.loads(Path(p).read_text())


def _reader(src: dict) -> tuple[str, str]:
    ks = [k for k in LINK_READERS if k in src]
    assert len(ks) == 1, src
    return ks[0], src[ks[0]]


def link_items(side: dict | None) -> set:
    out = set()
    for r in ((side or {}).get("roles") or {}).values():
        s, g = r["solidity"], r["go"]
        out.add(("link", s["document"], *_reader(s), g["document"], *_reader(g)))
    return out


def go_ops_items(side: dict | None) -> set:
    if not side:
        return set()
    return {("go_ops", c.get("document") or side["document"], c["carrier"])
            for c in (side.get("components") or {}).values()}


def go_laws_items(side: dict | None) -> set:
    if not side:
        return set()
    out = {("go_laws_document", side["document"])}
    for spec in (side.get("recompute") or {}).values():
        g, s = spec["go"], spec["solidity"]
        for fn in g["functions"]:
            out.add(("recompute", g["document"], fn, s["document"], s["action"], s["store"]))
    return out


def items(go_laws: dict | None, link: dict | None, go_ops: dict | None) -> set:
    return go_laws_items(go_laws) | link_items(link) | go_ops_items(go_ops)


def hand_items(root: Path = ROOT) -> set:
    lib = root / "spec" / "M3" / "lib"
    return items(load(lib / "go_laws.json"), load(lib / "link.json"), load(lib / "go_ops.json"))


def auto_items(d: Path) -> set:
    def opt(n):
        p = d / n
        return load(p) if p.is_file() else None
    return items(opt("go_laws.json"), opt("link.json"), opt("go_ops.json"))


def strip_stamp(x):
    """A record with every generator_sha256 removed (the lead's re-stamp moves only that field)."""
    if isinstance(x, dict):
        return {k: strip_stamp(v) for k, v in x.items() if k != "generator_sha256"}
    if isinstance(x, list):
        return [strip_stamp(v) for v in x]
    return x
