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

Window views (I66, rules V2 and V4 of tests_m3/test_view_evidence.py). It also writes one diagram per window view of
the milestone (window_views: a holon-facts/0.2 document directly under gen/<M>/extracted/, holon.differential's output,
whose window declaration is one of spec/<M>/lib/window_*.json), named by the view file's stem and built by the same
adapters, its libraries anchored to its abstraction's (holon.gen.targetlib.anchor). A window view is never a fact
document; one whose stem is a fact document's is a DiagramError and nothing is written.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .build import ROOT, build
from .model import DiagramError, dumps

__all__ = ["build", "fact_documents", "window_views", "main", "DiagramError"]


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


def window_views(milestone: str, root: Path | str = ROOT) -> list[Path]:
    """The milestone's window views, sorted: every holon-facts/0.2 document directly under gen/<M>/extracted/
    (holon.differential's output) whose window declaration (holon.gen.targetlib.window_declaration) is one of the
    milestone's, spec/<M>/lib/window_*.json. Never a fact document (fact_documents)."""
    from ..gen.targetlib import window_declaration
    root = Path(root).resolve()
    decls = {p.relative_to(root).as_posix() for p in sorted((root / "spec" / milestone / "lib").glob("window_*.json"))}
    out = []
    for p in sorted((root / "gen" / milestone / "extracted").glob("*.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        if not isinstance(doc, dict) or doc.get("facts_version") != "holon-facts/0.2":
            continue
        w = window_declaration(p, root)
        if w is not None and w[0] in decls:
            out.append(p)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon diagram")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--out", help="output directory (default: <root>/gen/<milestone>/diagram)")
    ap.add_argument("--root", help="repository root holding the fact documents (default: this checkout)")
    a = ap.parse_args(argv)
    return run(a.milestone, a.out, a.root)


def linked_diagrams(milestone: str, root: Path) -> dict[str, str]:
    """From M3 on (I24, rule X6): {model: diagram text} of every linked codec document gen/<M>/codec/<role>.json."""
    import hashlib
    import json

    from . import linked as L
    out = {}
    for p in L.committed_codecs(milestone, root):
        raw = p.read_bytes()
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise DiagramError(f"{p}: not JSON ({e})") from e
        if not L.is_linked(doc):
            raise DiagramError(f"{p}: not a linked codec document ({L.LINKED_VERSION})")
        rel = p.resolve().relative_to(Path(root).resolve()).as_posix()
        try:
            dg = L.diagram(doc, rel, hashlib.sha256(raw).hexdigest())
        except (L.LinkedError, KeyError, TypeError) as e:
            raise DiagramError(f"{rel}: {e}") from e
        dg["provenance"] = {}
        dg["inputs"] = []
        out[doc["component"]] = dumps(dg)
    if not out:
        raise DiagramError(f"no linked codec documents under gen/{milestone}/codec (run `holon codecs --milestone "
                           f"{milestone}`)")
    return out


def run(milestone: str, out: str | None, root: str | None) -> int:
    root_p = Path(root).resolve() if root else ROOT
    try:
        from .linked import linked_milestone
        if linked_milestone(milestone):   # M3 on: the component diagrams of the linked codec layer (I24)
            texts = linked_diagrams(milestone, root_p)
        else:
            docs = fact_documents(milestone, root_p)
            views = window_views(milestone, root_p)   # I66: one diagram per window view too
            clash = sorted({p.stem for p in views} & {p.stem for p in docs})
            if clash:
                raise DiagramError(f"a window view has a fact document's model name: {clash}")
            texts = {p.stem: dumps(build(p, root_p).to_json()) for p in [*docs, *views]}
    except DiagramError as e:
        print(f"holon diagram: {e}", file=sys.stderr)
        return 1
    out_p = Path(out) if out else root_p / "gen" / milestone / "diagram"
    out_p.mkdir(parents=True, exist_ok=True)
    for model, text in sorted(texts.items()):
        (out_p / f"{model}.json").write_text(text, encoding="utf-8")
        print(f"{model}: {out_p / (model + '.json')}")
    return 0
