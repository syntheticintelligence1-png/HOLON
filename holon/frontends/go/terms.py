"""Terms, atoms and cells of the Go frontend (internally tuples; JSON arrays on output), constant folding, the linear
normal form of atoms and the reasoner.

Terms   ("const", int) ("bool", b) ("str", s) ("nil",) ("zero", type) ("param", name) ("global", name)
        ("field", T, name) ("len", T) ("cap", T) ("index", T, I) ("slice", T, LO, HI, MAX) ("op", op, A, B)
        ("unop", op, A) ("convert", type, T) ("iface", type, T) ("call", callee, (args...)) ("result", CALL, i)
        ("append", DST, SRC) ("alloc", span, LEN) ("var", ssa name, source name) ("unknown", why)
Atoms   (op, A, B) with op in == != < <= > >=, ("true", T), ("false", T)
Cells   ("const", v) ("byte", T, k) ("byte_le", T, k) ("unknown",)
"""
from __future__ import annotations

import json
from fractions import Fraction
from math import ceil, floor

C0 = ("const", 0)
NIL = ("nil",)
CMP_OPS = ("==", "!=", "<", "<=", ">", ">=")
NEG = {"==": "!=", "!=": "==", "<": ">=", ">=": "<", ">": "<=", "<=": ">", "true": "false", "false": "true"}
FLIP = {"==": "==", "!=": "!=", "<": ">", ">": "<", "<=": ">=", ">=": "<="}
UNKNOWN_CELL = ("unknown",)


def const(v: int):
    return ("const", int(v))


def is_const(t) -> bool:
    return isinstance(t, tuple) and len(t) == 2 and t[0] == "const"


def to_json(x):
    """Tuples become lists (recursively); everything else is kept."""
    if isinstance(x, tuple):
        return [to_json(y) for y in x]
    if isinstance(x, list):
        return [to_json(y) for y in x]
    if isinstance(x, dict):
        return {k: to_json(v) for k, v in x.items()}
    return x


def from_json(x):
    if isinstance(x, list):
        return tuple(from_json(y) for y in x)
    return x


def key(t) -> str:
    """A total order on terms (their JSON text)."""
    return json.dumps(to_json(t), sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------------------------- integers
def wrap(v: int, info) -> int:
    """v reduced to a sized integer type's range; info = (bits, unsigned) or None (unbounded)."""
    if not info:
        return v
    bits, unsigned = info
    m = 1 << bits
    v %= m
    if not unsigned and v >= m // 2:
        v -= m
    return v


def go_div(a: int, b: int) -> int:
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def go_rem(a: int, b: int) -> int:
    return a - go_div(a, b) * b


def arith(op: str, a: int, b: int):
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        return go_div(a, b) if b else None
    if op == "%":
        return go_rem(a, b) if b else None
    if op == "&":
        return a & b
    if op == "|":
        return a | b
    if op == "^":
        return a ^ b
    if op == "<<":
        return a << b if 0 <= b <= 1024 else None
    if op == ">>":
        return a >> b if b >= 0 else None
    if op == "&^":
        return a & ~b
    return None


def op(o: str, a, b, info=None):
    """["op", o, A, B], folded when both sides are constants."""
    if is_const(a) and is_const(b):
        v = arith(o, a[1], b[1])
        if v is not None:
            return const(wrap(v, info))
    return ("op", o, a, b)


def unop(o: str, a, info=None):
    if is_const(a):
        if o == "-":
            return const(wrap(-a[1], info))
        if o == "^":
            return const(wrap(~a[1], info))
    if o == "!" and isinstance(a, tuple) and a[:1] == ("bool",):
        return ("bool", not a[1])
    return ("unop", o, a)


def plus(a, b):
    if is_const(b) and b[1] == 0:
        return a
    if is_const(a) and a[1] == 0:
        return b
    return op("+", a, b)


def minus(a, b):
    if is_const(b) and b[1] == 0:
        return a
    return op("-", a, b)


class Lengths:
    """Known array lengths of terms (from the types of the values they were built from), and len/cap folding."""

    def __init__(self):
        self.arr: dict = {}

    def note(self, t, n) -> None:
        if n is not None and isinstance(t, tuple):
            self.arr[t] = int(n)

    def length_of(self, t):
        """A constant length of t when one is known (fixed allocation, array, constant string, nil), else None."""
        if not isinstance(t, tuple) or not t:
            return None
        if t in self.arr:
            return self.arr[t]
        tag = t[0]
        if tag == "alloc" and is_const(t[2] if len(t) > 2 else None):
            return t[2][1]
        if tag == "str":
            return len(t[1].encode("utf-8"))
        if tag == "nil":
            return 0
        if tag == "slice":
            lo = t[2] if t[2] is not None else C0
            hi = t[3] if t[3] is not None else self._len_term(t[1])
            r = op("-", hi, lo)
            return r[1] if is_const(r) else None
        return None

    def capacity_of(self, t):
        if not isinstance(t, tuple) or not t:
            return None
        if t in self.arr:
            return self.arr[t]
        tag = t[0]
        if tag == "alloc" and is_const(t[2] if len(t) > 2 else None):
            return t[2][1]
        if tag == "nil":
            return 0
        if tag == "slice":
            lo = t[2] if t[2] is not None else C0
            mx = t[4] if t[4] is not None else self._cap_term(t[1])
            r = op("-", mx, lo)
            return r[1] if is_const(r) else None
        return None

    def _len_term(self, t):
        n = self.length_of(t)
        return const(n) if n is not None else ("len", t)

    def _cap_term(self, t):
        n = self.capacity_of(t)
        return const(n) if n is not None else ("cap", t)

    def len_(self, t):
        return self._len_term(t)

    def cap_(self, t):
        return self._cap_term(t)


# ---------------------------------------------------------------------------------------------- atoms
def negate(a):
    if a[0] in ("true", "false"):
        return (NEG[a[0]], a[1])
    return (NEG[a[0]], a[1], a[2])


def universal(a):
    """True / False for atoms that hold / fail for every x by 0 <= len(x) <= cap(x); else None."""
    o, x, y = a
    def is_(t, tag):
        return isinstance(t, tuple) and t[:1] == (tag,)
    pairs = []
    # normalize to x REL y with REL in <=, <
    if o in (">", ">="):
        o, x, y = FLIP[o], y, x
    if o == "<=":
        if x == C0 and (is_(y, "len") or is_(y, "cap")):
            return True
        if is_(x, "len") and is_(y, "cap") and x[1] == y[1]:
            return True
    if o == "<":
        if (is_(x, "len") or is_(x, "cap")) and y == C0:
            return False
        if is_(x, "cap") and is_(y, "len") and x[1] == y[1]:
            return False
    del pairs
    return None


def fold_atom(a, nonnil=lambda t: False):
    """True / False when the atom folds (constants, identical sides, nil against nil or a non-nil term, the universal
    0 <= len(x) <= cap(x)), else None."""
    if a[0] in ("true", "false"):
        t = a[1]
        if isinstance(t, tuple) and t[:1] == ("bool",):
            return t[1] if a[0] == "true" else (not t[1])
        return None
    o, x, y = a
    if is_const(x) and is_const(y):
        return {"==": x[1] == y[1], "!=": x[1] != y[1], "<": x[1] < y[1], "<=": x[1] <= y[1],
                ">": x[1] > y[1], ">=": x[1] >= y[1]}[o]
    if x == y:
        return o in ("==", "<=", ">=")
    if o in ("==", "!="):
        for p, q in ((x, y), (y, x)):
            if q == NIL:
                if p == NIL:
                    return o == "=="
                if nonnil(p):
                    return o == "!="
        if x[:1] == y[:1] and x[:1] in (("bool",), ("str",)):
            return (x[1] == y[1]) == (o == "==")
    return universal(a)


# ---------------------------------------------------------------------------------------------- linear forms
def lin(t):
    """(coeffs {var term: int}, constant) with every maximal non-linear or non-constant subterm a variable."""
    if is_const(t):
        return {}, t[1]
    if isinstance(t, tuple) and t[:1] == ("op",):
        o, a, b = t[1], t[2], t[3]
        if o in ("+", "-"):
            ca, ka = lin(a)
            cb, kb = lin(b)
            s = 1 if o == "+" else -1
            out = dict(ca)
            for v, c in cb.items():
                out[v] = out.get(v, 0) + s * c
            return {v: c for v, c in out.items() if c}, ka + s * kb
        if o == "*":
            if is_const(a):
                cb, kb = lin(b)
                return {v: c * a[1] for v, c in cb.items() if c * a[1]}, kb * a[1]
            if is_const(b):
                ca, ka = lin(a)
                return {v: c * b[1] for v, c in ca.items() if c * b[1]}, ka * b[1]
    if isinstance(t, tuple) and t[:2] == ("unop", "-"):
        ca, ka = lin(t[2])
        return {v: -c for v, c in ca.items()}, -ka
    return {t: 1}, 0


def _canon(coeffs: dict) -> tuple:
    return tuple(sorted(coeffs.items(), key=lambda kv: key(kv[0])))


def norm(a):
    """The normal form of an atom: ("le" | "eq" | "ne", ((var, coeff), ...), c) for sum + c REL 0, or
    ("true" | "false", T)."""
    if a[0] in ("true", "false"):
        return a
    o, x, y = a
    cx, kx = lin(x)
    cy, ky = lin(y)
    co = dict(cx)
    for v, c in cy.items():
        co[v] = co.get(v, 0) - c
    co = {v: c for v, c in co.items() if c}
    k = kx - ky
    if o == "<":
        return ("le", _canon(co), k + 1)
    if o == "<=":
        return ("le", _canon(co), k)
    if o == ">":
        return ("le", _canon({v: -c for v, c in co.items()}), -k + 1)
    if o == ">=":
        return ("le", _canon({v: -c for v, c in co.items()}), -k)
    items = _canon(co)
    if items and items[0][1] < 0:
        items = tuple((v, -c) for v, c in items)
        k = -k
    return ("eq" if o == "==" else "ne", items, k)


def norm_negate(f):
    if f[0] in ("true", "false"):
        return (NEG[f[0]], f[1])
    if f[0] == "le":
        return ("le", tuple((v, -c) for v, c in f[1]), -f[2] + 1)
    return ("ne" if f[0] == "eq" else "eq", f[1], f[2])


INF = None


class Reasoner:
    """Implication over the assumed atoms (path conditions, dominator-edge atoms) and the loop facts.

    implied: an assumed atom has the same normal form, or the atom has one variable (after substituting variables
    whose interval is one point) and holds over the whole interval the facts give it; refuted: its negation is implied
    the same way, or it holds nowhere in that interval."""

    def __init__(self, facts=(), nonnil=lambda t: False):
        self.facts = list(facts)
        self.nonnil = nonnil
        self.forms = set()
        self.order = []      # the facts' normal forms in fact order (iteration never depends on hashing)
        for f in self.facts:
            n = norm(f)
            if n not in self.forms:
                self.forms.add(n)
                self.order.append(n)
        self._iv = None

    def plus(self, atom) -> "Reasoner":
        r = Reasoner(self.facts + [atom], self.nonnil)
        return r

    # intervals --------------------------------------------------------------------------------
    def _intervals(self):
        if self._iv is not None:
            return self._iv
        lo: dict = {}
        hi: dict = {}
        ne: dict = {}
        vars_ = set()
        for f in self.order:
            if f[0] in ("le", "eq", "ne"):
                for v, _ in f[1]:
                    vars_.add(v)
        for v in list(vars_):
            if v[:1] == ("cap",):
                vars_.add(("len", v[1]))
        for v in vars_:
            if v[:1] in (("len",), ("cap",)):
                lo[v] = 0

        def point(v):
            a, b = lo.get(v), hi.get(v)
            return a if a is not None and a == b else None

        empty = set()
        for _round in range(32):
            changed = False
            for f in self.order:
                if f[0] not in ("le", "eq", "ne"):
                    continue
                rest = []
                c = Fraction(f[2])
                for v, a in f[1]:
                    p = point(v)
                    if p is not None:
                        c += a * p
                    else:
                        rest.append((v, a))
                if len(rest) != 1:
                    continue
                v, a = rest[0]
                r = -c / a
                if f[0] == "le":
                    if a > 0:
                        nb = floor(r)
                        if hi.get(v) is None or nb < hi[v]:
                            hi[v] = nb
                            changed = True
                    else:
                        nb = ceil(r)
                        if lo.get(v) is None or nb > lo[v]:
                            lo[v] = nb
                            changed = True
                elif f[0] == "eq":
                    if r.denominator != 1:
                        empty.add(v)
                        continue
                    r = int(r)
                    if lo.get(v) is None or r > lo[v]:
                        lo[v] = r
                        changed = True
                    if hi.get(v) is None or r < hi[v]:
                        hi[v] = r
                        changed = True
                else:
                    if r.denominator == 1:
                        s = ne.setdefault(v, set())
                        if int(r) not in s:
                            s.add(int(r))
                            changed = True
            for v in sorted(set(lo) | set(hi), key=key):
                if v[:1] == ("cap",):
                    ll = lo.get(("len", v[1]))
                    if ll is not None and (lo.get(v) is None or ll > lo[v]):
                        lo[v] = ll
                        changed = True
            for v in sorted(ne, key=key):
                s = ne[v]
                while lo.get(v) is not None and lo[v] in s:
                    lo[v] += 1
                    changed = True
                while hi.get(v) is not None and hi[v] in s:
                    hi[v] -= 1
                    changed = True
            if not changed:
                break
        self._iv = (lo, hi, ne, empty)
        return self._iv

    def interval(self, v):
        lo, hi, ne, empty = self._intervals()
        base_lo = 0 if v[:1] in (("len",), ("cap",)) else None
        a = lo.get(v, base_lo)
        if v[:1] == ("cap",):
            ll = lo.get(("len", v[1]), 0)
            a = ll if a is None else max(a, ll)
        return a, hi.get(v), ne.get(v, set()), v in empty

    # queries ----------------------------------------------------------------------------------
    def status(self, atom):
        """True (implied), False (refuted) or None."""
        fo = fold_atom(atom, self.nonnil)
        if fo is not None:
            return fo
        f = norm(atom)
        if f in self.forms:
            return True
        if norm_negate(f) in self.forms:
            return False
        if f[0] in ("true", "false"):
            return None
        lo_, hi_, _ne, _empty = self._intervals()
        c = Fraction(f[2])
        rest = []
        for v, a in f[1]:
            lo, hi, ne, empty = self.interval(v)
            if lo is not None and lo == hi:
                c += a * lo
            else:
                rest.append((v, a))
        if not rest:
            return {"le": c <= 0, "eq": c == 0, "ne": c != 0}[f[0]]
        if len(rest) != 1:
            return None
        v, a = rest[0]
        lo, hi, ne, empty = self.interval(v)
        if empty or (lo is not None and hi is not None and lo > hi):
            return None
        if f[0] == "le":
            if a > 0:
                if hi is not None and a * hi + c <= 0:
                    return True
                if lo is not None and a * lo + c > 0:
                    return False
            else:
                if lo is not None and a * lo + c <= 0:
                    return True
                if hi is not None and a * hi + c > 0:
                    return False
            return None
        r = -c / a
        inside = r.denominator == 1 and (lo is None or r >= lo) and (hi is None or r <= hi) and int(r) not in ne
        if f[0] == "eq":
            if not inside:
                return False
            if lo is not None and lo == hi == r:
                return True
            return None
        if not inside:
            return True
        if lo is not None and lo == hi == r:
            return False
        return None

    def implies(self, atom) -> bool:
        return self.status(atom) is True


def atom_vars(a) -> list:
    """The variables of an atom's normal form."""
    f = norm(a)
    if f[0] in ("true", "false"):
        return [f[1]]
    return [v for v, _ in f[1]]


def witness_range(atom, var, lo: int, hi: int):
    """The least and greatest values of var in [lo, hi] that violate atom (linear in var alone), or None."""
    f = norm(atom)
    if f[0] not in ("le", "eq", "ne") or len(f[1]) != 1 or f[1][0][0] != var:
        return None
    a, c = f[1][0][1], f[2]

    def holds(x):
        s = a * x + c
        return {"le": s <= 0, "eq": s == 0, "ne": s != 0}[f[0]]
    bad = None
    if hi - lo <= 1 << 20:
        vals = [x for x in range(lo, hi + 1) if not holds(x)]
        if vals:
            bad = (vals[0], vals[-1])
        return bad
    return None
