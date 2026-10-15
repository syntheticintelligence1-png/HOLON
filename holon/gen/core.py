"""The core library (whitepaper §6 core library, §10.3; BUILD_PLAN I8, Q14a default).

Shared Nat/Bool lemmas, stated once as laws in <gen_dir>/core/LAWS.bend and proved in
<gen_dir>/core/PROOF.bend. Proofs are never hand-written: each lemma names a proof class, the class
fixes the case skeleton, and every case body is chosen from the class's candidates. Bend decides: the
search advances the case Bend rejects, until the file checks or a case runs out of candidates.

Classes (the case skeleton):
  absurd   no match: ex falso from a False == True hypothesis
  nat1     a match on the first binder (0n / 1n+p)
  nat2     a match on the first two binders
  nat3     a match on the first three binders (audit M2/1 F-M2-04: transitivity needs three)
  bool1    a match on the first binder (True{} / False{})
  compose  no match: the claim follows from earlier catalog lemmas alone

Candidates per case, in this order: `{==}`; each hypothesis; ex falso on a hypothesis that computes to
False == True, or on an inequality applied to `{==}`; the induction hypothesis (every scrutinee a
successor); for a Nat equation, the induction hypothesis under the successor (`1n+L == 1n+R` from
`L == R`); then **compositions**: calls of EARLIER catalog lemmas whose claim matches the case's goal,
their binders found by first-order matching against the goal and their hypotheses supplied by the
case's hypotheses, by the induction hypothesis, or by a call of another earlier lemma (depth 2). The
matching runs on a normaliser that approximates Bend's evaluation on literal-headed arguments
(Bool.and/or/not on constructors, Nat.add/sub on 0n and successors, comparisons of successors); it is
untrusted like the rest of the search: a wrong match only proposes a candidate Bend rejects.

The catalog covers the shapes the M2+ proof generators need: the M1 CORE lemmas that holon.gen.mproofs
pasted by hand for deadline and chain_revert (core_lt_of_le_lt, core_le_add_l, core_kappa_site,
core_and_lt_add, ...), now generated and checked once; transitivity (core_le_trans, core_lt_of_le_lt,
core_lt_of_lt_le); monotonicity of sums (core_le_add_mono); and the guard-to-subtraction shapes a SORT
coercion guard rests on (a < b, b >= 1, b <= a, !(a < b), !(a > b) give the sign obligation of a
subtraction: core_le_of_lt, core_one_le_of_lt, core_le_of_ge, core_le_of_not_lt, core_le_of_not_gt, and
core_sub_add / core_sub_add_of_lt for the value of a non-truncated Nat.sub). Since I15 also the shapes
holon.gen.coercion (SORT-site coercion guards) needs to turn ONE passed condition into the obligation
`is_le(subtrahend, minuend)`: core_le_of_gt (a > b), core_le_of_not_le and core_one_le_sub_of_not_le (a <= b failed,
for b - a and (a - b) - 1); a hypothesis {X == False{}} whose X computes to True{} is closed ex falso through
Equal.sym.

Generated proofs of M2+ milestones import the core as `../core/PROOF.bend` (which imports
`core/LAWS.bend`) and call a lemma through the core LAWS alias `C` (holon.gen.mproofs.core_ref), so the
core's proofs are in every importer's checked closure (probe bend/notes/p_core_import (b)); an unproved
core law makes the importer fail (probe (a)). A bare core LAWS import is banned by G3 (bare_laws_imports).
"""
from __future__ import annotations

import hashlib
import itertools
import json
import re
from pathlib import Path

from .. import bend

_LT = "{Nat.is_lt(%s, %s) == True{} : Bool}"
_LE = "{Nat.is_le(%s, %s) == True{} : Bool}"

# name, binders [(mode, name, type)], hypotheses [(name, type)], claim, class. Order matters: a composition
# candidate calls only lemmas listed before the lemma it proves.
CATALOG = [
    ("core_false_ne_true", [], [("e", "{False{} == True{} : Bool}")], "Empty", "absurd"),
    ("core_le_refl", [("", "x", "Nat")], [], "{Nat.is_le(x, x) == True{} : Bool}", "nat1"),
    ("core_is_eq_refl", [("", "x", "Nat")], [], "{Nat.is_eq(x, x) == True{} : Bool}", "nat1"),
    ("core_le_zero", [("", "x", "Nat")], [], "{Nat.is_le(0n, x) == True{} : Bool}", "nat1"),
    ("core_lt_add", [("", "x", "Nat"), ("", "t", "Nat"), ("+", "dt", "Nat")], [("e", "{Nat.is_lt(x, t) == True{} : Bool}")],
     "{Nat.is_lt(x, Nat.add(t, dt)) == True{} : Bool}", "nat2"),
    ("core_lt_not_le", [("", "x", "Nat"), ("", "t", "Nat")], [("e", "{Nat.is_lt(x, t) == True{} : Bool}")],
     "{Nat.is_le(t, x) == False{} : Bool}", "nat2"),
    ("core_is_eq_false", [("", "a", "Nat"), ("", "b", "Nat")], [("ne", "{a != b : Nat}")],
     "{Nat.is_eq(a, b) == False{} : Bool}", "nat2"),
    ("core_and_left", [("", "a", "Bool"), ("+", "b", "Bool")], [("e", "{Bool.and(a, b) == True{} : Bool}")],
     "{a == True{} : Bool}", "bool1"),
    ("core_and_right", [("", "a", "Bool"), ("+", "b", "Bool")], [("e", "{Bool.and(a, b) == True{} : Bool}")],
     "{b == True{} : Bool}", "bool1"),
    # ---- audit M2/1 (F-M2-04): order, guards and subtraction
    ("core_and_intro", [("", "a", "Bool"), ("+", "b", "Bool")], [("ea", "{a == True{} : Bool}"), ("eb", "{b == True{} : Bool}")],
     "{Bool.and(a, b) == True{} : Bool}", "bool1"),
    ("core_le_of_lt", [("", "a", "Nat"), ("", "b", "Nat")], [("e", _LT % ("a", "b"))], _LE % ("a", "b"), "nat2"),
    ("core_one_le_of_lt", [("", "a", "Nat"), ("", "b", "Nat")], [("e", _LT % ("a", "b"))], _LE % ("1n", "b"), "nat2"),
    ("core_le_of_ge", [("", "a", "Nat"), ("", "b", "Nat")], [("e", "{Nat.is_ge(a, b) == True{} : Bool}")],
     _LE % ("b", "a"), "nat2"),
    ("core_lt_of_gt", [("", "a", "Nat"), ("", "b", "Nat")], [("e", "{Nat.is_gt(a, b) == True{} : Bool}")],
     _LT % ("b", "a"), "nat2"),
    ("core_le_of_not_lt", [("", "a", "Nat"), ("", "b", "Nat")], [("e", "{Bool.not(Nat.is_lt(a, b)) == True{} : Bool}")],
     _LE % ("b", "a"), "nat2"),
    ("core_le_of_not_gt", [("", "a", "Nat"), ("", "b", "Nat")], [("e", "{Bool.not(Nat.is_gt(a, b)) == True{} : Bool}")],
     _LE % ("a", "b"), "nat2"),
    ("core_le_succ", [("", "x", "Nat"), ("", "y", "Nat")], [("e", _LE % ("x", "y"))], _LE % ("x", "1n+y"), "nat2"),
    ("core_le_add_self", [("", "a", "Nat"), ("+", "d", "Nat")], [], _LE % ("a", "Nat.add(a, d)"), "nat1"),
    ("core_le_trans", [("", "a", "Nat"), ("", "b", "Nat"), ("", "c", "Nat")], [("e1", _LE % ("a", "b")), ("e2", _LE % ("b", "c"))],
     _LE % ("a", "c"), "nat3"),
    ("core_lt_of_le_lt", [("", "a", "Nat"), ("", "b", "Nat"), ("", "c", "Nat")], [("e1", _LE % ("a", "b")), ("e2", _LT % ("b", "c"))],
     _LT % ("a", "c"), "nat3"),
    ("core_lt_of_lt_le", [("", "a", "Nat"), ("", "b", "Nat"), ("", "c", "Nat")], [("e1", _LT % ("a", "b")), ("e2", _LE % ("b", "c"))],
     _LT % ("a", "c"), "nat3"),
    ("core_le_add_l", [("", "w", "Nat"), ("+", "a", "Nat"), ("+", "b", "Nat")], [("e", _LE % ("a", "b"))],
     _LE % ("Nat.add(w, a)", "Nat.add(w, b)"), "nat1"),
    ("core_le_add_left", [("+", "k", "Nat"), ("+", "c", "Nat"), ("+", "d", "Nat")], [("e", _LE % ("c", "d"))],
     _LE % ("c", "Nat.add(k, d)"), "nat1"),
    ("core_le_add_mono", [("", "a", "Nat"), ("", "b", "Nat"), ("+", "c", "Nat"), ("+", "d", "Nat")],
     [("e1", _LE % ("a", "b")), ("e2", _LE % ("c", "d"))], _LE % ("Nat.add(a, c)", "Nat.add(b, d)"), "nat2"),
    ("core_sub_add", [("", "a", "Nat"), ("", "b", "Nat")], [("e", _LE % ("b", "a"))],
     "{Nat.add(b, Nat.sub(a, b)) == a : Nat}", "nat2"),
    ("core_sub_add_of_lt", [("+", "a", "Nat"), ("+", "b", "Nat")], [("e", _LT % ("b", "a"))],
     "{Nat.add(b, Nat.sub(a, b)) == a : Nat}", "compose"),
    # a guard b && x < t falsifies the require !b || t <= x (M1's hand-pasted CORE, now generated)
    ("core_kappa_site", [("", "b", "Bool"), ("+", "x", "Nat"), ("+", "t", "Nat")],
     [("e", "{Bool.and(b, Nat.is_lt(x, t)) == True{} : Bool}")],
     "{Bool.or(Bool.not(b), Nat.is_le(t, x)) == False{} : Bool}", "bool1"),
    ("core_and_lt_add", [("", "b", "Bool"), ("+", "x", "Nat"), ("+", "t", "Nat"), ("+", "dt", "Nat")],
     [("e", "{Bool.and(b, Nat.is_lt(x, t)) == True{} : Bool}")],
     "{Bool.and(b, Nat.is_lt(x, Nat.add(t, dt))) == True{} : Bool}", "bool1"),
    # ---- I15 (SORT-site coercion guards, holon.gen.mproofs.coercion_guard): one passed condition gives the sign
    # obligation of a subtraction, `is_le(subtrahend, minuend)`, by ONE of these (or the earlier guard shapes)
    ("core_le_of_gt", [("", "a", "Nat"), ("", "b", "Nat")], [("e", "{Nat.is_gt(a, b) == True{} : Bool}")],
     _LE % ("b", "a"), "nat2"),
    ("core_le_of_not_le", [("", "a", "Nat"), ("", "b", "Nat")], [("e", "{Nat.is_le(a, b) == False{} : Bool}")],
     _LE % ("b", "a"), "nat2"),
    ("core_one_le_sub_of_not_le", [("", "a", "Nat"), ("", "b", "Nat")], [("e", "{Nat.is_le(a, b) == False{} : Bool}")],
     _LE % ("1n", "Nat.sub(a, b)"), "nat2"),
]

# ---- I42 (Theory core I: 2-categorical whiskering, horizontal/vertical pasting, domain-localized naturality,
# and spanning-tree cycle-basis reduction). Emitted into M3+ core libraries alongside CATALOG.
THEORY_CORE_I: list[tuple[str, list[tuple[str, str, str]], list[tuple[str, str]], str, str]] = [
    ("core_whisker_pre",
     [("-", "X", "Type"), ("-", "A", "Type"), ("-", "B", "Type"),
      ("", "r", "X -> A"), ("-", "p", "A -> B"), ("-", "q", "A -> B")],
     [("e", "@a:A -> {p(a) == q(a) : B}")],
     "@x:X -> {p(r(x)) == q(r(x)) : B}", "core_whisker"),
    ("core_whisker_post",
     [("-", "A", "Type"), ("-", "B", "Type"), ("-", "Y", "Type"),
      ("-", "p", "A -> B"), ("-", "q", "A -> B"), ("-", "l", "B -> Y")],
     [("e", "@a:A -> {p(a) == q(a) : B}")],
     "@a:A -> {l(p(a)) == l(q(a)) : Y}", "core_whisker"),
    ("core_whisker_both",
     [("-", "X", "Type"), ("-", "A", "Type"), ("-", "B", "Type"), ("-", "Y", "Type"),
      ("", "r", "X -> A"), ("-", "p", "A -> B"), ("-", "q", "A -> B"), ("-", "l", "B -> Y")],
     [("e", "@a:A -> {p(a) == q(a) : B}")],
     "@x:X -> {l(p(r(x))) == l(q(r(x))) : Y}", "core_whisker"),
    ("core_walk_2",
     [("-", "A", "Data"), ("-", "B", "Type"), ("-", "C", "Type"),
      ("-", "f1", "A -> B"), ("-", "f2", "A -> B"), ("-", "g1", "B -> C"), ("-", "g2", "B -> C")],
     [("e1", "@a:A -> {f1(a) == f2(a) : B}"),
      ("e2", "@a:A -> {g1(f2(a)) == g2(f2(a)) : C}")],
     "@+a:A -> {g1(f1(a)) == g2(f2(a)) : C}", "core_paste"),
    ("core_walk_3",
     [("-", "A", "Data"), ("-", "B", "Type"), ("-", "C", "Type"), ("-", "D", "Type"),
      ("-", "f1", "A -> B"), ("-", "f2", "A -> B"), ("-", "g1", "B -> C"), ("-", "g2", "B -> C"),
      ("-", "h1", "C -> D"), ("-", "h2", "C -> D")],
     [("e1", "@a:A -> {f1(a) == f2(a) : B}"),
      ("e2", "@a:A -> {g1(f2(a)) == g2(f2(a)) : C}"),
      ("e3", "@a:A -> {h1(g2(f2(a))) == h2(g2(f2(a))) : D}")],
     "@+a:A -> {h1(g1(f1(a))) == h2(g2(f2(a))) : D}", "core_paste"),
    ("core_square_paste_h",
     [("-", "A", "Data"), ("-", "B", "Type"), ("-", "C", "Type"),
      ("", "f1", "A -> B"), ("-", "f2", "A -> B"), ("-", "g1", "B -> C"), ("-", "g2", "B -> C")],
     [("e1", "@a:A -> {f1(a) == f2(a) : B}"),
      ("e2", "@b:B -> {g1(b) == g2(b) : C}")],
     "@+a:A -> {g1(f1(a)) == g2(f2(a)) : C}", "core_paste"),
    ("core_square_paste_v",
     [("-", "A", "Data"), ("-", "B", "Type"),
      ("-", "p", "A -> B"), ("-", "q", "A -> B"), ("-", "s", "A -> B")],
     [("e1", "@a:A -> {p(a) == q(a) : B}"),
      ("e2", "@a:A -> {q(a) == s(a) : B}")],
     "@+a:A -> {p(a) == s(a) : B}", "core_paste"),
    ("core_domain_local_pre",
     [("-", "Z", "Type"), ("-", "X", "Type"), ("-", "A", "Type"), ("-", "B", "Type"),
      ("", "u", "Z -> X"), ("-", "r", "X -> A"), ("-", "p", "A -> B"), ("-", "q", "A -> B")],
     [("e", "@x:X -> {p(r(x)) == q(r(x)) : B}")],
     "@z:Z -> {p(r(u(z))) == q(r(u(z))) : B}", "core_domain_local"),
    ("core_domain_local_post",
     [("-", "X", "Type"), ("-", "A", "Type"), ("-", "B", "Type"), ("-", "Y", "Type"),
      ("-", "r", "X -> A"), ("-", "p", "A -> B"), ("-", "q", "A -> B"), ("-", "l", "B -> Y")],
     [("e", "@x:X -> {p(r(x)) == q(r(x)) : B}")],
     "@x:X -> {l(p(r(x))) == l(q(r(x))) : Y}", "core_domain_local"),
    ("core_domain_local_paste",
     [("-", "X", "Data"), ("-", "A", "Type"), ("-", "B", "Type"),
      ("-", "r", "X -> A"), ("-", "p", "A -> B"), ("-", "q", "A -> B"), ("-", "s", "A -> B")],
     [("e1", "@x:X -> {p(r(x)) == q(r(x)) : B}"),
      ("e2", "@x:X -> {q(r(x)) == s(r(x)) : B}")],
     "@+x:X -> {p(r(x)) == s(r(x)) : B}", "core_domain_local"),
    ("core_tree_unique_2",
     [("-", "A", "Data"), ("-", "B", "Type"), ("-", "C", "Type"),
      ("-", "f", "A -> B"), ("-", "g1", "B -> C"), ("-", "g2", "B -> C"), ("-", "t", "A -> C")],
     [("e1", "@a:A -> {g1(f(a)) == t(a) : C}"),
      ("e2", "@a:A -> {g2(f(a)) == t(a) : C}")],
     "@+a:A -> {g1(f(a)) == g2(f(a)) : C}", "core_basis"),
    ("core_cycle_basis_2",
     [("-", "X", "Data"), ("-", "A", "Type"), ("-", "B", "Type"), ("-", "Y", "Type"),
      ("", "r", "X -> A"), ("-", "t", "A -> B"), ("-", "e", "A -> B"),
      ("-", "l", "B -> Y"), ("-", "obs", "X -> Y")],
     [("cyc", "@a:A -> {t(a) == e(a) : B}"),
      ("tree_law", "@x:X -> {l(t(r(x))) == obs(x) : Y}")],
     "@+x:X -> {l(e(r(x))) == obs(x) : Y}", "core_basis"),
]

_THEORY_CORE_I_CLASSES = ("core_whisker", "core_paste", "core_domain_local", "core_basis")

HELPERS = ["def core_efq(-P: Type, x: Empty) -> P:", "  match x:", "",
           "def core_is_true(b: Bool) -> Type:", "  match b:", "    case True{}:", "      Unit", "    case False{}:", "      Empty", ""]

_SCRUT = {"nat1": 1, "nat2": 2, "nat3": 3, "bool1": 1}
_NATC = [["0n", "1n+p"], ["0n", "1n+q"], ["0n", "1n+r"]]
_CASES = {"nat1": [list(c) for c in itertools.product(*_NATC[:1])],
          "nat2": [list(c) for c in itertools.product(*_NATC[:2])],
          "nat3": [list(c) for c in itertools.product(*_NATC[:3])],
          "bool1": [["True{}"], ["False{}"]],
          "compose": [[]], "absurd": [[]],
          "core_whisker": [[]], "core_paste": [[]], "core_domain_local": [[]], "core_basis": [[]]}
_PRED = {"1n+p": "p", "1n+q": "q", "1n+r": "r"}
MAX_COMPOSE = 12   # composition candidates per case


def _sub(text: str, env: dict) -> str:
    for k, v in env.items():
        text = re.sub(rf"(?<![\w.]){re.escape(k)}(?![\w])", v, text)
    return text


# ---------------------------------------------------------------- Bend terms (the claim subset)
class TermError(Exception):
    pass


_TOK = re.compile(r"\s*(\{\}|==|!=|=>|[{}(),:]|\d+n\+|\d+n|[A-Za-z_][\w.]*)")


def parse(text: str):
    """A term of the claim subset: ("eq"|"ne", a, b, T), ("app", f, args), ("succ", k, t), ("nat", k),
    ("ctor", name) for `Name{}`, ("var", name)."""
    toks, pos = [], 0
    text = text.strip()
    while pos < len(text):
        m = _TOK.match(text, pos)
        if not m:
            raise TermError(f"cannot read {text[pos:pos + 20]!r}")
        toks.append(m.group(1))
        pos = m.end()
    i = 0

    def peek():
        return toks[i] if i < len(toks) else None

    def take(want=None):
        nonlocal i
        t = peek()
        if t is None or (want is not None and t != want):
            raise TermError(f"expected {want!r}, got {t!r}")
        i += 1
        return t

    def term():
        t = take()
        if t == "{":
            a = term()
            op = take()
            if op not in ("==", "!="):
                raise TermError(f"expected == or !=, got {op!r}")
            b = term()
            take(":")
            ty = term()
            take("}")
            return ("eq" if op == "==" else "ne", a, b, ty)
        if re.fullmatch(r"\d+n\+", t):
            return _succ(int(t[:-2]), term())
        if re.fullmatch(r"\d+n", t):
            return ("nat", int(t[:-1]))
        if re.fullmatch(r"[A-Za-z_][\w.]*", t):
            if peek() == "{}":
                take()
                return ("ctor", t)
            if peek() == "(":
                take("(")
                args = []
                if peek() != ")":
                    args.append(term())
                    while peek() == ",":
                        take(",")
                        args.append(term())
                take(")")
                return ("app", t, tuple(args))
            return ("var", t)
        raise TermError(f"unexpected {t!r}")
    out = term()
    if i != len(toks):
        raise TermError(f"trailing tokens in {text!r}")
    return out


def _succ(k: int, t):
    if k == 0:
        return t
    if t[0] == "succ":
        return ("succ", k + t[1], t[2])
    if t[0] == "nat":
        return ("nat", k + t[1])
    return ("succ", k, t)


def render(t) -> str:
    kind = t[0]
    if kind in ("eq", "ne"):
        return f"{{{render(t[1])} {'==' if kind == 'eq' else '!='} {render(t[2])} : {render(t[3])}}}"
    if kind == "app":
        return f"{t[1]}({', '.join(render(a) for a in t[2])})"
    if kind == "succ":
        return "1n+" * t[1] + render(t[2])
    if kind == "nat":
        return f"{t[1]}n"
    if kind == "ctor":
        return t[1] + "{}"
    return t[1]


_TRUE, _FALSE = ("ctor", "True"), ("ctor", "False")
_CMP = {"Nat.is_lt": lambda a, b: a < b, "Nat.is_le": lambda a, b: a <= b, "Nat.is_eq": lambda a, b: a == b,
        "Nat.is_gt": lambda a, b: a > b, "Nat.is_ge": lambda a, b: a >= b}


def _head(t):
    """(successors, rest) of a literal-headed Nat: rest is ("nat", 0) for a literal, else the symbolic part
    under the successors; None when the term is not literal-headed."""
    if t[0] == "nat":
        return t[1], ("nat", 0)
    if t[0] == "succ":
        return t[1], t[2]
    return None


def simp(t):
    """Normalise the reductions Bend performs on literal-headed arguments (an approximation; untrusted)."""
    kind = t[0]
    if kind in ("eq", "ne"):
        return (kind, simp(t[1]), simp(t[2]), t[3])
    if kind == "succ":
        return _succ(t[1], simp(t[2]))
    if kind != "app":
        return t
    f, args = t[1], tuple(simp(a) for a in t[2])
    if f == "Bool.not" and len(args) == 1 and args[0] in (_TRUE, _FALSE):
        return _FALSE if args[0] == _TRUE else _TRUE
    if f in ("Bool.and", "Bool.or") and len(args) == 2 and args[0] in (_TRUE, _FALSE):
        unit = _TRUE if f == "Bool.and" else _FALSE
        return args[1] if args[0] == unit else args[0]
    if f == "Nat.add" and len(args) == 2 and _head(args[0]):
        k, rest = _head(args[0])
        inner = args[1] if rest == ("nat", 0) else simp(("app", "Nat.add", (rest, args[1])))
        return _succ(k, inner)
    if f == "Nat.sub" and len(args) == 2 and _head(args[0]) and _head(args[1]):
        (k, a), (j, b) = _head(args[0]), _head(args[1])
        m = min(k, j)
        a, b = _succ(k - m, a), _succ(j - m, b)
        if a == ("nat", 0):
            return a
        if b == ("nat", 0):
            return a
        return ("app", "Nat.sub", (a, b))
    if f in _CMP and len(args) == 2 and _head(args[0]) and _head(args[1]):
        # Nat.cmp matches both arguments: peel common successors; decided once one side is 0n and the other
        # is 0n or a successor, stuck on a symbolic side
        (k, a), (j, b) = _head(args[0]), _head(args[1])
        m = min(k, j)
        a, b = _succ(k - m, a), _succ(j - m, b)
        sa, sb = _sign(a), _sign(b)
        if sa is not None and sb is not None:
            return _TRUE if _CMP[f](sa, sb) else _FALSE
        return ("app", f, (a, b))
    return ("app", f, args)


def _sign(t) -> int | None:
    """0 for the literal 0n, 1 for a successor, None for a symbolic Nat."""
    if t == ("nat", 0):
        return 0
    h = _head(t)
    return 1 if h and h[0] >= 1 else None


def match(pat, t, pvars: set, sub: dict) -> dict | None:
    """First-order matching of pattern `pat` (variables `pvars`) against term t, extending `sub`."""
    if pat[0] == "var" and pat[1] in pvars:
        if pat[1] in sub:
            return sub if render(simp(sub[pat[1]])) == render(simp(t)) else None
        return {**sub, pat[1]: t}
    if pat[0] == "succ":
        h = _head(t)
        if h is None or h[0] < pat[1]:
            return None
        return match(pat[2], _succ(h[0] - pat[1], h[1]), pvars, sub)
    if pat[0] != t[0]:
        if pat[0] == "nat" and _head(t):
            k, rest = _head(t)
            return sub if (rest == ("nat", 0) and k == pat[1]) else None
        return None
    if pat[0] in ("nat", "ctor") or pat[0] == "var":
        return sub if pat == t else None
    if pat[0] == "app":
        if pat[1] != t[1] or len(pat[2]) != len(t[2]):
            return None
        for p, x in zip(pat[2], t[2]):
            sub = match(p, x, pvars, sub)
            if sub is None:
                return None
        return sub
    for p, x in zip(pat[1:], t[1:]):   # eq / ne
        sub = match(p, x, pvars, sub)
        if sub is None:
            return None
    return sub


def subst(t, sub: dict):
    if t[0] == "var" and t[1] in sub:
        return sub[t[1]]
    if t[0] == "app":
        return ("app", t[1], tuple(subst(a, sub) for a in t[2]))
    if t[0] == "succ":
        return _succ(t[1], subst(t[2], sub))
    if t[0] in ("eq", "ne"):
        return (t[0],) + tuple(subst(x, sub) for x in t[1:])
    return t


def _vars(t) -> set:
    if t[0] == "var":
        return {t[1]}
    if t[0] == "app":
        return set().union(set(), *(_vars(a) for a in t[2]))
    if t[0] == "succ":
        return _vars(t[2])
    if t[0] in ("eq", "ne"):
        return set().union(*(_vars(x) for x in t[1:3]))
    return set()


def _matches(pat, t, pvars: set, sub: dict) -> dict | None:
    """Match the pattern (normalised under `sub`) against the term as written, then against its normal form."""
    p = simp(subst(pat, sub))
    out = match(p, t, pvars, sub)
    return out if out is not None else match(p, simp(t), pvars, sub)


def _pattern(text: str, names) -> tuple:
    """A lemma's statement as a pattern: its binders renamed apart (`?x`), so they never meet a goal's names."""
    return subst(parse(text), {n: ("var", "?" + n) for n in names})


def compositions(goal: str, sources: list, lemmas: list, prefix: str, depth: int = 2, limit: int = MAX_COMPOSE) -> list[str]:
    """Calls of `lemmas` (catalog entries) proving `goal`: binders by matching the lemma's claim against the
    goal, then its hypotheses against `sources` [(term text, type text)] or, below depth, by a call of
    another of `lemmas`. Every binder must be determined. Untrusted: Bend checks every candidate."""
    try:
        g = parse(goal)
        srcs = [(st, parse(sty)) for st, sty in sources]
    except TermError:
        return []
    out: list[str] = []
    for name, bs, hs, claim, cls in lemmas:
        if cls == "absurd" or len(out) >= limit:
            continue
        names = [n for _, n, _ in bs]
        pv = {"?" + n for n in names}
        try:
            pat, wants = _pattern(claim, names), [_pattern(ht, names) for _, ht in hs]
        except TermError:
            continue
        sub0 = _matches(pat, g, pv, {})
        if sub0 is None:
            continue

        def fill(k: int, sub: dict, args: list):
            if len(out) >= limit:
                return
            if k == len(hs):
                if pv <= set(sub):
                    call = f"{prefix}{name}({', '.join([render(sub['?' + n]) for n in names] + args)})"
                    if call not in out:
                        out.append(call)
                return
            for st, sty in srcs:
                s2 = _matches(wants[k], sty, pv, sub)
                if s2 is not None:
                    fill(k + 1, s2, args + [st])
            if depth > 1 and _vars(wants[k]) & pv <= set(sub):
                for c in compositions(render(simp(subst(wants[k], sub))), sources, [x for x in lemmas if x[0] != name],
                                      prefix, depth - 1, limit):
                    fill(k + 1, sub, args + [c])
        fill(0, sub0, [])
    return out


def laws_text(include_theory_core_i: bool = False) -> str:
    out = ["# GENERATED by holon.gen.core: the core library's statements (Q14a: proofs come from per-class",
           "# generators, never by hand). Import core/PROOF.bend, never this file alone.", "import Base", ""]
    entries = CATALOG + (THEORY_CORE_I if include_theory_core_i else [])
    for name, bs, hs, claim, _ in entries:
        out.append(f"law {name}:")
        out += [f"  for {mo}{n}: {t}" for mo, n, t in bs] + [f"  for {n}: {t}" for n, t in hs] + [f"  {claim}", ""]
    return "\n".join(out).rstrip() + "\n"


_PI_EQ_CLAIM = re.compile(r"^@(\+?)(\w+):(\S+)\s*->\s*\{(.+)\s*==\s*(.+)\s*:\s*(.+)\}$")


class _Lemma:
    def __init__(self, entry, prefix: str, earlier: list):
        self.name, self.bs, self.hs, self.claim, self.cls = entry
        self.prefix = prefix   # "Laws." (core PROOF) or "" (pasted)
        self.earlier = earlier  # the catalog entries before this one (composition candidates)
        self.cases = _CASES[self.cls]
        self._cands: dict = {}
        k = _SCRUT.get(self.cls, 0)
        taken = {n for _, n, _ in self.bs[k:]} | {n for n, _ in self.hs}
        if k and (taken & set(_PRED.values())):
            raise ValueError(f"core: {self.name} binds a predecessor name {sorted(taken & set(_PRED.values()))}")

    def candidates(self, case: list) -> list[str]:
        key = tuple(case)
        if key not in self._cands:
            self._cands[key] = self._candidates(case)
        return self._cands[key]

    def _theory_core_i_candidates(self) -> list[str]:
        m = _PI_EQ_CLAIM.fullmatch(self.claim.strip())
        if not m:
            raise ValueError(f"core: unsupported Theory core I claim shape: {self.claim!r}")
        v_mod, v, _v_ty, lhs, rhs, ret_ty = m.groups()
        unerased = [n for mo, n, _ in self.bs if mo == ""]
        if self.cls == "core_whisker":
            hn = self.hs[0][0]
            last_fn = self.bs[-1][1]
            if lhs.startswith(f"{last_fn}("):
                arg = f"{unerased[0]}({v})" if unerased else v
                return [f"{v} => (%{hn}({arg}) : {{{lhs} == {last_fn}(_) : {ret_ty}}}; {{==}})"]
            return [f"{v} => {hn}({unerased[0]}({v}))"]
        if self.cls == "core_paste":
            if len(self.hs) == 3:
                e1, e2, e3 = (h[0] for h in self.hs)
                g1, h1 = self.bs[6][1], self.bs[8][1]
                return [f"{v_mod}{v} => (%{e3}({v}) : {{{lhs} == _ : {ret_ty}}}; "
                        f"(%{e2}({v}) : {{{lhs} == {h1}(_) : {ret_ty}}}; "
                        f"(%{e1}({v}) : {{{lhs} == {h1}({g1}(_)) : {ret_ty}}}; {{==}})))"]
            e1, e2 = (h[0] for h in self.hs)
            if len(self.bs) == 5:
                return [f"{v_mod}{v} => (%{e2}({v}) : {{{lhs} == _ : {ret_ty}}}; {e1}({v}))"]
            if unerased:
                f1, g2 = unerased[0], self.bs[-1][1]
                return [f"{v_mod}{v} => (%{e1}({v}) : {{{lhs} == {g2}(_) : {ret_ty}}}; {e2}({f1}({v})))"]
            g1 = self.bs[-2][1]
            return [f"{v_mod}{v} => (%{e2}({v}) : {{{lhs} == _ : {ret_ty}}}; "
                    f"(%{e1}({v}) : {{{lhs} == {g1}(_) : {ret_ty}}}; {{==}}))"]
        if self.cls == "core_domain_local":
            if len(self.hs) == 2:
                e1, e2 = (h[0] for h in self.hs)
                return [f"{v_mod}{v} => (%{e2}({v}) : {{{lhs} == _ : {ret_ty}}}; {e1}({v}))"]
            hn = self.hs[0][0]
            if unerased:
                return [f"{v} => {hn}({unerased[0]}({v}))"]
            last_fn = self.bs[-1][1]
            return [f"{v} => (%{hn}({v}) : {{{lhs} == {last_fn}(_) : {ret_ty}}}; {{==}})"]
        if self.cls == "core_basis":
            e1, e2 = (h[0] for h in self.hs)
            if unerased:
                r_fn, l_fn = unerased[0], self.bs[-2][1]
                return [f"{v_mod}{v} => (%{e1}({r_fn}({v})) : {{{l_fn}(_) == {rhs} : {ret_ty}}}; {e2}({v}))"]
            t_fn = self.bs[-1][1]
            return [f"{v_mod}{v} => (%{{(%{e2}({v}) : {{_ == {rhs} : {ret_ty}}}; {{==}}) : "
                    f"{{{t_fn}({v}) == {rhs} : {ret_ty}}}}} : {{{lhs} == _ : {ret_ty}}}; {e1}({v}))"]
        raise ValueError(f"core: unknown Theory core I class: {self.cls!r}")

    def _candidates(self, case: list) -> list[str]:
        if self.cls in _THEORY_CORE_I_CLASSES:
            return self._theory_core_i_candidates()
        if self.cls == "absurd":
            return ["(%Equal.sym(Bool, False{}, True{}, e) : core_is_true(_); Unit{})"]
        k = len(case)
        env = {n: c for (_, n, _), c in zip(self.bs[:k], case)}
        goal = _sub(self.claim, env)
        out = ["{==}"]
        sources = []
        for hn, ht in self.hs:
            out.append(hn)
            sources.append((hn, _sub(ht, env)))
            if "!=" in ht:
                out.append(f"core_efq({goal}, {hn}({{==}}))")
            else:
                out.append(f"core_efq({goal}, {self.prefix}core_false_ne_true({hn}))")
                if ht.rstrip().endswith("== False{} : Bool}"):   # {X == False{}} where X computes to True{} (I15)
                    out.append(f"core_efq({goal}, {self.prefix}core_false_ne_true(Equal.sym(Bool, True{{}}, False{{}}, {hn})))")
        if k and all(c in _PRED for c in case):   # induction hypothesis at the predecessors
            args = [_PRED[c] for c in case] + [n for _, n, _ in self.bs[k:]]
            hargs = []
            for hn, ht in self.hs:
                if "!=" in ht:   # transport a != b to the successors
                    a, b = (_PRED[c] for c in case[:2])
                    hargs.append(f"(z => {hn}((%z : {{1n+{a} == 1n+_ : Nat}}; {{==}})))")
                else:
                    hargs.append(hn)
            ih = f"{self.prefix}{self.name}({', '.join(args + hargs)})"
            out.append(ih)
            ih_ty = _sub(self.claim, {n: _PRED[c] for (_, n, _), c in zip(self.bs[:k], case)})
            sources.append((ih, ih_ty))
            try:   # a Nat equation: the induction hypothesis under the successor
                eq = parse(ih_ty)
                if eq[0] == "eq" and eq[3] == ("var", "Nat"):
                    lhs, rhs = render(eq[1]), render(eq[2])
                    out.append(f"(%{ih} : {{1n+{lhs} == 1n+_ : Nat}}; {{==}})")
            except TermError:
                pass
        out += [c for c in compositions(goal, sources, self.earlier, self.prefix) if c not in out]
        return out

    def body(self, choice: list[int], indent: str = "  ") -> tuple[list[str], list[int]]:
        """Lines of the body and, per case, the index of the line holding its chosen term."""
        if self.cls in ("absurd", "compose", *_THEORY_CORE_I_CLASSES):
            return [indent + self.candidates([])[choice[0]]], [0]
        k = len(self.cases[0])
        scrut = " ".join(n for _, n, _ in self.bs[:k])
        lines, at = [f"{indent}match {scrut}:"], []
        for c, ch in zip(self.cases, choice):
            lines.append(f"{indent}  case {' '.join(c)}:")
            at.append(len(lines))
            lines.append(f"{indent}    {self.candidates(c)[ch]}")
        return lines, at

    def n_slots(self) -> int:
        return len(self.cases)

    def n_cands(self, i: int) -> int:
        return len(self.candidates(self.cases[i]))


def lemmas(prefix: str, include_theory_core_i: bool = False) -> list[_Lemma]:
    entries = CATALOG + (THEORY_CORE_I if include_theory_core_i else [])
    return [_Lemma(e, prefix, entries[:i]) for i, e in enumerate(entries)]


def _proof_text(lems: list, choices: dict, omit: str | None = None) -> tuple[str, dict]:
    out = ["# GENERATED by holon.gen.core: per-class proofs, each case chosen from the class's candidates and",
           "# accepted only if Bend checks it.", "import Base", "import ./LAWS.bend as Laws", ""] + HELPERS
    where = {}
    for L in lems:
        if L.name == omit:
            out += [f"# {L.name}: left unproved (canary)", ""]
            continue
        out.append(f"# class {L.cls}")
        params = [n for _, n, _ in L.bs] + [n for n, _ in L.hs]
        out.append(f"def Laws.{L.name}({', '.join(params)}):")
        lines, at = L.body(choices[L.name])
        base = len(out)
        out += lines + [""]
        for i, a in enumerate(at):   # 1-based line numbers: the chosen term, and the case pattern above it
            where[base + a + 1] = where[base + a] = (L.name, i)   # (Bend reports a reused pattern binder there)
    return "\n".join(out).rstrip() + "\n", where


_ERR_LINE = re.compile(r"^\s*(\d+)>\|", re.M)


def catalog_key() -> str:
    """The cache key of the solved choices: the catalog, the helpers and this generator's source."""
    src = Path(__file__).read_bytes()
    return hashlib.sha256(json.dumps(CATALOG).encode() + "\n".join(HELPERS).encode() + src).hexdigest()[:16]


def solve(work: Path, cfg: dict | None = None, max_tries: int = 600) -> dict:
    """Per-lemma case choices that Bend accepts (cached by catalog hash in the build dir)."""
    cache = bend.build_dir(Path(__file__).resolve().parents[2]) / "core" / f"choices-{catalog_key()}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    lems = lemmas("Laws.")
    choices = {L.name: [0] * L.n_slots() for L in lems}
    d = Path(work) / "core"
    d.mkdir(parents=True, exist_ok=True)
    (d / "LAWS.bend").write_text(laws_text())
    for _ in range(max_tries):
        text, where = _proof_text(lems, choices)
        (d / "PROOF.bend").write_text(text)
        r = bend.check(d / "PROOF.bend", cfg)
        if r.ok:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(choices, sort_keys=True))
            return choices
        m = _ERR_LINE.search(r.out)
        slot = where.get(int(m.group(1))) if m else None
        if slot is None:
            raise RuntimeError(f"core: Bend rejected a line outside the case slots: {r.out[:600]}")
        name, i = slot
        L = next(x for x in lems if x.name == name)
        choices[name][i] += 1
        if choices[name][i] >= L.n_cands(i):
            raise RuntimeError(f"core: no candidate proves {name} case {i}: {r.out[:600]}")
    raise RuntimeError("core: search budget exhausted")


def emit(gen_dir: Path, omit: str | None = None, cfg: dict | None = None,
         include_theory_core_i: bool | None = None) -> list[str]:
    """Write <gen_dir>/core/{LAWS.bend, PROOF.bend}; `omit` leaves that law unproved (the G4 canary)."""
    gen_dir = Path(gen_dir)
    if include_theory_core_i is None:
        include_theory_core_i = any(re.fullmatch(r"M([3-9]|\d\d+)", part) for part in gen_dir.parts)
    choices = dict(solve(gen_dir, cfg))
    if include_theory_core_i:
        for name, *_ in THEORY_CORE_I:
            choices[name] = [0]
    d = gen_dir / "core"
    d.mkdir(parents=True, exist_ok=True)
    (d / "LAWS.bend").write_text(laws_text(include_theory_core_i=include_theory_core_i))
    text, _ = _proof_text(lemmas("Laws.", include_theory_core_i=include_theory_core_i), choices, omit)
    (d / "PROOF.bend").write_text(text)
    entries = CATALOG + (THEORY_CORE_I if include_theory_core_i else [])
    return [e[0] for e in entries]


def paste_text(gen_dir: Path, cfg: dict | None = None) -> str:
    """The same lemmas as plain defs, for `holon run --core paste` (the cost baseline): every core
    lemma is checked inside each importing file instead of through the import."""
    choices = solve(gen_dir, cfg)
    out = ["# core library, pasted (holon run --core paste)"] + HELPERS
    for L in lemmas(""):
        sig = [f"{mo}{n}: {t}" for mo, n, t in L.bs] + [f"{n}: {t}" for n, t in L.hs]
        out.append(f"def {L.name}({', '.join(sig)}) -> {L.claim}:")
        out += L.body(choices[L.name])[0] + [""]
    return "\n".join(out).rstrip() + "\n"


def calls(text: str) -> list[str]:
    """The core lemmas a generated proof calls through the core LAWS alias (`C.core_*`), in first-call order."""
    out: list[str] = []
    for n in re.findall(r"(?<![\w.])C\.(core_\w+)\(", text):
        if n not in out:
            out.append(n)
    return out


_IMPORT = re.compile(r"^\s*import\s+(\S*core/(LAWS|PROOF)\.bend)\b", re.M)


def bare_laws_imports(text: str) -> list[str]:
    """Lines importing a core LAWS module without importing the core PROOF beside it (G3)."""
    found = _IMPORT.findall(text)
    proofs = {p.rsplit("/", 1)[0] for p, kind in found if kind == "PROOF"}
    return [f"import {p}" for p, kind in found if kind == "LAWS" and p.rsplit("/", 1)[0] not in proofs]
