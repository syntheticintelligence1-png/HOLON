"""The core lemmas of the proof class residue_bound (BUILD_PLAN I33; tests_m3/test_o12_m3.py rule B6): the typed model's
word arithmetic read as natural numbers, proved (never assumed) in every residue_bound proof file, which states them
over Base (Nat, Bool, Cmp, Word, U32) and the typed model's prelude (W, u_add, u_addc, w_add, w_add_ok, ite: holon.sorts
.prelude3), imported as M; a model whose prelude differs makes the file fail to check.

  Nat         n_add_z, n_add_s, n_add_comm, n_add_assoc, n_dbl_add, n_cancel_l, n_succ_inj, n_succ_nz, rearrangements
  shifts      shn(n, x) = x 2^n, shn_add, b2n, cmul(c, pw) (a carry times a power of two kept opaque)
  Word        w_adc_nat: to_nat(adc(a, b, c)) + 2^n carry == to_nat(a) + to_nat(b) + c (wcarry: the carry out); adding
              zero; w_inc_adc: inc(a + b) == a + b + 1; w_cmp_nat: Word.cmp is Nat.cmp of the values; w_bound:
              to_nat(w) + 1 + to_nat(not w) == 2^n
  limbs       u_add_eq: the model's u_add is U32.add; u_s_limb: a limb's sum u_addc(u_add(x, y), k) is adc with the carry
              in; u_c_limb0, u_c_limb: its carry tests (U32.is_lt) are wcarry
  words       w_bridge: N(a + b) + carry 2^256 == N(a) + N(b); w_wrap: N(a + b) <= N(a) + N(b); wl_bound: N(w) + 1 +
              wcn(w) == 2^256; nw, okn: a sum below 2^256, or a checked one (w_add_ok), has no carry; ks_0, ks_i, ks_j,
              ks_s: a loop's key c0 + it starts at N(c0) and steps by one under the checked increment of the key;
              lt_irr, lt_succ, lt_up: Nat order

The power of two 2^32 is written shn(32n, 1n) at every use and passed to the generic lemmas as an opaque parameter: Bend's
Nat is unary, and the checker normalizes both sides of any equation it cannot match syntactically, so a comparison of two
different terms that contain a closed power of two would expand it. Nothing here names a target.
"""
from __future__ import annotations

import re

NAT = r'''
def n_pred(n: Nat) -> Nat:
  match n:
    case 0n:
      0n
    case 1n+p:
      p

def n_disc(n: Nat) -> Type:
  match n:
    case 0n:
      Empty
    case 1n+p:
      Unit

def n_succ_nz(+a: Nat, e: {1n+a == 0n : Nat}) -> Empty:
  (%e : n_disc(_)
  Unit{})

def n_succ_inj(+a: Nat, +b: Nat, e: {1n+a == 1n+b : Nat}) -> {a == b : Nat}:
  Equal.cong(Nat, Nat, n_pred, 1n+a, 1n+b, e)

def n_add_z(+a: Nat) -> {Nat.add(a, 0n) == a : Nat}:
  match a:
    case 0n:
      {==}
    case 1n+p:
      Equal.cong(Nat, Nat, x => 1n+x, Nat.add(p, 0n), p, n_add_z(p))

def n_add_s(+a: Nat, +b: Nat) -> {Nat.add(a, 1n+b) == 1n+Nat.add(a, b) : Nat}:
  match a:
    case 0n:
      {==}
    case 1n+p:
      Equal.cong(Nat, Nat, x => 1n+x, Nat.add(p, 1n+b), 1n+Nat.add(p, b), n_add_s(p, b))

def n_add_comm(+a: Nat, +b: Nat) -> {Nat.add(a, b) == Nat.add(b, a) : Nat}:
  match a:
    case 0n:
      Equal.sym(Nat, Nat.add(b, 0n), b, n_add_z(b))
    case 1n+p:
      Equal.trans(Nat, 1n+Nat.add(p, b), 1n+Nat.add(b, p), Nat.add(b, 1n+p),
        Equal.cong(Nat, Nat, x => 1n+x, Nat.add(p, b), Nat.add(b, p), n_add_comm(p, b)),
        Equal.sym(Nat, Nat.add(b, 1n+p), 1n+Nat.add(b, p), n_add_s(b, p)))

def n_add_assoc(+a: Nat, +b: Nat, +c: Nat) -> {Nat.add(Nat.add(a, b), c) == Nat.add(a, Nat.add(b, c)) : Nat}:
  match a:
    case 0n:
      {==}
    case 1n+p:
      Equal.cong(Nat, Nat, x => 1n+x, Nat.add(Nat.add(p, b), c), Nat.add(p, Nat.add(b, c)), n_add_assoc(p, b, c))

def n_dbl_add(+a: Nat, +b: Nat) -> {Nat.double(Nat.add(a, b)) == Nat.add(Nat.double(a), Nat.double(b)) : Nat}:
  match a:
    case 0n:
      {==}
    case 1n+p:
      Equal.cong(Nat, Nat, x => 2n+x, Nat.double(Nat.add(p, b)), Nat.add(Nat.double(p), Nat.double(b)), n_dbl_add(p, b))

# a + c == b + c gives a == b (cancellation on the left of add: c + a == c + b)
def n_cancel_l(+c: Nat, +a: Nat, +b: Nat, e: {Nat.add(c, a) == Nat.add(c, b) : Nat}) -> {a == b : Nat}:
  match c:
    case 0n:
      e
    case 1n+p:
      n_cancel_l(p, a, b, n_succ_inj(Nat.add(p, a), Nat.add(p, b), e))

# ---- rearrangements
def n_cong_l(+a: Nat, +b: Nat, +c: Nat, e: {a == b : Nat}) -> {Nat.add(a, c) == Nat.add(b, c) : Nat}:
  Equal.cong(Nat, Nat, x => Nat.add(x, c), a, b, e)

def n_cong_r(+c: Nat, +a: Nat, +b: Nat, e: {a == b : Nat}) -> {Nat.add(c, a) == Nat.add(c, b) : Nat}:
  Equal.cong(Nat, Nat, x => Nat.add(c, x), a, b, e)

# (a + b) + (c + d) == (a + c) + (b + d)
def n_swap_mid(+a: Nat, +b: Nat, +c: Nat, +d: Nat) -> {Nat.add(Nat.add(a, b), Nat.add(c, d)) == Nat.add(Nat.add(a, c), Nat.add(b, d)) : Nat}:
  Equal.trans(Nat, Nat.add(Nat.add(a, b), Nat.add(c, d)), Nat.add(a, Nat.add(b, Nat.add(c, d))), Nat.add(Nat.add(a, c), Nat.add(b, d)),
    n_add_assoc(a, b, Nat.add(c, d)),
    Equal.trans(Nat, Nat.add(a, Nat.add(b, Nat.add(c, d))), Nat.add(a, Nat.add(c, Nat.add(b, d))), Nat.add(Nat.add(a, c), Nat.add(b, d)),
      n_cong_r(a, Nat.add(b, Nat.add(c, d)), Nat.add(c, Nat.add(b, d)),
        Equal.trans(Nat, Nat.add(b, Nat.add(c, d)), Nat.add(Nat.add(b, c), d), Nat.add(c, Nat.add(b, d)),
          Equal.sym(Nat, Nat.add(Nat.add(b, c), d), Nat.add(b, Nat.add(c, d)), n_add_assoc(b, c, d)),
          Equal.trans(Nat, Nat.add(Nat.add(b, c), d), Nat.add(Nat.add(c, b), d), Nat.add(c, Nat.add(b, d)),
            n_cong_l(Nat.add(b, c), Nat.add(c, b), d, n_add_comm(b, c)),
            n_add_assoc(c, b, d)))),
      Equal.sym(Nat, Nat.add(Nat.add(a, c), Nat.add(b, d)), Nat.add(a, Nat.add(c, Nat.add(b, d))), n_add_assoc(a, c, Nat.add(b, d)))))

# ---- shifts and bits
def shn(n: Nat, x: Nat) -> Nat:
  match n:
    case 0n:
      x
    case 1n+p:
      Nat.double(shn(p, x))

def shn_add(+n: Nat, +a: Nat, +b: Nat) -> {shn(n, Nat.add(a, b)) == Nat.add(shn(n, a), shn(n, b)) : Nat}:
  match n:
    case 0n:
      {==}
    case 1n+p:
      Equal.trans(Nat, Nat.double(shn(p, Nat.add(a, b))), Nat.double(Nat.add(shn(p, a), shn(p, b))), Nat.add(Nat.double(shn(p, a)), Nat.double(shn(p, b))),
        Equal.cong(Nat, Nat, Nat.double, shn(p, Nat.add(a, b)), Nat.add(shn(p, a), shn(p, b)), shn_add(p, a, b)),
        n_dbl_add(shn(p, a), shn(p, b)))

def b2n(b: Bool) -> Nat:
  match b:
    case False{}:
      0n
    case True{}:
      1n

# the carry out of Bool.full_add (its second component)
def fa_carry(a: Bool, +b: Bool, +c: Bool) -> Bool:
  match a:
    case False{}:
      Bool.and(b, c)
    case True{}:
      Bool.or(b, c)

# the carry out of Word.adc(n, a, b, False{}, c)
def wcarry(n: Nat, a: Word(n), b: Word(n), c: Bool) -> Bool:
  match n:
    case 0n:
      c
    case 1n+p:
      match a b:
        case WCon{ah, at} WCon{bh, bt}:
          wcarry(p, at, bt, fa_carry(ah, bh, c))

# the full adder's step, in Nat: (s + 2 L) + 2 Cy == ((h + 2 A) + (g + 2 B)) + c, from L + Cy == (A + B) + k and s + 2 k == (h + g) + c
def n_fa_step(+sn: Nat, +kn: Nat, +hn: Nat, +gn: Nat, +cn: Nat, +l: Nat, +cy: Nat, +a: Nat, +b: Nat,
              ih: {Nat.add(l, cy) == Nat.add(Nat.add(a, b), kn) : Nat},
              fa: {Nat.add(sn, Nat.double(kn)) == Nat.add(Nat.add(hn, gn), cn) : Nat}) ->
              {Nat.add(Nat.add(sn, Nat.double(l)), Nat.double(cy)) == Nat.add(Nat.add(Nat.add(hn, Nat.double(a)), Nat.add(gn, Nat.double(b))), cn) : Nat}:
  +da = Nat.double(a)
  +db = Nat.double(b)
  +dk = Nat.double(kn)
  # left: (sn + 2l) + 2cy == sn + 2(l + cy) == sn + 2((a + b) + k) == sn + ((da + db) + dk) == (sn + dk) + (da + db)
  +l1 = Equal.trans(Nat, Nat.add(Nat.add(sn, Nat.double(l)), Nat.double(cy)), Nat.add(sn, Nat.add(Nat.double(l), Nat.double(cy))), Nat.add(sn, Nat.double(Nat.add(l, cy))),
    n_add_assoc(sn, Nat.double(l), Nat.double(cy)),
    n_cong_r(sn, Nat.add(Nat.double(l), Nat.double(cy)), Nat.double(Nat.add(l, cy)), Equal.sym(Nat, Nat.double(Nat.add(l, cy)), Nat.add(Nat.double(l), Nat.double(cy)), n_dbl_add(l, cy))))
  +l2 = n_cong_r(sn, Nat.double(Nat.add(l, cy)), Nat.add(Nat.add(da, db), dk),
    Equal.trans(Nat, Nat.double(Nat.add(l, cy)), Nat.double(Nat.add(Nat.add(a, b), kn)), Nat.add(Nat.add(da, db), dk),
      Equal.cong(Nat, Nat, Nat.double, Nat.add(l, cy), Nat.add(Nat.add(a, b), kn), ih),
      Equal.trans(Nat, Nat.double(Nat.add(Nat.add(a, b), kn)), Nat.add(Nat.double(Nat.add(a, b)), dk), Nat.add(Nat.add(da, db), dk),
        n_dbl_add(Nat.add(a, b), kn),
        n_cong_l(Nat.double(Nat.add(a, b)), Nat.add(da, db), dk, n_dbl_add(a, b)))))
  # sn + ((da + db) + dk) == sn + (dk + (da + db)) == (sn + dk) + (da + db)
  +l3 = Equal.trans(Nat, Nat.add(sn, Nat.add(Nat.add(da, db), dk)), Nat.add(sn, Nat.add(dk, Nat.add(da, db))), Nat.add(Nat.add(sn, dk), Nat.add(da, db)),
    n_cong_r(sn, Nat.add(Nat.add(da, db), dk), Nat.add(dk, Nat.add(da, db)), n_add_comm(Nat.add(da, db), dk)),
    Equal.sym(Nat, Nat.add(Nat.add(sn, dk), Nat.add(da, db)), Nat.add(sn, Nat.add(dk, Nat.add(da, db))), n_add_assoc(sn, dk, Nat.add(da, db))))
  +l4 = n_cong_l(Nat.add(sn, dk), Nat.add(Nat.add(hn, gn), cn), Nat.add(da, db), fa)
  # right: ((hn + da) + (gn + db)) + cn == ((hn + gn) + (da + db)) + cn == ((hn + gn) + cn) + (da + db)
  +r1 = n_cong_l(Nat.add(Nat.add(hn, da), Nat.add(gn, db)), Nat.add(Nat.add(hn, gn), Nat.add(da, db)), cn, n_swap_mid(hn, da, gn, db))
  +r2 = Equal.trans(Nat, Nat.add(Nat.add(Nat.add(hn, gn), Nat.add(da, db)), cn), Nat.add(Nat.add(hn, gn), Nat.add(Nat.add(da, db), cn)), Nat.add(Nat.add(Nat.add(hn, gn), cn), Nat.add(da, db)),
    n_add_assoc(Nat.add(hn, gn), Nat.add(da, db), cn),
    Equal.trans(Nat, Nat.add(Nat.add(hn, gn), Nat.add(Nat.add(da, db), cn)), Nat.add(Nat.add(hn, gn), Nat.add(cn, Nat.add(da, db))), Nat.add(Nat.add(Nat.add(hn, gn), cn), Nat.add(da, db)),
      n_cong_r(Nat.add(hn, gn), Nat.add(Nat.add(da, db), cn), Nat.add(cn, Nat.add(da, db)), n_add_comm(Nat.add(da, db), cn)),
      Equal.sym(Nat, Nat.add(Nat.add(Nat.add(hn, gn), cn), Nat.add(da, db)), Nat.add(Nat.add(hn, gn), Nat.add(cn, Nat.add(da, db))), n_add_assoc(Nat.add(hn, gn), cn, Nat.add(da, db)))))
  +lhs = Equal.trans(Nat, Nat.add(Nat.add(sn, Nat.double(l)), Nat.double(cy)), Nat.add(sn, Nat.double(Nat.add(l, cy))), Nat.add(Nat.add(Nat.add(hn, gn), cn), Nat.add(da, db)),
    l1, Equal.trans(Nat, Nat.add(sn, Nat.double(Nat.add(l, cy))), Nat.add(sn, Nat.add(Nat.add(da, db), dk)), Nat.add(Nat.add(Nat.add(hn, gn), cn), Nat.add(da, db)),
      l2, Equal.trans(Nat, Nat.add(sn, Nat.add(Nat.add(da, db), dk)), Nat.add(Nat.add(sn, dk), Nat.add(da, db)), Nat.add(Nat.add(Nat.add(hn, gn), cn), Nat.add(da, db)), l3, l4)))
  +rhs = Equal.trans(Nat, Nat.add(Nat.add(Nat.add(hn, da), Nat.add(gn, db)), cn), Nat.add(Nat.add(Nat.add(hn, gn), Nat.add(da, db)), cn), Nat.add(Nat.add(Nat.add(hn, gn), cn), Nat.add(da, db)), r1, r2)
  Equal.trans(Nat, Nat.add(Nat.add(sn, Nat.double(l)), Nat.double(cy)), Nat.add(Nat.add(Nat.add(hn, gn), cn), Nat.add(da, db)), Nat.add(Nat.add(Nat.add(hn, da), Nat.add(gn, db)), cn),
    lhs, Equal.sym(Nat, Nat.add(Nat.add(Nat.add(hn, da), Nat.add(gn, db)), cn), Nat.add(Nat.add(Nat.add(hn, gn), cn), Nat.add(da, db)), rhs))

# the adder in Nat: to_nat(adc(a, b, c)) + 2^n carry == (to_nat(a) + to_nat(b)) + c (induction on the width)
def w_adc_nat(+n: Nat, +a: Word(n), +b: Word(n), +c: Bool) ->
    {Nat.add(Word.to_nat(n, Word.adc(n, a, b, False{}, c)), shn(n, b2n(wcarry(n, a, b, c)))) == Nat.add(Nat.add(Word.to_nat(n, a), Word.to_nat(n, b)), b2n(c)) : Nat}:
  match n:
    case 0n:
      {==}
    case 1n+p:
      match a b c:
        case WCon{False{}, +at} WCon{False{}, +bt} False{}:
          n_fa_step(0n, 0n, 0n, 0n, 0n, Word.to_nat(p, Word.adc(p, at, bt, False{}, False{})),
            shn(p, b2n(wcarry(p, at, bt, False{}))), Word.to_nat(p, at), Word.to_nat(p, bt), w_adc_nat(p, at, bt, False{}), {==})
        case WCon{False{}, +at} WCon{False{}, +bt} True{}:
          n_fa_step(1n, 0n, 0n, 0n, 1n, Word.to_nat(p, Word.adc(p, at, bt, False{}, False{})),
            shn(p, b2n(wcarry(p, at, bt, False{}))), Word.to_nat(p, at), Word.to_nat(p, bt), w_adc_nat(p, at, bt, False{}), {==})
        case WCon{False{}, +at} WCon{True{}, +bt} False{}:
          n_fa_step(1n, 0n, 0n, 1n, 0n, Word.to_nat(p, Word.adc(p, at, bt, False{}, False{})),
            shn(p, b2n(wcarry(p, at, bt, False{}))), Word.to_nat(p, at), Word.to_nat(p, bt), w_adc_nat(p, at, bt, False{}), {==})
        case WCon{False{}, +at} WCon{True{}, +bt} True{}:
          n_fa_step(0n, 1n, 0n, 1n, 1n, Word.to_nat(p, Word.adc(p, at, bt, False{}, True{})),
            shn(p, b2n(wcarry(p, at, bt, True{}))), Word.to_nat(p, at), Word.to_nat(p, bt), w_adc_nat(p, at, bt, True{}), {==})
        case WCon{True{}, +at} WCon{False{}, +bt} False{}:
          n_fa_step(1n, 0n, 1n, 0n, 0n, Word.to_nat(p, Word.adc(p, at, bt, False{}, False{})),
            shn(p, b2n(wcarry(p, at, bt, False{}))), Word.to_nat(p, at), Word.to_nat(p, bt), w_adc_nat(p, at, bt, False{}), {==})
        case WCon{True{}, +at} WCon{False{}, +bt} True{}:
          n_fa_step(0n, 1n, 1n, 0n, 1n, Word.to_nat(p, Word.adc(p, at, bt, False{}, True{})),
            shn(p, b2n(wcarry(p, at, bt, True{}))), Word.to_nat(p, at), Word.to_nat(p, bt), w_adc_nat(p, at, bt, True{}), {==})
        case WCon{True{}, +at} WCon{True{}, +bt} False{}:
          n_fa_step(0n, 1n, 1n, 1n, 0n, Word.to_nat(p, Word.adc(p, at, bt, False{}, True{})),
            shn(p, b2n(wcarry(p, at, bt, True{}))), Word.to_nat(p, at), Word.to_nat(p, bt), w_adc_nat(p, at, bt, True{}), {==})
        case WCon{True{}, +at} WCon{True{}, +bt} True{}:
          n_fa_step(1n, 1n, 1n, 1n, 1n, Word.to_nat(p, Word.adc(p, at, bt, False{}, True{})),
            shn(p, b2n(wcarry(p, at, bt, True{}))), Word.to_nat(p, at), Word.to_nat(p, bt), w_adc_nat(p, at, bt, True{}), {==})

# ---- adding zero, and the carry-in as an increment
def w_adc_zr(+n: Nat, +x: Word(n)) -> {Word.adc(n, x, Word.zero(n), False{}, False{}) == x : Word(n)}:
  match n:
    case 0n:
      match x:
        case WNil{}:
          {==}
    case 1n+p:
      match x:
        case WCon{False{}, +xt}:
          Equal.cong(Word(p), Word(1n+p), t => WCon{False{}, t}, Word.adc(p, xt, Word.zero(p), False{}, False{}), xt, w_adc_zr(p, xt))
        case WCon{True{}, +xt}:
          Equal.cong(Word(p), Word(1n+p), t => WCon{True{}, t}, Word.adc(p, xt, Word.zero(p), False{}, False{}), xt, w_adc_zr(p, xt))

def w_adc_zl(+n: Nat, +y: Word(n)) -> {Word.adc(n, Word.zero(n), y, False{}, False{}) == y : Word(n)}:
  match n:
    case 0n:
      match y:
        case WNil{}:
          {==}
    case 1n+p:
      match y:
        case WCon{False{}, +yt}:
          Equal.cong(Word(p), Word(1n+p), t => WCon{False{}, t}, Word.adc(p, Word.zero(p), yt, False{}, False{}), yt, w_adc_zl(p, yt))
        case WCon{True{}, +yt}:
          Equal.cong(Word(p), Word(1n+p), t => WCon{True{}, t}, Word.adc(p, Word.zero(p), yt, False{}, False{}), yt, w_adc_zl(p, yt))

def w_inc_adc(+n: Nat, +x: Word(n), +y: Word(n)) -> {Word.inc(n, Word.adc(n, x, y, False{}, False{})) == Word.adc(n, x, y, False{}, True{}) : Word(n)}:
  match n:
    case 0n:
      {==}
    case 1n+p:
      match x y:
        case WCon{False{}, +xt} WCon{False{}, +yt}:
          {==}
        case WCon{False{}, +xt} WCon{True{}, +yt}:
          Equal.cong(Word(p), Word(1n+p), t => WCon{False{}, t}, Word.inc(p, Word.adc(p, xt, yt, False{}, False{})), Word.adc(p, xt, yt, False{}, True{}), w_inc_adc(p, xt, yt))
        case WCon{True{}, +xt} WCon{False{}, +yt}:
          Equal.cong(Word(p), Word(1n+p), t => WCon{False{}, t}, Word.inc(p, Word.adc(p, xt, yt, False{}, False{})), Word.adc(p, xt, yt, False{}, True{}), w_inc_adc(p, xt, yt))
        case WCon{True{}, +xt} WCon{True{}, +yt}:
          {==}

# ---- the order of words is the order of their values
def fin_ff(+t: Cmp) -> {Word.cmp.fin(False{}, False{}, t) == t : Cmp}:
  match t:
    case LT{}:
      {==}
    case EQ{}:
      {==}
    case GT{}:
      {==}

def fin_tt(+t: Cmp) -> {Word.cmp.fin(True{}, True{}, t) == t : Cmp}:
  match t:
    case LT{}:
      {==}
    case EQ{}:
      {==}
    case GT{}:
      {==}

def nc_dd(+a: Nat, +b: Nat) -> {Nat.cmp(Nat.double(a), Nat.double(b)) == Nat.cmp(a, b) : Cmp}:
  match a b:
    case 0n 0n:
      {==}
    case 0n 1n+q:
      {==}
    case 1n+p 0n:
      {==}
    case 1n+p 1n+q:
      nc_dd(p, q)

def nc_d1d(+a: Nat, +b: Nat) -> {Nat.cmp(Nat.double(a), 1n+Nat.double(b)) == Word.cmp.fin(False{}, True{}, Nat.cmp(a, b)) : Cmp}:
  match a b:
    case 0n 0n:
      {==}
    case 0n 1n+q:
      {==}
    case 1n+p 0n:
      {==}
    case 1n+p 1n+q:
      nc_d1d(p, q)

def nc_1dd(+a: Nat, +b: Nat) -> {Nat.cmp(1n+Nat.double(a), Nat.double(b)) == Word.cmp.fin(True{}, False{}, Nat.cmp(a, b)) : Cmp}:
  match a b:
    case 0n 0n:
      {==}
    case 0n 1n+q:
      {==}
    case 1n+p 0n:
      {==}
    case 1n+p 1n+q:
      nc_1dd(p, q)

def w_cmp_nat(+n: Nat, +a: Word(n), +b: Word(n)) -> {Word.cmp(n, a, b) == Nat.cmp(Word.to_nat(n, a), Word.to_nat(n, b)) : Cmp}:
  match n:
    case 0n:
      {==}
    case 1n+p:
      match a b:
        case WCon{False{}, +at} WCon{False{}, +bt}:
          Equal.trans(Cmp, Word.cmp.fin(False{}, False{}, Word.cmp(p, at, bt)), Word.cmp.fin(False{}, False{}, Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt))), Nat.cmp(Nat.double(Word.to_nat(p, at)), Nat.double(Word.to_nat(p, bt))),
            Equal.cong(Cmp, Cmp, t => Word.cmp.fin(False{}, False{}, t), Word.cmp(p, at, bt), Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt)), w_cmp_nat(p, at, bt)),
            Equal.trans(Cmp, Word.cmp.fin(False{}, False{}, Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt))), Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt)), Nat.cmp(Nat.double(Word.to_nat(p, at)), Nat.double(Word.to_nat(p, bt))),
              fin_ff(Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt))),
              Equal.sym(Cmp, Nat.cmp(Nat.double(Word.to_nat(p, at)), Nat.double(Word.to_nat(p, bt))), Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt)), nc_dd(Word.to_nat(p, at), Word.to_nat(p, bt)))))
        case WCon{True{}, +at} WCon{True{}, +bt}:
          Equal.trans(Cmp, Word.cmp.fin(True{}, True{}, Word.cmp(p, at, bt)), Word.cmp.fin(True{}, True{}, Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt))), Nat.cmp(Nat.double(Word.to_nat(p, at)), Nat.double(Word.to_nat(p, bt))),
            Equal.cong(Cmp, Cmp, t => Word.cmp.fin(True{}, True{}, t), Word.cmp(p, at, bt), Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt)), w_cmp_nat(p, at, bt)),
            Equal.trans(Cmp, Word.cmp.fin(True{}, True{}, Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt))), Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt)), Nat.cmp(Nat.double(Word.to_nat(p, at)), Nat.double(Word.to_nat(p, bt))),
              fin_tt(Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt))),
              Equal.sym(Cmp, Nat.cmp(Nat.double(Word.to_nat(p, at)), Nat.double(Word.to_nat(p, bt))), Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt)), nc_dd(Word.to_nat(p, at), Word.to_nat(p, bt)))))
        case WCon{False{}, +at} WCon{True{}, +bt}:
          Equal.trans(Cmp, Word.cmp.fin(False{}, True{}, Word.cmp(p, at, bt)), Word.cmp.fin(False{}, True{}, Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt))), Nat.cmp(Nat.double(Word.to_nat(p, at)), 1n+Nat.double(Word.to_nat(p, bt))),
            Equal.cong(Cmp, Cmp, t => Word.cmp.fin(False{}, True{}, t), Word.cmp(p, at, bt), Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt)), w_cmp_nat(p, at, bt)),
            Equal.sym(Cmp, Nat.cmp(Nat.double(Word.to_nat(p, at)), 1n+Nat.double(Word.to_nat(p, bt))), Word.cmp.fin(False{}, True{}, Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt))), nc_d1d(Word.to_nat(p, at), Word.to_nat(p, bt))))
        case WCon{True{}, +at} WCon{False{}, +bt}:
          Equal.trans(Cmp, Word.cmp.fin(True{}, False{}, Word.cmp(p, at, bt)), Word.cmp.fin(True{}, False{}, Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt))), Nat.cmp(1n+Nat.double(Word.to_nat(p, at)), Nat.double(Word.to_nat(p, bt))),
            Equal.cong(Cmp, Cmp, t => Word.cmp.fin(True{}, False{}, t), Word.cmp(p, at, bt), Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt)), w_cmp_nat(p, at, bt)),
            Equal.sym(Cmp, Nat.cmp(1n+Nat.double(Word.to_nat(p, at)), Nat.double(Word.to_nat(p, bt))), Word.cmp.fin(True{}, False{}, Nat.cmp(Word.to_nat(p, at), Word.to_nat(p, bt))), nc_1dd(Word.to_nat(p, at), Word.to_nat(p, bt))))

# ---- the bound: to_nat(w) + 1 + to_nat(not w) == 2^n
def w_bound(+n: Nat, +w: Word(n)) -> {Nat.add(Word.to_nat(n, w), 1n+Word.to_nat(n, Word.not(n, w))) == shn(n, 1n) : Nat}:
  match n:
    case 0n:
      {==}
    case 1n+p:
      match w:
        case WCon{False{}, +t}:
          Equal.trans(Nat, Nat.add(Nat.double(Word.to_nat(p, t)), 2n+Nat.double(Word.to_nat(p, Word.not(p, t)))), Nat.double(Nat.add(Word.to_nat(p, t), 1n+Word.to_nat(p, Word.not(p, t)))), Nat.double(shn(p, 1n)), Equal.sym(Nat, Nat.double(Nat.add(Word.to_nat(p, t), 1n+Word.to_nat(p, Word.not(p, t)))), Nat.add(Nat.double(Word.to_nat(p, t)), 2n+Nat.double(Word.to_nat(p, Word.not(p, t)))), n_dbl_add(Word.to_nat(p, t), 1n+Word.to_nat(p, Word.not(p, t)))), Equal.cong(Nat, Nat, Nat.double, Nat.add(Word.to_nat(p, t), 1n+Word.to_nat(p, Word.not(p, t))), shn(p, 1n), w_bound(p, t)))
        case WCon{True{}, +t}:
          Equal.trans(Nat, 1n+Nat.add(Nat.double(Word.to_nat(p, t)), 1n+Nat.double(Word.to_nat(p, Word.not(p, t)))), 1n+(1n+Nat.add(Nat.double(Word.to_nat(p, t)), Nat.double(Word.to_nat(p, Word.not(p, t))))), Nat.double(shn(p, 1n)), Equal.cong(Nat, Nat, x => 1n+x, Nat.add(Nat.double(Word.to_nat(p, t)), 1n+Nat.double(Word.to_nat(p, Word.not(p, t)))), 1n+Nat.add(Nat.double(Word.to_nat(p, t)), Nat.double(Word.to_nat(p, Word.not(p, t)))), n_add_s(Nat.double(Word.to_nat(p, t)), Nat.double(Word.to_nat(p, Word.not(p, t))))), Equal.trans(Nat, 1n+(1n+Nat.add(Nat.double(Word.to_nat(p, t)), Nat.double(Word.to_nat(p, Word.not(p, t))))), Nat.add(Nat.double(Word.to_nat(p, t)), 2n+Nat.double(Word.to_nat(p, Word.not(p, t)))), Nat.double(shn(p, 1n)), Equal.sym(Nat, Nat.add(Nat.double(Word.to_nat(p, t)), 2n+Nat.double(Word.to_nat(p, Word.not(p, t)))), 1n+(1n+Nat.add(Nat.double(Word.to_nat(p, t)), Nat.double(Word.to_nat(p, Word.not(p, t))))), Equal.trans(Nat, Nat.add(Nat.double(Word.to_nat(p, t)), 2n+Nat.double(Word.to_nat(p, Word.not(p, t)))), 1n+Nat.add(Nat.double(Word.to_nat(p, t)), 1n+Nat.double(Word.to_nat(p, Word.not(p, t)))), 1n+(1n+Nat.add(Nat.double(Word.to_nat(p, t)), Nat.double(Word.to_nat(p, Word.not(p, t))))), n_add_s(Nat.double(Word.to_nat(p, t)), 1n+Nat.double(Word.to_nat(p, Word.not(p, t)))), Equal.cong(Nat, Nat, x => 1n+x, Nat.add(Nat.double(Word.to_nat(p, t)), 1n+Nat.double(Word.to_nat(p, Word.not(p, t)))), 1n+Nat.add(Nat.double(Word.to_nat(p, t)), Nat.double(Word.to_nat(p, Word.not(p, t)))), n_add_s(Nat.double(Word.to_nat(p, t)), Nat.double(Word.to_nat(p, Word.not(p, t))))))), Equal.trans(Nat, Nat.add(Nat.double(Word.to_nat(p, t)), 2n+Nat.double(Word.to_nat(p, Word.not(p, t)))), Nat.double(Nat.add(Word.to_nat(p, t), 1n+Word.to_nat(p, Word.not(p, t)))), Nat.double(shn(p, 1n)), Equal.sym(Nat, Nat.double(Nat.add(Word.to_nat(p, t), 1n+Word.to_nat(p, Word.not(p, t)))), Nat.add(Nat.double(Word.to_nat(p, t)), 2n+Nat.double(Word.to_nat(p, Word.not(p, t)))), n_dbl_add(Word.to_nat(p, t), 1n+Word.to_nat(p, Word.not(p, t)))), Equal.cong(Nat, Nat, Nat.double, Nat.add(Word.to_nat(p, t), 1n+Word.to_nat(p, Word.not(p, t))), shn(p, 1n), w_bound(p, t)))))
'''



def add(a, b):
    return f"Nat.add({a}, {b})"


def dbl(a):
    return f"Nat.double({a})"


def chain(T, t0, steps):
    """A proof of {t0 == tn : T} from steps [(proof of {t_{i-1} == t_i}, t_i), ...]."""
    if not steps:
        return "{==}"
    terms = [t0] + [t for _p, t in steps]
    tn = terms[-1]

    def go(i):
        p, ti = steps[i]
        if i == len(steps) - 1:
            return p
        return f"Equal.trans({T}, {terms[i]}, {ti}, {tn}, {p}, {go(i + 1)})"
    return go(0)


def sym(T, a, b, p):
    """{b == a} from p : {a == b}."""
    return f"Equal.sym({T}, {a}, {b}, {p})"


def cong(A, B, f, a, b, p):
    return f"Equal.cong({A}, {B}, {f}, {a}, {b}, {p})"


def cong_l(a, b, c, p):
    """{a + c == b + c} from {a == b}."""
    return f"n_cong_l({a}, {b}, {c}, {p})"


def cong_r(c, a, b, p):
    """{c + a == c + b} from {a == b}."""
    return f"n_cong_r({c}, {a}, {b}, {p})"


def succ(a, b, p):
    return cong("Nat", "Nat", "x => 1n+x", a, b, p)

P32 = "shn(32n, 1n)"


def _u32_add(M="M."):
    out = []
    # u_add(a, b) == a + b
    out.append(f'''
# a + 0 == a and 0 + b == b on U32
def u_add_z(+a: U32) -> {{U32.add(a, 0) == a : U32}}:
  match a:
    case U32{{+x}}:
      Equal.cong(Word(32n), U32, w => U32{{w}}, Word.adc(32n, x, Word.zero(32n), False{{}}, False{{}}), x, w_adc_zr(32n, x))

def u_z_add(+b: U32) -> {{U32.add(0, b) == b : U32}}:
  match b:
    case U32{{+y}}:
      Equal.cong(Word(32n), U32, w => U32{{w}}, Word.adc(32n, Word.zero(32n), y, False{{}}, False{{}}), y, w_adc_zl(32n, y))

def u_add_eq_a(c: Bool, +a: U32, +b: U32, e: {{U32.is_eq(a, 0) == c : Bool}}) -> {{{M}ite(U32, c, b, U32.add(a, b)) == U32.add(a, b) : U32}}:
  match c:
    case True{{}}:
      (%Equal.sym(U32, a, 0, u_refl(a, 0, e)) : {{b == U32.add(_, b) : U32}}
      Equal.sym(U32, U32.add(0, b), b, u_z_add(b)))
    case False{{}}:
      {{==}}

def u_add_eq_b(c: Bool, +a: U32, +b: U32, e: {{U32.is_eq(b, 0) == c : Bool}}) -> {{{M}ite(U32, c, a, {M}ite(U32, U32.is_eq(a, 0), b, U32.add(a, b))) == U32.add(a, b) : U32}}:
  match c:
    case True{{}}:
      (%Equal.sym(U32, b, 0, u_refl(b, 0, e)) : {{a == U32.add(a, _) : U32}}
      Equal.sym(U32, U32.add(a, 0), a, u_add_z(a)))
    case False{{}}:
      u_add_eq_a(U32.is_eq(a, 0), a, b, {{==}})

def u_add_eq(+a: U32, +b: U32) -> {{{M}u_add(a, b) == U32.add(a, b) : U32}}:
  u_add_eq_b(U32.is_eq(b, 0), a, b, {{==}})
''')
    return "\n".join(out)


def _u32_limbs(M="M."):
    """One limb of the model's w_add: its sum (u_addc of u_add) is Word.adc with the carry in, and its carry out
    (U32.is_lt tests) is wcarry; then the limb's Nat identity with the power 2^32 kept opaque."""
    X, Y = "U32{x}", "U32{y}"
    ua = f"{M}u_add({X}, {Y})"
    T = "Word.to_nat(32n, Word.adc(32n, x, y, False{}, False{}))"
    S = "Word.to_nat(32n, Word.adc(32n, x, y, False{}, True{}))"
    Xn, Yn = "Word.to_nat(32n, x)", "Word.to_nat(32n, y)"
    Tn = "Word.to_nat(32n, Word.not(32n, Word.adc(32n, x, y, False{}, False{})))"
    Sn = "Word.to_nat(32n, Word.not(32n, Word.adc(32n, x, y, False{}, True{})))"
    YN = "Word.to_nat(32n, Word.not(32n, y))"
    P = "shn(32n, 1n)"

    def bridge(c):   # {T + cmul(wcarry(c), P) == (X + Y) + b2n(c)} from w_adc_nat and shn_b2n
        tt = T if c == "False{}" else S
        cw = f"wcarry(32n, x, y, {c})"
        return chain("Nat", add(tt, f"cmul({cw}, {P})"), [
            (cong_r(tt, f"cmul({cw}, {P})", f"shn(32n, b2n({cw}))", sym("Nat", f"shn(32n, b2n({cw}))", f"cmul({cw}, {P})",
                                                                     f"shn_b2n(32n, {cw})")), add(tt, f"shn(32n, b2n({cw}))")),
            (f"w_adc_nat(32n, x, y, {c})", add(add(Xn, Yn), f"b2n({c})")),
            ("{==}", add(add(Xn, Yn), "0n" if c == "False{}" else "1n"))])
    c0 = (f"nc_carry0(wcarry(32n, x, y, False{{}}), {T}, {Xn}, {Yn}, {YN}, {P}, {bridge('False{}')}, w_bound(32n, y))")
    c1 = (f"nc_carry1(wcarry(32n, x, y, False{{}}), wcarry(32n, x, y, True{{}}), {T}, {S}, {Xn}, {Yn}, {YN}, {Sn}, {Tn}, {P}, "
          f"shn(31n, 1n), {bridge('False{}')}, {bridge('True{}')}, w_bound(32n, y), w_bound(32n, Word.adc(32n, x, y, False{{}}, True{{}})), "
          f"w_bound(32n, Word.adc(32n, x, y, False{{}}, False{{}})), shn_dbl(32n, 31n, {{==}}))")
    t_cmp = "Word.cmp(32n, Word.adc(32n, x, y, False{}, False{}), x)"
    s_cmp = "Word.cmp(32n, Word.adc(32n, x, y, False{}, True{}), Word.adc(32n, x, y, False{}, False{}))"
    t_ncmp = f"Nat.cmp({T}, {Xn})"
    s_ncmp = f"Nat.cmp({S}, {T})"
    return f'''
def shn_dbl(+n: Nat, +q: Nat, e: {{n == 1n+q : Nat}}) -> {{shn(n, 1n) == Nat.double(shn(q, 1n)) : Nat}}:
  (%Equal.sym(Nat, n, 1n+q, e) : {{shn(_, 1n) == Nat.double(shn(q, 1n)) : Nat}}
  {{==}})

# the limb's sum: u_addc(u_add(x, y), k) is Word.adc with the carry k in
def u_s_limb_k(+k: Bool, +x: Word(32n), +y: Word(32n)) -> {{{M}u_addc(U32.add({X}, {Y}), k) == U32{{Word.adc(32n, x, y, False{{}}, k)}} : U32}}:
  match k:
    case True{{}}:
      Equal.cong(Word(32n), U32, w => U32{{w}}, Word.inc(32n, Word.adc(32n, x, y, False{{}}, False{{}})), Word.adc(32n, x, y, False{{}}, True{{}}), w_inc_adc(32n, x, y))
    case False{{}}:
      {{==}}

def u_s_limb(+k: Bool, +x: Word(32n), +y: Word(32n)) -> {{{M}u_addc({ua}, k) == U32{{Word.adc(32n, x, y, False{{}}, k)}} : U32}}:
  (%Equal.sym(U32, {ua}, U32.add({X}, {Y}), u_add_eq({X}, {Y})) : {{{M}u_addc(_, k) == U32{{Word.adc(32n, x, y, False{{}}, k)}} : U32}}
  u_s_limb_k(k, x, y))

# limb 0's carry out: t < x for t = u_add(x, y)
def u_c_limb0(+x: Word(32n), +y: Word(32n)) -> {{U32.is_lt({ua}, {X}) == wcarry(32n, x, y, False{{}}) : Bool}}:
  (%Equal.sym(U32, {ua}, U32.add({X}, {Y}), u_add_eq({X}, {Y})) : {{U32.is_lt(_, {X}) == wcarry(32n, x, y, False{{}}) : Bool}}
  (%Equal.sym(Cmp, {t_cmp}, {t_ncmp}, w_cmp_nat(32n, Word.adc(32n, x, y, False{{}}, False{{}}), x)) : {{Cmp.is_lt(_) == wcarry(32n, x, y, False{{}}) : Bool}}
  {c0}))

# a limb's carry out with the carry k in: (t < x) or (s < t) for t = u_add(x, y), s = u_addc(t, k)
def u_c_limb_k(+k: Bool, +x: Word(32n), +y: Word(32n)) -> {{Bool.or(U32.is_lt(U32.add({X}, {Y}), {X}), U32.is_lt(U32{{Word.adc(32n, x, y, False{{}}, k)}}, U32.add({X}, {Y}))) == wcarry(32n, x, y, k) : Bool}}:
  match k:
    case True{{}}:
      (%Equal.sym(Cmp, {t_cmp}, {t_ncmp}, w_cmp_nat(32n, Word.adc(32n, x, y, False{{}}, False{{}}), x)) : {{Bool.or(Cmp.is_lt(_), Cmp.is_lt({s_cmp})) == wcarry(32n, x, y, True{{}}) : Bool}}
      (%Equal.sym(Cmp, {s_cmp}, {s_ncmp}, w_cmp_nat(32n, Word.adc(32n, x, y, False{{}}, True{{}}), Word.adc(32n, x, y, False{{}}, False{{}}))) : {{Bool.or(Cmp.is_lt({t_ncmp}), Cmp.is_lt(_)) == wcarry(32n, x, y, True{{}}) : Bool}}
      {c1}))
    case False{{}}:
      (%Equal.sym(Cmp, Word.cmp(32n, Word.adc(32n, x, y, False{{}}, False{{}}), Word.adc(32n, x, y, False{{}}, False{{}})), EQ{{}}, Equal.trans(Cmp, Word.cmp(32n, Word.adc(32n, x, y, False{{}}, False{{}}), Word.adc(32n, x, y, False{{}}, False{{}})), Nat.cmp({T}, {T}), EQ{{}}, w_cmp_nat(32n, Word.adc(32n, x, y, False{{}}, False{{}}), Word.adc(32n, x, y, False{{}}, False{{}})), n_cmp_refl({T}))) : {{Bool.or(U32.is_lt(U32.add({X}, {Y}), {X}), Cmp.is_lt(_)) == wcarry(32n, x, y, False{{}}) : Bool}}
      Equal.trans(Bool, Bool.or(U32.is_lt(U32.add({X}, {Y}), {X}), False{{}}), U32.is_lt(U32.add({X}, {Y}), {X}), wcarry(32n, x, y, False{{}}),
        bool_or_f(U32.is_lt(U32.add({X}, {Y}), {X})),
        (%Equal.sym(Cmp, {t_cmp}, {t_ncmp}, w_cmp_nat(32n, Word.adc(32n, x, y, False{{}}, False{{}}), x)) : {{Cmp.is_lt(_) == wcarry(32n, x, y, False{{}}) : Bool}}
        {c0})))

def u_c_limb(+k: Bool, +x: Word(32n), +y: Word(32n)) -> {{Bool.or(U32.is_lt({ua}, {X}), U32.is_lt({M}u_addc({ua}, k), {ua})) == wcarry(32n, x, y, k) : Bool}}:
  (%Equal.sym(U32, {M}u_addc({ua}, k), U32{{Word.adc(32n, x, y, False{{}}, k)}}, u_s_limb(k, x, y)) : {{Bool.or(U32.is_lt({ua}, {X}), U32.is_lt(_, {ua})) == wcarry(32n, x, y, k) : Bool}}
  (%Equal.sym(U32, {ua}, U32.add({X}, {Y}), u_add_eq({X}, {Y})) : {{Bool.or(U32.is_lt(_, {X}), U32.is_lt(U32{{Word.adc(32n, x, y, False{{}}, k)}}, _)) == wcarry(32n, x, y, k) : Bool}}
  u_c_limb_k(k, x, y)))
'''

def _natcmp():
    out = ['''
def n_cmp_refl(+a: Nat) -> {Nat.cmp(a, a) == EQ{} : Cmp}:
  match a:
    case 0n:
      {==}
    case 1n+p:
      n_cmp_refl(p)

# a < a + 1 + d
def n_lt_add(+a: Nat, +d: Nat) -> {Cmp.is_lt(Nat.cmp(a, Nat.add(a, 1n+d))) == True{} : Bool}:
  match a:
    case 0n:
      {==}
    case 1n+p:
      n_lt_add(p, d)

# not (a + d < a)
def n_nlt_add(+a: Nat, +d: Nat) -> {Cmp.is_lt(Nat.cmp(Nat.add(a, d), a)) == False{} : Bool}:
  match a:
    case 0n:
      match d:
        case 0n:
          {==}
        case 1n+q:
          {==}
    case 1n+p:
      n_nlt_add(p, d)

def n_zero_sum(+a: Nat, +b: Nat, e: {Nat.add(a, b) == 0n : Nat}) -> {a == 0n : Nat}:
  match a:
    case 0n:
      {==}
    case 1n+p:
      efq({1n+p == 0n : Nat}, n_succ_nz(Nat.add(p, b), e))

def n_dbl_ne1(+q: Nat, e: {Nat.double(q) == 1n : Nat}) -> Empty:
  match q:
    case 0n:
      n_succ_nz(0n, Equal.sym(Nat, 0n, 1n, e))
    case 1n+r:
      n_succ_nz(Nat.double(r), n_succ_inj(1n+Nat.double(r), 0n, e))

def bool_or_f(+c: Bool) -> {Bool.or(c, False{}) == c : Bool}:
  match c:
    case True{}:
      {==}
    case False{}:
      {==}

# c * pw for a carry c (pw a power of two, kept opaque: the checker never expands it)
def cmul(c: Bool, +pw: Nat) -> Nat:
  match c:
    case True{}:
      pw
    case False{}:
      0n

def shn_z(+n: Nat) -> {shn(n, 0n) == 0n : Nat}:
  match n:
    case 0n:
      {==}
    case 1n+p:
      Equal.cong(Nat, Nat, Nat.double, shn(p, 0n), 0n, shn_z(p))

def shn_b2n(+n: Nat, +c: Bool) -> {shn(n, b2n(c)) == cmul(c, shn(n, 1n)) : Nat}:
  match c:
    case True{}:
      {==}
    case False{}:
      shn_z(n)
''']
    # rearrangement: t + (y + (1 + d)) == y + (t + (1 + d))
    t, y, d, x = "t", "y", "d", "x"
    r1 = chain("Nat", add(t, add(y, f"1n+{d}")), [
        (sym("Nat", add(add(t, y), f"1n+{d}"), add(t, add(y, f"1n+{d}")), f"n_add_assoc({t}, {y}, 1n+{d})"), add(add(t, y), f"1n+{d}")),
        (cong_l(add(t, y), add(y, t), f"1n+{d}", f"n_add_comm({t}, {y})"), add(add(y, t), f"1n+{d}")),
        (f"n_add_assoc({y}, {t}, 1n+{d})", add(y, add(t, f"1n+{d}")))])
    out.append(f'''
def n_rot3(+t: Nat, +y: Nat, +d: Nat) -> {{{add(t, add(y, "1n+d"))} == {add(y, add(t, "1n+d"))} : Nat}}:
  {r1}
''')
    # NC1: from t + 2^32 c == (x + y) + 0 and y + (1 + d) == 2^32, the test t < x is the carry c
    P = "pw"
    # case True: t + P == (x + y) + 0 -> t + (y + (1 + d)) == ... -> y + (t + (1 + d)) == y + x -> t + (1 + d) == x
    lhs = add(t, P)
    e_sub = f"(%Equal.sym(Nat, {add(y, '1n+d')}, {P}, by) : {{{add(t, '_')} == {add(add(x, y), '0n')} : Nat}}\n        e)"
    # e_sub : {t + (y + (1 + d)) == (x + y) + 0}
    to_x = chain("Nat", add(y, add(t, "1n+d")), [
        (sym("Nat", add(t, add(y, "1n+d")), add(y, add(t, "1n+d")), "n_rot3(t, y, d)"), add(t, add(y, "1n+d"))),
        (e_sub, add(add(x, y), "0n")),
        (f"n_add_z({add(x, y)})", add(x, y)),
        (f"n_add_comm({x}, {y})", add(y, x))])
    eq_x = f"n_cancel_l({y}, {add(t, '1n+d')}, {x}, {to_x})"
    true_case = f"(%{eq_x} : {{Cmp.is_lt(Nat.cmp({t}, _)) == True{{}} : Bool}}\n        n_lt_add({t}, {d}))"
    # case False: t + 0 == (x + y) + 0 -> t == x + y
    t_eq = chain("Nat", t, [
        (sym("Nat", add(t, "0n"), t, f"n_add_z({t})"), add(t, "0n")),
        ("e", add(add(x, y), "0n")),
        (f"n_add_z({add(x, y)})", add(x, y))])
    false_case = f"(%Equal.sym(Nat, {t}, {add(x, y)}, {t_eq}) : {{Cmp.is_lt(Nat.cmp(_, {x})) == False{{}} : Bool}}\n        n_nlt_add({x}, {y}))"
    out.append(f'''
# the carry of t = x + y (mod 2^32) is the test t < x (y + 1 + d == 2^32 bounds y)
def nc_carry0(c: Bool, +t: Nat, +x: Nat, +y: Nat, +d: Nat, +pw: Nat, e: {{Nat.add(t, cmul(c, pw)) == {add(add(x, y), "0n")} : Nat}},
              +by: {{{add(y, "1n+d")} == {P} : Nat}}) -> {{Cmp.is_lt(Nat.cmp(t, x)) == c : Bool}}:
  match c:
    case True{{}}:
      {true_case}
    case False{{}}:
      {false_case}
''')
    return "\n".join(out)


def _natcarry():
    """The carry with a carry-in: or(t < x, s < t) is the carry of s = x + y + 1 (mod pw), t = x + y (mod pw)."""
    x, y, t, s = "x", "y", "t", "s"
    xy = add(x, y)
    # (F, F): t == x + y, s == (x + y) + 1 -> s == t + 1
    t_eq = chain("Nat", t, [(sym("Nat", add(t, "0n"), t, f"n_add_z({t})"), add(t, "0n")), ("e1", add(xy, "0n")),
                            (f"n_add_z({xy})", xy)])
    s_eq = chain("Nat", s, [(sym("Nat", add(s, "0n"), s, f"n_add_z({s})"), add(s, "0n")), ("e2", add(xy, "1n"))])
    s_t1 = chain("Nat", s, [(s_eq, add(xy, "1n")), (cong_l(xy, t, "1n", sym("Nat", t, xy, t_eq)), add(t, "1n"))])
    ff = (f"(%Equal.sym(Nat, {s}, {add(t, '1n')}, {s_t1}) : {{Cmp.is_lt(Nat.cmp(_, {t})) == False{{}} : Bool}}\n"
          f"        n_nlt_add({t}, 1n))")
    # (T, F): s == (t + pw) + 1, and s + (1 + ds) == pw: pw + (t + (1 + (1 + ds))) == pw + 0, a successor is 0
    s_tp = chain("Nat", s, [(s_eq, add(xy, "1n")), (cong_l(xy, add(t, "pw"), "1n", sym("Nat", add(t, "pw"), xy,
                                                                                   f"Equal.trans(Nat, {add(t, 'pw')}, {add(xy, '0n')}, {xy}, e1, n_add_z({xy}))")),
                                                      add(add(t, "pw"), "1n"))])
    z = add(t, "1n+(1n+ds)")
    # ((t + pw) + 1) + (1 + ds) == pw + (t + (1 + (1 + ds)))
    lhs = add(add(add(t, "pw"), "1n"), "1n+ds")
    rr = chain("Nat", lhs, [
        (f"n_add_assoc({add(t, 'pw')}, 1n, 1n+ds)", add(add(t, "pw"), add("1n", "1n+ds"))),
        (f"n_add_assoc({t}, pw, {add('1n', '1n+ds')})", add(t, add("pw", add("1n", "1n+ds")))),
        (cong_r(t, add("pw", add("1n", "1n+ds")), add(add("1n", "1n+ds"), "pw"), f"n_add_comm(pw, {add('1n', '1n+ds')})"),
         add(t, add(add("1n", "1n+ds"), "pw"))),
        (sym("Nat", add(add(t, add("1n", "1n+ds")), "pw"), add(t, add(add("1n", "1n+ds"), "pw")),
             f"n_add_assoc({t}, {add('1n', '1n+ds')}, pw)"), add(add(t, add("1n", "1n+ds")), "pw")),
        (f"n_add_comm({add(t, add('1n', '1n+ds'))}, pw)", add("pw", add(t, add("1n", "1n+ds"))))])
    # pw + (t + (1 + (1 + ds))) == s + (1 + ds) == pw == pw + 0
    to0 = chain("Nat", add("pw", add(t, add("1n", "1n+ds"))), [
        (sym("Nat", lhs, add("pw", add(t, add("1n", "1n+ds"))), rr), lhs),
        (sym("Nat", add(s, "1n+ds"), lhs, cong_l(s, add(add(t, "pw"), "1n"), "1n+ds", s_tp)), add(s, "1n+ds")),
        ("bs", "pw"), (sym("Nat", add("pw", "0n"), "pw", "n_add_z(pw)"), add("pw", "0n"))])
    z0 = f"n_cancel_l(pw, {add(t, add('1n', '1n+ds'))}, 0n, {to0})"
    # t + (1 + (1 + ds)) == 1 + (t + (1 + ds)) (n_add_s), so a successor is 0
    tf = (f"efq({{Bool.or(True{{}}, Cmp.is_lt(Nat.cmp({s}, {t}))) == False{{}} : Bool}}, n_succ_nz({add(t, '1n+ds')}, "
          f"Equal.trans(Nat, 1n+{add(t, '1n+ds')}, {add(t, add('1n', '1n+ds'))}, 0n, "
          f"Equal.sym(Nat, {add(t, add('1n', '1n+ds'))}, 1n+{add(t, '1n+ds')}, n_add_s({t}, 1n+ds)), {z0})))")
    # (F, T): t == x + y; s + pw == t + 1; t + (1 + dt) == pw  ->  s + dt == 0 -> s == 0, dt == 0 -> pw == 1, unless t > 0
    s_pw = chain("Nat", add(s, "pw"), [("e2", add(xy, "1n")), (cong_l(xy, t, "1n", sym("Nat", t, xy, t_eq)), add(t, "1n"))])
    # (t + 1) + (s + dt) == s + (t + (1 + dt)) == s + pw == t + 1 == (t + 1) + 0
    a1 = add(add(t, "1n"), add(s, "dt"))
    a2 = add(s, add(t, "1n+dt"))
    a1a2 = chain("Nat", a1, [
        (f"n_add_comm({add(t, '1n')}, {add(s, 'dt')})", add(add(s, "dt"), add(t, "1n"))),
        (f"n_add_assoc({s}, dt, {add(t, '1n')})", add(s, add("dt", add(t, "1n")))),
        (cong_r(s, add("dt", add(t, "1n")), add(t, "1n+dt"),
                chain("Nat", add("dt", add(t, "1n")), [
                    (f"n_add_comm(dt, {add(t, '1n')})", add(add(t, "1n"), "dt")),
                    (f"n_add_assoc({t}, 1n, dt)", add(t, add("1n", "dt")))])), a2)])
    to_t1 = chain("Nat", a1, [(a1a2, a2), (cong_r(s, add(t, "1n+dt"), "pw", "bt"), add(s, "pw")), (s_pw, add(t, "1n")),
                              (sym("Nat", add(add(t, "1n"), "0n"), add(t, "1n"), f"n_add_z({add(t, '1n')})"), add(add(t, "1n"), "0n"))])
    sd0 = f"n_cancel_l({add(t, '1n')}, {add(s, 'dt')}, 0n, {to_t1})"
    s0 = f"n_zero_sum({s}, dt, {sd0})"
    dt0 = f"n_zero_sum(dt, {s}, Equal.trans(Nat, {add('dt', s)}, {add(s, 'dt')}, 0n, n_add_comm(dt, {s}), {sd0}))"
    ft = (f"(%Equal.sym(Nat, {s}, 0n, {s0}) : {{Bool.or(False{{}}, Cmp.is_lt(Nat.cmp(_, {t}))) == True{{}} : Bool}}\n"
          f"        nc_pos(t, dt, pw, q, bt, {dt0}, ev))")
    out = [f'''
# 0 < t when t + (1 + dt) == pw, dt == 0 and pw == 2 q (so pw is not 1)
def nc_pos(+t: Nat, +dt: Nat, +pw: Nat, +q: Nat, bt: {{{add('t', '1n+dt')} == pw : Nat}}, d0: {{dt == 0n : Nat}},
           ev: {{pw == Nat.double(q) : Nat}}) -> {{Cmp.is_lt(Nat.cmp(0n, t)) == True{{}} : Bool}}:
  match t:
    case 0n:
      efq({{Cmp.is_lt(Nat.cmp(0n, 0n)) == True{{}} : Bool}}, n_dbl_ne1(q, Equal.trans(Nat, Nat.double(q), pw, 1n,
        Equal.sym(Nat, pw, Nat.double(q), ev), Equal.trans(Nat, pw, 1n+dt, 1n, Equal.sym(Nat, 1n+dt, pw, bt),
        Equal.cong(Nat, Nat, z => 1n+z, dt, 0n, d0)))))
    case 1n+r:
      {{==}}

def nc_carry1_cases(c1: Bool, c2: Bool, +t: Nat, +s: Nat, +x: Nat, +y: Nat, +ds: Nat, +dt: Nat, +pw: Nat, +q: Nat,
              +e1: {{Nat.add(t, cmul(c1, pw)) == {add(xy, '0n')} : Nat}}, +e2: {{Nat.add(s, cmul(c2, pw)) == {add(xy, '1n')} : Nat}},
              +bs: {{{add('s', '1n+ds')} == pw : Nat}},
              +bt: {{{add('t', '1n+dt')} == pw : Nat}}, +ev: {{pw == Nat.double(q) : Nat}}) ->
              {{Bool.or(c1, Cmp.is_lt(Nat.cmp(s, t))) == c2 : Bool}}:
  match c1 c2:
    case True{{}} True{{}}:
      {{==}}
    case False{{}} False{{}}:
      {ff}
    case True{{}} False{{}}:
      {tf}
    case False{{}} True{{}}:
      {ft}

def nc_carry1(+c1: Bool, +c2: Bool, +t: Nat, +s: Nat, +x: Nat, +y: Nat, +dy: Nat, +ds: Nat, +dt: Nat, +pw: Nat, +q: Nat,
              +e1: {{Nat.add(t, cmul(c1, pw)) == {add(xy, '0n')} : Nat}}, +e2: {{Nat.add(s, cmul(c2, pw)) == {add(xy, '1n')} : Nat}},
              +by: {{{add('y', '1n+dy')} == pw : Nat}}, +bs: {{{add('s', '1n+ds')} == pw : Nat}},
              +bt: {{{add('t', '1n+dt')} == pw : Nat}}, +ev: {{pw == Nat.double(q) : Nat}}) ->
              {{Bool.or(Cmp.is_lt(Nat.cmp(t, x)), Cmp.is_lt(Nat.cmp(s, t))) == c2 : Bool}}:
  (%Equal.sym(Bool, Cmp.is_lt(Nat.cmp(t, x)), c1, nc_carry0(c1, t, x, y, dy, pw, e1, by)) : {{Bool.or(_, Cmp.is_lt(Nat.cmp(s, t))) == c2 : Bool}}
  nc_carry1_cases(c1, c2, t, s, x, y, ds, dt, pw, q, e1, e2, bs, bt, ev))

''']
    return "\n".join(out)

def p256():
    q = "1n"
    for _ in range(8):
        q = f"shn(32n, {q})"
    return q


def _w_generic():
    s, r, x, xr, y, yr = "s", "r", "x", "xr", "y", "yr"
    A, B = "shn(32n, xr)", "shn(32n, yr)"
    CM = f"cmul(k1, {P32})"
    L0 = add(add(s, "shn(32n, r)"), "cmul(k8, shn(32n, q))")
    steps = [
        (cong_r(add(s, "shn(32n, r)"), "cmul(k8, shn(32n, q))", "shn(32n, cmul(k8, q))",
                sym("Nat", "shn(32n, cmul(k8, q))", "cmul(k8, shn(32n, q))", "shn_cmul(32n, k8, q)")),
         add(add(s, "shn(32n, r)"), "shn(32n, cmul(k8, q))")),
        ("n_add_assoc(s, shn(32n, r), shn(32n, cmul(k8, q)))", add(s, add("shn(32n, r)", "shn(32n, cmul(k8, q))"))),
        (cong_r(s, add("shn(32n, r)", "shn(32n, cmul(k8, q))"), "shn(32n, Nat.add(r, cmul(k8, q)))",
                sym("Nat", "shn(32n, Nat.add(r, cmul(k8, q)))", add("shn(32n, r)", "shn(32n, cmul(k8, q))"),
                    "shn_add(32n, r, cmul(k8, q))")), add(s, "shn(32n, Nat.add(r, cmul(k8, q)))")),
        (cong_r(s, "shn(32n, Nat.add(r, cmul(k8, q)))", f"shn(32n, {add(add(xr, yr), 'b2n(k1)')})",
                cong("Nat", "Nat", "z => shn(32n, z)", "Nat.add(r, cmul(k8, q))", add(add(xr, yr), "b2n(k1)"), "rest")),
         add(s, f"shn(32n, {add(add(xr, yr), 'b2n(k1)')})")),
        (cong_r(s, f"shn(32n, {add(add(xr, yr), 'b2n(k1)')})", add(f"shn(32n, {add(xr, yr)})", "shn(32n, b2n(k1))"),
                f"shn_add(32n, {add(xr, yr)}, b2n(k1))"), add(s, add(f"shn(32n, {add(xr, yr)})", "shn(32n, b2n(k1))"))),
        (cong_r(s, add(f"shn(32n, {add(xr, yr)})", "shn(32n, b2n(k1))"), add(add(A, B), "shn(32n, b2n(k1))"),
                cong_l(f"shn(32n, {add(xr, yr)})", add(A, B), "shn(32n, b2n(k1))", "shn_add(32n, xr, yr)")),
         add(s, add(add(A, B), "shn(32n, b2n(k1))"))),
        (cong_r(s, add(add(A, B), "shn(32n, b2n(k1))"), add(add(A, B), CM),
                cong_r(add(A, B), "shn(32n, b2n(k1))", CM, "shn_b2n(32n, k1)")), add(s, add(add(A, B), CM))),
        (f"n_r1({s}, {add(A, B)}, {CM})", add(add(s, CM), add(A, B))),
        (cong_l(add(s, CM), add(add(x, y), "b2n(k)"), add(A, B), "limb"), add(add(add(x, y), "b2n(k)"), add(A, B)))]
    lhs = chain("Nat", L0, steps)
    R0 = add(add(add(x, A), add(y, B)), "b2n(k)")
    rsteps = [(cong_l(add(add(x, A), add(y, B)), add(add(x, y), add(A, B)), "b2n(k)", f"n_swap_mid({x}, {A}, {y}, {B})"),
               add(add(add(x, y), add(A, B)), "b2n(k)")),
              (f"n_r2({add(x, y)}, {add(A, B)}, b2n(k))", add(add(add(x, y), "b2n(k)"), add(A, B)))]
    rhs = chain("Nat", R0, rsteps)
    mid = add(add(add(x, y), "b2n(k)"), add(A, B))
    return f'''
def shn_cmul(+n: Nat, +c: Bool, +q: Nat) -> {{shn(n, cmul(c, q)) == cmul(c, shn(n, q)) : Nat}}:
  match c:
    case True{{}}:
      {{==}}
    case False{{}}:
      shn_z(n)

def bool_nn(+c: Bool) -> {{Bool.not(Bool.not(c)) == c : Bool}}:
  match c:
    case True{{}}:
      {{==}}
    case False{{}}:
      {{==}}

# s + (u + v) == (s + v) + u
def n_r1(+s: Nat, +u: Nat, +v: Nat) -> {{Nat.add(s, Nat.add(u, v)) == Nat.add(Nat.add(s, v), u) : Nat}}:
  {chain("Nat", add("s", add("u", "v")), [(cong_r("s", add("u", "v"), add("v", "u"), "n_add_comm(u, v)"), add("s", add("v", "u"))),
                                          (sym("Nat", add(add("s", "v"), "u"), add("s", add("v", "u")), "n_add_assoc(s, v, u)"), add(add("s", "v"), "u"))])}

# (u + v) + w == (u + w) + v
def n_r2(+u: Nat, +v: Nat, +w: Nat) -> {{Nat.add(Nat.add(u, v), w) == Nat.add(Nat.add(u, w), v) : Nat}}:
  {chain("Nat", add(add("u", "v"), "w"), [("n_add_assoc(u, v, w)", add("u", add("v", "w"))),
                                          ("n_r1(u, v, w)", add(add("u", "w"), "v"))])}

# a <= a + d
def n_le_add(+a: Nat, +d: Nat) -> {{Nat.is_le(a, Nat.add(a, d)) == True{{}} : Bool}}:
  match a:
    case 0n:
      match d:
        case 0n:
          {{==}}
        case 1n+e:
          {{==}}
    case 1n+p:
      n_le_add(p, d)

# one Horner step of the sum of two words: a limb (s with its carry k1 out of k in) below the rest (r, carry k8 out)
def hs(+s: Nat, +r: Nat, +x: Nat, +xr: Nat, +y: Nat, +yr: Nat, +k: Bool, +k1: Bool, +k8: Bool, +q: Nat,
       +limb: {{Nat.add(s, cmul(k1, {P32})) == Nat.add(Nat.add(x, y), b2n(k)) : Nat}},
       +rest: {{Nat.add(r, cmul(k8, q)) == Nat.add(Nat.add(xr, yr), b2n(k1)) : Nat}}) ->
       {{{L0} == {R0} : Nat}}:
  Equal.trans(Nat, {L0}, {mid}, {R0}, {lhs}, Equal.sym(Nat, {R0}, {mid}, {rhs}))
'''


def _w_limbs(M="M."):
    X, Y = "U32{x}", "U32{y}"
    ua = f"{M}u_add({X}, {Y})"
    kout = f"Bool.or(U32.is_lt({ua}, {X}), U32.is_lt({M}u_addc({ua}, k), {ua}))"
    sl = f"{M}u_addc({ua}, k)"
    adc = "Word.adc(32n, x, y, False{}, k)"
    cw = "wcarry(32n, x, y, k)"
    rhs = add(add("U32.to_nat(U32{x})", "U32.to_nat(U32{y})"), "b2n(k)")
    rhs_w = add(add("Word.to_nat(32n, x)", "Word.to_nat(32n, y)"), "b2n(k)")
    L = add(f"U32.to_nat({sl})", f"cmul({kout}, {P32})")
    steps = [
        (cong_l(f"U32.to_nat({sl})", f"Word.to_nat(32n, {adc})", f"cmul({kout}, {P32})",
                cong("U32", "Nat", "U32.to_nat", sl, f"U32{{{adc}}}", f"u_s_limb(k, x, y)")),
         add(f"Word.to_nat(32n, {adc})", f"cmul({kout}, {P32})")),
        (cong_r(f"Word.to_nat(32n, {adc})", f"cmul({kout}, {P32})", f"cmul({cw}, {P32})",
                cong("Bool", "Nat", f"c => cmul(c, {P32})", kout, cw, "u_c_limb(k, x, y)")),
         add(f"Word.to_nat(32n, {adc})", f"cmul({cw}, {P32})")),
        (cong_r(f"Word.to_nat(32n, {adc})", f"cmul({cw}, {P32})", f"shn(32n, b2n({cw}))",
                sym("Nat", f"shn(32n, b2n({cw}))", f"cmul({cw}, {P32})", f"shn_b2n(32n, {cw})")),
         add(f"Word.to_nat(32n, {adc})", f"shn(32n, b2n({cw}))")),
        ("w_adc_nat(32n, x, y, k)", rhs_w),
        ("{==}", rhs)]
    X0 = f"U32.is_lt({ua}, {X})"
    adc0 = "Word.adc(32n, x, y, False{}, False{})"
    cw0 = "wcarry(32n, x, y, False{})"
    L0 = add(f"U32.to_nat({ua})", f"cmul({X0}, {P32})")
    rhs0 = add(add("U32.to_nat(U32{x})", "U32.to_nat(U32{y})"), "b2n(False{})")
    steps0 = [
        (cong_l(f"U32.to_nat({ua})", f"Word.to_nat(32n, {adc0})", f"cmul({X0}, {P32})",
                cong("U32", "Nat", "U32.to_nat", ua, f"U32.add({X}, {Y})", f"u_add_eq({X}, {Y})")),
         add(f"Word.to_nat(32n, {adc0})", f"cmul({X0}, {P32})")),
        (cong_r(f"Word.to_nat(32n, {adc0})", f"cmul({X0}, {P32})", f"cmul({cw0}, {P32})",
                cong("Bool", "Nat", f"c => cmul(c, {P32})", X0, cw0, "u_c_limb0(x, y)")),
         add(f"Word.to_nat(32n, {adc0})", f"cmul({cw0}, {P32})")),
        (cong_r(f"Word.to_nat(32n, {adc0})", f"cmul({cw0}, {P32})", f"shn(32n, b2n({cw0}))",
                sym("Nat", f"shn(32n, b2n({cw0}))", f"cmul({cw0}, {P32})", f"shn_b2n(32n, {cw0})")),
         add(f"Word.to_nat(32n, {adc0})", f"shn(32n, b2n({cw0}))")),
        ("w_adc_nat(32n, x, y, False{})", add(add("Word.to_nat(32n, x)", "Word.to_nat(32n, y)"), "b2n(False{})")),
        ("{==}", rhs0)]
    return f'''
# a limb's value identity in the model's terms: to_nat(u_addc(u_add(x, y), k)) + carry_out 2^32 == x + y + k
def limb_id(+k: Bool, +x: Word(32n), +y: Word(32n)) -> {{{L} == {rhs} : Nat}}:
  {chain("Nat", L, steps)}

def limb0_id(+x: Word(32n), +y: Word(32n)) -> {{{L0} == {rhs0} : Nat}}:
  {chain("Nat", L0, steps0)}
'''


def _w_bridge(M="M.", WN="c3_wnat"):
    """N(w_add(a, b)) + carry_out 2^256 == N(a) + N(b), for a, b of the model's W (eight U32 limbs)."""
    A = [f"U32{{x{i}}}" for i in range(8)]
    B = [f"U32{{y{i}}}" for i in range(8)]
    t = [f"{M}u_add({A[i]}, {B[i]})" for i in range(8)]
    k = [None, f"U32.is_lt({t[0]}, {A[0]})"]
    s = [t[0]]
    for i in range(1, 8):
        s.append(f"{M}u_addc({t[i]}, {k[i]})")
        k.append(f"Bool.or(U32.is_lt({t[i]}, {A[i]}), U32.is_lt({s[i]}, {t[i]}))")
    k8 = k[8]

    def H(ls, j):
        h = f"U32.to_nat({ls[7]})"
        for i in range(6, j - 1, -1):
            h = add(f"U32.to_nat({ls[i]})", f"shn(32n, {h})")
        return h
    Q = {7: P32}
    for j in range(6, -1, -1):
        Q[j] = f"shn(32n, {Q[j + 1]})"
    P256 = Q[0]
    proof = f"limb_id({k[7]}, x7, y7)"
    for j in range(6, -1, -1):
        limb = f"limb_id({k[j]}, x{j}, y{j})" if j > 0 else "limb0_id(x0, y0)"
        kj = k[j] if j > 0 else "False{}"
        proof = (f"hs(U32.to_nat({s[j]}), {H(s, j + 1)}, U32.to_nat({A[j]}), {H(A, j + 1)}, U32.to_nat({B[j]}), {H(B, j + 1)}, "
                 f"{kj}, {k[j + 1]}, {k8}, {Q[j + 1]}, {limb}, {proof})")
    Wa = f"{M}W{{{', '.join(A)}}}"
    Wb = f"{M}W{{{', '.join(B)}}}"
    wsum = f"{WN}({M}w_add({Wa}, {Wb}))"
    carry = f"Bool.not({M}w_add_ok({Wa}, {Wb}))"
    L = add(wsum, f"cmul({carry}, {P256})")
    e_carry = chain("Bool", carry, [("{==}", f"Bool.not(Bool.not({k8}))"), (f"bool_nn({k8})", k8)])
    steps = [
        (cong_l(wsum, H(s, 0), f"cmul({carry}, {P256})", "{==}"), add(H(s, 0), f"cmul({carry}, {P256})")),
        (cong_r(H(s, 0), f"cmul({carry}, {P256})", f"cmul({k8}, {P256})",
                cong("Bool", "Nat", f"c => cmul(c, {P256})", carry, k8, e_carry)), add(H(s, 0), f"cmul({k8}, {P256})")),
        (proof, add(add(H(A, 0), H(B, 0)), "b2n(False{})")),
        ("{==}", add(add(H(A, 0), H(B, 0)), "0n")),
        (f"n_add_z({add(H(A, 0), H(B, 0))})", add(H(A, 0), H(B, 0))),
        ("{==}", add(f"{WN}({Wa})", f"{WN}({Wb})"))]
    pat_a = f"{M}W{{{', '.join(f'U32{{+x{i}}}' for i in range(8))}}}"
    pat_b = f"{M}W{{{', '.join(f'U32{{+y{i}}}' for i in range(8))}}}"
    return f'''
# the model's w_add as a natural number: N(a + b) + carry_out 2^256 == N(a) + N(b) (2^256 = (2^32)^8, kept as written)
def w_bridge(+a: {M}W, +b: {M}W) -> {{Nat.add({WN}({M}w_add(a, b)), cmul(Bool.not({M}w_add_ok(a, b)), {P256})) == Nat.add({WN}(a), {WN}(b)) : Nat}}:
  match a b:
    case {pat_a} {pat_b}:
      {chain("Nat", L, steps)}

# the wrap bound: N(a + b) <= N(a) + N(b)
def w_wrap(+a: {M}W, +b: {M}W) -> {{Nat.is_le({WN}({M}w_add(a, b)), Nat.add({WN}(a), {WN}(b))) == True{{}} : Bool}}:
  (%w_bridge(a, b) : {{Nat.is_le({WN}({M}w_add(a, b)), _) == True{{}} : Bool}}
  n_le_add({WN}({M}w_add(a, b)), cmul(Bool.not({M}w_add_ok(a, b)), {P256})))
'''


# ------------------------------------------------------------------------------- sums as trees (assoc/comm)
def _r(e):
    """A Nat sum tree rendered: an atom (text), ("+", x, y) or ("S", x) for 1n+x."""
    if isinstance(e, str):
        return e
    if e[0] == "S":
        return "1n+" + _r(e[1])
    return add(_r(e[1]), _r(e[2]))


def _canon(lst):
    return lst[0] if len(lst) == 1 else ("+", lst[0], _canon(lst[1:]))


def _tr(T, terms, proofs):
    """{terms[0] == terms[-1]} from proofs[i] : {terms[i] == terms[i+1]} ({==} steps between equal texts dropped)."""
    pts = [(p, t) for p, t in zip(proofs, terms[1:])]
    keep = []
    cur = terms[0]
    for p, t in pts:
        if p == "{==}" and t == cur:
            continue
        keep.append((p, t))
        cur = t
    if not keep:
        return "{==}"
    out = keep[-1][0]
    for i in range(len(keep) - 2, -1, -1):
        a = terms[0] if i == 0 else keep[i - 1][1]
        out = f"Equal.trans({T}, {a}, {keep[i][1]}, {keep[-1][1]}, {keep[i][0]}, {out})"
    # rebuild left to right
    res = None
    for i in range(len(keep) - 1, -1, -1):
        a = terms[0] if i == 0 else keep[i - 1][1]
        res = keep[i][0] if res is None else f"Equal.trans({T}, {a}, {keep[i][1]}, {keep[-1][1]}, {keep[i][0]}, {res})"
    return res


def _insert(a, L):
    if a <= L[0]:
        return [a] + L, "{==}"
    if len(L) == 1:
        return [L[0], a], f"n_add_comm({a}, {L[0]})"
    rest = _r(_canon(L[1:]))
    newR, p2 = _insert(a, L[1:])
    out = [L[0]] + newR
    q = "{==}" if p2 == "{==}" else cong_r(L[0], add(a, rest), _r(_canon(newR)), p2)
    return out, _tr("Nat", [add(a, _r(_canon(L))), add(L[0], add(a, rest)), _r(_canon(out))],
                   [f"n_swap3({a}, {L[0]}, {rest})", q])


def _merge(L1, L2):
    if len(L1) == 1:
        return _insert(L1[0], L2)
    a, R1 = L1[0], L1[1:]
    m, p2 = _merge(R1, L2)
    L, p3 = _insert(a, m)
    mid = add(a, add(_r(_canon(R1)), _r(_canon(L2))))
    q2 = "{==}" if p2 == "{==}" else cong_r(a, add(_r(_canon(R1)), _r(_canon(L2))), _r(_canon(m)), p2)
    return L, _tr("Nat", [add(_r(_canon(L1)), _r(_canon(L2))), mid, add(a, _r(_canon(m))), _r(_canon(L))],
                 [f"n_add_assoc({a}, {_r(_canon(R1))}, {_r(_canon(L2))})", q2, p3])


def _norm(e):
    if isinstance(e, str):
        return [e], "{==}"
    if e[0] == "S":
        L, p = _norm(("+", "1n", e[1]))
        return L, _tr("Nat", [_r(e), add("1n", _r(e[1])), _r(_canon(L))], ["{==}", p])
    x, y = e[1], e[2]
    Lx, px = _norm(x)
    Ly, py = _norm(y)
    cx, cy = _r(_canon(Lx)), _r(_canon(Ly))
    L, pm = _merge(Lx, Ly)
    pa = "{==}" if px == "{==}" else cong_l(_r(x), cx, _r(y), px)
    pb = "{==}" if py == "{==}" else cong_r(cx, _r(y), cy, py)
    return L, _tr("Nat", [add(_r(x), _r(y)), add(cx, _r(y)), add(cx, cy), _r(_canon(L))], [pa, pb, pm])


def ac_eq(e1, e2):
    """A proof of {_r(e1) == _r(e2) : Nat} for two sums of the same atoms (assoc/comm)."""
    L1, p1 = _norm(e1)
    L2, p2 = _norm(e2)
    if L1 != L2:
        raise ValueError(f"not AC-equal: {L1} {L2}")
    c = _r(_canon(L1))
    return _tr("Nat", [_r(e1), c, _r(e2)], [p1, "{==}" if p2 == "{==}" else sym("Nat", _r(e2), c, p2)])


def _P(e1, e2):
    return ("+", e1, e2)


def _w_order(M="M.", WN="c3_wnat"):
    """Words below 2^256, sums without a carry, and the step of a loop's key c0 + it (BUILD_PLAN I33, B6)."""
    S = lambda x: f"shn(32n, {x})"
    B = S("1n")
    Q = {7: B}
    for j in range(6, -1, -1):
        Q[j] = S(Q[j + 1])
    P256 = Q[0]
    W1 = f"{M}W{{1, 0, 0, 0, 0, 0, 0, 0}}"
    N = lambda w: f"{WN}({w})"
    out = []
    out.append(f'''
# x + (y + z) == y + (x + z)
def n_swap3(+x: Nat, +y: Nat, +z: Nat) -> {{Nat.add(x, Nat.add(y, z)) == Nat.add(y, Nat.add(x, z)) : Nat}}:
  {_tr("Nat", ["Nat.add(x, Nat.add(y, z))", "Nat.add(Nat.add(x, y), z)", "Nat.add(Nat.add(y, x), z)", "Nat.add(y, Nat.add(x, z))"],
       [sym("Nat", "Nat.add(Nat.add(x, y), z)", "Nat.add(x, Nat.add(y, z))", "n_add_assoc(x, y, z)"),
        cong_l("Nat.add(x, y)", "Nat.add(y, x)", "z", "n_add_comm(x, y)"), "n_add_assoc(y, x, z)"])}

# a limb's complement value and its bound: to_nat(u) + 1 + to_nat(not u) == 2^32
def unc(u: U32) -> Nat:
  match u:
    case U32{{d}}:
      Word.to_nat(32n, Word.not(32n, d))

def u_bnd(+u: U32) -> {{Nat.add(U32.to_nat(u), 1n+unc(u)) == {B} : Nat}}:
  match u:
    case U32{{+d}}:
      Equal.trans(Nat, Nat.add(U32.to_nat(U32{{d}}), 1n+unc(U32{{d}})), Nat.add(Word.to_nat(32n, d), 1n+Word.to_nat(32n, Word.not(32n, d))), {B}, {{==}}, w_bound(32n, d))
''')
    C = "unc(l7)"
    for j in range(6, -1, -1):
        C = add(f"unc(l{j})", S(C))
    a, ac_, rr, rc, T = "a", "ac", "r", "rc", "T"
    lhs = add(add(a, S(rr)), "1n+" + add(ac_, S(rc)))
    tree_l = _P(_P(a, S(rr)), ("S", _P(ac_, S(rc))))
    tree_x = _P(_P(a, ("S", ac_)), _P(S(rr), S(rc)))
    X = _r(tree_x)
    Y = add(B, add(S(rr), S(rc)))
    left = _tr("Nat", [lhs, X, Y], [ac_eq(tree_l, tree_x), cong_l(add(a, "1n+" + ac_), B, add(S(rr), S(rc)), "ea")])
    right = _tr("Nat", [S(T), S(add(rr, add("1n", rc))), add(S(rr), S(add("1n", rc))), add(S(rr), add(B, S(rc))), Y],
               [cong("Nat", "Nat", "z => shn(32n, z)", T, add(rr, add("1n", rc)), sym("Nat", add(rr, add("1n", rc)), T, "er")),
                f"shn_add(32n, {rr}, {add('1n', rc)})",
                cong_r(S(rr), S(add("1n", rc)), add(B, S(rc)), f"shn_add(32n, 1n, {rc})"),
                f"n_swap3({S(rr)}, {B}, {S(rc)})"])
    out.append(f'''
# the complement of a word, limb by limb, as a natural number
def wcn(w: {M}W) -> Nat:
  match w:
    case {M}W{{l0, l1, l2, l3, l4, l5, l6, l7}}:
      {C}

# one Horner step of the bound: a + 1 + ac == 2^32 and r + 1 + rc == T give (a + 2^32 r) + 1 + (ac + 2^32 rc) == 2^32 T
def hb_step(+a: Nat, +ac: Nat, +r: Nat, +rc: Nat, +T: Nat, ea: {{Nat.add(a, 1n+ac) == {B} : Nat}}, er: {{Nat.add(r, 1n+rc) == T : Nat}}) -> {{{lhs} == {S(T)} : Nat}}:
  {_tr("Nat", [lhs, Y, S(T)], [left, sym("Nat", S(T), Y, right)])}
''')
    H = {7: "U32.to_nat(l7)"}
    Cc = {7: "unc(l7)"}
    for j in range(6, -1, -1):
        H[j] = add(f"U32.to_nat(l{j})", S(H[j + 1]))
        Cc[j] = add(f"unc(l{j})", S(Cc[j + 1]))
    Wl = f"{M}W{{l0, l1, l2, l3, l4, l5, l6, l7}}"
    pf = "u_bnd(l7)"
    for j in range(6, -1, -1):
        pf = f"hb_step(U32.to_nat(l{j}), unc(l{j}), {H[j + 1]}, {Cc[j + 1]}, {Q[j + 1]}, u_bnd(l{j}), {pf})"
    out.append(f'''
# every word is below 2^256: N(w) + 1 + wcn(w) == 2^256
def wl_bound(+w: {M}W) -> {{Nat.add({N("w")}, 1n+wcn(w)) == {P256} : Nat}}:
  match w:
    case {M}W{{+l0, +l1, +l2, +l3, +l4, +l5, +l6, +l7}}:
      Equal.trans(Nat, Nat.add({N(Wl)}, 1n+wcn({Wl})), Nat.add({H[0]}, 1n+{Cc[0]}), {P256}, {{==}}, {pf})
''')
    # no wrap
    s, x, d, pw = "s", "x", "d", "pw"
    E1 = _tr("Nat", [add(s, add(x, "1n+d")), add(s, pw), x], [cong_r(s, add(x, "1n+d"), pw, "e"), "eb"])
    E2 = _tr("Nat", [add(x, add(s, "1n+d")), add(s, add(x, "1n+d")), x, add(x, "0n")],
            [f"n_swap3(x, s, 1n+d)", E1, sym("Nat", add(x, "0n"), x, "n_add_z(x)")])
    E3 = f"n_cancel_l(x, {add(s, '1n+d')}, 0n, {E2})"
    E4 = _tr("Nat", ["1n+" + add(s, d), add(s, "1n+d"), "0n"], [sym("Nat", add(s, "1n+d"), "1n+" + add(s, d), "n_add_s(s, d)"), E3])
    nwa = lambda a_, b_: add(N(a_), N(b_))
    out.append(f'''
# a sum with a carry of pw that stays below pw has no carry
def nw_c(c: Bool, +s: Nat, +x: Nat, +d: Nat, +pw: Nat, eb: {{Nat.add(s, cmul(c, pw)) == x : Nat}}, e: {{Nat.add(x, 1n+d) == pw : Nat}}) -> {{s == x : Nat}}:
  match c:
    case False{{}}:
      {_tr("Nat", ["s", add("s", "0n"), "x"], [sym("Nat", add("s", "0n"), "s", "n_add_z(s)"), "eb"])}
    case True{{}}:
      efq({{s == x : Nat}}, n_succ_nz({add(s, d)}, {E4}))

# no wrap: N(a) + N(b) + 1 + d == 2^256 gives N(a + b) == N(a) + N(b)
def nw(+a: {M}W, +b: {M}W, +d: Nat, e: {{Nat.add({nwa("a", "b")}, 1n+d) == {P256} : Nat}}) -> {{{N(f"{M}w_add(a, b)")} == {nwa("a", "b")} : Nat}}:
  nw_c(Bool.not({M}w_add_ok(a, b)), {N(f"{M}w_add(a, b)")}, {nwa("a", "b")}, d, {P256}, w_bridge(a, b), e)

def ok_c(c: Bool, +s: Nat, +x: Nat, +pw: Nat, eb: {{Nat.add(s, cmul(Bool.not(c), pw)) == x : Nat}}, ec: {{c == True{{}} : Bool}}) -> {{s == x : Nat}}:
  match c:
    case True{{}}:
      {_tr("Nat", ["s", add("s", "0n"), "x"], [sym("Nat", add("s", "0n"), "s", "n_add_z(s)"), "eb"])}
    case False{{}}:
      efq({{s == x : Nat}}, false_ne_true(ec))

# a checked sum: w_add_ok(a, b) gives N(a + b) == N(a) + N(b)
def okn(+a: {M}W, +b: {M}W, ok: {{{M}w_add_ok(a, b) == True{{}} : Bool}}) -> {{{N(f"{M}w_add(a, b)")} == {nwa("a", "b")} : Nat}}:
  ok_c({M}w_add_ok(a, b), {N(f"{M}w_add(a, b)")}, {nwa("a", "b")}, {P256}, w_bridge(a, b), ok)
''')
    # the loop key step
    K, K1, I1, Kp = f"{M}w_add(c0, it)", f"{M}w_add({M}w_add(c0, it), {W1})", f"{M}w_add(it, {W1})", f"{M}w_add(c0, {M}w_add(it, {W1}))"
    n0, ni, nk, n1, Cw = N("c0"), N("it"), N(K), N(W1), f"wcn({K1})"
    eK1 = f"okn({K}, {W1}, ok3)"
    B2 = _tr("Nat", [add(add(nk, n1), "1n+" + Cw), add(N(K1), "1n+" + Cw), P256],
            [cong_l(add(nk, n1), N(K1), "1n+" + Cw, sym("Nat", N(K1), add(nk, n1), eK1)), f"wl_bound({K1})"])
    B3 = _tr("Nat", [add(add(add(n0, ni), n1), "1n+" + Cw), add(add(nk, n1), "1n+" + Cw), P256],
            [cong_l(add(add(n0, ni), n1), add(nk, n1), "1n+" + Cw, cong_l(add(n0, ni), nk, n1, sym("Nat", nk, add(n0, ni), "J"))), B2])
    base = _P(_P(_P(n0, ni), n1), ("S", Cw))
    e1 = _tr("Nat", [add(add(ni, n1), "1n+" + add(n0, Cw)), _r(base), P256],
            [ac_eq(_P(_P(ni, n1), ("S", _P(n0, Cw))), base), B3])
    out.append(f'''
# the loop key step: J = N(c0 + it) == N(c0) + N(it) and the checked increment of c0 + it give it + 1 no wrap
def ks_i(+c0: {M}W, +it: {M}W, +J: {{{nk} == {add(n0, ni)} : Nat}}, +ok3: {{{M}w_add_ok({K}, {W1}) == True{{}} : Bool}}) -> {{{N(I1)} == {add(ni, n1)} : Nat}}:
  nw(it, {W1}, {add(n0, Cw)}, {e1})
''')
    e2 = _tr("Nat", [add(add(n0, N(I1)), "1n+" + Cw), add(add(n0, add(ni, n1)), "1n+" + Cw), _r(base), P256],
            [cong_l(add(n0, N(I1)), add(n0, add(ni, n1)), "1n+" + Cw, cong_r(n0, N(I1), add(ni, n1), "ks_i(c0, it, J, ok3)")),
             ac_eq(_P(_P(n0, _P(ni, n1)), ("S", Cw)), base), B3])
    out.append(f'''
# ... and J at it + 1: N(c0 + (it + 1)) == N(c0) + N(it + 1)
def ks_j(+c0: {M}W, +it: {M}W, +J: {{{nk} == {add(n0, ni)} : Nat}}, +ok3: {{{M}w_add_ok({K}, {W1}) == True{{}} : Bool}}) -> {{{N(Kp)} == {add(n0, N(I1))} : Nat}}:
  nw(c0, {I1}, {Cw}, {e2})

# ... and the key's value steps by one: N(c0 + (it + 1)) == N(c0 + it) + N(1)
def ks_s(+c0: {M}W, +it: {M}W, +J: {{{nk} == {add(n0, ni)} : Nat}}, +ok3: {{{M}w_add_ok({K}, {W1}) == True{{}} : Bool}}) -> {{{N(Kp)} == {add(nk, n1)} : Nat}}:
  {_tr("Nat", [N(Kp), add(n0, N(I1)), add(n0, add(ni, n1)), add(add(n0, ni), n1), add(nk, n1)],
       ["ks_j(c0, it, J, ok3)", cong_r(n0, N(I1), add(ni, n1), "ks_i(c0, it, J, ok3)"),
        sym("Nat", add(add(n0, ni), n1), add(n0, add(ni, n1)), f"n_add_assoc({n0}, {ni}, {n1})"),
        cong_l(add(n0, ni), nk, n1, sym("Nat", nk, add(n0, ni), "J"))])}

# J at the loop's start: N(c0 + 0) == N(c0) + N(0)
def ks_0(+c0: {M}W) -> {{{N(f"{M}w_add(c0, {M}w0())")} == {add(n0, N(f"{M}w0()"))} : Nat}}:
  nw(c0, {M}w0(), wcn(c0), {_tr("Nat", [add(add(n0, N(f"{M}w0()")), "1n+wcn(c0)"), add(n0, "1n+wcn(c0)"), P256],
                              [cong_l(add(n0, N(f"{M}w0()")), n0, "1n+wcn(c0)", f"n_add_z({n0})"), "wl_bound(c0)"])})

# Nat order: irreflexive, a successor above, a step up
def lt_irr(+a: Nat) -> {{Nat.is_lt(a, a) == False{{}} : Bool}}:
  (%Equal.sym(Cmp, Nat.cmp(a, a), EQ{{}}, n_cmp_refl(a)) : {{Cmp.is_lt(_) == False{{}} : Bool}}
  {{==}})

def lt_succ(+a: Nat) -> {{Nat.is_lt(a, Nat.add(a, 1n)) == True{{}} : Bool}}:
  n_lt_add(a, 0n)

def lt_up(a: Nat, b: Nat, h: {{Nat.is_lt(a, b) == True{{}} : Bool}}) -> {{Nat.is_lt(a, Nat.add(b, 1n)) == True{{}} : Bool}}:
  match a b:
    case 0n 0n:
      efq({{Nat.is_lt(0n, Nat.add(0n, 1n)) == True{{}} : Bool}}, false_ne_true(h))
    case 0n 1n+q:
      {{==}}
    case 1n+p 0n:
      efq({{Nat.is_lt(1n+p, Nat.add(0n, 1n)) == True{{}} : Bool}}, false_ne_true(h))
    case 1n+p 1n+q:
      lt_up(p, q, h)
''')
    return "\n".join(out)


def wnat_def(M="M."):
    limbs = [f"l{i}" for i in range(8)]
    body = f"U32.to_nat({limbs[7]})"
    for i in range(6, -1, -1):
        body = f"Nat.add(U32.to_nat({limbs[i]}), shn(32n, {body}))"
    return f"def c3_wnat(w: {M}W) -> Nat:\n  match w:\n    case {M}W{{{', '.join(limbs)}}}:\n      {body}\n"


_SHN_DEF = re.compile(r"(?ms)^def shn\(n: Nat, x: Nat\) -> Nat:\n.*?(?=^\S|\Z)")
_SHN_USE = re.compile(r"(?<![\w.])shn\(")


def library(M: str = "M.", shn: str = "shn", wnat: str = "c3_wnat") -> str:
    """The lemmas' text (after the core library of holon.disch.lemmas, whose u_refl and efq it uses). shn and wnat name
    the shift and the word's value the law file states (its statement helpers, e.g. Laws.c3_shn and Laws.c3_wnat): the
    library's own shn is then left out and every use of it is the law file's, so that the powers of two its lemmas
    write are the statement's terms, syntactically."""
    text = "\n".join([NAT, _u32_add(M), _natcmp(), _natcarry(), _u32_limbs(M), _w_generic(), _w_limbs(M),
                      _w_bridge(M, wnat), _w_order(M, wnat)])
    if shn != "shn":
        text = _SHN_USE.sub(shn + "(", _SHN_DEF.sub("", text))
    return text
