"""The generated go.work of a corpus run under rule main_module (I103, D1; the contract is the docstring of
tests_m6/test_i103_frontend_reach.py, rule F5; the protocol is spec/M6/lib/i103_run.json go.work_replace).

A package whose module has a relative replace that leaves the module directory is built in a workspace: a go.work at
the checkout's root whose use list is the closure of the module directory under its relative replace targets that hold
a go.mod (I51's rule, unchanged). In workspace mode Go applies the replace directives of every used module, and stops
with "conflicting replacements" when two used modules replace one module path with different targets, unless go.work
itself replaces that path. Outside workspace mode only the main module's replaces apply. Rule main_module therefore
writes, for every module path two used modules replace differently, the replace of the module that holds the package
(the main module of the build the package's own go.mod describes), its relative target rewritten relative to the
workspace root. When the main module does not replace that path itself, nothing in the sources says which replace the
build means: the conflict is recorded (path, and each module's target) and no go.work is written, so the document
fails with that reason. The go line is the highest go directive among the used modules (go.work's go must be at least
every used module's). Everything is sorted; the text is a function of the go.mod files alone.
"""
from __future__ import annotations

import re
from pathlib import Path

RULE = "main_module"


def _vkey(v: str) -> tuple:
    parts = [int(x) for x in re.match(r"\d+(?:\.\d+)*", v).group(0).split(".")]
    return tuple(parts + [0] * (3 - len(parts)))


def parse(mod_dir: Path) -> dict:
    """{module, go, replaces: [(old path, old version or None, target, target version or None)], rel: [targets]}."""
    text = (mod_dir / "go.mod").read_text(encoding="utf-8", errors="replace")
    body = re.sub(r"//[^\n]*", "", text)
    mod = re.search(r"(?m)^\s*module\s+(\S+)", body)
    gov = re.search(r"(?m)^\s*go\s+(\S+)", body)
    lines = []
    for blk in re.findall(r"(?ms)^\s*replace\s*\((.*?)\)", body):
        lines += [ln for ln in blk.splitlines() if "=>" in ln]
    lines += re.findall(r"(?m)^\s*replace\s+([^(\n][^\n]*=>[^\n]*)$", body)
    reps = []
    for ln in lines:
        left, right = ln.split("=>", 1)
        lw, rw = [w.strip('"') for w in left.split()], [w.strip('"') for w in right.split()]
        if not lw or not rw:
            continue
        reps.append((lw[0], lw[1] if len(lw) > 1 else None, rw[0], rw[1] if len(rw) > 1 else None))
    rel = [r[2] for r in reps if r[2].startswith("./") or r[2].startswith("../") or r[2] in (".", "..")]
    return {"module": mod.group(1).strip('"') if mod else None, "go": gov.group(1) if gov else None,
            "replaces": reps, "rel": rel}


def _is_local(t: str) -> bool:
    return t.startswith("./") or t.startswith("../") or t in (".", "..") or t.startswith("/")


def uses_of(ck: Path, module_dir: Path) -> list[Path]:
    """The closure of module_dir under relative replace targets that hold a go.mod, inside the checkout."""
    ck = ck.resolve()
    uses, todo = [], [module_dir.resolve()]
    while todo:
        d = todo.pop()
        if d in uses or not (d / "go.mod").is_file() or ck not in [d, *d.parents]:
            continue
        uses.append(d)
        todo += [(d / t).resolve() for t in parse(d)["rel"]]
    return uses


def _rel(ck: Path, d: Path) -> str:
    return "./" + d.relative_to(ck).as_posix() if d != ck else "."


def generate(ck: Path, module_dir: Path, rule: str = RULE) -> dict:
    """{"text", "uses", "go", "replaces", "conflicts"} of the go.work for module_dir's package (rule main_module)."""
    if rule != RULE:
        raise ValueError(f"go.work rule {rule!r} (want {RULE!r})")
    ck = ck.resolve()
    main = module_dir.resolve()
    used = uses_of(ck, main)
    parsed = {d: parse(d) for d in used}
    rels = sorted(_rel(ck, d) for d in used)
    gos = [p["go"] for p in parsed.values() if p["go"]]
    go = max(gos, key=_vkey) if gos else "1.21"
    # every used module's replaces, keyed by the replaced (path, version); targets resolved to compare them
    by_path: dict = {}
    for d in sorted(used):
        for old, oldv, tgt, tgtv in parsed[d]["replaces"]:
            res = (str((d / tgt).resolve()), None) if _is_local(tgt) else (tgt, tgtv)
            by_path.setdefault((old, oldv), {})[d] = (res, tgt, tgtv)
    replaces, conflicts = [], []
    for (old, oldv), per in sorted(by_path.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        if len({v[0] for v in per.values()}) < 2:
            continue
        name = old + (f" {oldv}" if oldv else "")
        if main in per:
            (res, tgt, tgtv) = per[main]
            if _is_local(tgt):
                t = Path(res[0])
                target = _rel(ck, t) if ck in [t, *t.parents] else res[0]
            else:
                target = tgt + (f" {tgtv}" if tgtv else "")
            replaces.append({"path": old, "version": oldv, "target": target, "from": _rel(ck, main),
                             "line": f"{name} => {target}"})
        else:
            conflicts.append({"path": old, "version": oldv,
                              "targets": {_rel(ck, d): v[1] + (f" {v[2]}" if v[2] else "") for d, v in sorted(per.items())}})
    text = None
    if not conflicts:
        text = f"go {go}\n\nuse (\n" + "".join(f"\t{r}\n" for r in rels) + ")\n"
        if replaces:
            text += "\nreplace (\n" + "".join(f"\t{r['line']}\n" for r in replaces) + ")\n"
    return {"text": text, "uses": rels, "go": go, "replaces": replaces, "conflicts": conflicts}


def conflict_reason(g: dict) -> str:
    return "generated go.work (rule main_module): conflicting replacements the package's own module does not settle: " \
        + "; ".join(f"{c['path']}{' ' + c['version'] if c['version'] else ''}: " +
                    ", ".join(f"{m} => {t}" for m, t in c["targets"].items()) for c in g["conflicts"])
