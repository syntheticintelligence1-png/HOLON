"""The coverage debt of the total sort pass over every committed transitions document (I103, D2; the contract is the
docstring of tests_m6/test_i103_frontend_reach.py, rules F6 and R4-R5).

  python -m holon.sorts.coverage [--root DIR] [--out results/M6/i103/sorts_coverage.json] [--check]

The documents: every git-tracked *.extracted.json under gen/, spec/ and results/ (Go documents aside) that is a
transitions document (an "actions" list, extraction.kind "transitions"), sorted by path. Each is walked by
holon.sorts.extracted under holon-sort-types/0.3 with the seeds file below, and recorded with its sha256, status
("complete", or "refused" with every refusal), its debt entries and its debt per head. The walk is the sort pass's
first stage, the one that refused I50's and I50b's documents; whether the later stages accept a document is the
corpus run's record (results/M6/i103/<id>/), not this file's. Deterministic: sorted, no timestamps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from . import extracted as E

ROOT = Path(__file__).resolve().parents[2]
SEEDS = "spec/M3/lib/sort_seeds.json"
OUT = "results/M6/i103/sorts_coverage.json"


def documents(root: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(root), "ls-files", "--", "gen", "spec", "results"], capture_output=True,
                         text=True, check=True).stdout.splitlines()
    docs = []
    for rel in out:
        if not rel.endswith(".extracted.json") or rel.endswith(".go.extracted.json"):
            continue
        d = json.loads((root / rel).read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("actions"), list) \
                and (d.get("extraction") or {}).get("kind") == "transitions":
            docs.append(rel)
    return sorted(docs)


def report(root: Path) -> dict:
    seeds = json.loads((root / SEEDS).read_text(encoding="utf-8"))
    rows = []
    for rel in documents(root):
        b = (root / rel).read_bytes()
        doc = json.loads(b)
        row = {"path": rel, "sha256": hashlib.sha256(b).hexdigest()}
        try:
            w = E.walk("m", doc, seeds, E.SORT_TYPES_0_3)
            heads: dict = {}
            for e in w.debt:
                heads[e["head"]] = heads.get(e["head"], 0) + e["count"]
            row.update({"status": "refused" if w.refusals else "complete", "refusals": list(w.refusals),
                        "debt_heads": dict(sorted(heads.items())), "debt": w.debt})
        except E.ExtractedError as e:
            row.update({"status": "refused", "refusals": [str(e)], "debt_heads": None, "debt": None})
        rows.append(row)
    return {"doc": "I103: the total sort pass (holon-sort-types/0.3) over every committed transitions document; "
                   "written by python -m holon.sorts.coverage", "sort_types_version": E.SORT_TYPES_0_3,
            "seeds": SEEDS, "documents": rows,
            "summary": {"documents": len(rows), "complete": sum(r["status"] == "complete" for r in rows),
                        "with_debt": sum(bool(r["debt"]) for r in rows),
                        "heads": dict(sorted({h: sum((r["debt_heads"] or {}).get(h, 0) for r in rows)
                                              for r in rows for h in (r["debt_heads"] or {})}.items()))}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon.sorts.coverage")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    text = json.dumps(report(root), indent=1, sort_keys=True) + "\n"
    p = root / a.out
    if a.check:
        ok = p.is_file() and p.read_text(encoding="utf-8") == text
        print(f"holon sorts coverage --check: {'OK' if ok else 'DIFFERS'}")
        return 0 if ok else 1
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    s = json.loads(text)["summary"]
    print(f"holon sorts coverage: {s['complete']}/{s['documents']} complete, {s['with_debt']} with debt, heads "
          f"{s['heads']} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
