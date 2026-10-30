"""Rule IS2 (BUILD_PLAN I83; the contract is the docstring of tests_m3/test_versions_debt.py): the candidate generator of
an in-flight inhabitant's commit, over the versioned machine's untyped modules (holon.versions.machine), with the rules
and budget of the sidecar spec/<M>/lib/inflight_search.json.

A call of an action at a state is synthesized from its start (every word leaf 0, every bytes or string leaf empty, every
array empty; a bytes leaf that an abi.decode term of the action decodes holds the canonical ABI encoding of the decoded
types, every word 0 and every array empty) by moves directed by the first failing check of its run on the versioned
machine: for each comparison of the check's expression, in term order, a side that reads one leaf of the call in a form
below gets the candidates that make it meet the other side's value v (evaluated by holon.extracted_eval's evaluator over
the version's document, extended by model3's L1-L5 terms, every external call answered as the machine's A-env answers
it: candidates, never evidence):
  a word leaf X:                      v, v + 1, v - 1
  len(X), X bytes:                    X cut or extended with zero bytes to v, v + 1, v - 1 bytes (below 2^16)
  a 32-byte read of X at a literal offset o, shifted right by a literal s or not (["word", X, o]; L3's read of X's
  memory copy; L4's calldataload of X):  the (256 - s) / 8 bytes of X at o set to v, v + 1, v - 1 (big-endian)
  keccak256(X):                       every byte string the trace has hashed whose keccak256 is v
A candidate is taken when its run fails at a later check or succeeds; when no candidate of the failing check is taken,
the synthesis by that caller fails. Nothing here names a target: every name comes from the document and the sidecars.
"""
from __future__ import annotations

import copy
import json
import re

from .. import extracted_eval as EV
from ..sorts.model3 import TOP_CODE, decode_shape
from .machine import Machine, STANDIN_ANSWER, cd_bytes, num, storage_of

MASK = (1 << 256) - 1
CMP = ("==", "!=", "<", "<=", ">", ">=")
_VALUE = re.compile(r"^(u?int\d*|address|bool|bytes\d+)$")


def _input_path(t) -> tuple | None:
    """(param, member, ..) of an entry parameter or a member of one, else None."""
    if not isinstance(t, list) or len(t) < 2:
        return None
    if t[0] == "param" and isinstance(t[1], str):
        return (t[1],)
    if t[0] == "member" and len(t) == 3 and isinstance(t[2], str):
        p = _input_path(t[1])
        return p + (t[2],) if p else None
    return None


def _sum_terms(t) -> list:
    if isinstance(t, list) and len(t) == 3 and t[0] == "+":
        return _sum_terms(t[1]) + _sum_terms(t[2])
    return [t]


def _lit(t) -> bool:
    return isinstance(t, int) and not isinstance(t, bool)


def leaf_types(params: list) -> dict:
    """{path: ABI type} of every leaf of the parameters (a tuple's components flattened; an array is one leaf)."""
    out = {}

    def walk(p, path):
        if p.get("type") == "tuple":
            for c in p.get("components") or []:
                walk(c, path + (c["name"],))
        else:
            out[path] = p.get("type", "")
    for p in params:
        walk(p, (p["name"],))
    return out


def zero(params: list) -> dict:
    def z(p):
        t = p.get("type", "")
        if t == "tuple":
            return {c["name"]: z(c) for c in p.get("components") or []}
        if t.endswith("]"):
            return []
        if t in ("bytes", "string"):
            return b""
        if t == "bool":
            return False
        return 0
    return {p["name"]: z(p) for p in params}


def get(values: dict, path: tuple):
    v = values
    for k in path:
        v = v[k]
    return v


def put(values: dict, path: tuple, x) -> dict:
    out = copy.deepcopy(values)
    v = out
    for k in path[:-1]:
        v = v[k]
    v[path[-1]] = x
    return out


def canonical_encoding(shape: list) -> bytes:
    """The ABI encoding of a decode's types with every word 0 and every array empty."""
    n = len(shape)
    head, tail = b"", b""
    for kind, _ty in shape:
        if kind == "a":
            head += (32 * n + len(tail)).to_bytes(32, "big")
            tail += (0).to_bytes(32, "big")
        else:
            head += bytes(32)
    return head + tail


def _walk(t, f):
    if isinstance(t, list):
        f(t)
        for x in t:
            _walk(x, f)
    elif isinstance(t, dict):
        for x in t.values():
            _walk(x, f)


def decode_starts(action: dict) -> dict:
    """{path: canonical encoding} of the bytes leaves an abi.decode term of the action decodes."""
    out = {}

    def f(t):
        if t and t[0] == "abi.decode" and len(t) == 3:
            p, shape = _input_path(t[1]), decode_shape(t[2])
            if p and shape is not None:
                out.setdefault(p, canonical_encoding(shape))
    _walk(action, f)
    return dict(sorted(out.items()))


def comparisons(t, out: list) -> list:
    """The comparisons [op, L, R] of a term, in term order (outer first)."""
    if isinstance(t, list) and t and isinstance(t[0], str):
        if t[0] in CMP and len(t) == 3:
            out.append(t)
        for x in t[1:]:
            comparisons(x, out)
    elif isinstance(t, list):
        for x in t:
            comparisons(x, out)
    return out


def encodable(values: dict, params: list) -> dict:
    """The values as holon.evm_abi encodes them: a word leaf of type bytesN as its N left bytes in hex (its other bytes
    must be zero), of type intN as a signed int; every other leaf as it is."""
    def enc(p, v):
        t = p.get("type", "")
        if t == "tuple":
            return {c["name"]: enc(c, v[c["name"]]) for c in p.get("components") or []}
        m = re.fullmatch(r"bytes(\d+)", t)
        if m and isinstance(v, int):
            n = int(m.group(1))
            b = (v & MASK).to_bytes(32, "big")
            if any(b[n:]):
                raise ValueError(f"a {t} word with nonzero low bytes")
            return "0x" + b[:n].hex()
        if re.fullmatch(r"int\d*", t) and isinstance(v, int):
            v &= MASK
            return v - (1 << 256) if v >> 255 else v
        return v
    return {p["name"]: enc(p, values[p["name"]]) for p in params}


# ------------------------------------------------------------------------------------------------ the move evaluator
class MoveEval(EV.Eval):
    """holon.extracted_eval's evaluator, extended by model3's L1-L5 terms, with every external call answered as the
    versioned machine's A-env answers it (the labelled stand-in: success, the ABI word 1)."""

    def answer(self, fn, receiver, raw):
        return True, STANDIN_ANSWER, (self.m.call_signature(fn) if hasattr(self.m, "call_signature") else None)

    def _bytes_leaf(self, t) -> bytes | None:
        p = _input_path(t)
        if p is None:
            return None
        v = self.ev(t)
        return bytes(v) if isinstance(v, (bytes, bytearray)) else None

    def _split(self, t, want):
        """(X, offset) of a sum holding exactly one input bytes value X (want: its form), the other summands words."""
        xs, rest = [], []
        for s in _sum_terms(t):
            b = want(s)
            (xs if b is not None else rest).append((s, b))
        if len(xs) != 1:
            raise EV.Unsupported("not a pointer into one input bytes value")
        return xs[0][1], sum(self.iv(s) for s, _b in rest) & MASK

    def t_mload(self, t):
        if isinstance(t[1], list) and t[1][:1] == ["unknown"]:
            x, off = self._split(t[2], self._bytes_leaf)
            copy_ = len(x).to_bytes(32, "big") + x
            return int.from_bytes(copy_[off:off + 32].ljust(32, b"\0"), "big")
        return super().t_mload(t)

    def t_calldataload(self, t):
        def cd(s):
            return self._bytes_leaf(s[1]) if isinstance(s, list) and s[:1] == ["cdoff"] and len(s) == 2 else None
        x, off = self._split(t[1], cd)
        return int.from_bytes(x[off:off + 32].ljust(32, b"\0"), "big")

    def t_abi_decode(self, t):
        shape = decode_shape(t[2])
        if shape is None:
            raise EV.Unsupported("an abi.decode of other types")
        d = self.as_bytes(self.ev(t[1]))

        def word(o):
            return int.from_bytes(d[o:o + 32].ljust(32, b"\0"), "big")
        out = []
        for i, (kind, _ty) in enumerate(shape):
            if kind == "v":
                out.append(word(32 * i))
            else:
                off = word(32 * i)
                n = word(off) if off < len(d) else 0
                out.append([word(off + 32 + 32 * j) for j in range(min(n, max(0, (len(d) - off) // 32)))])
        return out


# ------------------------------------------------------------------------------------------------ the synthesis
class Synth:
    """IS2 over one versioned machine."""

    def __init__(self, m: Machine, side: dict, log=None):
        self.m = m
        self.side = side
        self.max_evals = int(side.get("max_evals", 400))
        self.log = log or (lambda s: None)

    def callers(self) -> list:
        out = []
        for c in self.m.dep.get("calls") or []:
            a = num(c["caller"])
            if a != self.m.admin and a not in out:
                out.append(a)
        return out

    def run(self, vid: str, action: str, state: dict, caller: int, values: dict) -> tuple[int, dict | None, str]:
        """(score, the run, calldata): the run's code 0 scores highest, a failing check its index, anything else -1."""
        try:
            cd = self.m.calldata(vid, action, encodable(values, self.m.function(vid, action)["inputs"]))
            r = self.m.run_action(vid, action, state["sl"], caller, cd)
        except Exception as e:  # noqa: BLE001  (a candidate the encoder or the machine cannot run is no candidate)
            self.log(f"  candidate not run: {type(e).__name__}: {str(e)[:160]}")
            return -1, None, ""
        if r["status"] == "ok":
            return 1 << 40, r, cd
        c = int(r.get("code") or 0)
        return (c if 0 < c < TOP_CODE else -1), r, cd

    def env(self, vid: str, action: str, caller: int, cd: str) -> dict:
        e = self.m.env(vid, action, caller, cd)
        e = dict(e)
        e["blobhash"] = []
        e["calls"] = []
        return e

    def other_value(self, vid: str, action: str, state: dict, caller: int, values: dict, cd: str, term):
        try:
            ev = MoveEval(self.m.extracted(vid), {hex(k): hex(v) for k, v in storage_of(state["sl"]).items()}, action,
                          values, self.env(vid, action, caller, cd))
            return ev.as_int(ev.ev(term)) & MASK
        except Exception:  # noqa: BLE001  (a side the evaluator cannot decide gives no candidate)
            return None

    def moves(self, vid: str, action: str, state: dict, caller: int, values: dict, cd: str, expr, types: dict,
              hashed: dict) -> list:
        """Candidate argument values for the failing check's expression (the module's rules)."""
        out = []
        for op, left, right in [(c[0], c[1], c[2]) for c in comparisons(expr, [])]:
            for side, other in ((left, right), (right, left)):
                cands = self.side_moves(side, values, types, hashed,
                                        lambda: self.other_value(vid, action, state, caller, values, cd, other))
                for c in cands:
                    if c not in out:
                        out.append(c)
        return out

    def side_moves(self, side, values: dict, types: dict, hashed: dict, value) -> list:
        p = _input_path(side)
        if p is not None and p in types and _VALUE.match(types[p]):
            v = value()
            return [] if v is None else [put(values, p, (v + d) & MASK) for d in (0, 1, -1)]
        if isinstance(side, list) and len(side) == 2 and side[0] == "len":
            p = _input_path(side[1])
            if p in types and types[p] in ("bytes", "string"):
                v = value()
                if v is None:
                    return []
                cur = bytes(get(values, p))
                out = []
                for d in (0, 1, -1):
                    n = v + d
                    if 0 <= n < (1 << 16):
                        out.append(put(values, p, cur[:n] + bytes(max(0, n - len(cur)))))
                return out
        if isinstance(side, list) and len(side) == 2 and side[0] == "keccak256":
            p = _input_path(side[1])
            if p in types and types[p] in ("bytes", "string"):
                v = value()
                if v is None:
                    return []
                return [put(values, p, bytes.fromhex(k[2:])) for k, w in sorted(hashed.items()) if w == v]
        shift, read = 0, side
        if isinstance(side, list) and len(side) == 3 and side[0] == ">>" and _lit(side[2]):
            shift, read = side[2], side[1]
        loc = self.read_location(read, types)
        if loc is None or not 0 <= shift < 256 or shift % 8:
            return []
        p, o = loc
        v = value()
        if v is None:
            return []
        width = (256 - shift) // 8
        cur = bytes(get(values, p))
        out = []
        for d in (0, 1, -1):
            x = ((v + d) % (1 << (8 * width))).to_bytes(width, "big")
            b = bytearray(cur.ljust(o + width, b"\0"))
            b[o:o + width] = x
            out.append(put(values, p, bytes(b)))
        return out

    @staticmethod
    def read_location(t, types: dict) -> tuple | None:
        """(path, data offset) of a 32-byte read of one input bytes leaf at a literal offset, else None."""
        if not isinstance(t, list) or not t:
            return None

        def pointer(addr, sub: int, want):
            xs, lits = [], 0
            for s in _sum_terms(addr):
                q = want(s)
                if q is not None:
                    xs.append(q)
                elif _lit(s):
                    lits += s
                else:
                    return None
            if len(xs) != 1 or lits - sub < 0:
                return None
            return xs[0], lits - sub

        def bytes_leaf(s):
            p = _input_path(s)
            return p if p in types and types[p] in ("bytes", "string") else None
        if t[0] == "word" and len(t) == 3 and _lit(t[2]):
            p = bytes_leaf(t[1])
            return (p, t[2]) if p else None
        if t[0] == "mload" and len(t) == 3 and isinstance(t[1], list) and t[1][:1] == ["unknown"]:
            return pointer(t[2], 32, bytes_leaf)
        if t[0] == "calldataload" and len(t) == 2:
            return pointer(t[1], 0, lambda s: bytes_leaf(s[1]) if isinstance(s, list) and s[:1] == ["cdoff"] else None)
        return None

    def synthesize(self, vid: str, action: str, state: dict, hashed: dict) -> tuple[dict | None, list]:
        """(the successful call step, or None; what was tried) of an action at a state."""
        fn = self.m.function(vid, action)
        if fn is None:
            return None, [f"{vid} {action}: not a compiled action"]
        params = fn["inputs"]
        types = leaf_types(params)
        start = zero(params)
        for p, enc in decode_starts(self.m.extracted(vid).actions.get(action) or {}).items():
            if p in types:
                start = put(start, p, enc)
        checks = self.m.extracted(vid).program(action).checks()
        tried = []
        for caller in self.callers():
            values, evals = start, 0
            score, run, cd = self.run(vid, action, state, caller, values)
            evals += 1
            while evals < self.max_evals:
                if run is not None and run["status"] == "ok":
                    return self.m.call_step(vid, action, caller, cd), tried
                if not 0 < score <= len(checks):
                    tried.append(f"caller 0x{caller:040x}: the run fails outside the document's checks (code "
                                 f"{run.get('code') if run else None})")
                    break
                cands = self.moves(vid, action, state, caller, values, cd, checks[score - 1].expr, types,
                                   {**hashed, **(run.get("kh") or {})})
                taken = None
                for c in cands:
                    if evals >= self.max_evals:
                        break
                    s2, r2, cd2 = self.run(vid, action, state, caller, c)
                    evals += 1
                    if s2 > score:
                        taken = (c, s2, r2, cd2)
                        break
                if taken is None:
                    tried.append(f"caller 0x{caller:040x}: no candidate passes check {score} ({checks[score - 1].id}) "
                                 f"after {evals} runs")
                    break
                values, score, run, cd = taken
                self.log(f"  {vid} {action}: check {score if score < (1 << 40) else 'none'} after {evals} runs")
            else:
                tried.append(f"caller 0x{caller:040x}: the budget of {self.max_evals} runs is spent")
        return None, tried


def load_side(ctx) -> dict:
    """The search sidecar spec/<M>/lib/inflight_search.json (an empty dict when there is none: the defaults)."""
    p = ctx.root / "spec" / ctx.milestone / "lib" / "inflight_search.json"
    if not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def committed_key(m: Machine, vid: str, family: str, run: dict) -> int | None:
    """The mapping key of the entry of `family` (a commitment family of PI1) a successful run writes, read from its
    writes and the keccak256 preimages it looked up (the family's base slot in the version's layout: I63's history)."""
    lay = [e for e in m.ctx.version(vid)["layout"] if e["label"] == family]
    if len(lay) != 1:
        return None
    base = int(lay[0]["slot"])
    written = set((run.get("writes") or {}).keys())
    for k, v in sorted((run.get("kh") or {}).items()):
        b = cd_bytes(k)
        if len(b) == 64 and int.from_bytes(b[32:], "big") == base and v in written:
            return int.from_bytes(b[:32], "big")
    return None
