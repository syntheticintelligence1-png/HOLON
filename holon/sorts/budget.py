"""I110 (a): the per-document sort budget, a deterministic work meter (never wall-clock).

A typed-sorts sidecar may name "sort_budget": a positive integer, the most work units the sort pass may spend on one
document. A work unit is one step of the pass's own loops, counted where the work is done:
  * one node of a term the walk visits (holon.sorts.extracted.Walker._ex, holon.sorts.flow);
  * one row of an affine table a propagation sweep reads (holon.sorts.solve._propagate);
  * one node of the torsor-role search (holon.sorts.solve._search);
  * one call of the minimal-core oracle (holon.sorts.core.minimal_core) and one sweep of a conflict search;
  * one candidate of a site or union search (holon.sorts.extracted.build_sites, holon.sorts.unions).
The count is a function of the document and the code alone, so the pass's outputs stay byte-identical across runs
and machines (AGENTS.md rule 7). A sidecar without the key meters nothing: tick() is a no-op and every output is
exactly as before.

A document whose count exceeds the budget is a recorded miss (holon.sorts.assign.run_pass): the pass writes it in
gen/<M>/sorts/budget.json with its count and status "over_budget", gives every variable of its model the unrefined
sort ("Nat (unrefined)", why "sort budget exceeded"), and writes no conflict, site or union of it. Downstream its terms
are opaque: no sort refines them, so a law over them can only be weaker (or UNKNOWN), never stronger.
"""
from __future__ import annotations


class OverBudget(Exception):
    """The current document spent more than its budget."""

    def __init__(self, used: int, limit: int):
        super().__init__(f"sort budget exceeded: more than {limit} work units")
        self.used, self.limit = used, limit


class Meter:
    def __init__(self, limit: int | None):
        self.limit = limit
        self.used = 0


_CURRENT: Meter | None = None


def start(limit: int | None) -> Meter:
    """Meter the work from here on (limit None: count only, never refuse)."""
    global _CURRENT
    _CURRENT = Meter(limit)
    return _CURRENT


def resume(m: Meter | None) -> None:
    global _CURRENT
    _CURRENT = m


def stop() -> None:
    global _CURRENT
    _CURRENT = None


def tick(n: int = 1) -> None:
    m = _CURRENT
    if m is None:
        return
    m.used += n
    if m.limit is not None and m.used > m.limit:
        raise OverBudget(m.used, m.limit)


def parse(value) -> int | None:
    """The sidecar's sort_budget: absent (None) or a positive integer."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"sort_budget is {value!r}, not a positive integer")
    return value
