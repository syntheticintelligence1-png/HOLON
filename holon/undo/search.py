"""Refutation of the UNDO laws on the typed M3 model (BUILD_PLAN I27; the contract is the docstring of
tests_m3/test_undo.py, "Deciding": the search, the witness and its realization).

The search runs on the combined module of holon.undo.trace (the typed model and the trace section, compiled once by
Bend and executed by holon/js/eval3.mjs), with I30's machinery (holon.sorts.search3): its state handles, S1's step
synthesis (argument and environment variants, generic in the document), its hash tables (the real keccak256 and
sha256 of every key a candidate looks up) and its external-call hints. The UNDO sidecar's budget bounds it:

  prefixes       breadth first from Reach's initial state, at most prefix_depth successful steps (S2's successors,
                 the actions writing most of what a reads first), at most max_prefixes distinct states
  the pair       x a successful call of a (S1), then y a successful call of the undo action whose run restores every
                 register the pair restores (uhit_<x>: the law's premises, evaluated as Bend states them)
  continuations  at most continuation_depth steps: first the redo of x itself (its clock moved to y's), then for every
                 action (those reading what a writes first) its synthesized successful steps from each of the two
                 states and their argument variants (the registers' keys first); every t whose observations from the
                 two states differ (obs, as Bend states it) is a witness
  candidates     every (x, y, t) evaluated counts; at most max_candidates per law; the first witness ends the search

A residue law's witness is realized by one of its pairs: x a call of one of its pairs' a, y of the undo action
(restoring as the pair law requires), k the key x writes the residue at, v the register's raw words in the state after
prefix, x, y; t must observe set_F(s, k, v) differently from s and exactly as the state after x and y (the divergence
is the residue's alone, checked on the model). The order is deterministic; the search is not a proof of absence.

Nothing here names a target.
"""
from __future__ import annotations

import json
import time

from ..machine_bend import bname
from ..rules import undo as U
from ..sorts import search3 as S3

MASK = (1 << 256) - 1


def norm_to(to) -> str | None:
    return None if to is None else "0x" + str(to)[-40:].lower()


def _hex(v) -> str:
    if isinstance(v, dict) and "$b" in v:
        return v["$b"].lower()
    if isinstance(v, list) and not v:
        return "0x"
    if isinstance(v, list):
        return "0x" + bytes(int(x) for x in v).hex()
    raise ValueError(f"not a byte string: {str(v)[:80]}")


def ob_json(o: dict, st: S3.Step | None = None, looked: list | None = None) -> dict:
    """A decoded UOb as the observation {"status", "ret", "logs", "calls"} (calls: the step's environment answers its
    evaluation looked up, in the environment's order; none for a reverted step)."""
    f = o["f"]
    ok = bool(f["ok"])
    logs = []
    for lg in (f.get("lg") or []) if ok else []:
        lf = lg["f"]
        topics = [str(t).lower() for t in (lf.get("t") or [])]
        logs.append({"topics": topics, "data": _hex(lf.get("d"))})
    calls = []
    if ok and st is not None:
        seen = {(norm_to(t), d) for t, d in (looked or [])}
        seen_d = {d for t, d in (looked or []) if t is None}
        for c in st.env.get("calls") or []:
            if (norm_to(c.get("to")), c.get("data")) in seen or c.get("data") in seen_d:
                calls.append({"to": norm_to(c.get("to")), "data": str(c.get("data")).lower()})
    return {"status": "ok" if ok else "revert", "ret": _hex(f.get("d")), "logs": logs, "calls": calls}


def reenc(v):
    """A decoded evaluator value (words as "0x.." strings) as an argument the evaluator encodes again."""
    if isinstance(v, str) and v.startswith("0x"):
        return {"$w": v}
    if isinstance(v, dict) and "$r" in v:
        return {"$r": v["$r"], "f": {k: reenc(x) for k, x in (v.get("f") or {}).items()}}
    if isinstance(v, list):
        return [reenc(x) for x in v]
    return v


def limited(o: dict) -> bool:
    """A step the model could not observe: an external call without an answer, or a loop past its fuel."""
    return int(o.get("code") or 0) in (S3.CALL_CODE, S3.FUEL_CODE)


def bend_view(o: dict) -> dict:
    """The part of an observation Bend's obs states (holon.undo.trace: success, data, logs)."""
    return {k: o[k] for k in ("status", "ret", "logs")}


class Obs:
    """UNDO evaluations on one combined-module model (an S3.Model)."""

    def __init__(self, m: S3.Model):
        self.m = m

    def settle(self, req: dict, st: S3.Step | None, save: str | None = None) -> dict:
        """An evaluation with the hash keys it looks up learned and the calls it looks up answered (on st's env).
        req["args"] may be a function giving the arguments: each round encodes them again (an answer just added to a
        step's environment is part of its next encoding)."""
        m = self.m
        for _ in range(40):
            tabs = m.tables()
            args = req["args"]() if callable(req["args"]) else list(req["args"])
            r = m.mreq(dict(req, args=list(args) + tabs, **({"save": save, "quiet": True} if save else {})))
            new = m.learn(r)
            changed = m.answer_calls(st, r.get("calls") or []) if st is not None else False
            if not (new or changed):
                return r
        raise RuntimeError(f"{req.get('fn')}: the hash keys and call answers did not settle")

    def ostep(self, g: str, st: S3.Step) -> tuple[dict, str]:
        """(the step's observation, the state after it) from state g. The observation carries "code", the step's
        check code: an unanswered external call or the loop fuel is the model's limit, not an observation."""
        m = self.m
        u = m.fresh()
        r = self.settle({"fn": "ux_ostep", "args": lambda: [m.act(st), {"$ref": g}]}, st, save=u)
        o = m.mreq({"fn": "ux_uos_o", "args": [{"$ref": u}]})["out"]
        c = int(m.mreq({"fn": "ux_uos_c", "args": [{"$ref": u}]})["out"])
        g2 = m.fresh()
        m.mreq({"fn": "ux_uos_g", "args": [{"$ref": u}], "save": g2, "quiet": True})
        m.drop([u])
        return dict(ob_json(o, st, r.get("calls") or []), code=c), g2

    def run(self, g: str, steps: list) -> tuple[list, list]:
        """(observations, the state handle after each step) of a trace from g."""
        out, gs = [], []
        for st in steps:
            o, g = self.ostep(g, st)
            out.append(o)
            gs.append(g)
        return out, gs

    def pred(self, fn: str, args: list, st: S3.Step | None = None) -> bool:
        r = self.settle({"fn": fn, "args": args}, st)
        return bool(r["out"])

    def word(self, fn: str, args: list) -> int:
        r = self.settle({"fn": fn, "args": args}, None)
        return int(r["out"], 16)

    def value(self, fn: str, args: list):
        return self.settle({"fn": fn, "args": args}, None)["out"]

    def state_of(self, fn: str, args: list) -> str:
        g = self.m.fresh()
        self.settle({"fn": fn, "args": args}, None, save=g)
        return g


def settle_witness(model_f, prefix: list, fn: str, args_of) -> tuple[dict, dict, object, list]:
    """The witness's hash tables: the real hash of exactly the keys its prefix and the law's function at it (fn, with
    args_of(model, the state after the prefix) giving the arguments after the state) look up, from empty tables (a
    fixpoint on a fresh model whose tables are passed as Bend lists, never native). The steps' call answers are
    theirs (none is added). Returns (kh, sh, fn's value, the decoded state after each prefix step)."""
    prefix = [fresh_step(st) for st in prefix]
    for _ in range(8):
        m = model_f(empty=True, native=False)
        g = m.s0()
        n0 = None
        for _round in range(4):
            g = m.s0()
            for st in prefix:
                code, g, _c = m.run_step(g, st, save=True)
                if code != 0:
                    raise RuntimeError(f"the witness's prefix step {st.action} does not succeed (code {code})")
            o = Obs(m)
            r = o.settle({"fn": fn, "args": lambda: [{"$ref": g}] + list(args_of(m, g))}, None)
            n = (len(m.kh), len(m.sh))
            if n == n0:
                break
            n0 = n
        states = []
        g = m.s0()
        for st in prefix:
            _code, g, _c = m.run_step(g, st, save=True)
            states.append(m.ev.req({"show": g})["out"])
        return dict(m.kh), dict(m.sh), r["out"], states
    raise RuntimeError("the witness's hash tables did not settle")


def retime(st: S3.Step, ts: int) -> S3.Step:
    env = json.loads(json.dumps(st.env))
    env["calls"] = []
    env.pop("_unanswered", None)
    env["block.timestamp"] = max(int(env.get("block.timestamp") or 0), int(ts))
    return S3.Step(st.action, json.loads(json.dumps(st.args)), env)


def fresh_step(st: S3.Step) -> S3.Step:
    env = json.loads(json.dumps(st.env))
    env.pop("_unanswered", None)
    return S3.Step(st.action, json.loads(json.dumps(st.args)), env)


def _reads(t, out: set) -> None:
    if isinstance(t, list):
        if len(t) == 2 and t[0] == "storage" and isinstance(t[1], str):
            out.add(t[1])
        for x in t:
            _reads(x, out)
    elif isinstance(t, dict):
        for x in t.values():
            _reads(x, out)


def readers_order(doc: dict, fams: set) -> list[str]:
    """Every action, those whose records read most of the given families first (then by name)."""
    rows = []
    for a in doc.get("actions") or []:
        r: set = set()
        _reads(a, r)
        rows.append((-len(r & fams), a["name"]))
    return [n for _k, n in sorted(rows)]


class Budget(Exception):
    pass


class UndoSearch:
    """accept(w), when given, is asked about every witness the model gives (the caller's real-side check): a witness it
    refuses is counted and the search goes on."""

    def __init__(self, model_f, doc: dict, sorts: dict, budget: dict, log=None, accept=None):
        self.mf = model_f
        self.accept = accept
        self.refused = 0
        self.m = model_f()
        self.o = Obs(self.m)
        self.doc = doc
        self.d = U.Doc(doc)
        self.sorts = sorts
        self.budget = dict(budget or {})
        self.log = log or (lambda s: None)
        rb = {"prefix_depth": int(self.budget.get("prefix_depth", 3)),
              "max_prefixes": int(self.budget.get("max_prefixes", 3000))}
        self.ref = S3.Refuter(self.m, doc, sorts, rb, log=self.log)
        self.cands = 0
        self.max_cands = int(self.budget.get("max_candidates", 200000))
        self.cont_depth = int(self.budget.get("continuation_depth", 2))

    # ---------------------------------------------------------- helpers
    def tick(self, n: int = 1) -> None:
        self.cands += n
        if self.cands > self.max_cands:
            raise Budget()

    def st_of(self, g: str) -> dict:
        return {"$call": "gh_get_st", "args": [{"$ref": g}]}

    def synth(self, g: str, a: str, trace: list, **kw):
        st, code = self.ref.synth(g, a, trace, **kw)
        return st if (st is not None and (code == 0 or kw.get("accept") is not None)) else None

    def writes_of(self, a: str) -> set:
        return {w.get("family") for w in (self.d.by.get(a) or {}).get("writes") or []}

    def key_pool(self, keys: list) -> list[int]:
        out = []
        for k in keys:
            for d in (0, 1, -1):
                v = (k + d) & MASK
                if v not in out:
                    out.append(v)
        return out

    # ---------------------------------------------------------- continuations
    def variants(self, g: str, trace: list, st: S3.Step, keys: list) -> list:
        """A step's argument variants: each numeric parameter at the registers' keys (and +-1), then each leaf at a few
        of S1's values; the clock at the previous clock and one past each duration the state holds."""
        state, pools = self.ref.pools(g, trace)
        sy = S3.Synth(self.m, pools, 0)
        out = []
        prev_ts = int(st.env.get("block.timestamp") or 0)
        for leaf, ty in sy.leaves(st.action):
            if leaf[0] == "env":
                if leaf[1] != "block.timestamp":
                    continue
                vals = sy.value_set(leaf, ty, st, state, prev_ts)[:8]
            elif ty in ("bytes", "string") or ty.endswith("]"):
                continue
            else:
                vals = self.key_pool(keys) + [v for v in sy.value_set(leaf, ty, st, state, prev_ts)[:6]
                                              if v not in keys]
            for v in vals:
                c = sy.assign(st, leaf, ty, v)
                if c is not None:
                    out.append(c)
        return out

    def first_steps(self, gs: list, trace: list, seeds: list, fams: set, keys: list):
        """Candidate first steps of a continuation from the states gs (the run with the pair first): the seeds, then
        per action (those reading fams first) its synthesized successful step from each state and their variants."""
        seen = set()
        for st in seeds:
            k = st.key()
            if k not in seen:
                seen.add(k)
                yield st
        for b in readers_order(self.doc, fams):
            bases = []
            for g in gs:
                st = self.synth(g, b, trace)
                if st is None:
                    st = S3.Synth(self.m, self.ref.pools(g, trace)[1], 0).base(b, trace[-1] if trace else None,
                                                                              self.ref.ts0)
                bases.append(st)
            for st in bases:
                for c in [st] + self.variants(gs[0], trace, st, keys):
                    c = retime(c, int(trace[-1].env.get("block.timestamp") or 0) if trace else 0)
                    k = c.key()
                    if k in seen:
                        continue
                    seen.add(k)
                    yield c

    def continuations(self, ga: str, gb: str, trace: list, seeds: list, fams: set, keys: list, check):
        """Search t (at most continuation_depth steps) whose observations from ga and gb differ (check(t, obs_a,
        obs_b) decides); returns t or None."""
        level = [([], ga, gb)]
        for _d in range(self.cont_depth):
            nxt = []
            for t, xa, xb in level:
                tr = trace + t
                for st in self.first_steps([xa, xb], tr, seeds if not t else [], fams, keys):
                    self.tick()
                    sa = fresh_step(st)
                    oa, ha = self.o.ostep(xa, sa)
                    ob, hb = self.o.ostep(xb, sa)
                    tt = t + [sa]
                    if limited(oa) or limited(ob):     # the model's limit on either run: no observation
                        self.m.drop([ha, hb])
                        continue
                    if check(tt, oa, ob):
                        self.log(f"  divergence at {st.action} (codes {oa.get('code')}, {ob.get('code')}): "
                                 f"{json.dumps(bend_view(oa))[:300]} / {json.dumps(bend_view(ob))[:300]}")
                        return tt
                    if oa["status"] == "ok" or ob["status"] == "ok":
                        nxt.append((tt, ha, hb))
                    else:
                        self.m.drop([ha, hb])
            level = nxt
        return None

    # ---------------------------------------------------------- the pair
    X_VARIANTS = 8

    def x_candidates(self, g: str, trace: list, a: str) -> list:
        """Successful calls of a from g: S1's step, then its argument variants (each leaf at a few of S1's values),
        at most X_VARIANTS with distinct post-states."""
        st = self.synth(g, a, trace)
        self.tick()
        if st is None:
            return []
        state, pools = self.ref.pools(g, trace)
        sy = S3.Synth(self.m, pools, 0)
        cands = [st]
        prev_ts = int(st.env.get("block.timestamp") or 0)
        # one move per leaf before a second move of any (the leaves round robin)
        per_leaf = []
        for leaf, ty in sy.leaves(a):
            if leaf[0] == "env" and leaf[1] in ("msg.value", "block.timestamp"):
                continue
            cur = S3._get(st.args, list(leaf[1:])) if leaf[0] == "param" else st.env.get(leaf[1])
            row = []
            for v in sy.value_set(leaf, ty, st, state, prev_ts)[:6]:
                if v == cur:
                    continue
                c = sy.assign(st, leaf, ty, v)
                if c is not None:
                    row.append(c)
            per_leaf.append(row)
        for r in range(max([len(x) for x in per_leaf] or [0])):
            cands += [row[r] for row in per_leaf if r < len(row)]
        out, seen = [], set()
        for c in cands:
            if len(out) >= self.X_VARIANTS:
                break
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

    def pairs_at(self, e: dict, trace: list, g: str):
        """Every (x, y, s2) of a pair law at a prefix state, x over x_candidates."""
        b = e["basis"]
        x = U.ghost_x(e["law_id"])
        for xs, s1 in self.x_candidates(g, trace, b["a"]):
            def acc(st, c, xs=xs):
                return c == 0 and self.o.pred(f"uhit_{x}", lambda: [{"$ref": g}, self.m.act(xs), self.m.act(st), []],
                                              st)
            ys = self.synth(s1, b["undo"], trace + [xs], accept=acc)
            self.tick()
            if ys is None:
                continue
            code, s2, _c = self.m.run_step(s1, ys, save=True)
            if code != 0:
                continue
            yield xs, ys, s2

    def keys_of(self, e: dict, xs: S3.Step, g: str) -> list[int]:
        """The keys x writes the pair's restored mapping registers (and residues) at, evaluated in x's context."""
        x = U.ghost_x(e["law_id"])
        out = []
        a = bname(xs.action)
        for j, r in enumerate(e["basis"]["restores"]):
            if self.d.is_mapping(r["family"]):
                x0 = {"$call": f"x0_{a}", "args": [self.st_of(g), self.m.act(xs)["f"]["ar"],
                                                    self.m.act(xs)["f"]["en"]] + self.m.tables()}
                try:
                    out.append(self.o.word(f"ux_key_{x}_{j}", [x0]))
                except Exception:  # noqa: BLE001: a key the evaluator cannot give is no candidate
                    pass
        return sorted(set(out))

    def pair(self, e: dict) -> tuple[dict | None, str]:
        b = e["basis"]
        fams = {r["family"] for r in b["restores"]} | set(b["residues"])
        return self.over_prefixes(b["a"], lambda trace, g: self.pair_witness(e, trace, g, fams))

    def pair_witness(self, e, trace, g, fams):
        for xs, ys, s2 in self.pairs_at(e, trace, g):
            keys = self.keys_of(e, xs, g)
            seeds = [retime(xs, int(ys.env.get("block.timestamp") or 0))]

            def check(t, oa, ob):
                return bend_view(oa) != bend_view(ob)
            t = self.continuations(s2, g, trace + [xs, ys], seeds, fams, keys, check)
            if t is not None:
                w = {"prefix": trace, "x": xs, "y": ys, "t": t}
                if self.accepted(w):
                    return w
        return None

    def accepted(self, w: dict) -> bool:
        if self.accept is None or self.accept(w):
            return True
        self.refused += 1
        self.log(f"  the witness ({w['x'].action}, {w['y'].action}, t {[s.action for s in w['t']]}) is refused by "
                 f"the real-side check ({self.refused} refused)")
        return False

    # ---------------------------------------------------------- the residue
    def residue(self, e: dict, pair_laws: dict) -> tuple[dict | None, str]:
        b = e["basis"]
        fams = {b["family"]}

        def at(trace, g):
            for a in b["pairs"]:
                pl = pair_laws.get(a)
                if pl is None:
                    continue
                w = self.residue_witness(e, pl, a, trace, g, fams)
                if w is not None:
                    return w
            return None
        return self.over_prefixes(b["pairs"][0], at)

    def residue_witness(self, e, pl, a, trace, g, fams):
        for xs, ys, s2 in self.pairs_at(pl, trace, g):
            w = self.residue_at(e, a, trace, g, fams, xs, ys, s2)
            if w is not None and self.accepted(w):
                return w
        return None

    def residue_at(self, e, a, trace, g, fams, xs, ys, s2):
        b = e["basis"]
        x = U.ghost_x(e["law_id"])
        ab = bname(a)
        act = self.m.act(xs)
        x0 = {"$call": f"x0_{ab}", "args": [self.st_of(g), act["f"]["ar"], act["f"]["en"]] + self.m.tables()}
        k = self.o.word(f"ux_rk_{x}_{ab}", [x0])
        bf = bname(b["family"])
        v = reenc(self.o.value(f"ux_reg_{bf}", [self.st_of(s2), {"$w": "0x%064x" % k}]))
        if not self.o.pred(f"uhit_{x}", [{"$ref": g}, {"$w": "0x%064x" % k}, v, []]):
            return None
        gf = self.o.state_of(f"set_{bf}", [{"$ref": g}, {"$w": "0x%064x" % k}, v])
        seeds = [retime(xs, int(ys.env.get("block.timestamp") or 0))]
        realized = {}

        def check(t, oa, ob):
            if bend_view(oa) == bend_view(ob):
                return False
            # the divergence is the residue's alone: t observes set_F(s, k, v) as it observes the state after x and y
            o2, h2 = self.o.ostep(realized["s2"], fresh_step(t[-1])) if len(t) == 1 else (None, None)
            return True if o2 is None else bend_view(o2) == bend_view(oa)
        realized["s2"] = s2
        t = self.continuations(gf, g, trace + [xs, ys], seeds, fams, [k], check)
        if t is None:
            return None
        # the realization on the model, over the whole of t
        oa, _ = self.o.run(gf, [fresh_step(st) for st in t])
        o2, _ = self.o.run(s2, [fresh_step(st) for st in t])
        if [bend_view(o) for o in oa] != [bend_view(o) for o in o2]:
            return None
        return {"prefix": trace, "x": xs, "y": ys, "t": t, "k": k, "v": v}

    # ---------------------------------------------------------- prefixes
    def over_prefixes(self, entry: str, at) -> tuple[dict | None, str]:
        depth = int(self.budget.get("prefix_depth", 3))
        maxp = int(self.budget.get("max_prefixes", 3000))
        g0 = self.m.s0()
        tried = 1
        t0 = time.time()
        seen = {(self.m.fingerprint(g0), self.ref.ts0)}
        level = [([], g0)]
        try:
            for d in range(depth + 1):
                nxt = []
                for trace, g in level:
                    w = at(trace, g)
                    if w is not None:
                        self.log(f"  witness at prefix depth {d} after {tried} states, {self.cands} candidates "
                                 f"({round(time.time() - t0, 1)} s)")
                        return w, (f"{tried} prefix states (depth <= {depth}, max {maxp}), {self.cands} candidates "
                                   f"(max {self.max_cands})" + self.refused_note())
                    if d == depth:
                        continue
                    for t2, g2 in self.ref.successors(g, trace, entry, maxp - tried):
                        key = (self.ref.fp.get(g2) or self.m.fingerprint(g2), int(t2[-1].env.get("block.timestamp") or 0))
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
        except Budget:
            return None, (f"the candidate budget ({self.max_cands}) ran out after {tried} prefix states; no witness"
                          + self.refused_note())
        return None, (f"{tried} prefix states of at most {depth} successful steps (max {maxp}), {self.cands} "
                      f"candidates (max {self.max_cands}), continuations of at most {self.cont_depth} steps: no witness"
                      + self.refused_note())

    def refused_note(self) -> str:
        return f"; {self.refused} model witnesses refused by the real-side check" if self.refused else ""
