"""goloop's loop shapes (I122; spec/M6/predictions/I122.json's definitions; the contract is
tests_m6/test_i122_goloop_loop_shapes.py). Two loop classes of the Go-op model, each defined from the Go specification
for any program of the shape, never from a corpus entry. holon.gen.goloop tries them only after its I67 class refuses an
op, and only for a loop body the Go frontend emitted under its opt-in loops "shapes" (the entry's "typed" section), so
an op in the I67 class, and every document without the opt-in, is modelled exactly as before.

S1 (range; "For statements with range clause"): the op has one parameter p and exactly one loop, init 0, step 1,
  cmp <, limit len(X), where X is p or a field path from p, a slice whose element type E is an integer type of at most
  32 bits. The range expression is evaluated once before the loop, so the trip count is len(X) at entry, read from the
  carrier; the iterations are i = 0, ..., len(X)-1 and iteration i's element is X[i], always in range. The frontend
  writes the range's index as (iv - 1) + 1 over int, which is iv exactly: int is 64 bits and 0 <= iv <= len(X) < 2**63.
  The carrier value is X's element sequence, of any length, one List<&2, U32> node per element: an unsigned E as its
  value, a signed E of n bits as value + 2**(n-1) (offset binary keeps the signed order, so E's comparison with a
  constant k is the unsigned comparison with k + 2**(n-1)). A body path's atoms compare the element with constants or
  the index with constants; the atom index < len(X) is the loop's own range, index >= len(X) its exit.
S2 (stride; "For statements with for clause", "Integer overflow"): the op has one parameter p, a byte array (or a
  pointer to one) of known length n, and exactly one counted loop with constant init, constant limit, constant step s
  other than 0 and 1 (either sign), cmp one of < <= > >= != ==, and an induction variable of an integer type T. The
  post statement i += s is an assignment of i + s in T, which wraps modulo 2**bits(T), so the trip sequence is
  iv_0 = init, iv_(k+1) = fit(iv_k + s, T) while cmp(iv_k, limit) holds in T's order; it is computed concretely (more
  than MAX_TRIP iterations is Unsupported). Iteration k reads the one cell p[a*iv_k + c] (the frontend's affine read);
  every affine value a*iv_k + c an atom compares is an exact integer inside T's range (else Unsupported: it would wrap),
  so each atom is evaluated at iv_k exactly, and becomes a set of iteration numbers (a constant outside T's range
  comes from a bounds check, which compares the index's value converted to int: the same exact comparison). Every index is in [0, n) and no
  two iterations read one byte. The carrier is the cell sequence (p[idx_0], ..., p[idx_(m-1)]), its cell map the
  explicit index tuple ("idx", (idx_0, ...)); every other byte of p is not modelled (0 on replay, as rule Y9).

Both: the outcome of a path is OPanic, OErr, ORet or continue (holon.gen.goloop._outcome); exit paths read no cell and
share one outcome; the body paths partition the sample points (every iteration, every sample cell value: exactly one
path holds). Anything else raises goloop's Unsupported, and the laws naming the op stay unbound and UNKNOWN. The
frontend's typed reading (ops "typed") is required: its reasoner reads sized arithmetic as opaque, so no path was
pruned by unbounded arithmetic, and a step other than 1 gets no init <= iv fact.

Nothing here names a target: every constant is read from the document.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import goint

MAX_TRIP = 4096


def _gl():
    from . import goloop
    return goloop


def _types(lb: dict) -> dict:
    import json
    return {json.dumps(t): ty for t, ty in (lb.get("typed") or {}).get("terms") or []}


def _ty(types: dict, t):
    import json
    return types.get(json.dumps(t))


def _carrier_path(t, param: str):
    """The field path (a tuple of names) when t is the parameter or a field path from it, through dereferences."""
    names = []
    while True:
        if t == ["param", param]:
            return tuple(reversed(names))
        if isinstance(t, list) and len(t) == 2 and t[0] == "deref":
            t = t[1]
            continue
        if isinstance(t, list) and len(t) == 3 and t[0] == "field" and isinstance(t[2], str):
            names.append(t[2])
            t = t[1]
            continue
        return None


# ====================================================================== S1
@dataclass
class RangeShape:
    op: str
    param: str
    path: tuple            # the field path from the parameter to the slice X (empty: X is the parameter)
    elem: str              # E, the element's Go integer type
    paths: list            # [goloop.Path_]: cell atoms over the encoded element, index thresholds over i
    exit: str
    samples: list = field(default_factory=list)
    horizon: int = 1       # iterations past which every index threshold is constant (the witness search's bound)
    kind: str = "S1"
    init: int = 0

    @property
    def n(self) -> int:
        return self.horizon

    def cell_map(self) -> tuple:
        return ("range", self.path)

    def bias(self) -> int:
        bits, signed = goint.itype(self.elem)
        return 1 << (bits - 1) if signed else 0

    def top(self) -> int:
        return (1 << goint.itype(self.elem)[0]) - 1

    def encode(self, xs: list[int]) -> list[int]:
        return [x + self.bias() for x in xs]

    def decode(self, cells: list[int]) -> list[int]:
        return [c - self.bias() for c in cells]

    def pick(self, h: int, i: int):
        gl = _gl()
        hits = [p for p in self.paths if all(gl.holds_cell(o, h, v) for o, v in p.cells)
                and all(gl.holds_index(c, i) for c in p.index)]
        if len(hits) != 1:
            raise gl.Unsupported(f"{self.op}: {len(hits)} body paths hold at cell {h}, index {i}")
        return hits[0]

    def witness_value(self, cells: list[int]):
        xs = self.decode(cells)
        return {".".join(self.path): xs} if self.path else xs


def shape_s1(name: str, op: dict, lb: dict):
    gl = _gl()
    U = gl.Unsupported
    param = op["params"][0]["name"]
    iv = lb.get("iv") or "i"
    lim = lb.get("limit")
    if not (gl._const(lb.get("init")) == 0 and lb.get("step") == 1 and lb.get("cmp") == "<"
            and isinstance(lim, list) and len(lim) == 2 and lim[0] == "len"):
        raise U(f"{name}: not a range from 0 to len(X), step 1 (class S1)")
    X = lim[1]
    path = _carrier_path(X, param)
    if path is None:
        raise U(f"{name}: the loop's bound len(X) does not read a slice the carrier holds (class S1)")
    types = _types(lb)
    xt = _ty(types, X) or (op["params"][0]["type"] if not path else None)
    if (lb.get("typed") or {}).get("stale"):
        raise U(f"{name}: the loop body loads a term after a store or a call (stale)")
    if iv_ := (lb.get("typed") or {}).get("iv_type"):
        if goint.itype(iv_) != (64, True):
            raise U(f"{name}: a range index of type {iv_} (class S1's index is int)")
    elem = None
    if isinstance(xt, str) and xt.startswith("[]"):
        elem = goint.ALIASES.get(xt[2:], xt[2:])

    def index_of(t):
        return gl.affine(t, iv)   # (iv - 1) + 1 is (1, 0): exact over int (the docstring)

    def element(t):
        """The element type when t reads X[iv] (a plain index or an elem-wrapped one), else None."""
        e = t
        et = None
        if isinstance(e, list) and len(e) == 3 and e[0] == "elem":
            et, e = e[1], e[2]
        if not (isinstance(e, list) and len(e) == 3 and e[0] == "index" and e[1] == X):
            return None
        if index_of(e[2]) != (1, 0):
            raise U(f"{name}: the body reads X at an index other than the range's own")
        return goint.ALIASES.get(et or _ty(types, t) or "", et or _ty(types, t) or "")

    body, exits, consts = [], [], []
    for p in lb["paths"]:
        cells, index, is_exit = [], [], False
        for atom in p["cond"]:
            if not (isinstance(atom, list) and len(atom) == 3 and atom[0] in gl.FLIP):
                raise U(f"{name}: condition {atom!r} is not a comparison")
            o, x, y = atom
            if y == ["len", X] or x == ["len", X]:
                oo, t = (o, x) if y == ["len", X] else (gl.FLIP[o], y)
                if index_of(t) != (1, 0):
                    raise U(f"{name}: a comparison of len(X) with {t!r}")
                if oo == "<":
                    continue                    # the loop's own range
                if oo == ">=":
                    is_exit = True
                    continue
                raise U(f"{name}: a comparison {oo} of the index with len(X)")
            kx, ky = gl._const(x), gl._const(y)
            if (kx is None) == (ky is None):
                raise U(f"{name}: condition {atom!r} does not compare a term with a constant")
            oo, t, k = (o, x, ky) if ky is not None else (gl.FLIP[o], y, kx)
            et = element(t)
            if et is not None:
                if elem is None:
                    elem = et
                if et != elem:
                    raise U(f"{name}: elements of two types, {elem} and {et}")
                info = goint.itype(elem)
                if info is None or info[0] > 32:
                    raise U(f"{name}: an element of type {elem} (class S1's elements are integers of at most 32 bits; "
                            "a 64-bit or non-integer element is outside it)")
                if goint.fit(k, elem) != k:
                    raise U(f"{name}: the constant {k} is not a value of {elem}")
                cells.append((oo, k))
                consts.append(k)
                continue
            a = index_of(t)
            if a is not None:
                index.append(gl.threshold(oo, a[0], a[1], k))
                continue
            raise U(f"{name}: condition {atom!r} reads more than the index and the element")
        out = gl._outcome(p)
        if is_exit:
            if cells:
                raise U(f"{name}: an exit path reads a cell")
            exits.append(out)
        else:
            body.append((cells, index, out, p.get("site")))
    if elem is None:
        raise U(f"{name}: the element type of X is not recorded")
    info = goint.itype(elem)
    if info is None or info[0] > 32:
        raise U(f"{name}: an element of type {elem} (class S1's elements are integers of at most 32 bits; a 64-bit "
                "or non-integer element is outside it)")
    if not exits or len(set(exits)) != 1 or exits[0] == "continue":
        raise U(f"{name}: the loop's exit paths end in {sorted(set(exits))} (the class has one outcome)")
    sh = RangeShape(name, param, path, elem, [], exits[0])
    b = sh.bias()
    paths = [gl.Path_([(o, v + b) for o, v in cells], index, out, site) for cells, index, out, site in body]
    if not any(p.outcome == "continue" for p in paths):
        raise U(f"{name}: no body path continues the loop")
    paths.sort(key=lambda p: (p.outcome != "continue", p.outcome, p.site or "", repr(p.cells), repr(p.index)))
    sh.paths = paths
    lo, hi = 0, sh.top()
    sh.samples = sorted(x for x in {v + d + b for v in consts for d in (-1, 0, 1)} | {lo, hi} if lo <= x <= hi)
    ts = [c[1] for p in paths for c in p.index if len(c) == 2]
    sh.horizon = max(ts + [0]) + 2
    for i in range(sh.horizon):
        for h in sh.samples:
            sh.pick(h, i)
    return sh


# ====================================================================== S2
@dataclass
class StrideShape:
    op: str
    param: str
    trip: list             # iv_0, ..., iv_(m-1): the induction values of the iterations, in T
    idx: tuple             # the byte each iteration reads
    paths: list            # [goloop.Path_]: cell atoms over the byte, index conditions ("set", frozenset of k)
    exit: str
    samples: list = field(default_factory=list)
    kind: str = "S2"
    init: int = 0

    @property
    def n(self) -> int:
        return len(self.trip)

    def cell_map(self) -> tuple:
        return ("idx", tuple(self.idx))

    def pick(self, h: int, i: int):
        gl = _gl()
        hits = [p for p in self.paths if all(gl.holds_cell(o, h, v) for o, v in p.cells)
                and all(holds(c, i) for c in p.index)]
        if len(hits) != 1:
            raise gl.Unsupported(f"{self.op}: {len(hits)} body paths hold at cell {h}, iteration {i}")
        return hits[0]

    def witness_value(self, cells: list[int]):
        return "0x" + bytes(cells).hex()


def holds(c, i: int) -> bool:
    if c[0] == "set":
        return i in c[1]
    return _gl().holds_index(c, i)


def shape_s2(name: str, op: dict, lb: dict):
    gl = _gl()
    U = gl.Unsupported
    param = op["params"][0]["name"]
    iv = lb.get("iv") or "i"
    typed = lb.get("typed") or {}
    if typed.get("stale"):
        raise U(f"{name}: the loop body loads a term after a store or a call (stale)")
    init, limit, s, cmp = gl._const(lb.get("init")), gl._const(lb.get("limit")), lb.get("step"), lb.get("cmp")
    if init is None or limit is None or not isinstance(s, int) or s in (0, 1) or cmp not in goint.CMPS:
        raise U(f"{name}: not a counted loop from a constant to a constant with a constant step other than 0 and 1 "
                "(class S2)")
    T = typed.get("iv_type")
    if not T or goint.itype(T) is None:
        raise U(f"{name}: the induction variable's type {T!r} is not a recorded integer type")
    n = (typed.get("lengths") or {}).get(param)
    if not isinstance(n, int) or n < 1:
        raise U(f"{name}: the parameter is not a byte array of known length (class S2)")
    if goint.fit(init, T) != init or goint.fit(limit, T) != limit:
        raise U(f"{name}: a loop constant is not a value of {T}")
    trip, v = [], init
    while goint.compare(cmp, T, v, limit):
        trip.append(v)
        if len(trip) > MAX_TRIP:
            raise U(f"{name}: more than {MAX_TRIP} iterations (or none ending)")
        v = goint.fit(v + s, T)
    if not trip:
        raise U(f"{name}: a loop of 0 iterations")
    bits, signed = goint.itype(T)
    lo_t, hi_t = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)

    def values(a: int, c: int) -> list[int]:
        out = []
        for x in trip:
            for w in (a * x, a * x + c):
                if not lo_t <= w <= hi_t:
                    raise U(f"{name}: the term {a}*iv + {c} leaves {T}'s range at iv = {x} (it would wrap)")
            out.append(a * x + c)
        return out

    neg = {"<": ">=", ">=": "<", ">": "<=", "<=": ">", "==": "!=", "!=": "=="}[cmp]
    m = len(trip)
    read, body, exits = None, [], []
    for p in lb["paths"]:
        cells, index, is_exit = [], [], False
        for atom in p["cond"]:
            if not (isinstance(atom, list) and len(atom) == 3 and atom[0] in gl.FLIP):
                raise U(f"{name}: condition {atom!r} is not a comparison")
            o, x, y = atom
            kx, ky = gl._const(x), gl._const(y)
            if (kx is None) == (ky is None):
                raise U(f"{name}: condition {atom!r} does not compare a term with a constant")
            oo, t, k = (o, x, ky) if ky is not None else (gl.FLIP[o], y, kx)
            if t == ["iv", iv] and k == limit and oo == neg:
                is_exit = True
                continue
            r = gl.cell_read(t, iv, param)
            if r is not None:
                if read is not None and r != read:
                    raise U(f"{name}: the body reads two cells, {read} and {r}")
                read = r
                if not 0 <= k <= 255:
                    raise U(f"{name}: a byte compared with {k}")
                cells.append((oo, k))
                continue
            a = gl.affine(t, iv)
            if a is None:
                raise U(f"{name}: condition {atom!r} reads more than the induction variable and the cell")
            # exact integers in T's range, so T's order is the integers' order; a constant outside T (a bounds
            # check, which compares the index's value converted to int) is compared with the same exact value
            vals = values(*a)
            index.append(("set", frozenset(j for j in range(m) if gl.holds_cell(oo, vals[j], k))))
        out = gl._outcome(p)
        if is_exit:
            if cells:
                raise U(f"{name}: an exit path reads a cell")
            exits.append(out)
        else:
            body.append(gl.Path_(cells, index, out, p.get("site")))
    if read is None:
        raise U(f"{name}: no cell read of the parameter")
    a, c = read
    idx = tuple(values(a, c))
    if any(not 0 <= j < n for j in idx):
        raise U(f"{name}: an iteration reads a byte outside [0, {n})")
    if len(set(idx)) != len(idx):
        raise U(f"{name}: two iterations read one byte")
    if not exits or len(set(exits)) != 1 or exits[0] == "continue":
        raise U(f"{name}: the loop's exit paths end in {sorted(set(exits))} (the class has one outcome)")
    if not any(p.outcome == "continue" for p in body):
        raise U(f"{name}: no body path continues the loop")
    body.sort(key=lambda p: (p.outcome != "continue", p.outcome, p.site or "", repr(p.cells),
                             repr([sorted(c[1]) if c[0] == "set" else c for c in p.index])))
    consts = {v for p in body for _, v in p.cells}
    samples = sorted(x for x in {v + d for v in consts for d in (-1, 0, 1)} | {0, 255} if 0 <= x <= 255)
    sh = StrideShape(name, param, trip, idx, body, exits[0], samples)
    for i in range(m):
        for h in sh.samples:
            sh.pick(h, i)
    return sh


# ====================================================================== SEQ (I126)
def _segment(name: str, param: str, n: int, lb: dict, nxt: str | None):
    """One loop of a SEQ op (spec/M6/predictions/I126.json's definitions): (trip, read, body paths over local iteration
    numbers, exit outcome), or Unsupported. nxt is the next loop's span (its exit paths end "next" naming it), None for
    the last loop (its exit paths share one outcome)."""
    gl = _gl()
    U = gl.Unsupported
    iv = lb.get("iv") or "i"
    typed = lb.get("typed") or {}
    if lb.get("paths") is None:
        raise U(f"{name}: a loop of the sequence has no paths")
    if typed.get("stale"):
        raise U(f"{name}: a loop of the sequence loads a term after a store or a call (stale)")
    init, limit, s, cmp = gl._const(lb.get("init")), gl._const(lb.get("limit")), lb.get("step"), lb.get("cmp")
    if init is None or limit is None or not isinstance(s, int) or s == 0 or cmp not in goint.CMPS:
        raise U(f"{name}: a loop of the sequence is not counted from a constant to a constant with a constant step")
    T = typed.get("iv_type")
    if not T or goint.itype(T) is None:
        raise U(f"{name}: the induction variable's type {T!r} is not a recorded integer type")
    if goint.fit(init, T) != init or goint.fit(limit, T) != limit:
        raise U(f"{name}: a loop constant is not a value of {T}")
    trip, v = [], init
    while goint.compare(cmp, T, v, limit):
        trip.append(v)
        if len(trip) > MAX_TRIP:
            raise U(f"{name}: more than {MAX_TRIP} iterations (or none ending)")
        v = goint.fit(v + s, T)
    bits, signed = goint.itype(T)
    lo_t, hi_t = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)

    def values(a: int, c: int, xs) -> list[int]:
        out = []
        for x in xs:
            for w in (a * x, a * x + c):
                if not lo_t <= w <= hi_t:
                    raise U(f"{name}: the term {a}*iv + {c} leaves {T}'s range at iv = {x} (it would wrap)")
            out.append(a * x + c)
        return out

    neg = {"<": ">=", ">=": "<", ">": "<=", "<=": ">", "==": "!=", "!=": "=="}[cmp]
    m = len(trip)
    read, body, exits = None, [], []
    for p in lb["paths"]:
        cells, index, is_exit, live = [], [], False, True
        for atom in p["cond"]:
            if not (isinstance(atom, list) and len(atom) == 3 and atom[0] in gl.FLIP):
                raise U(f"{name}: condition {atom!r} is not a comparison")
            o, x, y = atom
            kx, ky = gl._const(x), gl._const(y)
            if (kx is None) == (ky is None):
                raise U(f"{name}: condition {atom!r} does not compare a term with a constant")
            oo, t, k = (o, x, ky) if ky is not None else (gl.FLIP[o], y, kx)
            if t == ["iv", iv] and k == limit and oo == neg:
                is_exit = True
                continue
            r = gl.cell_read(t, iv, param)
            if r is not None:
                if read is not None and r != read:
                    raise U(f"{name}: the body reads two cells, {read} and {r}")
                read = r
                if not 0 <= k <= 255:
                    raise U(f"{name}: a byte compared with {k}")
                cells.append((oo, k))
                continue
            a = gl.affine(t, iv)
            if a is None:
                raise U(f"{name}: condition {atom!r} reads more than the induction variable and the cell")
            index.append((a, oo, k))
        end = p.get("end")
        if is_exit:
            if cells:
                raise U(f"{name}: an exit path reads a cell")
            # the exit is reached at the induction value after the trip: an index atom is evaluated there exactly
            if not all(gl.holds_cell(oo, w, k) for (a, oo, k) in index for w in values(*a, [v])):
                continue
            if end == "next":
                exits.append(("next", p.get("next")))
            else:
                exits.append((gl._outcome(p), None))
            continue
        if end == "next":
            raise U(f"{name}: a break out of a loop of the sequence (an early exit into the next loop)")
        out = gl._outcome(p)
        sets = [("set", frozenset(j for j, w in enumerate(values(*a, trip)) if gl.holds_cell(oo, w, k)))
                for (a, oo, k) in index]
        if live:
            body.append(gl.Path_(cells, sets, out, p.get("site")))
    want = {("next", nxt)} if nxt is not None else None
    if not exits:
        raise U(f"{name}: a loop of the sequence has no exit path")
    if want is not None and set(exits) != want:
        raise U(f"{name}: a loop's exit paths end in {sorted(set(e[0] for e in exits))}, not in the next loop")
    if want is None and (len(set(exits)) != 1 or exits[0][0] in ("continue", "next")):
        raise U(f"{name}: the last loop's exit paths end in {sorted(set(e[0] for e in exits))} (one outcome)")
    if read is None:
        if any(p.outcome != "continue" for p in body):
            raise U(f"{name}: a loop of the sequence reads no cell and does not only continue")
        return trip, None, [], exits[0][0]
    a, c = read
    idx = values(a, c, trip)
    if any(not 0 <= j < n for j in idx):
        raise U(f"{name}: an iteration reads a byte outside [0, {n})")
    if not any(p.outcome == "continue" for p in body):
        raise U(f"{name}: no body path of a loop of the sequence continues")
    return trip, idx, body, exits[0][0]


def shape_seq(name: str, op: dict):
    """Class SEQ (I126): the op's loop bodies, counted loops over one byte array, composed in program order; an empty
    loop (no read, every path continues) dropped once its trip is shown finite. The shape is I122's StrideShape over
    the concatenated trip, of kind SEQ."""
    gl = _gl()
    U = gl.Unsupported
    if name in gl.RESERVED or not gl.IDENT.match(name) or name.startswith(("gw_", "gs_")):
        raise U(f"op name {name!r} is reserved or not an identifier")
    params = op.get("params") or []
    if len(params) != 1:
        raise U(f"{name}: {len(params)} parameters")
    param = params[0]["name"]
    lbs = op.get("loop_bodies")
    if not isinstance(lbs, list) or not lbs:
        raise U(f"{name}: 0 loop bodies")
    forms = op.get("loop_forms") or []
    if len(forms) != len(lbs) or any(f.get("depth") != 1 for f in forms):
        raise U(f"{name}: a loop the frontend gave no body, or a nested loop (the sequence is every loop, at depth 1)")
    n = ((lbs[0].get("typed") or {}).get("lengths") or {}).get(param)
    if not isinstance(n, int) or n < 1:
        raise U(f"{name}: the parameter is not a byte array of known length (class SEQ)")
    trip, idx, paths, exit_, kept = [], [], [], None, 0
    for j, lb in enumerate(lbs):
        last = j == len(lbs) - 1
        t, ix, body, ex = _segment(name, param, n, lb, None if last else lbs[j + 1].get("span"))
        if last:
            exit_ = ex
        if ix is None:
            continue   # an empty loop: its trip ends (computed), it reads nothing and every path continues
        kept += 1
        off = len(trip)
        whole = frozenset(range(off, off + len(t)))
        for p in body:
            sets = [("set", frozenset(off + i for i in c[1])) for c in p.index]
            paths.append(gl.Path_(p.cells, [("set", whole)] + sets, p.outcome, p.site))
        trip += t
        idx += ix
    if len(lbs) < 2 and kept == len(lbs):
        raise U(f"{name}: one loop, not empty (the classes I67, S1 and S2 take one loop)")
    if not trip:
        raise U(f"{name}: every loop of the sequence is empty")
    if len(set(idx)) != len(idx):
        raise U(f"{name}: two iterations read one byte")
    paths.sort(key=lambda p: (p.outcome != "continue", p.outcome, p.site or "", repr(p.cells),
                              repr([sorted(c[1]) for c in p.index])))
    consts = {v for p in paths for _, v in p.cells}
    samples = sorted(x for x in {v + d for v in consts for d in (-1, 0, 1)} | {0, 255} if 0 <= x <= 255)
    sh = StrideShape(name, param, trip, tuple(idx), paths, exit_, samples, kind="SEQ")
    for i in range(sh.n):
        for h in sh.samples:
            sh.pick(h, i)
    return sh


# ====================================================================== dispatch, evaluation, text
def shape(name: str, op: dict):
    """The S1 or S2 shape of an op the I67 class refused, or goloop's Unsupported."""
    gl = _gl()
    params = op.get("params") or []
    if len(params) != 1:
        raise gl.Unsupported(f"{name}: {len(params)} parameters")
    lbs = op.get("loop_bodies")
    if not isinstance(lbs, list) or len(lbs) != 1:
        raise gl.Unsupported(f"{name}: {0 if not lbs else len(lbs)} loop bodies (the classes have one)")
    lb = lbs[0]
    if lb.get("paths") is None:
        raise gl.Unsupported(f"{name}: the loop body has no paths")
    if lb.get("limit") and isinstance(lb["limit"], list) and lb["limit"][:1] == ["len"]:
        return shape_s1(name, op, lb)
    return shape_s2(name, op, lb)


def is_shape(sh) -> bool:
    return isinstance(sh, (RangeShape, StrideShape))


def evaluate(sh, cells: list[int]) -> str:
    """The op's outcome on a cell sequence by its shape (a check of the generator, never a verdict)."""
    m = len(cells) if isinstance(sh, RangeShape) else sh.n
    for j in range(m):
        if j >= len(cells):
            return sh.exit
        o = sh.pick(cells[j], j).outcome
        if o != "continue":
            return o
    return sh.exit


def continue_value(sh, i: int):
    for h in sh.samples:
        if sh.pick(h, i).outcome == "continue":
            return h
    return None


def panic_witness(sh):
    """The shortest panic witness: the first iteration k at which a panic path holds for some cell value, every
    earlier iteration at its smallest continue value; S1's witness ends at k (its length is k + 1), S2's has every
    iteration's cell (the later ones at their smallest continue value, else 0)."""
    m = sh.n
    for k in range(m):
        h = next((v for v in sh.samples if sh.pick(v, k).outcome == "OPanic"), None)
        if h is not None:
            pre = [continue_value(sh, j) for j in range(k)]
            if any(x is None for x in pre):
                return None
            if isinstance(sh, RangeShape):
                return pre + [h]
            return pre + [h] + [continue_value(sh, j) or 0 for j in range(k + 1, m)]
        if continue_value(sh, k) is None:
            return None
    return None


def candidates(sh) -> list[tuple[str, list[int]]]:
    out = []
    w = panic_witness(sh)
    if w is not None:
        out.append((f"the shortest panic witness of {sh.op}", w))
    if isinstance(sh, RangeShape):
        out.append((f"the empty sequence ({sh.op})", []))
    c = [continue_value(sh, j) for j in range(sh.n)]
    if all(x is not None for x in c):
        out.append((f"the continue values of {sh.op}", c))
    return out


PRELUDE = '''\
# I122: the length of a cell sequence (class S1's trip count, read from the carrier)
def gs_len(hs: List<&2, U32>) -> Nat:
  match hs:
    case Nil{}:
      0n
    case Con{h, t}:
      1n+gs_len(t)
'''


def _set_test(s: frozenset) -> str:
    ks = sorted(s)
    if not ks:
        return "False{}"
    runs, start = [], ks[0]
    for a, b in zip(ks, ks[1:] + [None]):
        if b != a + 1:
            runs.append((start, a + 1))
            start = b
    tests = [f"Bool.and(Nat.is_le({lo}n, i), Nat.is_lt(i, {hi}n))" for lo, hi in runs]
    out = tests[-1]
    for t in reversed(tests[:-1]):
        out = f"Bool.or({t}, {out})"
    return out


def _test(p) -> str:
    gl = _gl()
    return gl._and([f"{gl.U32_CMP[o]}(h, {v})" for o, v in p.cells]
                   + [_set_test(c[1]) if c[0] == "set" else gl._index_test(c) for c in p.index])


def op_text(sh) -> str:
    """One op's definitions, as goloop's op_text writes an I67 op's (selectors, body, step, run), with S1's fuel the
    sequence's length and S2's iteration index the iteration number."""
    gl = _gl()
    op, ps = sh.op, sh.paths
    if isinstance(sh, RangeShape):
        what = (f"class S1: cell k is {sh.param}{''.join('.' + f for f in sh.path)}[k] ({sh.elem}"
                f"{', offset ' + str(sh.bias()) if sh.bias() else ''}), len cells; exit outcome {sh.exit}")
        fuel = "gs_len(hs)"
    elif sh.kind == "SEQ":   # I126
        what = (f"class SEQ: cell k is {sh.param}[idx_k], idx = {list(sh.idx)}, the loops' trips in program order "
                f"{sh.trip}; exit outcome {sh.exit}")
        fuel = f"{sh.n}n"
    else:
        what = (f"class S2: cell k is {sh.param}[idx_k], idx = {list(sh.idx)}, trip {sh.trip}; exit outcome "
                f"{sh.exit}")
        fuel = f"{sh.n}n"
    lines = [f"# {op}: {what}"]
    for k in range(len(ps) - 2, -1, -1):
        nxt = gl._result(ps[-1]) if k == len(ps) - 2 else f"sel_{op}_{k + 1}({_test(ps[k + 1])}, h, i, nx)"
        lines += [f"def sel_{op}_{k}(t: Bool, +h: U32, +i: Nat, +nx: St) -> Res:", "  match t:", "    case True{}:",
                  f"      {gl._result(ps[k])}", "    case False{}:", f"      {nxt}", ""]
    first = f"sel_{op}_0({_test(ps[0])}, h, i, nx)" if len(ps) > 1 else gl._result(ps[0])
    lines += [f"def body_{op}(+h: U32, +i: Nat, +nx: St) -> Res:", f"  {first}", "",
              f"def step_{op}(st: St) -> Res:", "  match st:", "    case St{hs, +i}:", "      match hs:",
              "        case Nil{}:", f"          Fin{{{sh.exit}{{}}}}", "        case Con{h, t}:",
              f"          body_{op}(h, i, St{{t, 1n+i}})", "",
              f"def run_{op}(fuel: Nat, r: Res) -> Out:", "  match fuel r:", "    case 0n Next{st}:",
              f"      {sh.exit}{{}}", "    case 0n Fin{o}:", "      o", "    case 1n+p Next{st}:",
              f"      run_{op}(p, step_{op}(st))", "    case 1n+p Fin{o}:", "      o", "",
              f"def {op}({'+' if isinstance(sh, RangeShape) else ''}hs: List<&2, U32>) -> Out:",
              f"  run_{op}({fuel}, Next{{St{{hs, 0n}}}})", "",
              f"def ok_{op}(hs: List<&2, U32>) -> Bool:", f"  Bool.not(is_panic({op}(hs)))", ""]
    return "\n".join(lines)


def op_defs(sh) -> dict[str, list[str]]:
    op = sh.op
    key = "A-goshapes-range" if isinstance(sh, RangeShape) else "A-goshapes-seq" if sh.kind == "SEQ" else \
        "A-goshapes-stride"
    return {key: [op, f"step_{op}", f"run_{op}"], "A-goloop-outcome": [f"ok_{op}"],
            "A-goloop-sites": [f"body_{op}"] + [f"sel_{op}_{k}" for k in range(len(sh.paths) - 1)]}


TEXTS = {
    "A-goshapes-range": "Class S1 (I122): an op's argument is the element sequence of the slice its one for-range loop "
                        "ranges over (the parameter or a field path from it), of any length, each element an integer of "
                        "at most 32 bits (a signed one in offset binary); the trip count is the sequence's length, as "
                        "the range expression is evaluated once; every other field or memory of the carrier, and a nil "
                        "receiver, is not modelled.",
    "A-goshapes-stride": "Class S2 (I122): an op's argument is the sequence of the bytes its one counted loop reads, "
                         "one per iteration of the trip sequence computed in the induction variable's Go type with "
                         "wraparound (iv_(k+1) = fit(iv_k + step, T)); every other byte of the array is not modelled "
                         "(0 on replay, rule Y9).",
    "A-goshapes-prelude": "The length of a cell sequence (gs_len), class S1's trip count.",
    "A-goshapes-seq": "Class SEQ (I126): an op's argument is the sequence of the bytes its counted loops read, in "
                      "program order, one per iteration of each loop's trip sequence computed in its induction "
                      "variable's Go type with wraparound; a loop that reads nothing and only continues is dropped once "
                      "its trip is shown finite; every other byte of the array is not modelled (0 on replay, rule Y9).",
}
