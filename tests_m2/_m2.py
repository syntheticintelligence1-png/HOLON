"""Shared helpers for the M2 acceptance tests.

The cone computation here is deliberately independent of holon/: it reads the generated
model and the generated LAWS.bend files with regular expressions, so a bug in
holon.records cannot make the tests agree with it.
"""
from __future__ import annotations

import fnmatch
import importlib
import json
import re
from pathlib import Path

from tests._util import ROOT, copy_repo, load_json, run_holon  # noqa: F401  (frozen helpers)
from tests.reference import mini_schema

SPEC2 = ROOT / "spec" / "M2"
LEDGER = ROOT / "spec" / "ledger" / "assumptions.json"
SCHEMAS2 = ROOT / "spec" / "schemas"
MILESTONES = ("M0", "M1")


def holon_module(name: str):
    """Import a holon module inside a test, so a missing module fails that test (red), not the file."""
    return importlib.import_module(name)


def predictions(it: str) -> dict:
    return load_json(SPEC2 / "predictions.json")["iterations"][it]


def item(it: str, pid: str) -> dict:
    p = predictions(it)
    return next(x for x in p["predictions"] + p["regressions"] if x["id"] == pid)


def ledger() -> dict:
    return load_json(LEDGER)


def laws(m: str) -> dict[str, dict]:
    return {p.stem: load_json(p) for p in sorted((ROOT / "laws" / m).glob("L_*.json"))}


def records(m: str, root: Path = ROOT) -> dict[str, dict]:
    return {p.stem: load_json(p) for p in sorted((root / "results" / m).glob("L_*.json"))}


def validate(instance, schema_path: Path) -> list[str]:
    return mini_schema.errors(instance, load_json(schema_path))


# ------------------------------------------------------------------ independent cone
_TOP = re.compile(r"^(def|type)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def model_defs(model_file: Path) -> dict[str, str]:
    """Top-level def/type name -> its text (up to the next top-level item)."""
    text = re.sub(r"#[^\n]*", "", model_file.read_text())
    ms = list(_TOP.finditer(text))
    out = {}
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        out[m.group(2)] = text[m.start():end]
    return out


def ctor_owner(defs: dict[str, str]) -> dict[str, str]:
    """Constructor name -> the type that declares it (types whose constructors are named otherwise)."""
    own = {}
    for name, body in defs.items():
        if body.startswith("type "):
            for line in body.splitlines()[1:]:
                m = re.match(r"\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", line)
                if m:
                    own[m.group(1)] = name
    return own


def refs(name: str, defs: dict[str, str], own: dict[str, str]) -> set[str]:
    body = defs[name].split("\n", 1)[1] if "\n" in defs[name] else ""
    head = defs[name].split("\n", 1)[0]
    out = set()
    for tok in _IDENT.findall(head + "\n" + body):
        if tok in defs and tok != name:
            out.add(tok)
        elif tok in own and own[tok] != name:
            out.add(own[tok])
    return out


def cone_from_roots(roots: set[str], defs: dict[str, str]) -> set[str]:
    own = ctor_owner(defs)
    seen, todo = set(), [r for r in roots]
    while todo:
        d = todo.pop()
        if d in seen:
            continue
        seen.add(d)
        todo.extend(refs(d, defs, own) - seen)
    return seen


def law_roots(laws_bend: Path, defs: dict[str, str]) -> set[str]:
    """Model definitions named as M.<x> in a law's LAWS.bend (constructors map to their type)."""
    own = ctor_owner(defs)
    out = set()
    text = re.sub(r"#[^\n]*", "", laws_bend.read_text())
    for tok in re.findall(r"(?<![\w.])M\.([A-Za-z_][A-Za-z0-9_]*)", text):
        if tok in defs:
            out.add(tok)
        elif tok in own:
            out.add(own[tok])
    return out


def bundle_for(rec: dict) -> dict:
    return next(b for b in ledger()["bundles"] if b["facts_sha256"] == rec["facts_sha256"])


def model_file(rec: dict, root: Path = ROOT) -> Path:
    p = Path(rec["artifacts"]["model"])
    return p if p.is_absolute() else root / p


def independent_cone(rec: dict, root: Path = ROOT) -> set[str]:
    defs = model_defs(model_file(rec, root))
    lb = Path(rec["artifacts"]["laws"])
    lb = lb if lb.is_absolute() else root / lb
    return cone_from_roots(law_roots(lb, defs), defs)


def introduces(entry: dict, cone: set[str]) -> bool:
    return any(p == "*" or any(fnmatch.fnmatchcase(d, p) for d in cone) for p in entry["introduced_by"])


def write_json(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
