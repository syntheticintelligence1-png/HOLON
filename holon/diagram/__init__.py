"""The protocol diagram 𝔇 (whitepaper §4, Defs 4.1-4.4 and 4.7; §8.3; BUILD_PLAN I11).

One deterministic diagram per fact document, built by adapters with one mapping per facts section
(holon.diagram.build) and zero unmapped constructs:

  model.py       Carrier, Edge, Diagram (to_json)
  build.py       adapters for holon-facts/0.1 and holon-facts/0.2
  access.py      index-sensitive read/write sets of facts expressions
  principals.py  principal classes: caller type plus a permission predicate from the guards

  python -m holon diagram --milestone M2 [--out DIR] [--root DIR]

writes <out or gen/<M>/diagram>/<model>.json for every fact document of the milestone: facts/*.json
and spec/M<j>/facts/*.json for j <= the milestone, except extracted documents (*.extracted.json, holon extract:
compared with the frozen facts, not fact documents yet). Diagrams start at M2: gen/M0 and gen/M1 are
pinned byte for byte (I6), so no diagram is written under them.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .build import ROOT, build
from .model import DiagramError, dumps

__all__ = ["build", "fact_documents", "main", "DiagramError"]


def fact_documents(milestone: str, root: Path | str = ROOT) -> list[Path]:
    root = Path(root)
    m = re.fullmatch(r"M(\d+)", milestone)
    if not m:
        raise DiagramError(f"milestone {milestone!r} is not M<k>")
    k = int(m.group(1))
    if k < 2:
        raise DiagramError("diagrams start at M2 (gen/M0 and gen/M1 are pinned byte for byte)")
    docs = sorted((root / "facts").glob("*.json"))
    for j in range(1, k + 1):
        docs += sorted((root / "spec" / f"M{j}" / "facts").glob("*.json"))
    # An extracted document (holon extract, holon-facts/0.3: *.extracted.json, I17/I18) is compared with the frozen
    # facts, not used as one: it becomes a fact document only when a later iteration adopts it (I20).
    docs = [p for p in docs if not p.name.endswith(".extracted.json")]
    stems = [p.stem for p in docs]
    dup = sorted({s for s in stems if stems.count(s) > 1})
    if dup:
        raise DiagramError(f"two fact documents would write the same diagram: {dup}")
    if not docs:
        raise DiagramError(f"no fact documents for {milestone} under {root}")
    return docs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon diagram")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--out", help="output directory (default: <root>/gen/<milestone>/diagram)")
    ap.add_argument("--root", help="repository root holding the fact documents (default: this checkout)")
    a = ap.parse_args(argv)
    return run(a.milestone, a.out, a.root)


def run(milestone: str, out: str | None, root: str | None) -> int:
    root_p = Path(root).resolve() if root else ROOT
    try:
        docs = fact_documents(milestone, root_p)
        texts = {p.stem: dumps(build(p, root_p).to_json()) for p in docs}
    except DiagramError as e:
        print(f"holon diagram: {e}", file=sys.stderr)
        return 1
    out_p = Path(out) if out else root_p / "gen" / milestone / "diagram"
    out_p.mkdir(parents=True, exist_ok=True)
    for model, text in sorted(texts.items()):
        (out_p / f"{model}.json").write_text(text, encoding="utf-8")
        print(f"{model}: {out_p / (model + '.json')}")
    return 0
