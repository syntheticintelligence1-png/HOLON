"""L6 after V9 (key I56: definitions.V9 and l6, L6-C1..C4): holon.m5.metrics.l6, I54's definition, unchanged, over
the inputs V9 leaves; when V9 does not hold every target record is invalid with rule V9 and the decided threshold is
not_judged; the corpus is not scored (the lead's condition 5)."""
from __future__ import annotations

from ..m5 import metrics as M
from ..m5.common import overall

PENDING_CORPUS = "pending the corpus-truth key (the lead's condition 5): no corpus item is scored"


def l6_v9(inputs: dict, v9: dict) -> dict:
    inp = dict(inputs)
    demoted = []
    if not v9["holds"]:
        demoted = sorted({r["finding"] for r in inputs["records"] if r["kind"] == "target"})
        inp["records"] = [r for r in inputs["records"] if r["kind"] != "target"]
    out = M.l6(inp)
    for f in demoted:
        out["invalid"].setdefault(f, []).append("V9")
    out["invalid"] = {k: out["invalid"][k] for k in sorted(out["invalid"])}
    if not v9["holds"]:
        out["thresholds"]["decided"] = "not_judged"
    if inputs.get("corpus_truth") is None:
        out["corpus"] = {"label": "not_measured", "reason": PENDING_CORPUS}
    out["overall"] = overall(out["thresholds"])
    out["v9"] = {k: v9[k] for k in ("numerator", "denominator", "holds")}
    return out
