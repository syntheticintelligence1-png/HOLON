"""The refutation search of rule SYM's laws on the typed model's combined module (BUILD_PLAN I34; the contract is rule
J6 of the docstring of tests_m3/test_sym.py, "REFUTED", and J5's race classification).

The search is UNDO's prefix search (holon.undo.search: reachable prefixes breadth first, successful calls of an action
with argument variants), with the law's own claim (holon.gen.symsec sy_ok_<n>) evaluated at each candidate exactly as
Bend states it:

  tau        at a prefix state s, a successful call x of the law's action and d in the law's translations (one, an
             hour, a day, a week, 2^32): sy_ok_<n>(s, x, d) false
  pi         at s, a call x of the action (a successful one, and the same call by each member of the role) and an
             ordered pair (a, b) of distinct members of the role in s: sy_ok_<n>(s, x, a, b) false; the members tried
             are address(0), the callers of the trace and of x, and the role's register values the state holds
  omega      at s, successful calls x of a and y of b from s: sy_ok_<n>(s, x, y) false (both orders execute and
             differ on a sink-reaching key); a pair where both succeed from s and one order's second step fails is a
             race (J5: race_disabling), recorded with its witness and never a counterexample
  sentinel   at s, a successful call x of the action: sy_ok_<n>(s, x) false

A witness whose either run is a run the model cannot observe (an unanswered call or the loop fuel, holon.gen.symsec
LIMIT_CODES) is not one. Every witness is then offered to accept(w) (the caller's real-side check, holon.symd.run),
which may refuse it; the search goes on. Nothing here names a target.
"""
from __future__ import annotations

from ..gen.symsec import LIMIT_CODES
from ..sorts import search3 as S3
from ..undo import search as US

MASK = (1 << 256) - 1
TAU_D = (1, 3600, 86400, 604800, 1 << 32)


def W(n: int) -> dict:
    return {"$w": "0x" + format(int(n) & MASK, "064x")}


def _int(v) -> int:
    if isinstance(v, str):
        return int(v, 0)
    return int(v or 0)


class SymSearch(US.UndoSearch):
    """One milestone document's SYM search. fn: {law id: n} (the section's function index)."""

    def __init__(self, model_f, doc: dict, sorts: dict, budget: dict, fn: dict, log=None, accept=None,
                 deadline: float | None = None):
        super().__init__(model_f, doc, sorts, budget, log=log, accept=accept, deadline=deadline)
        self.fn = fn
        self.races: list = []

    def accepted(self, w: dict) -> bool:
        why = None if self.accept is None else self.accept(w)
        if why is None:
            return True
        self.refused += 1
        self.log(f"  the witness of {w['law']} ({w['subform']}) is refused by the real-side check: {why} "
                 f"({self.refused} refused)")
        return False

    # ---------------------------------------------------------- evaluations
    def ok(self, n: int, args: list, st: S3.Step) -> bool:
        self.tick()
        return self.o.pred(f"sy_ok_{n}", args, st)

    def hit(self, n: int, args: list, st: S3.Step) -> bool:
        return self.o.pred(f"sy_hit_{n}", args, st)

    def code_of(self, act, g, st: S3.Step) -> int:
        """The check code of one step (act: an encoded act or a $call giving one; g: a state $ref or $call)."""
        m = self.m
        u = m.fresh()
        self.o.settle({"fn": "ux_ostep", "args": lambda: [act() if callable(act) else act, g]}, st, save=u)
        c = int(m.mreq({"fn": "ux_uos_c", "args": [{"$ref": u}]})["out"])
        m.drop([u])
        return c

    def limited(self, codes: list) -> bool:
        return any(c in LIMIT_CODES for c in codes)

    def members(self, g: str, role: str, trace: list, extra: list) -> list[int]:
        """The members of the role in g among address(0), the trace's callers and extra, in that order."""
        cands = [0]
        for st in list(trace) + list(extra):
            c = _int(st.env.get("caller")) if isinstance(st, S3.Step) else _int(st)
            if c not in cands:
                cands.append(c)
        out = []
        for c in cands:
            if self.m.mreq({"fn": f"sy_mem_{role}", "args": [{"$ref": g}, W(c)]})["out"]:
                out.append(c)
        return out

    def with_caller(self, g: str, trace: list, st: S3.Step, caller: int) -> S3.Step | None:
        """st by another caller, if it still succeeds from g (its call answers settled again)."""
        c = S3.Step(st.action, dict(st.args), dict(st.env, caller=caller))
        c = US.fresh_step(c)
        self.tick()
        code, g1, _calls = self.m.run_step(g, c, save=False)
        return c if code == 0 else None

    # ---------------------------------------------------------- the four sub-forms at one prefix state
    def tau_at(self, e: dict, n: int, trace: list, g: str):
        a = e["basis"]["action"]
        for xs, g1 in self.x_candidates(g, trace, a):
            self.m.drop([g1])
            for d in TAU_D:
                args = lambda xs=xs, d=d: [{"$ref": g}, self.m.act(xs), W(d)]  # noqa: E731
                if not self.hit(n, args(), xs) or self.ok(n, args(), xs):
                    continue
                c1 = self.code_of(lambda xs=xs: self.m.act(xs), {"$ref": g}, xs)
                c2 = self.code_of(lambda xs=xs, d=d: {"$call": "sy_tau_x", "args": [self.m.act(xs), W(d)]},
                                  {"$call": "sy_tau_g", "args": [{"$ref": g}, W(d)]}, xs)
                if self.limited([c1, c2]):
                    continue
                w = {"law": e["law_id"], "subform": "tau", "prefix": list(trace), "x": xs, "d": d, "codes": [c1, c2]}
                if self.accepted(w):
                    return w
        return None

    def pi_at(self, e: dict, n: int, trace: list, g: str):
        b = e["basis"]
        a, role = b["action"], b["role"]
        for xs, g1 in self.x_candidates(g, trace, a):
            self.m.drop([g1])
            mem = self.members(g, role, trace, [xs])
            if len(mem) < 2:
                continue
            # the call as made, then by each member (a member's own call is what π moves)
            calls = [xs] + [c for c in (self.with_caller(g, trace, xs, mm) for mm in mem
                                        if mm != _int(xs.env.get("caller"))) if c is not None]
            for x in calls:
                for p in mem:
                    for q in mem:
                        if p == q:
                            continue
                        args = [{"$ref": g}, self.m.act(x), W(p), W(q)]
                        if self.ok(n, args, x):
                            continue
                        c1 = self.code_of(lambda x=x: self.m.act(x), {"$ref": g}, x)
                        try:
                            c2 = self.code_of(lambda x=x, p=p, q=q: {"$call": "sy_pi_x",
                                                                       "args": [self.m.act(x), W(p), W(q)]},
                                              {"$call": "sy_pi_g", "args": [{"$ref": g}, W(p), W(q)]}, x)
                        except RuntimeError:     # the π world looks up a call the original never made: unanswered
                            continue
                        if self.limited([c1, c2]):
                            continue
                        w = {"law": e["law_id"], "subform": "pi", "prefix": list(trace), "x": x, "a": p, "b": q,
                             "codes": [c1, c2]}
                        if self.accepted(w):
                            return w
        return None

    def omega_at(self, e: dict, n: int, trace: list, g: str):
        b = e["basis"]
        xs_ = self.x_candidates(g, trace, b["a"])
        ys_ = self.x_candidates(g, trace, b["b"])
        try:
            for xs, gx in xs_:
                for ys, gy in ys_:
                    args = [{"$ref": g}, self.m.act(xs), self.m.act(ys)]
                    if self.ok(n, args, xs):
                        if not self.hit(n, args, xs):
                            self.race(e, trace, g, xs, ys, gx, gy)
                        continue
                    w = {"law": e["law_id"], "subform": "omega", "prefix": list(trace), "x": xs, "y": ys}
                    if self.accepted(w):
                        return w
        finally:
            self.m.drop([h for _s, h in xs_] + [h for _s, h in ys_])
        return None

    def race(self, e: dict, trace: list, g: str, xs, ys, gx: str, gy: str) -> None:
        """Both succeed from g and one order's second step fails: race_disabling (J5), the first per law kept."""
        if any(r["law"] == e["law_id"] for r in self.races):
            return
        cy = self.code_of(lambda: self.m.act(ys), {"$ref": gx}, ys)     # y after x
        cx = self.code_of(lambda: self.m.act(xs), {"$ref": gy}, xs)     # x after y
        if self.limited([cx, cy]) or (cx == 0) == (cy == 0):
            return
        self.races.append({"law": e["law_id"], "a": e["basis"]["a"], "b": e["basis"]["b"], "prefix": list(trace),
                           "x": xs, "y": ys, "disabled": "y after x" if cy else "x after y",
                           "code": cy or cx})

    def sentinel_at(self, e: dict, n: int, trace: list, g: str):
        a = e["basis"]["action"]
        for xs, g1 in self.x_candidates(g, trace, a):
            self.m.drop([g1])
            args = [{"$ref": g}, self.m.act(xs)]
            if self.ok(n, args, xs):
                continue
            w = {"law": e["law_id"], "subform": "sentinel", "prefix": list(trace), "x": xs}
            if self.accepted(w):
                return w
        return None

    # ---------------------------------------------------------- one law
    def decide(self, e: dict) -> tuple[dict | None, str]:
        n = self.fn[e["law_id"]]
        sub = e["subform"]
        at = getattr(self, f"{sub}_at")
        entry = e["basis"].get("action") or e["basis"].get("a")
        return self.over_prefixes(entry, lambda trace, g: at(e, n, trace, g))

    def inhabitant(self, e: dict) -> tuple[dict | None, str]:
        """A reachable state and arguments where the law's premises hold (G11V): sy_hit_<n> true."""
        n = self.fn[e["law_id"]]
        sub = e["subform"]
        b = e["basis"]

        def at(trace, g):
            if sub == "omega":
                xs_ = self.x_candidates(g, trace, b["a"])
                ys_ = self.x_candidates(g, trace, b["b"])
                try:
                    for xs, _gx in xs_:
                        for ys, _gy in ys_:
                            if self.hit(n, [{"$ref": g}, self.m.act(xs), self.m.act(ys)], xs):
                                return {"law": e["law_id"], "subform": sub, "prefix": list(trace), "x": xs, "y": ys}
                finally:
                    self.m.drop([h for _s, h in xs_] + [h for _s, h in ys_])
                return None
            for xs, g1 in self.x_candidates(g, trace, b["action"]):
                self.m.drop([g1])
                if sub == "tau":
                    if self.hit(n, [{"$ref": g}, self.m.act(xs), W(1)], xs):
                        return {"law": e["law_id"], "subform": sub, "prefix": list(trace), "x": xs, "d": 1}
                elif sub == "pi":
                    mem = self.members(g, b["role"], trace, [xs])
                    for p in mem:
                        for q in mem:
                            if p != q and self.hit(n, [{"$ref": g}, self.m.act(xs), W(p), W(q)], xs):
                                return {"law": e["law_id"], "subform": sub, "prefix": list(trace), "x": xs, "a": p,
                                        "b": q}
                elif self.hit(n, [{"$ref": g}, self.m.act(xs)], xs):
                    return {"law": e["law_id"], "subform": sub, "prefix": list(trace), "x": xs}
            return None
        entry = b.get("action") or b.get("a")
        return self.over_prefixes(entry, at)
