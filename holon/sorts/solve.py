"""The sort solver: a pure-Python union-find over the §7.2 rules (whitepaper §7.7 steps 2-3; BUILD_PLAN I13).

`satisfiable(constraints) -> bool` decides from the constraint objects alone (holon.sorts.constraints writes
them; every field read here is in each object). Variables are (model, name) pairs, so constraints of
different models never interact.

  flow, compare, link   unify the BASE sorts of their two variables (R2): one union-find class
  seed, type            fix the family of their variable's class (grammar.families of "sort"; a union sort
                        contributes one family per member, so a seed whose grounds disagree on the family
                        clashes by itself)
  affine                {"op": "+" | "-", "vars": [lhs, rhs, out]}: the §7.2 table on families, with the
                        result realized unsigned (R1: SDur flows on as Dur, SIdx[k] as Idx[k], SCnt[k] as Cnt[k])
  writer                provenance only (labels are not unified, R2): ignored here

Decision procedure. After the union-find, a class with two fixed families is a base clash. The affine
constraints link classes into components; every affine triple lies in one torsor pair (Time/Dur, or
Idx[k]/Cnt[k]) or one closed sort (Amt[a], Mach(w)), so in any solution a whole component lives in one pair.
The fixed classes of a component name its pair: none means the component is free (every class a group
element satisfies both tables), two pairs or a fixed family outside arithmetic (Dig, Prin, Ver, Bool, a
record) is a clash. Inside a pair each class is a point P or a group element G, and the table is a relation
on roles:

  +: (P,G,P) (G,P,P) (G,G,G)        -: (P,P,G) (P,G,P) (G,G,G)

decided exactly by generalized arc consistency and backtracking. The procedure is exact (not a propagation
approximation): restricting to the pairs the fixed classes name loses no solution, since a free component can
be renamed into any pair. It is monotone, so holon.sorts.core.minimal_core's QuickXplain finds minimal cores.

`System(constraints)` also answers what the constraints force: `family(model, var)` is the family every
solution gives the variable (None when two solutions differ, or nothing constrains it), and
`difference_sorts(model, a, b)` the §7.2 sorts the subtraction a - b can take.
"""
from __future__ import annotations

from . import grammar as G

TABLES = {"+": frozenset({("P", "G", "P"), ("G", "P", "P"), ("G", "G", "G")}),
          "-": frozenset({("P", "P", "G"), ("P", "G", "P"), ("G", "G", "G")})}
UNIFY = ("flow", "compare", "link")
FIX = ("seed", "type")
KINDS = UNIFY + FIX + ("affine", "writer")


class SolveError(ValueError):
    pass


class UF:
    def __init__(self):
        self.parent: dict = {}

    def add(self, x):
        self.parent.setdefault(x, x)

    def find(self, x):
        self.add(x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            if rb < ra:
                ra, rb = rb, ra
            self.parent[rb] = ra  # the smaller key is the root: deterministic


def _vars(c: dict) -> list:
    vs = c.get("vars")
    if not isinstance(vs, list) or not all(isinstance(v, str) for v in vs):
        raise SolveError(f"constraint {c.get('id')}: vars must be a list of names")
    return [(c["model"], v) for v in vs]


def _propagate(doms: dict, cons: list) -> bool:
    changed = True
    while changed:
        changed = False
        for tab, trip in cons:
            sup = []
            for t in tab:
                ok = True
                seen: dict = {}
                for pos in range(3):
                    v = trip[pos]
                    if t[pos] not in doms[v] or seen.setdefault(v, t[pos]) != t[pos]:
                        ok = False
                        break
                if ok:
                    sup.append(t)
            for pos in range(3):
                v = trip[pos]
                new = doms[v] & {t[pos] for t in sup}
                if new != doms[v]:
                    if not new:
                        return False
                    doms[v] = new
                    changed = True
    return True


def _search(doms: dict, cons: list) -> bool:
    doms = {v: set(d) for v, d in doms.items()}
    if not _propagate(doms, cons):
        return False
    for v in sorted(doms):
        if len(doms[v]) > 1:
            for val in sorted(doms[v]):
                trial = dict(doms)
                trial[v] = {val}
                if _search(trial, cons):
                    return True
            return False
    return True


class Component:
    """Classes linked by affine constraints, with the pair their fixed classes name."""

    def __init__(self, roots: list, cons: list, fixed: dict):
        self.roots = sorted(roots)
        self.ok = True
        self.pair: str | None = None
        self.single = False
        self._roles: dict = {}
        pairs, roles = set(), {}
        for r in self.roots:
            fam = fixed.get(r)
            if fam is None:
                continue
            pr = G.pair_role(fam)
            if pr is None:
                self.ok = False  # a non-arithmetic family under + or -
                return
            pairs.add(pr[0])
            roles[r] = pr[1]
        if len(pairs) > 1:
            self.ok = False
            return
        self.pair = next(iter(pairs)) if pairs else None
        self.single = self.pair is not None and self.pair.startswith("S:")
        self.cons = [(TABLES[op], trip) for op, trip in cons]
        self.doms = {r: ({roles[r]} if r in roles else {"P", "G"}) for r in self.roots}
        if self.pair is None or self.single:
            return  # free (all G satisfies both tables) or a closed sort (all S)
        self.ok = _search(self.doms, self.cons)

    def roles(self, r) -> set:
        """The roles r takes over all solutions (pair known, not a closed sort)."""
        if r not in self._roles:
            self._roles[r] = {x for x in sorted(self.doms[r]) if _search({**self.doms, r: {x}}, self.cons)}
        return self._roles[r]

    def role_pairs(self, a, b) -> set:
        out = set()
        for x in sorted(self.roles(a)):
            for y in sorted(self.roles(b)):
                if a == b:
                    if x == y:
                        out.add((x, y))
                elif _search({**self.doms, a: {x}, b: {y}}, self.cons):
                    out.add((x, y))
        return out


class System:
    def __init__(self, constraints: list):
        self.uf = UF()
        fix_items, affine = [], []
        for c in constraints:
            kind = c.get("kind")
            if kind not in KINDS:
                raise SolveError(f"constraint {c.get('id')}: unknown kind {kind!r}")
            vs = _vars(c)
            for v in vs:
                self.uf.add(v)
            if kind in UNIFY:
                if len(vs) != 2:
                    raise SolveError(f"constraint {c.get('id')}: {kind} relates two variables")
                self.uf.union(vs[0], vs[1])
            elif kind in FIX:
                if len(vs) != 1:
                    raise SolveError(f"constraint {c.get('id')}: a {kind} constraint is a unit constraint")
                fix_items.append((vs[0], G.families(G.parse(c["sort"]))))
            elif kind == "affine":
                if len(vs) != 3 or c.get("op") not in TABLES:
                    raise SolveError(f"constraint {c.get('id')}: affine needs op +/- and vars [lhs, rhs, out]")
                affine.append((c["op"], vs))
        find = self.uf.find
        fams: dict = {}
        for v, fs in fix_items:
            fams.setdefault(find(v), set()).update(fs)
        self.ok = all(len(fs) <= 1 for fs in fams.values())
        self.fixed = {r: next(iter(fs)) for r, fs in fams.items() if len(fs) == 1}
        # affine components over classes
        cuf = UF()
        triples = []
        for op, vs in affine:
            trip = tuple(find(v) for v in vs)
            triples.append((op, trip))
            for r in trip:
                cuf.add(r)
            cuf.union(trip[0], trip[1])
            cuf.union(trip[0], trip[2])
        groups: dict = {}
        for r in sorted(cuf.parent):
            groups.setdefault(cuf.find(r), []).append(r)
        bycomp: dict = {}
        for op, trip in triples:
            bycomp.setdefault(cuf.find(trip[0]), []).append((op, trip))
        self.comp_of: dict = {}
        self.components = []
        for key in sorted(groups):
            comp = Component(groups[key], bycomp.get(key, []), self.fixed)
            self.components.append(comp)
            for r in comp.roots:
                self.comp_of[r] = comp
            if not comp.ok:
                self.ok = False

    # ---------------------------------------------------------- what the constraints force
    def family(self, model: str, var: str) -> str | None:
        """The family every solution gives (model, var); None when unconstrained or not forced."""
        if not self.ok:
            raise SolveError("family() on an unsatisfiable system")
        r = self.uf.find((model, var))
        if r in self.fixed:
            return self.fixed[r]
        comp = self.comp_of.get(r)
        if comp is None or comp.pair is None:
            return None
        if comp.single:
            return G.family_of(comp.pair, "S")
        roles = comp.roles(r)
        return G.family_of(comp.pair, next(iter(roles))) if len(roles) == 1 else None

    def why_open(self, model: str, var: str) -> str:
        """Why (model, var) has no forced family (for unresolved.json)."""
        r = self.uf.find((model, var))
        comp = self.comp_of.get(r)
        if comp is None:
            return "no seed, type or affine constraint reaches its class"
        if comp.pair is None:
            return "its arithmetic component holds no seeded variable, so no torsor pair is forced"
        return "its component's pair is forced, but not whether it is a point or a group element"

    def difference_sorts(self, model: str, a: str, b: str) -> set | None:
        """The §7.2 sorts a - b takes over all solutions (signed where the table says so); None when the
        operands' component has no forced pair."""
        ra, rb = self.uf.find((model, a)), self.uf.find((model, b))
        comp = self.comp_of.get(ra)
        if comp is None or comp is not self.comp_of.get(rb) or comp.pair is None:
            return None
        if comp.single:
            return {G.parse(G.family_of(comp.pair, "S"))}
        out = set()
        for x, y in comp.role_pairs(ra, rb):
            d = G.difference_sort(comp.pair, x, y)
            if d is not None:
                out.add(d)
        return out

    def same_class(self, model: str, a: str, b: str) -> bool:
        return self.uf.find((model, a)) == self.uf.find((model, b))


def satisfiable(constraints: list) -> bool:
    """True iff some assignment of sorts satisfies every constraint (see the module docstring)."""
    return System(constraints).ok
