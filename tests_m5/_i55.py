"""I55's instrument (pinned by sha256 in tests_m5/test_m5_intent.py PINNED; frozen at the I55 prereg).

It checks the intent lane's outputs without sharing code with holon/intent:
  * closure(): the static import closure of a holon module (absolute, relative and function-level imports), for the
    lead's condition G2(a): the atomizer's closure holds no holon.m5 module and no file that names the census;
  * span_problems(): an atom's pieces are exact substrings of its source lines and rebuild its text;
  * l10_inputs(): the L10 inputs document assembled from the lane's records alone (key design L1);
  * trivially_true(): the share of covering laws that are trivially true (key design TT, the lead's condition G2(b));
  * route_i(): SYM route (i) recomputed from the M3 splits and the lane's records (key design Y).
Nothing here imports holon/. I54's instrument (tests_m5/_i54.py) supplies the proportion, the labels, l10 and the
census rule.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from tests_m5 import _i54 as I54
from tests_m5._m5 import ROOT, load_json

SCOPE_COMMIT = "4fd64a52f030438cac06595f8673840d6c5c6525"   # I54's base: the facts documents the census scope read
CENSUS = "results/M5/l10_census_base.json"
CONTROLS = "spec/M5/controls/intent"
OUT = "results/M5/intent"
COMPILER = "holon.intent.compile"
FORBIDDEN_IN_CLOSURE = ("l10_census", "holon.m5", "m5.census", "m5 import census")


# ------------------------------------------------------------------ G2(a): the atomizer's static closure
def _module_file(mod: str) -> Path | None:
    parts = mod.split(".")
    if parts[0] != "holon":
        return None
    base = ROOT.joinpath(*parts)
    if (base / "__init__.py").is_file():
        return base / "__init__.py"
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py")
    return None


def _imports(path: Path, mod: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    pkg = mod if path.name == "__init__.py" else mod.rsplit(".", 1)[0]
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                anchor = pkg.split(".")
                anchor = anchor[:len(anchor) - (node.level - 1)]
                base = ".".join(anchor + ([node.module] if node.module else []))
            else:
                base = node.module or ""
            out.add(base)
            out.update(f"{base}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")) in (
                "import_module", "__import__") and node.args and isinstance(node.args[0], ast.Constant):
            out.add(str(node.args[0].value))
    return {m for m in out if m == "holon" or m.startswith("holon.")}


def closure(module: str) -> dict[str, Path]:
    """{module: file} of every holon module reachable from `module` by imports (packages' __init__ included)."""
    seen: dict[str, Path] = {}
    todo = [module]
    while todo:
        m = todo.pop()
        if m in seen:
            continue
        f = _module_file(m)
        if f is None:
            continue
        seen[m] = f
        parts = m.split(".")
        todo.extend(".".join(parts[:i]) for i in range(1, len(parts)))
        todo.extend(sorted(_imports(f, m)))
    return dict(sorted(seen.items()))


def closure_problems(module: str) -> list[str]:
    out = []
    cl = closure(module)
    if module not in cl:
        out.append(f"{module} is not a module of holon/")
    for m, f in cl.items():
        if m == "holon.m5" or m.startswith("holon.m5."):
            out.append(f"{module} reaches {m}")
        text = f.read_text(encoding="utf-8")
        for w in FORBIDDEN_IN_CLOSURE:
            if w in text:
                out.append(f"{f.relative_to(ROOT).as_posix()} names {w!r}")
    return out


# ------------------------------------------------------------------ exact spans
def span_problems(atom: dict, lines: list[str]) -> list[str]:
    """lines: the source file's lines (1-based through lines[n - 1]), decoded as UTF-8, without line ends."""
    out, parts = [], []
    for ln, a, b in atom["pieces"]:
        if not (1 <= ln <= len(lines)) or not (0 <= a <= b <= len(lines[ln - 1])):
            out.append(f"piece {[ln, a, b]} outside the file")
            continue
        parts.append(lines[ln - 1][a:b])
    joined = re.sub(r"\s+", " ", " ".join(parts)).strip()
    if joined != atom["text"]:
        out.append(f"pieces give {joined!r}, the atom says {atom['text']!r}")
    ls = [p[0] for p in atom["pieces"]]
    if ls and atom["lines"] != [min(ls), max(ls)]:
        out.append(f"lines {atom['lines']} are not the pieces' {[min(ls), max(ls)]}")
    if atom["decl"] is not None:
        d = atom["decl"]
        if not (1 <= d["line"] <= len(lines)) or lines[d["line"] - 1].strip() != d["text"]:
            out.append(f"decl line {d['line']} is not {d['text']!r}")
    return out


# ------------------------------------------------------------------ L10 inputs (key design L1)
def project_atom(a: dict) -> dict:
    return {"id": a["id"], "file": a["file"], "lines": list(a["lines"]), "text": a["text"]}


def project_record(r: dict) -> dict:
    return {"law": r["law_id"], "clauses": list(r["clauses"]), "status": r["status"], "evidence": dict(r["evidence"]),
            "review": dict(r["review"]), "control": r["control"]}


def records(root: Path = ROOT) -> list[dict]:
    d = root / OUT / "records"
    return [load_json(p) for p in sorted(d.glob("L_intent_*.json"))] if d.is_dir() else []


def control_documents(root: Path = ROOT) -> list[dict]:
    return [load_json(p) for p in sorted((root / CONTROLS).glob("i_*.json"))]


def l10_inputs(root: Path = ROOT) -> dict:
    atoms = load_json(root / OUT / "atoms.json")
    return {"census": load_json(root / CENSUS)["clauses"],
            "atomized": [project_atom(a) for a in atoms["atoms"]],
            "laws": [project_record(r) for r in records(root)],
            "controls": control_documents(root)}


def _w1(r):
    return r["status"] in ("PROVED", "REFUTED") and r["evidence"]["marker"] == I54.CHECKED and r["evidence"]["law_present"]


def _w2(r):
    return r["review"]["verdict"] == "faithful" and r["review"]["reviewer"] != r["review"]["compiler"]


def trivially_true(root: Path = ROOT) -> dict:
    """TT: over the laws that pass W1-W3 and cover a census clause (the laws that make coverage), the share that are
    PROVED and trivially true; and the same share over the control laws that pass W1 and W2."""
    inp = l10_inputs(root)
    atoms = {a["id"]: a for a in inp["atomized"]}
    recs = records(root)
    counts = {}
    for r in recs:
        counts[r["law_id"]] = counts.get(r["law_id"], 0) + 1
    cover = [r for r in recs if counts[r["law_id"]] == 1 and _w1(r) and _w2(r) and r["clauses"]
             and all(c in atoms for c in r["clauses"])
             and any(I54._meets(atoms[c], k) for c in r["clauses"] for k in inp["census"])]
    ctl = [r for r in recs if counts[r["law_id"]] == 1 and r["control"] is not None and _w1(r) and _w2(r)]
    tt = lambda r: r["status"] == "PROVED" and r["trivial"]["trivially_true"] is True  # noqa: E731
    return {"covering": I54.prop(sum(map(tt, cover)), len(cover)),
            "controls": I54.prop(sum(map(tt, ctl)), len(ctl))}


# ------------------------------------------------------------------ SYM route (i) (key design Y)
def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def route_i(root: Path = ROOT) -> dict:
    laws = {p.stem: load_json(p) for p in sorted((root / "laws" / "INTENT").glob("L_intent_*.json"))}
    recs = {r["law_id"]: r for r in records(root)}
    atoms = {a["id"] for a in load_json(root / OUT / "atoms.json")["atoms"]}
    out = []
    for fam in ("pi", "tau"):
        doc = load_json(root / "results" / "M3" / "sym" / f"{fam}.json")
        for sp in doc["splits"]:
            acts = set(sp["eq"]) | set(sp["break"]) | set(sp["unknown"])
            marks = sorted(lid for lid, lw in laws.items() if fam == "pi" and lw["template"] == "access"
                           and _norm(lw["binding"]["name"]) == _norm(sp["role"]) and set(lw["actions"]) & acts
                           and lid in recs and recs[lid]["status"] == "PROVED" and _w1(recs[lid]) and _w2(recs[lid])
                           and all(c in atoms for c in lw["clauses"]))
            if not sp["break"]:
                reason, promoted = "no breaking action: nothing to promote", False
            elif fam != "pi":
                reason, promoted = f"no intent template marks the {fam} family", False
            elif not marks:
                reason, promoted = f"no reviewed PROVED access law names the role {sp['role']}", False
            else:
                reason, promoted = "route (i): a reviewed PROVED intent law marks the family as intended", True
            out.append({"document": doc["document"], "family": fam, "role": sp["role"], "break": sorted(sp["break"]),
                        "promoted": promoted, "reason": reason, "laws": marks})
    return {"route_version": "holon-intent-route-i/0.1", "splits": out}


# ------------------------------------------------------------------ the statement language (key design S)
TERM_KEYS = {"var", "w", "u32", "bool", "fn", "m", "act", "get", "nat"}


def term_problems(t, binders: set[str], path: str = "holds") -> list[str]:
    if not isinstance(t, dict) or len(set(t) & TERM_KEYS) != 1:
        return [f"{path}: not a term"]
    k = next(iter(set(t) & TERM_KEYS))
    if k == "var":
        return [] if t["var"] in binders else [f"{path}: unbound {t['var']}"]
    if k in ("w", "u32", "nat"):
        return [] if isinstance(t[k], int) and t[k] >= 0 and set(t) == {k} else [f"{path}: bad literal"]
    if k == "bool":
        return [] if isinstance(t["bool"], bool) and set(t) == {"bool"} else [f"{path}: bad bool"]
    if set(t) != {k, "args"} or not isinstance(t["args"], list) or not isinstance(t[k], str):
        return [f"{path}: an application is {{{k}, args}}"]
    out = []
    for i, a in enumerate(t["args"]):
        out += term_problems(a, binders, f"{path}.{t[k]}[{i}]")
    return out
