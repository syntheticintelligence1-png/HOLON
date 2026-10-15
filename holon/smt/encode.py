"""Ground SMT-LIB 2 encodings (whitepaper Appendix D, as spec/M3/lib/refute.json "encodings" lists them; I40).

Every query is QF_AUFBV text. Nothing here is quantified: each Appendix D property is instantiated over the query's own
terms (Thm 6.15: global hash injectivity is inconsistent; Cor 6.16: the ground instances are CF(h, S_query)).

  E1  keccak256 / sha256: one function each, K(n, x) of the byte length n and the bytes x. A K term is a fresh 256-bit
      word with its preimage (array, offset, length); for every pair of terms of one function the query states
      K1 = K2 <=> (n1 = n2 and the first n1 bytes agree): ground injectivity and functionality over the query's terms.
      A hash the deployment computed is a K term with its concrete preimage, equal to its concrete word.
  NZ  every K term is non-zero.
  E2  VH: ground injectivity over the query's VH terms, Z = VH(0) = the document's ZERO_VERSIONED_HASH, top byte 0x01.
  E3  a blob-hash vector is a dense prefix of at most blob_count_max entries, every non-zero entry with top byte 0x01.
  E4  Enc / Dec with HypZ instantiated for the query's x terms and k = 0..K (instances(): hypz = Enc terms x (K + 1)).
  E5  block.timestamp per step: never 0, at least the deployment's clock at the first step, non-decreasing.
  E6  checked arithmetic is a revert predicate over the exact result (bvuaddo / bvusubo / bvumulo, written as
      zero-extended comparisons); unchecked arithmetic wraps.
  E7  cost: c0 + sum_l c_l * iters_l against the gas limit G, with non-negative uninterpreted coefficients (it binds
      nothing until the coefficients are calibrated).

instances(terms, hypz_K) gives the instance counts a query over those terms gets; Query.header() states them in the
query's first line ("; holon-smt " + canonical JSON).
"""
from __future__ import annotations

import json

BV = "(_ BitVec 256)"
BYTE = "(_ BitVec 8)"
ARR = "(Array (_ BitVec 256) (_ BitVec 8))"
HASH_FNS = ("keccak256", "sha256")
LOGIC = "QF_AUFBV"


def instances(terms: dict, hypz_K: int) -> dict:
    """The instance counts of a query over a multiset of terms {fn: count} (fn among keccak256, sha256, VH, blobhash (a
    vector's slots) and Enc): cf = sum over the hash functions of n(n-1)/2, nz = the number of hash terms, vh_top = the
    number of VH terms, dense = slots - 1, hypz = Enc terms x (hypz_K + 1)."""
    out = {}
    hs = {f: int(terms.get(f) or 0) for f in HASH_FNS if terms.get(f)}
    if hs:
        out["cf"] = sum(n * (n - 1) // 2 for n in hs.values())
        out["nz"] = sum(hs.values())
    if terms.get("VH"):
        n = int(terms["VH"])
        out["vh_top"] = n
        out["cf_vh"] = n * (n - 1) // 2
    if terms.get("blobhash"):
        out["dense"] = max(0, int(terms["blobhash"]) - 1)
    if terms.get("Enc"):
        out["hypz"] = int(terms["Enc"]) * (int(hypz_K) + 1)
    return out


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def lit(v: int, bits: int = 256) -> str:
    return f"(_ bv{int(v) % (1 << bits)} {bits})"


def zx(e: str, extra: int) -> str:
    return f"((_ zero_extend {extra}) {e})"


def sx(e: str, extra: int) -> str:
    return f"((_ sign_extend {extra}) {e})"


def ite(c: str, a: str, b: str) -> str:
    if a == b:
        return a
    if c == "true":
        return a
    if c == "false":
        return b
    return f"(ite {c} {a} {b})"


def band(*xs: str) -> str:
    ys = []
    for x in xs:
        if x == "false":
            return "false"
        if x != "true" and x not in ys:
            ys.append(x)
    if not ys:
        return "true"
    return ys[0] if len(ys) == 1 else "(and " + " ".join(ys) + ")"


def bor(*xs: str) -> str:
    ys = []
    for x in xs:
        if x == "true":
            return "true"
        if x != "false" and x not in ys:
            ys.append(x)
    if not ys:
        return "false"
    return ys[0] if len(ys) == 1 else "(or " + " ".join(ys) + ")"


def bnot(x: str) -> str:
    if x == "true":
        return "false"
    if x == "false":
        return "true"
    if x.startswith("(not ") and x.endswith(")"):
        inner = x[5:-1]
        if _balanced(inner):
            return inner
    return f"(not {x})"


def _balanced(s: str) -> bool:
    d = 0
    for ch in s:
        d += ch == "("
        d -= ch == ")"
        if d < 0:
            return False
    return d == 0


def eq(a: str, b: str) -> str:
    if a == b:
        return "true"
    return f"(= {a} {b})"


class Hash:
    """One E1 term: its word (a declared constant), its preimage (array, offset, length) and static bounds."""

    def __init__(self, fn: str, word: str, arr: str, off: str, n: str, nmax: int, nmin: int = 0, const: bytes | None = None,
                 value: int | None = None):
        self.fn, self.word, self.arr, self.off, self.n = fn, word, arr, off, n
        self.nmax, self.nmin, self.const, self.value = nmax, nmin, const, value


class Query:
    """An SMT-LIB 2 query: sorted declarations, definitions in creation order, assertions, and the E1/NZ instances of
    its hash terms (added by close())."""

    def __init__(self, rlimit: int, seed: int = 0):
        self.rlimit = int(rlimit)
        self.seed = int(seed)
        self.decls: dict[str, str] = {}
        self.defs: list[tuple[str, str, str]] = []
        self.defmap: dict[tuple[str, str], str] = {}
        self.asserts: list[str] = []
        self.hashes: list[Hash] = []
        self.terms: dict[str, int] = {}
        self.inst: dict[str, int] = {}
        self.extra: dict = {}
        self.n = 0
        self.notes: list[str] = []

    # ---------------------------------------------------------- names
    def fresh(self, prefix: str, sort: str = BV) -> str:
        self.n += 1
        name = f"{prefix}_{self.n}"
        self.decls[name] = sort
        return name

    def const(self, name: str, sort: str = BV) -> str:
        if name in self.decls and self.decls[name] != sort:
            raise ValueError(f"{name} declared twice with different sorts")
        self.decls[name] = sort
        return name

    def define(self, expr: str, sort: str = BV, prefix: str = "d") -> str:
        """A named definition of expr (shared when the same expression is defined again)."""
        if expr.startswith("(_ bv") or expr in ("true", "false") or " " not in expr:
            return expr
        key = (expr, sort)
        if key in self.defmap:
            return self.defmap[key]
        self.n += 1
        name = f"{prefix}_{self.n}"
        self.defs.append((name, sort, expr))
        self.defmap[key] = name
        return name

    def add(self, cond: str) -> None:
        if cond != "true":
            self.asserts.append(cond)

    def count(self, fn: str, k: int = 1) -> None:
        self.terms[fn] = self.terms.get(fn, 0) + k

    # ---------------------------------------------------------- E1 / NZ
    def hash_term(self, fn: str, arr: str, off: str, n: str, nmax: int, nmin: int = 0) -> str:
        w = self.fresh(f"h_{fn}")
        self.hashes.append(Hash(fn, w, arr, off, n, nmax, nmin))
        self.count(fn)
        return w

    def hash_known(self, fn: str, preimage: bytes, value: int) -> str:
        """A hash the deployment (or the document) computed: a K term with a concrete preimage and word."""
        for h in self.hashes:
            if h.fn == fn and h.const == preimage:
                return h.word
        w = self.fresh(f"h_{fn}")
        arr = const_array(preimage)
        self.hashes.append(Hash(fn, w, arr, lit(0), lit(len(preimage)), len(preimage), len(preimage), preimage, value))
        self.add(eq(w, lit(value)))
        self.count(fn)
        return w

    def _content_eq(self, a: Hash, b: Hash) -> str:
        top = min(a.nmax, b.nmax)
        if a.const is not None and b.const is not None:
            return "true" if a.const == b.const else "false"
        parts = [eq(a.n, b.n)]
        for i in range(top):
            ia = f"(bvadd {a.off} {lit(i)})" if a.off != lit(0) else lit(i)
            ib = f"(bvadd {b.off} {lit(i)})" if b.off != lit(0) else lit(i)
            sa, sb = f"(select {a.arr} {ia})", f"(select {b.arr} {ib})"
            if i < min(a.nmin, b.nmin):
                parts.append(eq(sa, sb))
            else:
                parts.append(f"(or (bvule {a.n} {lit(i)}) {eq(sa, sb)})")
        return band(*parts)

    def close(self) -> None:
        """E1 (ground injectivity and functionality over the query's own K terms of each function) and NZ."""
        cf = nz = 0
        for fn in HASH_FNS:
            hs = [h for h in self.hashes if h.fn == fn]
            nz += len(hs)
            for h in hs:
                self.add(f"(not (= {h.word} {lit(0)}))")
                if h.const is None:
                    self.add(f"(bvule {h.n} {lit(h.nmax)})")
                    if h.nmin:
                        self.add(f"(bvuge {h.n} {lit(h.nmin)})")
            for i in range(len(hs)):
                for j in range(i + 1, len(hs)):
                    a, b = hs[i], hs[j]
                    cf += 1
                    if a.nmax < b.nmin or b.nmax < a.nmin:
                        self.add(f"(not (= {a.word} {b.word}))")
                        continue
                    if a.const is not None and b.const is not None:
                        continue      # two concrete words: their equality is the words'
                    c = self.define(self._content_eq(a, b), "Bool", "ceq")
                    self.add(f"(= (= {a.word} {b.word}) {c})")
        if nz:
            self.inst["cf"] = cf
            self.inst["nz"] = nz

    # ---------------------------------------------------------- text
    def header(self) -> dict:
        h = {"logic": LOGIC, "random_seed": self.seed, "rlimit": self.rlimit,
             "terms": {k: v for k, v in sorted(self.terms.items()) if v}, "instances": dict(sorted(self.inst.items()))}
        h.update(self.extra)
        return h

    def text(self, get: list[str] | None = None) -> str:
        out = ["; holon-smt " + canonical(self.header())]
        out += [f"; {n}" for n in self.notes]
        out += [f"(set-option :rlimit {self.rlimit})", f"(set-option :smt.random_seed {self.seed})",
                f"(set-option :sat.random_seed {self.seed})", "(set-option :produce-models true)",
                f"(set-logic {LOGIC})"]
        out += [f"(declare-const {n} {s})" for n, s in sorted(self.decls.items())]
        out += [f"(define-fun {n} () {s} {e})" for n, s, e in self.defs]
        out += [f"(assert {a})" for a in self.asserts]
        out.append("(check-sat)")
        return "\n".join(out) + "\n"


def const_array(b: bytes) -> str:
    """The array holding bytes b at 0.. (zero elsewhere)."""
    a = f"((as const {ARR}) {lit(0, 8)})"
    for i, x in enumerate(b):
        if x:
            a = f"(store {a} {lit(i)} {lit(x, 8)})"
    return a


def blob_vector(q: Query, names: list[str], top_one: bool = True) -> None:
    """E3 over one step's blob-hash vector (its slots in order): a dense prefix, every non-zero entry with top byte
    0x01."""
    for i, n in enumerate(names):
        if i + 1 < len(names):
            q.add(f"(=> (= {n} {lit(0)}) (= {names[i + 1]} {lit(0)}))")
        if top_one:
            q.add(f"(or (= {n} {lit(0)}) (= ((_ extract 255 248) {n}) {lit(1, 8)}))")
    q.count("blobhash", len(names))


def time_chain(q: Query, names: list[str], deployed_at: int) -> None:
    """E5: never 0, at least the deployment's clock at the first step, non-decreasing."""
    prev = lit(deployed_at)
    for n in names:
        q.add(f"(bvuge {n} {prev})")
        q.add(f"(not (= {n} {lit(0)}))")
        prev = n
