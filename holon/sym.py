"""Rule SYM's analysis (BUILD_PLAN I34; whitepaper §5.4 SYM: symmetry splits; the contract is rules J1, J5, J7 and J8 of
the docstring of tests_m3/test_sym.py).

`holon sym --milestone M [--check]` writes results/<M>/sym/families.json from a typed milestone's facts document (the
typed sidecar's, holon.sorts.typed_sidecar) and its sort assignment (gen/<M>/sorts/assignment.json):

  families   tau: admitted when some word of the assignment is Time (its Time words: storage families and members,
             env:*, call:* answers); pi: admitted when the facts have a set role (roles below); iota and mu: admitted
             only with an Idx or an Amt sort in the assignment, else vacuous with the reason; omega: admitted when the
             facts have an eligible pair.
  roles      a principal predicate that reads storage names a role (the modifier without its "only", first letter
             lower-cased), kind "set" when it looks the caller up in a mapping, "singleton" when it compares the caller
             with a scalar; an address register some action writes with the caller names a role by its own name, kind
             "set" for a member of a mapping family's struct, "singleton" for a scalar; "set" wins when both apply.
  pairs      two state-changing actions, neither an initializer (modifiers initializer or reinitializer), of different
             principal classes, and a sink family (read by some guard, or by a view's return) one writes and the other
             writes or reads (J5).
  sentinels  a Time-sorted register compared against an integer constant in a guard or a view's return; its write sites
             whose value is not that constant (J7).

After `holon run`, splits() reads the SYM records into results/<M>/sym/<family>.json and the adjudication requests
audit/sym_adjudications/<family>_<role or time>.json (J8), and races.json lists the race_disabling pairs (J5). Every
name comes from the facts and the assignment: nothing here names a target.
"""
from __future__ import annotations

import json
from pathlib import Path

SYM_VERSION = "holon-sym/0.1"
CMP = ("==", "!=", "<", "<=", ">", ">=")
TIME, IDX, AMT = "Time", "Idx", "Amt"


class SymError(ValueError):
    pass


def dumps(doc) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sym_dir(root: Path, milestone: str) -> Path:
    return Path(root) / "results" / milestone / "sym"


# ---------------------------------------------------------------------------------------------------- inputs
def typed_inputs(root: Path, milestone: str) -> tuple[str, dict, dict]:
    """(facts path, facts, the model's assignment) of a typed milestone's one sorted document."""
    a = _load(Path(root) / "gen" / milestone / "sorts" / "assignment.json")
    models = a.get("models") or {}
    if len(models) != 1:
        raise SymError(f"gen/{milestone}/sorts/assignment.json has {len(models)} models; SYM states one")
    (name, m), = models.items()
    rel = (m.get("facts") or {}).get("path") if isinstance(m.get("facts"), dict) else m.get("facts")
    if not isinstance(rel, str):
        rel = next((d.get("path") for d in a.get("inputs") or [] if str(d.get("path", "")).endswith(".extracted.json")),
                   None)
    if not isinstance(rel, str):
        raise SymError(f"the assignment of {name} names no facts document")
    return rel, _load(Path(root) / rel), dict(m.get("assignment") or {})


def _walk(e):
    yield e
    if isinstance(e, list):
        for x in e:
            yield from _walk(x)
    elif isinstance(e, dict):
        for x in e.values():
            yield from _walk(x)


def _families_in(e) -> set:
    return {x[1] for x in _walk(e) if isinstance(x, list) and len(x) == 2 and x[0] == "storage" and isinstance(x[1], str)}


def _changing(a: dict) -> bool:
    return a.get("mutability") not in ("view", "pure")


def _initializer(a: dict) -> bool:
    return any(m in ("initializer", "reinitializer") for m in a.get("modifiers") or [])


def principal_class(a: dict):
    p = a.get("principal")
    return p.get("modifier") if isinstance(p, dict) else None


def _reads(a: dict) -> set:
    out: set = set()
    for k in ("guards", "writes", "returns", "checks", "loops", "calls", "post"):
        out |= _families_in(a.get(k))
    return out


def _writes(a: dict) -> set:
    return {w.get("family") for w in a.get("writes") or [] if isinstance(w, dict)}


# ---------------------------------------------------------------------------------------------------- families
def time_words(assignment: dict, facts: dict | None = None) -> list:
    """The Time words, sorted, in J1's format: "storage:<family>[.<member>]" for a storage variable of the facts,
    "param:<action>.<param>" for an action's argument, and the assignment's own "env:<x>" and "call:<x>"."""
    fams = {s["name"] for s in (facts or {}).get("storage") or []}
    out = []
    for k, v in assignment.items():
        if v != TIME or k.startswith("loop:"):
            continue
        if k.startswith(("env:", "call:")):
            out.append(k)
        elif k.split(".", 1)[0] in fams:
            out.append(f"storage:{k}")
        else:
            out.append(f"param:{k}")
    return sorted(out)


def roles(facts: dict) -> list:
    """[[name, kind]] sorted (see the module docstring)."""
    st = {s["name"]: s for s in facts.get("storage") or []}
    kinds: dict = {}

    def add(name: str, kind: str) -> None:
        kinds[name] = "set" if "set" in (kinds.get(name), kind) else kind
    for a in facts.get("actions") or []:
        p = a.get("principal")
        if isinstance(p, dict) and p.get("modifier") and _families_in(p.get("predicate")):
            mod = p["modifier"][4:] if p["modifier"].startswith("only") else p["modifier"]
            pred = p.get("predicate")
            add(mod[:1].lower() + mod[1:], "set" if isinstance(pred, list) and pred[:1] == ["map"] else "singleton")
        for w in a.get("writes") or []:
            v, fam = w.get("value"), st.get(w.get("family")) or {}
            if isinstance(v, list) and v[:1] == ["struct"]:
                types = {f["name"]: f.get("type") for f in fam.get("fields") or []}
                for name, val in v[2]:
                    if val == ["caller"] and types.get(name) == "address":
                        add(name, "set" if fam.get("kind") == "mapping" else "singleton")
            elif v == ["caller"] and fam.get("value") == "address":
                add(w["family"], "singleton")
    return sorted([k, v] for k, v in kinds.items())


def _sinks(facts: dict) -> set:
    out: set = set()
    for a in facts.get("actions") or []:
        for g in a.get("guards") or []:
            out |= _families_in(g.get("expr"))
        if not _changing(a):
            out |= _families_in(a.get("returns"))
    return out


def pairs(facts: dict) -> list:
    acts = sorted((a for a in facts.get("actions") or [] if _changing(a) and not _initializer(a)),
                  key=lambda a: a["name"])
    sinks = _sinks(facts)
    out = []
    for i, a in enumerate(acts):
        for b in acts[i + 1:]:
            if principal_class(a) == principal_class(b):
                continue
            wa, wb, ra, rb = _writes(a), _writes(b), _reads(a), _reads(b)
            if ((wa & (wb | rb)) | (wb & ra)) & sinks:
                out.append([a["name"], b["name"]])
    return out


def _register(e):
    if isinstance(e, list) and len(e) == 2 and e[0] == "storage" and isinstance(e[1], str):
        return e[1]
    if (isinstance(e, list) and len(e) == 3 and e[0] == "member" and isinstance(e[1], list) and e[1][:1] == ["map"]
            and isinstance(e[1][1], list) and e[1][1][:1] == ["storage"]):
        return f"{e[1][1][1]}.{e[2]}"
    return None


def constant_compares(facts: dict):
    """(action, where, operator, register, constant) for each comparison of a storage register against an integer
    constant in a guard (where: its src) or a view's return (where: "returns")."""
    for a in facts.get("actions") or []:
        places = [(g.get("src") or "guard", g.get("expr")) for g in a.get("guards") or []]
        if not _changing(a):
            places.append(("returns", a.get("returns")))
        for where, e in places:
            for x in _walk(e):
                if isinstance(x, list) and len(x) == 3 and x[0] in CMP:
                    for reg, c in ((x[1], x[2]), (x[2], x[1])):
                        if isinstance(c, int) and not isinstance(c, bool):
                            path = _register(reg)
                            if path:
                                yield a["name"], where, x[0], path, c


def write_values(facts: dict, path: str):
    fam, _, mem = path.partition(".")
    for a in facts.get("actions") or []:
        for w in a.get("writes") or []:
            if w.get("family") != fam:
                continue
            v = w.get("value")
            if mem:
                if isinstance(v, list) and v[:1] == ["struct"]:
                    for name, val in v[2]:
                        if name == mem:
                            yield a["name"], w.get("src"), val
            elif not (isinstance(v, list) and v[:1] == ["struct"]):
                yield a["name"], w.get("src"), v


def sentinels(facts: dict, assignment: dict) -> list:
    """[{register, constant, compares: [action:where], sites: [{action, src}]}] sorted by register."""
    tw = set(time_words(assignment, facts))
    regs: dict = {}
    for act, where, _, path, c in constant_compares(facts):
        if f"storage:{path}" in tw:
            regs.setdefault((path, c), set()).add(f"{act}:{where}")
    out = []
    for (path, c), cmps in sorted(regs.items()):
        sites = sorted({(act, src) for act, src, v in write_values(facts, path) if v != c})
        out.append({"register": path, "constant": c, "compares": sorted(cmps),
                    "sites": [{"action": a, "src": s} for a, s in sites]})
    return out


def families(facts: dict, assignment: dict) -> list:
    sorts = set(assignment.values())
    rs = roles(facts)
    out = [{"family": "tau", "status": "admitted" if TIME in sorts else "vacuous",
            "time_words": time_words(assignment, facts),
            **({} if TIME in sorts else {"reason": "no word of the assignment has the sort Time"})}]
    sets, singles = [r for r, k in rs if k == "set"], [r for r, k in rs if k == "singleton"]
    out.append({"family": "pi", "status": "admitted" if sets else "vacuous", "roles": sets, "singleton_roles": singles,
                **({} if sets else {"reason": "no set role: a singleton role has at most one member"})})
    for fam, sort in (("iota", IDX), ("mu", AMT)):
        out.append({"family": fam, "status": "admitted" if sort in sorts else "vacuous",
                    **({} if sort in sorts else {"reason": f"no word of the assignment has the sort {sort} (the sorts "
                                                           f"are {', '.join(sorted(sorts))})"})})
    ps = pairs(facts)
    out.append({"family": "omega", "status": "admitted" if ps else "vacuous", "pairs": ps,
                **({} if ps else {"reason": "no eligible pair"})})
    return sorted(out, key=lambda f: f["family"])


def analysis(root: Path, milestone: str) -> dict:
    rel, facts, assignment = typed_inputs(root, milestone)
    return {"sym_version": SYM_VERSION, "milestone": milestone, "facts": rel,
            "families": families(facts, assignment), "sentinels": sentinels(facts, assignment)}


def main(root: Path, milestone: str, check: bool = False) -> int:
    doc = analysis(root, milestone)
    p = sym_dir(root, milestone) / "families.json"
    text = dumps(doc)
    if check:
        ok = p.is_file() and p.read_text(encoding="utf-8") == text
        print("SYM OK" if ok else f"SYM DIFFERS: {p} is not what holon sym writes")
        return 0 if ok else 1
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    fam = {f["family"]: f["status"] for f in doc["families"]}
    print(f"holon sym: {', '.join(f'{k} {v}' for k, v in sorted(fam.items()))}; "
          f"{len(next(f for f in doc['families'] if f['family'] == 'omega').get('pairs') or [])} pairs; "
          f"{sum(len(s['sites']) for s in doc['sentinels'])} sentinel sites -> {p}")
    return 0


def cli(argv: list[str]) -> int:
    """`holon sym --milestone M [--root DIR] [--check]`: exit 0 written (or --check reproduced), 1 --check differs,
    2 refused (no typed milestone of one sorted document)."""
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="holon sym")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    try:
        return main(Path(a.root), a.milestone, check=a.check)
    except (SymError, OSError, ValueError) as e:
        print(f"holon sym: {e}", file=sys.stderr)
        return 2
