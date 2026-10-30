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

The power of two 2^32 is written shn(32n, 1n) at every use and passed to the generic lemmas as an opaque parameter: Bend's
Nat is unary, and the checker normalizes both sides of any equation it cannot match syntactically, so a comparison of two
different terms that contain a closed power of two would expand it. Nothing here names a target.
"""
from __future__ import annotations

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


def library(M: str = "M.") -> str:
    """The lemmas' text (after the core library of holon.disch.lemmas, whose u_refl and efq it uses)."""
    return "\n".join([NAT, _u32_add(M), _natcmp(), _natcarry(), _u32_limbs(M)])
