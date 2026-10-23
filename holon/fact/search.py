"""Refutation of the FACT laws on the typed model (BUILD_PLAN I26; the contract is the docstring of tests_m3/test_fact.py,
"Deciding": the search).

The search runs on the combined module of holon.fact.section (the typed model and the FACT section, executed by the
evaluator), with I30's machinery (holon.sorts.search3: state handles, S1's step synthesis, the real hash tables of the
keys a candidate looks up, the external-call hints) and I27's prefix walk (holon.undo.search.UndoSearch). The FACT
sidecar's budget bounds it; the law's own Bend function decides every candidate (fact_<x> false at it).

  kernel (K1)    prefixes shared by both runs, breadth first up to prefix_depth steps, at most max_prefixes states; x1 a
                 succeeding candidate step of the action (S1's step, then its single-leaf variants); x2 each
                 single-component variant of x1 (one argument, the caller, msg.value, block.timestamp or the blob-hash
                 list) that succeeds; the first pair at which fact_<x> is false (equal commitments, different
                 consumers). Runs with different prefixes are not searched.
  attribution    prefixes breadth first up to prefix_depth steps; y a candidate step of w taking the pin (S1's step and
                 its single-leaf variants whose pre-context takes the pin's copy branch, fx_pin_<x>, evaluated before
                 the step runs; only such a step is a candidate, counted and run) that succeeds; the first (prefix, y)
                 at which fact_<x> is false and which the real side accepts. Then t: the first sequence of at most
                 continuation_depth successful steps after y whose last step makes the consumer's external call with
                 A[k].m (the calls the model's step looks up) and which the real side accepts after (prefix, y), []
                 when none within that bound. Shortest first, each length depth first; the steps before the last in
                 rounds over the actions (each action's i-th candidate in turn), so a refused or fruitless action
                 never holds up the others' S1 steps.
  inhabitants    for a PROVED kernel law: the first prefix and succeeding step x of the action with fhit_<x>(s, x, s, x)
                 true (G11V).

Candidate values are I30's (S1's value sets), and for the blob-hash list also every list of the law's measure domain
(F9: the admissible lists, which x2's variants of the consumer range over). No value is taken from the deployment's
recorded calls (Q23: an oracle's acceptance is learned by replay, never offered by hand). A first run the deployment
refuses ends K1's second runs for it. The order is deterministic; the search is not a proof of absence. Nothing
here names a target.
"""
from __future__ import annotations

import itertools
import json
import time

from ..machine_bend import bname
from ..rules import fact as RF
from ..sorts import search3 as S3
from ..undo import search as US


def blob_lists(alphabet: list, max_length: int) -> list:
    """Every blob-hash list over the alphabet of length 0..max_length, shortest first (a deterministic order)."""
    out = [[]]
    for n in range(1, max_length + 1):
        out += [list(t) for t in itertools.product(alphabet, repeat=n)]
    return out


class FactSearch(US.UndoSearch):
    """accept(w), when given, is asked about every witness the model gives (the real-side check), as in UndoSearch."""

    def __init__(self, model_f, doc: dict, sorts: dict, budget: dict, law: dict, log=None, accept=None,
                 deadline: float | None = None, consumer_sel: str | None = None):
        super().__init__(model_f, doc, sorts, budget, log=log, accept=accept, deadline=deadline)
        self.law = law
        m = (law.get("measure") or {}).get("domain") or {}
        self.blobs = blob_lists([w.lower() for w in (m.get("alphabet") or [])], int(m.get("max_length") or 0))
        self.consumer_sel = (consumer_sel or "").lower()
        self.last_refusal = None

    # ---------------------------------------------------------- candidates
    def succeeds(self, g: str, st: S3.Step) -> bool:
        self.tick()
        code, _g, _calls = self.m.run_step(g, st, save=False)
        return code == 0

    def variants1(self, g: str, trace: list, st: S3.Step) -> list:
        """The single-component variants of a step: each argument leaf and each environment leaf at S1's values (the
        blob-hash list also at every list of the measure's domain), in leaf order."""
        state, pools = self.ref.pools(g, trace)
        sy = S3.Synth(self.m, pools, 0)
        prev_ts = int(st.env.get("block.timestamp") or 0)
        out, seen = [], {st.key()}
        for leaf, ty in sy.leaves(st.action):
            if leaf[0] == "env" and leaf[1] == "blobhash":
                vals = [v for v in sy.value_set(leaf, ty, st, state, prev_ts)]
                vals += [b for b in self.blobs if b not in vals]
            else:
                vals = sy.value_set(leaf, ty, st, state, prev_ts)
            for v in vals:
                c = sy.assign(st, leaf, ty, v)
                if c is None:
                    continue
                k = c.key()
                if k in seen:
                    continue
                seen.add(k)
                out.append(c)
        return out

    def x1_candidates(self, g: str, trace: list, a: str):
        """Succeeding steps of a from g: S1's step, then its single-leaf variants that succeed."""
        st = self.synth(g, a, trace)
        self.tick()
        if st is None:
            return
        if self.succeeds(g, US.fresh_step(st)):
            yield US.fresh_step(st)
        for c in self.variants1(g, trace, st):
            c = US.fresh_step(c)
            if self.succeeds(g, c):
                yield c

    # ---------------------------------------------------------- K1
    def kernel(self, e: dict) -> tuple[dict | None, str]:
        a = e["basis"]["action"]
        x = RF.ghost_x(e["law_id"])

        def at(trace, g):
            for x1 in self.x1_candidates(g, trace, a):
                for x2 in self.variants1(g, trace, x1):
                    x2 = US.fresh_step(x2)
                    if not self.succeeds(g, x2):
                        continue
                    self.tick()
                    # each run's calls are answered by its own step (run_step), then the law at the pair
                    self.m.run_step(g, x1, save=False)
                    self.m.run_step(g, x2, save=False)
                    if not self.o.pred(f"fact_{x}", lambda: [{"$ref": g}, self.m.act(x1), {"$ref": g},
                                                             self.m.act(x2)]):
                        w = {"runs": [{"prefix": trace, "x": x1}, {"prefix": trace, "x": x2}]}
                        if self.accepted_fact(w):
                            return w
                        if str(self.last_refusal or "").startswith("run 1:"):
                            break       # the deployment rejects the first run itself: no second run helps it
            return None
        return self.over_prefixes(a, at)

    def inhabit_kernel(self, e: dict) -> tuple[dict | None, str]:
        """A reachable prefix and a succeeding step x of the action with fhit_<x>(s, x, s, x) true."""
        a = e["basis"]["action"]
        x = RF.ghost_x(e["law_id"])

        def at(trace, g):
            for x1 in self.x1_candidates(g, trace, a):
                self.m.run_step(g, x1, save=False)
                if self.o.pred(f"fhit_{x}", lambda: [{"$ref": g}, self.m.act(x1), {"$ref": g}, self.m.act(x1)]):
                    return {"prefix": trace, "x": x1}
            return None
        return self.over_prefixes(a, at)

    # ---------------------------------------------------------- attribution
    def takes_pin(self, g: str, y: S3.Step, x: str) -> bool:
        """Does the step y, from g, take the pin's copy branch (fx_pin_<x> in its pre-context)? An evaluation of the
        pin's condition only; the step is not run."""
        a = bname(y.action)
        act = self.m.act(y)
        x0 = {"$call": f"x0_{a}", "args": [self.st_of(g), act["f"]["ar"], act["f"]["en"]] + self.m.tables()}
        return self.o.pred(f"fx_pin_{x}", [x0])

    def pin_candidates(self, g: str, trace: list, a: str, x: str):
        """The candidate steps y of the action at g: S1's step and its single-component variants that take the pin
        (the contract's "y a candidate step of w taking the pin") and succeed. Only a step taking the pin is a
        candidate: it alone counts against the budget and is run."""
        st = self.synth(g, a, trace)
        if st is None:
            return
        for c in [st] + self.variants1(g, trace, st):
            c = US.fresh_step(c)
            if not self.takes_pin(g, c, x):
                continue
            if self.succeeds(g, c):
                yield c

    def attribution(self, e: dict, bonded_of, key_of) -> tuple[dict | None, str]:
        """bonded_of(g_after_y, k) -> A[k].m after y; key_of(g, y) -> the pin's key k (both evaluated by the caller's
        FACT section functions)."""
        w_action = e["basis"]["action"]
        x = RF.ghost_x(e["law_id"])

        def at(trace, g):
            for y in self.pin_candidates(g, trace, w_action, x):
                self.m.run_step(g, y, save=False)
                acts = lambda: [[self.m.act(s) for s in trace], self.m.act(y)]  # noqa: E731
                if self.o.pred(f"fact_{x}", acts):
                    continue
                k = key_of(g, y)
                code, gy, _c = self.m.run_step(g, y, save=True)
                try:
                    if code != 0:
                        continue
                    w = {"prefix": trace, "y": y, "t": [], "k": k, "bonded": bonded_of(gy, k)}
                    if not self.accepted_fact(w):   # (prefix, y) first: a y the deployment refuses gets no continuation
                        continue
                    t, bound = self.continuation(gy, trace + [y], w, e["basis"]["consumer"]["action"])
                finally:
                    self.forget(gy)
                w = dict(w, t=t, t_bound=bound)
                if self.accepted_fact(w):
                    return w
            return None
        return self.product_prefixes(w_action, at)

    R0 = {"$r": "FxR", "f": {"s": {"$call": "gh_s0", "args": []}, "g": {"$call": "fx_g0", "args": []}}}

    def companions(self, trace: list) -> str:
        """The FACT section's chooser companions after a trace (run_fact's g from Reach's initial state), canonical."""
        v = self.o.value("run_fact", [[self.m.act(st) for st in trace], self.R0])
        return json.dumps(((v or {}).get("f") or {}).get("g"), sort_keys=True)

    def product_prefixes(self, entry: str, at) -> tuple[dict | None, str]:
        """The attribution search's prefixes: as UndoSearch.over_prefixes, breadth first up to prefix_depth steps, at
        most max_prefixes states, but a state is the typed state with the chooser companions (the contract: "prefixes
        ... with the chooser companions"): two prefixes are one state only when their typed states, last times and
        companions agree, for the claim reads the companions (a chooser) as well as the typed state."""
        depth = int(self.budget.get("prefix_depth", 3))
        maxp = int(self.budget.get("max_prefixes", 3000))
        g0 = self.m.s0()
        tried = 1
        t0 = time.time()
        seen = {(self.m.fingerprint(g0), self.ref.ts0, self.companions([]))}
        level = [([], g0)]
        try:
            for d in range(depth + 1):
                nxt = []
                for trace, g in level:
                    self.timebox()
                    w = at(trace, g)
                    if w is not None:
                        self.log(f"  witness at prefix depth {d} after {tried} states, {self.cands} candidates "
                                 f"({round(time.time() - t0, 1)} s)")
                        return w, (f"{tried} prefix states with their chooser companions (depth <= {depth}, max "
                                   f"{maxp}), {self.cands} candidates (max {self.max_cands})" + self.refused_note())
                    if d == depth:
                        continue
                    for t2, g2 in self.ref.successors(g, trace, entry, maxp - tried):
                        ts = int(t2[-1].env.get("block.timestamp") or 0)
                        key = (self.ref.fp.get(g2) or self.m.fingerprint(g2), ts, self.companions(t2))
                        if key in seen:
                            continue
                        seen.add(key)
                        tried += 1
                        nxt.append((t2, g2))
                        if tried >= maxp:
                            break
                    if tried >= maxp:
                        break
                self.log(f"  prefix depth {d}: {tried} states, {self.cands} candidates")
                level = nxt
                if not level:
                    break
        except US.Budget:
            return None, (f"the candidate budget ({self.max_cands}) ran out after {tried} prefix states with their "
                          "chooser companions; no witness" + self.refused_note())
        except US.TimeBox:
            when = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.deadline))
            return None, (f"the time box ({when}) ended the search after {tried} prefix states with their chooser "
                          f"companions and {self.cands} candidates, at prefix depth <= {depth}; the preregistered "
                          f"budget (max {maxp} prefix states, {self.max_cands} candidates) was not exhausted: no "
                          "witness, and no bound" + self.refused_note())
        return None, (f"{tried} prefix states with their chooser companions, of at most {depth} successful steps (max "
                      f"{maxp}), {self.cands} candidates (max {self.max_cands}), continuations of at most "
                      f"{self.cont_depth} steps: no witness" + self.refused_note())

    def forget(self, g: str | None) -> None:
        """Drop a state the search is done with: the evaluator's saved state, and the state and pools I30's refuter
        cached for it (a continuation explores thousands of states; kept, they grew the search to gigabytes)."""
        if g is None:
            return
        self.m.drop([g])
        for key in [key for key in self.ref.cache if key[0] == g]:
            del self.ref.cache[key]
        self.ref.fp.pop(g, None)

    def makes_consumer_call(self, calls: list, bonded: int) -> bool:
        for _to, data in calls or []:
            d = str(data).lower()
            if self.consumer_sel and d.startswith(self.consumer_sel) and len(d) >= 10 + 64:
                if int(d[10:74], 16) == int(bonded):
                    return True
        return False

    def step_cands(self, g: str, trace: list, b: str) -> list:
        """A continuation step's candidates for action b at g: S1's step and its single-component variants with S1's
        blob-hash list."""
        st = self.synth(g, b, trace)
        self.tick()
        if st is None:
            return []
        return [US.fresh_step(st)] + [US.fresh_step(c) for c in self.variants1(g, trace, st)
                                      if c.env.get("blobhash") == st.env.get("blobhash")]

    def continuation(self, g: str, trace: list, w: dict, consumer_action: str) -> tuple[list, str]:
        """The first sequence t of at most continuation_depth successful steps from g (the state after y) whose last
        step makes the consumer's call with the bonded principal w["bonded"], and which the real side accepts as the
        witness w's continuation; ([], the bound) when none.
        Shortest first: each length is searched depth first. The last step is a call of the action that makes the
        consumer's call (F5). The steps before it are calls of every state-changing action, in rounds: the i-th
        candidate of each action in turn, the actions writing most of the families the consumer's action reads first,
        so every action's S1 step is tried before any variant.
        A model continuation the real side refuses is counted (the bound says how many) and the search goes on. Every
        state saved here is forgotten once explored. A budget or the run's time box running out here ends the
        continuation (t = [], the bound says so), never the witness."""
        reads: set = set()
        US._reads(self.d.by.get(consumer_action) or {}, reads)
        acts = [a["name"] for a in self.doc.get("actions") or []
                if self.d.by.get(a["name"], {}).get("mutability") not in ("view", "pure")]
        order = sorted(acts, key=lambda b: (-len(self.writes_of(b) & reads), b))
        tried, refused = [0], [0]

        def last(gg: str, t: list):
            for c in self.step_cands(gg, trace + t, consumer_action):
                self.tick()
                tried[0] += 1
                code, g2, calls = self.m.run_step(gg, c, save=True)
                self.forget(g2)
                if code != 0 or not self.makes_consumer_call(calls, w["bonded"]):
                    continue
                if self.accept is None or self.accept(dict(w, t=t + [c])) is None:
                    return t + [c]
                refused[0] += 1
            return None

        def rounds(gg: str, t: list):
            cands = [self.step_cands(gg, trace + t, b) for b in order]
            for i in range(max((len(cs) for cs in cands), default=0)):
                for cs in cands:
                    if i < len(cs):
                        yield cs[i]

        def search(gg: str, t: list, left: int):
            if left == 1:
                return last(gg, t)
            for c in rounds(gg, t):
                self.tick()
                tried[0] += 1
                code, g2, _calls = self.m.run_step(gg, c, save=True)
                try:
                    found = search(g2, t + [c], left - 1) if code == 0 else None
                finally:
                    self.forget(g2)
                if found is not None:
                    return found
            return None

        def note() -> str:
            return f"; {refused[0]} model continuation(s) refused by the real side" if refused[0] else ""
        try:
            for n in range(1, self.cont_depth + 1):
                found = search(g, [], n)
                if found is not None:
                    return found, f"{tried[0]} continuation candidates" + note()
        except US.Budget:
            return [], (f"the candidate budget ({self.max_cands}) ran out after {tried[0]} continuation candidates of at "
                        f"most {self.cont_depth} successful steps: none found makes the consumer's call with the bonded "
                        "principal" + note())
        except US.TimeBox:
            return [], (f"the run's time box ended the continuation after {tried[0]} continuation candidates of at most "
                        f"{self.cont_depth} successful steps: none found makes the consumer's call with the bonded "
                        "principal" + note())
        return [], (f"{tried[0]} continuation candidates of at most {self.cont_depth} successful steps: none makes the "
                    "consumer's call with the bonded principal" + note())

    def accepted_fact(self, w: dict) -> bool:
        why = None if self.accept is None else self.accept(w)
        self.last_refusal = why
        if why is None:
            return True
        self.refused += 1
        self.log(f"  a model witness is refused by the real-side check: {why} ({self.refused} refused)")
        return False


def witness_steps(w: dict) -> list:
    """Every step of a FACT witness, in trace order (kernel: both runs; attribution: prefix, y, t)."""
    if "runs" in w:
        out = []
        for r in w["runs"]:
            out += list(r["prefix"]) + [r["x"]]
        return out
    return list(w["prefix"]) + [w["y"]] + list(w.get("t") or [])


def dumps(o) -> str:
    return json.dumps(o, sort_keys=True)


__all__ = ["FactSearch", "blob_lists", "witness_steps", "bname"]
