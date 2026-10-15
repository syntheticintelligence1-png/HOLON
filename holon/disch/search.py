"""The refutation and witness search of the DISCH laws (BUILD_PLAN I31; the contract is the docstring of
tests_m3/test_disch.py, "Deciding"): I30's stages over the compiled typed model (holon.sorts.search3), from R0, with
the sidecar's budget.

  S1  the law's last step (S3.Synth's coordinate moves) from a state where B holds at a time t
  S2  breadth-first prefixes of at most prefix_depth successful steps (at most max_prefixes distinct states), the
      actions that write what B reads first; every state is a candidate prefix
  S3  I30's neighbourhood search (holon.sorts.search3's S3, the same machinery): for a law S1+S2 left without a
      candidate, the witnesses of the other entry points (every other DISCH law of the same model with an S1+S2
      candidate, law id order: a law's entry points are its actions, and a witness of another law is a trace to a
      state of the same model), each with its last step dropped; at every position, the end first, the prefix itself,
      then one to neighbourhood_insertion_length_max successful steps inserted (successors as in S2) and the rest of
      the prefix run again after them (the clock never decreasing); the law's last step from every such prefix where
      B holds, until neighbourhood_prefixes_per_entry_point_max prefixes (every entry point is tried at each prefix,
      so each has that many). A witness's neighbourhood is generated once per model, in the same order, and shared by
      every law that searches it (Explorer.neighbour); holon run's --deadline ends the stage early, and a law it
      leaves undecided is UNKNOWN by the time box, so recorded in its bound

One exploration serves every law of a model (the prefixes are law-independent: the same distinct states in the same
order, the actions that write what any blocked condition reads first), and each law tries its last step from the
states, in that order, where its B holds:

  t candidates   E - 1, E and E + 1 for every term E an atom of B compares with block.timestamp, evaluated on the
                 state (holon.extracted_eval), and the trace's own times; t is at least the prefix's last timestamp
  the last step  blocking: an action of x_closure_X|B with X's permission, after which B is false at its time (a
                 refutation); revert: an action excluded under B that succeeds (a refutation); external and
                 external_none: an action of Y's closure with Y's permission after which c holds (a witness, or a
                 refutation of the negation); its block.timestamp is at least t
  inhabitant     a PROVED law's premises: a reachable state where B holds at t and an action of the law's set whose
                 permission holds in an environment (G11V)

B and c are evaluated on the model's state with the I20 evaluator (holon.extracted_eval: the real keccak256 slots of
the state) to rank candidates only; Bend decides every witness (holon.disch.run). Nothing here names a target.
"""
from __future__ import annotations

import json

from .. import extracted_eval as EV
from ..sorts import search3 as S3


def _time_terms(t, out: list) -> None:
    """The terms an atom compares with block.timestamp (either side of a comparison, or of a checked difference)."""
    if not isinstance(t, list) or not t:
        return
    h = t[0]
    tt = ["env", "block.timestamp"]
    sides = None
    if h in ("==", "!=", "<", "<=", ">", ">=") and len(t) == 3:
        sides = (t[1], t[2])
    elif h == "fits" and len(t) == 3 and isinstance(t[2], list) and len(t[2]) == 3 and t[2][0] in ("-", "+"):
        sides = (t[2][1], t[2][2])
    if sides is not None:
        a, b = sides
        if b == tt and a != tt:
            out.append(a)
        if a == tt and b != tt:
            out.append(b)
    for x in t[1:]:
        _time_terms(x, out)


def _families(t, out: set) -> None:
    if isinstance(t, list):
        if len(t) == 2 and t[0] == "storage" and isinstance(t[1], str):
            out.add(t[1])
        for x in t:
            _families(x, out)


def _keyed_reads(t, out: list) -> None:
    """(family, leaf) of every read of a mapping keyed directly by an input leaf (["map", ["storage", F], leaf])."""
    if not isinstance(t, list) or not t:
        return
    if t[0] == "map" and len(t) == 3 and isinstance(t[1], list) and len(t[1]) == 2 and t[1][0] == "storage":
        k = t[2]
        if k == ["caller"]:
            out.append((t[1][1], ("env", "caller")))
        elif isinstance(k, list) and len(k) == 2 and k[0] == "param" and isinstance(k[1], str):
            out.append((t[1][1], ("param", k[1])))
    for x in t[1:]:
        _keyed_reads(x, out)


class DSynth(S3.Synth):
    """I30's S1 (holon.sorts.search3.Synth) with one more directed candidate: for a failing check that reads a mapping
    keyed by an input leaf (the caller, a parameter), the keys the hash tables hold for that mapping (the preimages
    key . slot of its slot), so that a step can be taken by an account a mapping already enrolls."""

    def directed(self, a: str, code: int, st, state: dict) -> dict:
        out = super().directed(a, code, st, state)
        checks = self.m.doc.program(a).checks()
        if not (0 < code <= len(checks)):
            return out
        reads: list = []
        _keyed_reads(checks[code - 1].expr, reads)
        for fam, leaf in reads:
            try:
                slot = int(self.m.doc.family(fam).slot)
            except Exception:  # noqa: BLE001
                continue
            for k in sorted(self.m.kh):
                b = bytes.fromhex(k[2:])
                if len(b) == 64 and int.from_bytes(b[32:], "big") == slot:
                    key = int.from_bytes(b[:32], "big")
                    vals = out.setdefault(self._dkey(leaf), [])
                    if key not in vals:
                        vals.append(key)
        return out


class Explorer(S3.Refuter):
    """The shared S2 exploration of one model: distinct reachable states (storage, ghost store, clock) breadth first,
    each with its trace."""

    def __init__(self, model, doc: dict, sorts: dict, budget: dict, an: dict, log=None):
        super().__init__(model, doc, sorts, budget, log=log)
        self.an = an
        reads: set = set()
        for b in an["basis"]:
            _families(b["blocked"], reads)
        self.order = self._order(reads)
        self.states: list = []          # [(trace, g)] in BFS order, the deployment first
        self.done = False
        self.tried = 0
        self._level = None
        self._seen = None
        self._d = 0

    def _order(self, reads: set) -> list:
        rows = []
        for a in self.doc.get("actions") or []:
            ws = {w.get("family") for w in a.get("writes") or []}
            if not ws:
                continue
            rows.append((-len(ws & reads), a["name"]))
        return [n for _k, n in sorted(rows)]

    def successors_b(self, g: str, trace: list, limit: int) -> list:
        """Successful steps from g (a few per action, distinct post-states), the actions that write what a blocked
        condition reads first (holon.sorts.search3.Refuter.successors with that order)."""
        saved, saved_synth = S3.relevance, S3.Synth
        try:
            S3.relevance = lambda doc, entry, _o=self.order: list(_o)
            S3.Synth = DSynth
            return self.successors(g, trace, "", limit)
        finally:
            S3.relevance, S3.Synth = saved, saved_synth

    def state_at(self, k: int):
        """The k-th explored state (exploring further as needed), or None past the budget."""
        depth = int(self.budget.get("prefix_depth", 2))
        maxp = int(self.budget.get("max_prefixes", 1000))
        while k >= len(self.states) and not self.done:
            if self._level is None:
                g0 = self.m.s0()
                self.states.append(([], g0))
                self._seen = {(self.m.fingerprint(g0), self.ts0)}
                self._level = [([], g0)]
                self._next = []
                self._i = 0
                self._d = 1
                self.tried = 1
                continue
            if self._d > depth or self.tried >= maxp:
                self.done = True
                break
            if self._i >= len(self._level):
                self.log(f"  explore: depth {self._d}: {self.tried} distinct states")
                self._level, self._next, self._i = self._next, [], 0
                self._d += 1
                if not self._level:
                    self.done = True
                continue
            trace, g = self._level[self._i]
            self._i += 1
            for t2, g2 in self.successors_b(g, trace, maxp - self.tried):
                key = (self.fp.get(g2) or self.m.fingerprint(g2), int(t2[-1].env.get("block.timestamp") or 0))
                if key in self._seen:
                    continue
                self._seen.add(key)
                self.tried += 1
                self.states.append((t2, g2))
                self._next.append((t2, g2))
                if self.tried >= maxp:
                    break
        return self.states[k] if k < len(self.states) else None

    def _neighbourhood(self, steps: list, limit: int):
        """I30's S3 neighbourhood of one witness (holon.sorts.search3.Refuter.refute's S3 loop): its last step dropped;
        at every position, the end first, the prefix itself, then one to neighbourhood_insertion_length_max successful
        steps inserted and the rest of the prefix run again after them. Yields (trace, g), at most limit."""
        ins = int(self.budget.get("neighbourhood_insertion_length_max", 2))
        base = list(steps[:-1])
        hs = [self.m.s0()]
        for st in base:
            code, g, _c = self.m.run_step(hs[-1], st, save=True)
            if code != 0:
                return
            hs.append(g)
        n = 0
        for p in range(len(base), -1, -1):
            if p == len(base):
                n += 1
                yield base, hs[-1]
                if n >= limit:
                    return
            level = [(base[:p], hs[p])]
            for _k in range(ins):
                nxt = []
                for trace, gg in level:
                    for t2, g2 in self.successors_b(gg, trace, limit - n):
                        nxt.append((t2, g2))
                        full, g3 = self._tail(g2, t2, base[p:])
                        if full is None:
                            continue
                        n += 1
                        yield full, g3
                        if n >= limit:
                            return
                level = nxt

    def neighbour(self, name: str, steps: list, k: int, limit: int):
        """The k-th prefix of the neighbourhood of the witness `name` (generated once per model and shared by every
        law, in the same order), or None past its end or the limit."""
        if not hasattr(self, "_nbh"):
            self._nbh = {}
        if name not in self._nbh:
            self._nbh[name] = ([], self._neighbourhood(steps, limit))
        items, it = self._nbh[name]
        while k >= len(items) and it is not None:
            try:
                items.append(next(it))
            except StopIteration:
                self._nbh[name] = (items, None)
                it = None
        return items[k] if k < len(items) and k < limit else None

    def bound(self) -> str:
        depth = int(self.budget.get("prefix_depth", 2))
        maxp = int(self.budget.get("max_prefixes", 1000))
        return (f"S1+S2: {len(self.states)} distinct states of at most {depth} successful steps (max {maxp})"
                f"{'' if self.done else ' (exploration not finished)'}; S3: no other entry point's witness")


class LawSearch:
    """One law's last-step search over the shared exploration. B, c and the law's claim are evaluated by a judge on the
    compiled model and its DISCH section (holon.disch.run.Judge: Bend's own functions, the real hash of every key they
    look up); the time candidates are computed with the I20 evaluator (holon.extracted_eval), candidates only."""

    def __init__(self, ex: Explorer, an: dict, law: dict, entries: list, judge, log=None):
        self.ex = ex
        self.m = ex.m
        self.an = an
        self.law = law
        self.judge = judge
        self.b = next(x for x in an["basis"] if x["tag"] == law["tag"])
        self.B = self.b["blocked"]
        self.c = self.b["check_expr"]
        self.scope = self.b["check"].split("#")[0]
        self.entries = list(entries)
        self.log = log or (lambda s: None)
        tt: list = []
        _time_terms(self.B, tt)
        self.tterms = tt
        self.tries = 0
        self.bstates = 0
        self.seen_states = 0
        self.capped = False
        self.validate = None            # (trace, step, t) -> bool: holon.disch.run.Run.valid
        self.deadline = None            # a wall-clock time box on this law's last-step syntheses (holon run)
        self.timeboxed = False          # the time box ended the search before its budget (UNKNOWN by the time box)

    # ------------------------------------------------------------------ time candidates
    def times(self, state: dict, trace: list) -> list:
        if not getattr(self.judge, "clock", True):
            return [0]                  # a model without block.timestamp: time(e) is 0, so t is 0
        last =int(trace[-1].env.get("block.timestamp") or 0) if trace else int(self.ex.ts0)
        cands = {last}
        for st in trace:
            cands.add(int(st.env.get("block.timestamp") or 0))
        for term in self.tterms:
            try:
                e = EV.Eval(self.m.doc, state, self.scope, {}, {"block.timestamp": last})
                v = e.as_int(e.ev(term))
            except Exception:  # noqa: BLE001: a term the evaluator cannot compute gives no candidate
                continue
            cands |= {v - 1, v, v + 1}
        return sorted(t for t in cands if t >= last and t > 0 and t < (1 << 64))

    def b_time(self, g: str, trace: list):
        """The first time candidate at which B holds in g (Bend's blk_<tag>), else None."""
        state = self.m.state(g)
        for t in self.times(state, trace):
            if self.judge.blocked(self.m, self.law["tag"], g, t):
                return t
        return None

    # ------------------------------------------------------------------ the search
    def candidates(self):
        """(trace, g, t) of every explored state where B holds, in the exploration's order (S1+S2)."""
        k = 0
        while True:
            s = self.ex.state_at(k)
            if s is None:
                return
            k += 1
            trace, g = s
            self.seen_states += 1
            t = self.b_time(g, trace)
            if t is None:
                continue
            self.bstates += 1
            yield trace, g, t

    def synth(self, g: str, trace: list, t: int, action: str, accept):
        prev = S3.Step(trace[-1].action if trace else action, {}, {"block.timestamp": t})
        _state, pools = self.ex.pools(g, trace)
        sy = DSynth(self.m, pools, self.ex.entry_evals)
        st, code = sy.synth(g, action, prev, self.ex.ts0, accept=accept)
        return st

    def out_of_time(self) -> bool:
        import time as _time
        if self.deadline is not None and _time.time() > self.deadline:
            self.timeboxed = True
            return True
        return False

    def refute(self, _s3: bool = False, max_states: int | None = None):
        """(witness steps, t) or None: the law's last step from a state where B holds, accepted when the judge finds
        the law's claim false there (a forall law) or true (an external law). At most max_states B-states are tried
        (None: every one)."""
        n = 0
        for trace, g, t in self.candidates():
            if max_states is not None and n >= max_states:
                self.capped = True
                return None
            n += 1
            for a in self.entries:
                if self.out_of_time():
                    return None
                self.tries += 1

                def acc(st, code, g=g, t=t, trace=trace):
                    if code != 0 or int(st.env.get("block.timestamp") or 0) < t:
                        return False
                    if not self.judge.decides(self.m, self.law, g, st, t):
                        return False
                    # with a binding: the step still decides the law with the deployment's external answers
                    return self.validate is None or self.validate(trace, st, t)
                st = self.synth(g, trace, t, a, acc)
                if st is not None:
                    self.log(f"  {self.law['law_id']}: a candidate at depth {len(trace)} ({a})")
                    return trace + [st], t
        return None

    def inhabit(self, max_states: int | None = None):
        """(trace + [a step], t) of the premises: a state where B holds at t and a step of an action of the law's set
        for which the judge finds the premise true."""
        n = 0
        for trace, g, t in self.candidates():
            if max_states is not None and n >= max_states:
                return None
            n += 1
            for a in self.entries:
                if self.out_of_time():
                    return None
                self.tries += 1

                def acc(st, code, g=g, t=t):
                    return int(st.env.get("block.timestamp") or 0) >= t and \
                        self.judge.premise(self.m, self.law, g, st, t)
                st = self.synth(g, trace, t, a, acc)
                if st is not None:
                    return trace + [st], t
        return None

    def neighbourhood(self, seeds: list, deadline: float | None = None):
        """S3 (I30's neighbourhood): (witness steps, t) or None. seeds: [(name, steps)] of the other entry points'
        witnesses. Every prefix tried is counted against neighbourhood_prefixes_per_entry_point_max; deadline (a
        wall-clock time) ends the stage early, recorded in the bound as a time box (never as an exhausted budget)."""
        import time as _time
        ins = int(self.ex.budget.get("neighbourhood_insertion_length_max", 2))
        maxn = int(self.ex.budget.get("neighbourhood_prefixes_per_entry_point_max", 1000))
        self.s3 = {"seeds": [n for n, _s in seeds], "prefixes": 0, "max": maxn, "insert": ins, "timebox": False}
        m = self.m
        g0 = m.s0()

        def out_of_time():
            if deadline is not None and _time.time() > deadline:
                self.s3["timebox"] = True
                return True
            return False

        def try_prefix(trace, g):
            """The law's last step from one neighbourhood prefix; a candidate or None."""
            self.s3["prefixes"] += 1
            self.seen_states += 1
            t = self.b_time(g, trace)
            if t is None:
                return None
            self.bstates += 1
            for a in self.entries:
                self.tries += 1

                def acc(st, code, g=g, t=t, trace=trace):
                    if code != 0 or int(st.env.get("block.timestamp") or 0) < t:
                        return False
                    if not self.judge.decides(self.m, self.law, g, st, t):
                        return False
                    return self.validate is None or self.validate(trace, st, t)
                st = self.synth(g, trace, t, a, acc)
                if st is not None:
                    self.log(f"  {self.law['law_id']}: an S3 candidate after {self.s3['prefixes']} neighbourhood "
                             f"prefixes ({a})")
                    return trace + [st], t
            return None

        for name, steps in seeds:
            k = 0
            while True:
                if self.s3["prefixes"] >= maxn or out_of_time():
                    return None
                item = self.ex.neighbour(name, steps, k, maxn)
                if item is None:
                    break
                k += 1
                r = try_prefix(*item)
                if r is not None:
                    return r
        return None

    def bound(self) -> str:
        n3 = getattr(self, "s3", None)
        if n3 is None:
            s3 = "; S3: not run"
        elif not n3["seeds"]:
            s3 = "; S3: no other entry point's witness (no neighbourhood to search)"
        else:
            s3 = (f"; S3: {n3['prefixes']} neighbourhood prefixes of the witnesses of {', '.join(n3['seeds'])} (one to "
                  f"{n3['insert']} successful steps inserted at every position; max {n3['max']} per entry point)")
            if n3["timebox"]:
                s3 += " (stopped by the run's time box before the budget: UNKNOWN by the time box)"
            elif n3["prefixes"] >= n3["max"]:
                s3 += " (budget exhausted)"
        cap = " (the last-step cap was reached)" if self.capped else ""
        if self.timeboxed:
            cap += (" (S1+S2 stopped by the run's per-law time box before its budget: UNKNOWN by the time box, not an "
                    "exhausted budget)")
        return (f"{self.ex.bound().split('; S3')[0]}{s3}; B held at a candidate time in {self.bstates} of "
                f"{self.seen_states} states; {self.tries} last-step syntheses{cap} "
                f"({', '.join(self.entries) or 'no entry point'})")


def step_key(st) -> str:
    return json.dumps([st.action, st.args, st.env], sort_keys=True, default=str)
