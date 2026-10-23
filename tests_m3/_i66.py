"""I66 instrument (holon differential's window view in M2's evidence set; Question Q62), fixed at the I66 prereg
(BUILD_PLAN §0.1, "instruments are inputs").

The contract is the docstring of tests_m3/test_view_evidence.py, rules V1-V9. This module writes out a second time,
independently of holon/, what those rules and I14's contract (the docstring of tests_m2/test_evidence.py) imply from
committed inputs, so that the tests can decide the predictions without asking the code under test what it should have
done. It reads JSON files and nothing else; nothing here imports holon/.

  window_declaration(path, root)       V3: the repo path of the window declaration a document is anchored by, or None
  lib_paths(path, root)                V3: the library files that apply to a document, as repo paths
  window_views(milestone, root)        V2: {stem: repo path} of the milestone's window views
  removed(view)                        V1: {action: [abstraction guard indices]} the view's extraction block records
  view_problems(abstraction, view)     V1: why the view is not its abstraction with exactly those guards removed
  reindex(rem, action, i)              the view's index of the abstraction's guard i of action, or None if removed
  kept_actions(abstraction, rem)       the actions whose guards the view keeps whole
  unchanged_reads(diagram, kept)       the endpoints whose reads no removed require can change
  anchors(diagram, sites, model)       I14's anchors rule, written again over one diagram
  naming_terms(statement)              the terms of a statement that I14's rule L2 reads
  law_atoms(law, doc)                  I14's rules L1-L4, written again: a law's model, named edges, context, atoms
  strip(entry)                         an atom or unresolved entry without "id" and "model", as canonical JSON
  relation(atoms, unresolved)          the (p, q, carrier) triples E2 relates by an atom or an unresolved entry
  e3_moved(atoms, rem)                 P2: the abstraction's E3 atoms carried to the view's guard positions
  exit_keys(diagram)                   I23's coverage keys of a diagram ("<facts>#<edge id>" of CODEC, CONS, TRANS)
  view_why(why, comp, view)            V7: the coverage why of a view's replayed action, from the abstraction's
  ledger_free(diagram)                 R5: a diagram with every ledger link and LEDGER or HASH debt emptied

A window view's model key is its file stem (I14's convention for fact documents); its diagram is
gen/<M>/diagram/<stem>.json.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
M = "M2"
VIEW = "gen/M2/extracted/m1_view.json"
VIEW_MODEL = "m1_view"
DECLARATION = "spec/M2/lib/window_rollup.json"
ABSTRACTION = "spec/M1/facts/morph_rollup.json"
ABSTRACTION_MODEL = "morph_rollup"
DIAGRAM = "gen/M2/diagram/m1_view.json"
ABSTRACTION_DIAGRAM = "gen/M2/diagram/morph_rollup.json"
FACT_DIAGRAMS = ("gen/M2/diagram/morph_batchdata.json", "gen/M2/diagram/morph_header.json", ABSTRACTION_DIAGRAM)
EVIDENCE = "gen/M2/evidence.json"
REGISTRY = "laws/M2/REGISTRY.json"
FACTS02 = "holon-facts/0.2"
WINDOW_VERSION = "holon-window/0.1"
ENDPOINTS = ("CODEC", "TRANS", "MIG", "CONS")
LEVELS = ("E1", "E2", "E3", "E4", "E5", "E6")
PATH_BINDERS = ("Trace", "State", "Act", "Reach")
IR01, IR02, IR03 = "holon-ir/0.1", "holon-ir/0.2", "holon-ir/0.3"
HAND = "the hand abstraction of "
_WHERE = re.compile(r"^guards\[(\d+)\]\.(require|expr)$")


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def canonical(obj) -> str:
    """I14's canonical JSON text: sorted keys, separators (",", ":"), no ASCII escaping."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(obj) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def _load_or_none(p: Path):
    try:
        return load(p)
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------------------------------- V2, V3
def _repo_path(x) -> bool:
    """A repository path: a non-empty relative string with no ".." part."""
    return isinstance(x, str) and bool(x) and not x.startswith("/") and ".." not in PurePosixPath(x).parts


def window_declaration(path: Path, root: Path = ROOT) -> str | None:
    """V3 (I65's anchor rule, written again): the repo path of the window declaration a document is anchored by. A JSON
    document whose extraction block names, in "declaration", a repository path under root whose JSON has
    window_version holon-window/0.1 and an "abstraction" that is a repository path of an existing file; else None."""
    p, root = Path(path), Path(root)
    if p.suffix != ".json" or not p.is_file():
        return None
    doc = _load_or_none(p)
    ex = doc.get("extraction") if isinstance(doc, dict) else None
    rel = ex.get("declaration") if isinstance(ex, dict) else None
    if not _repo_path(rel):
        return None
    decl = _load_or_none(root / rel)
    if (not isinstance(decl, dict) or decl.get("window_version") != WINDOW_VERSION
            or not _repo_path(decl.get("abstraction")) or not (root / decl["abstraction"]).is_file()):
        return None
    return rel


def lib_paths(path: Path, root: Path = ROOT) -> list:
    """V3: the repo paths of the library files that apply to the document at path: spec/lib/*.lib.json, then the
    *.lib.json of <anchor's dir>/../lib unless that is spec/lib, each sorted; the anchor is the declaration's
    abstraction for a window view (window_declaration), else the document itself."""
    root = Path(root).resolve()
    rel = window_declaration(path, root)
    anchor = root / load(root / rel)["abstraction"] if rel else Path(path)
    out = sorted((root / "spec" / "lib").glob("*.lib.json"))
    mine = anchor.resolve().parent.parent / "lib"
    if mine != (root / "spec" / "lib").resolve():
        out += sorted(mine.glob("*.lib.json"))
    return [q.resolve().relative_to(root).as_posix() for q in out]


def declarations(milestone: str, root: Path = ROOT) -> list:
    """The repo paths of the milestone's window declarations: spec/<M>/lib/window_*.json whose window_version is
    holon-window/0.1, sorted."""
    root = Path(root)
    out = []
    for p in sorted((root / "spec" / milestone / "lib").glob("window_*.json")):
        d = _load_or_none(p)
        if isinstance(d, dict) and d.get("window_version") == WINDOW_VERSION:
            out.append(p.relative_to(root).as_posix())
    return out


def window_views(milestone: str, root: Path = ROOT) -> dict:
    """V2: {stem: repo path} of every holon-facts/0.2 document directly under gen/<M>/extracted/ whose window
    declaration (window_declaration) is one of the milestone's (declarations)."""
    root = Path(root)
    decls = set(declarations(milestone, root))
    out = {}
    for p in sorted((root / "gen" / milestone / "extracted").glob("*.json")):
        d = _load_or_none(p)
        if isinstance(d, dict) and d.get("facts_version") == FACTS02 and window_declaration(p, root) in decls:
            out[p.stem] = p.relative_to(root).as_posix()
    return out


# ---------------------------------------------------------------------------------------------------- V1
def removed(view: dict) -> dict:
    """{action: sorted abstraction guard indices} as the view's extraction block records them (holon.differential)."""
    return {a: sorted(ix) for a, ix in sorted(((view.get("extraction") or {}).get("removed") or {}).items())}


def view_problems(abstraction: dict, view: dict) -> list:
    """Why the view is not the abstraction with exactly the recorded guards removed and its own extraction block (V1):
    [] when it is."""
    rem = removed(view)
    want = copy.deepcopy(abstraction)
    for a in want.get("actions") or []:
        gone = set(rem.get(a["name"], []))
        a["guards"] = [g for i, g in enumerate(a.get("guards") or []) if i not in gone]
    want["extraction"] = view.get("extraction")
    out = []
    names = {a["name"] for a in abstraction.get("actions") or []}
    out += [f"removed names an action the abstraction lacks: {a}" for a in rem if a not in names]
    for k in sorted(set(want) | set(view)):
        if want.get(k) != view.get(k):
            out.append(f"section {k} differs from the abstraction's with the recorded guards removed")
    return out


def reindex(rem: dict, action: str, i: int) -> int | None:
    """The view's index of the abstraction's guard i of action (None when the view removed it)."""
    gone = rem.get(action, [])
    if i in gone:
        return None
    return i - sum(1 for g in gone if g < i)


def kept_actions(abstraction: dict, rem: dict) -> list:
    """The actions whose guards the view keeps whole, sorted."""
    return sorted(a["name"] for a in abstraction.get("actions") or [] if not rem.get(a["name"]))


def unchanged_reads(diagram: dict, kept: list) -> set:
    """The edges whose access reads no removed require can change: the TRANS edges of the kept actions and every MIG,
    CONS and observer LOAD edge (a removed require is read by its own action's TRANS edge only)."""
    out = set()
    for e in diagram["edges"]:
        if e["kind"] == "TRANS" and e["component"] in kept:
            out.add(e["id"])
        elif e["kind"] in ("MIG", "CONS") or (e["kind"] == "LOAD" and e.get("observer")):
            out.add(e["id"])
    return out


# ---------------------------------------------------------------------------------------------------- I14's rules
def anchors(diagram: dict, sites: list, model: str) -> dict:
    """I14's anchors of a model (docstring of tests_m2/test_evidence.py, "anchors"), from its diagram and the frozen
    assignment's sites, written again here."""
    es = {e["id"]: e for e in diagram["edges"]}
    trans = sorted(i for i, e in es.items() if e["kind"] == "TRANS")
    actions = {es[i]["component"]: i for i in trans}
    reasons: dict = {}
    for i in trans:
        for g in es[i].get("guards") or []:
            if g.get("reason") is not None:
                reasons.setdefault(str(g["reason"]), set()).add(i)
    carriers = {}
    for i, e in es.items():
        if e["kind"] == "STORE":
            load_ = es.get(f"LOAD.{e['tgt']}") or {}
            carriers[e["tgt"]] = {"writers": sorted(e.get("writers") or []), "readers": sorted(load_.get("readers") or [])}
    preds = diagram.get("predicates") or {}
    return {
        "codec": {e["model_fn"]: i for i, e in es.items() if e["kind"] == "CODEC"},
        "domains": {p: sorted(i for i, e in es.items() if e["kind"] == "CODEC" and e.get("domain") == p) for p in preds},
        "actions": actions,
        "reasons": {k: sorted(v) for k, v in sorted(reasons.items())},
        "permissionless": sorted(i for i in trans if es[i].get("permissionless")),
        "observers": {e["component"]: i for i, e in es.items() if e["kind"] == "LOAD" and e.get("observer")},
        "migrations": {e["component"]: i for i, e in es.items() if e["kind"] == "MIG"},
        "consumers": {e["model_fn"]: i for i, e in es.items() if e["kind"] == "CONS"},
        "carriers": carriers,
        "trans": trans,
        "sites": {s["id"]: sorted({actions[o["action"]] for o in s.get("occurrences") or [] if o.get("action") in actions})
                  for s in sites if s.get("model") == model},
    }


def _terms(statement: dict):
    """Every JSON object of the statement's assume and claim (the hashed statement, I14's L2), depth first."""
    todo = [statement.get("claim"), statement.get("assume")]
    while todo:
        t = todo.pop()
        if isinstance(t, dict):
            yield t
            todo.extend(reversed(list(t.values())))
        elif isinstance(t, list):
            todo.extend(reversed(t))


def naming_terms(statement: dict) -> list:
    """The (key, canonical value) pairs of the statement that I14's rule L2 reads: "call", "act", "fn", "obsv", "mig",
    "proj" and "site" (every other term names nothing; a ghost term among them until I65's build), sorted."""
    out = []
    for t in _terms(statement):
        for k in ("call", "act", "fn", "obsv", "mig", "proj", "site"):
            if k in t:
                out.append((k, canonical(t[k])))
    return sorted(out)


def _named(statement: dict, irv: str, an: dict) -> set:
    """I14's rule L2, written again from the docstring of tests_m2/test_evidence.py."""
    out: set = set()
    for t in _terms(statement):
        f = t.get("call")
        if irv in (IR01, IR03) and isinstance(f, str):
            if f in an["codec"]:
                out.add(an["codec"][f])
            out.update(an["domains"].get(f, []))
        if irv not in (IR02, IR03):
            continue
        a = t.get("act")
        if isinstance(a, str) and a in an["actions"]:
            out.add(an["actions"][a])
        fn = t.get("fn")
        if isinstance(fn, str):
            if fn.startswith("is_") and fn[3:] in an["actions"]:
                out.add(an["actions"][fn[3:]])
            if fn == "perm":
                out.update(an["permissionless"])
            args = t.get("args")
            if fn == "no_code" and isinstance(args, list) and len(args) == 2 and isinstance(args[1], dict) \
                    and "nat" in args[1]:
                out.update(an["reasons"].get(str(args[1]["nat"]), []))
            if fn in an["consumers"]:
                out.add(an["consumers"][fn])
        o = t.get("obsv")
        if isinstance(o, str) and o in an["observers"]:
            out.add(an["observers"][o])
        mg = t.get("mig")
        if isinstance(mg, str) and mg in an["migrations"]:
            out.add(an["migrations"][mg])
        pj = t.get("proj")
        if isinstance(pj, list):
            for c in pj:
                if isinstance(c, str) and c in an["carriers"]:
                    out.update(an["carriers"][c]["writers"])
                    out.update(an["carriers"][c]["readers"])
        s = t.get("site")
        if irv == IR03 and isinstance(s, str):
            out.update(an["sites"].get(s, []))
    return out


def _version(statement: dict) -> int | None:
    """I14's rule L4 (holon-ir/0.1): the one value the premises fix for the record field "version", else None."""
    vals = set()
    for p in statement.get("assume") or []:
        eq = p.get("eq") if isinstance(p, dict) else None
        if not isinstance(eq, list) or len(eq) != 2:
            continue
        for a, b in (eq, eq[::-1]):
            if (isinstance(a, dict) and set(a) == {"field", "of"} and a["field"] == "version"
                    and isinstance(a["of"], dict) and set(a["of"]) == {"var"}
                    and isinstance(b, dict) and set(b) == {"bytes"} and isinstance(b["bytes"], str)):
                try:
                    vals.add(int(b["bytes"], 16))
                except ValueError:
                    continue
    return next(iter(vals)) if len(vals) == 1 else None


def law_atoms(law: dict, doc: dict) -> dict:
    """I14's rules L1-L4 (docstring of tests_m2/test_evidence.py, "Law evidence"), written again: {"model", "covered",
    "named", "context", "version", "atoms", "levels", "max"}. L4 is I14's holon-ir/0.1 rule; a holon-ir/0.3 law is
    taken to fix no version (I24's tag premise is not written here: no law the checks give it has one)."""
    models = doc.get("models") or {}
    model = next((m for m, mo in sorted(models.items()) if mo.get("facts") == law.get("facts")), None)
    sha = law.get("facts_sha256")
    covered = model is not None and (not sha or sha == models[model].get("facts_sha256"))
    out = {"model": model, "covered": covered, "named": [], "context": [], "version": None, "atoms": [],
           "levels": [], "max": None}
    if not covered:
        return out
    an = models[model]["anchors"]
    st = law.get("statement") or {}
    irv = law.get("ir_version")
    named = _named(st, irv, an)
    context = list(an["trans"]) if any(isinstance(b, dict) and b.get("type") in PATH_BINDERS
                                       for b in st.get("binders") or []) else []
    version = _version(st) if irv == IR01 else None
    n = named | set(context)
    rel = [a for a in doc.get("atoms") or [] if a["model"] == model and a["p"] in n and a["q"] in n
           and (a["p"] in named or a["q"] in named)
           and (version is None or "version" not in a["via"] or a["via"]["version"] == version)]
    levels = sorted({a["level"] for a in rel})
    out.update({"named": sorted(named), "context": context, "version": version, "atoms": sorted(a["id"] for a in rel),
                "levels": levels, "max": next((lv for lv in LEVELS if lv in levels), None)})
    return out


def strip(entry: dict) -> str:
    """An atom or unresolved entry without "id" and "model" (both name the model), as canonical JSON."""
    return canonical({k: v for k, v in entry.items() if k not in ("id", "model")})


def relation(atoms: list, unresolved: list) -> set:
    """The (p, q, carrier) triples E2 relates, by an atom or by an unresolved entry."""
    out = {(a["p"], a["q"], a["via"]["carrier"]) for a in atoms if a["level"] == "E2"}
    out |= {(u["p"], u["q"], u["carrier"]) for u in unresolved}
    return out


def e3_moved(atoms: list, rem: dict) -> list:
    """P2: the abstraction's E3 atoms (p = q = TRANS.<action>, via.where guards[i].require) whose guard the view keeps,
    each at the view's index of that guard, as stripped canonical JSON, sorted."""
    out = []
    for a in atoms:
        if a["level"] != "E3":
            continue
        m = _WHERE.match(a["via"]["where"])
        act = a["p"].split(".", 1)[1]
        j = reindex(rem, act, int(m.group(1)))
        if j is None:
            continue
        b = copy.deepcopy(a)
        b["via"]["where"] = f"guards[{j}].{m.group(2)}"
        out.append(strip(b))
    return sorted(out)


# ---------------------------------------------------------------------------------------------------- I23, R5
def exit_keys(diagram: dict) -> list:
    """The keys I23's exit coverage gives a diagram's CODEC, CONS and TRANS edges: "<diagram facts>#<edge id>"."""
    return sorted(f"{diagram['facts']}#{e['id']}" for e in diagram["edges"] if e["kind"] in ("CODEC", "CONS", "TRANS"))


def view_why(why: str, comp: str, view: dict) -> str:
    """V7: the coverage why of a window view's edge, from the abstraction's why for the same edge. Where the
    abstraction's reads "the hand abstraction of <comp> (<abstraction>, <its method>); its extracted counterpart ...",
    the view's reads "the window view's <comp> (gen/M2/extracted/m1_view.json, <the view's extraction method>); its
    extracted counterpart ..." (the rest unchanged); every other why is the abstraction's."""
    if not why.startswith(f"{HAND}{comp} ("):
        return why
    tail = why[why.index("); its extracted counterpart "):]
    return f"the window view's {comp} ({VIEW}, {view['extraction']['method']}" + tail


def ledger_free(diagram: dict) -> dict:
    """The diagram with every "ledger" value emptied and every LEDGER or HASH coverage debt removed: what a ledger
    bundle contributes to a facts-0.2 diagram (holon.diagram.build: Ctx.links, _hash_debt, the abstraction, assumption,
    parameter and migration ledger links)."""
    def walk(x):
        if isinstance(x, dict):
            return {k: ([] if k == "ledger" else walk(v)) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        return x
    out = walk(diagram)
    out["coverage_debt"] = [d for d in out.get("coverage_debt") or [] if d.get("kind") not in ("LEDGER", "HASH")]
    return out
