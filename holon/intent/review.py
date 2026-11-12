"""Review requests (key I55 design V): what the one fresh reviewer sees, per law.

  python -m holon intent requests [--root DIR] [--check]

writes results/M5/intent/review_requests.json: {"prompt": spec/M5/lib/intent_review_prompt.md's sha256, "requests":
[{law_id, clause, documents, reading, statement}]}. A request holds the clause verbatim (the atom's text), the
declaration line it documents, the law's generated plain reading and its LAWS.bend text; never a control's id, its
truth or the code's body. The reviewer's answer is recorded verbatim in spec/M5/intent/reviews.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .common import LAWS, OUT, ROOT, dumps, sha256_file
from .ir import law_text

PROMPT = "spec/M5/lib/intent_review_prompt.md"


def document(root: Path) -> dict:
    atoms = json.loads((root / OUT / "atoms.json").read_text(encoding="utf-8"))
    by = {a["id"]: a for a in atoms["atoms"] + atoms["controls"]}
    reqs = []
    for p in sorted((root / LAWS).glob("L_intent_*.json")):
        lw = json.loads(p.read_text(encoding="utf-8"))
        a = by[lw["clauses"][0]]
        reqs.append({"law_id": lw["law_id"], "clause": a["text"], "documents": a["decl"]["text"] if a["decl"] else "",
                     "reading": lw["reading"], "statement": law_text(lw)})
    return {"prompt_sha256": sha256_file(root / PROMPT), "requests": reqs}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="holon intent requests")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = a.root.resolve()
    out = root / OUT / "review_requests.json"
    text = dumps(document(root))
    if a.check:
        ok = out.is_file() and out.read_text(encoding="utf-8") == text
        print(f"intent requests: {'CHECK OK' if ok else 'CHECK FAILED'}")
        return 0 if ok else 1
    out.write_text(text, encoding="utf-8")
    print(f"intent requests: wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
