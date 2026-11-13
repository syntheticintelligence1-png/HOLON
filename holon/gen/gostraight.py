"""The Go-op model's straight-line class (BUILD_PLAN row I117; HUMAN_ANSWERS Q90): an op with no loop whose paths the Go
frontend enumerated under its config's ops "typed" (holon.frontends.go: every typed term's Go type is recorded, and
the reasoner reads sized arithmetic as opaque, so no branch is pruned by unbounded arithmetic).

The carrier is the op's one parameter, in one of two kinds:
  * bytes: a byte array of n cells (the frontend's "typed" lengths): cell k is byte k, so the cell map is (1, 0, n), the
    same carrier value as a loop op reading every byte;
  * fields (HUMAN_ANSWERS Q91 (1), guards over the carrier's fields): a struct or a pointer to one, whose leaves are
    the fields the component's ops read (a field path from the parameter): an integer field, a bool field, a field
    compared with nil (its nil-ness) or the len of a field. Each leaf is two U32 cells (hi, lo), its slot the leaf's
    place in the sorted leaves of the whole component (so every op of the component reads one carrier value): an
    integer field's value is hi * 2**32 + lo fit to its type, a bool is lo != 0, nil-ness is lo == 0, a len is
    (hi mod 2**31) * 2**32 + lo (a length is in [0, 2**63)). A nil receiver is not a value of the model (rule
    A-goloop-fields), and an op whose paths load a field after a store or a call (the frontend's "stale") is not
    stated exactly (the load's term reads the memory as before), so it is Unsupported.
A path is the conjunction of its
condition atoms, each a comparison of two integer terms over the cells; its outcome is its end (OPanic, OErr, ORet).
Every term is evaluated with Go's integer semantics (holon.gen.goint), by the reference here and by the model text
(Bend, over Word(64n)); the two meet only through Bend's acceptance of a counter-law, never by trust.

An op is in the class only when every atom of every path is stated exactly:
  * a term is a cell (a constant index of the parameter, of type byte or uint8), a constant (of its context's type),
    an arithmetic op, a unary op or a conversion of an integer type the frontend recorded unambiguously;
  * a term that can panic is not stated exactly, because the frontend's paths record no panic for it: a division or
    remainder whose divisor is not a non-zero constant, a shift whose count is not a constant and is of a signed type;
  * the paths partition the cell values at every sample point (one path holds; checked here, as goloop checks its
    body paths).
Anything else is Unsupported: its laws stay UNKNOWN (and unbound, I115).
"""
from __future__ import annotations

import itertools
import json
import random
from dataclasses import dataclass, field

from . import goint as GI

CELL_TYPES = ("byte", "uint8")
MAX_POINTS = 1 << 16   # sample points per op (the product of the per-leaf samples, else a seeded subset)
SEED = 117
LEN_HI = 0x7fffffff


class Unsupported(Exception):
    pass


def _key(t) -> str:
    return json.dumps(t, sort_keys=True, ensure_ascii=False)


def _is_const(t) -> bool:
    return isinstance(t, list) and len(t) == 2 and t[0] == "const" and isinstance(t[1], int) \
        and not isinstance(t[1], bool)


def _is_nil(t) -> bool:
    return t == ["nil"]


@dataclass
class Straight:
    op: str
    param: str
    kind: str                 # "bytes" | "fields"
    n: int                    # the carrier's cells (set by finalize for fields)
    paths: list               # [(atoms, outcome, site)]
    types: dict               # key(term) -> Go type
    leaves: dict = field(default_factory=dict)    # key(leaf) -> (leaf term, leaf kind, Go type)
    slots: dict = field(default_factory=dict)     # key(leaf) -> first cell
    consts: set = field(default_factory=set)
    atom_types: dict = field(default_factory=dict)

    def cell_map(self) -> tuple:
        return (1, 0, self.n) if self.kind == "bytes" else ("fields", self.n)

    # ------------------------------------------------------------------ leaves
    def _base_param(self, b) -> bool:
        while isinstance(b, list) and len(b) == 2 and b[0] == "deref":
            b = b[1]
        return b == ["param", self.param]

    def byte_cell(self, t):
        if self.kind != "bytes":
            return None
        if not (isinstance(t, list) and len(t) == 3 and t[0] == "index" and _is_const(t[2])
                and self._base_param(t[1])):
            return None
        k = t[2][1]
        if not 0 <= k < self.n:
            raise Unsupported(f"{self.op}: a cell index {k} outside the {self.n} cells")
        return k

    def is_field(self, t) -> bool:
        """A field path from the parameter: ["field", <the parameter or a field path>, name]."""
        if self.kind != "fields" or not (isinstance(t, list) and len(t) == 3 and t[0] == "field"
                                         and isinstance(t[2], str)):
            return False
        b = t[1]
        return self._base_param(b) or self.is_field(b)

    def leaf(self, t, kind: str, ty: str):
        k = _key(t)
        old = self.leaves.get(k)
        if old is not None and old[1:] != (kind, ty):
            raise Unsupported(f"{self.op}: the leaf {t!r} is read as {old[1]} and as {kind}")
        self.leaves[k] = (t, kind, ty)

    def tyof(self, t, ctx: str | None = None) -> str:
        if _is_const(t):
            if ctx is None:
                raise Unsupported(f"{self.op}: a constant {t[1]} with no typed context")
            return ctx
        ty = self.types.get(_key(t), "<none>")
        if ty is None:
            raise Unsupported(f"{self.op}: the term {str(t)[:120]} has two Go types")
        if ty == "<none>":
            raise Unsupported(f"{self.op}: the term {str(t)[:120]} has no recorded Go type")
        ty = GI.ALIASES.get(ty, ty)
        if GI.itype(ty) is None:
            raise Unsupported(f"{self.op}: the term {str(t)[:120]} is of type {ty} (not an integer type)")
        return ty

    # ------------------------------------------------------------------ the class (stated exactly or Unsupported)
    def check_term(self, t, ctx: str | None = None) -> str:
        """The integer term's Go type, or Unsupported when the term is not stated exactly."""
        if _is_const(t):
            self.consts.add(t[1])
            return self.tyof(t, ctx)
        k = self.byte_cell(t)
        if k is not None:
            ty = self.types.get(_key(t))
            if ty not in CELL_TYPES:
                raise Unsupported(f"{self.op}: the cell {k} is of type {ty} (a cell is a byte)")
            self.leaf(t, "byte", "uint8")
            return "uint8"
        if self.is_field(t):
            ty = self.tyof(t)
            self.leaf(t, "int", ty)
            return ty
        if isinstance(t, list) and len(t) == 2 and t[0] == "len" and self.is_field(t[1]):
            self.leaf(t, "len", "int")
            return "int"
        if isinstance(t, list) and len(t) == 4 and t[0] == "op" and t[1] in GI.BINOPS:
            ty = self.tyof(t)
            o, a, b = t[1], t[2], t[3]
            if self.check_term(a, ty) != ty:
                raise Unsupported(f"{self.op}: an operand of another type in a {ty} op")
            if o in ("<<", ">>"):
                if _is_const(b):
                    if b[1] < 0:
                        raise Unsupported(f"{self.op}: a negative constant shift count")
                    self.consts.add(b[1])
                elif GI.itype(self.check_term(b))[1]:
                    raise Unsupported(f"{self.op}: a shift by a signed count, whose negative-count panic the "
                                      "frontend's paths do not record")
                return ty
            if o in ("/", "%") and not (_is_const(b) and b[1] != 0):
                raise Unsupported(f"{self.op}: a division by a non-constant, whose zero-divisor panic the frontend's "
                                  "paths do not record")
            if self.check_term(b, ty) != ty:
                raise Unsupported(f"{self.op}: an operand of another type in a {ty} op")
            return ty
        if isinstance(t, list) and len(t) == 3 and t[0] == "unop" and t[1] in GI.UNOPS:
            ty = self.tyof(t)
            if self.check_term(t[2], ty) != ty:
                raise Unsupported(f"{self.op}: a unary operand of another type")
            return ty
        if isinstance(t, list) and len(t) == 3 and t[0] == "convert" and isinstance(t[1], str):
            ty = GI.ALIASES.get(t[1], t[1])
            if GI.itype(ty) is None:
                raise Unsupported(f"{self.op}: a conversion to {t[1]}")
            if _is_const(t[2]):
                raise Unsupported(f"{self.op}: a conversion of a constant")
            self.check_term(t[2])
            return ty
        raise Unsupported(f"{self.op}: the term {str(t)[:120]} is outside the straight-line class")

    def check_atom(self, a) -> str:
        """The atom's comparison type: an integer type, "bool" (a bool field) or "nil" (a field's nil-ness)."""
        if isinstance(a, list) and len(a) == 2 and a[0] in ("true", "false") and self.is_field(a[1]):
            if self.types.get(_key(a[1])) != "bool":
                raise Unsupported(f"{self.op}: a truth test of a field that is not a bool")
            self.leaf(a[1], "bool", "bool")
            return "bool"
        if not (isinstance(a, list) and len(a) == 3 and a[0] in GI.CMPS):
            raise Unsupported(f"{self.op}: the condition {str(a)[:120]} is not an integer comparison")
        x, y = a[1], a[2]
        if a[0] in ("==", "!=") and (_is_nil(x) or _is_nil(y)):
            f = y if _is_nil(x) else x
            if not self.is_field(f) or self.types.get(_key(f)) in (None, "<none>"):
                raise Unsupported(f"{self.op}: a nil comparison of {str(f)[:120]}, not a field")
            self.leaf(f, "nil", self.types.get(_key(f)))
            return "nil"
        if _is_const(x) and _is_const(y):
            raise Unsupported(f"{self.op}: a comparison of two constants")
        tx = None if _is_const(x) else self.check_term(x)
        ty = None if _is_const(y) else self.check_term(y)
        t = tx or ty
        if tx and ty and tx != ty:
            raise Unsupported(f"{self.op}: a comparison of {tx} with {ty}")
        for s in (x, y):
            if _is_const(s):
                self.check_term(s, t)
        return t

    # ------------------------------------------------------------------ the reference
    def leaf_value(self, t, cells):
        k = _key(t)
        _, kind, ty = self.leaves[k]
        i = self.slots[k]
        if kind == "byte":
            return cells[i] if i < len(cells) else 0
        hi, lo = (cells[i] if i < len(cells) else 0), (cells[i + 1] if i + 1 < len(cells) else 0)
        if kind == "int":
            return GI.fit((hi << 32) | lo, ty)
        if kind == "len":
            return ((hi & LEN_HI) << 32) | lo
        if kind == "bool":
            return lo != 0
        return lo == 0   # nil-ness

    def value(self, t, cells, ctx: str | None = None) -> int:
        """The term's Go value at the cells (the reference semantics, holon.gen.goint)."""
        if _is_const(t):
            return GI.fit(t[1], ctx)
        if _key(t) in self.leaves:
            return self.leaf_value(t, cells)
        if t[0] == "op":
            ty = self.tyof(t)
            o = t[1]
            a = self.value(t[2], cells, ty)
            if o in ("<<", ">>"):
                if _is_const(t[3]):
                    return GI.binop(o, ty, a, t[3][1], "uint64")
                return GI.binop(o, ty, a, self.value(t[3], cells), self.tyof(t[3]))
            return GI.binop(o, ty, a, self.value(t[3], cells, ty))
        if t[0] == "unop":
            ty = self.tyof(t)
            return GI.unop(t[1], ty, self.value(t[2], cells, ty))
        if t[0] == "convert":
            return GI.fit(self.value(t[2], cells), GI.ALIASES.get(t[1], t[1]))
        raise Unsupported(f"{self.op}: {t!r}")

    def holds(self, a, cells) -> bool:
        t = self.atom_types[_key(a)]
        if t == "bool":
            v = self.leaf_value(a[1], cells)
            return v if a[0] == "true" else not v
        if t == "nil":
            f = a[2] if _is_nil(a[1]) else a[1]
            v = self.leaf_value(f, cells)
            return v if a[0] == "==" else not v
        return GI.compare(a[0], t, self.value(a[1], cells, t), self.value(a[2], cells, t))

    def pick(self, cells) -> tuple:
        hits = [p for p in self.paths if all(self.holds(a, cells) for a in p[0])]
        if len(hits) != 1:
            raise Unsupported(f"{self.op}: {len(hits)} paths hold at cells {cells}")
        return hits[0]

    def evaluate(self, cells) -> str:
        return self.pick(list(cells))[1]

    # ------------------------------------------------------------------ sample points (deterministic)
    def leaf_samples(self, k: str) -> list[list[int]]:
        """Each sample value of a leaf as its cells."""
        _, kind, ty = self.leaves[k]
        if kind in ("bool", "nil"):
            return [[0, 0], [0, 1]]
        if kind == "byte":
            vs = {0, 1, 2, 127, 128, 129, 254, 255} | {(c + d) & 0xff for c in self.consts for d in (-1, 0, 1)}
            return [[v] for v in sorted(vs)]
        if kind == "len":
            vs = {0, 1, 2} | {c + d for c in self.consts for d in (-1, 0, 1) if 0 <= c + d < 1 << 63}
        else:
            bits, signed = GI.itype(ty)
            lo, hi = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)
            vs = {0, 1, 2, -1, lo, hi} | {c + d for c in self.consts for d in (-1, 0, 1)}
            vs = {v for v in vs if lo <= v <= hi}
        return [[GI.w64(v) >> 32, GI.w64(v) & 0xffffffff] for v in sorted(vs)]

    def points(self):
        """Cell sequences (n cells, unread cells 0), in lexicographic order of the leaves' sample values (leaves by
        slot); a seeded subset (in that order) when the product exceeds MAX_POINTS."""
        ks = sorted(self.leaves, key=lambda k: self.slots[k])
        ss = [self.leaf_samples(k) for k in ks]
        total = 1
        for s in ss:
            total *= len(s)
        if total <= MAX_POINTS:
            combos = itertools.product(*[range(len(s)) for s in ss])
        else:
            rng = random.Random(SEED)
            combos = sorted({tuple(rng.randrange(len(s)) for s in ss) for _ in range(MAX_POINTS)})
        for combo in combos:
            cells = [0] * self.n
            for k, s, j in zip(ks, ss, combo):
                for d, v in enumerate(s[j]):
                    cells[self.slots[k] + d] = v
            yield cells

    def witness(self, outcome: str) -> list[int] | None:
        """The first sample point at which the op's outcome is `outcome`, or None."""
        for cells in self.points():
            if self.evaluate(cells) == outcome:
                return cells
        return None

    def witness_value(self, cells) -> object:
        """A witness as the record states it: the bytes in hex (bytes), or every leaf's Go value (fields)."""
        if self.kind == "bytes":
            return "0x" + bytes(cells).hex()
        out = {}
        for k in sorted(self.leaves):
            t, kind, _ = self.leaves[k]
            name = ".".join(_field_names(t[1] if kind == "len" else t))
            out[f"len({name})" if kind == "len" else (f"{name} == nil" if kind == "nil" else name)] = \
                self.leaf_value(t, cells)
        return out


def _field_names(t) -> list[str]:
    if isinstance(t, list) and len(t) == 3 and t[0] == "field":
        return _field_names(t[1]) + [t[2]]
    return []


def shape(name: str, op: dict, outcome_of) -> Straight:
    """The straight-line shape of an op before its slots are set (finalize), or Unsupported (outcome_of: goloop's path
    end -> Out constructor)."""
    typed = op.get("typed")
    if not isinstance(typed, dict):
        raise Unsupported(f"{name}: no typed terms (the frontend's ops \"typed\" is off)")
    if op.get("loop_bodies"):
        raise Unsupported(f"{name}: a loop (the straight-line class has none)")
    paths = op.get("paths")
    if not isinstance(paths, list) or not paths:
        raise Unsupported(f"{name}: no paths ({op.get('paths_reason')})")
    params = op.get("params") or []
    if len(params) != 1:
        raise Unsupported(f"{name}: {len(params)} parameters")
    param = params[0]["name"]
    n = (typed.get("lengths") or {}).get(param)
    kind = "bytes" if isinstance(n, int) and n >= 1 else "fields"
    if kind == "fields" and typed.get("stale"):
        raise Unsupported(f"{name}: a path loads a field after a store or a call (the load's term reads the memory "
                          "as before it)")
    types = {_key(t): ty for t, ty in typed.get("terms") or []}
    sh = Straight(name, param, kind, n if kind == "bytes" else 0, [], types)
    for p in paths:
        try:
            out = outcome_of(p)
        except Exception as e:   # noqa: BLE001 - goloop's Unsupported: an end the model cannot state
            raise Unsupported(str(e))
        if out == "continue":
            raise Unsupported(f"{name}: a continue path outside a loop")
        atoms = p.get("cond") or []
        for a in atoms:
            sh.atom_types[_key(a)] = sh.check_atom(a)
        sh.paths.append((atoms, out, p.get("site")))
    sh.paths.sort(key=lambda p: (p[1], p[2] or "", _key(p[0])))
    return sh


def finalize(sh: Straight, slots: dict | None, n: int | None) -> Straight:
    """Set the leaves' cells (bytes: cell k is byte k; fields: the component-wide slots) and check that the paths
    partition the cells at every sample point (one path holds), else Unsupported."""
    if sh.kind == "bytes":
        sh.slots = {k: t[2][1] for k, (t, _, _) in sh.leaves.items()}
    else:
        sh.slots, sh.n = {k: slots[k] for k in sh.leaves}, n
    for cells in sh.points():
        sh.pick(cells)
    return sh


def field_slots(shs: list) -> tuple[dict, int]:
    """The component's field leaves, sorted, each two cells: {key(leaf): first cell}, cell count."""
    ks = sorted({k for sh in shs if sh.kind == "fields" for k in sh.leaves})
    return {k: 2 * i for i, k in enumerate(ks)}, 2 * len(ks)


# ====================================================================== the model text
def _cell(i: int) -> str:
    return f"gw_cell(hs, {i}n)"


def leaf_text(sh: Straight, t) -> str:
    k = _key(t)
    _, kind, ty = sh.leaves[k]
    i = sh.slots[k]
    if kind == "byte":
        return f"gw_byte({_cell(i)})"
    if kind == "int":
        return GI.fit_text(ty, f"gw_k({_cell(i)}, {_cell(i + 1)})")
    if kind == "len":
        return f"gw_k(U32.and({_cell(i)}, {LEN_HI}), {_cell(i + 1)})"
    if kind == "bool":
        return f"Bool.not(U32.is_eq({_cell(i + 1)}, 0))"
    return f"U32.is_eq({_cell(i + 1)}, 0)"


def term_text(sh: Straight, t, ctx: str | None = None) -> str:
    if _is_const(t):
        return GI.const_text(GI.fit(t[1], ctx))
    if _key(t) in sh.leaves:
        return leaf_text(sh, t)
    if t[0] == "op":
        ty = sh.tyof(t)
        o = t[1]
        a = term_text(sh, t[2], ty)
        if o in ("<<", ">>"):
            b = GI.const_text(t[3][1]) if _is_const(t[3]) else term_text(sh, t[3])
            return GI.binop_text(o, ty, a, b)
        return GI.binop_text(o, ty, a, term_text(sh, t[3], ty))
    if t[0] == "unop":
        ty = sh.tyof(t)
        return GI.unop_text(t[1], ty, term_text(sh, t[2], ty))
    if t[0] == "convert":
        return GI.convert_text(GI.ALIASES.get(t[1], t[1]), term_text(sh, t[2]))
    raise Unsupported(f"{sh.op}: {t!r}")


def atom_text(sh: Straight, a) -> str:
    t = sh.atom_types[_key(a)]
    if t == "bool":
        x = leaf_text(sh, a[1])
        return x if a[0] == "true" else f"Bool.not({x})"
    if t == "nil":
        x = leaf_text(sh, a[2] if _is_nil(a[1]) else a[1])
        return x if a[0] == "==" else f"Bool.not({x})"
    return GI.compare_text(a[0], t, term_text(sh, a[1], t), term_text(sh, a[2], t))


def test_text(sh: Straight, atoms) -> str:
    xs = [atom_text(sh, a) for a in atoms]
    if not xs:
        return "True{}"
    out = xs[-1]
    for x in reversed(xs[:-1]):
        out = f"Bool.and({x}, {out})"
    return out


CELL_DEF = '''\
# a cell of the carrier (0 past its end: a witness always has every cell)
def gw_cell(hs: List<&2, U32>, k: Nat) -> U32:
  match hs k:
    case Nil{} _:
      0
    case Con{h, t} 0n:
      h
    case Con{h, t} 1n+p:
      gw_cell(t, p)
'''


def op_text(sh: Straight) -> str:
    """One op's definitions: a selector per path, from the last to the first (a definition precedes its use); the
    last path needs no test (the paths partition the cells, checked in finalize())."""
    op, ps = sh.op, sh.paths
    lines = [f"# {op}: straight-line over {sh.kind}, {len(ps)} paths, {sh.n} cells (Go integer semantics)"]
    for k in range(len(ps) - 2, -1, -1):
        nxt = f"{ps[-1][1]}{{}}" if k == len(ps) - 2 else f"sel_{op}_{k + 1}({test_text(sh, ps[k + 1][0])}, hs)"
        lines += [f"def sel_{op}_{k}(t: Bool, +hs: List<&2, U32>) -> Out:", "  match t:", "    case True{}:",
                  f"      {ps[k][1]}{{}}", "    case False{}:", f"      {nxt}", ""]
    first = f"sel_{op}_0({test_text(sh, ps[0][0])}, hs)" if len(ps) > 1 else f"{ps[0][1]}{{}}"
    lines += [f"def {op}(+hs: List<&2, U32>) -> Out:", f"  {first}", "",
              f"def ok_{op}(hs: List<&2, U32>) -> Bool:", f"  Bool.not(is_panic({op}(hs)))", ""]
    return "\n".join(lines)


def op_defs(sh: Straight) -> dict[str, list[str]]:
    op = sh.op
    return {"A-goloop-cells": [op], "A-goloop-outcome": [f"ok_{op}"],
            "A-goloop-sites": [f"sel_{op}_{k}" for k in range(len(sh.paths) - 1)]}


PRELUDE_DEFS = ("gw_cat", "gw_k", "gw_fill", "gw_bit", "gw_mask", "gw_fit.sel", "gw_fit", "gw_byte", "gw_top",
                "gw_sign", "gw_is_lt", "gw_is_eq", "gw_eq", "gw_ult", "gw_slt.sel", "gw_slt", "gw_lt", "gw_add",
                "gw_sub", "gw_mul", "gw_and", "gw_or", "gw_xor", "gw_not", "gw_andnot", "gw_negate", "gw_is_zero",
                "gw_shin.fin", "gw_shin", "GD", "gw_dstep.u", "gw_dstep.t", "gw_dstep.r", "gw_dstep.a", "gw_dstep",
                "gw_udm", "gw_quo", "gw_rmd", "gw_udiv", "gw_urem", "gw_abs.sel", "gw_abs", "gw_sdiv", "gw_srem",
                "gw_div", "gw_rem", "gw_shln", "gw_shrn", "gw_big", "gw_shl.sel", "gw_shl", "gw_ushr.sel", "gw_ushr",
                "gw_sshr.sel", "gw_sshr", "gw_shr", "gw_div_panics", "gw_shift_panics", "gw_cell")
