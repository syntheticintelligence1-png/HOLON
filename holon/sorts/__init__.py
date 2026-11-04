"""Refined semantic sorts I (whitepaper §7.1-§7.4, §7.7 steps 1-4, Thm 6.18 freezing condition; BUILD_PLAN I13).

  python -m holon sorts [--milestone M2] [--root DIR] [--out DIR] [--facts PATH ...]

writes constraints.json, assignment.json, conflicts.json, unions.json and unresolved.json to --out (default
<root>/gen/<milestone>/sorts) from the milestone's fact documents (holon.diagram.fact_documents) or the
documents --facts names. The contract (formats, rules R1-R6) is the docstring of tests_m2/test_sorts_morph.py.

  grammar.py      the §7.1 sort grammar as text, parse/render, the §7.2 affine table, writer labels
  flow.py         value flow, register reads and writer sets read from the facts
  constraints.py  constraints from types, flow, the affine rules, comparisons and lexical seeds
  solve.py        satisfiable(constraints): union-find plus an exact torsor-role search
  core.py         minimal unsatisfiable cores (QuickXplain)
  unions.py       untagged unions (members along flow) and writer-provenance labels (SCCs)
  assign.py       the pass: conflicts, the frozen assignment, sites, unions, unresolved variables

The only target vocabulary is the frozen sidecar spec/M2/lib/sort_seeds.json; nothing here names a target's
variables. Pure Python, standard library only, deterministic output (sorted keys, stable ids, no timestamps).
Exit 0 whenever the solver ran (conflicts are results); 1 when an input is unreadable or holds a construct the
pass cannot map.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon sorts")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--root", help="repository root holding the inputs (default: this checkout)")
    ap.add_argument("--out", help="output directory (default: <root>/gen/<milestone>/sorts)")
    ap.add_argument("--facts", action="append", help="a fact document to read instead of the milestone's (repeatable)")
    ap.add_argument("--sidecar", help="the typed-sorts sidecar (M3+ and T30+: default spec/<M>/lib/sort_types.json)")
    a = ap.parse_args(argv)
    return run(a.milestone, a.root, a.out, a.facts, a.sidecar)


def run_typed(milestone: str, root_p: Path, facts: list[str] | None, sidecar: str | None) -> dict:
    """The pass of an M3+ or T30+ milestone (I30): the sidecar's documents (or --facts), its seeds; every one of
    them, and the sidecar, is an input."""
    from .assign import PassError, run_pass
    from .typed_sidecar import SidecarError, load
    try:
        sc = load(milestone, root_p, sidecar)
    except SidecarError as e:
        raise PassError(str(e)) from e
    if facts:
        docs = []
        for f in facts:
            p = Path(f)
            p = (p if p.is_absolute() else (root_p / p if (root_p / p).exists() else Path.cwd() / p)).resolve()
            try:
                p.relative_to(root_p)
            except ValueError:
                raise PassError(f"--facts {f}: not inside the root {root_p}") from None
            docs.append(p)
    else:
        docs = sc.documents
    return run_pass(docs, root_p, milestone, seeds_path=sc.seeds, sidecar_path=sc.path)


def run(milestone: str, root: str | None, out: str | None, facts: list[str] | None, sidecar: str | None = None) -> int:
    from .assign import DOCUMENTS, PassError, dumps, run_pass
    from .constraints import ConstraintError
    from .flow import FlowError
    from .grammar import SortError
    from .solve import SolveError
    from .typed_sidecar import typed

    root_p = Path(root).resolve() if root else ROOT
    try:
        if typed(milestone):
            texts = {name: dumps(doc) for name, doc in run_typed(milestone, root_p, facts, sidecar).items()}
        else:
            if facts:
                docs = []
                for f in facts:
                    p = Path(f)
                    p = (p if p.is_absolute() else Path.cwd() / p).resolve()
                    try:
                        p.relative_to(root_p)
                    except ValueError:
                        raise PassError(f"--facts {f}: not inside the root {root_p}") from None
                    docs.append(p)
                ms = None
            else:
                from ..diagram import DiagramError, fact_documents
                try:
                    docs = fact_documents(milestone, root_p)
                except DiagramError as e:
                    raise PassError(str(e)) from e
                ms = milestone
            texts = {name: dumps(doc) for name, doc in run_pass(docs, root_p, ms).items()}
    except (PassError, FlowError, ConstraintError, SortError, SolveError, OSError, json.JSONDecodeError) as e:
        print(f"holon sorts: {e}", file=sys.stderr)
        return 1
    out_p = Path(out) if out else root_p / "gen" / milestone / "sorts"
    out_p.mkdir(parents=True, exist_ok=True)
    for name in DOCUMENTS:
        (out_p / f"{name}.json").write_text(texts[name], encoding="utf-8")
    c = json.loads(texts["conflicts"])["conflicts"]
    u = json.loads(texts["unresolved"])["count"]
    print(f"holon sorts: {len(c)} conflicts, {u} unresolved variables -> {out_p}")
    return 0
