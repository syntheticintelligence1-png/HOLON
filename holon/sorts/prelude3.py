"""The fixed Bend prelude of the M3 model (I30; holon.sorts.model3): 256-bit words as eight 32-bit limbs, byte strings,
memory regions, raw storage, hash tables and external-call answers.

Words. A 256-bit word is W{l0, .., l7}, eight U32 limbs, l0 the least significant. U32 is evaluated natively by
Bend's checker and by the BendTT kernel, so a concrete step evaluates in time polynomial in the width (the contract's
N8; the I20 model's one-Nat words are normalized in unary). Arithmetic is modular (+ - * wrap mod 2^256), / and %
give 0 for a zero divisor (Yul), comparisons are unsigned; w_add_ok, w_sub_ok and w_mul_ok decide whether the exact
result fits 256 bits (the document's ["fits", 256, ..] checks).

Byte strings and memory are List<&2, U32>, one byte per element; an unwritten memory byte is the sentinel 57005
(outside the byte range, BEND_PRIMER §4). Storage is the raw slot map of the contract (HSt{sl}: a list of KW{k, v};
an absent slot reads 0). Hash tables (HKB{b, v}) are parameters of the law (I12's hashes as parameters): a lookup of a
key the table does not hold answers 0. External calls are answered by the environment (HCall{to, d, ok, ret}).

No definition here names a target; the text is fixed (holon.sorts.model3 adds the per-document parts).

The kernel's evaluation shape (A30). BendTT reduces by name with substitution and normalizes the argument of every
reusable (`+`, q=2) binder of a closed term by walking it whole, and U32 is a 32-bit Word of Bools in it. So the prelude
keeps a reusable binder off every list it recurses on (a table, a slot map, the remaining bytes of a list: each would be
walked once per element), binds a variable inside the match arm that uses it (bend2 makes a variable used in two arms
reusable), and builds bytes and limbs bit by bit (u8, u_b4, u_be4w: a byte is 8 bits of a U32, not a 24-place shift).
Word addition skips the U32 adder on a zero limb and adds a carry with U32.inc; lengths count with U32.inc; word
equality stops at the first differing limb. Every definition computes the value the I30 prelude computed.
"""
from __future__ import annotations

SENTINEL = 57005
FUEL = 4097          # loop iterations a step may run (holon.extracted_eval.MAX_ITERATIONS + 1)


def _match_u32(var: str, bits: str, inner, ind: int, n: int = 32) -> list:
    """Lines matching the U32 `var` down to its low n bits <bits>0..<bits>(n-1) (bit 0 the least significant: Base's
    Word is little-endian; the higher bits are left unmatched), then inner(indent)."""
    out = [f"{' ' * ind}match {var}:", f"{' ' * ind}  case U32{{{bits}w}}:"]
    cur, ind = f"{bits}w", ind + 4
    for i in range(n):
        nxt = f"{bits}t{i}" if i < n - 1 else "_"
        out += [f"{' ' * ind}match {cur}:", f"{' ' * ind}  case WCon{{{bits}{i}, {nxt}}}:"]
        cur, ind = nxt, ind + 4
    return out + inner(ind)


def _u32_of(bits: list) -> str:
    """A U32 term of 32 Bool terms, the least significant first."""
    s = "WNil{}"
    for b in reversed(bits):
        s = f"WCon{{{b}, {s}}}"
    return f"U32{{{s}}}"


def _u8() -> str:
    """The U32 of eight bits (a byte)."""
    ps = ", ".join(f"b{i}: Bool" for i in range(8))
    return f"def u8({ps}) -> U32:\n  {_u32_of([f'b{i}' for i in range(8)] + ['False{}'] * 24)}\n"


def _u_b4() -> str:
    """The four bytes of a limb, the most significant first: a zero limb at once (the compiled model's common case,
    decided by a match so that the JavaScript evaluator skips the bits too), else bit by bit."""
    def inner(ind):
        parts = ["u8(" + ", ".join(f"a{8 * j + k}" for k in range(8)) + ")" for j in (3, 2, 1, 0)]
        return [f"{' ' * ind}[{', '.join(parts)}]"]
    return ("def u_b4n(x: U32) -> List<&2, U32>:\n" + "\n".join(_match_u32("x", "a", inner, 2)) + "\n\n"
            "def u_b4z(c: Bool, x: U32) -> List<&2, U32>:\n  match c:\n    case True{}:\n      [0, 0, 0, 0]\n"
            "    case False{}:\n      u_b4n(x)\n\n"
            "def u_b4(+x: U32) -> List<&2, U32>:\n  u_b4z(U32.is_eq(x, 0), x)\n")


def _u_be4w() -> str:
    """(x0 << 24) | (x1 << 16) | (x2 << 8) | x3 mod 2^32, bit by bit, for any four U32 (an unwritten memory byte is the
    sentinel, wider than a byte): only the bits that reach the result are matched."""
    def bits_of(ind):
        rs = []
        for k in range(32):
            terms = [f"d{k}"] + ([f"c{k - 8}"] if k >= 8 else []) + ([f"b{k - 16}"] if k >= 16 else []) + \
                    ([f"a{k - 24}"] if k >= 24 else [])
            t = terms[-1]
            for x in reversed(terms[:-1]):
                t = f"Bool.or({x}, {t})"
            rs.append(t)
        return [f"{' ' * ind}{_u32_of(rs)}"]
    nest = bits_of
    for var, bits, n in (("x3", "d", 32), ("x2", "c", 24), ("x1", "b", 16)):
        nest = (lambda v, b, k, f: (lambda ind: _match_u32(v, b, f, ind, k)))(var, bits, n, nest)
    return ("def u_be4w(x0: U32, x1: U32, x2: U32, x3: U32) -> U32:\n"
            + "\n".join(_match_u32("x0", "a", nest, 2, 8)) + "\n")


def _w_add(ok: bool) -> str:
    """Limb by limb with the carry as a Bool: t = a_i + b_i, s = t + carry, carry' = t < a_i or s < t (the I30 cy)."""
    name, ret = ("w_add_ok", "Bool") if ok else ("w_add", "W")
    lines = [f"def {name}(a: W, b: W) -> {ret}:", "  match a b:",
             "    case W{" + ", ".join(f"+a{i}" for i in range(8)) + "} W{" + ", ".join(f"b{i}" for i in range(8)) + "}:",
             "      +t0 = u_add(a0, b0)", "      +k1 = U32.is_lt(t0, a0)"]
    for i in range(1, 8):
        lines += [f"      +t{i} = u_add(a{i}, b{i})", f"      +s{i} = u_addc(t{i}, k{i})"]
        if i < 7 or ok:
            lines.append(f"      +k{i + 1} = Bool.or(U32.is_lt(t{i}, a{i}), U32.is_lt(s{i}, t{i}))")
    lines.append("      Bool.not(k8)" if ok else "      W{t0, " + ", ".join(f"s{i}" for i in range(1, 8)) + "}")
    return "\n".join(lines) + "\n"


def _w_sub() -> str:
    """Limb by limb with the borrow as a Bool: d = a_i - b_i, s = d - borrow, borrow' = a_i < b_i or (borrow and d is
    0) (the I30 bw)."""
    lines = ["def w_sub(a: W, b: W) -> W:", "  match a b:",
             "    case W{" + ", ".join(f"+a{i}" for i in range(8)) + "} W{" + ", ".join(f"+b{i}" for i in range(8)) + "}:",
             "      +d0 = u_sub(a0, b0)", "      +k1 = U32.is_lt(a0, b0)"]
    for i in range(1, 8):
        lines += [f"      +d{i} = u_sub(a{i}, b{i})", f"      +s{i} = u_subc(d{i}, k{i})"]
        if i < 7:
            lines.append(f"      +k{i + 1} = Bool.or(U32.is_lt(a{i}, b{i}), Bool.and(k{i}, U32.is_eq(d{i}, 0)))")
    lines.append("      W{d0, " + ", ".join(f"s{i}" for i in range(1, 8)) + "}")
    return "\n".join(lines) + "\n"

_PRELUDE = '''\
def ite(-A: Data, c: Bool, a: A, b: A) -> A:
  match c:
    case True{}:
      a
    case False{}:
      b

def b2u(b: Bool) -> U32:
  match b:
    case True{}:
      1
    case False{}:
      0

def u_nz(+x: U32) -> Bool:
  Bool.not(U32.is_eq(x, 0))

type W is Data:
  W{l0: U32, l1: U32, l2: U32, l3: U32, l4: U32, l5: U32, l6: U32, l7: U32}

def w0() -> W:
  W{0, 0, 0, 0, 0, 0, 0, 0}

def w_u(+x: U32) -> W:
  W{x, 0, 0, 0, 0, 0, 0, 0}

def w_b(b: Bool) -> W:
  w_u(b2u(b))

def w_lo(w: W) -> U32:
  match w:
    case W{a0, a1, a2, a3, a4, a5, a6, a7}:
      a0

def w_nz(w: W) -> Bool:
  match w:
    case W{a0, a1, a2, a3, a4, a5, a6, a7}:
      u_nz(U32.or(U32.or(U32.or(a0, a1), U32.or(a2, a3)), U32.or(U32.or(a4, a5), U32.or(a6, a7))))

def w_hi0(w: W) -> Bool:
  match w:
    case W{a0, a1, a2, a3, a4, a5, a6, a7}:
      Bool.not(u_nz(U32.or(U32.or(U32.or(a1, a2), U32.or(a3, a4)), U32.or(U32.or(a5, a6), a7))))

def w_eq(a: W, b: W) -> Bool:
  match a b:
    case W{a0, a1, a2, a3, a4, a5, a6, a7} W{b0, b1, b2, b3, b4, b5, b6, b7}:
      Bool.and(U32.is_eq(a0, b0), Bool.and(U32.is_eq(a1, b1), Bool.and(U32.is_eq(a2, b2), Bool.and(U32.is_eq(a3, b3), Bool.and(U32.is_eq(a4, b4), Bool.and(U32.is_eq(a5, b5), Bool.and(U32.is_eq(a6, b6), U32.is_eq(a7, b7))))))))

def u_lt2(+a: U32, +b: U32, lo: Bool) -> Bool:
  Bool.or(U32.is_lt(a, b), Bool.and(U32.is_eq(a, b), lo))

def w_lt(a: W, b: W) -> Bool:
  match a b:
    case W{+a0, +a1, +a2, +a3, +a4, +a5, +a6, +a7} W{+b0, +b1, +b2, +b3, +b4, +b5, +b6, +b7}:
      u_lt2(a7, b7, u_lt2(a6, b6, u_lt2(a5, b5, u_lt2(a4, b4, u_lt2(a3, b3, u_lt2(a2, b2, u_lt2(a1, b1, U32.is_lt(a0, b0))))))))

def w_le(+a: W, +b: W) -> Bool:
  Bool.not(w_lt(b, a))

def w_gt(+a: W, +b: W) -> Bool:
  w_lt(b, a)

def w_ge(+a: W, +b: W) -> Bool:
  Bool.not(w_lt(a, b))

def u_add(+a: U32, +b: U32) -> U32:
  ite(U32, U32.is_eq(b, 0), a, ite(U32, U32.is_eq(a, 0), b, (a + b : U32)))

def u_addc(+t: U32, c: Bool) -> U32:
  ite(U32, c, U32.inc(t), t)

def u_sub(+a: U32, +b: U32) -> U32:
  ite(U32, U32.is_eq(b, 0), a, (a - b : U32))

def u_subc(+t: U32, c: Bool) -> U32:
  ite(U32, c, (t - 1 : U32), t)

def cy(+a: U32, +b: U32, +c: U32) -> U32:
  b2u(Bool.or(U32.is_lt((a + b : U32), a), U32.is_lt(((a + b : U32) + c : U32), (a + b : U32))))

@W_ADD@
@W_ADD_OK@
def bw(+a: U32, +b: U32, +c: U32) -> U32:
  b2u(Bool.or(U32.is_lt(a, b), U32.is_lt((a - b : U32), c)))

@W_SUB@
def w_sub_ok(+a: W, +b: W) -> Bool:
  w_ge(a, b)

def w_not(a: W) -> W:
  match a:
    case W{a0, a1, a2, a3, a4, a5, a6, a7}:
      W{U32.not(a0), U32.not(a1), U32.not(a2), U32.not(a3), U32.not(a4), U32.not(a5), U32.not(a6), U32.not(a7)}

def w_and(a: W, b: W) -> W:
  match a b:
    case W{a0, a1, a2, a3, a4, a5, a6, a7} W{b0, b1, b2, b3, b4, b5, b6, b7}:
      W{U32.and(a0, b0), U32.and(a1, b1), U32.and(a2, b2), U32.and(a3, b3), U32.and(a4, b4), U32.and(a5, b5), U32.and(a6, b6), U32.and(a7, b7)}

def w_or(a: W, b: W) -> W:
  match a b:
    case W{a0, a1, a2, a3, a4, a5, a6, a7} W{b0, b1, b2, b3, b4, b5, b6, b7}:
      W{U32.or(a0, b0), U32.or(a1, b1), U32.or(a2, b2), U32.or(a3, b3), U32.or(a4, b4), U32.or(a5, b5), U32.or(a6, b6), U32.or(a7, b7)}

def w_xor(a: W, b: W) -> W:
  match a b:
    case W{a0, a1, a2, a3, a4, a5, a6, a7} W{b0, b1, b2, b3, b4, b5, b6, b7}:
      W{U32.xor(a0, b0), U32.xor(a1, b1), U32.xor(a2, b2), U32.xor(a3, b3), U32.xor(a4, b4), U32.xor(a5, b5), U32.xor(a6, b6), U32.xor(a7, b7)}

def w_limbs(w: W) -> List<&2, U32>:
  match w:
    case W{a0, a1, a2, a3, a4, a5, a6, a7}:
      [a0, a1, a2, a3, a4, a5, a6, a7]

def l_at(xs: List<&2, U32>, n: Nat) -> U32:
  match xs n:
    case Nil{} _:
      0
    case Con{h, t} 0n:
      h
    case Con{h, t} 1n+p:
      l_at(t, p)

def w_of_limbs(+xs: List<&2, U32>) -> W:
  W{l_at(xs, 0n), l_at(xs, 1n), l_at(xs, 2n), l_at(xs, 3n), l_at(xs, 4n), l_at(xs, 5n), l_at(xs, 6n), l_at(xs, 7n)}

def mul_hi(+a: U32, +b: U32) -> U32:
  +al = U32.and(a, 65535)
  +ah = U32.shrn(a, 16n)
  +bl = U32.and(b, 65535)
  +bh = U32.shrn(b, 16n)
  +ll = (al * bl : U32)
  +lh = (al * bh : U32)
  +hl = (ah * bl : U32)
  +hh = (ah * bh : U32)
  +mid = (lh + hl : U32)
  +cmid = b2u(U32.is_lt(mid, lh))
  +lo = (ll + U32.shln(mid, 16n) : U32)
  +clo = b2u(U32.is_lt(lo, ll))
  (((hh + U32.shrn(mid, 16n) : U32) + U32.shln(cmid, 16n) : U32) + clo : U32)

def l_mul1(xs: List<&2, U32>, +b: U32, +c: U32) -> List<&2, U32>:
  match xs:
    case Nil{}:
      [c]
    case Con{+x, t}:
      +lo = (x * b : U32)
      +s = (lo + c : U32)
      Con{s, l_mul1(t, b, (mul_hi(x, b) + b2u(U32.is_lt(s, lo)) : U32))}

def l_add(xs: List<&2, U32>, ys: List<&2, U32>, +c: U32) -> List<&2, U32>:
  match xs ys:
    case Nil{} Nil{}:
      ite(List<&2, U32>, U32.is_eq(c, 0), Nil{}, [c])
    case Nil{} Con{+y, yt}:
      Con{(y + c : U32), l_add(Nil{}, yt, cy(y, 0, c))}
    case Con{+x, xt} Nil{}:
      Con{(x + c : U32), l_add(xt, Nil{}, cy(x, 0, c))}
    case Con{+x, xt} Con{+y, yt}:
      Con{((x + y : U32) + c : U32), l_add(xt, yt, cy(x, y, c))}

def l_mulfull(+xs: List<&2, U32>, ys: List<&2, U32>, +sh: List<&2, U32>) -> List<&2, U32>:
  match ys:
    case Nil{}:
      Nil{}
    case Con{+y, yt}:
      l_add(List.append(&2, U32, sh, l_mul1(xs, y, 0)), l_mulfull(xs, yt, Con{0, sh}), 0)

def l_hi_zero(xs: List<&2, U32>, n: Nat) -> Bool:
  match xs n:
    case Nil{} _:
      True{}
    case Con{h, t} 0n:
      Bool.and(Bool.not(u_nz(h)), l_hi_zero(t, 0n))
    case Con{h, t} 1n+p:
      l_hi_zero(t, p)

def w_mul(+a: W, +b: W) -> W:
  w_of_limbs(l_mulfull(w_limbs(a), w_limbs(b), Nil{}))

def w_mul_ok(+a: W, +b: W) -> Bool:
  l_hi_zero(l_mulfull(w_limbs(a), w_limbs(b), Nil{}), 8n)

def w_shl1(a: W) -> W:
  match a:
    case W{+a0, +a1, +a2, +a3, +a4, +a5, +a6, +a7}:
      W{U32.shln(a0, 1n), U32.or(U32.shln(a1, 1n), U32.shrn(a0, 31n)), U32.or(U32.shln(a2, 1n), U32.shrn(a1, 31n)), U32.or(U32.shln(a3, 1n), U32.shrn(a2, 31n)), U32.or(U32.shln(a4, 1n), U32.shrn(a3, 31n)), U32.or(U32.shln(a5, 1n), U32.shrn(a4, 31n)), U32.or(U32.shln(a6, 1n), U32.shrn(a5, 31n)), U32.or(U32.shln(a7, 1n), U32.shrn(a6, 31n))}

def w_top(a: W) -> U32:
  match a:
    case W{a0, a1, a2, a3, a4, a5, a6, a7}:
      U32.shrn(a7, 31n)

def w_setlow(a: W, +b: U32) -> W:
  match a:
    case W{a0, a1, a2, a3, a4, a5, a6, a7}:
      W{U32.or(a0, b), a1, a2, a3, a4, a5, a6, a7}

type DM is Data:
  DM{q: W, r: W, a: W}

def w_dm_step(+d: W, m: DM) -> DM:
  match m:
    case DM{q, r, +a}:
      +r1 = w_setlow(w_shl1(r), w_top(a))
      +ge = w_ge(r1, d)
      DM{w_setlow(w_shl1(q), b2u(ge)), ite(W, ge, w_sub(r1, d), r1), w_shl1(a)}

def w_dm_go(n: Nat, +d: W, m: DM) -> DM:
  match n:
    case 0n:
      m
    case 1n+p:
      w_dm_go(p, d, w_dm_step(d, m))

def dm_q(m: DM) -> W:
  match m:
    case DM{q, r, a}:
      q

def dm_r(m: DM) -> W:
  match m:
    case DM{q, r, a}:
      r

def w_div(+a: W, +b: W) -> W:
  ite(W, w_nz(b), dm_q(w_dm_go(256n, b, DM{w0(), w0(), a})), w0())

def w_mod(+a: W, +b: W) -> W:
  ite(W, w_nz(b), dm_r(w_dm_go(256n, b, DM{w0(), w0(), a})), w0())

def mul_c(+x: U32, +c: U32, +k: U32) -> U32:
  ((x * c : U32) + k : U32)

def mul_k(+x: U32, +c: U32, +k: U32) -> U32:
  (mul_hi(x, c) + b2u(U32.is_lt(((x * c : U32) + k : U32), (x * c : U32))) : U32)

def w_mul_small(a: W, +c: U32) -> W:
  match a:
    case W{+a0, +a1, +a2, +a3, +a4, +a5, +a6, +a7}:
      +k1 = mul_k(a0, c, 0)
      +k2 = mul_k(a1, c, k1)
      +k3 = mul_k(a2, c, k2)
      +k4 = mul_k(a3, c, k3)
      +k5 = mul_k(a4, c, k4)
      +k6 = mul_k(a5, c, k5)
      +k7 = mul_k(a6, c, k6)
      W{mul_c(a0, c, 0), mul_c(a1, c, k1), mul_c(a2, c, k2), mul_c(a3, c, k3), mul_c(a4, c, k4), mul_c(a5, c, k5), mul_c(a6, c, k6), mul_c(a7, c, k7)}

def dq16(+r: U32, +x: U32, +d: U32) -> U32:
  +c1 = U32.or(U32.shln(r, 16n), U32.shrn(x, 16n))
  +c2 = U32.or(U32.shln(U32.mod(c1, d), 16n), U32.and(x, 65535))
  U32.or(U32.shln(U32.div(c1, d), 16n), U32.div(c2, d))

def dr16(+r: U32, +x: U32, +d: U32) -> U32:
  +c1 = U32.or(U32.shln(r, 16n), U32.shrn(x, 16n))
  U32.mod(U32.or(U32.shln(U32.mod(c1, d), 16n), U32.and(x, 65535)), d)

def w_div_small(a: W, +d: U32) -> W:
  match a:
    case W{+a0, +a1, +a2, +a3, +a4, +a5, +a6, +a7}:
      +r7 = dr16(0, a7, d)
      +r6 = dr16(r7, a6, d)
      +r5 = dr16(r6, a5, d)
      +r4 = dr16(r5, a4, d)
      +r3 = dr16(r4, a3, d)
      +r2 = dr16(r3, a2, d)
      +r1 = dr16(r2, a1, d)
      W{dq16(r1, a0, d), dq16(r2, a1, d), dq16(r3, a2, d), dq16(r4, a3, d), dq16(r5, a4, d), dq16(r6, a5, d), dq16(r7, a6, d), dq16(0, a7, d)}

def w_mod_small(a: W, +d: U32) -> W:
  match a:
    case W{+a0, +a1, +a2, +a3, +a4, +a5, +a6, +a7}:
      w_u(dr16(dr16(dr16(dr16(dr16(dr16(dr16(dr16(0, a7, d), a6, d), a5, d), a4, d), a3, d), a2, d), a1, d), a0, d))

def b_len(xs: List<&2, U32>) -> U32:
  match xs:
    case Nil{}:
      0
    case Con{h, t}:
      U32.inc(b_len(t))

def b_at(xs: List<&2, U32>, n: Nat) -> U32:
  match xs n:
    case Nil{} _:
      0
    case Con{h, t} 0n:
      h
    case Con{h, t} 1n+p:
      b_at(t, p)

def b_dropn(n: Nat, xs: List<&2, U32>) -> List<&2, U32>:
  match n:
    case 0n:
      xs
    case 1n+p:
      match xs:
        case Nil{}:
          Nil{}
        case Con{h, t}:
          b_dropn(p, t)

def b_drop(xs: List<&2, U32>, n: Nat) -> List<&2, U32>:
  b_dropn(n, xs)

def b_take(n: Nat, xs: List<&2, U32>, +pad: U32) -> List<&2, U32>:
  match n xs:
    case 0n _:
      Nil{}
    case 1n+p Nil{}:
      Con{pad, b_take(p, Nil{}, pad)}
    case 1n+p Con{h, t}:
      Con{h, b_take(p, t, pad)}

@U8@
@U_BE4W@
def u_be4(xs: List<&2, U32>) -> U32:
  match xs:
    case Nil{}:
      0
    case Con{x0, r0}:
      match r0:
        case Nil{}:
          u_be4w(x0, 0, 0, 0)
        case Con{x1, r1}:
          match r1:
            case Nil{}:
              u_be4w(x0, x1, 0, 0)
            case Con{x2, r2}:
              match r2:
                case Nil{}:
                  u_be4w(x0, x1, x2, 0)
                case Con{x3, r3}:
                  u_be4w(x0, x1, x2, x3)

def w_of_b32(+xs: List<&2, U32>) -> W:
  W{u_be4(b_drop(xs, 28n)), u_be4(b_drop(xs, 24n)), u_be4(b_drop(xs, 20n)), u_be4(b_drop(xs, 16n)), u_be4(b_drop(xs, 12n)), u_be4(b_drop(xs, 8n)), u_be4(b_drop(xs, 4n)), u_be4(xs)}

def b_word(xs: List<&2, U32>, n: Nat) -> W:
  w_of_b32(b_take(32n, b_drop(xs, n), 0))

@U_B4@
def b_of_w(w: W) -> List<&2, U32>:
  match w:
    case W{a0, a1, a2, a3, a4, a5, a6, a7}:
      List.append(&2, U32, u_b4(a7), List.append(&2, U32, u_b4(a6), List.append(&2, U32, u_b4(a5), List.append(&2, U32, u_b4(a4), List.append(&2, U32, u_b4(a3), List.append(&2, U32, u_b4(a2), List.append(&2, U32, u_b4(a1), u_b4(a0))))))))

def b_of_u(x: U32) -> List<&2, U32>:
  List.append(&2, U32, [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], u_b4(x))

def b_eq(xs: List<&2, U32>, ys: List<&2, U32>) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      True{}
    case Nil{} Con{h, t}:
      False{}
    case Con{h, t} Nil{}:
      False{}
    case Con{a, s} Con{b, u}:
      Bool.and(U32.is_eq(a, b), b_eq(s, u))

def n_of_w(+w: W) -> Nat:
  U32.to_nat(w_lo(w))

def m_ov(bs: List<&2, U32>, mem: List<&2, U32>) -> List<&2, U32>:
  match bs:
    case Nil{}:
      mem
    case Con{b, r}:
      match mem:
        case Nil{}:
          Con{b, m_ov(r, Nil{})}
        case Con{h, t}:
          Con{b, m_ov(r, t)}

def m_over(mem: List<&2, U32>, bs: List<&2, U32>) -> List<&2, U32>:
  m_ov(bs, mem)

def m_put(off: Nat, mem: List<&2, U32>, bs: List<&2, U32>) -> List<&2, U32>:
  match off mem:
    case 0n Nil{}:
      m_over(Nil{}, bs)
    case 0n Con{h, t}:
      m_over(Con{h, t}, bs)
    case 1n+p Nil{}:
      Con{57005, m_put(p, Nil{}, bs)}
    case 1n+p Con{h, t}:
      Con{h, m_put(p, t, bs)}

def m_havoc(mem: List<&2, U32>) -> List<&2, U32>:
  match mem:
    case Nil{}:
      Nil{}
    case Con{h, t}:
      Con{57005, m_havoc(t)}

def m_slice(mem: List<&2, U32>, +off: W, +n: W) -> List<&2, U32>:
  b_take(n_of_w(n), b_drop(mem, n_of_w(off)), 57005)

type KW is Data:
  KW{k: W, v: W}

def kw_get(xs: List<&2, KW>, +k: W) -> W:
  match xs:
    case Nil{}:
      w0()
    case Con{h, t}:
      match h:
        case KW{hk, hv}:
          ite(W, w_eq(hk, k), hv, kw_get(t, k))

def kw_put(xs: List<&2, KW>, +k: W, +v: W, done: Bool) -> List<&2, KW>:
  match xs:
    case Nil{}:
      ite(List<&2, KW>, done, Nil{}, [KW{k, v}])
    case Con{h, t}:
      match h:
        case KW{+hk, hv}:
          +eq = w_eq(hk, k)
          Con{KW{hk, ite(W, eq, v, hv)}, kw_put(t, k, v, Bool.or(done, eq))}

def kw_set(xs: List<&2, KW>, +k: W, +v: W) -> List<&2, KW>:
  kw_put(xs, k, v, False{})

type HSt is Data:
  HSt{sl: List<&2, KW>}

def sload(s: HSt, +k: W) -> W:
  match s:
    case HSt{sl}:
      kw_get(sl, k)

def sstore(s: HSt, +k: W, +v: W) -> HSt:
  match s:
    case HSt{sl}:
      HSt{kw_set(sl, k, v)}

type HKB is Data:
  HKB{b: List<&2, U32>, v: W}

def b_rev(xs: List<&2, U32>, acc: List<&2, U32>) -> List<&2, U32>:
  match xs:
    case Nil{}:
      acc
    case Con{h, t}:
      b_rev(t, Con{h, acc})

def h_revs(xs: List<&2, HKB>) -> List<&2, HKB>:
  match xs:
    case Nil{}:
      Nil{}
    case Con{h, t}:
      match h:
        case HKB{hb, hv}:
          Con{HKB{b_rev(hb, Nil{}), hv}, h_revs(t)}

def h_cons(c: Bool, xt: List<&2, U32>, cv: W, r: List<&2, HKB>) -> List<&2, HKB>:
  match c:
    case True{}:
      Con{HKB{xt, cv}, r}
    case False{}:
      r

def h_one(+b: U32, cb: List<&2, U32>, cv: W, r: List<&2, HKB>) -> List<&2, HKB>:
  match cb:
    case Nil{}:
      r
    case Con{x, xt}:
      h_cons(U32.is_eq(x, b), xt, cv, r)

def h_step(+b: U32, cs: List<&2, HKB>) -> List<&2, HKB>:
  match cs:
    case Nil{}:
      Nil{}
    case Con{c, rest}:
      match c:
        case HKB{cb, cv}:
          h_one(b, cb, cv, h_step(b, rest))

def h_end1(cb: List<&2, U32>, cv: W, r: W) -> W:
  match cb:
    case Nil{}:
      cv
    case Con{x, xt}:
      r

def h_ends(cs: List<&2, HKB>) -> W:
  match cs:
    case Nil{}:
      w0()
    case Con{c, rest}:
      match c:
        case HKB{cb, cv}:
          h_end1(cb, cv, h_ends(rest))

def h_filt(k: List<&2, U32>, cs: List<&2, HKB>) -> W:
  match k:
    case Nil{}:
      h_ends(cs)
    case Con{b, t}:
      h_filt(t, h_step(b, cs))

# the value of the first entry whose key is k (0 when none): the table's entries filtered by k's bytes, the last byte
# first (keys share long prefixes: a mapping key is a word, then the slot), each byte bound once and each entry moved,
# never copied (A30: no reusable binder of the key or of the table)
def h_get(xs: List<&2, HKB>, k: List<&2, U32>) -> W:
  h_filt(b_rev(k, Nil{}), h_revs(xs))

type HCall is Data:
  HCall{to: W, d: List<&2, U32>, ok: Bool, ret: List<&2, U32>}

type HAns is Data:
  HAns{f: Bool, ok: Bool, ret: List<&2, U32>}

def c_find(xs: List<&2, HCall>, +to: W, +bt: Bool, +d: List<&2, U32>) -> HAns:
  match xs:
    case Nil{}:
      HAns{False{}, False{}, Nil{}}
    case Con{h, t}:
      match h:
        case HCall{cto, cd, cok, cret}:
          ite(HAns, Bool.and(Bool.or(Bool.not(bt), w_eq(cto, to)), b_eq(cd, d)), HAns{True{}, cok, cret}, c_find(t, to, bt, d))

def a_ok(a: HAns) -> Bool:
  match a:
    case HAns{f, ok, ret}:
      Bool.and(f, ok)

def a_ret(a: HAns) -> List<&2, U32>:
  match a:
    case HAns{f, ok, ret}:
      ret

type HLog is Data:
  HLog{t: List<&2, W>, d: List<&2, U32>}

type HOut is Data:
  HOut{c: U32, rv: List<&2, U32>, po: HSt, lg: List<&2, HLog>, tw: List<&2, W>}

def o_code(o: HOut) -> U32:
  match o:
    case HOut{c, rv, po, lg, tw}:
      c

def o_post(o: HOut) -> HSt:
  match o:
    case HOut{c, rv, po, lg, tw}:
      po

def o_logs(o: HOut) -> List<&2, HLog>:
  match o:
    case HOut{c, rv, po, lg, tw}:
      lg

def w_nth(xs: List<&2, W>, n: Nat) -> W:
  match xs n:
    case Nil{} _:
      w0()
    case Con{h, t} 0n:
      h
    case Con{h, t} 1n+p:
      w_nth(t, p)

def w_len(xs: List<&2, W>) -> U32:
  match xs:
    case Nil{}:
      0
    case Con{h, t}:
      U32.inc(w_len(t))

type KB is Data:
  KB{k: W, b: List<&2, U32>}

def kb_get(xs: List<&2, KB>, +k: W) -> List<&2, U32>:
  match xs:
    case Nil{}:
      Nil{}
    case Con{h, t}:
      match h:
        case KB{hk, hb}:
          ite(List<&2, U32>, w_eq(hk, k), hb, kb_get(t, k))
'''

PRELUDE = (_PRELUDE.replace("@W_ADD@\n", _w_add(False) + "\n").replace("@W_ADD_OK@\n", _w_add(True) + "\n")
           .replace("@W_SUB@\n", _w_sub() + "\n").replace("@U8@\n", _u8() + "\n")
           .replace("@U_BE4W@\n", _u_be4w() + "\n").replace("@U_B4@", _u_b4()))
