"""I122: the model-generation counts of a composed run's Go-op documents (results/M6/I122/loop_shapes.json; P8, P9).

  python tools/i122_shapes.py <run out dir> <output json>

For every Go-op document the run committed (<out>/<entry>/gen/goops/*.json), every op is classified by
holon.gen.goloop.shapes: its class (I67, straight, S1, S2) or its Unsupported reason, reduced to a reason category with
no name, value or identifier in it. These are model-generation reasons, before any law is decided (Q72), and are
committed as counts only: no entry, op or law is named.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CATEGORIES = (   # (pattern in the reason, category), first match wins
    (r"loop bodies \(the class", "loop bodies: not exactly one"),
    (r"parameters$", "parameters: not exactly one"),
    (r"the loop body has no paths", "loop body: no paths (another loop on a path, a store, a path limit)"),
    (r"not a range from 0|not a counted loop", "loop form: outside I67, S1 and S2"),
    (r"len\(X\) does not read a slice", "S1: the range is not over a slice the carrier holds"),
    (r"element of type|element type of X|elements of two types", "S1: element type"),
    (r"range index of type", "S1: index type"),
    (r"stale", "stale: a load after a store or a call"),
    (r"reads two cells", "two cells read"),
    (r"reads more than|does not compare a term with a constant|is not a comparison",
     "a condition outside the class (a call result, another term)"),
    (r"induction variable's type", "S2: induction type not recorded"),
    (r"byte array of known length", "S2: not a byte array of known length"),
    (r"iterations|leaves .* range|outside \[0|one byte", "S2: trip or index out of the class"),
    (r"return path whose error", "an error outcome the frontend does not resolve"),
    (r"exit paths end in|no body path continues|exit path reads a cell", "outcomes outside the class"),
    (r"body paths hold", "paths do not partition"),
    (r"straight-line class", "straight-line class: other"),
    (r"reserved or not an identifier", "op name"),
)


def category(reason: str) -> str:
    for pat, cat in CATEGORIES:
        if re.search(pat, reason):
            return cat
    return "other"


def counts(out: Path) -> dict:
    from holon.gen import goloop, goshapes, gostraight
    by_class, reasons = Counter(), Counter()
    ops = with_loop = bodies = docs = 0
    for p in sorted(out.glob("*/gen/goops/*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(doc.get("ops"), dict):
            continue
        docs += 1
        for name, sh in sorted(goloop.shapes(doc).items()):
            op = doc["ops"][name]
            ops += 1
            lbs = op.get("loop_bodies")
            if op.get("paths_reason") == "loop" or lbs:
                with_loop += 1
                if isinstance(lbs, list) and lbs and all(lb.get("paths") is not None for lb in lbs):
                    bodies += 1
            if isinstance(sh, goloop.Unsupported):
                reasons[category(str(sh))] += 1
            elif isinstance(sh, gostraight.Straight):
                by_class["straight"] += 1
            elif goshapes.is_shape(sh):
                by_class[sh.kind] += 1
            else:
                by_class["I67"] += 1
    return {"doc": "I122: model-generation counts (holon.gen.goloop.shapes) over the Go-op documents the counted run "
                   "committed; before any decision (Q72), counts only (tools/i122_shapes.py)",
            "go_op_documents": docs, "ops": ops, "ops_with_loop": with_loop, "loop_bodies": bodies,
            "by_class": dict(sorted(by_class.items())), "unsupported_reasons": dict(sorted(reasons.items()))}


def main(argv: list[str]) -> int:
    out, dest = Path(argv[1]), Path(argv[2])
    dest.write_text(json.dumps(counts(out), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"i122_shapes: wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
