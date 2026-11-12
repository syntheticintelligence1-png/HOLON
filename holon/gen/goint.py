"""Go integer op semantics for the Go-op model (BUILD_PLAN row I117; HUMAN_ANSWERS Q90 (1)). Every definition is read
from The Go Programming Language Specification (go.dev/ref/spec), never from corpus code; the pinned toolchain checks
each on planted programs (tests_m6/test_i117_go_op_semantics.py, the differential test).

A value of a Go integer type T is represented by the 64-bit two's complement of its mathematical value: sign-extended
when T is signed, zero-extended when T is unsigned (fit). The pinned toolchain targets linux/amd64, so int, uint and
uintptr are 64 bits wide ("Numeric types": "The size of int and uint is implementation-specific"; the differential test
checks the width on the pinned toolchain).

  * + - * on T: the exact result reduced modulo 2**n into T's range ("Integer overflow": "For unsigned integer values,
    the operations +, -, *, and << are computed modulo 2**n ... For signed integers, the operations +, -, *, /, and <<
    may legally overflow and the resulting value exists and is deterministically defined by the signed integer
    representation"). Computed on 64 bits, then fit to T: n divides 64, so the low n bits agree.
  * / and %: truncated division, x = q*y + r with |r| < |y| and r of the sign of x ("Integer operators"); "if the
    dividend x is the most negative value for the int type of x, the quotient q = x / -1 is equal to x (and r = 0) due to
    two's-complement integer overflow"; a zero divisor panics at run time ("If the divisor is a constant, it must not be
    zero. If the divisor is zero at run time, a run-time panic occurs").
  * & | ^ &^: bitwise on the two's complement representation.
  * << and >>: "The shift count must be non-negative"; "if the left operand is a signed integer ... arithmetic shifts
    ... if it is an unsigned integer ... logical shifts. There is no upper limit on the shift count. Shifts behave as if
    the left operand is shifted n times by 1"; a negative count (a signed count's value below 0) panics at run time
    ("Arithmetic operators": "If the shift count is negative at run time, a run-time panic occurs"). The result's
    type is the left operand's.
  * unary -x is 0 - x and ^x is m ^ x with m all ones for unsigned x and -1 for signed x ("Arithmetic operators").
  * conversions between integer types: "When converting between integer types, if the value is a signed integer, it is
    sign extended implicitly to infinite precision; otherwise it is zero extended. It is then truncated to fit in the
    result type's size" (fit to the target).
  * comparisons == != < <= > >= order the mathematical values ("Comparison operators"): signed order on the
    sign-extended form, unsigned order on the zero-extended one.

The panicking cases are defined (panics), but the Go frontend's paths record no panic for a division or a shift: an op
whose terms can reach one is not stated exactly by the model, so holon.gen.goloop leaves it Unsupported.

An op this module cannot state exactly (a floating-point, complex or string operand, an untyped term) has no
definition: compile() raises Undefined and the op's laws stay UNKNOWN.
"""
from __future__ import annotations

ALIASES = {"byte": "uint8", "rune": "int32"}
WIDTH = {"int8": 8, "int16": 16, "int32": 32, "int64": 64, "int": 64,
         "uint8": 8, "uint16": 16, "uint32": 32, "uint64": 64, "uint": 64, "uintptr": 64}
BINOPS = ("+", "-", "*", "/", "%", "&", "|", "^", "&^", "<<", ">>")
CMPS = ("==", "!=", "<", "<=", ">", ">=")
UNOPS = ("-", "^", "+")
M64 = (1 << 64) - 1


class Undefined(Exception):
    """An op or type HOLON cannot state exactly: its laws stay UNKNOWN."""


class Panic(Exception):
    """A Go run-time panic (a zero divisor, a negative shift count)."""


def itype(t: str):
    """(bits, signed) of a Go integer type name, or None. A named type is not resolved (its underlying type is not in
    the document), so it is not an integer type here."""
    t = ALIASES.get(t, t)
    if t not in WIDTH:
        return None
    return WIDTH[t], not t.startswith("u")


# ====================================================================== the reference (Python integers)
def fit(v: int, t: str) -> int:
    """The value of type t that v converts to ("Conversions"): truncated to t's size, read in t's signedness."""
    info = itype(t)
    if info is None:
        raise Undefined(f"not an integer type: {t}")
    bits, signed = info
    v &= (1 << bits) - 1
    if signed and v >> (bits - 1):
        v -= 1 << bits
    return v


def _trunc_div(a: int, b: int) -> tuple[int, int]:
    q = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        q = -q
    return q, a - q * b


def binop(o: str, t: str, a: int, b: int, count_type: str | None = None) -> int:
    """x o y for x of type t (y of type t, or of count_type for a shift), as Go computes it; Panic on a zero divisor or a
    negative shift count."""
    a, b = fit(a, t), fit(b, count_type or t) if o in ("<<", ">>") else fit(b, t)
    if o == "+":
        return fit(a + b, t)
    if o == "-":
        return fit(a - b, t)
    if o == "*":
        return fit(a * b, t)
    if o in ("/", "%"):
        if b == 0:
            raise Panic("integer divide by zero")
        q, r = _trunc_div(a, b)
        return fit(q if o == "/" else r, t)
    if o == "&":
        return fit(a & b, t)
    if o == "|":
        return fit(a | b, t)
    if o == "^":
        return fit(a ^ b, t)
    if o == "&^":
        return fit(a & ~b, t)
    if o in ("<<", ">>"):
        if b < 0:
            raise Panic("negative shift amount")
        if o == "<<":
            return fit(a << min(b, 128), t)
        return fit(a >> min(b, 128), t)   # Python's >> is arithmetic on a signed value, logical on a non-negative one
    raise Undefined(f"binary op {o}")


def unop(o: str, t: str, a: int) -> int:
    a = fit(a, t)
    if o == "-":
        return fit(-a, t)
    if o == "^":
        return fit(~a, t)
    if o == "+":
        return a
    raise Undefined(f"unary op {o}")


def compare(o: str, t: str, a: int, b: int) -> bool:
    a, b = fit(a, t), fit(b, t)
    return {"==": a == b, "!=": a != b, "<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[o]


def w64(v: int) -> int:
    """The 64-bit two's complement word of a value (what the model computes on)."""
    return v & M64


# ====================================================================== the model (Bend over Word(64n))
# GW is Word(64n), LSB first (Base's Word: WCon{head, tail}). Every definition is total and structural; none is trusted:
# Bend evaluates them when it checks a counter-law, and the differential test compares them with the pinned toolchain.
PRELUDE = '''\
# ---- Go integer ops (holon.gen.goint): a Go integer as the 64-bit two's complement of its value, Word(64n), LSB first
def gw_cat(n: Nat, a: Word(n), b: Word(32n)) -> Word(Nat.add(n, 32n)):
  match n:
    case 0n:
      b
    case 1n+p:
      match a:
        case WCon{h, t}:
          WCon{h, gw_cat(p, t, b)}

# the word hi * 2**32 + lo
def gw_k(hi: U32, lo: U32) -> Word(64n):
  match hi lo:
    case U32{b} U32{a}:
      gw_cat(32n, a, b)

def gw_fill(n: Nat, +f: Bool) -> Word(n):
  match n:
    case 0n:
      WNil{}
    case 1n+p:
      WCon{f, gw_fill(p, f)}

def gw_bit(n: Nat, i: Nat, w: Word(n)) -> Bool:
  match n:
    case 0n:
      False{}
    case 1n+p:
      match i:
        case 0n:
          match w:
            case WCon{h, t}:
              h
        case 1n+ip:
          match w:
            case WCon{h, t}:
              gw_bit(p, ip, t)

# the word whose low k bits are 1
def gw_mask(n: Nat, k: Nat) -> Word(n):
  match n:
    case 0n:
      WNil{}
    case 1n+p:
      match k:
        case 0n:
          Word.zero(1n+p)
        case 1n+kp:
          WCon{True{}, gw_mask(p, kp)}

def gw_fit.sel(g: Bool, k: Nat, w: Word(64n)) -> Word(64n):
  match g:
    case True{}:
      Word.or(64n, w, Word.not(64n, gw_mask(64n, k)))
    case False{}:
      Word.and(64n, w, gw_mask(64n, k))

# fit to k bits (kt = k - 1): the low k bits of w, every higher bit bit kt when s (sign extension), else 0
def gw_fit(k: Nat, kt: Nat, s: Bool, +w: Word(64n)) -> Word(64n):
  gw_fit.sel(Bool.and(s, gw_bit(64n, kt, w)), k, w)

# a byte cell (its low 8 bits) as a uint8 value
def gw_byte(x: U32) -> Word(64n):
  gw_k(0, U32.and(x, 255))

def gw_top(n: Nat, f: Bool, w: Word(n)) -> Bool:
  match n:
    case 0n:
      f
    case 1n+p:
      match w:
        case WCon{h, t}:
          gw_top(p, h, t)

def gw_sign(w: Word(64n)) -> Bool:
  gw_top(64n, False{}, w)
'''
PRELUDE += '''
def gw_is_lt(c: Cmp) -> Bool:
  match c:
    case LT{}:
      True{}
    case EQ{}:
      False{}
    case GT{}:
      False{}

def gw_is_eq(c: Cmp) -> Bool:
  match c:
    case LT{}:
      False{}
    case EQ{}:
      True{}
    case GT{}:
      False{}

def gw_eq(a: Word(64n), b: Word(64n)) -> Bool:
  gw_is_eq(Word.cmp(64n, a, b))

def gw_ult(a: Word(64n), b: Word(64n)) -> Bool:
  gw_is_lt(Word.cmp(64n, a, b))

def gw_slt.sel(sa: Bool, sb: Bool, u: Bool) -> Bool:
  match sa sb:
    case True{} False{}:
      True{}
    case False{} True{}:
      False{}
    case _ _:
      u

# signed order: a negative value is below every non-negative one; within one sign the unsigned order of the words
def gw_slt(+a: Word(64n), +b: Word(64n)) -> Bool:
  gw_slt.sel(gw_sign(a), gw_sign(b), gw_ult(a, b))

def gw_lt(s: Bool, +a: Word(64n), +b: Word(64n)) -> Bool:
  match s:
    case True{}:
      gw_slt(a, b)
    case False{}:
      gw_ult(a, b)

def gw_add(a: Word(64n), b: Word(64n)) -> Word(64n):
  Word.add(64n, a, b)

def gw_sub(a: Word(64n), b: Word(64n)) -> Word(64n):
  Word.sub(64n, a, b)

def gw_mul(a: Word(64n), b: Word(64n)) -> Word(64n):
  Word.mul(64n, a, b)

def gw_and(a: Word(64n), b: Word(64n)) -> Word(64n):
  Word.and(64n, a, b)

def gw_or(a: Word(64n), b: Word(64n)) -> Word(64n):
  Word.or(64n, a, b)

def gw_xor(a: Word(64n), b: Word(64n)) -> Word(64n):
  Word.xor(64n, a, b)

def gw_not(a: Word(64n)) -> Word(64n):
  Word.not(64n, a)

def gw_andnot(a: Word(64n), b: Word(64n)) -> Word(64n):
  Word.and(64n, a, Word.not(64n, b))

def gw_negate(a: Word(64n)) -> Word(64n):
  Word.sub(64n, Word.zero(64n), a)

def gw_is_zero(a: Word(64n)) -> Bool:
  gw_eq(a, Word.zero(64n))

# ---- unsigned division of 64-bit words: 64 restoring steps, the dividend's bits taken from the top
def gw_shin.fin(r: Bool & Word(64n)) -> Word(64n):
  (_o, w) = r
  w

def gw_shin(c: Bool, w: Word(64n)) -> Word(64n):
  gw_shin.fin(Word.shl.out(64n, c, w))

# the state of a restoring division: the dividend's bits not yet taken (from the top), the remainder, the quotient
type GD is Data:
  GD{a: Word(64n), r: Word(64n), q: Word(64n)}

def gw_dstep.u(g: Bool, a2: Word(64n), +b: Word(64n), r2: Word(64n), q: Word(64n)) -> GD:
  match g:
    case True{}:
      GD{a2, Word.sub(64n, r2, b), gw_shin(True{}, q)}
    case False{}:
      GD{a2, r2, gw_shin(False{}, q)}

def gw_dstep.t(a2: Word(64n), +b: Word(64n), c: Bool, +r2: Word(64n), q: Word(64n)) -> GD:
  gw_dstep.u(Bool.or(c, Bool.not(gw_ult(r2, b))), a2, b, r2, q)

def gw_dstep.r(a2: Word(64n), +b: Word(64n), rr: Bool & Word(64n), q: Word(64n)) -> GD:
  (c, r2) = rr
  gw_dstep.t(a2, b, c, r2, q)

def gw_dstep.a(ab: Bool & Word(64n), +b: Word(64n), r: Word(64n), q: Word(64n)) -> GD:
  (bit, a2) = ab
  gw_dstep.r(a2, b, Word.shl.out(64n, bit, r), q)

# one step: shift the dividend's top bit into the remainder; subtract the divisor when it fits (or the shift carried)
def gw_dstep(+b: Word(64n), st: GD) -> GD:
  match st:
    case GD{a, r, q}:
      gw_dstep.a(Word.shl.out(64n, False{}, a), b, r, q)

def gw_udm(k: Nat, +b: Word(64n), st: GD) -> GD:
  match k:
    case 0n:
      st
    case 1n+p:
      gw_udm(p, b, gw_dstep(b, st))

def gw_quo(st: GD) -> Word(64n):
  match st:
    case GD{a, r, q}:
      q

def gw_rmd(st: GD) -> Word(64n):
  match st:
    case GD{a, r, q}:
      r

def gw_udiv(a: Word(64n), +b: Word(64n)) -> Word(64n):
  gw_quo(gw_udm(64n, b, GD{a, Word.zero(64n), Word.zero(64n)}))

def gw_urem(a: Word(64n), +b: Word(64n)) -> Word(64n):
  gw_rmd(gw_udm(64n, b, GD{a, Word.zero(64n), Word.zero(64n)}))

def gw_abs.sel(s: Bool, +a: Word(64n)) -> Word(64n):
  match s:
    case True{}:
      gw_negate(a)
    case False{}:
      a

def gw_abs(+a: Word(64n)) -> Word(64n):
  gw_abs.sel(gw_sign(a), a)

# truncated signed division: |a| / |b| unsigned, negated when the signs differ (MinInt / -1 is MinInt: 2**63 negated)
def gw_sdiv(+a: Word(64n), +b: Word(64n)) -> Word(64n):
  gw_abs.sel(Bool.xor(gw_sign(a), gw_sign(b)), gw_udiv(gw_abs(a), gw_abs(b)))

# the remainder has the sign of the dividend
def gw_srem(+a: Word(64n), +b: Word(64n)) -> Word(64n):
  gw_abs.sel(gw_sign(a), gw_urem(gw_abs(a), gw_abs(b)))

def gw_div(s: Bool, +a: Word(64n), +b: Word(64n)) -> Word(64n):
  match s:
    case True{}:
      gw_sdiv(a, b)
    case False{}:
      gw_udiv(a, b)

def gw_rem(s: Bool, +a: Word(64n), +b: Word(64n)) -> Word(64n):
  match s:
    case True{}:
      gw_srem(a, b)
    case False{}:
      gw_urem(a, b)

# ---- shifts: a count of 64 or more saturates (every bit shifted out, or the sign everywhere)
def gw_shln(n: Nat, w: Word(64n)) -> Word(64n):
  match n:
    case 0n:
      w
    case 1n+p:
      gw_shln(p, Word.shl(64n, w))

def gw_shrn(n: Nat, w: Word(64n)) -> Word(64n):
  match n:
    case 0n:
      w
    case 1n+p:
      gw_shrn(p, Word.shr(64n, w))

def gw_big(+c: Word(64n)) -> Bool:
  Bool.not(gw_ult(c, gw_k(0, 64)))

def gw_shl.sel(g: Bool, a: Word(64n), +c: Word(64n)) -> Word(64n):
  match g:
    case True{}:
      Word.zero(64n)
    case False{}:
      gw_shln(Word.to_nat(64n, c), a)

def gw_shl(a: Word(64n), +c: Word(64n)) -> Word(64n):
  gw_shl.sel(gw_big(c), a, c)

def gw_ushr.sel(g: Bool, a: Word(64n), +c: Word(64n)) -> Word(64n):
  match g:
    case True{}:
      Word.zero(64n)
    case False{}:
      gw_shrn(Word.to_nat(64n, c), a)

def gw_ushr(a: Word(64n), +c: Word(64n)) -> Word(64n):
  gw_ushr.sel(gw_big(c), a, c)

# arithmetic shift: a negative value is shifted as the complement of its complement
def gw_sshr.sel(neg: Bool, a: Word(64n), +c: Word(64n)) -> Word(64n):
  match neg:
    case True{}:
      gw_not(gw_ushr(gw_not(a), c))
    case False{}:
      gw_ushr(a, c)

def gw_sshr(+a: Word(64n), +c: Word(64n)) -> Word(64n):
  gw_sshr.sel(gw_sign(a), a, c)

def gw_shr(s: Bool, +a: Word(64n), +c: Word(64n)) -> Word(64n):
  match s:
    case True{}:
      gw_sshr(a, c)
    case False{}:
      gw_ushr(a, c)

# ---- the panicking cases: a zero divisor; a negative count of a signed count type
def gw_div_panics(b: Word(64n)) -> Bool:
  gw_is_zero(b)

def gw_shift_panics(s: Bool, c: Word(64n)) -> Bool:
  Bool.and(s, gw_sign(c))
'''

BIN_DEF = {"+": "gw_add", "-": "gw_sub", "*": "gw_mul", "&": "gw_and", "|": "gw_or", "^": "gw_xor", "&^": "gw_andnot"}


def bool_lit(b: bool) -> str:
    return "True{}" if b else "False{}"


def const_text(v: int) -> str:
    w = w64(v)
    return f"gw_k({w >> 32}, {w & 0xffffffff})"


def fit_text(t: str, x: str) -> str:
    bits, signed = itype(t)
    return x if bits == 64 else f"gw_fit({bits}n, {bits - 1}n, {bool_lit(signed)}, {x})"


def binop_text(o: str, t: str, a: str, b: str, count_type: str | None = None) -> str:
    """The model's x o y over words a and b of type t (count_type for a shift's count), fit to t. Raises Undefined for
    an op outside BINOPS."""
    if itype(t) is None:
        raise Undefined(f"not an integer type: {t}")
    s = bool_lit(itype(t)[1])
    if o in BIN_DEF:
        return fit_text(t, f"{BIN_DEF[o]}({a}, {b})")
    if o == "/":
        return fit_text(t, f"gw_div({s}, {a}, {b})")
    if o == "%":
        return fit_text(t, f"gw_rem({s}, {a}, {b})")
    if o == "<<":
        return fit_text(t, f"gw_shl({a}, {b})")
    if o == ">>":
        return fit_text(t, f"gw_shr({s}, {a}, {b})")
    raise Undefined(f"binary op {o}")


def unop_text(o: str, t: str, a: str) -> str:
    if itype(t) is None:
        raise Undefined(f"not an integer type: {t}")
    if o == "-":
        return fit_text(t, f"gw_negate({a})")
    if o == "^":
        return fit_text(t, f"gw_not({a})")
    if o == "+":
        return a
    raise Undefined(f"unary op {o}")


def compare_text(o: str, t: str, a: str, b: str) -> str:
    if itype(t) is None:
        raise Undefined(f"not an integer type: {t}")
    s = bool_lit(itype(t)[1])
    return {"==": f"gw_eq({a}, {b})", "!=": f"Bool.not(gw_eq({a}, {b}))", "<": f"gw_lt({s}, {a}, {b})",
            ">": f"gw_lt({s}, {b}, {a})", "<=": f"Bool.not(gw_lt({s}, {b}, {a}))",
            ">=": f"Bool.not(gw_lt({s}, {a}, {b}))"}[o]


def convert_text(t: str, a: str) -> str:
    if itype(t) is None:
        raise Undefined(f"not an integer type: {t}")
    return fit_text(t, a)
