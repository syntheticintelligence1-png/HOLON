"""Lemmas about the M3 prelude's own definitions (F32; docs/HUMAN_ANSWERS.md Q31 (d)).

holon.sorts.prelude3 is fixed text that names no target, and every M3 model carries it verbatim. A30 rewrote its hash
table lookup (h_get: the table's keys and the looked-up key reversed, then filtered byte by byte, h_filt over h_step /
h_one / h_cons, the answer read by h_ends / h_end1). These are the list lemmas a proof that it is still a first-match
lookup needs, each stated for all lists and all values of its parameters, about the prelude's definitions only (never
about a pair of models, never about one law): reversal is an involution (lp_rev_rev), the byte-string equality b_eq is
reflexive, sound (b_eq(x, y) == True gives x == y) and blind to reversal (lp_beq_rev), and the filter over a table
with a first entry answers that entry's value when its key matches, else the rest's answer (lp_filt_con, lp_filt_nil).

The proofs of lp_rev_rev, lp_beq_refl, lp_filt_nil and lp_filt_con were produced once by holon.gen.eqprove from the
statements and are kept as fixed text; lp_beq_sound and lp_beq_rev are written out (reflection, and a case split
whose two contradictory cases are closed by rewriting). The kernel checks all of it (bend2 and BendTT, tests_m3).

The text is used only for a model whose prelude definitions these lemmas mention, and every definition they reach, are
the prelude's own text (applies); the model's names are reached through the pair module's alias P, as every lemma of
holon.gen.equivalence does. The library depends on holon.gen.eqlib (emitted before it).
"""
from __future__ import annotations

import re

# the prelude definitions the statements mention
NAMES = ["b_rev", "b_eq", "h_filt", "h_step", "h_one", "h_cons", "h_ends", "h_end1", "ite", "w0", "W", "HKB"]

TEXT = '''\
# ---- holon.sorts.prelude3_lemmas: lemmas about the M3 prelude's definitions (fixed text)
def lp_rev_rev(+x: List<&2, U32>, +a: List<&2, U32>) -> {P.b_rev(P.b_rev(x, a), Nil{}) == P.b_rev(a, x) : List<&2, U32>}:
  match x:
    case Nil{}:
      {==}
    case Con{+v_1, +v_2}:
      match a:
        case Nil{}:
          %Equal.sym(List<&2, U32>, P.b_rev(P.b_rev(v_2, Con{v_1, Nil{}}), Nil{}), P.b_rev(Con{v_1, Nil{}}, v_2), lp_rev_rev(v_2, Con{v_1, Nil{}})) : {_ == Con{v_1, v_2} : List<&2, U32>}
          {==}
        case Con{+v_3, +v_4}:
          %Equal.sym(List<&2, U32>, P.b_rev(P.b_rev(v_2, Con{v_1, Con{v_3, v_4}}), Nil{}), P.b_rev(Con{v_1, Con{v_3, v_4}}, v_2), lp_rev_rev(v_2, Con{v_1, Con{v_3, v_4}})) : {_ == P.b_rev(v_4, Con{v_3, Con{v_1, v_2}}) : List<&2, U32>}
          {==}


def lp_beq_refl(+x: List<&2, U32>) -> {P.b_eq(x, x) == True{} : Bool}:
  match x:
    case Nil{}:
      {==}
    case Con{+v_1, +v_2}:
      %Equal.sym(Bool, P.b_eq(v_2, v_2), True{}, lp_beq_refl(v_2)) : {Bool.and(Cmp.is_eq(U32.cmp(v_1, v_1)), _) == True{} : Bool}
      %Equal.sym(Bool, Cmp.is_eq(U32.cmp(v_1, v_1)), True{}, lbu_eq_self(v_1)) : {Bool.and(_, True{}) == True{} : Bool}
      {==}


def lp_filt_nil(+rk: List<&2, U32>) -> {P.h_filt(rk, Nil{}) == P.w0() : P.W}:
  match rk:
    case Nil{}:
      {==}
    case Con{+v_1, +v_2}:
      %Equal.sym(P.W, P.h_filt(v_2, Nil{}), P.w0(), lp_filt_nil(v_2)) : {_ == P.W{0, 0, 0, 0, 0, 0, 0, 0} : P.W}
      {==}

def lp_filt_con__h1496(+v_2: List<&2, U32>, +v_1132: U32, +v_1: U32, +v_1133: List<&2, U32>, +cv: P.W, +cs: List<&2, P.HKB>, +ih_1499: {P.h_filt(v_2, Con{P.HKB{v_1133, cv}, P.h_step(v_1, cs)}) == P.ite(P.W, P.b_eq(v_1133, v_2), cv, P.h_filt(v_2, P.h_step(v_1, cs))) : P.W}, c_1497: Bool, +e_1498: {Cmp.is_eq(U32.cmp(v_1132, v_1)) == c_1497 : Bool}) -> {P.h_filt(v_2, P.h_cons(Cmp.is_eq(U32.cmp(v_1132, v_1)), v_1133, cv, P.h_step(v_1, cs))) == P.ite(P.W, Bool.and(Cmp.is_eq(U32.cmp(v_1132, v_1)), P.b_eq(v_1133, v_2)), cv, P.h_filt(v_2, P.h_step(v_1, cs))) : P.W}:
  match c_1497:
    case True{}:
      %Equal.sym(Bool, Cmp.is_eq(U32.cmp(v_1132, v_1)), True{}, e_1498) : {P.h_filt(v_2, P.h_cons(_, v_1133, cv, P.h_step(v_1, cs))) == P.ite(P.W, Bool.and(_, P.b_eq(v_1133, v_2)), cv, P.h_filt(v_2, P.h_step(v_1, cs))) : P.W}
      %Equal.sym(P.W, P.h_filt(v_2, Con{P.HKB{v_1133, cv}, P.h_step(v_1, cs)}), P.ite(P.W, P.b_eq(v_1133, v_2), cv, P.h_filt(v_2, P.h_step(v_1, cs))), ih_1499) : {_ == P.ite(P.W, P.b_eq(v_1133, v_2), cv, P.h_filt(v_2, P.h_step(v_1, cs))) : P.W}
      {==}
    case False{}:
      %Equal.sym(Bool, Cmp.is_eq(U32.cmp(v_1132, v_1)), False{}, e_1498) : {P.h_filt(v_2, P.h_cons(_, v_1133, cv, P.h_step(v_1, cs))) == P.ite(P.W, Bool.and(_, P.b_eq(v_1133, v_2)), cv, P.h_filt(v_2, P.h_step(v_1, cs))) : P.W}
      {==}

def lp_filt_con(+rk: List<&2, U32>, +cb: List<&2, U32>, +cv: P.W, +cs: List<&2, P.HKB>) -> {P.h_filt(rk, Con{P.HKB{cb, cv}, cs}) == P.ite(P.W, P.b_eq(cb, rk), cv, P.h_filt(rk, cs)) : P.W}:
  match rk:
    case Nil{}:
      match cb:
        case Nil{}:
          {==}
        case Con{+v_3, +v_4}:
          {==}
    case Con{+v_1, +v_2}:
      match cb:
        case Nil{}:
          {==}
        case Con{+v_1132, +v_1133}:
          lp_filt_con__h1496(v_2, v_1132, v_1, v_1133, cv, cs, lp_filt_con(v_2, v_1133, cv, P.h_step(v_1, cs)), Cmp.is_eq(U32.cmp(v_1132, v_1)), {==})

def lp_beq_sound(+x: List<&2, U32>, +y: List<&2, U32>, +e: {P.b_eq(x, y) == True{} : Bool}) -> {x == y : List<&2, U32>}:
  match x y:
    case Nil{} Nil{}:
      {==}
    case Nil{} Con{+h, +t}:
      lb_ex({Nil{} == Con{h, t} : List<&2, U32>}, lb_ft(e))
    case Con{+h, +t} Nil{}:
      lb_ex({Con{h, t} == Nil{} : List<&2, U32>}, lb_ft(e))
    case Con{+a, +s} Con{+b, +u}:
      %Equal.sym(U32, a, b, lbu_refl(a, b, lb_and_l(U32.is_eq(a, b), P.b_eq(s, u), e))) : {Con{_, s} == Con{b, u} : List<&2, U32>}
      %Equal.sym(List<&2, U32>, s, u, lp_beq_sound(s, u, lb_and_r(U32.is_eq(a, b), P.b_eq(s, u), e))) : {Con{b, _} == Con{b, u} : List<&2, U32>}
      {==}

def lp_rev2(+x: List<&2, U32>) -> {P.b_rev(P.b_rev(x, Nil{}), Nil{}) == x : List<&2, U32>}:
  lp_rev_rev(x, Nil{})

def lp_beq_rev_h(+x: List<&2, U32>, +y: List<&2, U32>, c: Bool, +e: {P.b_eq(x, y) == c : Bool}, d: Bool, +f: {P.b_eq(P.b_rev(x, Nil{}), P.b_rev(y, Nil{})) == d : Bool}) -> {d == c : Bool}:
  match c d:
    case True{} True{}:
      {==}
    case False{} False{}:
      {==}
    case True{} False{}:
      %f : {_ == True{} : Bool}
      %lp_beq_sound(x, y, e) : {P.b_eq(P.b_rev(x, Nil{}), P.b_rev(_, Nil{})) == True{} : Bool}
      lp_beq_refl(P.b_rev(x, Nil{}))
    case False{} True{}:
      %e : {True{} == _ : Bool}
      %lp_rev2(x) : {True{} == P.b_eq(_, y) : Bool}
      %lp_rev2(y) : {True{} == P.b_eq(P.b_rev(P.b_rev(x, Nil{}), Nil{}), _) : Bool}
      %lp_beq_sound(P.b_rev(x, Nil{}), P.b_rev(y, Nil{}), f) : {True{} == P.b_eq(P.b_rev(P.b_rev(x, Nil{}), Nil{}), P.b_rev(_, Nil{})) : Bool}
      Equal.sym(Bool, P.b_eq(P.b_rev(P.b_rev(x, Nil{}), Nil{}), P.b_rev(P.b_rev(x, Nil{}), Nil{})), True{}, lp_beq_refl(P.b_rev(P.b_rev(x, Nil{}), Nil{})))

def lp_beq_rev(+x: List<&2, U32>, +y: List<&2, U32>) -> {P.b_eq(P.b_rev(x, Nil{}), P.b_rev(y, Nil{})) == P.b_eq(x, y) : Bool}:
  lp_beq_rev_h(x, y, P.b_eq(x, y), {==}, P.b_eq(P.b_rev(x, Nil{}), P.b_rev(y, Nil{})), {==})
'''

# (lemma, [(param, type)], left, right): {left == right} for all parameters, rewritten left to right
RULES = [
    ("lp_filt_nil", [("rk", "List<&2, U32>")], "P.h_filt(rk, Nil{})", "P.w0()"),
    ("lp_filt_con", [("rk", "List<&2, U32>"), ("cb", "List<&2, U32>"), ("cv", "P.W"), ("cs", "List<&2, P.HKB>")],
     "P.h_filt(rk, Con{P.HKB{cb, cv}, cs})", "P.ite(P.W, P.b_eq(cb, rk), cv, P.h_filt(rk, cs))"),
    ("lp_beq_rev", [("x", "List<&2, U32>"), ("y", "List<&2, U32>")],
     "P.b_eq(P.b_rev(x, Nil{}), P.b_rev(y, Nil{}))", "P.b_eq(x, y)"),
    ("lp_beq_refl", [("x", "List<&2, U32>")], "P.b_eq(x, x)", "True{}"),
]
# (lemma, [(param, type)], condition, (left, right)): from e : {condition == True{}}, lemma(params, e) : {left == right}
REFLECT = [
    ("lp_beq_sound", [("x", "List<&2, U32>"), ("y", "List<&2, U32>")], "P.b_eq(x, y)", ("x", "y")),
]


def _closure() -> dict:
    from ..gen.equivalence import parse_items
    from .prelude3 import PRELUDE
    _, items = parse_items(PRELUDE)
    by = {i.name: i for i in items}
    out, todo = {}, list(NAMES)
    while todo:
        n = todo.pop()
        if n in out or n not in by:
            continue
        out[n] = by[n].text
        todo += [m for m in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", by[n].text) if m in by and m not in out]
    return out


def applies(new_items: dict) -> bool:
    """True when the new model holds every prelude definition the lemmas reach, each with the prelude's own text."""
    need = _closure()
    if set(NAMES) - set(need):
        return False
    return all(n in new_items and new_items[n].text == t for n, t in need.items())
