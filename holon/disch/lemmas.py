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
"""

LIBRARY = _COMMON + _RAW_STORE
LIBRARY_SK = _COMMON + _SK_STORE


def library(structural: bool) -> str:
    """The core lemmas for a model whose store is raw (LIBRARY) or structural (LIBRARY_SK, I68)."""
    return LIBRARY_SK if structural else LIBRARY
