"""Shared helpers for the I13 sorts tests (tests_m2/test_sorts_*.py).

The contract these helpers read is stated in full in the docstring of tests_m2/test_sorts_morph.py.
Nothing here imports holon/: the CLI is run as a subprocess and its JSON files are read back, and the
sha256 of the frozen assignment is recomputed here, independently of holon.ir.canonical_json.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from tests_m2._m2 import ROOT, load_json, run_holon

FILES = ("constraints", "assignment", "conflicts", "unions", "unresolved")
OUT = ROOT / "gen" / "M2" / "sorts"
SCHEMA = ROOT / "spec" / "schemas" / "sorts.schema.json"
SORTS_VERSION = "holon-sorts/0.1"
UNREFINED = "Nat (unrefined)"
SIGNED = ("SDur", "SIdx[", "SCnt[")


class Run:
    """One `python -m holon sorts ... --out DIR` invocation and the files it wrote."""

    def __init__(self, args: list[str], cwd: Path = ROOT, out: Path | None = None):
        self.tmp = None
        if out is None:
            self.tmp = Path(tempfile.mkdtemp(prefix="holon-sorts-"))
            out = self.tmp / "out"
        self.out = Path(out)
        p = run_holon(["sorts", *args, "--out", str(self.out)], cwd=cwd)
        self.code = p.returncode
        self.log = f"exit {p.returncode}\n--- stdout\n{p.stdout[-3000:]}\n--- stderr\n{p.stderr[-3000:]}"
        self.docs = {n: load_json(self.out / f"{n}.json") for n in FILES if (self.out / f"{n}.json").exists()}

    def doc(self, name: str) -> dict:
        if name not in self.docs:
            raise AssertionError(f"holon sorts wrote no {name}.json\n{self.log}")
        return self.docs[name]

    def model(self, m: str) -> dict:
        models = self.doc("assignment").get("models", {})
        if m not in models:
            raise AssertionError(f"assignment.json has no model {m!r} (models: {sorted(models)})")
        return models[m]

    def assignment(self, m: str) -> dict:
        return self.model(m)["assignment"]

    def sites(self, m: str) -> list[dict]:
        return [s for s in self.doc("assignment")["sites"] if s["model"] == m]

    def cleanup(self) -> None:
        if self.tmp is not None:
            shutil.rmtree(self.tmp, ignore_errors=True)


def canonical_sha256(obj) -> str:
    """sha256 of the canonical JSON text: sorted keys, separators (",", ":"), UTF-8, no ASCII escaping."""
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def members(sort: str) -> set[str]:
    """The members of a union sort string ("A + B" -> {"A", "B"}); a non-union sort is its own member."""
    return {x.strip() for x in sort.split(" + ")}


def is_signed(sort: str) -> bool:
    return sort.startswith(SIGNED)


def without(doc: dict, *keys: str) -> dict:
    return {k: v for k, v in doc.items() if k not in keys}


def scalar(ty: str) -> bool:
    """A facts type that is a sort variable: Nat, Bool, or a list of them (the variable is the element)."""
    inner = ty[5:-1] if ty.startswith("List<") and ty.endswith(">") else ty
    return inner in ("Nat", "Bool")


def required_keys(facts: dict) -> dict[str, str]:
    """The variable keys a holon-facts/0.2 document must have in assignment.json, with their facts types:
    state fields "<f>" (scalar or list of scalar), record fields "<Type>.<g>", action inputs "<a>.<x>"."""
    out: dict[str, str] = {}
    for f, ty, *_ in facts["state"]:
        if scalar(ty):
            out[f] = ty
    for tname, t in facts.get("types", {}).items():
        for g, ty in t.get("fields", []):
            if scalar(ty):
                out[f"{tname}.{g}"] = ty
    for a in facts["actions"]:
        for x, ty in a.get("inputs", []):
            if scalar(ty):
                out[f"{a['name']}.{x}"] = ty
    return out


def subtractions(e) -> list:
    """Every binary "-" node of a DSL expression, outermost first."""
    out = []
    if isinstance(e, list) and e:
        if e[0] == "-" and len(e) == 3:
            out.append(e)
        if e[0] == "call":
            kids = e[2:]
        elif e[0] == "get":
            kids = [e[1]]
        elif e[0] == "mk":
            kids = list(e[2].values())
        elif e[0] == "with":
            kids = [e[2], *e[3].values()]
        elif e[0] == "list":
            kids = e[2:]
        else:
            kids = e[1:]
        for k in kids:
            out.extend(subtractions(k))
    return out


def action_subtractions(facts: dict) -> list[tuple[str, list]]:
    """(action, "-" expression) for every subtraction in the guards (require, let) and effects of every action."""
    out = []
    for a in facts["actions"]:
        exprs = [g[k] for g in a.get("guards", []) for k in ("require", "expr") if k in g]
        exprs += list(a.get("effects", {}).values())
        for e in exprs:
            out.extend((a["name"], s) for s in subtractions(e))
    return out
