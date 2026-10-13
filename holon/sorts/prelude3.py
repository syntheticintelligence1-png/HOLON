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
"""
from __future__ import annotations

SENTINEL = 57005
FUEL = 4097          # loop iterations a step may run (holon.extracted_eval.MAX_ITERATIONS + 1)

PRELUDE = '''\
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
      Bool.not(u_nz(U32.or(U32.or(U32.or(U32.xor(a0, b0), U32.xor(a1, b1)), U32.or(U32.xor(a2, b2), U32.xor(a3, b3))), U32.or(U32.or(U32.xor(a4, b4), U32.xor(a5, b5)), U32.or(U32.xor(a6, b6), U32.xor(a7, b7))))))

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

def cy(+a: U32, +b: U32, +c: U32) -> U32:
  b2u(Bool.or(U32.is_lt((a + b : U32), a), U32.is_lt(((a + b : U32) + c : U32), (a + b : U32))))

def w_add(a: W, b: W) -> W:
  match a b:
    case W{+a0, +a1, +a2, +a3, +a4, +a5, +a6, +a7} W{+b0, +b1, +b2, +b3, +b4, +b5, +b6, +b7}:
      +c1 = cy(a0, b0, 0)
      +c2 = cy(a1, b1, c1)
      +c3 = cy(a2, b2, c2)
      +c4 = cy(a3, b3, c3)
      +c5 = cy(a4, b4, c4)
      +c6 = cy(a5, b5, c5)
      +c7 = cy(a6, b6, c6)
      W{(a0 + b0 : U32), ((a1 + b1 : U32) + c1 : U32), ((a2 + b2 : U32) + c2 : U32), ((a3 + b3 : U32) + c3 : U32), ((a4 + b4 : U32) + c4 : U32), ((a5 + b5 : U32) + c5 : U32), ((a6 + b6 : U32) + c6 : U32), ((a7 + b7 : U32) + c7 : U32)}

def w_add_ok(a: W, b: W) -> Bool:
  match a b:
    case W{+a0, +a1, +a2, +a3, +a4, +a5, +a6, +a7} W{+b0, +b1, +b2, +b3, +b4, +b5, +b6, +b7}:
      +c1 = cy(a0, b0, 0)
      +c2 = cy(a1, b1, c1)
      +c3 = cy(a2, b2, c2)
      +c4 = cy(a3, b3, c3)
      +c5 = cy(a4, b4, c4)
      +c6 = cy(a5, b5, c5)
      +c7 = cy(a6, b6, c6)
      U32.is_eq(cy(a7, b7, c7), 0)

def bw(+a: U32, +b: U32, +c: U32) -> U32:
  b2u(Bool.or(U32.is_lt(a, b), U32.is_lt((a - b : U32), c)))

def w_sub(a: W, b: W) -> W:
  match a b:
    case W{+a0, +a1, +a2, +a3, +a4, +a5, +a6, +a7} W{+b0, +b1, +b2, +b3, +b4, +b5, +b6, +b7}:
      +c1 = bw(a0, b0, 0)
      +c2 = bw(a1, b1, c1)
      +c3 = bw(a2, b2, c2)
      +c4 = bw(a3, b3, c3)
      +c5 = bw(a4, b4, c4)
      +c6 = bw(a5, b5, c5)
      +c7 = bw(a6, b6, c6)
      W{(a0 - b0 : U32), ((a1 - b1 : U32) - c1 : U32), ((a2 - b2 : U32) - c2 : U32), ((a3 - b3 : U32) - c3 : U32), ((a4 - b4 : U32) - c4 : U32), ((a5 - b5 : U32) - c5 : U32), ((a6 - b6 : U32) - c6 : U32), ((a7 - b7 : U32) - c7 : U32)}

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
      (b_len(t) + 1 : U32)

def b_at(xs: List<&2, U32>, n: Nat) -> U32:
  match xs n:
    case Nil{} _:
      0
    case Con{h, t} 0n:
      h
    case Con{h, t} 1n+p:
      b_at(t, p)

def b_drop(xs: List<&2, U32>, n: Nat) -> List<&2, U32>:
  match xs n:
    case Nil{} _:
      Nil{}
    case Con{h, t} 0n:
      Con{h, t}
    case Con{h, t} 1n+p:
      b_drop(t, p)

def b_take(n: Nat, xs: List<&2, U32>, +pad: U32) -> List<&2, U32>:
  match n xs:
    case 0n _:
      Nil{}
    case 1n+p Nil{}:
      Con{pad, b_take(p, Nil{}, pad)}
    case 1n+p Con{h, t}:
      Con{h, b_take(p, t, pad)}

def u_be4(+xs: List<&2, U32>) -> U32:
  U32.or(U32.or(U32.shln(b_at(xs, 0n), 24n), U32.shln(b_at(xs, 1n), 16n)), U32.or(U32.shln(b_at(xs, 2n), 8n), b_at(xs, 3n)))

def w_of_b32(+xs: List<&2, U32>) -> W:
  W{u_be4(b_drop(xs, 28n)), u_be4(b_drop(xs, 24n)), u_be4(b_drop(xs, 20n)), u_be4(b_drop(xs, 16n)), u_be4(b_drop(xs, 12n)), u_be4(b_drop(xs, 8n)), u_be4(b_drop(xs, 4n)), u_be4(xs)}

def b_word(+xs: List<&2, U32>, n: Nat) -> W:
  w_of_b32(b_take(32n, b_drop(xs, n), 0))

def u_b4(+x: U32) -> List<&2, U32>:
  [U32.and(U32.shrn(x, 24n), 255), U32.and(U32.shrn(x, 16n), 255), U32.and(U32.shrn(x, 8n), 255), U32.and(x, 255)]

def b_of_w(w: W) -> List<&2, U32>:
  match w:
    case W{a0, a1, a2, a3, a4, a5, a6, a7}:
      List.append(&2, U32, u_b4(a7), List.append(&2, U32, u_b4(a6), List.append(&2, U32, u_b4(a5), List.append(&2, U32, u_b4(a4), List.append(&2, U32, u_b4(a3), List.append(&2, U32, u_b4(a2), List.append(&2, U32, u_b4(a1), u_b4(a0))))))))

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

def m_over(mem: List<&2, U32>, bs: List<&2, U32>) -> List<&2, U32>:
  match mem bs:
    case Nil{} Nil{}:
      Nil{}
    case Con{h, t} Nil{}:
      Con{h, t}
    case Nil{} Con{b, r}:
      Con{b, m_over(Nil{}, r)}
    case Con{h, t} Con{b, r}:
      Con{b, m_over(t, r)}

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

def m_slice(+mem: List<&2, U32>, +off: W, +n: W) -> List<&2, U32>:
  b_take(n_of_w(n), b_drop(mem, n_of_w(off)), 57005)

type KW is Data:
  KW{k: W, v: W}

def kw_get(+xs: List<&2, KW>, +k: W) -> W:
  match xs:
    case Nil{}:
      w0()
    case Con{+h, +t}:
      match h:
        case KW{+hk, +hv}:
          ite(W, w_eq(hk, k), hv, kw_get(t, k))

def kw_set(+xs: List<&2, KW>, +k: W, +v: W) -> List<&2, KW>:
  match xs:
    case Nil{}:
      [KW{k, v}]
    case Con{+h, +t}:
      match h:
        case KW{+hk, +hv}:
          ite(List<&2, KW>, w_eq(hk, k), Con{KW{k, v}, t}, Con{KW{hk, hv}, kw_set(t, k, v)})

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

def h_get(+xs: List<&2, HKB>, +k: List<&2, U32>) -> W:
  match xs:
    case Nil{}:
      w0()
    case Con{+h, +t}:
      match h:
        case HKB{+hb, +hv}:
          ite(W, b_eq(hb, k), hv, h_get(t, k))

type HCall is Data:
  HCall{to: W, d: List<&2, U32>, ok: Bool, ret: List<&2, U32>}

type HAns is Data:
  HAns{f: Bool, ok: Bool, ret: List<&2, U32>}

def c_find(+xs: List<&2, HCall>, +to: W, +bt: Bool, +d: List<&2, U32>) -> HAns:
  match xs:
    case Nil{}:
      HAns{False{}, False{}, Nil{}}
    case Con{+h, +t}:
      match h:
        case HCall{+cto, +cd, +cok, +cret}:
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
      (w_len(t) + 1 : U32)

type KB is Data:
  KB{k: W, b: List<&2, U32>}

def kb_get(+xs: List<&2, KB>, +k: W) -> List<&2, U32>:
  match xs:
    case Nil{}:
      Nil{}
    case Con{+h, +t}:
      match h:
        case KB{+hk, +hb}:
          ite(List<&2, U32>, w_eq(hk, k), hb, kb_get(t, k))
'''
