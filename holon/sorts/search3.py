"""Refutation of the I30 laws on the compiled M3 model (I30; the contract is the docstring of
tests_m3/test_sort_types.py, "Proofs, refutation, non-vacuity"): I15's stages over the typed model from its initial
state, with the sidecar's budget.

  S1  the entry point's step from the state a prefix reached: argument and environment variants, generic in the
      document: values the initial state and the trace hold (storage words, earlier arguments and environments, the
      words of the byte strings the deployment and the trace hashed), the document's literals, 0, 1 and the +-1
      neighbours of a number, a list's [] and one-element variants, a bytes argument's preimages; and, for the check a
      step fails first, the values of the terms it compares a leaf with (evaluated by holon.extracted_eval over the
      model's state: candidates, never evidence) and their +-1 neighbours. A block.timestamp is a chain's clock: never 0
      and never below the previous step's; its candidates also include the previous clock plus each duration the
      state holds (the §7.2 table: Time + Dur), plus one.
  S2  breadth-first prefixes of at most prefix_depth successful steps before the entry step (at most max_prefixes),
      actions ordered by how directly they write what the entry point reads.
  S3  for an entry point S2 left without a witness: the other entry points' witnesses, at most
      neighbourhood_insertion_length_max successful steps inserted and the last step replaced by the entry point's
      (at most neighbourhood_prefixes_per_entry_point_max prefixes).

Every candidate runs on the compiled model (holon.sorts.evaluate3): its hash tables are the real keccak256 / sha256 of
every key the trace looks up (a fixpoint), and its external calls are answered from hints (the corpus run's call
records, holon fragments --hints: candidate answers, never evidence; the replay compares them with the real ones).
A witness is a trace whose last step is the entry point's and on which the law's coerce_<x> is false; Bend and BendTT
decide it (holon.sorts.proofs3).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .. import extracted_eval as EV
from ..keccak import keccak256
from ..machine_bend import bname

MASK = (1 << 256) - 1
CALL_CODE = 4294967294
FUEL_CODE = 4294967295


def kec(b: bytes) -> int:
    return int.from_bytes(keccak256(b), "big")


@dataclass
class Step:
    action: str
    args: dict
    env: dict

    def key(self) -> str:
        return json.dumps([self.action, self.args, self.env], sort_keys=True, default=str)


@dataclass
class Result:
    entry: str
    steps: list
    stage: str
    kh: dict
    sh: dict
    tried: int


# ------------------------------------------------------------------------------------------------ hints
class Hints:
    """Candidate answers of external calls (holon fragments --hints): exact calldata first, then the selector; an
    answer that equals its step's block.timestamp at every occurrence is answered with the step's clock."""

    def __init__(self, doc: dict | None):
        self.calls = list((doc or {}).get("calls") or [])
        self.by_data: dict = {}
        self.by_sel: dict = {}
        for c in self.calls:
            self.by_data.setdefault(c["data"], []).append(c)
            self.by_sel.setdefault(c["data"][:10], []).append(c)

    @staticmethod
    def _rule(cs: list):
        ts_rule = all(c["ok"] and len(c["ret"]) == 66 and int(c["ret"], 16) == int(c["timestamp"]) for c in cs)
        if ts_rule and len({c["ret"] for c in cs}) > 1:
            return ("ts", cs[0]["to"])
        answers = {}
        for c in cs:
            answers.setdefault((c["ok"], c["ret"], c["to"]), 0)
            answers[(c["ok"], c["ret"], c["to"])] += 1
        best = sorted(answers.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        return ("const", best)

    def addresses(self) -> list[int]:
        """Address-sized words of the hints' calldata (candidate callers: hints, never evidence)."""
        out = set()
        for c in self.calls:
            d = c["data"][10:]
            for i in range(0, len(d) - 63, 64):
                w = int(d[i:i + 64], 16)
                if 0xff < w < (1 << 160):
                    out.add(w)
        return sorted(out)

    def answer(self, to: str | None, data: str, ts: int):
        if to is not None:
            to = "0x" + to[-40:]
        cs = self.by_data.get(data)
        if not cs:
            cs = self.by_sel.get(data[:10]) or []
            # another argument: only a selector whose every recorded call got one answer answers it
            if len({(c["ok"], c["ret"]) for c in cs}) != 1 and not all(
                    c["ok"] and len(c["ret"]) == 66 and int(c["ret"], 16) == int(c["timestamp"]) for c in cs):
                return None
        if not cs:
            return None
        if to is not None:
            same = [c for c in cs if c["to"] == to]
            cs = same or cs
        kind, v = self._rule(cs)
        if kind == "ts":
            return {"to": v, "data": data, "ok": True, "ret": "0x%064x" % ts}
        ok, ret, cto = v
        return {"to": to or cto, "data": data, "ok": ok, "ret": ret}


# ------------------------------------------------------------------------------------------------ the model
class Model:
    """The compiled model of one document with its initial state, as a refuter drives it (stored state handles)."""

    def __init__(self, ev, init: dict, hints: Hints, doc_path: Path):
        self.ev = ev
        self.doc = ev.doc                 # holon.machine.ExtractedModel
        self.init = init or {}
        self.hints = hints
        self.kh: dict = {}
        self.sh: dict = {}
        self.kh_sent = -1
        self.sh_sent = -1
        self.n = 0
        self.hashes = ev.hashes()
        self.base_env = {"this": self.init.get("target") or "0x" + "00" * 19 + "ab",
                         "immutable": dict(self.init.get("immutables") or {}),
                         "block.number": self.init.get("number") or 1, "block.chainid": self.init.get("chainid") or 1}
        if self.init.get("code"):
            self.base_env["code"] = {self.base_env["this"]: self.init["code"]}
        for p in self.init.get("preimages") or []:
            self.add_key(p)

    def add_key(self, k: str, which: str = "kh") -> bool:
        tab = self.kh if which == "kh" else self.sh
        if k in tab:
            return False
        b = bytes.fromhex(k[2:])
        tab[k] = kec(b) if which == "kh" else int.from_bytes(hashlib.sha256(b).digest(), "big")
        return True

    @staticmethod
    def _sig(tab: dict) -> tuple:
        return (len(tab), hash(frozenset(tab)))

    def tables(self) -> list:
        out = []
        if "keccak256" in self.hashes:
            if self.kh_sent != self._sig(self.kh):
                self.ev.req({"fn": "kt_id", "args": [self.ev.table(self.kh)], "save": "KH", "quiet": True})
                self.kh_sent = self._sig(self.kh)
            out.append({"$ref": "KH"})
        if "sha256" in self.hashes:
            if self.sh_sent != self._sig(self.sh):
                self.ev.req({"fn": "kt_id", "args": [self.ev.table(self.sh)], "save": "SH", "quiet": True})
                self.sh_sent = self._sig(self.sh)
            out.append({"$ref": "SH"})
        return out

    def fresh(self) -> str:
        self.n += 1
        return f"g{self.n}"

    def s0(self) -> str:
        if not getattr(self, "_s0", None):
            self.ev.req({"fn": "gh_s0", "args": [], "save": "G0", "quiet": True})
            self._s0 = "G0"
        return self._s0

    def calldata(self, st: Step) -> str:
        a = self.doc.actions[st.action]
        ps = self.doc.params(st.action) or []
        vals = [EV.norm(st.args.get(p["name"]), p) for p in ps]
        return (a.get("selector") or "0x") + EV.abi_encode(vals, ps).hex()

    def act(self, st: Step) -> dict:
        env = self.full_env(st)
        return {"$r": f"A_{bname(st.action)}", "f": {"ar": self.ev.args_in(st.action, st.args),
                                                       "en": self.ev.env_in(env)}}

    def full_env(self, st: Step) -> dict:
        env = dict(self.base_env)
        env.update(st.env)
        env["msg.data.length"] = (len(self.calldata(st)) - 2) // 2
        return env

    def forget(self, kh0: set, sh0: set) -> None:
        """Drop the keys learned since (kh0, sh0): a candidate that is not kept leaves the tables as they were (a later
        evaluation that needs a key learns it again)."""
        for k in [k for k in self.kh if k not in kh0]:
            del self.kh[k]
        for k in [k for k in self.sh if k not in sh0]:
            del self.sh[k]

    def run_step(self, g: str, st: Step, save: bool = True) -> tuple[int, str | None, list]:
        """(chk code, the next state's handle (None when not saved), the calls the step looks up) of one step from
        state g, with its hash keys and call answers settled (fixpoint)."""
        if save:
            return self._run_step(g, st, True)
        kh0, sh0 = set(self.kh), set(self.sh)
        try:
            return self._run_step(g, st, False)
        finally:
            self.forget(kh0, sh0)

    def _run_step(self, g: str, st: Step, save: bool) -> tuple[int, str | None, list]:
        for _ in range(40):
            tabs = self.tables()
            a = self.act(st)
            r = self.ev.req({"fn": f"chk_{bname(st.action)}",
                             "args": [{"$call": "gh_get_st", "args": [{"$ref": g}]}, a["f"]["ar"], a["f"]["en"]] + tabs})
            new = self.learn(r)
            calls = r.get("calls") or []
            changed = self.answer_calls(st, calls)
            if new or changed:
                continue
            code = int(r["out"])
            name = None
            if save:
                name = self.fresh()
                r2 = self.ev.req({"fn": "gh_step", "args": [a, {"$ref": g}] + tabs, "save": name, "quiet": True})
                if self.learn(r2):
                    continue
            return code, name, calls
        raise RuntimeError(f"{st.action}: the hash keys and call answers did not settle")

    def learn(self, r: dict) -> bool:
        new = False
        for k in (r.get("keys") or {}).get("kh") or []:
            new |= self.add_key(k, "kh")
        for k in (r.get("keys") or {}).get("sh") or []:
            new |= self.add_key(k, "sh")
        return new

    def answer_calls(self, st: Step, calls: list) -> bool:
        def norm(to):
            return None if to is None else "0x" + str(to)[-40:].lower()
        have = {(norm(c.get("to")), c["data"]) for c in st.env.get("calls") or []}
        have_d = {c["data"] for c in st.env.get("calls") or []}
        tried = st.env.setdefault("_unanswered", [])
        changed = False
        for to, data in calls:
            to = norm(to)
            if (to, data) in have or (to is None and data in have_d) or [to, data] in tried:
                continue
            ans = self.hints.answer(to, data, int(st.env.get("block.timestamp") or 0))
            if ans is None:
                tried.append([to, data])
                continue
            st.env.setdefault("calls", []).append(ans)
            have.add((ans["to"], data))
            have_d.add(data)
            changed = True
        return changed

    def pred(self, fn: str, g: str, st: Step) -> bool:
        kh0, sh0 = set(self.kh), set(self.sh)
        try:
            return self._pred(fn, g, st)
        finally:
            self.forget(kh0, sh0)

    def _pred(self, fn: str, g: str, st: Step) -> bool:
        for _ in range(40):
            tabs = self.tables()
            r = self.ev.req({"fn": fn, "args": [self.act(st), {"$ref": g}] + tabs})
            if self.learn(r) or self.answer_calls(st, r.get("calls") or []):
                continue
            return bool(r["out"])
        raise RuntimeError(f"{fn}: the hash keys did not settle")

    def state(self, g: str) -> dict:
        r = self.ev.req({"fn": "gh_get_st", "args": [{"$ref": g}]})
        out = {}
        for kv in r["out"]["f"]["sl"]:
            out[int(kv["f"]["k"], 16)] = int(kv["f"]["v"], 16)
        return out

    def fingerprint(self, g: str) -> str:
        """A state's identity: its storage and ghost store, each a set of keyed entries (a slot written 0 is a slot
        never written)."""
        def canon(x):
            if isinstance(x, dict):
                return {k: canon(v) for k, v in x.items()}
            if isinstance(x, list):
                ys = [canon(v) for v in x]
                if ys and all(isinstance(y, dict) and set((y.get("f") or {})) == {"k", "v"} for y in ys):
                    ys = [y for y in ys if not (isinstance(y["f"]["v"], str) and y["f"]["v"].startswith("0x")
                                               and int(y["f"]["v"], 16) == 0)]
                    ys = sorted(ys, key=lambda y: json.dumps(y, sort_keys=True))
                return ys
            return x
        r = self.ev.req({"show": g})
        return hashlib.sha256(json.dumps(canon(r["out"]), sort_keys=True).encode()).hexdigest()

    def drop(self, names: list) -> None:
        if names:
            self.ev.req({"drop": names})


# ------------------------------------------------------------------------------------------------ candidates
def _ints(t, out: set) -> None:
    if isinstance(t, bool):
        return
    if isinstance(t, int):
        if 0 <= t <= MASK:
            out.add(t)
        return
    if isinstance(t, list):
        for x in t:
            _ints(x, out)
    elif isinstance(t, dict):
        for x in t.values():
            _ints(x, out)


def _leaves(t, out: list) -> None:
    """The input leaves a term reads: ("param", path..) and ("env", name)."""
    if not isinstance(t, list) or not t:
        return
    h = t[0]
    if h == "param" and isinstance(t[1], str):
        out.append(("param", t[1]))
        return
    if h == "member" and len(t) >= 3:
        inner: list = []
        _leaves(t[1], inner)
        if inner and inner[0][0] == "param" and isinstance(t[1], list) and t[1][:1] in (["param"], ["member"]):
            out.append(inner[0] + (t[2],))
            return
    if h == "env":
        out.append(("env", t[1]))
        return
    if h == "caller":
        out.append(("env", "caller"))
        return
    if h == "blobhash":
        out.append(("env", "blobhash"))
    for x in t[1:]:
        _leaves(x, out)


def _comparisons(t, out: list) -> None:
    if not isinstance(t, list) or not t:
        return
    if t[0] in ("==", "!=", "<", "<=", ">", ">=") and len(t) == 3:
        out.append((t[0], t[1], t[2]))
    if t[0] == "fits" and len(t) == 3 and isinstance(t[2], list) and len(t[2]) == 3 and t[2][0] in ("+", "-"):
        out.append(("fits" + t[2][0], t[2][1], t[2][2]))
    for x in t[1:]:
        _comparisons(x, out)


def _get(d, path):
    for p in path:
        d = (d or {}).get(p) if isinstance(d, dict) else None
    return d


def _set(d: dict, path, v) -> dict:
    d = json.loads(json.dumps(d))
    cur = d
    for p in path[:-1]:
        cur = cur.setdefault(p, {})
    cur[path[-1]] = v
    return d


class Synth:
    """S1: a step of one action from a state, by coordinate moves over its input leaves."""

    def __init__(self, model: Model, pools: dict, max_evals: int = 400):
        self.m = model
        self.pools = pools
        self.max_evals = max_evals

    def params(self, a: str) -> list[dict]:
        return self.m.doc.params(a) or []

    def leaves(self, a: str) -> list:
        out = []

        def walk(p, path):
            t = p.get("type", "")
            if t == "tuple":
                for c in p.get("components") or []:
                    walk(c, path + [c["name"]])
            else:
                out.append((("param",) + tuple(path), t))
        for p in self.params(a):
            walk(p, [p["name"]])
        for e in ("caller", "msg.value", "block.timestamp", "blobhash"):
            out.append((("env", e), "env"))
        return out

    def base(self, a: str, prev: Step | None, ts0: int) -> Step:
        args = {}

        def zero(p):
            t = p.get("type", "")
            if t == "tuple":
                return {c["name"]: zero(c) for c in p.get("components") or []}
            if t.endswith("]"):
                return []
            if t in ("bytes", "string"):
                return "0x"
            if t == "bool":
                return False
            return 0
        for p in self.params(a):
            args[p["name"]] = zero(p)
        ts = int((prev.env.get("block.timestamp") if prev else ts0) or ts0)
        callers = self.pools.get("callers") or [0]
        env = {"caller": callers[0], "msg.value": 0, "block.timestamp": ts, "blobhash": [], "calls": []}
        return Step(a, args, env)

    def value_set(self, leaf, ty: str, st: Step, state: dict, prev_ts: int) -> list:
        """Candidate values of one leaf (S1)."""
        kind = leaf[0]
        if kind == "env":
            name = leaf[1]
            if name == "caller":
                return list(self.pools.get("callers") or [])
            if name == "msg.value":
                return sorted({0, 1} | {x for x in self.pools.get("nums", []) if x < 1 << 96})[:64]
            if name == "block.timestamp":
                c = {prev_ts, prev_ts + 1}
                for d in self.pools.get("durs", []):
                    c.add(prev_ts + d + 1)
                    for t in self.pools.get("times", []):
                        if t + d + 1 >= prev_ts:
                            c.add(t + d + 1)
                return sorted(x for x in c if x >= prev_ts and x > 0)
            if name == "blobhash":
                ws = self.pools.get("blobs") or []
                return [[]] + [[w] for w in ws[:8]]
        if ty in ("bytes", "string"):
            return ["0x"] + list(self.pools.get("bytes") or [])
        if ty.endswith("]"):
            return [[]] + [[x] for x in (self.pools.get("nums") or [])[:16]]
        if ty == "bool":
            return [False, True]
        m = re.fullmatch(r"u?int(\d*)", ty)
        bits = int(m.group(1) or 256) if m else 256
        if ty == "address":
            bits = 160
        vals = [x for x in self.pools.get("nums", []) if x < (1 << bits)]
        return vals

    def directed(self, a: str, code: int, st: Step, state: dict) -> dict:
        """Values of the terms the failing check compares a leaf with (holon.extracted_eval over the state)."""
        out: dict = {}
        checks = self.m.doc.program(a).checks()
        if not (0 < code <= len(checks)):
            return out
        c = checks[code - 1]
        cmps: list = []
        _comparisons(c.expr, cmps)
        env = self.m.full_env(st)
        env.setdefault("calls", [])
        try:
            e = EV.Eval(self.m.doc, state, a, st.args, env)
        except Exception:  # noqa: BLE001
            return out
        for op, x, y in cmps:
            for side, other in ((x, y), (y, x)):
                lv: list = []
                _leaves(side, lv)
                if not lv:
                    continue
                try:
                    v = e.as_int(e.ev(other))
                except Exception:  # noqa: BLE001: a term the evaluator cannot decide gives no candidate
                    continue
                for leaf in lv:
                    key = leaf
                    vals = out.setdefault(key, [])
                    for d in (0, 1, -1):
                        w = (v + d) & MASK
                        if w not in vals:
                            vals.append(w)
                    if op in ("fits-",) and side is y:
                        for w in ((v + 1) & MASK,):
                            if w not in vals:
                                vals.append(w)
        return out

    def score(self, code: int, target) -> tuple:
        """Larger is better: success (code 0) above every failing index; a target check index ranks first."""
        if target is not None:
            if code == target:
                return (3, 0)
            if code == 0:
                return (1, 0)
            return (0, code) if code < target else (1, -code)
        if code == 0:
            return (2, 0)
        if code >= FUEL_CODE - 1:
            return (0, -1)
        return (0, code)

    def synth(self, g: str, a: str, prev: Step | None, ts0: int, target=None, accept=None,
              start: Step | None = None, focus: list | None = None) -> tuple[Step | None, int]:
        """A step of action a from state g that succeeds (or, with target, fails exactly at check index target; with
        accept(step, code), any step it accepts)."""
        st = start or self.base(a, prev, ts0)
        state = self.m.state(g)
        prev_ts = int(st.env["block.timestamp"])
        code, _n, _c = self.m.run_step(g, st, save=False)
        best = self.score(code, target)
        evals = 1
        if accept is not None and accept(st, code):
            return st, code
        if accept is None and best[0] >= (3 if target is not None else 2):
            return st, code
        leaves = self.leaves(a)
        tried = set()
        fset = set(focus or [])
        done = (3 if target is not None else 2)

        def directed_of(dv: dict, leaf, ty) -> list:
            d = list(dv.get(self._dkey(leaf), []))
            if leaf[0] == "env" and leaf[1] == "block.timestamp":
                d = [x for x in d if x >= prev_ts and x > 0]
            if ty in ("bytes", "string"):
                d = ["0x%064x" % x if isinstance(x, int) else x for x in d]
            return d

        def ev_(cand):
            nonlocal evals
            k = cand.key()
            if k in tried:
                return None
            tried.add(k)
            c2, _n, _c = self.m.run_step(g, cand, save=False)
            evals += 1
            return c2

        while evals < self.max_evals:
            dvals = self.directed(a, code, st, state)
            order = sorted(leaves, key=lambda lt: (0 if self._dkey(lt[0]) in dvals else 1,
                                                   0 if lt[0] in fset else 1))
            # 1. the directed values of every leaf (the failing check's comparisons): the best of them
            top = None
            seconds = []
            for leaf, ty in order:
                for v in directed_of(dvals, leaf, ty):
                    cand = self.assign(st, leaf, ty, v)
                    if cand is None or evals >= self.max_evals:
                        continue
                    c2 = ev_(cand)
                    if c2 is None:
                        continue
                    if accept is not None and accept(cand, c2):
                        return cand, c2
                    s2 = self.score(c2, target)
                    if s2 > best and (top is None or s2 > top[2]):
                        top = (cand, c2, s2)
                    elif s2 < best:
                        seconds.append((cand, c2, leaf))
            if top is not None:
                st, code, best = top
                if accept is None and best[0] >= done:
                    return st, code
                continue
            # 2. the leaves' value sets: the first move that improves (at a step that already succeeds and is not yet
            # accepted, only the focus leaves: the others change what succeeds, not what is accepted)
            improved = False
            plateau = bool(fset) and accept is not None and code == 0
            for leaf, ty in order:
                if plateau and leaf not in fset:
                    continue
                d = directed_of(dvals, leaf, ty)
                cands = []
                for v in self.value_set(leaf, ty, st, state, prev_ts):
                    if v not in cands and v not in d:
                        cands.append(v)
                for v in cands[:(96 if leaf in fset else 32)]:
                    cand = self.assign(st, leaf, ty, v)
                    if cand is None:
                        continue
                    if evals >= self.max_evals:
                        break
                    c2 = ev_(cand)
                    if c2 is None:
                        continue
                    if accept is not None and accept(cand, c2):
                        return cand, c2
                    s2 = self.score(c2, target)
                    if s2 > best:
                        st, code, best, improved = cand, c2, s2, True
                        break
                    seconds.append((cand, c2, leaf))
                if improved or evals >= self.max_evals:
                    break
            if improved:
                if accept is None and best[0] >= done:
                    return st, code
                continue
            # 3. two coordinates: a move that made an earlier check fail (the latest failing first), then another
            # leaf at that check's directed values or a small value
            if plateau:
                seconds = [t for t in seconds if t[2] in fset]
            seconds.sort(key=lambda t: self.score(t[1], target), reverse=True)
            for cand, c2, leaf in seconds:
                if evals >= self.max_evals:
                    break
                dv2 = self.directed(a, c2, cand, state)
                for leaf2, ty2 in leaves:
                    if leaf2 == leaf:
                        continue
                    vs = directed_of(dv2, leaf2, ty2)
                    if leaf2[0] == "param" and not ty2.endswith("]") and ty2 not in ("bytes", "string", "bool"):
                        vs += [x for x in (0, 1, 2) if x not in vs]
                    for v in vs:
                        c3c = self.assign(cand, leaf2, ty2, v)
                        if c3c is None or evals >= self.max_evals:
                            continue
                        c3 = ev_(c3c)
                        if c3 is None:
                            continue
                        if accept is not None and accept(c3c, c3):
                            return c3c, c3
                        s3 = self.score(c3, target)
                        if s3 > best:
                            st, code, best, improved = c3c, c3, s3, True
                            break
                    if improved:
                        break
                if improved:
                    break
            if not improved:
                break
            if accept is None and best[0] >= done:
                return st, code
        return (st if accept is None and best[0] >= (3 if target is not None else 2) else None), code

    @staticmethod
    def _dkey(leaf):
        if leaf[0] == "env":
            return ("env", "caller") if leaf[1] == "caller" else leaf
        return leaf

    def assign(self, st: Step, leaf, ty: str, v) -> Step | None:
        if leaf[0] == "env":
            name = leaf[1]
            env = dict(st.env)
            env["calls"] = []
            env.pop("_unanswered", None)
            if name == "blobhash":
                env["blobhash"] = v if isinstance(v, list) else [v]
            elif name == "block.timestamp":
                if not isinstance(v, int) or v <= 0:
                    return None
                env[name] = v
            else:
                if not isinstance(v, int):
                    return None
                env[name] = v
            return Step(st.action, st.args, env)
        path = list(leaf[1:])
        if ty in ("bytes", "string") and isinstance(v, int):
            v = "0x%064x" % v
        if ty not in ("bytes", "string") and not ty.endswith("]") and not isinstance(v, (int, bool)):
            return None
        env = dict(st.env)
        env["calls"] = []
        env.pop("_unanswered", None)
        return Step(st.action, _set(st.args, path, v), env)


# ------------------------------------------------------------------------------------------------ pools
_LITERALS: dict = {}


def canonical_step(st) -> str:
    return json.dumps([st.action, st.args, {k: v for k, v in st.env.items() if k != "calls"}], sort_keys=True,
                      default=str)


def doc_literals(doc: dict) -> list[int]:
    key = id(doc)
    if key in _LITERALS and _LITERALS[key][0] is doc:
        return _LITERALS[key][1]
    lits = _doc_literals(doc)
    _LITERALS[key] = (doc, lits)
    return lits


def _doc_literals(doc: dict) -> list[int]:
    out: set = set()
    for a in doc.get("actions") or []:
        _ints([a.get(k) for k in ("guards", "checks", "panics", "writes", "calls", "loops")], out)
    return sorted(x for x in out if x < (1 << 64))


def pools_of(model: Model, trace: list, state: dict, doc: dict, sorts: dict) -> dict:
    nums: set = {0, 1, 2}
    nums |= set(doc_literals(doc)[:200])
    for v in state.values():
        nums.add(v)
    for k in state:
        if k < (1 << 64):
            nums.add(k)
    byts: list = []
    # the preimages of the hashes the state holds first (a header whose hash a commit stored), then the others
    held = set(state.values())
    pre = sorted(model.kh) + sorted(model.sh)
    first = [p for p in pre if model.kh.get(p) in held or model.sh.get(p) in held]
    fs = set(first)
    pre = first + [p for p in pre if p not in fs]
    for p in pre:
        b = bytes.fromhex(p[2:])
        if b not in byts and len(b) <= 512:
            byts.append(b)
        for i in range(0, len(b) - 31, 32):
            nums.add(int.from_bytes(b[i:i + 32], "big"))
    for st in trace:
        _ints(st.args, nums)
        for k in ("caller", "msg.value", "block.timestamp"):
            if isinstance(st.env.get(k), int):
                nums.add(st.env[k])
    nb = set()
    for x in nums:
        for d in (-1, 1):
            if 0 <= x + d <= MASK:
                nb.add(x + d)
    nums |= nb
    small = sorted(x for x in nums if x < (1 << 64))
    big = sorted(x for x in nums if x >= (1 << 64))
    stored = {v for v in state.values() if 0xff < v < (1 << 160)} | set(model.hints.addresses())
    callers = sorted(stored) + sorted({x for x in nums if 0xff < x < (1 << 160)} - stored)
    # durations and times the state holds (the families the frozen assignment sorts Dur / Time)
    durs, times = [], []
    for f, s in sorts.items():
        if "." in f or ":" in f:
            continue
        try:
            fam = model.doc.family(f)
        except Exception:  # noqa: BLE001
            continue
        t = model.doc.type_of(fam.type)
        if t.get("encoding") != "inplace" or "members" in t:
            continue
        v = (state.get(fam.slot, 0) >> (8 * fam.offset)) & ((1 << (8 * int(t["numberOfBytes"]))) - 1)
        if s == "Dur":
            durs.append(v)
        elif s == "Time":
            times.append(v)
    for st in trace:
        times.append(int(st.env.get("block.timestamp") or 0))
    return {"nums": small + big[:64], "bytes": ["0x" + b.hex() for b in byts], "callers": callers[:64],
            "blobs": [x for x in big[:8]], "durs": sorted(set(durs)), "times": sorted(set(times))}


# ------------------------------------------------------------------------------------------------ S1-S3
def _reads(t, out: set) -> None:
    if isinstance(t, list):
        if len(t) == 2 and t[0] == "storage" and isinstance(t[1], str):
            out.add(t[1])
        for x in t:
            _reads(x, out)
    elif isinstance(t, dict):
        for x in t.values():
            _reads(x, out)


def relevance(doc: dict, entry: str) -> list[str]:
    """The state-changing actions (those with a write record), the ones writing most of what the entry point reads
    first (then by name)."""
    acts = {a["name"]: a for a in doc.get("actions") or []}
    reads: set = set()
    _reads(acts[entry], reads)
    rows = []
    for n, a in sorted(acts.items()):
        ws = {w.get("family") for w in a.get("writes") or []}
        if not ws:
            continue
        rows.append((-len(ws & reads), n))
    return [n for _k, n in sorted(rows)]


class Refuter:
    def __init__(self, model: Model, doc: dict, sorts: dict, budget: dict, synth_evals: int = 600,
                 log=None):
        self.m = model
        self.doc = doc
        self.sorts = sorts
        self.budget = dict(budget or {})
        self.synth_evals = synth_evals
        self.log = log or (lambda s: None)
        self.ts0 = int(self.m.init.get("timestamp") or 1) or 1
        self.cache: dict = {}
        self.fp: dict = {}                  # state handle -> fingerprint (successors computes it)

    def pools(self, g: str, trace: list) -> tuple[dict, dict]:
        """(state, pools) of a reachable state (cached: a state handle is never reused for another state)."""
        key = (g, len(self.m.kh), len(self.m.sh))
        hit = self.cache.get(key)
        if hit is None or hit[0] != [canonical_step(st) for st in trace]:
            state = self.m.state(g)
            hit = ([canonical_step(st) for st in trace], state, pools_of(self.m, trace, state, self.doc, self.sorts))
            self.cache[key] = hit
        return hit[1], hit[2]

    def synth(self, g: str, a: str, trace: list, **kw):
        _state, pools = self.pools(g, trace)
        return Synth(self.m, pools, kw.pop("evals", self.synth_evals)).synth(g, a, trace[-1] if trace else None,
                                                                          self.ts0, **kw)

    def accept_for(self, law: dict, entry: str, g: str):
        x = law["law_id"][len("L_sort_"):]
        sub = law["subform"]
        if sub == "realize":
            ks = [self.m.doc.program(entry).checks().index(next(c for c in self.m.doc.program(entry).checks()
                                                                if c.id == h["at"])) + 1
                  for h in law["hits"] if h["action"] == entry and h["kind"] == "realization_check"]
            if ks:
                return None, ks[0], (lambda st, code: code in ks)

        def acc(st, code):
            if code != 0 and sub != "realize":
                return False
            return not self.m.pred(f"coerce_{x}", g, st)
        return acc, None, acc

    def focus_of(self, law: dict, entry: str) -> list:
        """The input leaves a coercion's outcome reads (its member function, its read, and the terms of the hit
        writes of the entry point), from the law's derivation entry and the document: the leaves a search of a step
        that already succeeds varies first."""
        terms = [(law.get("coercion") or {}).get("member_fn"), (law.get("basis") or {}).get("read")]
        act = next((x for x in self.doc.get("actions") or [] if x.get("name") == entry), None) or {}
        for h in law.get("hits") or []:
            m = re.fullmatch(r"(\w+)\[(\d+)\]", str(h.get("at") or ""))
            if h.get("action") == entry and m and m.group(1) in act and int(m.group(2)) < len(act[m.group(1)]):
                terms.append(act[m.group(1)][int(m.group(2))])
        out: list = []

        def walk(t):
            if isinstance(t, list) and t:
                if t[0] == "param" and len(t) == 2 and isinstance(t[1], str):
                    leaf = ("param", t[1])
                elif t[0] == "member" and len(t) == 3 and isinstance(t[2], str) and isinstance(t[1], list) \
                        and t[1][:1] == ["param"] and len(t[1]) == 2:
                    leaf = ("param", t[1][1], t[2])
                elif t[0] == "blobhash":
                    leaf = ("env", "blobhash")
                else:
                    leaf = None
                if leaf is not None and leaf not in out:
                    out.append(leaf)
                for y in t[1:]:
                    walk(y)
            elif isinstance(t, dict):
                for y in t.values():
                    walk(y)
        for t in terms:
            walk(t)
        return out

    def entry_at(self, law: dict, entry: str, g: str, trace: list):
        _acc, target, accept = self.accept_for(law, entry, g)
        focus = self.focus_of(law, entry) if target is None else None
        st, code = self.synth(g, entry, trace, target=target, accept=accept, focus=focus)
        return st

    def successors(self, g: str, trace: list, entry: str, limit: int, variants: int = 3) -> list:
        """Successful steps from state g, a few per action (distinct post-states), the most relevant actions first."""
        out = []
        for a in relevance(self.doc, entry):
            if len(out) >= limit:
                break
            st, code = self.synth(g, a, trace)
            if st is None or code != 0:
                continue
            seen = set()
            kept = []
            cands = [st]
            state, pools = self.pools(g, trace)
            sy = Synth(self.m, pools, 0)
            for leaf, ty in sy.leaves(a):
                if leaf[0] == "env" and leaf[1] in ("msg.value",):
                    continue
                vals = sy.value_set(leaf, ty, st, state, int(st.env["block.timestamp"]))[:6]
                for v in vals:
                    c = sy.assign(st, leaf, ty, v)
                    if c is not None:
                        cands.append(c)
            for c in cands:
                if len(kept) >= variants or len(out) + len(kept) >= limit:
                    break
                code, g2, _calls = self.m.run_step(g, c, save=True)
                if code != 0:
                    self.m.drop([g2])
                    continue
                h = self.m.fingerprint(g2)
                if h in seen:
                    self.m.drop([g2])
                    continue
                seen.add(h)
                self.fp[g2] = h
                kept.append((trace + [c], g2))
            out += kept
        return out

    def refute(self, law: dict, entry: str, others: dict | None = None) -> tuple[list | None, str, str]:
        """(witness steps, stage, bound) for one entry point."""
        depth = int(self.budget.get("prefix_depth", 2))
        maxp = int(self.budget.get("max_prefixes", 1000))
        g0 = self.m.s0()
        tried = 1
        st = self.entry_at(law, entry, g0, [])
        if st is not None:
            self.log(f"  {entry}: witness at depth 0")
            return [st], "S1", f"S1+S2: 1 prefix (depth <= {depth})"
        # breadth first: the prefixes of depth d are tried in their parents' order, each parent's successors
        # generated when its turn comes (a parent whose turn never comes is never expanded)
        level = [([], g0)]
        # a state reached again (its storage, ghost store and clock) is the state already tried: the budget counts
        # states, as I15's stages do
        seen = {(self.m.fingerprint(g0), self.ts0)}
        for d in range(1, depth + 1):
            nxt = []
            for trace, g in level:
                if tried >= maxp:
                    break
                for t2, g2 in self.successors(g, trace, entry, maxp - tried):
                    key = (self.fp.get(g2) or self.m.fingerprint(g2), int(t2[-1].env.get("block.timestamp") or 0))
                    if key in seen:
                        continue
                    seen.add(key)
                    tried += 1
                    st = self.entry_at(law, entry, g2, t2)
                    if st is not None:
                        self.log(f"  {entry}: witness at depth {d} after {tried} prefixes")
                        return t2 + [st], "S2", f"S1+S2: {tried} distinct states (depth <= {depth})"
                    nxt.append((t2, g2))
                    if tried >= maxp:
                        break
            self.log(f"  {entry}: depth {d}: {tried} prefixes tried "
                     f"({', '.join(sorted({t[-1].action for t, _g in nxt}))[:200]})")
            level = nxt
            if tried >= maxp or not level:
                break
        bound = f"S1+S2: {tried} distinct states of at most {depth} successful steps (max {maxp}), no witness"
        # S3: the other entry points' witnesses, steps inserted, the last step replaced by this entry point's
        ins = int(self.budget.get("neighbourhood_insertion_length_max", 2))
        maxn = int(self.budget.get("neighbourhood_prefixes_per_entry_point_max", 1000))
        n3 = 0
        for other, steps in sorted((others or {}).items()):
            if other == entry or not steps:
                continue
            base = steps[:-1]
            g = self.m.s0()
            ok = True
            hs = [g]
            for st in base:
                code, g, _c = self.m.run_step(g, st, save=True)
                hs.append(g)
                ok &= code == 0
            if not ok:
                continue
            cands = [(base, g)]
            frontier = [(base, g)]
            for _k in range(ins):
                new = []
                for trace, gg in frontier:
                    for t2, g2 in self.successors(gg, trace, entry, maxn - n3):
                        new.append((t2, g2))
                cands += new
                frontier = new
            for trace, gg in cands:
                if n3 >= maxn:
                    break
                n3 += 1
                st = self.entry_at(law, entry, gg, trace)
                if st is not None:
                    return trace + [st], "S3", bound + f"; S3: {n3} neighbourhood prefixes"
        return None, "S3" if others else "S2", bound + (f"; S3: {n3} neighbourhood prefixes, no witness" if others
                                                        else "")

    def inhabit(self, law: dict) -> list | None:
        """A reachable trace whose last step reaches a hit (chit_<x>): the non-vacuity witness of a PROVED law."""
        x = law["law_id"][len("L_sort_"):]
        depth = int(self.budget.get("prefix_depth", 2))
        for entry in law["entry_points"]:
            frontier = [([], self.m.s0())]
            for d in range(depth + 1):
                nxt = []
                for trace, g in frontier:
                    def acc(st, code, g=g):
                        return self.m.pred(f"chit_{x}", g, st)
                    st, _c = self.synth(g, entry, trace, accept=acc)
                    if st is not None:
                        return trace + [st]
                    if d < depth:
                        nxt += self.successors(g, trace, entry, 40)
                frontier = nxt
        return None


def settle(model_factory, steps: list, fns: list) -> tuple[dict, dict, list]:
    """The witness's hash tables: the real hash of exactly the keys its trace (and the given predicates on its last
    step) looks up, from empty tables (a fixpoint on a fresh model)."""
    m = model_factory(empty=True)
    g = m.s0()
    codes = []
    for st in steps[:-1]:
        code, g, _c = m.run_step(g, st, save=True)
        codes.append(code)
    code, _g2, _c = m.run_step(g, steps[-1], save=False)
    codes.append(code)
    vals = [m.pred(fn, g, steps[-1]) for fn in fns]
    # one more pass with the final tables: nothing new may appear
    g = m.s0()
    for st in steps[:-1]:
        _code, g, _c = m.run_step(g, st, save=True)
    for fn in fns:
        m.pred(fn, g, steps[-1])
    return dict(m.kh), dict(m.sh), codes + vals
