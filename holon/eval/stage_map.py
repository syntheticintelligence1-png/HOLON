"""The stage map of the total pass (I103, D2): which later stage refuses a whole document, and on what.

  python -m holon.eval.stage_map [--protocol spec/M6/lib/i103_run.json] [--out results/M6/i103/stage_map.json]
                                 DOC [DOC ...]

Each committed transitions document is run, alone, through the stages of the corpus protocol (holon eval holon's H3-H4:
sorts, types, model, disch, derive, run) in a scratch root with the protocol's generic sidecars, exactly as a corpus
entry's documents are (holon.eval.holon_run._rules). The record per document: each stage's status and its message's
tail (paths normalized), the laws derived and their statuses. Nothing is written into the repository but --out.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from . import common
from . import holon_run as H

ROOT = common.ROOT


def run_doc(root: Path, proto: dict, rel_doc: str) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="holon-i103-map-"))
    try:
        ctx = H.Ctx(tmp, tmp / "checkout")
        (tmp / "checkout").mkdir()
        S = H.scratch_root(root, tmp, "none/none", tmp / "checkout")
        timing: dict = {}
        R = H.Runner(ctx, S, proto, timing)
        rel = f"{proto['out']}/map"
        (S / rel / "sidecars").mkdir(parents=True)
        (S / rel / "facts").mkdir(parents=True)
        name = Path(rel_doc).name
        shutil.copy2(root / rel_doc, S / rel / "facts" / name)
        # the document's own extraction sidecar (holon types and the model generator check it by sha256)
        side = ((json.loads((root / rel_doc).read_text(encoding="utf-8")).get("extraction") or {}).get("sidecar")
                or {}).get("path")
        if side and (root / side).is_file() and not (S / side).exists():
            (S / side).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / side, S / side)
        stages: dict = {}
        H._rules(R, S, rel, proto["milestone"], proto, [{"file": name}], stages)
        laws = []
        M = proto["milestone"]
        for p in sorted((S / "laws" / M).glob("L*.json")):
            rec = S / "results" / M / p.name
            st = json.loads(rec.read_text())["status"] if rec.is_file() else "no_record"
            laws.append({"law": p.stem, "status": st})
        debt = S / "gen" / M / "sorts" / "coverage_debt.json"
        heads = None
        if debt.is_file():
            heads = {}
            for d in json.loads(debt.read_text())["documents"]:
                for h, n in d["debt_heads"].items():
                    heads[h] = heads.get(h, 0) + n
        return {"document": rel_doc, "stages": stages, "debt_heads": heads, "laws": laws,
                "statuses": {s: sum(x["status"] == s for x in laws) for s in sorted({x["status"] for x in laws})}}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon.eval.stage_map")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--protocol", default="spec/M6/lib/i103_run.json")
    ap.add_argument("--out", default="results/M6/i103/stage_map.json")
    ap.add_argument("docs", nargs="+")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    proto = common.load_json(root / a.protocol)
    proto["_path"] = a.protocol
    rows = []
    for d in a.docs:
        print(f"stage map: {d}", flush=True)
        rows.append(run_doc(root, proto, d))
        print("  " + ", ".join(f"{k} {v['status']}" for k, v in rows[-1]["stages"].items()), flush=True)
    out = {"doc": "I103: the corpus protocol's stages over single committed transitions documents "
                  "(python -m holon.eval.stage_map)", "protocol": a.protocol, "rows": rows}
    p = root / a.out
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
