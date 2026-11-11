"""Round 8 (M3), A3 beyond the round's window: M3's whole law history, read two ways.

    python -m holon audit regress --from <parent of the first laws/M3 commit> --to <C> --json > regress_full.json
    python audit/rounds/M3/round8/a3_history.py regress_full.json > audit/rounds/M3/round8/a3_history.json

1. `holon audit regress`'s hash_changes over the whole history, grouped by commit, with how many STATEMENT_DIFF lines
   cover each (covered_by);
2. G2's own reading of the same history (holon.statement_diff.registry_changes: each commit against its first parent,
   a merge against its other parents only for laws the first parent lacks), and whether some line of
   laws/STATEMENT_DIFF.jsonl covers each change (holon.statement_diff.covers, every line taken as accepted: an upper
   bound on G2's coverage);
3. the two sets of (law, old hash, new hash) transitions compared;
4. for one law, both histories side by side.
Read-only git; run from the repository root at C.
"""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from holon import statement_diff as SD  # noqa: E402

reg = json.loads(Path(sys.argv[1]).read_text())
hc = reg["hash_changes"]
unc = [h for h in hc if not h.get("covered_by")]


def subject(c: str) -> str:
    return subprocess.run(["git", "log", "-1", "--format=%s", c], capture_output=True, text=True).stdout.strip()[:120]


def parents(c: str) -> int:
    return len(subprocess.run(["git", "rev-list", "--parents", "-n", "1", c], capture_output=True,
                              text=True).stdout.split()) - 1


by = Counter(h["commit"] for h in unc)
rc = SD.registry_changes("M3", Path("."))
lines = [json.loads(x) for x in Path("laws/STATEMENT_DIFF.jsonl").read_text().splitlines() if x.strip()]
g2_unc = [c for c in rc["changes"] if not any(SD.covers(e, c) for e in lines)]
lid = unc[0]["law_id"] if unc else None
g2_set = {(c["law_id"], c["old_hash"], c["new_hash"]) for c in rc["changes"] if c.get("new_hash")}
rg_set = {(h["law_id"], h["old"], h["new"]) for h in hc}
missed = [c for c in rc["changes"] if (c["law_id"], c["old_hash"], c["new_hash"]) in g2_set - rg_set]
out = {
    "regress": {"from": reg["from"], "to": reg["to"], "hash_changes": len(hc), "uncovered": len(unc),
                "uncovered_by_commit": {c: {"n": n, "parents": parents(c), "subject": subject(c)}
                                        for c, n in sorted(by.items())}},
    "g2_registry_changes": {"note": rc["note"], "changes": len(rc["changes"]),
                            "uncovered_by_any_line": len(g2_unc)},
    "compared": {"g2_transitions": len(g2_set), "regress_transitions": len(rg_set),
                 "g2_not_in_regress": len(g2_set - rg_set), "regress_not_in_g2": len(rg_set - g2_set),
                 "g2_not_in_regress_by_commit": dict(sorted(Counter(c["at"] for c in missed).items()))},
    "example": {"law_id": lid,
                "regress": [[h["commit"], h["old"][:19], h["new"][:19], "covered" if h["covered_by"] else "UNCOVERED"]
                            for h in hc if h["law_id"] == lid],
                "g2": [[c["at"], str(c["old_hash"])[:19], str(c["new_hash"])[:19]]
                       for c in rc["changes"] if c["law_id"] == lid]},
}
print(json.dumps(out, indent=1, sort_keys=True))
