"""The sorts pass: fact documents -> the five gen/<M>/sorts documents (BUILD_PLAN I13).

Per model (fact document, named by its stem), in order:

  1. constraints (holon.sorts.flow walks the facts, holon.sorts.constraints writes the constraints);
  2. conflicts: while the model's active constraints are unsatisfiable (holon.sorts.solve.satisfiable), take
     a minimal core (holon.sorts.core.minimal_core, QuickXplain over the active constraints in order), report
     it, and set aside one constraint of the core: the first affine or compare constraint in core order (the
     ill-sorted expression: §7.8, a type error is never fixed by changing an assignment), else the last flow
     or link constraint, else the last constraint. Then repeat. Conflicts are results: the pass exits 0;
  3. the frozen assignment over the remaining constraints: a variable gets the sort every solution gives it
     (holon.sorts.solve.System.family), refined by members (unions) and writer labels (holon.sorts.unions);
     anything not forced is "Nat (unrefined)" and listed in unresolved.json;
  4. sites: one per (model, span, subtraction as written), with the §7.2 sort of the difference.

Site spans follow the contract: the span of the facts entry that holds the subtraction (its guard or let if
that has a src, else the action's effects_src for an effect, else the action's src), narrowed to the span of
a guard of the same action whose require contains a comparison implying the difference is non-negative and
whose span lies inside it (fewest lines; ties go to the guard listed first). Subtractions inside definitions,
observers and migrations are reported per definition (the occurrence names it; span: its src, else
"<model>:<name>"). A site whose occurrences disagree on the sort, or whose subtraction was set aside as a
conflict's culprit, has sort "Nat (unrefined)".
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..gen.targetlib import Library, lib_files
from . import constraints as C
from . import flow as F
from . import grammar as G
from . import unions as U
from .core import minimal_core
from .solve import System, satisfiable

SORTS_VERSION = "holon-sorts/0.1"
SEEDS = Path("spec") / "M2" / "lib" / "sort_seeds.json"
DOCUMENTS = ("constraints", "assignment", "conflicts", "unions", "unresolved")


class PassError(ValueError):
    pass


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def dumps(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


class Inputs:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.files: dict[str, str] = {}

    def rel(self, p: Path) -> str:
        try:
            return p.resolve().relative_to(self.root).as_posix()
        except ValueError:
            raise PassError(f"{p} is not inside the root {self.root}") from None

    def read_json(self, p: Path):
        data = p.read_bytes()
        self.files[self.rel(p)] = hashlib.sha256(data).hexdigest()
        return json.loads(data.decode("utf-8"))

    def listing(self) -> list[dict]:
        return [{"path": k, "sha256": v} for k, v in sorted(self.files.items())]


# ------------------------------------------------------------------ conflicts
def _culprit(core: list[dict]) -> dict:
    for c in core:
        if c["kind"] in ("affine", "compare"):
            return c
    for c in reversed(core):
        if c["kind"] in ("flow", "link"):
            return c
    return core[-1]


def find_conflicts(model: str, cs: list[dict]) -> tuple[list[dict], list[dict]]:
    active = list(cs)
    conflicts = []
    while not satisfiable(active):
        core = minimal_core(active, satisfiable)
        kinds = {c["kind"] for c in core}
        kind = "affine" if kinds & {"affine", "compare"} else "base"
        src = next((c["src"] for c in core if c["kind"] in ("affine", "compare") and c["src"]), None)
        if src is None:
            src = next((c["src"] for c in core if c["src"]), None)
        cul = _culprit(core)
        what = ("ill-sorted under §7.2" if kind == "affine" else "two base sorts meet")
        conflicts.append({"model": model, "kind": kind, "src": src, "core": [c["id"] for c in core],
                          "culprit": cul["id"],
                          "text": f"{what}: {cul['text']} (core: " + "; ".join(c["text"] for c in core) + ")"})
        active = [c for c in active if c is not cul]
    return active, conflicts


# ------------------------------------------------------------------ sites
def _implies_nonneg(cmp, a, b) -> bool:
    if not isinstance(cmp, list) or len(cmp) != 3 and not (len(cmp) == 2 and cmp[0] == "!"):
        return False
    op = cmp[0]
    if op == "<=" and cmp[1] == b and cmp[2] == a:
        return True
    if op == ">=" and cmp[1] == a and cmp[2] == b:
        return True
    if op == "<" and cmp[1] == b and cmp[2] == a:
        return True
    if op == ">" and cmp[1] == a and cmp[2] == b:
        return True
    if op == "!" and isinstance(cmp[1], list) and len(cmp[1]) == 3:
        inner = cmp[1]
        if inner[0] == "<" and inner[1] == a and inner[2] == b:
            return True
        if inner[0] == ">" and inner[1] == b and inner[2] == a:
            return True
    return False


def _contains_nonneg(e, a, b) -> bool:
    if _implies_nonneg(e, a, b):
        return True
    if isinstance(e, list):
        return any(_contains_nonneg(x, a, b) for x in e[1:] if isinstance(x, (list, dict)))
    if isinstance(e, dict):
        return any(_contains_nonneg(x, a, b) for x in e.values())
    return False


def _inside(inner: str, outer: str) -> bool:
    pi, po = F.span_lines(inner), F.span_lines(outer)
    return bool(pi and po and pi[0] == po[0] and po[1] <= pi[1] and pi[2] <= po[2])


def _nlines(sp: str) -> int:
    p = F.span_lines(sp)
    return p[2] - p[1] + 1


def site_span(model: str, facts: dict, ctx: F.Ctx, node: list) -> str:
    base = ctx.entry_span
    if ctx.actor_kind != "action":
        return base or f"{model}:{ctx.actor}"
    if base is None:
        return f"{model}:{ctx.actor}"
    action = next(a for a in facts["actions"] if a["name"] == ctx.actor)
    a, b = node[1], node[2]
    best, best_n = base, _nlines(base) if F.span_lines(base) else None
    for g in action.get("guards", []):
        if "require" not in g:
            continue
        gs = F.span(g.get("src"))
        if gs is None or not _inside(gs, base) or not _contains_nonneg(g["require"], a, b):
            continue
        n = _nlines(gs)
        if best_n is None or n < best_n:
            best, best_n = gs, n
    return best


def build_sites(model: str, facts: dict, prog: F.Program, system: System, active_ids: set,
                affine_ids: dict) -> list[dict]:
    groups: dict = {}
    for e in prog.events:
        if e[0] != "sub":
            continue
        _, node, lhs, rhs, out, ctx = e
        sp = site_span(model, facts, ctx, node)
        key = (sp, canonical(node))
        g = groups.setdefault(key, {"node": node, "occ": set(), "sorts": []})
        g["occ"].add((ctx.actor, ctx.where))
        cid = affine_ids.get(out)
        if cid is None or cid not in active_ids:
            g["sorts"].append(None)
        else:
            g["sorts"].append(system.difference_sorts(model, lhs, rhs))
    sites = []
    for (sp, ckey), g in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        ss = g["sorts"]
        if all(s is not None and len(s) == 1 for s in ss) and len({next(iter(s)) for s in ss}) == 1:
            sort = next(iter(ss[0]))
        else:
            sort = G.UNREFINED
        occ = sorted(g["occ"])
        sites.append({
            "id": f"{model}:{sp}:{hashlib.sha256(ckey).hexdigest()[:8]}",
            "model": model, "span": sp, "op": "-", "expr": g["node"], "sort": G.render(sort),
            "realized_in": "Nat", "obligation": "sign" if G.is_signed(sort) else None,
            "entry_points": sorted({a for a, _ in occ}),
            "occurrences": [{"action": a, "where": w} for a, w in occ]})
    ids = [s["id"] for s in sites]
    if len(ids) != len(set(ids)):
        raise PassError(f"{model}: two sites share an id")
    return sites


# ------------------------------------------------------------------ one model
class Model:
    def __init__(self, path: Path, inputs: Inputs, seeds: dict):
        self.path = path
        self.name = path.stem
        self.rel = inputs.rel(path)
        self.facts = inputs.read_json(path)
        self.version = self.facts.get("facts_version")
        self.prog = None
        self.walk03 = None
        if self.version == "holon-facts/0.3":
            # a transitions document (I30: the holon-facts/0.3 adapter, holon.sorts.extracted; seeds 0.2)
            from . import extracted as X
            if (self.facts.get("extraction") or {}).get("kind") != "transitions":
                raise PassError(f"{self.rel}: a holon-facts/0.3 document that is not a transitions document has no "
                                "sorts adapter")
            if seeds.get("seeds_version") != X.SEEDS_VERSION:
                raise PassError(f"{self.rel}: a holon-facts/0.3 document needs {X.SEEDS_VERSION} seeds, not "
                                f"{seeds.get('seeds_version')!r}")
            try:
                self.walk03 = X.walk(self.name, self.facts, seeds)
            except X.ExtractedError as e:
                raise PassError(f"{self.rel}: {e}") from e
            self.prog = self.walk03.prog
            self.keys = self.prog.keys
            self.raw = X.build(self.name, self.walk03)
            return
        if self.version == "holon-facts/0.2":
            lib = Library.for_facts(path, self.facts.get("params", {}), root=inputs.root)
            for p in lib_files(path, inputs.root):
                inputs.read_json(p)
            try:
                self.prog = F.walk(self.name, self.facts, lib.builtins)
            except (KeyError, TypeError, IndexError) as e:
                raise PassError(f"{self.rel}: malformed facts ({type(e).__name__}: {e})") from e
            self.keys = self.prog.keys
            raw = C.build_02(self.name, self.facts, self.prog, seeds)
        elif self.version == "holon-facts/0.1":
            self.keys, raw = C.build_01(self.name, self.facts)
        else:
            raise PassError(f"{self.rel}: facts_version {self.version!r} has no sorts adapter")
        self.raw = raw

    def solve(self, numbered: list[dict], writer_labels: dict) -> None:
        self.constraints = numbered
        self.active, self.conflicts = find_conflicts(self.name, numbered)
        self.system = System(self.active)
        active_ids = {c["id"] for c in self.active}
        self.assignment, self.provenance, self.unresolved = {}, {}, []
        fams = {k: self.system.family(self.name, k) for k in sorted(self.keys)}
        self.members = U.members(self.active)
        labels = U.labels(self.prog, fams, writer_labels) if self.prog else {}
        for k in sorted(self.keys):
            info = self.keys[k]
            sort, why = self._sort(k, info, fams[k], labels)
            self.assignment[k] = G.render(sort)
            if sort.head == "Unrefined":
                self.unresolved.append({"model": self.name, "var": k, "base_type": info["type"], "why": why})
            if k in labels and sort.label:
                self.provenance[k] = labels[k]
        if self.prog:
            affine_ids = {c["vars"][2]: c["id"] for c in numbered if c["kind"] == "affine"}
            if self.walk03 is not None:
                from . import extracted as X
                self.sites = X.build_sites(self.name, self.facts, self.walk03, self.system, active_ids, affine_ids)
            else:
                self.sites = build_sites(self.name, self.facts, self.prog, self.system, active_ids, affine_ids)
            writes = [(e[1], e[2], e[3]) for e in self.prog.events if e[0] == "write"]
            self.unions = U.union_entries(self.name, self.members, set(self.keys), self.active, writes,
                                          self.prog.writers)
        else:
            self.sites, self.unions = [], []

    def _sort(self, k: str, info: dict, fam: str | None, labels: dict):
        if info.get("ghost") and info["type"] not in ("Bool", "List<Bool>"):
            return G.UNREFINED, "ghost: hand-written ghost state is not read by the solver (honesty)"
        if fam is None:
            return G.UNREFINED, self.system.why_open(self.name, k)
        if fam in G.UNION_FAMILIES:
            ms = self.members.get(k, frozenset())
            if not ms:
                return G.UNREFINED, f"its family is {fam}, but no seed or flow gives it a member"
            return G.union([G.parse(m) for m in ms]), None
        if fam.startswith("Rec:"):
            return G.Sort("Rec", fam[4:]), None
        s = G.parse(fam)
        if s.head in G.LABELLED and k in labels:
            s = G.labelled(s, labels[k]["label"])
        return s, None


# ------------------------------------------------------------------ the pass
def run_pass(docs: list[Path], root: Path, milestone: str | None, seeds_path: Path | None = None,
             sidecar_path: Path | None = None) -> dict[str, dict]:
    """The pass over `docs`. seeds_path/sidecar_path: the typed-sorts sidecar of an M3+ or T30+ milestone and the
    seeds file it names (holon-sort-seeds/0.2, I30); both are inputs. Without them, I13's frozen M2 seeds."""
    root = Path(root).resolve()
    inputs = Inputs(root)
    if sidecar_path is not None:
        inputs.read_json(Path(sidecar_path))
    if seeds_path is None:
        seeds_path = root / SEEDS
        seeds = inputs.read_json(seeds_path)
        if seeds.get("seeds_version") != "holon-sort-seeds/0.1":
            raise PassError(f"{SEEDS}: seeds_version {seeds.get('seeds_version')!r}")
    else:
        seeds = inputs.read_json(Path(seeds_path))
        if seeds.get("seeds_version") != "holon-sort-seeds/0.2":
            raise PassError(f"{inputs.rel(Path(seeds_path))}: seeds_version {seeds.get('seeds_version')!r} (want "
                            "holon-sort-seeds/0.2)")
    models = []
    stems = [p.stem for p in docs]
    dup = sorted({s for s in stems if stems.count(s) > 1})
    if dup:
        raise PassError(f"two fact documents name the same model: {dup}")
    for p in sorted(docs, key=lambda p: p.stem):
        models.append(Model(p, inputs, seeds))
    numbered = C.number([c for m in models for c in m.raw])
    bymodel: dict[str, list] = {}
    for c in numbered:
        bymodel.setdefault(c["model"], []).append(c)
    wl = seeds.get("writer_labels", {})
    for m in models:
        m.solve(bymodel.get(m.name, []), wl)

    header = {"sorts_version": SORTS_VERSION, "milestone": milestone, "inputs": inputs.listing()}

    def doc(name: str, body: dict) -> dict:
        return {"document": name, **header, **body}

    conflicts = []
    for m in models:
        for i, c in enumerate(m.conflicts, 1):
            conflicts.append({"id": f"{m.name}.x{i:03d}", **c})
    unions = []
    for m in models:
        for i, u in enumerate(m.unions, 1):
            unions.append({"id": f"{m.name}.u{i:03d}", **u})
    assignment = doc("assignment", {
        "models": {m.name: {"facts": m.rel, "assignment": m.assignment, "provenance": m.provenance}
                   for m in models},
        "sites": [s for m in models for s in m.sites]})
    body = {k: v for k, v in assignment.items() if k != "inputs"}
    assignment["sorts_sha256"] = hashlib.sha256(canonical(body)).hexdigest()
    unresolved = [u for m in models for u in m.unresolved]
    return {
        "constraints": doc("constraints", {"constraints": numbered}),
        "assignment": assignment,
        "conflicts": doc("conflicts", {"conflicts": conflicts}),
        "unions": doc("unions", {"unions": unions}),
        "unresolved": doc("unresolved", {"count": len(unresolved), "unresolved": unresolved}),
    }
