"""G11V for the Go part of rule PAR (I93): a PROVED gox law with a premise (go_branch's HypZ_len) needs a dual-checked
inhabitant of its premises; an unpremised PROVED law (go_round_trip) and a REFUTED one (its accepted counter-law
inhabits the premises) need none. holon.gate routes the gox laws here, apart from holon.inhabit's typed laws."""
from __future__ import annotations

import json


def g11v(gate, laws: list) -> tuple[bool, str]:
    bad, n = [], 0
    for law in laws:
        lid = law["law_id"]
        p = gate.root / "results" / gate.m / f"{lid}.json"
        if not p.is_file():
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))
        if rec.get("status") != "PROVED" or not rec.get("premises"):
            continue
        n += 1
        nv = rec.get("non_vacuity") or {}
        if nv.get("status") != "inhabited" or (rec.get("kernel") or {}).get("verdict") != "checked":
            bad.append(f"{lid}: a premised PROVED law without a dual-checked inhabitant")
    if bad:
        return False, "; ".join(bad)
    return True, f"{len(laws)} PAR Go laws, {n} premised PROVED (each inhabited)"
