"""Coverage accounting (whitepaper §9.3 G8, L1 coverage; BUILD_PLAN I19; contract: the docstring of
tests_m2/test_coverage.py).

    python -m holon coverage --milestone M2 [--root DIR] [--out PATH] [--check]

writes <root>/gen/<M>/coverage.json (canonical JSON: indent 2, sorted keys, newline):

  {"documents": [{"document": "<extracted document>", "statements": n, "extracted": n,
                  "debt": [{"src", "kind", "detail"}], "unaccounted": [{"src", "node"}]}],
   "unaccounted": n}

One entry per extraction sidecar of the milestone whose frontend accounts for statements (holon.frontends.<frontend>
.coverage_document; for Solidity: a sidecar with "transitions", holon.frontends.solidity.transitions), sorted by
document; "unaccounted" is the total number of unaccounted statements. The classification (extracted, debt kinds
external_call, loop_storage_write, value_transfer and unsupported, unaccounted) is the frontend's walk, re-run here
from the compiler's output: the report never reads the extracted document it describes. A layout sidecar (I17) is
not listed: its debt is in its own document (walk.debt), and the Go documents carry theirs (go.coverage).

--check writes nothing and exits 0 iff --out (default the committed report) holds exactly the bytes of a fresh run.
Exit 0 written (or up to date), 1 (--check) differs or missing, 2 refused, 3 extraction error.

Gate check G8 (holon.gate, M2+ milestones that have such a sidecar or a committed report): the report exists, a fresh
run reproduces it byte for byte, and unaccounted is empty for every document.

Records (holon.records.coverage_field): an M2+ law whose facts document is one of the report's documents carries
{"document", "debt": len(debt), "unaccounted": len(unaccounted)}; every other law carries null.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def report_path(m: str, root=ROOT) -> Path:
    return Path(root) / "gen" / m / "coverage.json"


def accounting_sidecars(m: str, root=ROOT) -> list[tuple[Path, dict, object]]:
    """(path, sidecar, frontend module) of every extraction sidecar of m whose frontend accounts for statements."""
    from . import frontends
    out = []
    for sp in frontends.sidecars(m, root):
        side = frontends.load_sidecar(sp)
        mod = frontends._frontend(side["frontend"])
        if mod is not None and callable(getattr(mod, "coverage_document", None)) and "transitions" in side:
            out.append((sp, side, mod))
    return out


def compute(m: str, root=ROOT) -> dict:
    """The coverage report of milestone m (module docstring)."""
    root = Path(root)
    docs = []
    for sp, side, mod in accounting_sidecars(m, root):
        cov = mod.coverage_document(side, sp, root, None)
        if cov is not None:
            docs.append(dict(cov, document=side["output"]))
    docs.sort(key=lambda d: d["document"])
    return {"documents": docs, "unaccounted": sum(len(d["unaccounted"]) for d in docs)}


def render(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode()


def main(argv=None) -> int:
    from .frontends import ExtractionError, Refused
    ap = argparse.ArgumentParser(prog="holon coverage", description="statement coverage of the extracted documents")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--root")
    ap.add_argument("--out")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    out = Path(a.out) if a.out else report_path(a.milestone, root)
    try:
        data = render(compute(a.milestone, root))
    except Refused as e:
        print(f"holon coverage: refused: {e}", file=sys.stderr)
        return 2
    except ExtractionError as e:
        print(f"holon coverage: extraction error: {e}", file=sys.stderr)
        return 3
    doc = json.loads(data)
    if a.check:
        same = out.is_file() and out.read_bytes() == data
        print(f"holon coverage: {out} {'is up to date' if same else 'differs from a fresh run'}")
        return 0 if same else 1
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, out)
    for d in doc["documents"]:
        print(f"holon coverage: {d['document']}: {d['statements']} statements, {d['extracted']} extracted, "
              f"{len(d['debt'])} debt entries, {len(d['unaccounted'])} unaccounted")
    print(f"holon coverage: wrote {out}")
    return 0
