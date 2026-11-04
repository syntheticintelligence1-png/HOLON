"""Lemmas about the M3 prelude's own definitions (F32; docs/HUMAN_ANSWERS.md Q31 (d)).

holon.sorts.prelude3 is fixed text that names no target, and every M3 model carries it verbatim. A30 rewrote its hash
table lookup (h_get: the table's keys and the looked-up key reversed, then filtered byte by byte, h_filt over h_step /
h_one / h_cons, the answer read by h_ends / h_end1). These are the list lemmas a proof that it is still a first-match
lookup needs, each stated for all lists and all values of its parameters, about the prelude's definitions only (never
about a pair of models, never about one law): reversal is an involution (lp_rev_rev), the byte-string equality b_eq is
reflexive, sound (b_eq(x, y) == True gives x == y) and blind to reversal (lp_beq_rev), and the filter over a table
with a first entry answers that entry's value when its key matches, else the rest's answer (lp_filt_con, lp_filt_nil).

The statements are fixed. The proofs of lp_rev_rev, lp_beq_refl, lp_filt_nil and lp_filt_con are generated from their
statements by holon.gen.eqprove (GENERATED, proved against the prelude's own definitions; text()). lp_beq_sound,
lp_rev2, lp_beq_rev_h and lp_beq_rev are written out by hand (HAND: reflection, and a case split whose two
contradictory cases are closed by rewriting); docs/iterations/F32.md asks the human about them. The kernel checks all
of it (bend2 and BendTT, tests_m3).

The text is used only for a model whose prelude definitions these lemmas mention, and every definition they reach, are
the prelude's own text (applies); the model's names are reached through the pair module's alias P, as every lemma of
holon.gen.equivalence does. The library depends on holon.gen.eqlib (emitted before it).
"""
from __future__ import annotations

import re
from functools import lru_cache

# the prelude definitions the statements mention
NAMES = ["b_rev", "b_eq", "h_filt", "h_step", "h_one", "h_cons", "h_ends", "h_end1", "ite", "w0", "W", "HKB"]

HEADER = "# ---- holon.sorts.prelude3_lemmas: lemmas about the M3 prelude's definitions\n"

L = "List<&2, U32>"
# (lemma, [(param, type)], left, right, type): fixed statements whose proofs holon.gen.eqprove generates (text())
GENERATED = [
    ("lp_rev_rev", [("x", L), ("a", L)], "P.b_rev(P.b_rev(x, a), Nil{})", "P.b_rev(a, x)", L),
    ("lp_beq_refl", [("x", L)], "P.b_eq(x, x)", "True{}", "Bool"),
    ("lp_filt_nil", [("rk", L)], "P.h_filt(rk, Nil{})", "P.w0()", "P.W"),
    ("lp_filt_con", [("rk", L), ("cb", L), ("cv", "P.W"), ("cs", "List<&2, P.HKB>")],
     "P.h_filt(rk, Con{P.HKB{cb, cv}, cs})", "P.ite(P.W, P.b_eq(cb, rk), cv, P.h_filt(rk, cs))", "P.W"),
]

# written out by hand (they use the generated lemmas above by name)
HAND = '''\
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

@lru_cache(maxsize=1)
def text() -> str:
    """The library's Bend text: each GENERATED statement with the proof holon.gen.eqprove finds for it over Base and
    the prelude's own definitions (deterministic), then HAND. Raises holon.gen.eqprove.Fail when a proof is not
    found (applies is then False)."""
    from ..gen import eqlib, eqprove as EP, eqterms as ET
    from ..gen.equivalence import ALIAS, PREFIX
    from .prelude3 import PRELUDE
    bd, bt = eqlib.base_defs()
    pd, pt = ET.read_source("import Base\n\n" + PRELUDE, qualify=ALIAS)
    defs, types = {**bd, **pd}, {**bt, **pt}
    parts = [HEADER]
    for name, ps, lhs, rhs, ty in GENERATED:
        pv = EP.Prover(defs, types, f"{ALIAS}.{PREFIX}", set(), {}, tag=name)
        try:
            body = pv.prove_lemma(name, ps, ET.parse(lhs), ET.parse(rhs), ty)
        except (EP.E.TermError, RecursionError) as e:
            raise EP.Fail(f"{name}: {e}")
        parts.append("\n".join(pv.out + [body]))
    parts.append(HAND)
    return "\n".join(parts)


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
    if not all(n in new_items and new_items[n].text == t for n, t in need.items()):
        return False
    from ..gen import eqprove as EP
    try:
        text()
    except EP.Fail:
        return False
    return True
