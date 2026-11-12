"""L6's corpus accuracy against the corpus-truth key (key I56b; I54's corpus_mapping, unchanged).

An entry's truth is the pinned truth file's l6, read as given (an undocumented or disagreed answer is never resolved).
A finding is a corpus item only if it comes from I51's run on the entry's pre-fix commit (the rows of
results/eval/holon/corpus.json); without that file no entry maps a finding and the corpus has no item.
"""
from __future__ import annotations

import json
from pathlib import Path

TRUTH = "spec/M5/truth/corpus.json"
CORPUS = "spec/eval/corpus.json"
PROTOCOL = "spec/M5/lib/truth_protocol.json"
I51 = "results/eval/holon/corpus.json"


def mapping(root: Path) -> dict:
    load = lambda rel: json.loads((root / rel).read_text(encoding="utf-8"))  # noqa: E731
    truth = load(TRUTH)["entries"]
    excl = set(load(PROTOCOL).get("known_exclusions", {}))
    ent = {e["id"]: e for e in load(CORPUS)["entries"]}
    i51 = (root / I51).is_file()
    if i51:
        raise NotImplementedError("I51's rows exist: mapping findings to fix lines is a later key's (I56b found none)")
    rows = {}
    for cid, t in sorted(truth.items()):
        v = t["l6"]
        if cid in excl:
            why = "excluded (truth_protocol known_exclusions)"
        elif v not in ("rational", "irrational"):
            why = f"truth {v}: the entry contributes no item"
        else:
            why = ("I51 has not run: results/eval/holon/corpus.json does not exist, so no finding comes from a run on "
                   "the pre-fix commit")
        rows[cid] = {"l6": v, "fix_commit": ent[cid]["fix_commit"], "pre_fix": ent[cid]["fix_commit"] + "^",
                     "findings": [], "reason": why}
    return {"key": "I56b", "truth": TRUTH, "i51": I51 if i51 else None, "entries": rows}
