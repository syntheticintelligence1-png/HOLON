"""I126: model-generation and loop-form counts of a composed run's Go-op documents (results/M6/I126/loop_forms.json;
P8, P9; spec/M6/predictions/I126.json's counting).

  python tools/i126_forms.py <run out dir> <output json>

For every Go-op document the run committed (<out>/<entry>/gen/goops/*.json), every op is classified by
holon.gen.goloop.shapes: its class (I67, straight, S1, S2, SEQ) or its Unsupported reason, reduced to a category with no
name, value or identifier in it; and every loop the frontend recorded under loop_forms "seq" is counted by its form
(kind, syntax, over, body, why). These are model-generation counts, before any law is decided (Q72), committed as
counts only: no entry, op or law is named.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import i122_shapes  # noqa: E402  (I122's categories, for the reasons outside SEQ)

SEQ = (   # (pattern in the SEQ part of a reason, category), first match wins
    (r"has no paths", "a loop of the sequence with no paths"),
    (r"gave no body, or a nested loop", "a loop with no body, or a nested loop"),
    (r"break out", "a break into the next loop"),
    (r"stale", "stale: a load after a store or a call"),
    (r"reads more than|does not compare a term with a constant|is not a comparison",
     "a condition outside the class (a call result, a carried value, another term)"),
    (r"not counted from a constant", "a loop not counted between constants"),
    (r"byte array of known length", "not a byte array of known length"),
    (r"one loop, not empty", "one loop (the single-loop classes' shape)"),
    (r"exit paths end|no exit path|last loop's exit", "exits outside the class"),
    (r"return path whose error", "an error outcome the frontend does not resolve"),
    (r"induction variable's type|not a value of", "an induction type or constant outside the class"),
    (r"iterations|leaves .* range|outside \[0|one byte|reads no cell|no body path", "trip, index or body outside"),
    (r"parameters$", "parameters: not exactly one"),
    (r"reserved or not an identifier", "op name"),
)


def category(reason: str) -> str:
    if "; seq: " in reason:
        part = reason.split("; seq: ", 1)[1]
        for pat, cat in SEQ:
            if re.search(pat, part):
                return "SEQ: " + cat
        return "SEQ: other"
    if "loop forms: " in reason:
        whys = sorted({w.rsplit(": ", 1)[-1] for w in reason.split("loop forms: ", 1)[1].split("; ")})
        return "0 loop bodies: " + ", ".join(whys)
    return i122_shapes.category(reason)


def form_key(f: dict) -> str:
    return "/".join(str(f.get(k)) for k in ("kind", "syntax", "over", "body", "why"))


def counts(out: Path) -> dict:
    from holon.gen import goloop, goshapes, gostraight
    by_class, reasons, forms, zero = Counter(), Counter(), Counter(), Counter()
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
                for f in op.get("loop_forms") or []:
                    forms[form_key(f)] += 1
                    if not lbs and f.get("body") == "none":
                        zero[str(f.get("why"))] += 1
            if isinstance(sh, goloop.Unsupported):
                reasons[category(str(sh))] += 1
            elif isinstance(sh, gostraight.Straight):
                by_class["straight"] += 1
            elif goshapes.is_shape(sh):
                by_class[sh.kind] += 1
            else:
                by_class["I67"] += 1
    return {"doc": "I126: model-generation and loop-form counts (holon.gen.goloop.shapes; the frontend's loop_forms) "
                   "over the Go-op documents the run committed; before any decision (Q72), counts only "
                   "(tools/i126_forms.py)",
            "go_op_documents": docs, "ops": ops, "ops_with_loop": with_loop, "loop_bodies": bodies,
            "by_class": dict(sorted(by_class.items())), "unsupported_reasons": dict(sorted(reasons.items())),
            "loop_forms": dict(sorted(forms.items())), "zero_body_loops": dict(sorted(zero.items()))}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    d = counts(Path(argv[0]))
    Path(argv[1]).parent.mkdir(parents=True, exist_ok=True)
    Path(argv[1]).write_text(json.dumps(d, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(d, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
