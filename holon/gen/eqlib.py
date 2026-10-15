"""The Base lemma library of the equivalence prover (F32; docs/HUMAN_ANSWERS.md Q31).

Identities about Base only (Bool, Cmp, Word(n) and U32 as Base's Word of 32 Bools), each stated for every input of its
types, with no premise beyond the types (a reflection lemma's premise is the Bool fact it reflects), and proved here:
by induction over Word(n) whose step is a finite lemma over the bits and the Cmp of the tail (proved by exhaustive
case analysis, the case table computed by holon.gen.eqterms and checked by the kernel), or by finite case analysis
where that is the honest proof. The text is fixed: it names no model, no target and no definition of any model, and
it is the same for every pair of models. holon.gen.equivalence emits it in front of every lemma file, and the tests
check it alone in bend2 and BendTT.

RULES are the oriented rewrites the prover may use anywhere in a goal (holon.gen.eqprove): (lemma, parameters,
left side, right side) meaning {left == right} for all parameters, used left to right (each one simplifies: fewer
operations or a constant). REFLECT names the reflection lemmas: from {cond == True{}} they give an equality.

Every name defined here starts with `lb`. A model may define names starting with `lb` too (real models do); they
cannot collide, because every lemma file reaches the model's names only through the pair module's alias P.
"""
from __future__ import annotations

from functools import lru_cache
from itertools import product

FIN = {"Bool": ["True", "False"], "Cmp": ["LT", "EQ", "GT"]}


def _base_eval():
    from . import eqterms as E
    from .. import bend
    r = bend.run(["base"])
    text = "\n".join(ln for ln in r.out.splitlines() if "is available: run bend update" not in ln)
    bd, bt = E.read_source(text)
    return E.Evaluator(bd, bt)


@lru_cache(maxsize=1)
def base_text() -> str:
    from .. import bend
    r = bend.run(["base"])
    if r.code != 0:
        raise RuntimeError(f"bend base failed: {r.out[:300]}")
    return "\n".join(ln for ln in r.out.splitlines() if "is available: run bend update" not in ln) + "\n"


@lru_cache(maxsize=1)
def base_defs():
    from . import eqterms as E
    return E.read_source(base_text())


ABSURD = """\
def lb_bt(b: Bool) -> Type:
  match b:
    case True{}:
      Empty
    case False{}:
      Unit

def lb_ex(-A: Type, x: Empty) -> A:
  match x:

def lb_ft(e: {False{} == True{} : Bool}) -> Empty:
  %e : lb_bt(_)
  Unit{}

def lb_tf(e: {True{} == False{} : Bool}) -> Empty:
  %e : lb_bt(Bool.not(_))
  Unit{}
"""


def _absurd_cmp(a: str, b: str) -> str:
    return (f"def lb_c_{a}_{b}(e: {{{a}{{}} == {b}{{}} : Cmp}}) -> Empty:\n"
            f"  %e : lb_bt(Cmp.is_{b.lower()}(_))\n  Unit{{}}\n")


CMP_ABSURD = "\n".join(_absurd_cmp(a, b) for a in FIN["Cmp"] for b in FIN["Cmp"] if a != b)


def absurd(ty: str, a: str, b: str, h: str) -> str:
    """A term of Empty from h : {a{} == b{} : ty}, a != b."""
    if ty == "Bool":
        return f"lb_ft({h})" if (a, b) == ("False", "True") else f"lb_tf({h})"
    return f"lb_c_{a}_{b}({h})"


def finite(name: str, params: list, hyps: list, lhs: str, rhs: str, ty: str) -> str:
    """A lemma over finite parameters (Bool, Cmp) proved by exhaustive case analysis: in each case either the goal
    computes ({==}) or a hypothesis computes to an equation between distinct constructors (absurd). params:
    [(name, type)], hyps: [(name, left, right, type)]."""
    from . import eqterms as E
    bd, bt = base_defs()
    ev = E.Evaluator(bd, bt)
    ps = ", ".join(f"+{n}: {t}" for n, t in params)
    hs = ", ".join(f"{h}: {{{a} == {b} : {t}}}" for h, a, b, t in hyps)
    head = f"def {name}({ps}{', ' if hs else ''}{hs}) -> {{{lhs} == {rhs} : {ty}}}:"
    names = [n for n, _ in params]
    lines = [head, "  match " + " ".join(names) + ":"]
    for combo in product(*[FIN[t] for _, t in params]):
        env = {n: ("ctor", c, ()) for n, c in zip(names, combo)}
        lines.append("    case " + " ".join(f"{c}{{}}" for c in combo) + ":")
        leaf = None
        for h, a, b, t in hyps:
            va, vb = (ev.eval(E.parse(x), env) for x in (a, b))
            if va[0] == "ctor" and vb[0] == "ctor" and va != vb and not va[2] and not vb[2]:
                goal = E.show(E.subst(E.parse(lhs), env)) + " == " + E.show(E.subst(E.parse(rhs), env))
                leaf = f"lb_ex({{{goal} : {ty}}}, {absurd(t, va[1], vb[1], h)})"
                break
        if leaf is None:
            gl, gr = ev.eval(E.parse(lhs), env), ev.eval(E.parse(rhs), env)
            if gl != gr:
                raise AssertionError(f"{name}: the case {combo} does not compute ({E.show(gl)} vs {E.show(gr)})")
            leaf = "{==}"
        lines.append("      " + leaf)
    return "\n".join(lines) + "\n"


def _word_induction(name, params_after_n, stmt, base_case, step_case) -> str:
    """def name(n: Nat, <params>) -> stmt by induction on n (the Word params matched in each case)."""
    ps = ", ".join(["+n: Nat"] + params_after_n)
    return f"def {name}({ps}) -> {stmt}:\n  match n:\n    case 0n:\n{base_case}    case 1n+p:\n{step_case}"


def _gen() -> str:
    parts = ["# ---- holon.gen.eqlib: Base identities, each proved for all inputs (fixed text; no model is named)",
             ABSURD, CMP_ABSURD]
    F = lambda *a: parts.append(finite(*a))
    # -- Bool: simplifications (finite)
    F("lb_not_not", [("b", "Bool")], [], "Bool.not(Bool.not(b))", "b", "Bool")
    F("lb_and_t", [("b", "Bool")], [], "Bool.and(b, True{})", "b", "Bool")
    F("lb_and_f", [("b", "Bool")], [], "Bool.and(b, False{})", "False{}", "Bool")
    F("lb_or_f", [("b", "Bool")], [], "Bool.or(b, False{})", "b", "Bool")
    F("lb_or_t", [("b", "Bool")], [], "Bool.or(b, True{})", "True{}", "Bool")
    F("lb_xor_f", [("b", "Bool")], [], "Bool.xor(b, False{})", "b", "Bool")
    F("lb_not_xor_self", [("b", "Bool")], [], "Bool.not(Bool.xor(b, b))", "True{}", "Bool")
    # -- Bool reflection
    parts.append("""\
def lb_and_l(+a: Bool, +b: Bool, e: {Bool.and(a, b) == True{} : Bool}) -> {a == True{} : Bool}:
  match a:
    case True{}:
      {==}
    case False{}:
      e

def lb_and_r(+a: Bool, +b: Bool, e: {Bool.and(a, b) == True{} : Bool}) -> {b == True{} : Bool}:
  match a:
    case True{}:
      e
    case False{}:
      lb_ex({b == True{} : Bool}, lb_ft(e))
""")
    # -- finite steps of the Word inductions (bits and the Cmp of the tail)
    fin = "Word.cmp.fin"
    F("lbf_cmp_refl", [("b", "Bool"), ("c", "Cmp")], [("h", "c", "EQ{}", "Cmp")], f"{fin}(b, b, c)", "EQ{}", "Cmp")
    F("lbf_lt_z", [("b", "Bool"), ("c", "Cmp")], [("h", "Cmp.is_lt(c)", "False{}", "Bool")],
      f"Cmp.is_lt({fin}(b, False{{}}, c))", "False{}", "Bool")
    F("lbf_eqz_or", [("x", "Bool"), ("y", "Bool"), ("c", "Cmp"), ("d", "Cmp"), ("e", "Cmp")],
      [("h", "Cmp.is_eq(c)", "Bool.and(Cmp.is_eq(d), Cmp.is_eq(e))", "Bool")],
      f"Cmp.is_eq({fin}(Bool.or(x, y), False{{}}, c))",
      f"Bool.and(Cmp.is_eq({fin}(x, False{{}}, d)), Cmp.is_eq({fin}(y, False{{}}, e)))", "Bool")
    F("lbf_eqz_xor", [("x", "Bool"), ("y", "Bool"), ("c", "Cmp"), ("d", "Cmp")],
      [("h", "Cmp.is_eq(c)", "Cmp.is_eq(d)", "Bool")],
      f"Cmp.is_eq({fin}(Bool.xor(x, y), False{{}}, c))", f"Cmp.is_eq({fin}(x, y, d))", "Bool")
    F("lbf_bits", [("x", "Bool"), ("y", "Bool"), ("c", "Cmp")], [("h", f"Cmp.is_eq({fin}(x, y, c))", "True{}", "Bool")],
      "x", "y", "Bool")
    F("lbf_rest", [("x", "Bool"), ("y", "Bool"), ("c", "Cmp")], [("h", f"Cmp.is_eq({fin}(x, y, c))", "True{}", "Bool")],
      "Cmp.is_eq(c)", "True{}", "Bool")
    F("lbf_lt_one", [("b", "Bool"), ("c", "Cmp")], [("h", "Cmp.is_lt(c)", "False{}", "Bool")],
      f"Cmp.is_lt({fin}(b, True{{}}, c))", f"Cmp.is_eq({fin}(b, False{{}}, c))", "Bool")
    # -- Word(n), by induction on n
    nil = "      match {v}:\n        case WNil{{}}:\n          {{==}}\n"
    nil2 = "      match {a} {b}:\n        case WNil{{}} WNil{{}}:\n          {{==}}\n"
    parts.append(_word_induction(
        "lbn_cmp_refl", ["+w: Word(n)"], "{Word.cmp(n, w, w) == EQ{} : Cmp}", nil.format(v="w"),
        "      match w:\n        case WCon{+b, +t}:\n          lbf_cmp_refl(b, Word.cmp(p, t, t), lbn_cmp_refl(p, t))\n"))
    parts.append(_word_induction(
        "lbn_lt_z", ["+w: Word(n)"], "{Cmp.is_lt(Word.cmp(n, w, Word.zero(n))) == False{} : Bool}", nil.format(v="w"),
        "      match w:\n        case WCon{+b, +t}:\n"
        "          lbf_lt_z(b, Word.cmp(p, t, Word.zero(p)), lbn_lt_z(p, t))\n"))
    parts.append(_word_induction(
        "lbn_eqz_or", ["+x: Word(n)", "+y: Word(n)"],
        "{Cmp.is_eq(Word.cmp(n, Word.or(n, x, y), Word.zero(n))) == Bool.and(Cmp.is_eq(Word.cmp(n, x, Word.zero(n))), "
        "Cmp.is_eq(Word.cmp(n, y, Word.zero(n)))) : Bool}", nil2.format(a="x", b="y"),
        "      match x y:\n        case WCon{+a, +s} WCon{+b, +t}:\n"
        "          lbf_eqz_or(a, b, Word.cmp(p, Word.or(p, s, t), Word.zero(p)), Word.cmp(p, s, Word.zero(p)), "
        "Word.cmp(p, t, Word.zero(p)), lbn_eqz_or(p, s, t))\n"))
    parts.append(_word_induction(
        "lbn_eqz_xor", ["+x: Word(n)", "+y: Word(n)"],
        "{Cmp.is_eq(Word.cmp(n, Word.xor(n, x, y), Word.zero(n))) == Cmp.is_eq(Word.cmp(n, x, y)) : Bool}",
        nil2.format(a="x", b="y"),
        "      match x y:\n        case WCon{+a, +s} WCon{+b, +t}:\n"
        "          lbf_eqz_xor(a, b, Word.cmp(p, Word.xor(p, s, t), Word.zero(p)), Word.cmp(p, s, t), "
        "lbn_eqz_xor(p, s, t))\n"))
    parts.append(_word_induction(
        "lbn_refl", ["+x: Word(n)", "+y: Word(n)", "+e: {Cmp.is_eq(Word.cmp(n, x, y)) == True{} : Bool}"],
        "{x == y : Word(n)}", nil2.format(a="x", b="y"),
        "      match x y:\n        case WCon{+a, +s} WCon{+b, +t}:\n"
        "          %lbf_bits(a, b, Word.cmp(p, s, t), e) : {WCon{a, s} == WCon{_, t} : Word(1n+p)}\n"
        "          %lbn_refl(p, s, t, lbf_rest(a, b, Word.cmp(p, s, t), e)) : {WCon{a, s} == WCon{a, _} : Word(1n+p)}\n"
        "          {==}\n"))
    for nm, stmt_l, f, c in (("lbn_add_z", "Word.adc(n, w, Word.zero(n), False{}, False{})", "False{}", "False{}"),
                             ("lbn_z_add", "Word.adc(n, Word.zero(n), w, False{}, False{})", "False{}", "False{}"),
                             ("lbn_sub_z", "Word.adc(n, w, Word.zero(n), True{}, True{})", "True{}", "True{}")):
        rec = stmt_l.replace("(n, ", "(p, ").replace("Word.zero(n)", "Word.zero(p)").replace(", w,", ", t,").replace(
            "(p, w,", "(p, t,")
        cases = ""
        for bit in ("False{}", "True{}"):
            cases += (f"        case WCon{{{bit}, +t}}:\n"
                      f"          %{nm}(p, t) : {{WCon{{{bit}, {rec}}} == WCon{{{bit}, _}} : Word(1n+p)}}\n"
                      f"          {{==}}\n")
        parts.append(_word_induction(nm, ["+w: Word(n)"], f"{{{stmt_l} == w : Word(n)}}", nil.format(v="w"),
                                     "      match w:\n" + cases))
    parts.append(_word_induction(
        "lbn_inc", ["+w: Word(n)"], "{Word.adc(n, w, Word.zero(n), False{}, True{}) == Word.inc(n, w) : Word(n)}",
        nil.format(v="w"),
        "      match w:\n        case WCon{False{}, +t}:\n"
        "          %lbn_add_z(p, t) : {WCon{True{}, Word.adc(p, t, Word.zero(p), False{}, False{})} == WCon{True{}, _} : "
        "Word(1n+p)}\n          {==}\n"
        "        case WCon{True{}, +t}:\n"
        "          %lbn_inc(p, t) : {WCon{False{}, Word.adc(p, t, Word.zero(p), False{}, True{})} == WCon{False{}, _} : "
        "Word(1n+p)}\n          {==}\n"))
    # -- U32
    parts.append("""\
def lbu_eqz_or(+x: U32, +y: U32) -> {U32.is_eq(U32.or(x, y), 0) == Bool.and(U32.is_eq(x, 0), U32.is_eq(y, 0)) : Bool}:
  match x y:
    case U32{+a} U32{+b}:
      lbn_eqz_or(32n, a, b)

def lbu_eqz_xor(+x: U32, +y: U32) -> {U32.is_eq(U32.xor(x, y), 0) == U32.is_eq(x, y) : Bool}:
  match x y:
    case U32{+a} U32{+b}:
      lbn_eqz_xor(32n, a, b)

def lbu_refl(+x: U32, +y: U32, +e: {U32.is_eq(x, y) == True{} : Bool}) -> {x == y : U32}:
  match x y:
    case U32{+a} U32{+b}:
      %lbn_refl(32n, a, b, e) : {U32{a} == U32{_} : U32}
      {==}

def lbu_eq_self(+x: U32) -> {U32.is_eq(x, x) == True{} : Bool}:
  match x:
    case U32{+w}:
      %Equal.sym(Cmp, Word.cmp(32n, w, w), EQ{}, lbn_cmp_refl(32n, w)) : {Cmp.is_eq(_) == True{} : Bool}
      {==}

def lbu_lt_self(+x: U32) -> {U32.is_lt(x, x) == False{} : Bool}:
  match x:
    case U32{+w}:
      %Equal.sym(Cmp, Word.cmp(32n, w, w), EQ{}, lbn_cmp_refl(32n, w)) : {Cmp.is_lt(_) == False{} : Bool}
      {==}

def lbu_lt_z(+x: U32) -> {U32.is_lt(x, 0) == False{} : Bool}:
  match x:
    case U32{+w}:
      lbn_lt_z(32n, w)

def lbu_lt_one(+x: U32) -> {U32.is_lt(x, 1) == U32.is_eq(x, 0) : Bool}:
  match x:
    case U32{+w}:
      match w:
        case WCon{+b, +t}:
          lbf_lt_one(b, Word.cmp(31n, t, Word.zero(31n)), lbn_lt_z(31n, t))

def lbu_add_z(+x: U32) -> {U32.add(x, 0) == x : U32}:
  match x:
    case U32{+w}:
      %Equal.sym(Word(32n), Word.adc(32n, w, Word.zero(32n), False{}, False{}), w, lbn_add_z(32n, w)) : {U32{_} == U32{w} : U32}
      {==}

def lbu_z_add(+x: U32) -> {U32.add(0, x) == x : U32}:
  match x:
    case U32{+w}:
      %Equal.sym(Word(32n), Word.adc(32n, Word.zero(32n), w, False{}, False{}), w, lbn_z_add(32n, w)) : {U32{_} == U32{w} : U32}
      {==}

def lbu_sub_z(+x: U32) -> {U32.sub(x, 0) == x : U32}:
  match x:
    case U32{+w}:
      %Equal.sym(Word(32n), Word.adc(32n, w, Word.zero(32n), True{}, True{}), w, lbn_sub_z(32n, w)) : {U32{_} == U32{w} : U32}
      {==}

def lbu_add_one(+x: U32) -> {U32.add(x, 1) == U32.inc(x) : U32}:
  match x:
    case U32{+w}:
      match w:
        case WCon{False{}, +t}:
          %lbn_add_z(31n, t) : {U32{WCon{True{}, Word.adc(31n, t, Word.zero(31n), False{}, False{})}} == U32{WCon{True{}, _}} : U32}
          {==}
        case WCon{True{}, +t}:
          %lbn_inc(31n, t) : {U32{WCon{False{}, Word.adc(31n, t, Word.zero(31n), False{}, True{})}} == U32{WCon{False{}, _}} : U32}
          {==}
""")
    return "\n".join(p.rstrip("\n") + "\n" for p in parts)


@lru_cache(maxsize=1)
def text() -> str:
    return _gen()


# (lemma, [(param, type)], left, right): {left == right}, rewritten left to right
RULES = [
    ("lb_not_not", [("b", "Bool")], "Bool.not(Bool.not(b))", "b"),
    ("lb_and_t", [("b", "Bool")], "Bool.and(b, True{})", "b"),
    ("lb_and_f", [("b", "Bool")], "Bool.and(b, False{})", "False{}"),
    ("lb_or_f", [("b", "Bool")], "Bool.or(b, False{})", "b"),
    ("lb_or_t", [("b", "Bool")], "Bool.or(b, True{})", "True{}"),
    ("lb_xor_f", [("b", "Bool")], "Bool.xor(b, False{})", "b"),
    ("lbu_eqz_or", [("x", "U32"), ("y", "U32")], "U32.is_eq(U32.or(x, y), 0)",
     "Bool.and(U32.is_eq(x, 0), U32.is_eq(y, 0))"),
    ("lbu_eqz_xor", [("x", "U32"), ("y", "U32")], "U32.is_eq(U32.xor(x, y), 0)", "U32.is_eq(x, y)"),
    ("lbu_eq_self", [("x", "U32")], "U32.is_eq(x, x)", "True{}"),
    ("lbu_lt_self", [("x", "U32")], "U32.is_lt(x, x)", "False{}"),
    ("lbu_lt_z", [("x", "U32")], "U32.is_lt(x, 0)", "False{}"),
    ("lbu_lt_one", [("x", "U32")], "U32.is_lt(x, 1)", "U32.is_eq(x, 0)"),
    ("lbu_add_z", [("x", "U32")], "U32.add(x, 0)", "x"),
    ("lbu_z_add", [("x", "U32")], "U32.add(0, x)", "x"),
    ("lbu_sub_z", [("x", "U32")], "U32.sub(x, 0)", "x"),
    ("lbu_add_one", [("x", "U32")], "U32.add(x, 1)", "U32.inc(x)"),
]

# reflection: (lemma, [(param, type)], condition, (left, right)): from e : {condition == True{}}, lemma(params, e)
# proves {left == right}
REFLECT = [
    ("lbu_refl", [("x", "U32"), ("y", "U32")], "U32.is_eq(x, y)", ("x", "y")),
]
# conjunction: (left lemma, right lemma) from {Bool.and(a, b) == True{}}
AND_PROJ = ("lb_and_l", "lb_and_r")
