"""The Solidity frontend (whitepaper §10.1, §10.2; BUILD_PLAN I17): codec layouts from the compiler's AST and the Yul of
its inline assembly, written as holon-facts/0.3 (spec/schemas/facts_0_3.schema.json).

  python -m holon extract solidity [--milestone M2] [--sidecar PATH] [--root DIR] [--source DIR] [--out PATH] [--check]

  --sidecar  default <root>/spec/<milestone>/lib/extract_solidity.json (its "frontend" must be "solidity")
  --root     the HOLON checkout (default: this one): config/holon.json, the default sidecar and output live there
  --source   the target source tree (default: config/holon.json extract.sources[<sidecar target.repo>])
  --out      default <root>/<sidecar output>; --check writes nothing and exits 0 iff --out holds exactly the bytes
             of a fresh extraction, 1 otherwise
  exit 0 written; 1 (--check) differs or missing; 2 refused, nothing written; 3 extraction error, nothing written

Modules: compile (toolchain checks and the solc run, W1), ast (index, spans, terms, the symbolic walker over Solidity
statements and Yul, W2-W10), layout_extract (edges, naming, projection, merging, debt and the document). The contract
is the docstring of tests_m2/test_extract_solidity_layout.py. The frontend reads the sidecar, config/holon.json, the
compiler's output and the source tree; never a fact document, a law or a result, and no analysis tool.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

from .. import ROOT, ExtractionError, Refused, load_sidecar, render

FRONTEND = "solidity"
_SPAN = re.compile(r"^[^\s:]+:[1-9][0-9]*(-[1-9][0-9]*)?$")


def _check_sidecar(side: dict, path) -> None:
    """The Solidity keys of a sidecar: sources, compiler {version, settings}, edges; Refused when malformed."""
    bad = []
    if side.get("frontend") != FRONTEND:
        bad.append(f"frontend is {side.get('frontend')!r}, not {FRONTEND!r}")
    src = side.get("sources")
    if not isinstance(src, list) or not src or not all(isinstance(u, str) and u and not u.startswith("/")
                                                       and ".." not in u.split("/") for u in src):
        bad.append("sources is not a list of relative source unit names")
    comp = side.get("compiler")
    if not isinstance(comp, dict) or not isinstance(comp.get("version"), str) \
            or not isinstance(comp.get("settings", {}), dict):
        bad.append("compiler is not {version, settings}")
    edges = side.get("edges")
    if not isinstance(edges, dict) or not edges:
        bad.append("edges is not a non-empty object")
    else:
        for name, e in sorted(edges.items()):
            if not isinstance(e, dict) or e.get("kind") not in ("encoder", "loader"):
                bad.append(f"edge {name}: kind is neither encoder nor loader")
                continue
            if not isinstance(e.get("from"), str) or not e["from"]:
                bad.append(f"edge {name}: from is not a type name")
            if e["kind"] == "loader" and not (isinstance(e.get("input"), str) and e["input"]):
                bad.append(f"edge {name}: a loader names its input parameter")
            ent = e.get("entry")
            if not isinstance(ent, dict) or not all(isinstance(ent.get(k), str) and ent[k] for k in ("contract",
                                                                                                   "function")):
                bad.append(f"edge {name}: entry is not {{contract, function}}")
            sink = e.get("sink")
            if not isinstance(sink, list) or not sink or not all(isinstance(s, str) and _SPAN.match(s) for s in sink):
                bad.append(f"edge {name}: sink is not a non-empty list of spans")
    if bad:
        raise Refused(f"sidecar {path}: malformed: " + "; ".join(bad))


def _relative(p: Path, root: Path) -> str:
    try:
        return Path(os.path.realpath(p)).relative_to(os.path.realpath(root)).as_posix()
    except ValueError:
        return f"<outside>/{p.name}"


def extract_document(side: dict, sidecar_path: Path, root: Path, source=None) -> dict:
    """The holon-facts/0.3 document of a Solidity sidecar (Refused: exit 2; ExtractionError: exit 3)."""
    from . import compile as comp
    from .layout_extract import build
    _check_sidecar(side, sidecar_path)
    root = Path(root)
    cfg = comp.load_config(root)
    if source is None:
        source = ((cfg.get("extract") or {}).get("sources") or {}).get(side["target"]["repo"])
        if not source:
            raise Refused(f"no source tree: config/holon.json extract.sources has no {side['target']['repo']!r} "
                          "(pass --source)")
    compiled = comp.compile_sources(cfg, side, Path(os.path.abspath(source)))
    sha = hashlib.sha256(Path(sidecar_path).read_bytes()).hexdigest()
    doc = build(compiled, side, _relative(Path(sidecar_path), root), sha)
    _validate(doc, root)
    return doc


def _validate(doc: dict, root: Path) -> None:
    """The document validates against spec/schemas/facts_0_3.schema.json (when the root holds it)."""
    import json
    from ...schema import errors
    p = Path(root) / "spec" / "schemas" / "facts_0_3.schema.json"
    if not p.exists():
        return
    errs = errors(doc, json.loads(p.read_text(encoding="utf-8")))
    if errs:
        raise ExtractionError("the document does not validate against spec/schemas/facts_0_3.schema.json: "
                              + "; ".join(errs[:5]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon extract solidity",
                                 description="Solidity codec layouts from the compiler's AST and Yul (holon-facts/0.3)")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--sidecar")
    ap.add_argument("--root")
    ap.add_argument("--source")
    ap.add_argument("--out")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    sidecar = Path(a.sidecar) if a.sidecar else root / "spec" / a.milestone / "lib" / f"extract_{FRONTEND}.json"
    try:
        side = load_sidecar(sidecar)
        if side.get("frontend") != FRONTEND:
            raise Refused(f"sidecar {sidecar}: frontend {side.get('frontend')!r} is not {FRONTEND!r}")
        doc = extract_document(side, sidecar, root, a.source)
    except Refused as e:
        print(f"holon extract {FRONTEND}: refused: {e}", file=sys.stderr)
        return 2
    except ExtractionError as e:
        print(f"holon extract {FRONTEND}: extraction error: {e}", file=sys.stderr)
        return 3
    data = render(doc)
    out = Path(a.out) if a.out else root / side["output"]
    if a.check:
        same = out.is_file() and out.read_bytes() == data
        print(f"holon extract {FRONTEND}: {out} {'is up to date' if same else 'differs from a fresh extraction'}")
        return 0 if same else 1
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, out)
    print(f"holon extract {FRONTEND}: wrote {out}")
    return 0
