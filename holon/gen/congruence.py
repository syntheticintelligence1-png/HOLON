"""The congruence proof class (whitepaper Lemma 6.2: valid equations are closed under symmetry, transitivity and
whiskering, so checking a generating set establishes the congruence it generates; BUILD_PLAN I42).

Given equations between paths that start at one vertex, each with a Bend proof at a fixed starting value, this module
emits the Bend proof of an equation derived from them by prefix rewriting: a derivation is a list of rewrites, each
replacing a prefix lhs of the current path by rhs (direction "lr") or rhs by lhs ("rl"), so every step is one available
equation whiskered on the right by the path's remaining suffix. The emitted term chains the steps with Equal.trans,
flips a step with Equal.sym, and whiskers it with Equal.cong over `y => run(suffix, y)`; the middle terms are written
as `run(path, start)`, which the checker reduces on concrete paths. Nothing here is trusted: the kernel checks the
emitted term (AGENTS rule 6).

The module names no target: paths are lists of edge ids, and the caller names the instance's run, start, carrier type
and the defs that prove each available equation (holon.gen.basis).

Placement (I42 gap T-G5): this class is not in holon/gen/mproofs.py, which is a root of the holon-ir/0.2 and 0.3
generator closures (holon.records.GENERATORS); a change there changes generator_sha256 in every M1-M3 record.
"""
from __future__ import annotations

from collections import deque

MAX_STEPS = 6


def derivation(start: list[int], goal: list[int], available: list[dict], max_steps: int = MAX_STEPS) -> list | None:
    """A shortest derivation of `goal` from `start` by prefix rewriting with the available equations ({"lhs", "rhs"},
    paths as edge-id lists), as [[equation index, "lr" | "rl"], ...]; [] when start == goal; None when none exists within
    max_steps. Breadth-first over paths, equations in list order, "lr" before "rl"; deterministic."""
    s, g = tuple(start), tuple(goal)
    if s == g:
        return []
    seen = {s: []}
    q = deque([s])
    while q:
        x = q.popleft()
        if len(seen[x]) >= max_steps:
            continue
        for i, a in enumerate(available):
            for d, (frm, to) in (("lr", (a["lhs"], a["rhs"])), ("rl", (a["rhs"], a["lhs"]))):
                frm, to = tuple(frm), tuple(to)
                if x[:len(frm)] == frm:
                    y = to + x[len(frm):]
                    if y not in seen:
                        seen[y] = seen[x] + [[i, d]]
                        if y == g:
                            return seen[y]
                        q.append(y)
    return None


def path_term(path, run: str, start: str, step: str) -> str:
    """`run([step(e0), step(e1), ...], start)`: the value a path from the start vertex carries the start value to."""
    return f"{run}([{', '.join(step.format(e) for e in path)}], {start})"


def chain(start: list[int], steps: list, available: list[dict], *, car: str, run: str, start_term: str, step: str,
          proof_of: list[str]) -> str:
    """The Bend term proving {run(start, s0) == run(end, s0) : car}, end the path the derivation reaches.

    proof_of[i] is a term of type {run(lhs_i, s0) == run(rhs_i, s0) : car}. Each step rewrites the current path
    prefix-first; its proof is Equal.cong(car, car, y => run(suffix, y), run(frm, s0), run(to, s0), p), where p is
    proof_of[i] for "lr" and its Equal.sym for "rl"; the steps are chained left to right with Equal.trans."""
    if not steps:
        return "{==}"
    cur = tuple(start)
    links = []   # (from term, to term, proof)
    for i, d in steps:
        a = available[i]
        frm, to = (tuple(a["lhs"]), tuple(a["rhs"])) if d == "lr" else (tuple(a["rhs"]), tuple(a["lhs"]))
        if cur[:len(frm)] != frm:
            raise ValueError(f"step {i} {d} does not apply to path {list(cur)}")
        suffix = list(cur[len(frm):])
        nxt = to + cur[len(frm):]
        f_t, t_t = path_term(frm, run, start_term, step), path_term(to, run, start_term, step)
        base = proof_of[i] if d == "lr" else f"Equal.sym({car}, {t_t}, {f_t}, {proof_of[i]})"
        if suffix:
            sfx = "[" + ", ".join(step.format(e) for e in suffix) + "]"
            prf = f"Equal.cong({car}, {car}, y => {run}({sfx}, y), {f_t}, {t_t}, {base})"
        else:
            prf = base
        links.append((path_term(cur, run, start_term, step), path_term(nxt, run, start_term, step), prf))
        cur = nxt
    term = links[-1][2]
    end = links[-1][1]
    for frm_t, to_t, prf in reversed(links[:-1]):
        term = f"Equal.trans({car}, {frm_t}, {to_t}, {end}, {prf}, {term})"
    return term
