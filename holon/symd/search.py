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


class Learned(S3.Hints):
    """The corpus's hints with the deployment's own answers first. The real-side check (holon.symd.run) learns every
    external call a real run of a refused witness made, with its step's clock, so the model's later candidates meet
    the calls as the deployment answers them. A learned call answers by exact calldata, else by selector when every
    learned call of it got one answer or the clock. An answer that equals its step's clock at every learned call is
    answered with the step's clock: one such call is enough here, where the corpus's hints need two different values,
    since a learned call comes from the deployment the witness must run on. The corpus's hints answer every other call.
    reset() forgets what was learned, so each law's search starts from the hints alone and no law's outcome depends on
    the laws decided before it in the same process."""

    def __init__(self, doc: dict | None):
        super().__init__(doc)
        self.reset()

    def reset(self) -> None:
        self.learned: list = []
        self.l_data: dict = {}
        self.l_sel: dict = {}

    def learn(self, calls: list) -> int:
        """Adds the calls ({to, data, ok, ret, timestamp}) not learned yet; returns how many were new."""
        n = 0
        for c in calls:
            c = {"to": "0x" + str(c["to"])[-40:].lower(), "data": str(c["data"]).lower(), "ok": bool(c["ok"]),
                 "ret": str(c["ret"]).lower(), "timestamp": int(c["timestamp"])}
            if c in self.learned:
                continue
            self.learned.append(c)
            self.l_data.setdefault(c["data"], []).append(c)
            self.l_sel.setdefault(c["data"][:10], []).append(c)
            n += 1
        return n

    @staticmethod
    def _clock(cs: list) -> bool:
        return bool(cs) and all(c["ok"] and len(c["ret"]) == 66 and int(c["ret"], 16) == c["timestamp"] for c in cs)

    def answer(self, to: str | None, data: str, ts: int):
        if to is not None:
            to = "0x" + to[-40:].lower()
        cs = self.l_data.get(data.lower()) or []
        if not cs:
            cs = self.l_sel.get(data[:10].lower()) or []
            if len({(c["ok"], c["ret"]) for c in cs}) != 1 and not self._clock(cs):
                cs = []
        if to is not None and cs:
            cs = [c for c in cs if c["to"] == to]
        if not cs:
            return super().answer(to, data, ts)
        if self._clock(cs):
            return {"to": to or cs[0]["to"], "data": data, "ok": True, "ret": "0x%064x" % int(ts)}
        n: dict = {}
        for c in cs:
            n[(c["ok"], c["ret"], c["to"])] = n.get((c["ok"], c["ret"], c["to"]), 0) + 1
        ok, ret, cto = sorted(n.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        return {"to": to or cto, "data": data, "ok": ok, "ret": ret}


class SymSearch(US.UndoSearch):
    """One milestone document's SYM search. fn: {law id: n} (the section's function index)."""

    def __init__(self, model_f, doc: dict, sorts: dict, budget: dict, fn: dict, log=None, accept=None,
                 deadline: float | None = None):
        super().__init__(model_f, doc, sorts, budget, log=log, accept=accept, deadline=deadline)
        self.fn = fn
        self.races: list = []
        base = self.ref.successors

        def successors(g, trace, entry, limit, *a, **k):
            """The refuter's successors, a step whose bytes arguments the model's hints answer generically replaced by
            its variant on byte strings the deployment's recorded calls carried, when that variant succeeds: only
            such a prefix can run on the deployment (every witness's prefix is replayed there)."""
            out = []
            for t2, g2 in base(g, trace, entry, limit, *a, **k):
                st = t2[-1]
                vs = self.byte_variants(g, trace, st.action, [st])
                if vs:
                    self.m.drop([g2] + [h for _c, h in vs[1:]])
                    out.append((list(t2[:-1]) + [vs[0][0]], vs[0][1]))
                else:
                    out.append((t2, g2))
            return out
        self.ref.successors = successors

    def accepted(self, w: dict) -> bool:
        why = None if self.accept is None else self.accept(w)
        if why is None:
            return True
        self.refused += 1
        self.log(f"  the witness of {w['law']} ({w['subform']}) is refused by the real-side check: {why} "
                 f"({self.refused} refused)")
        key = str(why).split(":", 2)[:2] if str(why).startswith("x:") else None
        last, n = self.streak
        self.streak = (key, n + 1 if (key is not None and key == last) else 1)
        if key is not None and self.streak[1] >= self.X_VARIANTS:
            raise US.Disagree("pair:" + key[1])
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

    def recorded_bytes(self) -> list[str]:
        """Byte strings the deployment's recorded calls carried as dynamic arguments (holon fragments --hints: the
        calls' calldata, each head word read as an offset to a length-prefixed byte string), at most eight."""
        if getattr(self, "_rb", None) is not None:
            return self._rb
        out: list = []
        for c in getattr(self.m.hints, "calls", None) or []:
            data = c.get("data") or "0x"
            d = bytes.fromhex(data[10:]) if len(data) > 10 else b""
            for i in range(0, min(len(d), 32 * 8), 32):
                o = int.from_bytes(d[i:i + 32], "big")
                if o < 32 or o % 32 or o + 32 > len(d):
                    continue
                k = int.from_bytes(d[o:o + 32], "big")
                if 0 < k <= 4096 and o + 32 + k <= len(d):
                    v = "0x" + d[o + 32:o + 32 + k].hex()
                    if v not in out:
                        out.append(v)
        self._rb = out[:8]
        return self._rb

    def byte_variants(self, g: str, trace: list, a: str, base: list) -> list:
        """Successful calls of a from g whose top-level bytes arguments take a byte string the deployment's recorded
        calls carried (the external answers the model's hints give are then the deployment's own), first."""
        act = next((x for x in self.doc.get("actions") or [] if x["name"] == a), {})
        ps = [p["name"] for p in act.get("params") or [] if p.get("type") == "bytes"]
        if not ps or not base:
            return []
        out, seen = [], set()
        for st in base[:2]:
            for p in ps:
                for v in self.recorded_bytes():
                    if st.args.get(p) == v:
                        continue
                    c = US.fresh_step(S3.Step(a, dict(st.args, **{p: v}), dict(st.env)))
                    self.tick()
                    code, g1, _calls = self.m.run_step(g, c, save=True)
                    if code != 0:
                        self.m.drop([g1])
                        continue
                    h = self.m.fingerprint(g1)
                    if h in seen:
                        self.m.drop([g1])
                        continue
                    seen.add(h)
                    out.append((c, g1))
        return out

    def cands_of(self, g: str, trace: list, a: str) -> list:
        """x_candidates, with the recorded-bytes variants of its first calls first."""
        xs = self.x_candidates(g, trace, a)
        return self.byte_variants(g, trace, a, [c for c, _h in xs]) + xs

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
        for xs, g1 in self.cands_of(g, trace, a):
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
        for xs, g1 in self.cands_of(g, trace, a):
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
        xs_ = self.cands_of(g, trace, b["a"])
        ys_ = self.cands_of(g, trace, b["b"])
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
        for xs, g1 in self.cands_of(g, trace, a):
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
        w, note = self.over_prefixes(entry, lambda trace, g: at(e, n, trace, g))
        return w, note.replace("because a pair step (", "because the act x (")

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
