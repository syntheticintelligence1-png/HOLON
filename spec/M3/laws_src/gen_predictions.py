#!/usr/bin/env python3
"""Generate spec/M3/predictions.json from each law file's `predicted` key.

Shape: {milestone: {lid: {"predicted", "finding": false, "proposal_id": null}}}.
Deterministic: sorted milestones and law ids.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
M3 = ("M3_msg", "M3_router", "M3_nat")


def main() -> int:
    out: dict[str, dict] = {}
    for m in M3:
        entries = {}
        for p in sorted((ROOT / "laws" / m).glob("L_*.json")):
            law = json.loads(p.read_text())
            entries[law["law_id"]] = {"predicted": law.get("predicted"),
                                      "finding": False, "proposal_id": None}
        out[m] = entries
    dest = ROOT / "spec" / "M3" / "predictions.json"
    dest.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(f"{dest.relative_to(ROOT)}: {sum(len(v) for v in out.values())} predictions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
