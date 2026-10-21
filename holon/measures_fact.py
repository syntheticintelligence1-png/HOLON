"""The FACT measure F(m, c) of a kernel basis element (BUILD_PLAN I26; whitepaper Def 6.13, Thm 6.8; the contract is
the docstring of tests_m3/test_fact.py, rule F9).

F(m, c) = max over committed values mu of log2 |c(m^-1(mu) n R)|. The commitment's value is a hash of a memory region;
V is the list of the region's cells (mstore values, mloop blocks) that hold a blob term. Under CF, two steps with equal
commitments and equal other inputs differ only in what V reads of the blobs, so the fiber of a committed value is the
set of admissible blob lists B with equal (context, V(B)).

  atoms        the maximal subterms of V and of the evaluable guards that are not literals, blob terms, operators,
               hashes of regions or iter; an atom's candidates: 0 and c - 1, c, c + 1 for every integer literal c it is
               compared with (those >= 0)
  evaluable    every guard reach and check of the action that holds a blob term and only terms this module interprets
               (the others are "unevaluated"), plus those holding no blob term whose atoms are all atoms already found
  domain       the alphabet (the document's constants that are admissible blob hashes, plus the sidecar's fresh words)
               and the lists of length 0..max_length over it; ["blobhash", i] reads B[i] or 0; a blob loop's count is the
               first iteration at which its break holds; a hash of a region is an injective symbolic image of its cells

Over every context (a candidate per atom) and every list satisfying the evaluable guards the lists are grouped by
(context, V(B)): max_fiber is the largest group, bits log2 of it (6 decimals), max_fibers every largest group (in the
order of their canonical JSON).

Nothing here names a target: every action, term, constant and span comes from the document.
"""
from __future__ import annotations

import itertools
import json
import math

HASHES = ("keccak256", "sha256")
OPS = ("?", "==", "!=", "!", "||", "&&", "<", "<=", ">", ">=", "+", "-", "*")
CMP = ("==", "!=", "<", "<=", ">", ">=")
SCAN = ("guards", "checks", "panics", "calls", "writes", "events", "mstores", "loops")
MOD = 1 << 256


class Uninterpreted(ValueError):
    """A term the measure does not interpret."""


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def is_op(t, op=None) -> bool:
    return isinstance(t, list) and bool(t) and isinstance(t[0], str) and (op is None or t[0] == op)


def is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def word_hex(n: int) -> str:
    return "0x%064x" % n


def admissible_hash(n: int) -> bool:
    """An admissible blob versioned hash: a nonzero word whose top byte is 0x01 (EIP-4844, rule F8 blobs_wf)."""
    return is_int(n) and 0 < n < MOD and (n >> 248) == 1


def _int(v):
    if is_int(v):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        try:
            return int(s, 16) if s.startswith("0x") else int(s)
        except ValueError:
            return None
    return None


def contains_head(t, head: str) -> bool:
    if isinstance(t, list):
        if t and t[0] == head:
            return True
        return any(contains_head(x, head) for x in t)
    if isinstance(t, dict):
        return any(contains_head(x, head) for x in t.values())
    return False


class Action:
    """One action's blob loops and region structure."""

    def __init__(self, action: dict):
        self.a = action
        self.loops = {lp.get("src"): lp for lp in action.get("loops") or [] if contains_head(lp.get("break"), "blobhash")}

    def is_blob(self, t) -> bool:
        """A blob term: ["blobhash", i] or a blob loop's ["count", span]."""
        return is_op(t, "blobhash") or (is_op(t, "count") and len(t) == 2 and t[1] in self.loops)

    def holds_blob(self, t) -> bool:
        if self.is_blob(t):
            return True
        if isinstance(t, list):
            return any(self.holds_blob(x) for x in t)
        return False

    @staticmethod
    def region_cells(t):
        """The cells of a hash of a memory region ["keccak256" | "sha256", ["slice", ["mem", cells..], off, len]], or
        None."""
        if is_op(t) and t[0] in HASHES and len(t) == 2 and is_op(t[1], "slice") and len(t[1]) == 4 \
                and is_op(t[1][1], "mem"):
            return list(t[1][1][1:])
        return None

    # ---------------------------------------------------------- atoms
    def atoms(self, t, out: dict) -> bool:
        """Collect the atoms of t into out (canonical key -> term); False when t holds a term that is not interpreted
        and holds a blob term."""
        if is_int(t) or self.is_blob(t) or is_op(t, "iter"):
            return True
        if is_op(t) and t[0] in OPS:
            return all(self.atoms(x, out) for x in t[1:])
        cells = self.region_cells(t)
        if cells is not None:
            ok = self.cells_atoms(cells, out)
            return self.atoms(t[1][2], out) and self.atoms(t[1][3], out) and ok
        if self.holds_blob(t):
            return False
        out[canon(t)] = t
        return True

    def cells_atoms(self, cells: list, out: dict) -> bool:
        ok = True
        for c in cells:
            ok = self.cell_atoms(c, out) and ok
        return ok

    def cell_atoms(self, c, out: dict) -> bool:
        if is_op(c, "mstore") or is_op(c, "mstore8"):
            return self.atoms(c[1], out) and self.atoms(c[2], out)
        if is_op(c, "when") and len(c) == 3:
            return self.atoms(c[1], out) and self.cell_atoms(c[2], out)
        if is_op(c, "mloop") and len(c) == 5:
            return self.atoms(c[3], out) and self.cells_atoms(c[4], out)
        if self.holds_blob(c):
            return False
        out[canon(c)] = c
        return True

    # ---------------------------------------------------------- compared literals
    @staticmethod
    def compared(t, keys: set, out: dict) -> None:
        if isinstance(t, list):
            if is_op(t) and t[0] in CMP and len(t) == 3:
                for x, y in ((t[1], t[2]), (t[2], t[1])):
                    if is_int(y) and not is_int(x) and canon(x) in keys:
                        out.setdefault(canon(x), set()).add(y)
            for x in t:
                Action.compared(x, keys, out)

    # ---------------------------------------------------------- evaluation
    def ev(self, t, env: dict):
        if is_int(t):
            return t
        if isinstance(t, bool):
            return int(t)
        k = canon(t)
        if k in env["atoms"]:
            return env["atoms"][k]
        if is_op(t, "blobhash"):
            i = self.ev(t[1], env)
            B = env["B"]
            return B[i] if is_int(i) and 0 <= i < len(B) else 0
        if is_op(t, "count") and len(t) == 2 and t[1] in self.loops:
            return self.count(t[1], env)
        if is_op(t, "iter") and len(t) == 2:
            if t[1] not in env["iter"]:
                raise Uninterpreted(f"iter {t[1]} outside its loop")
            return env["iter"][t[1]]
        cells = self.region_cells(t)
        if cells is not None:
            return ("H", t[0], tuple(self.ev_cells(cells, env)), self.ev(t[1][2], env), self.ev(t[1][3], env))
        if is_op(t) and t[0] in OPS:
            return self.op(t, env)
        raise Uninterpreted(canon(t)[:200])

    def count(self, span: str, env: dict) -> int:
        lp = self.loops[span]
        limit = len(env["B"]) + 1
        for i in range(limit + 1):
            e2 = dict(env, iter=dict(env["iter"], **{span: i}))
            if truth(self.ev(lp.get("break"), e2)):
                return i
        raise Uninterpreted(f"the blob loop {span} does not break within the list")

    def ev_cells(self, cells: list, env: dict) -> list:
        out = []
        for c in cells:
            out += self.ev_cell(c, env)
        return out

    def ev_cell(self, c, env: dict) -> list:
        if is_op(c, "mstore") or is_op(c, "mstore8"):
            return [(c[0], self.ev(c[1], env), self.ev(c[2], env))]
        if is_op(c, "when") and len(c) == 3:
            return self.ev_cell(c[2], env) if truth(self.ev(c[1], env)) else []
        if is_op(c, "mloop") and len(c) == 5:
            span, n = c[1], self.ev(c[3], env)
            if not is_int(n) or n < 0:
                raise Uninterpreted("an mloop count that is not a number")
            out = []
            for i in range(n):
                e2 = dict(env, iter=dict(env["iter"], **{span: i}))
                out += self.ev_cells(c[4], e2)
            return out
        return [("cell", self.ev(c, env))]

    def op(self, t, env: dict):
        o = t[0]
        if o == "?":
            return self.ev(t[2], env) if truth(self.ev(t[1], env)) else self.ev(t[3], env)
        if o == "!":
            return int(not truth(self.ev(t[1], env)))
        if o == "&&":
            return int(all(truth(self.ev(x, env)) for x in t[1:]))
        if o == "||":
            return int(any(truth(self.ev(x, env)) for x in t[1:]))
        a, b = self.ev(t[1], env), self.ev(t[2], env)
        if o == "==":
            return int(a == b)
        if o == "!=":
            return int(a != b)
        if not (is_int(a) and is_int(b)):
            raise Uninterpreted(f"{o} of a hash image")
        if o == "<":
            return int(a < b)
        if o == "<=":
            return int(a <= b)
        if o == ">":
            return int(a > b)
        if o == ">=":
            return int(a >= b)
        if o == "+":
            return (a + b) % MOD
        if o == "-":
            return (a - b) % MOD
        if o == "*":
            return (a * b) % MOD
        raise Uninterpreted(o)


def truth(v) -> bool:
    if isinstance(v, tuple):
        return True
    return bool(v)


def _site_value(action: dict, at: str):
    i = int(at[len("writes["):-1])
    return action["writes"][i]["value"]


def measure(doc: dict, action: dict, at: str, fresh: list, max_length: int) -> dict:
    """Rule F9 for the kernel basis element of `action`'s commitment write `at`."""
    A = Action(action)
    value = _site_value(action, at)
    cells = A.region_cells(value)
    V = [c for c in (cells or []) if A.holds_blob(c)]
    found: dict = {}
    for c in V:
        if not A.cell_atoms(c, found):
            raise Uninterpreted("a cell of V holds a term the measure does not interpret")
    exprs = []   # (label, expr) of every guard reach and check
    for gi, g in enumerate(action.get("guards") or []):
        for ri, r in enumerate(g.get("reaches") or []):
            exprs.append((f"guards[{gi}].reaches[{ri}]", r.get("expr")))
    for ci, c in enumerate(action.get("checks") or []):
        exprs.append((f"checks[{ci}]", c.get("expr")))
    evaluable, unevaluated = [], []
    for label, e in exprs:
        if not A.holds_blob(e):
            continue
        at_ = {}
        if A.atoms(e, at_):
            evaluable.append((label, e))
            found.update(at_)
        else:
            unevaluated.append(label)
    for label, e in exprs:
        if A.holds_blob(e):
            continue
        at_ = {}
        if A.atoms(e, at_) and all(k in found for k in at_):
            evaluable.append((label, e))
    keys = set(found)
    lits: dict = {}
    for c in V:
        Action.compared(c, keys, lits)
    for _l, e in evaluable:
        Action.compared(e, keys, lits)
    cands = {}
    for k in sorted(found):
        s = {0}
        for c in lits.get(k, ()):
            s |= {x for x in (c - 1, c, c + 1) if x >= 0}
        cands[k] = sorted(s)
    alphabet = set()
    for v in (doc.get("constants") or {}).values():
        n = _int(v)
        if n is not None and admissible_hash(n):
            alphabet.add(n)
    for v in fresh:
        n = _int(v)
        if n is not None and admissible_hash(n):
            alphabet.add(n)
    alpha = sorted(alphabet, key=word_hex)
    lists = [list(x) for n in range(max_length + 1) for x in itertools.product(alpha, repeat=n)]
    atom_keys = sorted(found)
    groups: dict = {}
    for combo in itertools.product(*[cands[k] for k in atom_keys]):
        ctx = list(zip(atom_keys, combo))
        env0 = {"atoms": dict(ctx), "iter": {}}
        for B in lists:
            env = dict(env0, B=B)
            if not all(truth(A.ev(e, env)) for _l, e in evaluable):
                continue
            vb = tuple(tuple(A.ev_cell(c, env)) for c in V)
            key = (canon([list(p) for p in ctx]), repr(vb))
            groups.setdefault(key, (ctx, []))[1].append(B)
    if not groups:
        raise Uninterpreted("no admissible blob list satisfies the evaluable guards")
    mx = max(len(g[1]) for g in groups.values())
    fibers = []
    for ctx, ls in groups.values():
        if len(ls) == mx:
            fibers.append({"context": sorted([k, v] for k, v in ctx),
                           "lists": sorted([word_hex(h) for h in B] for B in ls)})
    fibers.sort(key=canon)
    return {"bits": round(math.log2(mx), 6), "max_fiber": mx, "max_fibers": fibers,
            "domain": {"alphabet": [word_hex(h) for h in alpha], "max_length": max_length, "atoms": cands},
            "unevaluated": sorted(unevaluated)}
