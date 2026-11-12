"""I111 (Q78): the planted blow-up of the torsor-role search, built from the search's semantics alone
(holon.sorts.solve; no target document is read). Writes tests_m6/fixtures/i111/search/blowup.json (canonical JSON).

    python tools/i111_search_fixture.py [--check]

One model "m", one affine component seeded Time through the class t (the pair T, so t is a point P):
  - n gadgets (a_i, b_i, t) under +: out = lhs + rhs, so exactly one of a_i, b_i is P. Each gadget has two solutions
    and the gadgets are independent given t. Their names sort before the cycle's.
  - an odd cycle (x, y, t) and (y, w, t) under + (x != y, y != w), and (x, w, r) under +. Arc consistency leaves every
    role open, but r = P needs x != w as well: three classes pairwise different over two roles, so r is only G (Dur).
The old strategy (chronological backtracking over the whole network) re-discovers the cycle's failure under every
combination of the gadgets' choices when it asks whether r can be P: 2^n nodes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests_m6" / "fixtures" / "i111" / "search" / "blowup.json"
SIZES = (6, 8, 10, 12)


def system(n: int) -> list[dict]:
    cs = [{"id": "seed_t", "kind": "seed", "model": "m", "sort": "Time", "vars": ["t"]}]
    for i in range(n):
        cs.append({"id": f"gadget_{i:03d}", "kind": "affine", "model": "m", "op": "+",
                   "vars": [f"a{i:03d}", f"b{i:03d}", "t"]})
    cs += [{"id": "cycle_1", "kind": "affine", "model": "m", "op": "+", "vars": ["x", "y", "t"]},
           {"id": "cycle_2", "kind": "affine", "model": "m", "op": "+", "vars": ["y", "w", "t"]},
           {"id": "cycle_3", "kind": "affine", "model": "m", "op": "+", "vars": ["x", "w", "r"]}]
    return cs


def document() -> str:
    doc = {"document": "i111_search_blowup", "doc": __doc__.strip().splitlines()[0],
           "query": {"model": "m", "var": "r", "family": "Dur"},
           "systems": {str(n): system(n) for n in SIZES}}
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = document()
    if "--check" in argv:
        ok = OUT.is_file() and OUT.read_text(encoding="utf-8") == text
        print("i111 search fixture: " + ("OK" if ok else "differs"))
        return 0 if ok else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
