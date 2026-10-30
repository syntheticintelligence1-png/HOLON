"""The core lemmas of the DISCH proofs (BUILD_PLAN I31: "time monotonicity, over the typed model's words (core lemmas,
proved, never assumed)"; Q14a: per-class generators, never hand-proved per law).

LIBRARY is fixed, generic text, emitted into every DISCH proof file that uses it and checked there by bend2 and BendTT
with the proof (nothing is assumed). It is stated over Base (Bool, Cmp, Word, U32) and over the typed model's prelude (W,
KW, HSt, w_eq, kw_get, kw_put, sload, sstore, ite), which every typed model shares (holon.sorts.prelude3); a model
whose prelude differs makes the file fail to check, never a lemma hold by assumption.

  efq, is_true, false_ne_true, true_ne_false    absurdity
  imp_g, and_l, and_r, and_intro                 implication and conjunction over Bool
  beq, weq, fin_same, fin_tf, fin_ft, cmp_weq    Word.cmp reflects bit-wise equality (induction on the width)
  weq_eq, u_refl, w_refl                         U32.is_eq and w_eq reflect equality
  kw_fr_c, kw_frame, st_frame                    the storage frame: a store at a slot whose key differs from k leaves
                                                 the word at k unchanged (induction on the slot list)
"""
from __future__ import annotations

_COMMON = r'''
# ---- core lemmas (holon.disch.lemmas: generic, proved here, never assumed)
def efq(-P: Type, x: Empty) -> P:
  match x:

def is_true(b: Bool) -> Type:
  match b:
    case True{}:
      Unit
    case False{}:
      Empty

def false_ne_true(e: {False{} == True{} : Bool}) -> Empty:
  (%Equal.sym(Bool, False{}, True{}, e) : is_true(_)
  Unit{})

def true_ne_false(e: {True{} == False{} : Bool}) -> Empty:
  (%e : is_true(_)
  Unit{})

def imp_g(p: Bool, +q: Bool, f: {p == True{} : Bool} -> {q == True{} : Bool}) -> {Bool.or(Bool.not(p), q) == True{} : Bool}:
  match p:
    case True{}:
      f({==})
    case False{}:
      {==}

def and_l(p: Bool, +q: Bool, e: {Bool.and(p, q) == True{} : Bool}) -> {p == True{} : Bool}:
  match p:
    case True{}:
      {==}
    case False{}:
      efq({False{} == True{} : Bool}, false_ne_true(e))

def and_r(p: Bool, +q: Bool, e: {Bool.and(p, q) == True{} : Bool}) -> {q == True{} : Bool}:
  match p:
    case True{}:
      e
    case False{}:
      efq({q == True{} : Bool}, false_ne_true(e))

def and_intro(p: Bool, +q: Bool, ep: {p == True{} : Bool}, eq: {q == True{} : Bool}) -> {Bool.and(p, q) == True{} : Bool}:
  match p:
    case True{}:
      eq
    case False{}:
      efq({Bool.and(False{}, q) == True{} : Bool}, false_ne_true(ep))

def beq(a: Bool, b: Bool) -> Bool:
  match a b:
    case True{} True{}:
      True{}
    case True{} False{}:
      False{}
    case False{} True{}:
      False{}
    case False{} False{}:
      True{}

def weq(n: Nat, x: Word(n), y: Word(n)) -> Bool:
  match n:
    case 0n:
      True{}
    case 1n+p:
      match x y:
        case WCon{a, xt} WCon{b, yt}:
          Bool.and(beq(a, b), weq(p, xt, yt))

def fin_same(a: Bool, r: Cmp) -> {Cmp.is_eq(Word.cmp.fin(a, a, r)) == Cmp.is_eq(r) : Bool}:
  match a r:
    case True{} LT{}:
      {==}
    case True{} EQ{}:
      {==}
    case True{} GT{}:
      {==}
    case False{} LT{}:
      {==}
    case False{} EQ{}:
      {==}
    case False{} GT{}:
      {==}

def fin_tf(r: Cmp) -> {Cmp.is_eq(Word.cmp.fin(True{}, False{}, r)) == False{} : Bool}:
  match r:
    case LT{}:
      {==}
    case EQ{}:
      {==}
    case GT{}:
      {==}

def fin_ft(r: Cmp) -> {Cmp.is_eq(Word.cmp.fin(False{}, True{}, r)) == False{} : Bool}:
  match r:
    case LT{}:
      {==}
    case EQ{}:
      {==}
    case GT{}:
      {==}

def cmp_weq(+n: Nat, x: Word(n), y: Word(n)) -> {Cmp.is_eq(Word.cmp(n, x, y)) == weq(n, x, y) : Bool}:
  match n:
    case 0n:
      {==}
    case 1n+p:
      match x y:
        case WCon{True{}, +xt} WCon{True{}, +yt}:
          Equal.trans(Bool, Cmp.is_eq(Word.cmp.fin(True{}, True{}, Word.cmp(p, xt, yt))), Cmp.is_eq(Word.cmp(p, xt, yt)), weq(p, xt, yt), fin_same(True{}, Word.cmp(p, xt, yt)), cmp_weq(p, xt, yt))
        case WCon{False{}, +xt} WCon{False{}, +yt}:
          Equal.trans(Bool, Cmp.is_eq(Word.cmp.fin(False{}, False{}, Word.cmp(p, xt, yt))), Cmp.is_eq(Word.cmp(p, xt, yt)), weq(p, xt, yt), fin_same(False{}, Word.cmp(p, xt, yt)), cmp_weq(p, xt, yt))
        case WCon{True{}, +xt} WCon{False{}, +yt}:
          fin_tf(Word.cmp(p, xt, yt))
        case WCon{False{}, +xt} WCon{True{}, +yt}:
          fin_ft(Word.cmp(p, xt, yt))

def weq_eq(+n: Nat, x: Word(n), y: Word(n), e: {weq(n, x, y) == True{} : Bool}) -> {x == y : Word(n)}:
  match n:
    case 0n:
      match x y:
        case WNil{} WNil{}:
          {==}
    case 1n+p:
      match x y:
        case WCon{True{}, +xt} WCon{True{}, +yt}:
          (%weq_eq(p, xt, yt, e) : {WCon{True{}, xt} == WCon{True{}, _} : Word(1n+p)}
          {==})
        case WCon{False{}, +xt} WCon{False{}, +yt}:
          (%weq_eq(p, xt, yt, e) : {WCon{False{}, xt} == WCon{False{}, _} : Word(1n+p)}
          {==})
        case WCon{True{}, +xt} WCon{False{}, +yt}:
          efq({WCon{True{}, xt} == WCon{False{}, yt} : Word(1n+p)}, false_ne_true(e))
        case WCon{False{}, +xt} WCon{True{}, +yt}:
          efq({WCon{False{}, xt} == WCon{True{}, yt} : Word(1n+p)}, false_ne_true(e))

def u_refl(a: U32, b: U32, e: {U32.is_eq(a, b) == True{} : Bool}) -> {a == b : U32}:
  match a b:
    case U32{+x} U32{+y}:
      (%weq_eq(32n, x, y, Equal.trans(Bool, weq(32n, x, y), Cmp.is_eq(Word.cmp(32n, x, y)), True{}, Equal.sym(Bool, Cmp.is_eq(Word.cmp(32n, x, y)), weq(32n, x, y), cmp_weq(32n, x, y)), e)) : {U32{x} == U32{_} : U32}
      {==})

def w_refl(a: M.W, b: M.W, +e: {M.w_eq(a, b) == True{} : Bool}) -> {a == b : M.W}:
  match a b:
    case M.W{+a0, +a1, +a2, +a3, +a4, +a5, +a6, +a7} M.W{+b0, +b1, +b2, +b3, +b4, +b5, +b6, +b7}:
      +c1 = Bool.and(U32.is_eq(a1, b1), Bool.and(U32.is_eq(a2, b2), Bool.and(U32.is_eq(a3, b3), Bool.and(U32.is_eq(a4, b4), Bool.and(U32.is_eq(a5, b5), Bool.and(U32.is_eq(a6, b6), U32.is_eq(a7, b7)))))))
      +c2 = Bool.and(U32.is_eq(a2, b2), Bool.and(U32.is_eq(a3, b3), Bool.and(U32.is_eq(a4, b4), Bool.and(U32.is_eq(a5, b5), Bool.and(U32.is_eq(a6, b6), U32.is_eq(a7, b7))))))
      +c3 = Bool.and(U32.is_eq(a3, b3), Bool.and(U32.is_eq(a4, b4), Bool.and(U32.is_eq(a5, b5), Bool.and(U32.is_eq(a6, b6), U32.is_eq(a7, b7)))))
      +c4 = Bool.and(U32.is_eq(a4, b4), Bool.and(U32.is_eq(a5, b5), Bool.and(U32.is_eq(a6, b6), U32.is_eq(a7, b7))))
      +c5 = Bool.and(U32.is_eq(a5, b5), Bool.and(U32.is_eq(a6, b6), U32.is_eq(a7, b7)))
      +c6 = Bool.and(U32.is_eq(a6, b6), U32.is_eq(a7, b7))
      +e1 = and_r(U32.is_eq(a0, b0), c1, e)
      +e2 = and_r(U32.is_eq(a1, b1), c2, e1)
      +e3 = and_r(U32.is_eq(a2, b2), c3, e2)
      +e4 = and_r(U32.is_eq(a3, b3), c4, e3)
      +e5 = and_r(U32.is_eq(a4, b4), c5, e4)
      +e6 = and_r(U32.is_eq(a5, b5), c6, e5)
      (%u_refl(a0, b0, and_l(U32.is_eq(a0, b0), c1, e)) : {M.W{a0, a1, a2, a3, a4, a5, a6, a7} == M.W{_, b1, b2, b3, b4, b5, b6, b7} : M.W}
      (%u_refl(a1, b1, and_l(U32.is_eq(a1, b1), c2, e1)) : {M.W{a0, a1, a2, a3, a4, a5, a6, a7} == M.W{a0, _, b2, b3, b4, b5, b6, b7} : M.W}
      (%u_refl(a2, b2, and_l(U32.is_eq(a2, b2), c3, e2)) : {M.W{a0, a1, a2, a3, a4, a5, a6, a7} == M.W{a0, a1, _, b3, b4, b5, b6, b7} : M.W}
      (%u_refl(a3, b3, and_l(U32.is_eq(a3, b3), c4, e3)) : {M.W{a0, a1, a2, a3, a4, a5, a6, a7} == M.W{a0, a1, a2, _, b4, b5, b6, b7} : M.W}
      (%u_refl(a4, b4, and_l(U32.is_eq(a4, b4), c5, e4)) : {M.W{a0, a1, a2, a3, a4, a5, a6, a7} == M.W{a0, a1, a2, a3, _, b5, b6, b7} : M.W}
      (%u_refl(a5, b5, and_l(U32.is_eq(a5, b5), c6, e5)) : {M.W{a0, a1, a2, a3, a4, a5, a6, a7} == M.W{a0, a1, a2, a3, a4, _, b6, b7} : M.W}
      (%u_refl(a6, b6, and_l(U32.is_eq(a6, b6), U32.is_eq(a7, b7), e6)) : {M.W{a0, a1, a2, a3, a4, a5, a6, a7} == M.W{a0, a1, a2, a3, a4, a5, _, b7} : M.W}
      (%u_refl(a7, b7, and_r(U32.is_eq(a6, b6), U32.is_eq(a7, b7), e6)) : {M.W{a0, a1, a2, a3, a4, a5, a6, a7} == M.W{a0, a1, a2, a3, a4, a5, a6, _} : M.W}
      {==}))))))))

'''

_RAW_STORE = r'''# the frame of one entry: when its key is k it is the entry read, and the store's key kw is not k
def kw_fr_c(c: Bool, +hk: M.W, +hv: M.W, +kw: M.W, +v: M.W, +d: Bool, +k: M.W, +y1: M.W, +y2: M.W, ec: {M.w_eq(hk, k) == c : Bool}, ne: {M.w_eq(k, kw) == False{} : Bool}, ih: {y1 == y2 : M.W}) -> {M.ite(M.W, c, M.ite(M.W, Bool.and(M.w_eq(hk, kw), Bool.not(d)), v, hv), y1) == M.ite(M.W, c, hv, y2) : M.W}:
  match c:
    case True{}:
      (%Equal.sym(M.W, hk, k, w_refl(hk, k, ec)) : {M.ite(M.W, Bool.and(M.w_eq(_, kw), Bool.not(d)), v, hv) == hv : M.W}
      (%Equal.sym(Bool, M.w_eq(k, kw), False{}, ne) : {M.ite(M.W, Bool.and(_, Bool.not(d)), v, hv) == hv : M.W}
      {==}))
    case False{}:
      ih

def kw_frame(xs: List<&2, M.KW>, +kw: M.W, +v: M.W, +d: Bool, +k: M.W, +ne1: {M.w_eq(kw, k) == False{} : Bool}, +ne2: {M.w_eq(k, kw) == False{} : Bool}) -> {M.kw_get(M.kw_put(xs, kw, v, d), k) == M.kw_get(xs, k) : M.W}:
  match xs:
    case Nil{}:
      match d:
        case True{}:
          {==}
        case False{}:
          (%Equal.sym(Bool, M.w_eq(kw, k), False{}, ne1) : {M.ite(M.W, _, v, M.w0()) == M.w0() : M.W}
          {==})
    case Con{h, +t}:
      match h:
        case M.KW{+hk, +hv}:
          kw_fr_c(M.w_eq(hk, k), hk, hv, kw, v, d, k, M.kw_get(M.kw_put(t, kw, v, Bool.or(d, M.w_eq(hk, kw))), k), M.kw_get(t, k), {==}, ne2, kw_frame(t, kw, v, Bool.or(d, M.w_eq(hk, kw)), k, ne1, ne2))

# a store at kw leaves the word at k unchanged (kw and k are different keys)
def st_frame(s: M.HSt, +kw: M.W, +v: M.W, +k: M.W, ne1: {M.w_eq(kw, k) == False{} : Bool}, ne2: {M.w_eq(k, kw) == False{} : Bool}) -> {M.sload(M.sstore(s, kw, v), k) == M.sload(s, k) : M.W}:
  match s:
    case M.HSt{sl}:
      kw_frame(sl, kw, v, False{}, k, ne1, ne2)
'''

# I68 (the Q21 fix): the storage frame over a structural store (holon.sorts.prelude3.PRELUDE_SK). The same names as the
# raw store's lemmas, so a route states a frame the same way over either model; sk_eq reflects key equality component by
# component (the base, the offset, each step's offset and key word), by w_refl.
_SK_STORE = r"""
def sp_refl(a: M.SP, b: M.SP, +e: {M.sp_eq(a, b) == True{} : Bool}) -> {a == b : M.SP}:
  match a b:
    case M.SP_m{+ak, +ao} M.SP_m{+bk, +bo}:
      (%w_refl(ao, bo, and_l(M.w_eq(ao, bo), M.w_eq(ak, bk), e)) : {M.SP_m{ak, ao} == M.SP_m{bk, _} : M.SP}
      (%w_refl(ak, bk, and_r(M.w_eq(ao, bo), M.w_eq(ak, bk), e)) : {M.SP_m{ak, ao} == M.SP_m{_, ao} : M.SP}
      {==}))

def sps_refl(a: List<&2, M.SP>, b: List<&2, M.SP>, +e: {M.sps_eq(a, b) == True{} : Bool}) -> {a == b : List<&2, M.SP>}:
  match a b:
    case Nil{} Nil{}:
      {==}
    case Nil{} Con{y, ys}:
      efq({Nil{} == Con{y, ys} : List<&2, M.SP>}, false_ne_true(e))
    case Con{x, xs} Nil{}:
      efq({Con{x, xs} == Nil{} : List<&2, M.SP>}, false_ne_true(e))
    case Con{+x, +xs} Con{+y, +ys}:
      (%sp_refl(x, y, and_l(M.sp_eq(x, y), M.sps_eq(xs, ys), e)) : {Con{x, xs} == Con{_, ys} : List<&2, M.SP>}
      (%sps_refl(xs, ys, and_r(M.sp_eq(x, y), M.sps_eq(xs, ys), e)) : {Con{x, xs} == Con{x, _} : List<&2, M.SP>}
      {==}))

def sk_refl(a: M.SK, b: M.SK, +e: {M.sk_eq(a, b) == True{} : Bool}) -> {a == b : M.SK}:
  match a b:
    case M.SK{+ab, +ao, +ap} M.SK{+bb, +bo, +bp}:
      +r = and_r(M.w_eq(ab, bb), Bool.and(M.w_eq(ao, bo), M.sps_eq(ap, bp)), e)
      (%w_refl(ab, bb, and_l(M.w_eq(ab, bb), Bool.and(M.w_eq(ao, bo), M.sps_eq(ap, bp)), e)) : {M.SK{ab, ao, ap} == M.SK{_, bo, bp} : M.SK}
      (%w_refl(ao, bo, and_l(M.w_eq(ao, bo), M.sps_eq(ap, bp), r)) : {M.SK{ab, ao, ap} == M.SK{ab, _, bp} : M.SK}
      (%sps_refl(ap, bp, and_r(M.w_eq(ao, bo), M.sps_eq(ap, bp), r)) : {M.SK{ab, ao, ap} == M.SK{ab, ao, _} : M.SK}
      {==})))

# the frame of one entry: when its key is k it is the entry read, and the store's key kw is not k
def kv_fr_c(c: Bool, +hk: M.SK, +hv: M.W, +kw: M.SK, +v: M.W, +d: Bool, +k: M.SK, +y1: M.W, +y2: M.W, ec: {M.sk_eq(hk, k) == c : Bool}, ne: {M.sk_eq(k, kw) == False{} : Bool}, ih: {y1 == y2 : M.W}) -> {M.ite(M.W, c, M.ite(M.W, Bool.and(M.sk_eq(hk, kw), Bool.not(d)), v, hv), y1) == M.ite(M.W, c, hv, y2) : M.W}:
  match c:
    case True{}:
      (%Equal.sym(M.SK, hk, k, sk_refl(hk, k, ec)) : {M.ite(M.W, Bool.and(M.sk_eq(_, kw), Bool.not(d)), v, hv) == hv : M.W}
      (%Equal.sym(Bool, M.sk_eq(k, kw), False{}, ne) : {M.ite(M.W, Bool.and(_, Bool.not(d)), v, hv) == hv : M.W}
      {==}))
    case False{}:
      ih

def kv_frame(xs: List<&2, M.KV>, +kw: M.SK, +v: M.W, +d: Bool, +k: M.SK, +ne1: {M.sk_eq(kw, k) == False{} : Bool}, +ne2: {M.sk_eq(k, kw) == False{} : Bool}) -> {M.kv_get(M.kv_put(xs, kw, v, d), k) == M.kv_get(xs, k) : M.W}:
  match xs:
    case Nil{}:
      match d:
        case True{}:
          {==}
        case False{}:
          (%Equal.sym(Bool, M.sk_eq(kw, k), False{}, ne1) : {M.ite(M.W, _, v, M.w0()) == M.w0() : M.W}
          {==})
    case Con{h, +t}:
      match h:
        case M.KV{+hk, +hv}:
          kv_fr_c(M.sk_eq(hk, k), hk, hv, kw, v, d, k, M.kv_get(M.kv_put(t, kw, v, Bool.or(d, M.sk_eq(hk, kw))), k), M.kv_get(t, k), {==}, ne2, kv_frame(t, kw, v, Bool.or(d, M.sk_eq(hk, kw)), k, ne1, ne2))

# a store at key kw leaves the word at key k unchanged (sk_eq tells the two keys apart both ways)
def st_frame(s: M.HSt, +kw: M.SK, +v: M.W, +k: M.SK, ne1: {M.sk_eq(kw, k) == False{} : Bool}, ne2: {M.sk_eq(k, kw) == False{} : Bool}) -> {M.sload(M.sstore(s, kw, v), k) == M.sload(s, k) : M.W}:
  match s:
    case M.HSt{sl}:
      kv_frame(sl, kw, v, False{}, k, ne1, ne2)

# the key split: two keys differ when the first of their words compared differently does (the comparisons before it
# evaluate to True); the symmetry of a word disequality, w_ne_sym, follows w_eq_self (holon.disch.order)
def sp_ne_o(+ak: M.W, +ao: M.W, +bk: M.W, +bo: M.W, e: {M.w_eq(ao, bo) == False{} : Bool}) -> {M.sp_eq(M.SP_m{ak, ao}, M.SP_m{bk, bo}) == False{} : Bool}:
  (%Equal.sym(Bool, M.w_eq(ao, bo), False{}, e) : {Bool.and(_, M.w_eq(ak, bk)) == False{} : Bool}
  {==})

def sp_ne_k(+ak: M.W, +ao: M.W, +bk: M.W, +bo: M.W, eo: {M.w_eq(ao, bo) == True{} : Bool}, e: {M.w_eq(ak, bk) == False{} : Bool}) -> {M.sp_eq(M.SP_m{ak, ao}, M.SP_m{bk, bo}) == False{} : Bool}:
  (%Equal.sym(Bool, M.w_eq(ao, bo), True{}, eo) : {Bool.and(_, M.w_eq(ak, bk)) == False{} : Bool}
  (%Equal.sym(Bool, M.w_eq(ak, bk), False{}, e) : {Bool.and(True{}, _) == False{} : Bool}
  {==}))

def sps_ne_h(+x: M.SP, +xs: List<&2, M.SP>, +y: M.SP, +ys: List<&2, M.SP>, e: {M.sp_eq(x, y) == False{} : Bool}) -> {M.sps_eq(Con{x, xs}, Con{y, ys}) == False{} : Bool}:
  (%Equal.sym(Bool, M.sp_eq(x, y), False{}, e) : {Bool.and(_, M.sps_eq(xs, ys)) == False{} : Bool}
  {==})

def sps_ne_t(+x: M.SP, +xs: List<&2, M.SP>, +y: M.SP, +ys: List<&2, M.SP>, eh: {M.sp_eq(x, y) == True{} : Bool}, e: {M.sps_eq(xs, ys) == False{} : Bool}) -> {M.sps_eq(Con{x, xs}, Con{y, ys}) == False{} : Bool}:
  (%Equal.sym(Bool, M.sp_eq(x, y), True{}, eh) : {Bool.and(_, M.sps_eq(xs, ys)) == False{} : Bool}
  (%Equal.sym(Bool, M.sps_eq(xs, ys), False{}, e) : {Bool.and(True{}, _) == False{} : Bool}
  {==}))

def sk_ne_b(+ab: M.W, +ao: M.W, +ap: List<&2, M.SP>, +bb: M.W, +bo: M.W, +bp: List<&2, M.SP>, e: {M.w_eq(ab, bb) == False{} : Bool}) -> {M.sk_eq(M.SK{ab, ao, ap}, M.SK{bb, bo, bp}) == False{} : Bool}:
  (%Equal.sym(Bool, M.w_eq(ab, bb), False{}, e) : {Bool.and(_, Bool.and(M.w_eq(ao, bo), M.sps_eq(ap, bp))) == False{} : Bool}
  {==})

def sk_ne_o(+ab: M.W, +ao: M.W, +ap: List<&2, M.SP>, +bb: M.W, +bo: M.W, +bp: List<&2, M.SP>, eb: {M.w_eq(ab, bb) == True{} : Bool}, e: {M.w_eq(ao, bo) == False{} : Bool}) -> {M.sk_eq(M.SK{ab, ao, ap}, M.SK{bb, bo, bp}) == False{} : Bool}:
  (%Equal.sym(Bool, M.w_eq(ab, bb), True{}, eb) : {Bool.and(_, Bool.and(M.w_eq(ao, bo), M.sps_eq(ap, bp))) == False{} : Bool}
  (%Equal.sym(Bool, M.w_eq(ao, bo), False{}, e) : {Bool.and(True{}, Bool.and(_, M.sps_eq(ap, bp))) == False{} : Bool}
  {==}))

def sk_ne_p(+ab: M.W, +ao: M.W, +ap: List<&2, M.SP>, +bb: M.W, +bo: M.W, +bp: List<&2, M.SP>, eb: {M.w_eq(ab, bb) == True{} : Bool}, eo: {M.w_eq(ao, bo) == True{} : Bool}, e: {M.sps_eq(ap, bp) == False{} : Bool}) -> {M.sk_eq(M.SK{ab, ao, ap}, M.SK{bb, bo, bp}) == False{} : Bool}:
  (%Equal.sym(Bool, M.w_eq(ab, bb), True{}, eb) : {Bool.and(_, Bool.and(M.w_eq(ao, bo), M.sps_eq(ap, bp))) == False{} : Bool}
  (%Equal.sym(Bool, M.w_eq(ao, bo), True{}, eo) : {Bool.and(True{}, Bool.and(_, M.sps_eq(ap, bp))) == False{} : Bool}
  (%Equal.sym(Bool, M.sps_eq(ap, bp), False{}, e) : {Bool.and(True{}, Bool.and(True{}, _)) == False{} : Bool}
  {==})))
"""

def _bitfield(P: str = "M.") -> str:
    """(I68, rule S9's bit-field lemmas) a masked write of a packed slot, x & m | v, reads back its field and keeps the
    others: (x & m | v) & k == v & k when m & k == 0 (w_bf_read), and == x & k when m & k == k and v & k == 0
    (w_bf_keep). Bit by bit (bit_read, bit_keep: by cases), by induction on a Word's length (wb_read, wb_keep), per
    U32 (ub_read, ub_keep) and per limb of a 256-bit word; the masks and the written value are literals at every use,
    so the hypotheses are {==}."""
    W = f"{P}W"
    L = range(8)
    out = []
    out.append("""# (I68: the bit-field lemmas) a masked write of a packed slot reads back its field and keeps the others:
# (x & m | v) & k == v & k when m & k == 0, and == x & k when m & k == k and v & k == 0; bit by bit, then by induction
# on the word's length, then per limb of a 256-bit word
def wz(n: Nat) -> Word(n):
  match n:
    case 0n:
      WNil{}
    case 1n+p:
      WCon{False{}, wz(p)}

def whd(+p: Nat, w: Word(1n+p)) -> Bool:
  match w:
    case WCon{b, t}:
      b

def wtl(+p: Nat, w: Word(1n+p)) -> Word(p):
  match w:
    case WCon{b, t}:
      t

def udata(u: U32) -> Word(32n):
  match u:
    case U32{d}:
      d
""")
    # bit lemmas
    rows_r, rows_k = [], []
    for x in (True, False):
        for m in (True, False):
            for v in (True, False):
                for k in (True, False):
                    pat = " ".join("True{}" if b else "False{}" for b in (x, m, v, k))
                    if m and k:
                        rows_r.append(f"    case {pat}:\n      efq({{Bool.and(Bool.or(Bool.and({pat.split()[0]}, True{{}}), {pat.split()[2]}), True{{}}) == Bool.and({pat.split()[2]}, True{{}}) : Bool}}, true_ne_false(h))\n")
                    else:
                        rows_r.append(f"    case {pat}:\n      {{==}}\n")
                    goal_k = f"{{Bool.and(Bool.or(Bool.and({pat.split()[0]}, {pat.split()[1]}), {pat.split()[2]}), {pat.split()[3]}) == Bool.and({pat.split()[0]}, {pat.split()[3]}) : Bool}}"
                    if k and not m:
                        rows_k.append(f"    case {pat}:\n      efq({goal_k}, false_ne_true(h1))\n")
                    elif k and v:
                        rows_k.append(f"    case {pat}:\n      efq({goal_k}, true_ne_false(h2))\n")
                    else:
                        rows_k.append(f"    case {pat}:\n      {{==}}\n")
    out.append("def bit_read(x: Bool, m: Bool, v: Bool, k: Bool, h: {Bool.and(m, k) == False{} : Bool}) -> "
               "{Bool.and(Bool.or(Bool.and(x, m), v), k) == Bool.and(v, k) : Bool}:\n  match x m v k:\n" + "".join(rows_r))
    out.append("def bit_keep(x: Bool, m: Bool, v: Bool, k: Bool, h1: {Bool.and(m, k) == k : Bool}, h2: {Bool.and(v, k) == "
               "False{} : Bool}) -> {Bool.and(Bool.or(Bool.and(x, m), v), k) == Bool.and(x, k) : Bool}:\n"
               "  match x m v k:\n" + "".join(rows_k))
    # word lemmas by induction
    hd = "WCon{Bool.and(mb, kb), Word.and(p, mt, kt)}"
    out.append(
        "def wb_read(n: Nat, x: Word(n), m: Word(n), v: Word(n), k: Word(n), +h: {Word.and(n, m, k) == wz(n) : Word(n)}) -> "
        "{Word.and(n, Word.or(n, Word.and(n, x, m), v), k) == Word.and(n, v, k) : Word(n)}:\n"
        "  match n:\n    case 0n:\n      {==}\n    case 1n+p:\n      match x m v k:\n"
        "        case WCon{+xb, +xt} WCon{+mb, +mt} WCon{+vb, +vt} WCon{+kb, +kt}:\n"
        f"          (%Equal.sym(Bool, Bool.and(Bool.or(Bool.and(xb, mb), vb), kb), Bool.and(vb, kb), bit_read(xb, mb, vb, kb, "
        f"Equal.cong(Word(1n+p), Bool, w => whd(p, w), {hd}, WCon{{False{{}}, wz(p)}}, h))) : "
        "{WCon{_, Word.and(p, Word.or(p, Word.and(p, xt, mt), vt), kt)} == WCon{Bool.and(vb, kb), Word.and(p, vt, kt)} : Word(1n+p)}\n"
        f"          (%Equal.sym(Word(p), Word.and(p, Word.or(p, Word.and(p, xt, mt), vt), kt), Word.and(p, vt, kt), wb_read(p, xt, mt, vt, kt, "
        f"Equal.cong(Word(1n+p), Word(p), w => wtl(p, w), {hd}, WCon{{False{{}}, wz(p)}}, h))) : "
        "{WCon{Bool.and(vb, kb), _} == WCon{Bool.and(vb, kb), Word.and(p, vt, kt)} : Word(1n+p)}\n"
        "          {==}))\n")
    out.append(
        "def wb_keep(n: Nat, x: Word(n), m: Word(n), v: Word(n), k: Word(n), +h1: {Word.and(n, m, k) == k : Word(n)}, "
        "+h2: {Word.and(n, v, k) == wz(n) : Word(n)}) -> "
        "{Word.and(n, Word.or(n, Word.and(n, x, m), v), k) == Word.and(n, x, k) : Word(n)}:\n"
        "  match n:\n    case 0n:\n      {==}\n    case 1n+p:\n      match x m v k:\n"
        "        case WCon{+xb, +xt} WCon{+mb, +mt} WCon{+vb, +vt} WCon{+kb, +kt}:\n"
        f"          (%Equal.sym(Bool, Bool.and(Bool.or(Bool.and(xb, mb), vb), kb), Bool.and(xb, kb), bit_keep(xb, mb, vb, kb, "
        f"Equal.cong(Word(1n+p), Bool, w => whd(p, w), {hd}, WCon{{kb, kt}}, h1), "
        f"Equal.cong(Word(1n+p), Bool, w => whd(p, w), WCon{{Bool.and(vb, kb), Word.and(p, vt, kt)}}, WCon{{False{{}}, wz(p)}}, h2))) : "
        "{WCon{_, Word.and(p, Word.or(p, Word.and(p, xt, mt), vt), kt)} == WCon{Bool.and(xb, kb), Word.and(p, xt, kt)} : Word(1n+p)}\n"
        f"          (%Equal.sym(Word(p), Word.and(p, Word.or(p, Word.and(p, xt, mt), vt), kt), Word.and(p, xt, kt), wb_keep(p, xt, mt, vt, kt, "
        f"Equal.cong(Word(1n+p), Word(p), w => wtl(p, w), {hd}, WCon{{kb, kt}}, h1), "
        f"Equal.cong(Word(1n+p), Word(p), w => wtl(p, w), WCon{{Bool.and(vb, kb), Word.and(p, vt, kt)}}, WCon{{False{{}}, wz(p)}}, h2))) : "
        "{WCon{Bool.and(xb, kb), _} == WCon{Bool.and(xb, kb), Word.and(p, xt, kt)} : Word(1n+p)}\n"
        "          {==}))\n")
    # U32 lemmas
    out.append(
        "def ub_read(x: U32, m: U32, v: U32, k: U32, h: {U32.and(m, k) == 0 : U32}) -> "
        "{U32.and(U32.or(U32.and(x, m), v), k) == U32.and(v, k) : U32}:\n  match x m v k:\n"
        "    case U32{+xw} U32{+mw} U32{+vw} U32{+kw}:\n"
        "      (%Equal.sym(Word(32n), Word.and(32n, Word.or(32n, Word.and(32n, xw, mw), vw), kw), Word.and(32n, vw, kw), "
        "wb_read(32n, xw, mw, vw, kw, Equal.cong(U32, Word(32n), u => udata(u), U32{Word.and(32n, mw, kw)}, 0, h))) : "
        "{U32{_} == U32{Word.and(32n, vw, kw)} : U32}\n      {==})\n")
    out.append(
        "def ub_keep(x: U32, m: U32, v: U32, k: U32, h1: {U32.and(m, k) == k : U32}, h2: {U32.and(v, k) == 0 : U32}) -> "
        "{U32.and(U32.or(U32.and(x, m), v), k) == U32.and(x, k) : U32}:\n  match x m v k:\n"
        "    case U32{+xw} U32{+mw} U32{+vw} U32{+kw}:\n"
        "      (%Equal.sym(Word(32n), Word.and(32n, Word.or(32n, Word.and(32n, xw, mw), vw), kw), Word.and(32n, xw, kw), "
        "wb_keep(32n, xw, mw, vw, kw, Equal.cong(U32, Word(32n), u => udata(u), U32{Word.and(32n, mw, kw)}, U32{kw}, h1), "
        "Equal.cong(U32, Word(32n), u => udata(u), U32{Word.and(32n, vw, kw)}, 0, h2))) : "
        "{U32{_} == U32{Word.and(32n, xw, kw)} : U32}\n      {==})\n")
    # limb getters and the 256-bit lemmas
    for i in L:
        lims = ", ".join(f"a{j}" for j in L)
        out.append(f"def wl{i}(w: {W}) -> U32:\n  match w:\n    case {W}{{{lims}}}:\n      a{i}\n")

    def limbs(pre):
        return ", ".join(f"+{pre}{j}" for j in L)
    for kind in ("read", "keep"):
        lhs = [f"U32.and(U32.or(U32.and(x{j}, m{j}), v{j}), k{j})" for j in L]
        rhs = [f"U32.and(v{j}, k{j})" if kind == "read" else f"U32.and(x{j}, k{j})" for j in L]
        mk = f"{W}{{{', '.join(f'U32.and(m{j}, k{j})' for j in L)}}}"
        vk = f"{W}{{{', '.join(f'U32.and(v{j}, k{j})' for j in L)}}}"
        kk = f"{W}{{{', '.join(f'k{j}' for j in L)}}}"
        body = "{==}"
        for j in range(7, -1, -1):
            hole = rhs[:j] + ["_"] + lhs[j + 1:]
            if kind == "read":
                pf = f"ub_read(x{j}, m{j}, v{j}, k{j}, Equal.cong({W}, U32, w => wl{j}(w), {mk}, {P}w0(), h))"
            else:
                pf = (f"ub_keep(x{j}, m{j}, v{j}, k{j}, Equal.cong({W}, U32, w => wl{j}(w), {mk}, {kk}, h1), "
                      f"Equal.cong({W}, U32, w => wl{j}(w), {vk}, {P}w0(), h2))")
            body = (f"(%Equal.sym(U32, {lhs[j]}, {rhs[j]}, {pf}) : {{{W}{{{', '.join(hole)}}} == {W}{{{', '.join(rhs)}}} : {W}}}\n"
                    f"      {body})")
        hyps = (f"+h: {{{P}w_and(m, k) == {P}w0() : {W}}}" if kind == "read" else
                f"+h1: {{{P}w_and(m, k) == k : {W}}}, +h2: {{{P}w_and(v, k) == {P}w0() : {W}}}")
        res = f"{P}w_and(v, k)" if kind == "read" else f"{P}w_and(x, k)"
        out.append(f"def w_bf_{kind}(x: {W}, m: {W}, v: {W}, k: {W}, {hyps}) -> {{{P}w_and({P}w_or({P}w_and(x, m), v), k) == "
                   f"{res} : {W}}}:\n  match x m v k:\n    case {W}{{{limbs('x')}}} {W}{{{limbs('m')}}} {W}{{{limbs('v')}}} "
                   f"{W}{{{limbs('k')}}}:\n      {body}\n")
    return "\n".join(out)



LIBRARY = _COMMON + _RAW_STORE
LIBRARY_SK = _COMMON + _SK_STORE + "\n" + _bitfield()


def library(structural: bool) -> str:
    """The core lemmas for a model whose store is raw (LIBRARY) or structural (LIBRARY_SK, I68)."""
    return LIBRARY_SK if structural else LIBRARY
