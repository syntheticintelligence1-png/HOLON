"""Bounded model checking over the TRANS edges of a transitions document (holon-facts/0.3; I40, whitepaper §10.5 and
§10.9; spec/M3/lib/refute.json "bmc").

From R0 (the binding's deployment, or the zero storage for a milestone without one), BMC asks z3 for a path of k steps,
k = 1..H (iterative deepening: one query per k, the first sat k is the shortest path of the encoding), each step one
public call of one action with its arguments and its environment (time E5, blob hashes E3, msg.value, the caller from
the principal table), every step but the last succeeding, and the target holding at the last step: a check that fails
there (a guard reach, a realization site), a step that succeeds and loads a byte string of a class, a store that narrows
there, or a predicate over the state after it.

The encoding (one symbolic step per action, written as SMT-LIB text by holon.smt.encode):
  - storage is held per family of the document (a scalar is a word, a mapping an array from its key word, a mapping
    to a struct one array per member): distinct families never alias (the compiler's layout under CF);
  - every term of the document's language is encoded exactly where it can be (words, checked and unchecked arithmetic
    (E6), comparisons, lazy logic, storage reads and store chains, byte strings as (array, offset, length) with a
    length of at most byte_length_max, memory regions, keccak256 / sha256 as E1 terms with NZ, the blob-hash vector
    (E3), loops unrolled to a bound) and otherwise by a fresh value, an OVER-approximation recorded in the query's
    notes; a loop that may run past its bound makes every value it defines fresh;
  - external calls are answered by the answer model (a data file transcribing the sidecar's answer table); a call
    with no answer in the model is a fresh answer (over-approximation);
  - the slice: the actions that may run before the last step are the writers of the target's cone of influence (the
    families the target's action and predicate read, closed under the reads of their writers), non-view; any other
    action changes nothing the target reads.

So an unsat k is a proof that no path of k steps exists in an over-approximation of the document's behaviour (relative
to R0, the principals, the answer model and the environment), and no_path (every k <= H unsat) is sound. A sat k gives a
candidate; it counts only after the candidate is concretized and replayed (holon.refute_engine), and a candidate the
replay does not confirm leaves the verdict unknown with the reason.
"""
from __future__ import annotations

import json
import re

from .machine import Check, Event, Loop, MStore, Write, _doc_param, canonical, document_programs
from .smt import encode as E
from .smt.encode import ARR, BV, band, bnot, bor, eq, ite, lit

MASK = (1 << 256) - 1
ZERO8 = lit(0, 8)
UNROLL = 7                 # iterations of a loop record unrolled before its overflow makes its values fresh


class B:
    """A Bool-valued term."""
    __slots__ = ("e",)

    def __init__(self, e: str):
        self.e = e


class Bytes:
    """A byte string: bytes off.. off+n-1 of array arr; n is at most nmax (and at least nmin)."""

    def __init__(self, arr: str, off: str, n: str, nmax: int, nmin: int = 0, const: bytes | None = None):
        self.arr, self.off, self.n, self.nmax, self.nmin, self.const = arr, off, n, nmax, nmin, const

    def at(self, i: str) -> str:
        return f"(select {self.arr} {i if self.off == lit(0) else f'(bvadd {self.off} {i})'})"


class Mem:
    def __init__(self, arr: str):
        self.arr = arr


class Ref:
    def __init__(self, fam: str, path: tuple = (), overlays: tuple = ()):
        self.fam, self.path, self.overlays = fam, path, overlays

    def ext(self, kind: str, x) -> "Ref":
        return Ref(self.fam, self.path + ((kind, x),), self.overlays)


class Unsup(Exception):
    pass


def _is_lit(e) -> bool:
    return isinstance(e, str) and e.startswith("(_ bv")


def lit_val(e: str) -> int | None:
    m = re.fullmatch(r"\(_ bv(\d+) (\d+)\)", e) if isinstance(e, str) else None
    return int(m.group(1)) if m else None


def word_bytes(w: str) -> list[str]:
    """The 32 big-endian bytes of a word."""
    v = lit_val(w)
    if v is not None:
        return [lit((v >> (8 * (31 - i))) & 0xFF, 8) for i in range(32)]
    return [f"((_ extract {255 - 8 * i} {248 - 8 * i}) {w})" for i in range(32)]


def concat_bytes(bs: list[str]) -> str:
    vals = [lit_val(b) for b in bs]
    if all(v is not None for v in vals):
        x = 0
        for v in vals:
            x = (x << 8) | v
        return lit(x, 8 * len(bs))
    return "(concat " + " ".join(bs) + ")" if len(bs) > 1 else bs[0]


# ------------------------------------------------------------------------------------------------ the document
class Machine:
    """A transitions document's programs, families, parameters and read/write sets."""

    def __init__(self, doc: dict, byte_length_max: int = 512):
        self.doc = doc
        self.progs = document_programs(doc)
        self.actions = {a["name"]: a for a in doc["actions"]}
        self.fams = {}
        for s in list(doc.get("inherited_storage") or []) + list(doc.get("storage") or []):
            if s.get("kind") == "array":
                continue
            self.fams[s["name"]] = s
        self.maxlen = int(byte_length_max)
        self.check_reads, self.write_reads = {}, {}
        for n, prog in self.progs.items():
            cr = {}
            for c in prog.checks():
                r = set()
                _storage_names(c.expr, r)
                cr[c.id] = (c.seq, r)
            lr = set()
            for lp in prog.records(Loop):
                _storage_names([lp.cond, lp.head, lp.brk, [x[1] for x in lp.carried], [x[1] for x in lp.next]], lr)
            self.check_reads[n] = (cr, lr)
            wr = {}
            for w in prog.records(Write):
                r = wr.setdefault(w.family, set())
                _storage_names([w.path, w.value, w.cond], r)
            self.write_reads[n] = wr
        self.reads, self.writes = {}, {}
        for n, a in self.actions.items():
            r, w = set(), set()
            _storage_names({k: v for k, v in a.items() if k not in ("post", "writes", "effects", "edges")}, r)
            for wr in a.get("writes") or []:
                w.add(wr["family"])
                _storage_names(wr.get("path"), r)
                _storage_names(wr.get("value"), r)
                _storage_names(wr.get("cond"), r)
            self.reads[n], self.writes[n] = r, w

    def params(self, action: str) -> list[dict]:
        return self.actions[action].get("params") or []

    def guard_reads(self, action: str, upto_seq=None) -> set:
        """The families an action's checks (up to a seq) and loop controls read: what decides whether it succeeds."""
        cr, lr = self.check_reads[action]
        out = set(lr)
        for _cid, (seq, r) in cr.items():
            if upto_seq is None or (seq is not None and seq <= upto_seq):
                out |= r
        return out

    def mutating(self, action: str) -> bool:
        return self.actions[action].get("mutability") not in ("view", "pure")

    def calldata(self, action: str, args: dict) -> str:
        from . import extracted_eval as EV
        a = self.actions[action]
        ps = [_doc_param(p) for p in self.params(action)]
        vals = [EV.norm(args.get(p["name"]), p) for p in ps]
        return (a.get("selector") or "0x") + EV.abi_encode(vals, ps).hex()


def _storage_names(t, out: set) -> None:
    if isinstance(t, list):
        if len(t) == 2 and t[0] == "storage" and isinstance(t[1], str):
            out.add(t[1])
        for x in t:
            _storage_names(x, out)
    elif isinstance(t, dict):
        for x in t.values():
            _storage_names(x, out)


def _call_fns(t, out: set) -> None:
    if isinstance(t, list):
        if t and t[0] in ("call", "callok") and len(t) > 1 and isinstance(t[1], str):
            out.add(t[1])
        for x in t:
            _call_fns(x, out)
    elif isinstance(t, dict):
        for x in t.values():
            _call_fns(x, out)


# ------------------------------------------------------------------------------------------------ one symbolic step
class Sym:
    """The symbolic execution of one action at one step: ok (it succeeds), fails (check id -> conditions under which
    that check is the one that fails), post (the families after it), notes (the over-approximations it used)."""

    def __init__(self, q: E.Query, m: Machine, action: str, pre: dict, inp: dict, env: dict, answers: dict, tag: str,
                 immutables: dict, consts: dict):
        self.q, self.m, self.action, self.pre, self.inp, self.env = q, m, action, pre, inp, env
        self.answers, self.tag, self.immutables, self.consts = answers, tag, immutables, consts
        self.subst: dict = {}
        self.guard = "true"
        self.bubble: list[str] = []
        self.notes: list[str] = []
        self.post = dict(pre)
        self.ok = "true"
        self.fails: dict = {}
        self.reached: dict = {}       # check id -> condition under which the check is evaluated
        self.loads: list = []          # (check, bytes value, condition): byte strings the action's checks read
        self.stores: list = []         # (write record, value, condition)
        self.ghost_writes: list = []
        self.extra_fams: dict = {}
        self.raw_slots: dict = {}
        self.pre = dict(pre)
        self.needed = None            # the families whose writes matter (None: all)
        self.stop = None              # a check id after which nothing matters (the target of the last step)
        self.stopped = False
        self.want_stores = False

    # ---------------------------------------------------------- helpers
    def fresh(self, why: str, sort: str = BV) -> str:
        self.notes.append(why)
        return self.q.fresh(f"x_{self.tag}", sort)

    def word(self, v) -> str:
        if isinstance(v, B):
            return ite(v.e, lit(1), lit(0))
        if isinstance(v, str):
            return v
        if isinstance(v, Ref):
            x = self.load(v)
            if isinstance(x, dict):
                raise Unsup("a struct used as a word")
            return self.word(x)
        if isinstance(v, Bytes):
            if v.const is not None and len(v.const) <= 32:
                return lit(int.from_bytes(v.const, "big"))
            raise Unsup("a byte string used as a word")
        if isinstance(v, int):
            return lit(v)
        raise Unsup(f"not a word: {type(v).__name__}")

    def truth(self, v) -> str:
        if isinstance(v, B):
            return v.e
        w = self.word(v)
        x = lit_val(w)
        if x is not None:
            return "true" if x else "false"
        return f"(not (= {w} {lit(0)}))"

    def bytes_of(self, v) -> Bytes:
        if isinstance(v, Bytes):
            return v
        if isinstance(v, Ref):
            v = self.load(v)
        w = self.word(v)
        return self.word_as_bytes(w)

    def word_as_bytes(self, w: str) -> Bytes:
        x = lit_val(w)
        if x is not None:
            b = x.to_bytes(32, "big")
            return Bytes(E.const_array(b), lit(0), lit(32), 32, 32, b)
        a = f"((as const {ARR}) {ZERO8})"
        for i, bb in enumerate(word_bytes(w)):
            a = f"(store {a} {lit(i)} {bb})"
        return Bytes(self.q.define(a, ARR, "wb"), lit(0), lit(32), 32, 32)

    # ---------------------------------------------------------- storage
    def fam(self, name: str) -> dict:
        f = self.m.fams.get(name) or self.extra_fams.get(name)
        if f is None:
            raise Unsup(f"storage family {name} not in the document's layout")
        return f

    def load(self, ref: Ref):
        base = self._load_base(ref)
        for wpath, val, ocond in reversed(ref.overlays):
            if len(wpath) > len(ref.path):
                raise Unsup("a read through a store to a deeper path")
            if [k for k, _ in wpath] != [k for k, _ in ref.path[:len(wpath)]]:
                continue
            conds = []
            same = True
            for (k1, x1), (k2, x2) in zip(wpath, ref.path):
                if k1 == "member":
                    if x1 != x2:
                        same = False
                        break
                else:
                    conds.append(eq(x1, x2))
            if not same:
                continue
            v = val
            for k, x in ref.path[len(wpath):]:
                if isinstance(v, dict) and k == "member":
                    v = v.get(x, lit(0))
                elif lit_val(self.word(v)) == 0:
                    v = lit(0)
                else:
                    raise Unsup("a read through a stored aggregate")
            c = band(ocond, *conds)
            base = self._merge(c, v, base)
        return base

    def _merge(self, c: str, a, b):
        if isinstance(a, dict) or isinstance(b, dict):
            ks = set(a if isinstance(a, dict) else {}) | set(b if isinstance(b, dict) else {})
            return {k: self._merge(c, a.get(k, lit(0)) if isinstance(a, dict) else lit(0),
                                   b.get(k, lit(0)) if isinstance(b, dict) else lit(0)) for k in ks}
        return ite(c, self.word(a), self.word(b))

    def _load_base(self, ref: Ref):
        f = self.fam(ref.fam)
        st = self.pre[ref.fam]
        kind = f.get("kind")
        if kind == "scalar":
            if ref.path:
                raise Unsup(f"{ref.fam}: an access into a scalar")
            return st
        if kind == "mapping":
            if not ref.path or ref.path[0][0] != "map":
                raise Unsup(f"{ref.fam}: a mapping read without a key")
            k = ref.path[0][1]
            if f.get("fields"):
                if len(ref.path) == 1:
                    return {fl["name"]: f"(select {st[fl['name']]} {k})" for fl in f["fields"]}
                if ref.path[1][0] == "member" and len(ref.path) == 2:
                    return f"(select {st[ref.path[1][1]]} {k})"
                raise Unsup(f"{ref.fam}: a nested access")
            if len(ref.path) != 1:
                raise Unsup(f"{ref.fam}: a nested access")
            return f"(select {st} {k})"
        raise Unsup(f"{ref.fam}: storage kind {kind}")

    def key_word(self, fam: str, k) -> str:
        f = self.fam(fam)
        w = self.word(k)
        kt = str(f.get("key") or "")
        if kt == "address":
            return self.q.define(f"(bvand {w} {lit((1 << 160) - 1)})")
        m = re.fullmatch(r"uint(\d+)", kt)
        if m and int(m.group(1)) < 256:
            return self.q.define(f"(bvand {w} {lit((1 << int(m.group(1))) - 1)})")
        return w

    # ---------------------------------------------------------- terms
    def ev(self, t):
        if isinstance(t, bool):
            return lit(int(t))
        if isinstance(t, int):
            return lit(t & MASK)
        if isinstance(t, str) and t.startswith("0x"):
            return lit(int(t, 16) & MASK)
        if not isinstance(t, list) or not t or not isinstance(t[0], str):
            raise Unsup(f"not a term: {str(t)[:60]}")
        h = t[0]
        if h in ("iter", "carried", "exit", "count", "returned", "arg", "receiver"):
            k = canonical(t)
            if k in self.subst:
                return self.subst[k]
            raise Unsup(f"{h} outside its loop")
        f = getattr(self, "t_" + _NAMES.get(h, h.replace(".", "_")), None)
        if f is not None:
            return f(t)
        if h in _BINOPS:
            return self.binop(h, t)
        raise Unsup(f"term {h}")

    def safe(self, t, why: str = ""):
        """ev, with an unsupported term replaced by a fresh word (an over-approximation, noted)."""
        try:
            return self.ev(t)
        except Unsup as x:
            return self.fresh(f"{self.action}: {why or 'term'}: {x}")

    def t_param(self, t):
        if t[1] not in self.inp:
            raise Unsup(f"parameter {t[1]}")
        return self.inp[t[1]]

    def t_caller(self, t):
        return self.env["caller"]

    def t_this(self, t):
        return self.env["this"]

    def t_env(self, t):
        if t[1] in self.env:
            return self.env[t[1]]
        return self.fresh(f"environment term {t[1]}")

    def t_storage(self, t):
        f = self.fam(t[1])
        if f.get("kind") == "scalar":
            return self.pre[t[1]]
        return Ref(t[1])

    def t_immutable(self, t):
        if t[1] in self.immutables:
            return lit(self.immutables[t[1]])
        raise Unsup(f"immutable {t[1]} without a value")

    def t_str(self, t):
        b = bytes.fromhex(t[1]) if t[1] else b""
        return Bytes(E.const_array(b), lit(0), lit(len(b)), len(b), len(b), b)

    def t_blobhash(self, t):
        i = self.word(self.ev(t[1]))
        bh = self.env["blobhash"]
        x = lit_val(i)
        if x is not None:
            return bh[x] if x < len(bh) else lit(0)
        out = lit(0)
        for j in reversed(range(len(bh))):
            out = ite(eq(i, lit(j)), bh[j], out)
        return self.q.define(out)

    def t_code(self, t):
        """The code of an address, as its length (the only use the document makes of it: ["len", ["code", a]])."""
        a = self.word(self.ev(t[1]))
        spec = self.answers.get("code length")
        if spec is not None:
            nz = bor(*[eq(a, self.addr(x)) for x in spec.get("nonzero", [])])
            return ite(nz, lit(1), lit(0)) if spec.get("only_listed") else self.fresh_nz(nz)
        return self.fresh("code length")

    def fresh_nz(self, nz: str) -> str:
        v = self.fresh("code length of an unlisted address")
        self.q.add(f"(=> {nz} (not (= {v} {lit(0)})))")
        return v

    def addr(self, x) -> str:
        if x == "@this":
            return self.env["this"]
        if isinstance(x, str) and x in self.env.get("@names", {}):
            return self.env["@names"][x]
        if isinstance(x, str) and x.startswith("0x"):
            return lit(int(x, 16))
        if isinstance(x, int):
            return lit(x)
        return self.word(self.ev(x))

    def t_ghost(self, t):
        g = "@" + t[1]
        if g not in self.pre:
            raise Unsup(f"ghost {t[1]}")
        return f"(select {self.pre[g]} {self.word(self.ev(t[2]))})"

    def t_unknown(self, t):
        return self.fresh(f"unknown term {canonical(t)[:60]}")

    def t_sload(self, t):
        """A raw storage read at a constant slot that no family of the document holds: the deployment's word there
        (R0), since only family writes change storage; any other read is fresh (an over-approximation)."""
        if isinstance(t[1], int) and t[1] in self.raw_slots:
            return lit(self.raw_slots[t[1]])
        return self.fresh("raw sload")

    def t_ptr(self, t):
        return self.fresh("memory pointer")

    def t_calldata(self, t):
        return self.fresh("raw calldata")

    def t_cdoff(self, t):
        return self.fresh("calldata offset")

    def t_balance(self, t):
        return self.fresh("balance")

    def t_blockhash(self, t):
        return self.fresh("blockhash")

    def t_member(self, t):
        b = self.ev(t[1])
        n = t[2]
        if isinstance(b, Ref):
            r = b.ext("member", n)
            return self.load(r)
        if isinstance(b, dict):
            if n in b:
                return b[n]
            raise Unsup(f"no member {n}")
        if isinstance(b, str) and lit_val(b) == 0:
            return lit(0)
        raise Unsup(f"member {n} of a {type(b).__name__}")

    def t_map(self, t):
        b = self.ev(t[1])
        if not isinstance(b, Ref):
            raise Unsup("a map access into a value that is not storage")
        k = self.ev(t[2])
        if isinstance(k, Bytes):
            raise Unsup("a mapping keyed by a byte string")
        r = b.ext("map", self.key_word(b.fam, k))
        f = self.fam(b.fam)
        if f.get("fields"):
            return r
        return self.load(r)

    def t_index(self, t):
        b = self.ev(t[1])
        i = self.word(self.ev(t[2]))
        if isinstance(b, Bytes):
            return concat_bytes([b.at(i)]) if False else f"((_ zero_extend 248) {b.at(i)})"
        if isinstance(b, list):
            x = lit_val(i)
            if x is not None and x < len(b):
                return b[x]
        raise Unsup("an index into a value")

    def t_len(self, t):
        if isinstance(t[1], list) and t[1][:1] == ["code"]:
            return self.t_code(t[1])
        x = self.ev(t[1])
        if isinstance(x, Bytes):
            return x.n
        if isinstance(x, list):
            return lit(len(x))
        raise Unsup("length of a value that is not a byte string")

    def t_byte(self, t):
        x = self.bytes_of(self.ev(t[1]))
        k = self.word(self.ev(t[2]))
        return f"((_ zero_extend 248) {x.at(k)})"

    def t_word(self, t):
        x = self.bytes_of(self.ev(t[1]))
        k = self.word(self.ev(t[2]))
        kv = lit_val(k)
        bs = []
        for j in range(32):
            idx = lit(kv + j) if kv is not None else f"(bvadd {k} {lit(j)})"
            sel = x.at(idx)
            if kv is not None and kv + j < x.nmin:
                bs.append(sel)
            else:
                bs.append(ite(f"(bvult {idx} {x.n})", sel, ZERO8))
        return self.q.define(concat_bytes(bs))

    def t_struct(self, t):
        return {mname: self.value(self.ev(v)) for mname, v in t[2]}

    def value(self, v):
        if isinstance(v, Ref) and not v.path and self.fam(v.fam).get("kind") == "scalar":
            return self.load(v)
        if isinstance(v, Ref) and v.path:
            return self.load(v)
        return v

    def t_tuple(self, t):
        return [self.ev(x) for x in t[1:]]

    def t_at(self, t):
        v = self.ev(t[2])
        k = t[1] if isinstance(t[1], int) else lit_val(self.word(self.ev(t[1])))
        if isinstance(v, list) and k is not None and k < len(v):
            return v[k]
        raise Unsup("component of a value")

    def t_value(self, t):
        return ("value", self.word(self.ev(t[1])))

    def t_ite(self, t):
        c = self.truth(self.ev(t[1]))
        if c == "true":
            return self.ev(t[2])
        if c == "false":
            return self.ev(t[3])
        g = self.guard
        self.guard = band(g, c)
        a = self.ev(t[2])
        self.guard = band(g, bnot(c))
        b = self.ev(t[3])
        self.guard = g
        if isinstance(a, B) and isinstance(b, B):
            return B(ite(c, a.e, b.e))
        if isinstance(a, Bytes) or isinstance(b, Bytes):
            a, b = self.bytes_of(a), self.bytes_of(b)
            return Bytes(self.q.define(ite(c, a.arr, b.arr), ARR), ite(c, a.off, b.off), ite(c, a.n, b.n),
                         max(a.nmax, b.nmax), min(a.nmin, b.nmin))
        if isinstance(a, dict) or isinstance(b, dict):
            return self._merge(c, self.value(a), self.value(b))
        if isinstance(a, Ref) and isinstance(b, Ref) and a.fam == b.fam and a.path == b.path:
            return self._mergev(c, a, b)
        if isinstance(a, Ref) or isinstance(b, Ref):
            a, b = self.value(a), self.value(b)
            if isinstance(a, Ref) or isinstance(b, Ref):
                raise Unsup("a conditional storage reference")
            return self._merge(c, a, b)
        return self.q.define(ite(c, self.word(a), self.word(b)))

    def t_and(self, t):
        g = self.guard
        acc = []
        for x in t[1:]:
            v = self.truth(self.ev(x))
            acc.append(v)
            self.guard = band(g, *acc)
        self.guard = g
        return B(band(*acc))

    def t_or(self, t):
        g = self.guard
        acc = []
        for x in t[1:]:
            v = self.truth(self.ev(x))
            acc.append(v)
            self.guard = band(g, *[bnot(a) for a in acc])
        self.guard = g
        return B(bor(*acc))

    def t_not(self, t):
        return B(bnot(self.truth(self.ev(t[1]))))

    def t_bnot(self, t):
        return f"(bvnot {self.word(self.ev(t[1]))})"

    def t_neg(self, t):
        return f"(bvneg {self.word(self.ev(t[1]))})"

    def t_trunc(self, t):
        bits = t[1] if isinstance(t[1], int) else lit_val(self.word(self.ev(t[1])))
        if bits is None:
            raise Unsup("trunc to a symbolic width")
        return self.q.define(f"(bvand {self.word(self.ev(t[2]))} {lit((1 << bits) - 1)})")

    def t_addmod(self, t):
        a, b, n = (self.word(self.ev(x)) for x in t[1:4])
        return self.q.define(ite(eq(n, lit(0)), lit(0), f"((_ extract 255 0) (bvurem (bvadd {E.zx(a, 256)} "
                                                       f"{E.zx(b, 256)}) {E.zx(n, 256)}))"))

    def t_mulmod(self, t):
        a, b, n = (self.word(self.ev(x)) for x in t[1:4])
        return self.q.define(ite(eq(n, lit(0)), lit(0), f"((_ extract 255 0) (bvurem (bvmul {E.zx(a, 256)} "
                                                       f"{E.zx(b, 256)}) {E.zx(n, 256)}))"))

    def binop(self, op: str, t):
        if len(t) != 3:
            raise Unsup(f"{op} with {len(t) - 1} operands")
        a, b = self.word(self.ev(t[1])), self.word(self.ev(t[2]))
        va, vb = lit_val(a), lit_val(b)
        if va is not None and vb is not None:
            from .extracted_eval import _BIN
            return lit(_BIN[op](va, vb))
        if op in _CMP:
            return B(_CMP[op](a, b))
        if op == "/":
            return self.q.define(ite(eq(b, lit(0)), lit(0), f"(bvudiv {a} {b})"))
        if op == "%":
            return self.q.define(ite(eq(b, lit(0)), lit(0), f"(bvurem {a} {b})"))
        if op == "**":
            if vb is not None and vb <= 8:
                out = lit(1)
                for _ in range(vb):
                    out = f"(bvmul {out} {a})"
                return self.q.define(out)
            if va == 2:
                return self.q.define(ite(f"(bvult {b} {lit(256)})", f"(bvshl {lit(1)} {b})", lit(0)))
            raise Unsup("exponentiation")
        if op == "<<":
            return self.q.define(f"(bvshl {a} {b})")
        if op == ">>":
            return self.q.define(f"(bvlshr {a} {b})")
        return self.q.define(f"({_ARITH[op]} {a} {b})")

    def _exact(self, t, signed: int | None):
        """(Bool: the exact result of [op a b] lies in range) for fits / sfits (E6)."""
        if not (isinstance(t, list) and len(t) in (2, 3)):
            raise Unsup("fits over a non-arithmetic term")
        op = t[0]
        if op == "neg":
            x = self.word(self.ev(t[1]))
            return None, x
        a, b = self.word(self.ev(t[1])), self.word(self.ev(t[2]))
        if signed:
            ea = E.sx(f"((_ extract {signed - 1} 0) {a})", 512 - signed)
            eb = E.sx(f"((_ extract {signed - 1} 0) {b})", 512 - signed)
        else:
            ea, eb = E.zx(a, 256), E.zx(b, 256)
        if op == "+":
            return "add", f"(bvadd {ea} {eb})"
        if op == "-":
            return "sub", f"(bvsub {ea} {eb})"
        if op == "*":
            return "mul", f"(bvmul {ea} {eb})"
        if op == "**":
            vb = lit_val(b)
            if vb is not None and vb <= 4:
                out = E.zx(lit(1), 256) if not signed else E.sx(lit(1, signed), 512 - signed)
                for _ in range(vb):
                    out = f"(bvmul {out} {ea})"
                return "pow", out
        raise Unsup(f"fits over {op}")

    def t_fits(self, t):
        n = t[1] if isinstance(t[1], int) else lit_val(self.word(self.ev(t[1])))
        x = t[2]
        if n == 256 and isinstance(x, list) and len(x) == 3 and x[0] in ("+", "-", "*"):
            a, b = self.word(self.ev(x[1])), self.word(self.ev(x[2]))
            if x[0] == "+":
                return B(f"(bvuge (bvadd {a} {b}) {a})")
            if x[0] == "-":
                return B(f"(bvuge {a} {b})")
            if lit_val(a) is not None or lit_val(b) is not None:
                c, y = (lit_val(a), b) if lit_val(a) is not None else (lit_val(b), a)
                return B("true" if c in (0, 1) else f"(bvule {y} {lit(MASK // c)})")
            return B(f"(not (bvumulo {a} {b}))")
        kind, r = self._exact(t[2], None)
        if kind is None:          # neg: the exact value is -x
            return B(eq(r, lit(0)))
        lo = "true"
        if kind == "sub":
            a, b = self.word(self.ev(t[2][1])), self.word(self.ev(t[2][2]))
            lo = f"(bvuge {a} {b})"
        return B(band(lo, f"(bvult {r} {lit(1 << n, 512)})"))

    def t_sfits(self, t):
        n = t[1] if isinstance(t[1], int) else lit_val(self.word(self.ev(t[1])))
        kind, r = self._exact(t[2], n)
        if kind is None:
            x = E.sx(f"((_ extract {n - 1} 0) {r})", 512 - n)
            r = f"(bvneg {x})"
        return B(band(f"(bvsge {r} {lit(-(1 << (n - 1)), 512)})", f"(bvslt {r} {lit(1 << (n - 1), 512)})"))

    # hashes
    def _hash(self, fn: str, x):
        v = self.ev(x)
        if isinstance(v, Ref):
            v = self.value(v)
        srcw = None if isinstance(v, Bytes) else self.word(v)
        bts = v if isinstance(v, Bytes) else self.word_as_bytes(srcw)
        if bts.const is not None:
            from .keccak import keccak256
            import hashlib
            d = keccak256(bts.const) if fn == "keccak256" else hashlib.sha256(bts.const).digest()
            return self.q.hash_known(fn, bts.const, int.from_bytes(d, "big"))
        return self.q.hash_term(fn, bts.arr, bts.off, bts.n, bts.nmax, bts.nmin, src_word=srcw)

    def t_keccak256(self, t):
        return self._hash("keccak256", t[1])

    def t_sha256(self, t):
        return self._hash("sha256", t[1])

    def _packed_width(self, x) -> tuple[int, bool] | None:
        ty = self.term_type(x)
        if ty is None:
            return None
        if ty in ("address",):
            return 20, False
        if ty == "bool":
            return 1, False
        m = re.fullmatch(r"u?int(\d*)", ty)
        if m:
            return int(m.group(1) or 256) // 8, False
        m = re.fullmatch(r"bytes(\d+)", ty)
        if m:
            return int(m.group(1)), True
        return None

    def term_type(self, t) -> str | None:
        if not isinstance(t, list) or not t:
            return None
        h = t[0]
        if h in ("word", "keccak256", "sha256", "blobhash", "blockhash"):
            return "bytes32"
        if h in ("caller", "this"):
            return "address"
        if h == "env":
            return "address" if t[1] in ("block.coinbase", "tx.origin") else "uint256"
        if h == "immutable":
            for c in (self.m.doc.get("immutables") or []):
                if isinstance(c, dict) and c.get("name") == t[1]:
                    return c.get("type")
            return "uint256"
        if h == "param":
            for p in self.m.params(self.action):
                if p.get("name") == t[1]:
                    return p.get("type")
            return None
        if h == "member" and isinstance(t[1], list) and t[1][:1] == ["param"]:
            for p in self.m.params(self.action):
                if p.get("name") == t[1][1]:
                    for fl in p.get("fields") or []:
                        if fl["name"] == t[2]:
                            return fl["type"]
            return None
        if h == "storage":
            f = self.m.fams.get(t[1])
            return (f or {}).get("value")
        if h == "map" and isinstance(t[1], list) and t[1][:1] == ["storage"]:
            f = self.m.fams.get(t[1][1])
            return None if (f or {}).get("fields") else (f or {}).get("value")
        return None

    def t_abi_encodePacked(self, t):
        parts = []
        for x in t[1:]:
            v = self.ev(x)
            if isinstance(v, Bytes):
                parts.append(v)
                continue
            w = self._packed_width(x)
            if w is None:
                raise Unsup("abi.encodePacked of a word of no known type")
            n, left = w
            bs = word_bytes(self.word(self.value(v)))
            parts.append(bs[:n] if left else bs[32 - n:])
        return self._concat(parts)

    def t_abi_encode(self, t):
        parts = []
        for x in t[1:]:
            v = self.ev(x)
            if isinstance(v, Bytes):
                raise Unsup("abi.encode of a byte string")
            parts.append(word_bytes(self.word(self.value(v))))
        return self._concat(parts)

    def _concat(self, parts: list) -> Bytes:
        a = f"((as const {ARR}) {ZERO8})"
        pos = 0
        const = b""
        for p in parts:
            if isinstance(p, Bytes):
                if p.const is None:
                    raise Unsup("a concatenation with a symbolic byte string")
                for i, x in enumerate(p.const):
                    a = f"(store {a} {lit(pos + i)} {lit(x, 8)})"
                pos += len(p.const)
                const = None if const is None else const + p.const
                continue
            for b in p:
                a = f"(store {a} {lit(pos)} {b})"
                pos += 1
                v = lit_val(b)
                const = None if (const is None or v is None) else const + bytes([v])
        return Bytes(self.q.define(a, ARR, "cat"), lit(0), lit(pos), pos, pos, const)

    # memory
    def t_mem(self, t):
        m = Mem(self.q.fresh(f"mem_{self.tag}", ARR))
        for w in t[1:]:
            self.mem_write(m, w, "true")
        m.arr = self.q.define(m.arr, ARR, "m")
        return m

    def mem_write(self, m: Mem, w, cond: str) -> None:
        k = w[0] if isinstance(w, list) and w else None
        if k == "mstore":
            off = self.word(self.ev(w[1]))
            bs = word_bytes(self.word(self.value(self.ev(w[2]))))
            a = m.arr
            for i, b in enumerate(bs):
                idx = lit(lit_val(off) + i) if lit_val(off) is not None else f"(bvadd {off} {lit(i)})"
                a = f"(store {a} {idx} {b})"
            m.arr = self.q.define(ite(cond, a, m.arr), ARR, "m")
        elif k == "mstore8":
            off = self.word(self.ev(w[1]))
            v = self.word(self.ev(w[2]))
            m.arr = self.q.define(ite(cond, f"(store {m.arr} {off} ((_ extract 7 0) {v}))", m.arr), ARR, "m")
        elif k == "calldatacopy":
            off, frm, n = (self.word(self.ev(w[i])) for i in (1, 3, 4))
            src = self.bytes_of(self.ev(w[2]))
            nv = lit_val(n)
            top = nv if nv is not None else src.nmax
            if top > 2 * self.m.maxlen:
                raise Unsup("calldatacopy longer than the byte-string bound")
            a = m.arr
            for i in range(top):
                si = f"(bvadd {frm} {lit(i)})"
                b = ite(f"(bvult {si} {src.n})", src.at(si), ZERO8)
                na = f"(store {a} (bvadd {off} {lit(i)}) {b})"
                a = self.q.define(na if (nv is not None) else ite(f"(bvult {lit(i)} {n})", na, a), ARR, "m")
            m.arr = self.q.define(ite(cond, a, m.arr), ARR, "m")
        elif k == "mloop":
            kvar, cnt = w[2], self.word(self.ev(w[3]))
            body = w[4] if isinstance(w[4], list) and w[4] and isinstance(w[4][0], list) else [w[4]]
            key = canonical(kvar)
            saved = self.subst.get(key)
            g = self.guard
            for j in range(UNROLL):
                cj = band(cond, f"(bvult {lit(j)} {cnt})")
                self.subst[key] = lit(j)
                self.guard = band(g, cj)
                for x in body:
                    self.mem_write(m, x, cj)
            self.guard = g
            if saved is None:
                self.subst.pop(key, None)
            else:
                self.subst[key] = saved
            over = band(cond, f"(bvugt {cnt} {lit(UNROLL)})")
            if over != "false":
                self.notes.append(f"{self.action}: memory loop {w[1]} beyond {UNROLL} iterations is havoc")
                m.arr = self.q.define(ite(over, self.q.fresh(f"mh_{self.tag}", ARR), m.arr), ARR, "m")
        elif k == "when":
            c = self.truth(self.ev(w[1]))
            self.mem_write(m, w[2], band(cond, c))
        else:
            self.notes.append(f"{self.action}: memory write {k} is havoc")
            m.arr = self.q.define(ite(cond, self.q.fresh(f"mh_{self.tag}", ARR), m.arr), ARR, "m")

    def t_slice(self, t):
        m = self.ev(t[1])
        if not isinstance(m, Mem):
            raise Unsup("a slice of a value that is not memory")
        off = self.word(self.ev(t[2]))
        n = self.word(self.ev(t[3]))
        nv = lit_val(n)
        nmax = nv if nv is not None else _bound(t[3], self.m.maxlen)
        nmin = nv if nv is not None else 0
        return Bytes(m.arr, off, n, nmax, nmin)

    def t_mload(self, t):
        m = self.ev(t[1])
        if not isinstance(m, Mem):
            raise Unsup("an mload of a value that is not memory")
        off = self.word(self.ev(t[2]))
        return self.q.define(concat_bytes([f"(select {m.arr} (bvadd {off} {lit(i)}))" for i in range(32)]))

    def t_store(self, t):
        if not t[2]:
            return self.value(self.ev(t[3]))
        base = self.ev(t[1])
        if not isinstance(base, Ref):
            raise Unsup("a store into a value that is not storage")
        wpath = self.path(base.fam, t[2])
        v = self.value(self.ev(t[3]))
        if isinstance(v, Ref):
            raise Unsup("a store of a storage reference")
        return Ref(base.fam, base.path, base.overlays + ((tuple(base.path) + tuple(wpath), v, "true"),))

    def path(self, fam: str, accs) -> list:
        out = []
        for acc in accs or []:
            kind, x = acc[0], acc[1]
            if kind == "member":
                out.append(("member", x))
            elif kind == "map":
                out.append(("map", self.key_word(fam, self.ev(x))))
            else:
                raise Unsup(f"store accessor {kind}")
        return out

    # external calls
    def _answer(self, fn: str, receiver, args: list) -> tuple[str, object]:
        """(ok condition, return value) of fn(args) by the answer model; no answer: fresh (noted)."""
        spec = self.answers.get(fn)
        if spec is None:
            ok = self.fresh(f"call {fn}: no answer in the model", "Bool")
            return ok, self.fresh(f"call {fn}: no answer in the model")
        saved = dict(self.subst)
        for i, a in enumerate(args):
            self.subst[canonical(["arg", i])] = a
        self.subst[canonical(["receiver"])] = receiver if receiver is not None else lit(0)
        try:
            ok = self.truth(self.ev(spec.get("ok", 1)))
            ret = self.ev(spec["ret"]) if spec.get("ret") is not None else lit(0)
            for gw in spec.get("ghost") or []:
                self.ghost_writes.append((gw["name"], self.word(self.ev(gw["key"])), self.word(self.ev(gw["value"])),
                                          band(self.guard, ok)))
        finally:
            self.subst = saved
        return ok, ret

    def t_call(self, t):
        fn = t[1]
        raw = [self.ev(x) for x in t[2:]]
        if raw and isinstance(raw[-1], tuple):
            raw = raw[:-1]
        raw = [self.value(x) if isinstance(x, Ref) else x for x in raw]
        if fn.startswith("address."):
            ok, ret = self._answer(fn, raw[0] if raw else None, raw[1:])
            return [self.word(B(ok)), Bytes(E.const_array(b""), lit(0), lit(0), 0, 0, b"")]
        ok, ret = self._answer(fn, None, raw)
        self.bubble.append(bor(bnot(self.guard), ok))
        return ret

    def t_callok(self, t):
        fn = t[1]
        receiver = self.word(self.ev(t[2])) if t[2] is not None else None
        raw = [self.ev(x) for x in t[3:]]
        raw = [self.value(x) if isinstance(x, Ref) else x for x in raw]
        ok, _ret = self._answer(fn, receiver, raw)
        return B(ok)

    # ---------------------------------------------------------- the program
    def run(self) -> None:
        prog = self.m.progs[self.action]
        self.block(prog.steps, "true")
        self.ok = self.q.define(self.ok, "Bool", "ok")
        for name, k, v, c in self.ghost_writes:
            g = "@" + name
            self.post[g] = self.q.define(ite(c, f"(store {self.post[g]} {k} {v})", self.post[g]), "(Array (_ BitVec 256) (_ BitVec 256))", "g")

    def block(self, steps, guard: str) -> None:
        for s in steps:
            if self.stopped:
                return
            if isinstance(s, Check):
                self.check(s, guard)
            elif isinstance(s, Write):
                self.write(s, guard)
            elif isinstance(s, Loop):
                self.loop(s, guard)
            elif isinstance(s, MStore):
                self.mstore(s, guard)
            # events change no family

    def mstore(self, s: MStore, guard: str) -> None:
        """A memory store record: changes no family; kept (with its reach condition) for store targets."""
        if not self.want_stores:
            return
        g0 = self.guard
        self.guard = band(self.ok, guard)
        try:
            c = band(guard, self.truth(self.ev(s.cond)))
            t = s.value
            field = t[1] if (isinstance(t, list) and len(t) == 3 and t[0] == "<<" and isinstance(t[2], int)) else t
            v = self.word(self.value(self.ev(field)))
            self.stores.append((s, v, self.q.define(band(self.ok, c, *self.bubble), "Bool", "r")))
        except Unsup:
            pass
        self.guard = g0

    def _flush(self) -> None:
        if self.bubble:
            self.ok = band(self.ok, *self.bubble)
            self.bubble = []

    def check(self, c: Check, guard: str) -> None:
        g0 = self.guard
        self.guard = band(self.ok, guard)
        try:
            v = self.truth(self.ev(c.expr))
        except Unsup as x:
            v = self.fresh(f"{self.action}: check {c.id}: {x}", "Bool")
        self.guard = g0
        reach = self.q.define(band(self.ok, guard, *self.bubble), "Bool", "r")
        self._flush()
        fail = self.q.define(band(reach, bnot(v)), "Bool", "f")
        self.fails.setdefault(c.id, []).append(fail)
        self.reached.setdefault(c.id, []).append(reach)
        for b in _param_bytes(c.expr):
            try:
                self.loads.append((c, self.ev(b), reach))
            except Unsup:
                pass
        self.ok = self.q.define(band(self.ok, bor(bnot(guard), v)), "Bool", "ok")
        if self.stop is not None and c.id == self.stop and c.loop is None:
            self.stopped = True

    def write(self, w: Write, guard: str) -> None:
        if self.needed is not None and w.family not in self.needed:
            return
        g0 = self.guard
        try:
            self.guard = band(self.ok, guard)
            c = band(guard, self.truth(self.ev(w.cond)))
            self.guard = band(self.ok, c)
            path = self.path(w.family, w.path)
            val = self.value(self.ev(w.value))
            self.guard = g0
            self._flush()
            self.stores.append((w, val, band(self.ok, c)))
            self._apply(w.family, path, val, c)
        except Unsup as x:
            self.guard = g0
            self._flush()
            self._havoc(w.family, f"{self.action}: write to {w.family}: {x}")

    def _havoc(self, fam: str, why: str) -> None:
        self.notes.append(why)
        f = self.fam(fam)
        if f.get("kind") == "scalar":
            self.post[fam] = self.q.fresh(f"hv_{self.tag}")
        elif f.get("fields"):
            self.post[fam] = {fl["name"]: self.q.fresh(f"hv_{self.tag}", "(Array (_ BitVec 256) (_ BitVec 256))")
                              for fl in f["fields"]}
        else:
            self.post[fam] = self.q.fresh(f"hv_{self.tag}", "(Array (_ BitVec 256) (_ BitVec 256))")

    def _mask(self, width, v: str) -> str:
        if isinstance(width, int) and width < 256:
            return self.q.define(f"(bvand {v} {lit((1 << width) - 1)})")
        return v

    def _apply(self, fam: str, path: list, val, cond: str) -> None:
        f = self.fam(fam)
        A = "(Array (_ BitVec 256) (_ BitVec 256))"
        if f.get("kind") == "scalar":
            if path:
                raise Unsup("a path into a scalar")
            v = self._mask(f.get("width"), self.word(val))
            self.post[fam] = self.q.define(ite(cond, v, self.post[fam]))
            return
        if isinstance(val, Ref) and val.fam == fam and not path and not val.path:
            for wpath, v, oc in val.overlays:
                self._apply(fam, list(wpath), v, band(cond, oc))
            return
        if f.get("kind") != "mapping" or not path or path[0][0] != "map":
            raise Unsup(f"a write of {fam} at {path}")
        k = path[0][1]
        if f.get("fields"):
            cur = dict(self.post[fam])
            if len(path) == 1:
                for fl in f["fields"]:
                    if isinstance(val, dict):
                        v = val.get(fl["name"], lit(0))
                    elif lit_val(self.word(val)) == 0:
                        v = lit(0)
                    else:
                        raise Unsup("a struct write of a word")
                    v = self._mask(fl.get("width"), self.word(v))
                    cur[fl["name"]] = self.q.define(ite(cond, f"(store {cur[fl['name']]} {k} {v})", cur[fl["name"]]), A, "s")
            elif len(path) == 2 and path[1][0] == "member":
                fl = next(x for x in f["fields"] if x["name"] == path[1][1])
                v = self._mask(fl.get("width"), self.word(val))
                cur[fl["name"]] = self.q.define(ite(cond, f"(store {cur[fl['name']]} {k} {v})", cur[fl["name"]]), A, "s")
            else:
                raise Unsup("a nested struct write")
            self.post[fam] = cur
            return
        if len(path) != 1:
            raise Unsup("a nested mapping write")
        v = self._mask(f.get("width"), self.word(val))
        self.post[fam] = self.q.define(ite(cond, f"(store {self.post[fam]} {k} {v})", self.post[fam]), A, "s")

    def loop(self, lp: Loop, guard: str) -> None:
        """A loop record, unrolled UNROLL times; past that, every value it defines and every family it writes is fresh
        (an over-approximation, noted). A loop whose values the encoding cannot carry is havoc as a whole."""
        saved = (dict(self.post), self.ok, dict(self.fails), dict(self.reached), list(self.loads), list(self.stores),
                 list(self.ghost_writes), list(self.bubble), self.guard)
        try:
            self._loop(lp, guard)
        except Unsup as x:
            (self.post, self.ok, self.fails, self.reached, self.loads, self.stores, self.ghost_writes, self.bubble,
             self.guard) = saved
            self.notes.append(f"{self.action}: loop {lp.src} is havoc ({x})")
            written = set()
            for w in lp.body:
                if isinstance(w, Write):
                    written.add(w.family)
            for fam in sorted(written):
                old = self.post[fam]
                self._havoc(fam, f"{self.action}: loop {lp.src} writes {fam}")
                new = self.post[fam]
                if isinstance(old, dict):
                    self.post[fam] = {k: self.q.define(ite(guard, new[k], old[k]), A256, "s") for k in old}
                else:
                    sort = BV if self.fam(fam).get("kind") == "scalar" else A256
                    self.post[fam] = self.q.define(ite(guard, new, old), sort, "s")
            self._havoc_records(lp.body, guard, f"loop {lp.src} is havoc")
            ov = self.q.fresh(f"x_{self.tag}", "Bool")
            self.ok = self.q.define(band(self.ok, bor(bnot(guard), ov)), "Bool", "ok")
            self._unbind(lp)
            for key in [k for k in list(self.subst) if json.loads(k)[1:2] == [lp.src]]:
                self.subst.pop(key, None)
            self.subst[canonical(lp.sym("count"))] = self.q.fresh(f"x_{self.tag}")
            for j in range(len(lp.returns)):
                self.subst[canonical(lp.sym("returned", j))] = self.q.fresh(f"x_{self.tag}")
                self.subst[canonical(lp.sym("exit", ["return", j]))] = self.q.fresh(f"x_{self.tag}")
            for n, _e, _v in lp.carried:
                self.subst[canonical(lp.sym("exit", n))] = self._fresh_like(n)
            for n, _e in lp.exits:
                self.subst.setdefault(canonical(lp.sym("exit", n)), self._fresh_like(n))

    def _havoc_records(self, body: list, cond: str, why: str) -> None:
        """The checks, loads and stores of loop iterations the encoding does not carry (a havoc loop, or the iterations
        past the unroll bound): each check may fail, each byte string it reads and each memory store's value is fresh,
        all under cond and the action's state at the loop (an over-approximation; dropping them would make a target
        inside the loop look unreachable)."""
        for r in body:
            if isinstance(r, Loop):
                self._havoc_records(r.body, cond, why)
            elif isinstance(r, Check):
                reach = self.q.define(band(self.ok, cond, *self.bubble), "Bool", "r")
                v = self.fresh(f"{self.action}: check {r.id} in {why}", "Bool")
                self.fails.setdefault(r.id, []).append(self.q.define(band(reach, v), "Bool", "f"))
                self.reached.setdefault(r.id, []).append(reach)
                for _b in _param_bytes(r.expr):
                    arr = self.q.fresh(f"x_{self.tag}", ARR)
                    n = self.q.fresh(f"x_{self.tag}")
                    self.q.add(f"(bvule {n} {lit(self.m.maxlen)})")
                    self.loads.append((r, Bytes(arr, lit(0), n, self.m.maxlen), reach))
            elif isinstance(r, MStore) and self.want_stores:
                reach = self.q.define(band(self.ok, cond, *self.bubble), "Bool", "r")
                self.stores.append((r, self.fresh(f"{self.action}: store {r.src} in {why}"), reach))

    def _fresh_like(self, n):
        """A fresh value for a loop name: a storage family's fresh state (a whole mapping), else a word."""
        if isinstance(n, list) and len(n) == 2 and n[0] == "storage" and n[1] in self.m.fams \
                and self.m.fams[n[1]].get("kind") != "scalar":
            f = self.m.fams[n[1]]
            name = f"{n[1]}#havoc_{self.q.n + 1}"
            self.extra_fams[name] = f
            if f.get("fields"):
                self.pre[name] = {fl["name"]: self.q.fresh(f"x_{self.tag}", A256) for fl in f["fields"]}
            else:
                self.pre[name] = self.q.fresh(f"x_{self.tag}", A256)
            return Ref(name)
        return self.q.fresh(f"x_{self.tag}")

    def _loop(self, lp: Loop, guard: str) -> None:
        g0 = self.guard
        c0 = band(guard, self.truth(self.safe(lp.cond, "loop condition")))
        vals = {}
        for n, e, _v in lp.carried:
            self.guard = band(self.ok, c0)
            vals[canonical(n)] = (n, self.safe(e, "loop entry value"))
        alive = c0
        count = lit(0)
        returned = []
        exits_at_break = {}
        written = set()
        for k in range(UNROLL):
            self._bind(lp, vals, k)
            self.guard = band(self.ok, alive)
            h = self.truth(self.safe(lp.head, "loop head"))
            run = self.q.define(band(alive, h), "Bool", "lr")
            self.block(lp.body, run)
            for w in lp.body:
                if isinstance(w, Write):
                    written.add(w.family)
            stop = "false"
            for j, (cnd, value) in enumerate(lp.returns):
                self.guard = band(self.ok, run)
                rc = band(run, self.truth(self.safe(cnd, "loop return")))
                returned.append((j, rc, self.safe(value, "loop return value")))
                stop = bor(stop, rc)
            self.guard = band(self.ok, run)
            br = band(run, bnot(stop), self.truth(self.safe(lp.brk, "loop break")))
            nxt = {}
            for n, e in lp.next:
                self.guard = band(self.ok, run)
                nxt[canonical(n)] = (n, self.safe(e, "loop next value"))
            for n, e in lp.at_break:
                exits_at_break.setdefault(canonical(n), []).append((br, self.safe(e, "loop break value")))
            newvals = {}
            for key, (n, v) in vals.items():
                nv = nxt.get(key, (n, v))[1]
                newvals[key] = (n, self._mergev(band(run, bnot(stop), bnot(br)), nv, v))
            vals = newvals
            count = self.q.define(ite(band(run, bnot(stop), bnot(br)), f"(bvadd {count} {lit(1)})", count))
            alive = self.q.define(band(run, bnot(stop), bnot(br)), "Bool", "la")
        self._unbind(lp)
        # past the bound: one more head evaluation decides whether the loop could go on
        self._bind(lp, vals, UNROLL)
        self.guard = band(self.ok, alive)
        h = self.truth(self.safe(lp.head, "loop head"))
        self._unbind(lp)
        over = self.q.define(band(alive, h), "Bool", "lo")
        self.guard = g0
        if over != "false":
            self.notes.append(f"{self.action}: loop {lp.src} beyond {UNROLL} iterations is havoc")
            for fam in sorted(written):
                saved = self.post[fam]
                self._havoc(fam, f"{self.action}: loop {lp.src} overflow writes {fam}")
                fresh = self.post[fam]
                srt = BV if self.fam(fam).get("kind") == "scalar" else A256
                self.post[fam] = self.q.define(ite(over, fresh, saved), srt, "s") if not isinstance(saved, dict) \
                    else {k: self.q.define(ite(over, fresh[k], saved[k]), A256, "s") for k in saved}
            self._havoc_records(lp.body, over, f"loop {lp.src} beyond {UNROLL} iterations")
            ov = self.fresh(f"{self.action}: loop {lp.src} overflow outcome", "Bool")
            self.ok = self.q.define(band(self.ok, bor(bnot(over), ov)), "Bool", "ok")
        self.subst[canonical(lp.sym("count"))] = self._mergev(over, self.fresh("loop count past the bound"), count) \
            if over != "false" else count
        for j in range(len(lp.returns)):
            rcs = [rc for jj, rc, _ in returned if jj == j]
            self.subst[canonical(lp.sym("returned", j))] = B(bor(*rcs)) if rcs else lit(0)
            val = lit(0)
            for jj, rc, v in returned:
                if jj == j:
                    val = self._mergev(rc, v, val)
            self.subst[canonical(lp.sym("exit", ["return", j]))] = val
        for key, (n, v) in vals.items():
            out = v
            for br, bv in exits_at_break.get(key, []):
                out = self._mergev(br, bv, out)
            if over != "false":
                out = self._mergev(over, self.fresh("loop exit value past the bound"), out)
            self.subst[canonical(lp.sym("exit", n))] = out
        self._bind(lp, vals, None)
        for n, e in lp.exits:
            key = canonical(lp.sym("exit", n))
            if key not in self.subst:
                self.subst[key] = self.safe(e, "loop exit value")
        self._unbind(lp)

    def _mergev(self, c: str, a, b):
        if c == "true":
            return a
        if c == "false":
            return b
        if isinstance(a, Bytes) or isinstance(b, Bytes):
            a, b = self.bytes_of(a), self.bytes_of(b)
            return Bytes(self.q.define(ite(c, a.arr, b.arr), ARR), ite(c, a.off, b.off), ite(c, a.n, b.n),
                         max(a.nmax, b.nmax), min(a.nmin, b.nmin))
        if isinstance(a, Ref) and isinstance(b, Ref) and a.fam == b.fam and a.path == b.path:
            n = 0          # the overlays both share (a store chain extended on one branch keeps its prefix once)
            while n < min(len(a.overlays), len(b.overlays)) and a.overlays[n] is b.overlays[n]:
                n += 1
            if len(a.overlays) + len(b.overlays) - n > 64:
                raise Unsup("a conditional store chain longer than 64")
            return Ref(a.fam, a.path, a.overlays[:n] +
                       tuple((p, v, band(oc, bnot(c))) for p, v, oc in b.overlays[n:]) +
                       tuple((p, v, band(oc, c)) for p, v, oc in a.overlays[n:]))
        if isinstance(a, (dict, Ref)) or isinstance(b, (dict, Ref)):
            return self._merge(c, self.value(a), self.value(b))
        return self.q.define(ite(c, self.word(a), self.word(b)))

    def _bind(self, lp: Loop, vals: dict, k) -> None:
        if k is not None:
            self.subst[canonical(lp.sym("iter"))] = lit(k)
        for _key, (n, v) in vals.items():
            self.subst[canonical(lp.sym("carried", n))] = v

    def _unbind(self, lp: Loop) -> None:
        for key in [k for k in self.subst if k.startswith('["iter",') or k.startswith('["carried",')]:
            if json.loads(key)[1] == lp.src:
                self.subst.pop(key, None)


def _param_bytes(t) -> list:
    """The byte-string parameter terms a check reads (["param", p] and ["member", ["param", p], f])."""
    out = []

    def walk(x):
        if isinstance(x, list):
            if x[:1] in (["word"], ["byte"], ["len"], ["keccak256"]) and len(x) > 1 and isinstance(x[1], list) \
                    and x[1][:1] in (["param"], ["member"]):
                k = x[1]
                if k[:1] == ["param"] or (k[:1] == ["member"] and isinstance(k[1], list) and k[1][:1] == ["param"]):
                    if k not in out:
                        out.append(k)
            for y in x:
                walk(y)
    walk(t)
    return out


def _bound(t, dflt: int) -> int:
    """A static upper bound of a length term (literals, conditionals, sums and products of them, loop counts)."""
    if isinstance(t, bool):
        return int(t)
    if isinstance(t, int):
        return t
    if isinstance(t, list) and t:
        h = t[0]
        if h == "?":
            return max(_bound(t[2], dflt), _bound(t[3], dflt))
        if h == "+":
            return _bound(t[1], dflt) + _bound(t[2], dflt)
        if h == "*":
            return _bound(t[1], dflt) * _bound(t[2], dflt)
        if h == "count":
            return UNROLL
    return dflt


_NAMES = {"?": "ite", "&&": "and", "||": "or", "!": "not", "~": "bnot", "not": "bnot", "neg": "neg",
          "abi.encode": "abi_encode", "abi.encodePacked": "abi_encodePacked"}
_CMP = {"==": lambda a, b: eq(a, b), "!=": lambda a, b: bnot(eq(a, b)), "<": lambda a, b: f"(bvult {a} {b})",
        "<=": lambda a, b: f"(bvule {a} {b})", ">": lambda a, b: f"(bvugt {a} {b})",
        ">=": lambda a, b: f"(bvuge {a} {b})"}
_ARITH = {"+": "bvadd", "-": "bvsub", "*": "bvmul", "&": "bvand", "|": "bvor", "^": "bvxor"}
_BINOPS = set(_CMP) | set(_ARITH) | {"/", "%", "**", "<<", ">>"}


# ------------------------------------------------------------------------------------------------ the unrolling
A256 = "(Array (_ BitVec 256) (_ BitVec 256))"


class Problem:
    """What BMC runs over: the document, R0 (family values), the environment and the answer model.

    principals: [(name, address int)]; answers: {fn: {"ok", "ret", "ghost"}} (terms over ["arg", i], ["receiver"],
    ["ghost", name, key] and the step's environment), "code length": {"nonzero": [addresses or principal names]};
    ghosts: {name: {key int: value int}} at R0."""

    def __init__(self, m: Machine, r0: dict, principals: list, deployed_at: int, H: int, rlimit: int,
                 blob_count_max: int, answers: dict | None = None, immutables: dict | None = None,
                 this: int | None = None, value_max: int = 100 * 10 ** 18, ghosts: dict | None = None,
                 doc_consts: dict | None = None):
        self.m, self.r0, self.principals = m, r0, principals
        self.deployed_at, self.H, self.rlimit, self.blob_max = deployed_at, H, rlimit, blob_count_max
        self.answers = answers or {}
        self.immutables = immutables or {}
        self.this = this
        self.value_max = value_max
        self.ghosts = dict(ghosts or {})
        for spec in self.answers.values():
            if isinstance(spec, dict):
                for g in spec.get("ghost") or []:
                    self.ghosts.setdefault(g["name"], {})
        self.consts = doc_consts or {}
        self.preimages: list[bytes] = []     # the byte strings the deployment hashed (E1: K of each is its word)
        self.raw_slots: dict = {}            # slot -> word of the deployment's storage outside every family

    def cone(self, last_reads: set, last: list[str]) -> tuple[list[str], set]:
        """(the non-view actions that can write a family the target reads, the cone's families): the families the
        target reads (the last step's guards up to the target, its predicate), closed under the families each writer's
        guards read and its writes to cone families read (the cone of influence, family-level; Def 4.2 coarsened to
        families). A call whose answer reads a ghost makes the ghost a cone family; a call whose answer writes it makes
        its action a writer."""
        ghost_writers = {name for name, spec in self.answers.items() if isinstance(spec, dict) and spec.get("ghost")}
        ghost_readers = {name for name, spec in self.answers.items() if isinstance(spec, dict)
                         and '"ghost"' in json.dumps([spec.get("ok", 1), spec.get("ret")])}

        def calls(a):
            out = set()
            _call_fns(self.m.actions[a], out)
            return out
        fams = set(last_reads)
        for a in last:
            if calls(a) & ghost_readers:
                fams.add("@ghost")
        acts = set()
        self.levels = []
        while True:
            lvl = []
            for a in sorted(self.m.actions):
                if self.m.mutating(a) and (self.m.writes[a] & fams or ("@ghost" in fams and calls(a) & ghost_writers)):
                    if a not in acts:
                        lvl.append(a)
                    acts.add(a)
            if lvl:
                self.levels.append(lvl)
            new = set(fams)
            for a in acts:
                new |= self.m.guard_reads(a)
                for f in self.m.writes[a] & fams:
                    new |= self.m.write_reads[a].get(f, set())
                if calls(a) & ghost_readers:
                    new.add("@ghost")
            if new == fams:
                break
            fams = new
        return sorted(acts), fams


def r0_symbolic(q: E.Query, p: Problem) -> dict:
    """R0 as SMT values: scalars as words, mappings as arrays with the deployment's entries stored."""
    st = {}
    for name, f in p.m.fams.items():
        v = p.r0.get(name)
        if f.get("kind") == "scalar":
            st[name] = lit(int(v or 0))
        elif f.get("kind") == "mapping":
            if f.get("fields"):
                st[name] = {}
                for fl in f["fields"]:
                    a = f"((as const {A256}) {lit(0)})"
                    for k, rec in sorted((v or {}).items()):
                        x = int((rec or {}).get(fl["name"], 0))
                        if x:
                            a = f"(store {a} {lit(int(k))} {lit(x)})"
                    st[name][fl["name"]] = q.define(a, A256, "r0")
            else:
                a = f"((as const {A256}) {lit(0)})"
                for k, x in sorted((v or {}).items()):
                    if int(x):
                        a = f"(store {a} {lit(int(k))} {lit(int(x))})"
                st[name] = q.define(a, A256, "r0")
    for g, entries in sorted(p.ghosts.items()):
        a = f"((as const {A256}) {lit(0)})"
        for k, x in sorted(entries.items()):
            a = f"(store {a} {lit(int(k))} {lit(int(x))})"
        st["@" + g] = q.define(a, A256, "r0")
    return st


def _ptype(p: dict) -> str:
    return str(p.get("type") or "")


def param_value(q: E.Query, p: dict, tag: str, maxlen: int, decode: dict, path: tuple):
    """Fresh inputs for one parameter: a word (range-constrained by its ABI type), a byte string, or a struct."""
    t = _ptype(p)
    if p.get("fields"):
        return {f["name"]: param_value(q, f, tag, maxlen, decode, path + (f["name"],)) for f in p["fields"]}
    if t in ("bytes", "string"):
        arr = q.fresh(f"pb_{tag}", ARR)
        n = q.fresh(f"pn_{tag}")
        q.add(f"(bvule {n} {lit(maxlen)})")
        decode[path] = ("bytes", arr, n)
        return Bytes(arr, lit(0), n, maxlen)
    w = q.fresh(f"p_{tag}")
    m = re.fullmatch(r"uint(\d*)", t)
    if m and int(m.group(1) or 256) < 256:
        q.add(f"(bvult {w} {lit(1 << int(m.group(1)))})")
    elif t == "address":
        q.add(f"(bvult {w} {lit(1 << 160)})")
    elif t == "bool":
        q.add(f"(bvule {w} {lit(1)})")
    else:
        mb = re.fullmatch(r"bytes(\d+)", t)
        if mb and int(mb.group(1)) < 32:
            q.add(f"(= ((_ extract {255 - 8 * int(mb.group(1))} 0) {w}) {lit(0, 256 - 8 * int(mb.group(1)))})")
        elif not (t.startswith("uint") or t.startswith("int") or mb):
            decode[path] = ("unsupported", t, None)
            return w
    decode[path] = ("word", w, t)
    return w


class Unrolled:
    """The k-step query of one target, with what decoding a model needs."""

    def __init__(self, p: Problem, target: dict, k: int, level: int | None = None):
        self.p, self.target, self.k = p, target, k
        q = self.q = E.Query(p.rlimit)
        m = p.m
        last = self.last_actions()
        fams = set()
        _storage_names(target.get("pred"), fams)
        _storage_names(target.get("post"), fams)
        _storage_names(target.get("cond"), fams)
        self.stop = None
        for a in last:
            if target["kind"] == "check":
                seq = m.check_reads[a][0][target["check"]][0]
                self.stop = target["check"]
                fams |= m.guard_reads(a, seq)
            else:
                fams |= m.guard_reads(a)
                if target["kind"] == "store":
                    for st in m.progs[a].records(MStore):
                        _storage_names(st.value, fams)
        self.cone, self.cone_fams = p.cone(fams, last)
        self.levels = list(p.levels)
        self.level = level
        if level is not None and level < len(self.levels):
            # an under-approximation: only the actions of the cone's first levels before the last step (a sat answer
            # is still a candidate path; an unsat answer decides nothing and the search widens)
            self.cone = sorted(a for lv in self.levels[:level + 1] for a in lv)
        if target["kind"] in ("state", "step"):
            self.cone_fams |= fams
        state = r0_symbolic(q, p)
        names = {n: lit(a) for n, a in p.principals}
        from .keccak import keccak256 as _k
        for pre in p.preimages:
            q.hash_known("keccak256", pre, int.from_bytes(_k(pre), "big"))
        self.trivial = False
        self.trivial_why = None
        if k > 1 and target.get("blob_gap"):
            # the goal asks for a zero blob hash before a non-zero one in the last step's vector, which E3's dense
            # prefix (asserted on the same vector) excludes: no path of any length; the one-step query states it
            self.trivial, self.trivial_why = True, ("the target's blob-hash gap contradicts E3's dense prefix on the "
                                                    "same vector (by E3), so no k <= H has a path")
            k = 1
        elif k > 1 and target["kind"] == "check" and self._goal_false(last, state, names):
            # the last step's goal is false in every state (e.g. a check whose condition is a constant): no path of any
            # length exists, and the prefix is not encoded
            self.trivial = True
            k = 1
        self.steps = []
        tss = []
        cost = 0
        dense = False
        for i in range(k):
            final = i == k - 1
            acts = last if final else self.cone
            env = {"@names": names}
            caller = q.const(f"caller_{i}")
            q.add(bor(*[eq(caller, lit(a)) for _n, a in p.principals]))
            env["caller"] = caller
            ts = q.const(f"ts_{i}")
            tss.append(ts)
            env["block.timestamp"] = ts
            val = q.const(f"value_{i}")
            q.add(f"(bvule {val} {lit(p.value_max)})")
            env["msg.value"] = val
            bh = [q.const(f"bh_{i}_{j}") for j in range(p.blob_max)]
            E.blob_vector(q, bh)
            dense = True
            env["blobhash"] = bh
            env["this"] = lit(p.this) if p.this is not None else q.const("this_addr")
            dl = q.const(f"datalen_{i}")
            q.add(f"(bvuge {dl} {lit(4)})")
            q.add(f"(bvule {dl} {lit(4 + 64 * 32 + 4 * p.m.maxlen)})")
            env["msg.data.length"] = dl
            sel = q.const(f"sel_{i}")
            q.add(f"(bvult {sel} {lit(len(acts))})")
            per = []
            for j, a in enumerate(acts):
                tag = f"s{i}a{j}"
                decode = {}
                inp = {}
                for prm in m.params(a):
                    inp[prm["name"]] = param_value(q, prm, tag, m.maxlen, decode, (prm["name"],))
                q.group = f"{i}/{a}"
                sym = Sym(q, m, a, state, inp, env, p.answers, tag, p.immutables, p.consts)
                sym.raw_slots = p.raw_slots
                sym.needed = None if (final and target["kind"] in ("state", "step")) else self.cone_fams
                sym.stop = self.stop if final else None
                sym.want_stores = final and target["kind"] == "store"
                sym.run()
                if (m.actions[a].get("cost") or {}).get("terms"):
                    cost += 1
                    self.cost_constraint(sym, a, i, j)
                q.group = None
                per.append({"action": a, "sym": sym, "decode": decode, "sel": eq(sel, lit(j))})
            self.steps.append({"sel": sel, "env": env, "acts": per, "final": final})
            if not final:
                q.add(bor(*[band(x["sel"], x["sym"].ok) for x in per]))
                new = {}
                for fam, v0 in state.items():
                    if isinstance(v0, dict):
                        new[fam] = {}
                        for mem in v0:
                            e = v0[mem]
                            for x in reversed(per):
                                pv = x["sym"].post[fam]
                                if pv[mem] != v0[mem]:
                                    e = ite(x["sel"], pv[mem], e)
                            new[fam][mem] = q.define(e, A256, f"st{i}")
                    else:
                        e = v0
                        sort = BV if not (fam.startswith("@") or m.fams[fam].get("kind") == "mapping") else A256
                        for x in reversed(per):
                            pv = x["sym"].post[fam]
                            if pv != v0:
                                e = ite(x["sel"], pv, e)
                        new[fam] = q.define(e, sort, f"st{i}")
                state = new
            else:
                q.add(bor(*[band(x["sel"], self.goal(x)) for x in per]))
        E.time_chain(q, tss, p.deployed_at)
        q.close(lazy=True)
        self.group_sel = {}
        for i, st in enumerate(self.steps):
            for j, x in enumerate(st["acts"]):
                self.group_sel[f"{i}/{x['action']}"] = (st["sel"], j)
        notes = sorted({n for st in self.steps for x in st["acts"] for n in x["sym"].notes})
        q.notes = [f"target: {canonical(target)}", f"actions before the last step: {', '.join(self.cone)}"
                   + (f" (cone levels 0..{level} of {len(self.levels)}: an under-approximation)"
                      if level is not None and level + 1 < len(self.levels) else " (the whole cone)")] + \
            [f"over-approximation: {n}" for n in notes]
        self.approx = notes
        if self.trivial:
            q.notes.insert(1, f"the last step's goal is false in every state: no path of any length (the query states "
                              f"one step; it decides every k <= {self.k})")
        q.extra = {"steps": k, "cone": "full" if level is None or level + 1 >= len(self.levels) else f"levels<={level}"}
        q.inst["time"] = k
        q.inst["cost"] = cost

    def _goal_false(self, last: list, state: dict, names: dict) -> bool:
        """Is the target's goal syntactically false for every last action from an arbitrary state?"""
        q2 = E.Query(self.p.rlimit)
        free = {}
        for fam, v in state.items():
            if isinstance(v, dict):
                free[fam] = {k: q2.fresh("fs", A256) for k in v}
            else:
                srt = A256 if (fam.startswith("@") or self.p.m.fams[fam].get("kind") == "mapping") else BV
                free[fam] = q2.fresh("fs", srt)
        env = {"@names": names, "caller": q2.fresh("c"), "block.timestamp": q2.fresh("t"), "msg.value": q2.fresh("v"),
               "blobhash": [q2.fresh("b") for _ in range(self.p.blob_max)], "this": q2.fresh("th"),
               "msg.data.length": q2.fresh("dl")}
        for a in last:
            inp = {prm["name"]: param_value(q2, prm, "g", self.p.m.maxlen, {}, (prm["name"],))
                   for prm in self.p.m.params(a)}
            sym = Sym(q2, self.p.m, a, free, inp, env, self.p.answers, "g", self.p.immutables, self.p.consts)
            sym.raw_slots = self.p.raw_slots
            sym.stop = self.stop
            sym.run()
            if self.target["check"] not in sym.reached or self.goal({"sym": sym}) != "false":
                # a check the evaluation never reached decides nothing: only a reached check whose every fail term is
                # literally false is constant
                return False
        return True

    def cost_constraint(self, sym: Sym, a: str, i: int, j: int) -> None:
        """E7: c0 + sum over the action's loops of c_l * iters_l <= G, with non-negative uninterpreted coefficients
        (they bind nothing until calibrated: the coefficients may be 0)."""
        q = self.q
        terms = (self.p.m.actions[a].get("cost") or {}).get("terms") or []
        c0 = q.const(f"cost_c0_{a.lower()}" if False else f"cost_{i}_{j}_c0")
        acc = c0
        for n, _t in enumerate(terms):
            c = q.const(f"cost_{i}_{j}_c{n + 1}")
            it = q.const(f"cost_{i}_{j}_it{n + 1}")
            q.add(f"(bvule {it} {lit(1 << 32)})")
            q.add(f"(bvule {c} {lit(1 << 32)})")
            acc = f"(bvadd {acc} (bvmul {c} {it}))"
        q.add(f"(bvule {c0} {lit(1 << 32)})")
        q.add(f"(=> (= sel_{i} {lit(j)}) (bvule {acc} {lit(self.p.gas_limit if hasattr(self.p, 'gas_limit') else 30000000)}))")

    def last_actions(self) -> list[str]:
        t = self.target
        m = self.p.m
        if t["kind"] == "check":
            return [t["action"]]
        if t["kind"] in ("load", "store"):
            out = []
            for a in sorted(m.actions):
                if not m.mutating(a) and t["kind"] == "store":
                    continue
                prog = m.progs[a]
                recs = prog.checks() if t["kind"] == "load" else prog.records(MStore)
                for r in recs:
                    span = r.span if t["kind"] == "load" else r.src
                    stack = r.stack or []
                    if span == t["span"] or t["span"] in stack:
                        out.append(a)
                        break
            return out
        if t["kind"] in ("state", "step"):
            acts = t.get("actions") or [a for a in sorted(m.actions) if m.mutating(a)]
            return list(acts)
        raise ValueError(f"unknown target kind {t['kind']}")

    def goal(self, x: dict) -> str:
        t = self.target
        sym: Sym = x["sym"]
        if t["kind"] == "check":
            return bor(*sym.fails.get(t["check"], ["false"]))
        if t["kind"] == "load":
            conds = []
            for c, v, reach in sym.loads:
                stack = c.stack or []
                if not (c.span == t["span"] or t["span"] in stack) or not isinstance(v, Bytes):
                    continue
                cc = [reach, sym.ok]
                if "byte0" in t:
                    cc.append(eq(v.at(lit(0)), lit(int(t["byte0"]), 8)))
                    cc.append(f"(bvugt {v.n} {lit(0)})")
                if "length_gt" in t:
                    cc.append(f"(bvugt {v.n} {lit(int(t['length_gt']))})")
                if "length_eq" in t:
                    cc.append(eq(v.n, lit(int(t["length_eq"]))))
                conds.append(band(*cc))
            return bor(*conds)
        if t["kind"] == "store":
            conds = []
            for s, v, reach in sym.stores:
                if isinstance(s, MStore) and (s.src == t["span"] or t["span"] in (s.stack or [])):
                    conds.append(band(reach, sym.ok, f"(bvuge {v} {lit(1 << int(t['width']))})"))
            return bor(*conds)
        if t["kind"] in ("state", "step"):
            cc = [sym.ok]
            if t.get("cond") is not None:
                cc.append(sym.truth(sym.safe(t["cond"], "target condition")))
            if t.get("post") is not None:
                post = Sym(self.q, self.p.m, sym.action, sym.post, sym.inp, sym.env, self.p.answers, sym.tag + "p",
                           self.p.immutables, self.p.consts)
                cc.append(post.truth(post.safe(t["post"], "target predicate")))
            if t.get("pred") is not None:
                post = Sym(self.q, self.p.m, sym.action, sym.post, sym.inp, sym.env, self.p.answers, sym.tag + "p",
                           self.p.immutables, self.p.consts)
                cc.append(post.truth(post.safe(t["pred"], "target predicate")))
            if t.get("blob_gap"):
                bh = sym.env["blobhash"]
                cc.append(bor(*[band(eq(bh[a], lit(0)), bnot(eq(bh[b], lit(0))))
                                for a in range(len(bh)) for b in range(a + 1, len(bh))]))
            return band(*cc)
        return "false"

    # ---------------------------------------------------------- lazy E1
    def real_hashes(self, sess) -> list[str]:
        """Hash concretization (a path that a replay hashes for real): the assertions "this content hashes to its real
        digest" for every live hash term whose model word is not the real hash of the content the model gives it
        (keccak256 and sha256; the words are otherwise free under E1, so this narrows the model to one the real
        functions agree with, or makes the query unsat: then no path with these contents exists in the encoding)."""
        import hashlib
        from .keccak import keccak256
        real = {"keccak256": lambda b: keccak256(b), "sha256": lambda b: hashlib.sha256(b).digest()}
        live = [h for h in self._live(sess) if h.fn in real and h.const is None]
        if not live:
            return []
        for h in live:
            if h.src_word is None:
                self.q.digest(h)
        nd = getattr(self, "sent_defs", None)
        if nd is not None and len(self.q.defs) > nd:
            sess.send("".join(f"(define-fun {n} () {srt} {e})\n" for n, srt, e in self.q.defs[nd:]))
            self.sent_defs = len(self.q.defs)
        terms = set()
        for h in live:
            terms.add(h.word)
            if h.src_word is not None:
                terms.add(h.src_word)
            else:
                terms.add(h.n)
                d = self.q.digest(h)
                if d:
                    terms.add(d)
        vals = sess.values(sorted(terms))
        out = []
        for h in live:
            if h.src_word is not None:
                content = vals[h.src_word].to_bytes(32, "big")
                cond = eq(h.src_word, lit(vals[h.src_word]))
            else:
                n = vals[h.n]
                d = self.q.digest(h)
                content = (vals[d].to_bytes(h.nmax, "big") if d else b"")[:n]
                cond = band(eq(h.n, lit(n)), *([eq(d, "#x" + vals[d].to_bytes(h.nmax, "big").hex())] if d else []))
            want = int.from_bytes(real[h.fn](content), "big")
            if vals[h.word] != want:
                out.append(f"(=> {cond} {eq(h.word, lit(want))})")
        return out

    def pin_inputs(self, sess) -> list[str]:
        """Assertions fixing every step's selected action, its decoded parameters and its environment to the model's
        values (hash concretization then only follows the hashes those inputs determine)."""
        out = []
        for st in self.steps:
            sel = sess.values([st["sel"]])[st["sel"]]
            out.append(eq(st["sel"], lit(sel)))
            x = st["acts"][sel]
            env = st["env"]
            names = [env["caller"], env["block.timestamp"], env["msg.value"]] + list(env["blobhash"])
            for path, (kind, a, b) in sorted(x["decode"].items()):
                if kind == "word":
                    names.append(a)
                elif kind == "bytes":
                    n = sess.values([b])[b]
                    out.append(eq(b, lit(n)))
                    sels = [f"(select {a} {lit(j)})" for j in range(n)]
                    bv = sess.values(sels) if sels else {}
                    out += [eq(t, lit(bv[t], 8)) for t in sels]
            vals = sess.values(sorted(set(names)))
            out += [eq(t, lit(v)) for t, v in sorted(vals.items())]
        return out

    def _live(self, sess) -> list:
        live = []
        groups = {}
        for h in self.q.hashes:
            if h.group is None:
                live.append(h)
                continue
            groups.setdefault(h.group, []).append(h)
        sels = sess.values(sorted({self.group_sel[g][0] for g in groups if g in self.group_sel}))
        for g, hs in groups.items():
            sv, j = self.group_sel.get(g, (None, None))
            if sv is None or sels.get(sv) == j:
                live += hs
        return live

    def violations(self, sess) -> list:
        """The pending E1 pairs a model violates among the hash terms its selected actions evaluate: equal words over
        different contents, or equal contents under different words."""
        live = []
        groups = {}
        for h in self.q.hashes:
            if h.group is None:
                live.append(h)
                continue
            groups.setdefault(h.group, []).append(h)
        sels = sess.values(sorted({self.group_sel[g][0] for g in groups if g in self.group_sel}))
        for g, hs in groups.items():
            sv, j = self.group_sel.get(g, (None, None))
            if sv is None or sels.get(sv) == j:
                live += hs
        ids = {id(h) for h in live}
        pend = [(a, b) for a, b in self.q.pending if id(a) in ids and id(b) in ids]
        if not pend:
            return []
        terms = set()
        for a, b in pend:
            for h in (a, b):
                terms.add(h.word)
                if h.const is None and h.src_word is None:
                    terms.add(h.n)
                    d = self.q.digest(h)
                    if d:
                        terms.add(d)
                elif h.src_word is not None:
                    terms.add(h.src_word)
        nd = getattr(self, "sent_defs", None)
        if nd is not None and len(self.q.defs) > nd:
            sess.send("".join(f"(define-fun {n} () {srt} {e})\n" for n, srt, e in self.q.defs[nd:]))
            self.sent_defs = len(self.q.defs)
        vals = sess.values(sorted(terms))

        def content(h):
            if h.const is not None:
                return h.const
            if h.src_word is not None:
                return vals[h.src_word].to_bytes(32, "big")
            n = vals[h.n]
            d = self.q.digest(h)
            raw = vals[d].to_bytes(h.nmax, "big") if d else b""
            return raw[:n]
        out = []
        for a, b in pend:
            if (vals[a.word] == vals[b.word]) != (content(a) == content(b)):
                out.append((a, b))
        return out

    # ---------------------------------------------------------- decoding a model
    def preimages(self, sess, spec: dict) -> list[str]:
        """The contents the model gives the hash terms of a function (spec: {"fn", "byte0"?, "lengths"?}), as hex,
        sorted: what the path hashed (e.g. the bytes whose hash it stores)."""
        hs = [h for h in self.q.hashes if h.fn == spec.get("fn") and h.const is None and h.src_word is None]
        if not hs:
            return []
        for h in hs:
            self.q.digest(h)
        nd = getattr(self, "sent_defs", None)
        if nd is not None and len(self.q.defs) > nd:
            sess.send("".join(f"(define-fun {n} () {srt} {e})\n" for n, srt, e in self.q.defs[nd:]))
            self.sent_defs = len(self.q.defs)
        ns = sess.values(sorted({h.n for h in hs}))
        out = set()
        for h in hs:
            n = ns[h.n]
            if spec.get("lengths") and n not in spec["lengths"]:
                continue
            d = self.q.digest(h)
            if not d:
                continue
            raw = sess.values([d])[d].to_bytes(h.nmax, "big")[:n]
            if "byte0" in spec and (not raw or raw[0] != int(spec["byte0"])):
                continue
            out.add("0x" + raw.hex())
        return sorted(out)

    def decode(self, sess) -> list[dict]:
        out = []
        for i, st in enumerate(self.steps):
            sel = sess.values([st["sel"]])[st["sel"]]
            x = st["acts"][sel]
            env = st["env"]
            names = [env["caller"], env["block.timestamp"], env["msg.value"]] + env["blobhash"]
            vals = sess.values(names)
            args = {}
            for path, (kind, a, b) in sorted(x["decode"].items()):
                if kind == "word":
                    v = sess.values([a])[a]
                    val = "0x%040x" % v if b == "address" else ("0x%064x" % v if re.fullmatch(r"bytes\d+", b or "")
                                                                else (bool(v) if b == "bool" else v))
                elif kind == "bytes":
                    n = sess.values([b])[b]
                    sels = [f"(select {a} {lit(j)})" for j in range(n)]
                    bv = sess.values(sels) if sels else {}
                    val = "0x" + bytes(bv[s] for s in sels).hex()
                else:
                    val = 0
                d = args
                for key in path[:-1]:
                    d = d.setdefault(key, {})
                d[path[-1]] = val
            bh = [vals[b] for b in env["blobhash"]]
            bh = bh[:next((j for j, v in enumerate(bh) if v == 0), len(bh))]
            out.append({"action": x["action"], "args": args,
                        "calldata": self.p.m.calldata(x["action"], args),
                        "env": {"caller": "0x%040x" % vals[env["caller"]], "msg.value": vals[env["msg.value"]],
                                "block.timestamp": vals[env["block.timestamp"]],
                                "blobhash": ["0x%064x" % v for v in bh], "calls": []}})
        return out


QUERY_PLAIN_MAX = 1 << 20     # a query file larger than this is stored gzip-compressed (deterministic: no name, mtime 0)


def write_query(f, text: str):
    """Write a query: as .smt2, or, past QUERY_PLAIN_MAX bytes, as .smt2.gz (byte-identical across runs)."""
    import gzip
    from pathlib import Path
    f = Path(f)
    data = text.encode("utf-8")
    gz = f.with_name(f.name + ".gz")
    if len(data) <= QUERY_PLAIN_MAX:
        gz.unlink(missing_ok=True)
        f.write_bytes(data)
        return f
    f.unlink(missing_ok=True)
    with open(gz, "wb") as fh:
        with gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0, compresslevel=9) as z:
            z.write(data)
    return gz


GUARD_S = None          # the build's wall-clock watchdog per query (None: none); a fired guard is an unknown
MEMORY_MB = None


def search(p: Problem, target: dict, solver: dict, qdir=None, name: str = "q", log=None, ks=None) -> dict:
    """Iterative deepening, k = 1..H. At each k the actions before the last step widen through the cone's levels
    (level 0: the writers of what the target reads; each further level the writers of what the previous level's guards
    read): a sat answer at any level is a candidate path (decoded from the model); only the whole cone's unsat decides
    k. Every k unsat gives no_path; a query that ends unknown (the rlimit) stops the search: unknown, with the largest
    k decided."""
    from pathlib import Path
    from .smt.run import Session
    largest = 0
    queries = []
    approx = set()
    for k in (ks or range(1, p.H + 1)):
        lv = 0
        while True:
            u = Unrolled(p, target, k, lv if k > 1 else None)
            full = k == 1 or lv + 1 >= len(u.levels)
            approx |= set(u.approx)
            text = u.q.text()
            tag = "" if full else f".l{lv}"
            if qdir is not None:
                f = Path(qdir) / f"{name}.k{k}{tag}.smt2"
                f.parent.mkdir(parents=True, exist_ok=True)
                queries.append(str(f))
            sess = Session(solver)
            try:
                res = sess.check(text, GUARD_S, MEMORY_MB)
                u.sent_defs = len(u.q.defs)
                rounds = 0
                while res == "sat" and rounds < 64:
                    viol = u.violations(sess)
                    if not viol:
                        break
                    rounds += 1
                    nd, na = u.sent_defs, len(u.q.asserts)
                    for a, b in viol:
                        u.q.pending.remove((a, b))
                        u.q.assert_pair(a, b)
                    res = sess.more("".join(f"(define-fun {n} () {srt} {e})\n" for n, srt, e in u.q.defs[nd:]) +
                                    "".join(f"(assert {x})\n" for x in u.q.asserts[na:]))
                    u.sent_defs = len(u.q.defs)
                if res == "sat" and rounds >= 64:
                    res = "unknown"
                    sess.guard = "E1 instantiation did not converge in 64 rounds"
                hrounds = 0
                if res == "sat" and target.get("observe"):
                    na = len(u.q.asserts)
                    for a in u.pin_inputs(sess):
                        u.q.add(a)
                    res = sess.more("".join(f"(assert {x})\n" for x in u.q.asserts[na:]))
                while res == "sat" and target.get("observe") and hrounds < 32:
                    # the observed contents must hash for real: concretize the hash words (and re-close E1)
                    na = len(u.q.asserts)
                    for a in u.real_hashes(sess):
                        u.q.add(a)
                    for a, b in u.violations(sess):
                        u.q.pending.remove((a, b))
                        u.q.assert_pair(a, b)
                    if len(u.q.asserts) == na:
                        break
                    hrounds += 1
                    nd = u.sent_defs
                    res = sess.more("".join(f"(define-fun {n} () {srt} {e})\n" for n, srt, e in u.q.defs[nd:]) +
                                    "".join(f"(assert {x})\n" for x in u.q.asserts[na:]))
                    u.sent_defs = len(u.q.defs)
                if res == "sat" and hrounds >= 32:
                    res = "unknown"
                    sess.guard = "hash concretization did not converge in 32 rounds"
                if hrounds and res == "unsat":
                    res = "unknown"
                    sess.guard = "no model with real hash values for the contents tried (hash concretization)"
                u.q.inst["cf_asserted"] = u.q.inst.get("cf", 0) - len(u.q.pending)
                text = u.q.text()
                if qdir is not None:
                    queries[-1] = str(write_query(Path(qdir, f"{name}.k{k}{tag}.smt2"), text))
                if log:
                    log(f"  {name} k={k}{tag}: {res} ({len(text) // 1024} KiB, E1 rounds {rounds})"
                        f"{' ' + sess.guard if sess.guard else ''}")
                if res == "sat":
                    path = u.decode(sess)
                    seen = {"observed": u.preimages(sess, target["observe"])} if target.get("observe") else {}
                    return {"verdict": "path", "length": k, "path": path, "largest_k": k, "queries": queries,
                            "approx": sorted(approx), **seen,
                            "reason": f"sat at k = {k} (the first sat depth){'' if full else f', cone levels <= {lv}'}"}
                if res != "unsat" and not full:
                    # an under-approximate level that ends unknown decides nothing: widen to the next level (the full
                    # cone last) rather than stopping
                    if log:
                        log(f"  {name} k={k}{tag}: unknown on an under-approximate level; widening")
                    lv += 1
                    continue
                if res != "unsat":
                    why = sess.guard or sess.reason()
                    return {"verdict": "unknown", "length": None, "path": None, "largest_k": largest,
                            "queries": queries, "approx": sorted(approx),
                            "reason": f"solver unknown at k = {k}{'' if full else f' (cone levels <= {lv})'} "
                                      f"({why.strip()}); rlimit {p.rlimit}"}
            finally:
                sess.close()
            if u.trivial and res == "unsat":
                return {"verdict": "no_path", "length": None, "path": None, "largest_k": p.H, "queries": queries,
                        "approx": sorted(approx), "reason": u.trivial_why or "the target's check, reached at the last step, cannot fail "
                                                            "there in any state of the encoding (its condition is "
                                                            "constant under the answer model), so no k <= H has a path"}
            if full:
                break
            lv += 1
        largest = k
    return {"verdict": "no_path", "length": None, "path": None, "largest_k": largest, "queries": queries,
            "approx": sorted(approx), "reason": f"every k <= {p.H} unsat within the rlimit {p.rlimit} (relative to R0, "
                                                 f"the principals, the answer model and the environment)"}
