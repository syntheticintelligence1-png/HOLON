"""Untagged unions (§7.4) and writer-provenance labels (§7.3) over a solved constraint set (BUILD_PLAN I13).

Members (rule R5). Flow unifies base families; within the union-capable families (Dig, whose members are
digest kinds, and Prin, whose members are roles) the members a variable carries are those of its own seed
(a lexical seed on a register counts as one of its members) and of every value that flows into it:
members(v) = seed(v) ∪ ⋃ {members(u) : a flow constraint u -> v}, computed to a fixpoint over the active flow
constraints. Members travel with values, in the direction of flow only. A variable with two or more members
carries their union; distinct families never reach this point (they clash in holon.sorts.solve).

Labels (rules R2-R4). Values carry base sorts, never labels (R2): a register's label is a function of its
own writer set (the syntactic writers of holon.sorts.flow), so a one-way copy b := a keeps the labels of a
and b apart. Registers that read each other's values both ways, i.e. lie in one strongly connected component
of the register flow graph (an edge a -> b for every write of b whose written expression reads a, directly or
through lets), share one label per base family, computed from the union of their writer sets (R3). Because
labels never travel with values, the "Idx[k] with distinct labels" branch of R5 does not arise in this
construction: a register has exactly one label.

Union entries. The variables carrying one union sort are grouped by the weakly connected components of the
flow graph restricted to variables (keys and auxiliaries) carrying that same union; an entry lists the keys
of one component. Its "writers" map each member to the actions and migrations whose writes of a register in
the entry carry that member.
"""
from __future__ import annotations

from . import grammar as G


def seed_members(constraints: list[dict]) -> dict[str, set]:
    out: dict[str, set] = {}
    for c in constraints:
        if c["kind"] != "seed":
            continue
        s = G.parse(c["sort"])
        for m in (s.members if s.head == "Union" else (s,)):
            if m.head in G.UNION_FAMILIES:
                out.setdefault(c["vars"][0], set()).add(G.render(m))
    return out


def flow_edges(constraints: list[dict]) -> list[tuple[str, str]]:
    return [(c["vars"][0], c["vars"][1]) for c in constraints if c["kind"] == "flow"]


def members(constraints: list[dict]) -> dict[str, frozenset]:
    """members(v) for every variable that carries any (fixpoint over the flow constraints)."""
    succ: dict[str, list] = {}
    for a, b in flow_edges(constraints):
        succ.setdefault(a, []).append(b)
    mem = {v: set(ms) for v, ms in seed_members(constraints).items()}
    todo = sorted(mem)
    while todo:
        v = todo.pop()
        for w in succ.get(v, ()):
            cur = mem.setdefault(w, set())
            if not mem[v] <= cur:
                cur |= mem[v]
                todo.append(w)
    return {v: frozenset(ms) for v, ms in mem.items() if ms}


def sccs(nodes: list, edges: dict) -> list[list]:
    """Strongly connected components (iterative Tarjan), each sorted, in a deterministic order."""
    index, low, on, stack, out = {}, {}, set(), [], []
    counter = [0]
    for root in sorted(nodes):
        if root in index:
            continue
        work = [(root, iter(sorted(edges.get(root, ()))))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on.add(root)
        while work:
            v, it = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter[0]
                    counter[0] += 1
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(sorted(edges.get(w, ())))))
                    advanced = True
                    break
                if w in on:
                    low[v] = min(low[v], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                out.append(sorted(comp))
    return sorted(out)


def register_graph(prog) -> dict[str, set]:
    """R3: a -> b for every write of register b (by one of b's writers) whose expression reads register a."""
    edges: dict[str, set] = {}
    for actor, reg, reads in prog.reads:
        if reg not in prog.registers or actor not in prog.writers.get(reg, ()):
            continue
        for a in reads:
            if a in prog.registers:
                edges.setdefault(a, set()).add(reg)
    return edges


def labels(prog, fams: dict[str, str | None], writer_labels: dict) -> dict[str, dict]:
    """register -> {"label", "writers", ("component")} for every written register of family Idx[k] or Cnt[k]."""
    regs = sorted(prog.registers)
    comps = sccs(regs, register_graph(prog))
    out = {}
    for comp in comps:
        byfam: dict[str, list] = {}
        for r in comp:
            f = fams.get(r)
            if f is not None and (f.startswith("Idx[") or f.startswith("Cnt[")):
                byfam.setdefault(f, []).append(r)
        for f, rs in sorted(byfam.items()):
            ws = sorted(set().union(*[prog.writers.get(r, set()) for r in rs]))
            label = G.writer_label(ws, writer_labels)
            if label is None:
                continue
            for r in rs:
                own = sorted(prog.writers.get(r, ()))
                entry = {"label": label, "writers": own}
                if len(rs) > 1:
                    entry["component"] = list(rs)
                out[r] = entry
    return out


def union_entries(model: str, var_members: dict[str, frozenset], keys: set, constraints: list[dict],
                  writes: list[tuple[str, str, str | None]], writers: dict[str, set]) -> list[dict]:
    """One entry per weakly connected group of variables carrying the same union (see the module docstring)."""
    unioned = {v: ms for v, ms in var_members.items() if len(ms) >= 2}
    adj: dict[str, set] = {v: set() for v in unioned}
    for a, b in flow_edges(constraints):
        if a in unioned and b in unioned and unioned[a] == unioned[b]:
            adj[a].add(b)
            adj[b].add(a)
    seen, groups = set(), []
    for v in sorted(unioned):
        if v in seen:
            continue
        comp, todo = [], [v]
        seen.add(v)
        while todo:
            x = todo.pop()
            comp.append(x)
            for y in sorted(adj[x]):
                if y not in seen:
                    seen.add(y)
                    todo.append(y)
        ks = sorted(x for x in comp if x in keys)
        if ks:
            groups.append((ks, unioned[v]))
    out = []
    for ks, ms in sorted(groups, key=lambda g: (g[0][0], sorted(g[1]))):
        kset = set(ks)
        wmap = {}
        for m in sorted(ms):
            wmap[m] = sorted({actor for actor, reg, var in writes
                              if reg in kset and var is not None and actor in writers.get(reg, ())
                              and m in var_members.get(var, ())})
        mlist = sorted(ms)
        out.append({"model": model, "vars": ks, "members": mlist, "sort": " + ".join(mlist), "writers": wmap})
    return out
