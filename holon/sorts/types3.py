"""`holon types`: the nominal types and the ghost-taint check of a typed milestone's models (I30; the contract is the
docstring of tests_m3/test_sort_types.py, rules N1, N2, G1 and G4 and the CLI section).

  python -m holon types --milestone M [--root DIR] [--sidecar PATH] [--facts PATH ..] [--model PATH] [--out DIR]

writes <out, default gen/<M>/sorts>/types.json and taint.json (canonical JSON, no timestamp, no absolute path; two runs
byte-identical). Typing reads the frozen assignment (gen/<M>/sorts/assignment.json, written by `holon sorts` only) and
never writes it (Thm 6.18). Exit 0; exit 2, nothing written, on an ill-sorted operation (N2: an operation the §7.2
table has no row for, named by its action, operator and span) or a taint violation (G4); exit 1 on an unreadable
input.

types.json {"document": "types", "milestone", "sorts_sha256", "inputs", "models": {model: {"types": {sort: Bend type},
            "ops": [{"name", "op", "args", "result"}], "coercions": [{"name", "kind", "from", "to"}],
            "ghosts": {register: companion}, "external_guards": [{"action", "guard", "src", "calls"}]}}}
taint.json {"document": "taint", "milestone", "inputs", "models": {model: {"model_file", "model_sha256",
            "hand_written": {"state": [], "fields": [], "defs": []}, "generated": [companion], "violations":
            [{"definition", "reaches", "span"}]}}}

The taint check (G4) is over names, definition by definition, on the typed model as `holon model` writes it (or the file
--model names; it need not type-check): no definition above GHOST_MARKER names a definition below it or a companion.
An extracted document carries no hand-written ghost, so the hand_written lists are those of the document's own ghost
declarations (none in holon-facts/0.3).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from . import extracted as X
from .model3 import GHOST_MARKER, GenError, documents_of, generate, init_of, model_name

TYPES_VERSION = "holon-types/0.1"
_DEF = re.compile(r"(?m)^def\s+([\w.]+)\s*\(")


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def blocks(text: str) -> list[tuple[str, str, str]]:
    """(name, body, comment above it) of every definition of a Bend text, in order."""
    out = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        m = re.match(r"^def\s+([\w.]+)\s*\(", lines[i])
        if not m:
            i += 1
            continue
        j = i - 1
        cm = ""
        while j >= 0 and lines[j].startswith("#"):
            cm = lines[j][1:].strip() + (" " + cm if cm else "")
            j -= 1
        k = i + 1
        while k < len(lines) and (lines[k].startswith((" ", "\t")) or not lines[k].strip()):
            k += 1
        out.append((m.group(1), "\n".join(lines[i:k]), cm))
        i = k
    return out


def names_in(name: str, text: str) -> bool:
    return re.search(rf"(?<![\w.]){re.escape(name)}(?![\w])", re.sub(r"#[^\n]*", "", text)) is not None


def taint(text: str, companions: list[str]) -> list[dict]:
    """G4 over names: every definition above the ghost marker that names a definition below it or a companion."""
    if text.count(GHOST_MARKER) != 1:
        raise GenError(f"the typed model holds the ghost marker {text.count(GHOST_MARKER)} times, not once")
    head, ghost = text.split(GHOST_MARKER)
    ghosts = sorted(set(_DEF.findall(ghost)) | set(companions))
    out = []
    for name, body, cm in blocks(head):
        sig, _, rest = body.partition("\n")
        for g in ghosts:
            if names_in(g, body):
                span = re.search(r"\S+\.\w+:\d+(?:-\d+)?", cm)
                out.append({"definition": name, "reaches": g, "span": span.group(0) if span else None})
    return sorted(out, key=lambda v: (v["definition"], v["reaches"]))


def compute(milestone: str, root: Path, sidecar: str | None = None, facts: list | None = None,
            model_path: Path | None = None) -> tuple[dict, dict]:
    from .typed_sidecar import load as load_sidecar
    root = Path(root)
    sc = load_sidecar(milestone, root, sidecar)
    asg_p = root / "gen" / milestone / "sorts" / "assignment.json"
    try:
        assignment = json.loads(asg_p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise OSError(f"{asg_p}: {e}") from None
    rels = documents_of(milestone, root, sidecar, facts)
    inputs = {asg_p.relative_to(root).as_posix(): sha256_file(asg_p), sc.rel: sha256_file(sc.path),
              sc.seeds.relative_to(root).as_posix(): sha256_file(sc.seeds)}
    if sc.binding:
        inputs[sc.binding] = sha256_file(root / sc.binding)
    tmodels, xmodels = {}, {}
    for rel in rels:
        inputs[rel] = sha256_file(root / rel)
        init = init_of(milestone, root, sidecar, rel)
        text, mm = generate(milestone, root, rel, typed=True, sidecar=sidecar, init=init, assignment=assignment)
        name = model_name(rel)
        regs = sorted(mm.basis.unions)
        ghosts = {r: "gc_" + re.sub(r"[^A-Za-z0-9_]", "_", r) for r in regs}
        doc = json.loads((root / rel).read_text(encoding="utf-8"))
        tmodels[name] = {"types": {s: mm.T(s) for s in mm.n1},
                         "ops": sorted(mm.ops.values(), key=lambda o: o["name"]),
                         "coercions": sorted(mm.coercions.values(), key=lambda c: c["name"]),
                         "ghosts": ghosts,
                         "external_guards": X.external_guards(doc)}
        mf = f"gen/{milestone}/sorts/models/{name}.bend"
        check_text, check_sha = text, hashlib.sha256(text.encode("utf-8")).hexdigest()
        if model_path is not None:
            check_text = Path(model_path).read_text(encoding="utf-8")
            check_sha = sha256_file(model_path)
        xmodels[name] = {"model_file": mf, "model_sha256": check_sha,
                         "hand_written": {"state": [], "fields": [], "defs": []},
                         "generated": sorted(ghosts.values()),
                         "violations": taint(check_text, sorted(ghosts.values()))}
    ins = [{"path": p, "sha256": h} for p, h in sorted(inputs.items())]
    types = {"document": "types", "types_version": TYPES_VERSION, "milestone": milestone,
             "sorts_sha256": assignment.get("sorts_sha256"), "inputs": ins, "models": tmodels}
    taint_doc = {"document": "taint", "types_version": TYPES_VERSION, "milestone": milestone, "inputs": ins,
                 "models": xmodels}
    return types, taint_doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon types")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root")
    ap.add_argument("--sidecar")
    ap.add_argument("--facts", action="append")
    ap.add_argument("--model", help="check this model file for taint instead of the generated one")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    from ..machine import ROOT as _ROOT
    root = Path(a.root).resolve() if a.root else _ROOT
    out = Path(a.out) if a.out else root / "gen" / a.milestone / "sorts"
    out = out if out.is_absolute() else Path.cwd() / out
    mp = None
    if a.model:
        mp = Path(a.model)
        mp = mp if mp.is_absolute() else Path.cwd() / mp
    try:
        types, taint_doc = compute(a.milestone, root, a.sidecar, a.facts, mp)
    except GenError as e:
        print(f"holon types: ill-sorted: {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError) as e:
        print(f"holon types: {e}", file=sys.stderr)
        return 1
    bad = [(m, v) for m, x in taint_doc["models"].items() for v in x["violations"]]
    if bad:
        for m, v in bad:
            print(f"holon types: taint ({m}): {v['definition']} (above the ghost marker) names {v['reaches']}"
                  f"{' at ' + v['span'] if v.get('span') else ''}", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    (out / "types.json").write_text(dumps(types), encoding="utf-8")
    (out / "taint.json").write_text(dumps(taint_doc), encoding="utf-8")
    for m, x in sorted(types["models"].items()):
        print(f"holon types: {m}: {len(x['types'])} types, {len(x['ops'])} typed operations, {len(x['coercions'])} "
              f"coercions, {len(x['ghosts'])} companions, {len(x['external_guards'])} external guards")
    return 0
