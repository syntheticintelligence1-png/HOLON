"""Minimal unsatisfiable cores (whitepaper §7.7 step 4; BUILD_PLAN I13).

`minimal_core(items, satisfiable)` returns a sublist of `items` (same objects, original order, no repeats)
that is unsatisfiable under the oracle and irreducible: removing any one element makes it satisfiable.

It runs QuickXplain (Junker 2004): split the candidates in halves, explain the second half against the first,
then the first against what the second contributed. With a monotone oracle (a superset of an unsatisfiable
set is unsatisfiable, which holds for holon.sorts.solve.satisfiable: adding a constraint only adds
equations) the result is a minimal core. A final deletion pass re-checks irreducibility element by element
and drops any element whose removal keeps the core unsatisfiable, so the result is irreducible under any
deterministic oracle. Items are handled by position, so they need not be hashable; the result depends only
on the items' order and the oracle.
"""
from __future__ import annotations

from typing import Callable


def minimal_core(items: list, satisfiable: Callable[[list], bool]) -> list:
    items = list(items)
    if not items:
        if satisfiable([]):
            raise ValueError("minimal_core: the items are satisfiable, so they have no unsatisfiable core")
        return []

    def sat(ix) -> bool:
        return bool(satisfiable([items[i] for i in sorted(ix)]))

    if sat(range(len(items))):
        raise ValueError("minimal_core: the items are satisfiable, so they have no unsatisfiable core")

    def qx(background: list[int], changed: bool, cand: list[int]) -> list[int]:
        if changed and not sat(background):
            return []
        if len(cand) == 1:
            return list(cand)
        k = len(cand) // 2
        c1, c2 = cand[:k], cand[k:]
        d2 = qx(background + c1, bool(c1), c2)
        d1 = qx(background + d2, bool(d2), c1)
        return d1 + d2

    core = sorted(set(qx([], False, list(range(len(items))))))
    # deletion pass: every element must be needed
    i = 0
    while i < len(core):
        rest = core[:i] + core[i + 1:]
        if not sat(rest):
            core = rest
        else:
            i += 1
    return [items[i] for i in core]
