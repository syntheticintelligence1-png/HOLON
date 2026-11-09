"""One rule for G6 and the final filter (I98): a REFUTED record stands only on a passed replay that G6 binds to it.

Every clause of G6 that judges a REFUTED record reports its judgment here. These are the typed I30 entries, UNDO, NAT,
DISCH, FACT, the contract, bundle and derivation laws, the PAR-init laws, and since I98 every other law
(holon.sorts.gate3.Gate3.g6_other).

  judged(law)          the clause examined the record;
  refuse(law, why)     the clause refuses it, because no passed replay binds it. Returns why, for the clause's own
                       detail.

Outside a collection both only return, so G6 itself is unchanged.

binding(milestone, root) runs G6 for the milestone at root inside a collection: holon.sorts.gate3.Gate3(milestone,
root).run(["G6"]). It returns (unbound, examined, G6's result) over the records that are REFUTED at root:
  unbound   {law: [why]}, the records a clause refused;
  examined  [law], the records some clause judged.
It raises RuntimeError when G6 did not judge: GENV failed, or the milestone cannot be checked. A caller never reads
"nothing refused" from a G6 that did not run.

The final filter (holon.refute_m3.concretize) takes every unbound record out of REFUTED. The record becomes UNKNOWN,
with G6's refusal as its bound and an attempt that keeps the witness and the replay. So a record the filter leaves
REFUTED is one G6 binds, and G6 fails exactly when this rule would move a record.
"""
from __future__ import annotations

import json
from pathlib import Path

_ACTIVE: list = []


class _Collection:
    def __init__(self):
        self.judged: set = set()
        self.refused: dict = {}


def judged(law: str) -> None:
    for c in _ACTIVE:
        c.judged.add(law)


def refuse(law: str, why: str) -> str:
    for c in _ACTIVE:
        c.judged.add(law)
        c.refused.setdefault(law, []).append(why)
    return why


def _status(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("status")
    except (OSError, ValueError, AttributeError):
        return None


def binding(milestone: str, root) -> tuple[dict, list, dict]:
    from .sorts.gate3 import Gate3
    root = Path(root)
    c = _Collection()
    _ACTIVE.append(c)
    try:
        rep = Gate3(milestone, root).run(["G6"])
    finally:
        _ACTIVE.remove(c)
    g6 = (rep.get("checks") or {}).get("G6")
    if g6 is None and "G6" in (rep.get("not_applicable") or {}):
        return {}, [], {"passed": True, "detail": f"not applicable: {rep['not_applicable']['G6']}"}
    if g6 is None or rep.get("setup_error") or str(g6.get("detail", "")).startswith("skipped"):
        raise RuntimeError(f"G6 did not judge {milestone}: "
                           f"{rep.get('setup_error') or (g6 or {}).get('detail') or 'no G6 result'}")
    refuted = {p.stem for p in (root / "results" / milestone).glob("L*.json") if _status(p) == "REFUTED"}
    unbound = {law: sorted(set(why)) for law, why in sorted(c.refused.items()) if law in refuted}
    return unbound, sorted(law for law in c.judged if law in refuted), g6


def unbound(milestone: str, root) -> dict:
    return binding(milestone, root)[0]


def examined(milestone: str, root) -> list:
    return binding(milestone, root)[1]
