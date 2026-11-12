"""Explicit-state breadth-first exploration of small abstract transition systems.

A layer model provides:
  ASSUMPTIONS : tuple[str, ...]            boolean knobs; a knob in the set A means the assumption is ENFORCED
  init(A)     -> state                      hashable state
  succ(s, A)  -> iterable[(label, state)]   enabled transitions (a revert is simply an absent transition)
  INVARIANTS  : dict[name, Inv]
An Inv is either a state predicate (kind="state": f(s, A) -> bool) or a transition predicate
(kind="step": f(s, label, t, A) -> bool).

bfs() returns the shortest violating trace (BFS order, actions sorted by label, so results are deterministic),
or None after exhausting the reachable state space (optionally depth-bounded).
"""

from collections import deque
from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class Inv:
    kind: str  # "state" | "step"
    fn: object
    text: str


@dataclass
class Outcome:
    holds: bool
    trace: list  # [(state, label, next_state), ...] for a violation
    explored: int
    exhaustive: bool


_EXPLORED = {}


def explore(model, A, max_depth=None, max_states=4_000_000):
    """Breadth-first reachable set of `model` under enforced assumptions A (cached per (model, A, depth)).

    Returns (order, parent, edges, truncated): `order` lists states in BFS discovery order (non-decreasing depth),
    `edges[s]` the sorted outgoing transitions of s."""
    key = (model.NAME, A, max_depth)
    if key in _EXPLORED:
        return _EXPLORED[key]
    s0 = model.init(A)
    parent = {s0: None}
    depth = {s0: 0}
    order = [s0]
    edges = {}
    truncated = False
    i = 0
    while i < len(order):
        s = order[i]
        i += 1
        succ = sorted(model.succ(s, A), key=lambda lt: (lt[0], repr(lt[1])))
        if max_depth is not None and depth[s] >= max_depth:
            edges[s] = []
            truncated = truncated or bool(succ)
            continue
        edges[s] = succ
        for label, t in succ:
            if t not in parent:
                parent[t] = (s, label)
                depth[t] = depth[s] + 1
                order.append(t)
                if len(order) > max_states:
                    raise RuntimeError(f"state budget exceeded in {model.NAME}")
    res = (order, parent, edges, truncated)
    _EXPLORED[key] = res
    return res


def bfs(model, A, inv_name, max_depth=None):
    """Shortest violation of one invariant (state or step), using the cached BFS exploration."""
    inv = model.INVARIANTS[inv_name]
    order, parent, edges, truncated = explore(model, A, max_depth)
    if inv.kind == "state":
        for s in order:  # BFS order => first violating state has minimal depth
            if not inv.fn(s, A):
                return Outcome(False, _reconstruct(parent, s), len(order), True)
    else:
        for s in order:  # first source (in BFS order) with a violating outgoing step => minimal trace
            for label, t in edges[s]:
                if not inv.fn(s, label, t, A):
                    tr = _reconstruct(parent, s)
                    tr.append((s, label, t))
                    return Outcome(False, tr, len(order), True)
    return Outcome(True, [], len(order), not truncated)


def _reconstruct(parent, s):
    steps = []
    while parent[s] is not None:
        p, label = parent[s]
        steps.append((p, label, s))
        s = p
    steps.reverse()
    return steps


def assumption_lattice(model, inv_name, max_depth=None):
    if max_depth is None:
        max_depth = getattr(model, "MAX_DEPTH", None)
    """Minimal enforced-assumption sets under which inv holds, plus one counterexample per relaxation.

    Relaxation of assumption a (a member of some minimal set M): drop a from the FULL set if that already yields a
    counterexample; otherwise drop it from M (guaranteed to fail by minimality)."""
    names = tuple(model.ASSUMPTIONS)
    full = frozenset(names)
    cache = {}

    def check(A):
        if A not in cache:
            cache[A] = bfs(model, A, inv_name, max_depth)
        return cache[A]

    minimal = []
    for k in range(len(names) + 1):
        for combo in combinations(names, k):
            A = frozenset(combo)
            if any(m <= A for m in minimal):
                continue
            if check(A).holds:
                minimal.append(A)
    relaxations = {}
    for m in minimal:
        for a in sorted(m):
            if a in relaxations:
                continue
            out = check(full - {a})
            base = "ALL"
            if out.holds:
                out = check(m - {a})
                base = "MINIMAL"
            relaxations[a] = (base, out)
    unconditional_cex = None if minimal else check(full)
    return {
        "full": check(full),
        "minimal": [sorted(m) for m in minimal],
        "relaxations": relaxations,
        "unconditional_cex": unconditional_cex,
    }
