"""Order lemmas over the typed model's words, generated once and checked in every DISCH proof file that uses them
(BUILD_PLAN I31: "time monotonicity, over the typed model's words (core lemmas of gen/M3/core, proved, never
assumed)"; the arithmetic comparison facts chain_revert needs). Nothing is assumed: every lemma below is a Bend
definition checked by bend2 and BendTT with the proof that imports it.

The lemmas, bottom up:

  cflip, ccomb, cok          Cmp helpers: the flipped comparison, the composition of two comparisons (a ? b, b ? c gives
                             a ? c) and when it is defined (not LT then GT, not GT then LT)
  cmp_flip(n, a, b)          Word.cmp(n, b, a) == cflip(Word.cmp(n, a, b))           induction on the width
  cmp_trans(n, a, b, c, ok)  Word.cmp(n, a, c) == ccomb(Word.cmp(n, a, b), Word.cmp(n, b, c)) when cok holds
                             (each step of the induction is a generated case table over the head bits and the tails'
                             comparisons: _fin_trans, _fin_flip)
  ucmp, u_flip, u_trans      the same over U32 (U32.cmp is Word.cmp over 32 bits)
  wcmp(a, b)                 the lexicographic comparison of two words' limbs (limb 7 most significant)
  w_lt_cmp(a, b)             M.w_lt(a, b) == Cmp.is_lt(wcmp(a, b))                   (u_lt2 against lex, per limb)
  w_flip, w_trans            wcmp's flip and composition, from the limbs'
  w_lt_le(a, b, c)           a < b and not c < b give a < c   (a < b <= c)
  w_le_lt(a, b, c)           not b < a and b < c give a < c   (a <= b < c)
  w_le_le(a, b, c)           not b < a and not c < b give not c < a   (a <= b <= c)

M.w_lt is the typed model's prelude (holon.sorts.prelude3): u_lt2 nested over limbs 7..1 with U32.is_lt on limb 0; a
model whose prelude differs makes the proof fail to check, never a lemma hold by assumption.
"""
from __future__ import annotations

import itertools

CMPS = ("LT", "EQ", "GT")


def _flip(c: str) -> str:
    return {"LT": "GT", "EQ": "EQ", "GT": "LT"}[c]


def _comb(a: str, b: str) -> str:
    """a ? b and b ? c give a ? c (EQ is neutral; LT with LT is LT; LT with GT is undefined, given as EQ)."""
    if a == "EQ":
        return b
    if b == "EQ":
        return a
    return a if a == b else "EQ"


def _ok(a: str, b: str) -> bool:
    return not ({a, b} == {"LT", "GT"})


def _bcmp(x: bool, y: bool) -> str:
    """Bool.cmp (False < True)."""
    if x == y:
        return "EQ"
    return "LT" if (not x and y) else "GT"


def _fin(x: bool, y: bool, r: str) -> str:
    """Word.cmp.fin(x, y, r): the tail's comparison r unless it is EQ, then the head bits'."""
    return r if r != "EQ" else _bcmp(x, y)


def _b(x: bool) -> str:
    return "True{}" if x else "False{}"


def _c(c: str) -> str:
    return c + "{}"


def _fin_trans() -> str:
    """_fin_trans(x, y, z, r1, r2, r3, ih, ok): the step of cmp_trans by cases (216)."""
    lines = ["def _fin_trans(x: Bool, y: Bool, z: Bool, r1: Cmp, r2: Cmp, r3: Cmp, "
             "ih: {cok(r1, r2) == True{} : Bool} -> {r3 == ccomb(r1, r2) : Cmp}, "
             "ok: {cok(Word.cmp.fin(x, y, r1), Word.cmp.fin(y, z, r2)) == True{} : Bool}) -> "
             "{Word.cmp.fin(x, z, r3) == ccomb(Word.cmp.fin(x, y, r1), Word.cmp.fin(y, z, r2)) : Cmp}:",
             "  match x y z r1 r2 r3:"]
    for x, y, z in itertools.product((True, False), repeat=3):
        for r1, r2, r3 in itertools.product(CMPS, repeat=3):
            f1, f2 = _fin(x, y, r1), _fin(y, z, r2)
            goal = "{Word.cmp.fin(%s, %s, %s) == ccomb(Word.cmp.fin(%s, %s, %s), Word.cmp.fin(%s, %s, %s)) : Cmp}" % (
                _b(x), _b(z), _c(r3), _b(x), _b(y), _c(r1), _b(y), _b(z), _c(r2))
            if not _ok(f1, f2):
                body = f"efq({goal}, false_ne_true(ok))"
            elif _ok(r1, r2) and r3 != _comb(r1, r2):
                body = f"efq({goal}, cmp_ne_{r3}_{_comb(r1, r2)}(ih({{==}})))"
            else:
                if _fin(x, z, r3) != _comb(f1, f2):   # the case table is wrong: never emit a false {==}
                    raise AssertionError(("fin_trans", x, y, z, r1, r2, r3))
                body = "{==}"
            lines.append(f"    case {_b(x)} {_b(y)} {_b(z)} {_c(r1)} {_c(r2)} {_c(r3)}:\n      {body}")
    return "\n".join(lines) + "\n"


def _fin_flip() -> str:
    lines = ["def _fin_flip(x: Bool, y: Bool, r: Cmp, s: Cmp, ih: {s == cflip(r) : Cmp}) -> "
             "{Word.cmp.fin(y, x, s) == cflip(Word.cmp.fin(x, y, r)) : Cmp}:",
             "  match x y r s:"]
    for x, y in itertools.product((True, False), repeat=2):
        for r, s in itertools.product(CMPS, repeat=2):
            goal = "{Word.cmp.fin(%s, %s, %s) == cflip(Word.cmp.fin(%s, %s, %s)) : Cmp}" % (
                _b(y), _b(x), _c(s), _b(x), _b(y), _c(r))
            if s != _flip(r):
                body = f"efq({goal}, cmp_ne_{s}_{_flip(r)}(ih))"
            else:
                if _fin(y, x, s) != _flip(_fin(x, y, r)):
                    raise AssertionError(("fin_flip", x, y, r, s))
                body = "{==}"
            lines.append(f"    case {_b(x)} {_b(y)} {_c(r)} {_c(s)}:\n      {body}")
    return "\n".join(lines) + "\n"


def _cmp_ne() -> str:
    out = ["def is_cmp(a: Cmp, b: Cmp) -> Type:\n  match a b:\n" + "".join(
        f"    case {_c(x)} {_c(y)}:\n      {'Unit' if x == y else 'Empty'}\n" for x in CMPS for y in CMPS)]
    for x in CMPS:
        for y in CMPS:
            if x != y:
                out.append(f"def cmp_ne_{x}_{y}(e: {{{_c(x)} == {_c(y)} : Cmp}}) -> Empty:\n"
                           f"  (%Equal.sym(Cmp, {_c(x)}, {_c(y)}, e) : is_cmp(_, {_c(y)})\n  Unit{{}})\n")
    return "\n".join(out)


def _table(name: str, args: list, fn) -> str:
    """def name(a: Cmp, b: Cmp..) -> Cmp|Bool by cases."""
    ps = ", ".join(f"{a}: Cmp" for a in args)
    rows = []
    for vals in itertools.product(CMPS, repeat=len(args)):
        rows.append(f"    case {' '.join(_c(v) for v in vals)}:\n      {fn(*vals)}")
    ret = "Bool" if name == "cok" else "Cmp"
    return f"def {name}({ps}) -> {ret}:\n  match {' '.join(args)}:\n" + "\n".join(rows) + "\n"


def _lex_tables() -> str:
    """lex(hi, lo): hi unless it is EQ, then lo; its flip and composition steps (by cases on Cmp values)."""
    out = ["def lex(hi: Cmp, lo: Cmp) -> Cmp:\n  match hi:\n    case LT{}:\n      LT{}\n    case EQ{}:\n      lo\n"
           "    case GT{}:\n      GT{}\n"]
    # _lex_trans(h1, h2, h3, l1, l2, l3, ihh, ihl, ok)
    lines = ["def _lex_trans(h1: Cmp, h2: Cmp, h3: Cmp, l1: Cmp, l2: Cmp, l3: Cmp, "
             "ihh: {cok(h1, h2) == True{} : Bool} -> {h3 == ccomb(h1, h2) : Cmp}, "
             "ihl: {cok(l1, l2) == True{} : Bool} -> {l3 == ccomb(l1, l2) : Cmp}, "
             "ok: {cok(lex(h1, l1), lex(h2, l2)) == True{} : Bool}) -> "
             "{lex(h3, l3) == ccomb(lex(h1, l1), lex(h2, l2)) : Cmp}:",
             "  match h1 h2 h3 l1 l2 l3:"]
    lexf = lambda h, l: l if h == "EQ" else h   # noqa: E731
    for h1, h2, h3, l1, l2, l3 in itertools.product(CMPS, repeat=6):
        f1, f2 = lexf(h1, l1), lexf(h2, l2)
        goal = "{lex(%s, %s) == ccomb(lex(%s, %s), lex(%s, %s)) : Cmp}" % (
            _c(h3), _c(l3), _c(h1), _c(l1), _c(h2), _c(l2))
        if not _ok(f1, f2):
            body = f"efq({goal}, false_ne_true(ok))"
        elif _ok(h1, h2) and h3 != _comb(h1, h2):
            body = f"efq({goal}, cmp_ne_{h3}_{_comb(h1, h2)}(ihh({{==}})))"
        elif h1 == "EQ" and h2 == "EQ" and _ok(l1, l2) and l3 != _comb(l1, l2) and h3 == "EQ":
            body = f"efq({goal}, cmp_ne_{l3}_{_comb(l1, l2)}(ihl({{==}})))"
        else:
            if lexf(h3, l3) != _comb(f1, f2):
                raise AssertionError(("lex_trans", h1, h2, h3, l1, l2, l3))
            body = "{==}"
        lines.append(f"    case {_c(h1)} {_c(h2)} {_c(h3)} {_c(l1)} {_c(l2)} {_c(l3)}:\n      {body}")
    out.append("\n".join(lines) + "\n")
    lines = ["def _lex_flip(h: Cmp, l: Cmp, hs: Cmp, ls: Cmp, ihh: {hs == cflip(h) : Cmp}, ihl: {ls == cflip(l) : Cmp}) "
             "-> {lex(hs, ls) == cflip(lex(h, l)) : Cmp}:", "  match h l hs ls:"]
    for h, l, hs, ls in itertools.product(CMPS, repeat=4):
        goal = "{lex(%s, %s) == cflip(lex(%s, %s)) : Cmp}" % (_c(hs), _c(ls), _c(h), _c(l))
        if hs != _flip(h):
            body = f"efq({goal}, cmp_ne_{hs}_{_flip(h)}(ihh))"
        elif ls != _flip(l) and h == "EQ":
            body = f"efq({goal}, cmp_ne_{ls}_{_flip(l)}(ihl))"
        else:
            if lexf(hs, ls) != _flip(lexf(h, l)):
                raise AssertionError(("lex_flip", h, l, hs, ls))
            body = "{==}"
        lines.append(f"    case {_c(h)} {_c(l)} {_c(hs)} {_c(ls)}:\n      {body}")
    out.append("\n".join(lines) + "\n")
    # u_lt2(a, b, lo) against lex: given U32.is_lt(a, b) == Cmp.is_lt(c), U32.is_eq(a, b) == Cmp.is_eq(c) for c the
    # limbs' comparison, and lo == Cmp.is_lt(l)
    out.append("def _ult2_lex(c: Cmp, +l: Cmp, +lt: Bool, +eq: Bool, +lo: Bool, elt: {lt == Cmp.is_lt(c) : Bool}, "
               "eeq: {eq == Cmp.is_eq(c) : Bool}, elo: {lo == Cmp.is_lt(l) : Bool}) -> "
               "{Bool.or(lt, Bool.and(eq, lo)) == Cmp.is_lt(lex(c, l)) : Bool}:\n"
               "  match c:\n"
               "    case LT{}:\n      %Equal.sym(Bool, lt, True{}, elt) : {Bool.or(_, Bool.and(eq, lo)) == True{} : Bool}\n      {==}\n"
               "    case EQ{}:\n      %Equal.sym(Bool, lt, False{}, elt) : {Bool.or(_, Bool.and(eq, lo)) == Cmp.is_lt(l) : Bool}\n"
               "      %Equal.sym(Bool, eq, True{}, eeq) : {Bool.or(False{}, Bool.and(_, lo)) == Cmp.is_lt(l) : Bool}\n"
               "      elo\n"
               "    case GT{}:\n      %Equal.sym(Bool, lt, False{}, elt) : {Bool.or(_, Bool.and(eq, lo)) == False{} : Bool}\n"
               "      %Equal.sym(Bool, eq, False{}, eeq) : {Bool.or(False{}, Bool.and(_, lo)) == False{} : Bool}\n"
               "      {==}\n")
    return "\n".join(out)


def text(prefix: str = "M.", structural: bool = False) -> str:
    """The library, for a proof file that imports the typed model as `prefix` (M.)."""
    W = f"{prefix}W"
    parts = [
        "# ---- word order (holon.disch.order: generic, proved here, never assumed)",
        "def cflip(a: Cmp) -> Cmp:\n  match a:\n    case LT{}:\n      GT{}\n    case EQ{}:\n      EQ{}\n"
        "    case GT{}:\n      LT{}\n",
        _table("ccomb", ["a", "b"], lambda a, b: _c(_comb(a, b))),
        _table("cok", ["a", "b"], lambda a, b: _b(_ok(a, b))),
        _cmp_ne(),
        _fin_trans(),
        _fin_flip(),
        "def cmp_trans(+n: Nat, a: Word(n), b: Word(n), c: Word(n), ok: {cok(Word.cmp(n, a, b), Word.cmp(n, b, c)) == "
        "True{} : Bool}) -> {Word.cmp(n, a, c) == ccomb(Word.cmp(n, a, b), Word.cmp(n, b, c)) : Cmp}:\n"
        "  match n:\n    case 0n:\n      {==}\n    case 1n+p:\n      match a b c:\n"
        "        case WCon{x, +at} WCon{y, +bt} WCon{z, +ct}:\n"
        "          _fin_trans(x, y, z, Word.cmp(p, at, bt), Word.cmp(p, bt, ct), Word.cmp(p, at, ct), "
        "o => cmp_trans(p, at, bt, ct, o), ok)\n",
        "def cmp_flip(+n: Nat, a: Word(n), b: Word(n)) -> {Word.cmp(n, b, a) == cflip(Word.cmp(n, a, b)) : Cmp}:\n"
        "  match n:\n    case 0n:\n      {==}\n    case 1n+p:\n      match a b:\n"
        "        case WCon{x, +at} WCon{y, +bt}:\n"
        "          _fin_flip(x, y, Word.cmp(p, at, bt), Word.cmp(p, bt, at), cmp_flip(p, at, bt))\n",
        "def u_trans(a: U32, b: U32, c: U32, ok: {cok(U32.cmp(a, b), U32.cmp(b, c)) == True{} : Bool}) -> "
        "{U32.cmp(a, c) == ccomb(U32.cmp(a, b), U32.cmp(b, c)) : Cmp}:\n"
        "  match a b c:\n    case U32{x} U32{y} U32{z}:\n      cmp_trans(32n, x, y, z, ok)\n",
        "def u_flip(a: U32, b: U32) -> {U32.cmp(b, a) == cflip(U32.cmp(a, b)) : Cmp}:\n"
        "  match a b:\n    case U32{x} U32{y}:\n      cmp_flip(32n, x, y)\n",
        _lex_tables(),
    ]
    # wcmp over the limbs, limb 7 most significant
    ab = ", ".join(f"+a{i}" for i in range(8))
    bb = ", ".join(f"+b{i}" for i in range(8))
    cb = ", ".join(f"+c{i}" for i in range(8))

    def lexn(x, y, top=7):
        t = f"U32.cmp({x}0, {y}0)"
        for i in range(1, top + 1):
            t = f"lex(U32.cmp({x}{i}, {y}{i}), {t})"
        return t
    parts.append(f"def wcmp(a: {W}, b: {W}) -> Cmp:\n  match a b:\n    case {W}{{{ab}}} {W}{{{bb}}}:\n      {lexn('a', 'b')}\n")
    # w_lt == is_lt(wcmp): u_lt2 nested; level i proves u_lt2(a_i, b_i, inner) == is_lt(lex(cmp_i, inner_lex))
    lt0 = "U32.is_lt(a0, b0)"
    inner, inner_lex, proof = lt0, "U32.cmp(a0, b0)", "{==}"
    for i in range(1, 8):
        proof = (f"_ult2_lex(U32.cmp(a{i}, b{i}), {inner_lex}, U32.is_lt(a{i}, b{i}), U32.is_eq(a{i}, b{i}), "
                 f"{inner}, {{==}}, {{==}}, {proof})")
        inner = f"{prefix}u_lt2(a{i}, b{i}, {inner})"
        inner_lex = f"lex(U32.cmp(a{i}, b{i}), {inner_lex})"
    parts.append(f"def w_lt_cmp(a: {W}, b: {W}) -> {{{prefix}w_lt(a, b) == Cmp.is_lt(wcmp(a, b)) : Bool}}:\n"
                 f"  match a b:\n    case {W}{{{ab}}} {W}{{{bb}}}:\n      {proof}\n")
    # w_flip: wcmp(b, a) == cflip(wcmp(a, b))
    pf = "u_flip(a0, b0)"
    lx, lxs = "U32.cmp(a0, b0)", "U32.cmp(b0, a0)"
    for i in range(1, 8):
        pf = f"_lex_flip(U32.cmp(a{i}, b{i}), {lx}, U32.cmp(b{i}, a{i}), {lxs}, u_flip(a{i}, b{i}), {pf})"
        lx, lxs = f"lex(U32.cmp(a{i}, b{i}), {lx})", f"lex(U32.cmp(b{i}, a{i}), {lxs})"
    parts.append(f"def w_flip(a: {W}, b: {W}) -> {{wcmp(b, a) == cflip(wcmp(a, b)) : Cmp}}:\n"
                 f"  match a b:\n    case {W}{{{ab}}} {W}{{{bb}}}:\n      {pf}\n")
    # w_trans: given cok(wcmp(a, b), wcmp(b, c)), wcmp(a, c) == ccomb(..); limb by limb, each level's ok derived from
    # the whole's by _lex_ok (cok of the high parts follows from cok of the lex'd values or the high parts are EQ)
    parts.append(_w_trans(W))
    parts.append(_w_rel(prefix))
    parts.append(_store(prefix, structural))
    return "\n".join(parts)


def _store(prefix: str, structural: bool = False) -> str:
    """The transport route's store fact: st_same(s, k, v): M.sload(M.sstore(s, k, v), k) == v (through w_eq's
    reflexivity, from Word.cmp's; over a structural store, I68, through sk_eq's: sk_self, from w_eq_self)."""
    W = f"{prefix}W"
    lims = [f"+a{i}" for i in range(8)]
    eqs = [f"U32.is_eq(a{i}, a{i})" for i in range(8)]

    def conj(i):
        return eqs[7] if i == 7 else f"Bool.and({eqs[i]}, {conj(i + 1)})"

    def pf(i):
        return f"u_eq_self(a{i})" if i == 7 else f"and_intro({eqs[i]}, {conj(i + 1)}, u_eq_self(a{i}), {pf(i + 1)})"
    out = [
        "def bcmp_refl(b: Bool) -> {Word.cmp.fin(b, b, EQ{}) == EQ{} : Cmp}:\n  match b:\n    case True{}:\n      {==}\n"
        "    case False{}:\n      {==}\n",
        "def cmp_refl(+n: Nat, x: Word(n)) -> {Word.cmp(n, x, x) == EQ{} : Cmp}:\n  match n:\n    case 0n:\n      {==}\n"
        "    case 1n+p:\n      match x:\n        case WCon{+b, +xt}:\n"
        "          (%Equal.sym(Cmp, Word.cmp(p, xt, xt), EQ{}, cmp_refl(p, xt)) : {Word.cmp.fin(b, b, _) == EQ{} : Cmp}\n"
        "          bcmp_refl(b))\n",
        "def u_eq_self(+a: U32) -> {U32.is_eq(a, a) == True{} : Bool}:\n  match a:\n    case U32{+x}:\n"
        "      (%Equal.sym(Cmp, Word.cmp(32n, x, x), EQ{}, cmp_refl(32n, x)) : {Cmp.is_eq(_) == True{} : Bool}\n      {==})\n",
        f"def w_eq_self(+a: {W}) -> {{{prefix}w_eq(a, a) == True{{}} : Bool}}:\n  match a:\n"
        f"    case {W}{{{', '.join(lims)}}}:\n      {pf(0)}\n",
    ]
    if structural:
        return "\n".join(out + _store_sk(prefix))
    out += [
        f"def kw_same_c(c: Bool, +hv: {W}, +k: {W}, +v: {W}, +t: List<&2, {prefix}KW>, ih: {{{prefix}kw_get({prefix}kw_put(t, k, "
        f"v, False{{}}), k) == v : {W}}}) -> {{{prefix}ite({W}, c, {prefix}ite({W}, Bool.and(c, Bool.not(False{{}})), v, hv), "
        f"{prefix}kw_get({prefix}kw_put(t, k, v, Bool.or(False{{}}, c)), k)) == v : {W}}}:\n  match c:\n"
        f"    case True{{}}:\n      {{==}}\n    case False{{}}:\n      ih\n",
        f"def kw_same(xs: List<&2, {prefix}KW>, +k: {W}, +v: {W}) -> {{{prefix}kw_get({prefix}kw_put(xs, k, v, False{{}}), k) "
        f"== v : {W}}}:\n  match xs:\n    case Nil{{}}:\n"
        f"      (%Equal.sym(Bool, {prefix}w_eq(k, k), True{{}}, w_eq_self(k)) : {{{prefix}ite({W}, _, v, {prefix}w0()) == v : "
        f"{W}}}\n      {{==}})\n    case Con{{h, +t}}:\n      match h:\n        case {prefix}KW{{+hk, +hv}}:\n"
        f"          kw_same_c({prefix}w_eq(hk, k), hv, k, v, t, kw_same(t, k, v))\n",
        f"def st_same(s: {prefix}HSt, +k: {W}, +v: {W}) -> {{{prefix}sload({prefix}sstore(s, k, v), k) == v : {W}}}:\n"
        f"  match s:\n    case {prefix}HSt{{sl}}:\n      kw_same(sl, k, v)\n",
    ]
    return "\n".join(out)


def _store_sk(prefix: str) -> list[str]:
    """st_same over a structural store (I68): sk_eq is reflexive (sp_self, sps_self, sk_self), so a store at key k is
    read back at k whatever the store held before."""
    W, P = f"{prefix}W", prefix
    return [
        f"def sp_self(+a: {P}SP) -> {{{P}sp_eq(a, a) == True{{}} : Bool}}:\n  match a:\n    case {P}SP_m{{+k, +o}}:\n"
        f"      and_intro({P}w_eq(o, o), {P}w_eq(k, k), w_eq_self(o), w_eq_self(k))\n",
        f"def sps_self(+p: List<&2, {P}SP>) -> {{{P}sps_eq(p, p) == True{{}} : Bool}}:\n  match p:\n    case Nil{{}}:\n"
        f"      {{==}}\n    case Con{{+h, +t}}:\n      and_intro({P}sp_eq(h, h), {P}sps_eq(t, t), sp_self(h), sps_self(t))\n",
        f"def sk_self(+a: {P}SK) -> {{{P}sk_eq(a, a) == True{{}} : Bool}}:\n  match a:\n    case {P}SK{{+b, +o, +p}}:\n"
        f"      and_intro({P}w_eq(b, b), Bool.and({P}w_eq(o, o), {P}sps_eq(p, p)), w_eq_self(b), "
        f"and_intro({P}w_eq(o, o), {P}sps_eq(p, p), w_eq_self(o), sps_self(p)))\n",
        f"def kv_same_c(c: Bool, +hv: {W}, +k: {P}SK, +v: {W}, +t: List<&2, {P}KV>, ih: {{{P}kv_get({P}kv_put(t, k, "
        f"v, False{{}}), k) == v : {W}}}) -> {{{P}ite({W}, c, {P}ite({W}, Bool.and(c, Bool.not(False{{}})), v, hv), "
        f"{P}kv_get({P}kv_put(t, k, v, Bool.or(False{{}}, c)), k)) == v : {W}}}:\n  match c:\n"
        f"    case True{{}}:\n      {{==}}\n    case False{{}}:\n      ih\n",
        f"def kv_same(xs: List<&2, {P}KV>, +k: {P}SK, +v: {W}) -> {{{P}kv_get({P}kv_put(xs, k, v, False{{}}), k) "
        f"== v : {W}}}:\n  match xs:\n    case Nil{{}}:\n"
        f"      (%Equal.sym(Bool, {P}sk_eq(k, k), True{{}}, sk_self(k)) : {{{P}ite({W}, _, v, {P}w0()) == v : "
        f"{W}}}\n      {{==}})\n    case Con{{h, +t}}:\n      match h:\n        case {P}KV{{+hk, +hv}}:\n"
        f"          kv_same_c({P}sk_eq(hk, k), hv, k, v, t, kv_same(t, k, v))\n",
        f"def st_same(s: {P}HSt, +k: {P}SK, +v: {W}) -> {{{P}sload({P}sstore(s, k, v), k) == v : {W}}}:\n"
        f"  match s:\n    case {P}HSt{{sl}}:\n      kv_same(sl, k, v)\n",
        # the key split's symmetry: w_eq(a, b) false gives w_eq(b, a) false (equal words would compare equal)
        f"def w_ne_sym_c(c: Bool, +a: {W}, +b: {W}, e: {{{P}w_eq(a, b) == False{{}} : Bool}}, ec: {{{P}w_eq(b, a) == c : "
        f"Bool}}) -> {{c == False{{}} : Bool}}:\n  match c:\n    case True{{}}:\n"
        f"      efq({{True{{}} == False{{}} : Bool}}, true_ne_false(Equal.trans(Bool, True{{}}, {P}w_eq(b, b), False{{}}, "
        f"Equal.sym(Bool, {P}w_eq(b, b), True{{}}, w_eq_self(b)), (%Equal.sym({W}, b, a, w_refl(b, a, ec)) : "
        f"{{{P}w_eq(_, b) == False{{}} : Bool}}\n      e))))\n    case False{{}}:\n      {{==}}\n",
        f"def w_ne_sym(+a: {W}, +b: {W}, e: {{{P}w_eq(a, b) == False{{}} : Bool}}) -> {{{P}w_eq(b, a) == False{{}} : "
        f"Bool}}:\n  w_ne_sym_c({P}w_eq(b, a), a, b, e, {{==}})\n",
    ]


def _w_trans(W: str) -> str:
    """w_trans by nesting _lex_trans from limb 0 up: the inner ih is the previous level's statement as a function of
    its ok. Each level needs ok for its high limbs (cok(h1, h2)) and for its low parts, both from the level's ok:
    _lex_okh and _lex_okl give them (when lex(h1, l1), lex(h2, l2) compose, so do h1, h2; and when h1, h2 are both EQ,
    l1, l2 compose)."""
    out = []
    # the low parts' ok is needed only under h1 == h2 == EQ: _lex_trans asks ihl as a function of cok(l1, l2), so the
    # inner level's statement is passed as that function directly
    ab = ", ".join(f"+a{i}" for i in range(8))
    bb = ", ".join(f"+b{i}" for i in range(8))
    cb = ", ".join(f"+c{i}" for i in range(8))

    def lx(x, y, top):
        t = f"U32.cmp({x}0, {y}0)"
        for i in range(1, top + 1):
            t = f"lex(U32.cmp({x}{i}, {y}{i}), {t})"
        return t
    # level 0: ih0(o) = u_trans(a0, b0, c0, o)
    fn = "(o0 => u_trans(a0, b0, c0, o0))"
    for i in range(1, 8):
        l1, l2, l3 = lx("a", "b", i - 1), lx("b", "c", i - 1), lx("a", "c", i - 1)
        h1, h2, h3 = f"U32.cmp(a{i}, b{i})", f"U32.cmp(b{i}, c{i})", f"U32.cmp(a{i}, c{i})"
        fn = (f"(o{i} => _lex_trans({h1}, {h2}, {h3}, {l1}, {l2}, {l3}, (q{i} => u_trans(a{i}, b{i}, c{i}, q{i})), "
              f"{fn}, o{i}))")
    out.append(f"def w_trans(a: {W}, b: {W}, c: {W}, ok: {{cok(wcmp(a, b), wcmp(b, c)) == True{{}} : Bool}}) -> "
               f"{{wcmp(a, c) == ccomb(wcmp(a, b), wcmp(b, c)) : Cmp}}:\n"
               f"  match a b c:\n    case {W}{{{ab}}} {W}{{{bb}}} {W}{{{cb}}}:\n      {fn}(ok)\n")
    return "\n".join(out)


def _w_rel(prefix: str) -> str:
    """The three facts the routes use, from w_lt_cmp, w_flip and w_trans, by cases on the comparisons."""
    W = f"{prefix}W"
    lt = f"{prefix}w_lt"
    out = []
    # _rel_lt_le(x, y, z, r, ex, ey, ez, ok-free): is_lt(x) True, is_lt(cflip(y)) False (y = wcmp(b, c), not c < b),
    # z == ccomb(x, y) -> is_lt(z) True;  cok(x, y) holds whenever x is LT and y is not GT
    def table(name, cond, concl):
        rows = []
        for x, y in itertools.product(CMPS, repeat=2):
            hx, hy = cond(x, y)
            goal = concl
            if not hx:
                body = "efq(%s, false_ne_true(ex))" % goal.replace("@X", _c(x)).replace("@Y", _c(y))
            elif not hy:
                body = "efq(%s, false_ne_true(ey))" % goal.replace("@X", _c(x)).replace("@Y", _c(y))
            else:
                body = "{==}"
            rows.append(f"    case {_c(x)} {_c(y)}:\n      {body}")
        return rows
    # lt_le: a < b (x = wcmp(a, b) is LT) and not c < b (wcmp(c, b) = cflip(y) is not LT, y = wcmp(b, c)):
    # cok(x, y) and is_lt(ccomb(x, y))
    for name, cx, cy, want in (
            ("lt_le", lambda x: x == "LT", lambda y: _flip(y) != "LT", lambda x, y: _comb(x, y) == "LT"),
            ("le_lt", lambda x: _flip(x) != "LT", lambda y: y == "LT", lambda x, y: _comb(x, y) == "LT"),
            ("le_le", lambda x: _flip(x) != "LT", lambda y: _flip(y) != "LT", lambda x, y: _flip(_comb(x, y)) != "LT")):
        ex = "{Cmp.is_lt(x) == True{} : Bool}" if name == "lt_le" else "{Cmp.is_lt(cflip(x)) == False{} : Bool}"
        ey = "{Cmp.is_lt(y) == True{} : Bool}" if name == "le_lt" else "{Cmp.is_lt(cflip(y)) == False{} : Bool}"
        rows_ok, rows_c = [], []
        for x, y in itertools.product(CMPS, repeat=2):
            okx = cx(x)
            oky = cy(y)
            g_ok = "{cok(%s, %s) == True{} : Bool}" % (_c(x), _c(y))
            if name == "le_le":
                g_c = "{Cmp.is_lt(cflip(ccomb(%s, %s))) == False{} : Bool}" % (_c(x), _c(y))
            else:
                g_c = "{Cmp.is_lt(ccomb(%s, %s)) == True{} : Bool}" % (_c(x), _c(y))
            if not okx:
                bx = "false_ne_true(ex)" if name == "lt_le" else "true_ne_false(ex)"
                rows_ok.append(f"    case {_c(x)} {_c(y)}:\n      efq({g_ok}, {bx})")
                rows_c.append(f"    case {_c(x)} {_c(y)}:\n      efq({g_c}, {bx})")
                continue
            if not oky:
                by = "false_ne_true(ey)" if name == "le_lt" else "true_ne_false(ey)"
                rows_ok.append(f"    case {_c(x)} {_c(y)}:\n      efq({g_ok}, {by})")
                rows_c.append(f"    case {_c(x)} {_c(y)}:\n      efq({g_c}, {by})")
                continue
            if not (_ok(x, y) and want(x, y)):
                raise AssertionError((name, x, y))
            rows_ok.append(f"    case {_c(x)} {_c(y)}:\n      {{==}}")
            rows_c.append(f"    case {_c(x)} {_c(y)}:\n      {{==}}")
        out.append(f"def _{name}_ok(x: Cmp, y: Cmp, ex: {ex}, ey: {ey}) -> {{cok(x, y) == True{{}} : Bool}}:\n"
                   f"  match x y:\n" + "\n".join(rows_ok) + "\n")
        concl = ("{Cmp.is_lt(cflip(ccomb(x, y))) == False{} : Bool}" if name == "le_le" else
                 "{Cmp.is_lt(ccomb(x, y)) == True{} : Bool}")
        out.append(f"def _{name}_c(x: Cmp, y: Cmp, ex: {ex}, ey: {ey}) -> {concl}:\n"
                   f"  match x y:\n" + "\n".join(rows_c) + "\n")
    out.append("def rw_lt(+x: Cmp, +y: Cmp, +v: Bool, e: {x == y : Cmp}, h: {Cmp.is_lt(x) == v : Bool}) -> "
               "{Cmp.is_lt(y) == v : Bool}:\n  (%e : {Cmp.is_lt(_) == v : Bool}\n  h)\n")
    out.append("def rw_ltf(+x: Cmp, +y: Cmp, +v: Bool, e: {x == y : Cmp}, h: {Cmp.is_lt(cflip(x)) == v : Bool}) -> "
               "{Cmp.is_lt(cflip(y)) == v : Bool}:\n  (%e : {Cmp.is_lt(cflip(_)) == v : Bool}\n  h)\n")
    # the word facts. Hypotheses as the routes have them: M.w_lt(..) == True / False.
    # a < b <= c:  w_lt(a, b) == True, w_lt(c, b) == False  ->  w_lt(a, c) == True
    def eq_lt(a, b):    # {M.w_lt(a, b) == Cmp.is_lt(wcmp(a, b))}
        return f"w_lt_cmp({a}, {b})"
    out.append(
        f"def w_lt_le(+a: {W}, +b: {W}, +c: {W}, h1: {{{lt}(a, b) == True{{}} : Bool}}, h2: {{{lt}(c, b) == False{{}} : "
        f"Bool}}) -> {{{lt}(a, c) == True{{}} : Bool}}:\n"
        f"  +ex = Equal.trans(Bool, Cmp.is_lt(wcmp(a, b)), {lt}(a, b), True{{}}, Equal.sym(Bool, {lt}(a, b), "
        f"Cmp.is_lt(wcmp(a, b)), {eq_lt('a', 'b')}), h1)\n"
        f"  +e2 = Equal.trans(Bool, Cmp.is_lt(wcmp(c, b)), {lt}(c, b), False{{}}, Equal.sym(Bool, {lt}(c, b), "
        f"Cmp.is_lt(wcmp(c, b)), {eq_lt('c', 'b')}), h2)\n"
        f"  +ey = rw_lt(wcmp(c, b), cflip(wcmp(b, c)), False{{}}, w_flip(b, c), e2)\n"
        f"  +tr = w_trans(a, b, c, _lt_le_ok(wcmp(a, b), wcmp(b, c), ex, ey))\n"
        f"  +r = rw_lt(ccomb(wcmp(a, b), wcmp(b, c)), wcmp(a, c), True{{}}, Equal.sym(Cmp, wcmp(a, c), "
        f"ccomb(wcmp(a, b), wcmp(b, c)), tr), _lt_le_c(wcmp(a, b), wcmp(b, c), ex, ey))\n"
        f"  Equal.trans(Bool, {lt}(a, c), Cmp.is_lt(wcmp(a, c)), True{{}}, {eq_lt('a', 'c')}, r)\n")
    # a <= b < c:  w_lt(b, a) == False, w_lt(b, c) == True  ->  w_lt(a, c) == True
    out.append(
        f"def w_le_lt(+a: {W}, +b: {W}, +c: {W}, h1: {{{lt}(b, a) == False{{}} : Bool}}, h2: {{{lt}(b, c) == True{{}} : "
        f"Bool}}) -> {{{lt}(a, c) == True{{}} : Bool}}:\n"
        f"  +e1 = Equal.trans(Bool, Cmp.is_lt(wcmp(b, a)), {lt}(b, a), False{{}}, Equal.sym(Bool, {lt}(b, a), "
        f"Cmp.is_lt(wcmp(b, a)), {eq_lt('b', 'a')}), h1)\n"
        f"  +ex = rw_lt(wcmp(b, a), cflip(wcmp(a, b)), False{{}}, w_flip(a, b), e1)\n"
        f"  +ey = Equal.trans(Bool, Cmp.is_lt(wcmp(b, c)), {lt}(b, c), True{{}}, Equal.sym(Bool, {lt}(b, c), "
        f"Cmp.is_lt(wcmp(b, c)), {eq_lt('b', 'c')}), h2)\n"
        f"  +tr = w_trans(a, b, c, _le_lt_ok(wcmp(a, b), wcmp(b, c), ex, ey))\n"
        f"  +r = rw_lt(ccomb(wcmp(a, b), wcmp(b, c)), wcmp(a, c), True{{}}, Equal.sym(Cmp, wcmp(a, c), "
        f"ccomb(wcmp(a, b), wcmp(b, c)), tr), _le_lt_c(wcmp(a, b), wcmp(b, c), ex, ey))\n"
        f"  Equal.trans(Bool, {lt}(a, c), Cmp.is_lt(wcmp(a, c)), True{{}}, {eq_lt('a', 'c')}, r)\n")
    # a <= b <= c:  w_lt(b, a) == False, w_lt(c, b) == False  ->  w_lt(c, a) == False
    out.append(
        f"def w_le_le(+a: {W}, +b: {W}, +c: {W}, h1: {{{lt}(b, a) == False{{}} : Bool}}, h2: {{{lt}(c, b) == False{{}} : "
        f"Bool}}) -> {{{lt}(c, a) == False{{}} : Bool}}:\n"
        f"  +e1 = Equal.trans(Bool, Cmp.is_lt(wcmp(b, a)), {lt}(b, a), False{{}}, Equal.sym(Bool, {lt}(b, a), "
        f"Cmp.is_lt(wcmp(b, a)), {eq_lt('b', 'a')}), h1)\n"
        f"  +ex = rw_lt(wcmp(b, a), cflip(wcmp(a, b)), False{{}}, w_flip(a, b), e1)\n"
        f"  +e2 = Equal.trans(Bool, Cmp.is_lt(wcmp(c, b)), {lt}(c, b), False{{}}, Equal.sym(Bool, {lt}(c, b), "
        f"Cmp.is_lt(wcmp(c, b)), {eq_lt('c', 'b')}), h2)\n"
        f"  +ey = rw_lt(wcmp(c, b), cflip(wcmp(b, c)), False{{}}, w_flip(b, c), e2)\n"
        f"  +tr = w_trans(a, b, c, _le_le_ok(wcmp(a, b), wcmp(b, c), ex, ey))\n"
        f"  +r = rw_ltf(ccomb(wcmp(a, b), wcmp(b, c)), wcmp(a, c), False{{}}, Equal.sym(Cmp, wcmp(a, c), "
        f"ccomb(wcmp(a, b), wcmp(b, c)), tr), _le_le_c(wcmp(a, b), wcmp(b, c), ex, ey))\n"
        f"  +r2 = rw_lt(cflip(wcmp(a, c)), wcmp(c, a), False{{}}, Equal.sym(Cmp, wcmp(c, a), cflip(wcmp(a, c)), "
        f"w_flip(a, c)), r)\n"
        f"  Equal.trans(Bool, {lt}(c, a), Cmp.is_lt(wcmp(c, a)), False{{}}, {eq_lt('c', 'a')}, r2)\n")
    return "\n".join(out)
