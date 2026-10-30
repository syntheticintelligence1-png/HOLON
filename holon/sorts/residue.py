"""The proof class residue_bound (BUILD_PLAN I33; tests_m3/test_o12_m3.py rule B6): the residue of two steps of a typed
contract law, bounded over I68's structural store.

It applies to a law with binders s: Reach, x: Act, y: Act and Word binders, the premises is[A](x), ok(x, s), is[B](y),
ok(y, step(x, s)) for two actions A, B of the facts, and a claim that is a conjunction of

  N(sread[F](K, step(y, step(x, s)))) == N(sread[F](K, s))                      (the word at K is kept)
  N(sread[F](K, step(y, step(x, s)))) <= N(sread[F](K, s)) + N(T)               (it grows by at most T)

for whole-word reads (no packed field) at the same key K, and T a whole-word read at s or an env word of x.

The proof is symbolic evaluation of the two steps over the store, one fact per key and step, each a chain of lemmas
over the action's statement chain (holon.disch.mirror), whose invariant is the word at K in the context's overlay:

  frame       every store of the step is at a key that differs from K (st_frame): the word is the pre-state's
  transport   a store at K itself (st_same): the word is the stored one, kept by the later frames; it needs the step
              to succeed (its ok premise), as every fact here takes it
  split       a store at a key that meets K only in one word pair (x, y), whose value is w_add(sload(st, key), D): by
              cases on w_eq(x, y), the word grows by at most D (the wrap bound w_wrap) or is kept (a frame)
  loop        a loop that keeps K (an observation of the record kept by every iteration, by induction on the fuel), or
              a loop that adds D to the word at its key c0 + it once per index, it stepping by one under the checked
              increment of the key (the key-step lemmas ks_*): every key gets D at most once (the accumulating loop)

A conjunct is then the composition: B's fact at K over the state x leaves, A's fact at K over s, and the budget D of a
split rewritten through A's transports of the words it reads (each a fact of A at that word's key). Every lemma is
generated here and checked with the file; the core lemmas are holon.disch.lemmas', holon.disch.order's and
holon.sorts.residue_lemmas'. prove() writes the law's PROOF.bend text or raises NoProof naming what it lacks. Nothing
here names a law, a contract, an action or a slot.
"""
from __future__ import annotations

import json
import re

from ..disch import lemmas as DL
from ..disch import order as ORDER
from ..disch.mirror import Branch, Final, Loop, Mirror, NoMirror, Next, Record, as_call, split_top
from ..disch.proofs import key_cmp, sk_ne_proof, stores
from ..machine_bend import bname
from ..sorts.proofs3 import PHEADER, model_names
from . import contract3 as C3
from . import residue_lemmas as RL

CLASS = "residue_bound"
N = "Laws.c3_wnat"
FIXED = ("st", "ar", "en", "kh")
FX = {"st": "st", "ar": "ar", "en": "e", "kh": "kh"}
HEADER = PHEADER.replace("holon.sorts.proofs3", "holon.sorts.residue")


class NoProof(ValueError):
    """The class does not apply, or cannot prove a conjunct (named)."""


def _sub(t: str, ren: dict) -> str:
    """t with the identifiers of ren renamed (whole names, not fields or qualified names)."""
    if not ren:
        return t
    pat = re.compile(r"(?<![\w.])(" + "|".join(re.escape(k) for k in ren) + r")(?![\w{])")
    return pat.sub(lambda m: ren[m.group(1)], t)


def _strip(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip())


# ------------------------------------------------------------------------------------------------ the model
class Model:
    def __init__(self, text: str):
        self.text = text
        self.names = model_names(text)
        if "\ntype SK is Data:\n" not in text:
            raise NoProof("the typed model's store is not structural (SK keys): residue_bound reads I68's store")
        self.mirrors: dict = {}

    def mirror(self, ab: str) -> Mirror:
        if ab not in self.mirrors:
            try:
                self.mirrors[ab] = Mirror(self.text, ab, self.names)
            except NoMirror as e:
                raise NoProof(f"{ab}: {e}")
        return self.mirrors[ab]

    def mtype(self, ty: str) -> str:
        return re.sub(r"(?<![\w.])([A-Z]\w*)", lambda m: "M." + m.group(1) if m.group(1) in self.names else m.group(1),
                      ty)

    def record_types(self, ab: str) -> list:
        m = re.search(rf"(?m)^type X_{ab} is Data:\n  X_{ab}\{{(.*)\}}$", self.text)
        if not m:
            raise NoProof(f"{ab}: no context record X_{ab}")
        return [self.mtype(p.split(":", 1)[1].strip()) for p in split_top(m.group(1))]

    def x0(self, ab: str, fields: list) -> dict:
        """The context record the action's program starts from (x0_<a>), its fields as proof terms."""
        m = re.search(rf"(?m)^def x0_{ab}\(\+st: HSt, \+ar: AR_{ab}, \+en: HEnv(.*)\) -> X_{ab}:\n  X_{ab}\{{(.*)\}}$",
                      self.text)
        if not m:
            raise NoProof(f"{ab}: its starting record x0_{ab} is not of the known shape")
        vals = [x.strip() for x in split_top(m.group(2))]
        q = lambda t: _sub(re.sub(r"(?<![\w.])(w0|W)(?=[({])", r"M.\1", t), {"en": "e"})
        return {f: q(v) for f, v in zip(fields, vals)}

    def defined(self, name: str, body: str) -> bool:
        m = re.search(rf"(?ms)^def {re.escape(name)}\(.*?\n(.*?)(?=^\S|\Z)", self.text)
        return m is not None and _strip(m.group(1)) == _strip(body)


def norm_value(t: str) -> str:
    """A stored value with the model's time arithmetic read as words: pay_T_Time(add_Time_Dur(T_Time{a}, T_Dur{b}))
    is w_add(a, b) (checked against the model's definitions by the caller)."""
    c = as_call(t.strip())
    if c and c[0] == "M.pay_T_Time" and len(c[1]) == 1:
        d = as_call(c[1][0].strip())
        if d and d[0] == "M.add_Time_Dur" and len(d[1]) == 2:
            a, b = (as_call(x.strip()) for x in d[1])
            if a and b and a[0] == "M.T_Time" and b[0] == "M.T_Dur" and len(a[1]) == 1 and len(b[1]) == 1:
                return f"M.w_add({a[1][0].strip()}, {b[1][0].strip()})"
    return t.strip()


TIME_DEFS = {"pay_T_Time": "match x:\n case T_Time{v}:\n v",
             "add_Time_Dur": "match a b:\n case T_Time{x} T_Dur{y}:\n T_Time{w_add(x, y)}"}


# ------------------------------------------------------------------------------------------------ facts
class Fact:
    """The word at key K after one action's step, as a relation to the step's pre-state: ("eq", R) the word is R;
    ("le", R, D) N(word) <= N(R) + N(D). K, R and D are terms of the action's context (st, ar, e, kh) and of params
    [(name, type)], the law's words the key names."""

    def __init__(self, key: str, params: list, goal: tuple):
        self.K = _strip(key)
        self.params = params
        self.goal = tuple(_strip(x) for x in goal[1:])
        self.goal = (goal[0],) + self.goal

    def pp(self) -> str:
        return "".join(f", +{n}: {t}" for n, t in self.params)

    def pa(self) -> str:
        return "".join(f", {n}" for n, _t in self.params)


def inv(o: str, K: str, state: tuple) -> str:
    if state[0] == "eq":
        return f"{{M.sload({o}, {K}) == {state[1]} : M.W}}"
    return (f"{{Nat.is_le({N}(M.sload({o}, {K})), Nat.add({N}({state[1]}), {N}({state[2]}))) == True{{}} : "
            f"Bool}}")


# ------------------------------------------------------------------------------------------------ walkers
class Walk:
    """Lemmas over one action's statement chain for one fact (prefix p): a lemma per statement and state of the
    invariant, a lemma per branch."""

    def __init__(self, md: Model, ab: str, fact: Fact, p: str, defs: list):
        self.md, self.ab, self.f, self.p, self.defs = md, ab, fact, p, defs
        self.mi = md.mirror(ab)
        self.fields = self.mi.field_names
        self.types = md.record_types(ab)
        if [f for f in FIXED if f in self.fields] != list(FIXED[:3]) + (["kh"] if "kh" in self.fields else []):
            raise NoProof(f"{ab}: its record's fixed fields are not st, ar, en, kh")
        self.fixed = {f: FX[f] for f in FIXED if f in self.fields}
        self.var = [f for f in self.fields if f not in self.fixed]
        self.done: dict = {}
        self.nb = 0
        self.X = f"M.X_{ab}"

    # text pieces
    def ty(self, f: str) -> str:
        return self.types[self.fields.index(f)]

    def fixed_params(self) -> str:
        return f"+st: M.HSt, +ar: M.AR_{self.ab}, +e: M.HEnv, +kh: List<&2, M.HKB>{self.f.pp()}"

    def fixed_args(self) -> str:
        return f"st, ar, e, kh{self.f.pa()}"

    def var_params(self) -> str:
        return "".join(f", +v_{f}: {self.ty(f)}" for f in self.var)

    def var_args(self) -> str:
        return "".join(f", v_{f}" for f in self.var)

    def rec(self, vals: dict) -> str:
        return f"{self.X}{{{', '.join(vals[f] if f in vals else self.fixed[f] for f in self.fields)}}}"

    def vrec(self) -> str:
        return self.rec({f: f"v_{f}" for f in self.var})

    def vals(self, fields: list) -> dict:
        d = dict(zip(self.fields, [x.strip() for x in fields]))
        for f, want in self.fixed.items():
            if d[f] != want:
                raise NoProof(f"{self.ab}: its program changes its context's {f}")
        return {f: d[f] for f in self.var}

    # the goal (subclasses)
    def goal(self, x: str) -> str:
        raise NotImplementedError

    def hyp_params(self, x: str) -> str:
        return ""

    def hyp_args(self) -> str:
        return ""

    # ---------------------------------------------------------------- statements and branches
    def stmt(self, i: int, state: tuple) -> str:
        key = (i, state)
        if key in self.done:
            return self.done[key]
        k = len([1 for (j, _s) in self.done if j == i])
        name = f"{self.p}_s{i}" + (f"_{k}" if k else "")
        self.done[key] = name
        node = self.mi.step(i, [self.fixed.get(f, f"v_{f}") for f in self.fields])
        x = f"M.s_{self.ab}_{i}({self.vrec()})"
        body = self.emit(node, {f: f"v_{f}" for f in self.var}, "inv", state)
        self.defs.append(f"def {name}({self.fixed_params()}{self.var_params()}, +inv: {inv('v_ov', self.f.K, state)}"
                         f"{self.hyp_params(x)}) -> {self.goal(x)}:\n  {body}\n")
        return name

    def call(self, name: str, vals: dict, pf: str) -> str:
        return f"{name}({self.fixed_args()}{''.join(', ' + vals[f] for f in self.var)}, {pf}{self.hyp_args()})"

    def emit(self, node, cur: dict, pf: str, state: tuple) -> str:
        if isinstance(node, Branch):
            return self.branch(node, cur, pf, state)
        if isinstance(node, Next):
            vals = self.vals(node.fields)
            pf2, st2 = self.track(cur["ov"], vals["ov"], pf, state)
            return self.call(self.stmt(node.j, st2), vals, pf2)
        if isinstance(node, Final):
            return self.final(node, cur, pf, state)
        if isinstance(node, Record):
            return self.leaf(node, cur, pf, state)
        if isinstance(node, Loop):
            return self.loop(node, cur, pf, state)
        raise NoProof(f"{self.ab}: an evaluation result the mirror cannot state ({type(node).__name__})")

    def branch(self, br: Branch, cur: dict, pf: str, state: tuple) -> str:
        """A lemma over the enclosing lemma's variables (the same names), the current invariant and the condition's
        equation, by cases."""
        self.nb += 1
        name = f"{self.p}_b{self.nb}"
        x = f"{br.fn}(c, {', '.join(br.args)})"
        then = self.emit(br.then, cur, "inv", state)
        other = self.emit(br.other, cur, "inv", state)
        self.defs.append(f"def {name}(c: Bool, {self.fixed_params()}{self.var_params()}, +inv: "
                         f"{inv(cur['ov'], self.f.K, state)}, +ec: {{{br.cond} == c : Bool}}{self.hyp_params(x)}) -> "
                         f"{self.goal(x)}:\n  match c:\n    case True{{}}:\n      {then}\n    case False{{}}:\n"
                         f"      {other}\n")
        return f"{name}({br.cond}, {self.fixed_args()}{self.var_args()}, {pf}, {{==}}{self.hyp_args()})"

    # ---------------------------------------------------------------- the invariant through stores
    def track(self, o_old: str, o_new: str, pf: str, state: tuple) -> tuple:
        if _strip(o_new) == _strip(o_old):
            return pf, state
        ss = stores(o_new, o_old.strip())
        if ss is None:
            raise NoProof(f"{self.ab}: its overlay changes other than by stores")
        K = self.f.K
        o = o_old.strip()
        for kw, v in ss:
            kw, v = kw.strip(), v.strip()
            rel, at = key_cmp(kw, K, True)
            if rel == "differ":
                pf = self.frame(o, kw, v, pf, state, "{==}", "{==}")
            elif rel == "same" or _strip(kw) == K:
                if state[0] != "eq":
                    raise NoProof(f"{self.ab}: it stores again at the key {K[:120]} after adding to it")
                if re.search(r"(?<![\w.])v_\w+", v):
                    raise NoProof(f"{self.ab}: it stores at {K[:120]} a word read from its own overlay")
                pf = f"st_same_k({o}, {kw}, {v}, {K}, {{==}})" if rel == "same" else f"st_same({o}, {K}, {v})"
                state = ("eq", _strip(v))
            else:
                pf, state = self.split(o, kw, v, at, pf, state)
            o = f"M.sstore({o}, {kw}, {v})"
        return pf, state

    def frame(self, o, kw, v, pf, state, ne1, ne2) -> str:
        K = self.f.K
        if state[0] == "eq":
            return f"fr_eq({o}, {kw}, {v}, {K}, {state[1]}, {ne1}, {ne2}, {pf})"
        return f"fr_le({o}, {kw}, {v}, {K}, {state[1]}, {state[2]}, {ne1}, {ne2}, {pf})"

    def split(self, o: str, kw: str, v: str, at: tuple, pf: str, state: tuple) -> tuple:
        K = self.f.K
        x, y = (_strip(a) for a in at)
        g = self.f.goal
        R0 = f"M.sload(st, {K})"
        if g[0] != "le" or state != ("eq", R0) or g[1] != R0:
            raise NoProof(f"{self.ab}: it stores at {kw[:120]}, which meets the key {K[:120]} when {x[:80]} == "
                          f"{y[:80]}: a split needs a bounded fact over the untouched pre-state word")
        D = g[2]
        if _sub(_strip(kw), {}).replace(x, y) != K or _strip(norm_value(v)).replace(x, y) != _strip(
                f"M.w_add(M.sload(st, {K}), {D})"):
            raise NoProof(f"{self.ab}: its store at {kw[:120]} is not w_add(sload(st, key), {D[:80]}) at a key that "
                          "differs from the fact's in one word")
        ne1, ne2 = sk_ne_proof(kw, K, "ec"), sk_ne_proof(K, kw, f"w_ne_sym({x}, {y}, ec)")
        if ne1 is None or ne2 is None:
            raise NoProof(f"{self.ab}: no key inequality for the split at {kw[:120]}")
        self.nb += 1
        name = f"{self.p}_k{self.nb}"
        hole = lambda t: t.replace(x, "_")
        motive = (f"{{Nat.is_le({N}(M.sload(M.sstore(o, {hole(kw)}, {hole(v)}), {K})), Nat.add({N}({R0}), {N}({D}))) "
                  f"== True{{}} : Bool}}")
        sto = f"M.sload(M.sstore(o, {kw}, {v}), {K})"
        self.defs.append(
            f"def {name}(c: Bool, {self.fixed_params()}{self.var_params()}, +o: M.HSt, +inv: {{M.sload(o, {K}) == "
            f"{R0} : M.W}}, +ec: {{M.w_eq({x}, {y}) == c : Bool}}) -> {inv('M.sstore(o, ' + kw + ', ' + v + ')', K, g)}:\n"
            f"  match c:\n    case True{{}}:\n      (%Equal.sym(M.W, {x}, {y}, w_refl({x}, {y}, ec)) : {motive}\n"
            f"      bnd_hit(o, st, {K}, {D}))\n    case False{{}}:\n"
            f"      wk({sto}, {R0}, {D}, fr_eq(o, {kw}, {v}, {K}, {R0}, {ne1}, {ne2}, inv))\n")
        return (f"{name}(M.w_eq({x}, {y}), {self.fixed_args()}{self.var_args()}, {o}, {pf}, {{==}})", g)

    # subclasses
    def final(self, node, cur, pf, state):
        raise NotImplementedError

    def leaf(self, node, cur, pf, state):
        raise NoProof(f"{self.ab}: a loop's record outside its loop")

    def loop(self, node, cur, pf, state):
        raise NoProof(f"{self.ab}: a loop inside a loop")


class Chain(Walk):
    """The fact through the action's whole program: each lemma takes hz, the step succeeds (its code is not 0 is
    false), and shows the fact of the overlay the program ends with."""

    def __init__(self, md, ab, fact, p, defs, loops):
        super().__init__(md, ab, fact, p, defs)
        self.loops = loops       # the loop proof builder (Loops)

    def goal(self, x: str) -> str:
        return inv(f"M.gx_{self.ab}_ov({x})", self.f.K, self.f.goal)

    def hz(self, x: str) -> str:
        return f"{{M.u_nz(M.gx_{self.ab}_cd({x})) == False{{}} : Bool}}"

    def hyp_params(self, x: str) -> str:
        return f", +hz: {self.hz(x)}"

    def hyp_args(self) -> str:
        return ", hz"

    def final(self, node: Final, cur: dict, pf: str, state: tuple) -> str:
        vals = self.vals(node.fields)
        cd = vals["cd"]
        if re.fullmatch(r"\d+", cd) and int(cd) != 0:
            return f"efq({inv(vals['ov'], self.f.K, self.f.goal)}, true_ne_false(hz))"
        pf2, st2 = self.track(cur["ov"], vals["ov"], pf, state)
        return self.conclude(vals["ov"], pf2, st2)

    def conclude(self, ov: str, pf: str, state: tuple) -> str:
        g = self.f.goal
        if state == g:
            return pf
        if g[0] == "le" and state == ("eq", g[1]):
            return f"wk(M.sload({ov}, {self.f.K}), {g[1]}, {g[2]}, {pf})"
        raise NoProof(f"{self.ab}: a path of its program ends with the word at {self.f.K[:120]} {state[0]} "
                      f"{state[1][:120]}, not the fact's {g[0]} {g[1][:120]}")

    def loop(self, node: Loop, cur: dict, pf: str, state: tuple) -> str:
        return self.loops.at(self, node, cur, pf, state)

    def top(self) -> str:
        """{p}_top(st, ar, e, kh, params.., hz): the fact of the overlay xr_<a> ends with."""
        name = f"{self.p}_top"
        x0 = self.md.x0(self.ab, self.fields)
        vals = {f: x0[f] for f in self.var}
        if any(x0[f] != self.fixed[f] for f in self.fixed):
            raise NoProof(f"{self.ab}: its starting record's fixed fields are not its context")
        st0 = ("eq", f"M.sload(st, {self.f.K})")
        if vals["ov"] != "st":
            raise NoProof(f"{self.ab}: its starting overlay is not its pre-state")
        first = self.stmt(self.mi.first, st0)
        x = f"M.xr_{self.ab}(st, ar, e, kh)"
        self.defs.append(f"def {name}({self.fixed_params()}{self.hyp_params(x)}) -> {self.goal(x)}:\n"
                         f"  {self.call(first, vals, '{==}')}\n")
        return name


class Iter(Walk):
    """One iteration of a loop that keeps the fact's key: the observation ob(params, x) = Ob{st, ar, en, kh, word at K}
    of the record after li_<a>_<L>(x) is the one before (frames by evaluation; a store at K is refused)."""

    def __init__(self, md, ab, fact, p, defs, L: int):
        super().__init__(md, ab, fact, p, defs)
        self.L = L
        self.O = f"Ob_{p}"
        self.lb = f"M.lb_{ab}_{L}"
        self.own = tuple(f"M.{q}_{ab}_{L}" for q in ("li", "lh", "lb", "lc", "lk", "ln", "lbk", "lx", "lz", "ls"))

    def fixed_params(self) -> str:
        return super().fixed_params() + ", +o0: M.HSt"

    def fixed_args(self) -> str:
        return super().fixed_args() + ", o0"

    def ref(self) -> str:
        return f"{self.O}{{st, ar, e, kh, M.sload(o0, {self.f.K})}}"

    def goal(self, x: str) -> str:
        t = x if x.strip().startswith(self.own) else f"{self.lb}({x})"
        return f"{{ob_{self.p}({self.f.pa()[2:]}{', ' if self.f.params else ''}{t}) == {self.ref()} : {self.O}}}"

    def final(self, node: Final, cur: dict, pf: str, state: tuple) -> str:
        vals = self.vals(node.fields)
        pf2, st2 = self.track(cur["ov"], vals["ov"], pf, state)
        nxt = self.mi.apply(f"lb_{self.ab}_{self.L}", [Record(f"X_{self.ab}", list(node.fields))])
        return self.emit(nxt, vals, pf2, st2)

    def leaf(self, node: Record, cur: dict, pf: str, state: tuple) -> str:
        vals = self.vals(node.fields)
        pf2, st2 = self.track(cur["ov"], vals["ov"], pf, state)
        want = ("eq", f"M.sload(o0, {self.f.K})")
        if st2 != want:
            raise NoProof(f"{self.ab}: its loop {self.L} stores at the key {self.f.K[:120]}")
        w = f"M.sload({vals['ov']}, {self.f.K})"
        return (f"(%Equal.sym(M.W, {w}, M.sload(o0, {self.f.K}), {pf2}) : {{{self.O}{{st, ar, e, kh, _}} == "
                f"{self.ref()} : {self.O}}}\n      {{==}})")

    def split(self, *a):
        raise NoProof(f"{self.ab}: its loop {self.L} stores at a key that meets {self.f.K[:120]} in words that are not "
                      "literals: no loop frame by evaluation")


class Loops:
    """The loop statements of a chain: a fact of eq kind is kept by the loop (Iter, by induction on the fuel); the
    continuation opens the loop's result, rewrites its fixed fields to the context's and steps la_<a>_<n>."""

    def __init__(self, md: Model, defs: list):
        self.md, self.defs = md, defs
        self.made: dict = {}

    def ctx(self, ch: Chain) -> list:
        """The context names the fact's key mentions, as the loop lemmas' own copies [(name, copy, type)]: the key
        is then a term of the copies and the params, whatever the record's fixed fields are called."""
        cs = [("st", "s0", "M.HSt"), ("ar", "a0", f"M.AR_{ch.ab}"), ("e", "e0", "M.HEnv"), ("kh", "k0", "List<&2, M.HKB>")]
        return [c for c in cs if re.search(rf"(?<![\w.]){c[0]}(?![\w{{])", ch.f.K)]

    def lemmas(self, ch: Chain, L: int) -> tuple:
        """The observation, the iteration and the fuel induction of loop L for the chain's fact (once)."""
        key = (ch.p, L)
        if key in self.made:
            return self.made[key]
        p = f"{ch.p}L{L}"
        ab, X, f = ch.ab, ch.X, ch.f
        cx = self.ctx(ch)
        K2 = _sub(f.K, {c: n for c, n, _t in cx})
        f2 = Fact(K2, f.params + [(n, t) for _c, n, t in cx], ("eq", f"M.sload(o0, {K2})"))
        it = Iter(self.md, ab, f2, p, self.defs, L)
        O = it.O
        tys = ["M.HSt", f"M.AR_{ab}", "M.HEnv", "List<&2, M.HKB>", "M.W"]
        pat = f"{X}{{{', '.join('+x_' + q for q in ch.fields)}}}"
        xrec = f"{X}{{{', '.join('x_' + q for q in ch.fields)}}}"
        pp, pa = f2.pp()[2:], f2.pa()[2:]
        sep = ", " if f2.params else ""
        out = [f"type {O} is Data:\n  {O}{{{', '.join(f'f{i}: {t}' for i, t in enumerate(tys))}}}\n",
               f"def ob_{p}({pp}{sep}r: {X}) -> {O}:\n  match r:\n    case {pat}:\n"
               f"      {O}{{x_st, x_ar, x_en, x_kh, M.sload(x_ov, {K2})}}\n"]
        gs = ", ".join(f"+a{i}" for i in range(len(tys)))
        for i, t in enumerate(tys):
            out.append(f"def ob_{p}_g{i}(o: {O}) -> {t}:\n  match o:\n    case {O}{{{gs}}}:\n      a{i}\n")
        self.defs.extend(out)
        node = it.mi.apply(f"li_{ab}_{L}", [Record(f"X_{ab}", [it.fixed.get(q, f"v_{q}") for q in ch.fields])])
        body = it.emit(node, {q: f"v_{q}" for q in it.var}, "inv", ("eq", f"M.sload(o0, {K2})"))
        top = f"{p}_top"
        self.defs.append(f"def {top}({it.fixed_params()}{it.var_params()}, +inv: {{M.sload(v_ov, {K2}) == "
                         f"M.sload(o0, {K2}) : M.W}}) -> {it.goal(f'M.li_{ab}_{L}({it.vrec()})')}:\n  {body}\n")
        call = (f"{top}(x_st, x_ar, x_en, x_kh{f2.pa()}, x_ov" + "".join(f", x_{q}" for q in it.var) + ", {==})")
        obx = lambda t: f"ob_{p}({pa}{sep}{t})"
        self.defs.append(
            f"def {p}_li({pp}{sep}+x: {X}, +o: {O}, h: {{{obx('x')} == o : {O}}}) -> {{{obx(f'M.li_{ab}_{L}(x)')} == o : "
            f"{O}}}:\n  match x:\n    case {pat}:\n      Equal.trans({O}, {obx(f'M.li_{ab}_{L}({xrec})')}, {obx(xrec)}, o, "
            f"{call}, h)\n")
        ld = f"M.gx_{ab}_ld{L}"
        lp = f"{p}_lp"
        self.defs.append(
            f"def {lp}(f: Nat, +d: Nat, {pp}{sep}+x: {X}, +o: {O}, h: {{{obx('x')} == o : {O}}}) -> "
            f"{{{obx(f'M.lp_{ab}_{L}(f, d, x)')} == o : {O}}}:\n"
            f"  match f:\n    case 0n:\n      match d:\n        case 0n:\n          h\n        case 1n+q:\n"
            f"          match q:\n            case 0n:\n              match x:\n                case {pat}:\n"
            f"                  h\n            case 1n+s:\n              h\n"
            f"    case 1n+r:\n      match d:\n        case 0n:\n          h\n        case 1n+q:\n"
            f"          match q:\n            case 0n:\n"
            f"              {lp}(r, {ld}(M.li_{ab}_{L}(x)), {pa}{sep}M.li_{ab}_{L}(x), o, {p}_li({pa}{sep}x, o, h))\n"
            f"            case 1n+s:\n              h\n")
        self.made[key] = (p, cx)
        return p, cx

    def at(self, ch: Chain, node: Loop, cur: dict, pf: str, state: tuple) -> str:
        if state[0] != "eq":
            raise NoProof(f"{ch.ab}: its loop {node.L} meets a bounded fact (an accumulating loop is not built here)")
        vals = ch.vals(node.rec.fields)
        p, cx = self.lemmas(ch, node.L)
        f, ab, X, O = ch.f, ch.ab, ch.X, f"Ob_{p}"
        pa = (f.pa() + "".join(f", {c}" for c, _n, _t in cx))[2:]
        sep = ", " if pa else ""
        ov = vals["ov"]
        ls = f"M.ls_{ab}_{node.L}({ch.rec(vals)})"
        y = f"M.lp_{ab}_{node.L}({node.fuel}, {node.d}, {ls})"
        ref = f"{O}{{st, ar, e, kh, M.sload({ov}, {f.K})}}"
        hy = f"{p}_lp({node.fuel}, {node.d}, {pa}{sep}{ls}, {ref}, {{==}})"
        ch.nb += 1
        cname = f"{ch.p}_c{ch.nb}"
        aname = self.after(ch, node.n, state)
        ys = [f"y_{q}" for q in ch.fields]
        pat = f"{X}{{{', '.join('+' + v for v in ys)}}}"
        yrec = f"{X}{{{', '.join(ys)}}}"
        obq = f"ob_{p}({pa}{sep}{yrec})"
        fx = [("st", "M.HSt"), ("ar", f"M.AR_{ab}"), ("en", "M.HEnv"), ("kh", "List<&2, M.HKB>")]
        eqs = {q: (t, f"Equal.cong({O}, {t}, z => ob_{p}_g{i}(z), {obq}, {ref}, hy)") for i, (q, t) in enumerate(fx)}
        ctxn = {q: FX[q] for q, _t in fx}
        la = lambda r: f"M.la_{ab}_{node.n}(M.u_nz(y_cd), {r})"
        # hz on the rewritten record: each fixed field y_q to the context's, st first
        hz = "hz"
        cur_f = {q: f"y_{q}" for q in ch.fields}
        for q, _t in fx:
            holes = dict(cur_f)
            holes[q] = "_"
            r = f"{X}{{{', '.join(holes[z] for z in ch.fields)}}}"
            hz = f"(%{eqs[q][1]} : {ch.hz(la(r))}\n        {hz})"
            cur_f[q] = ctxn[q]
        kword = f"Equal.cong({O}, M.W, z => ob_{p}_g4(z), {obq}, {ref}, hy)"
        inv2 = f"Equal.trans(M.W, M.sload(y_ov, {f.K}), M.sload({ov}, {f.K}), {state[1]}, {kword}, inv)"
        body = f"{aname}({ch.fixed_args()}" + "".join(f", y_{q}" for q in ch.var) + f", {inv2}, {hz})"
        cur_f = {q: ctxn.get(q, f"y_{q}") for q in ch.fields}
        for q, t in reversed(fx):
            holes = dict(cur_f)
            holes[q] = "_"
            r = f"{X}{{{', '.join(holes[z] for z in ch.fields)}}}"
            body = f"(%Equal.sym({t}, y_{q}, {ctxn[q]}, {eqs[q][1]}) : {ch.goal(la(r))}\n        {body})"
            cur_f[q] = f"y_{q}"
        x = f"M.la_{ab}_{node.n}(M.u_nz(M.gx_{ab}_cd(y)), y)"
        self.defs.append(
            f"def {cname}({ch.fixed_params()}{ch.var_params()}, +inv: {inv(ov, f.K, state)}, +y: {X}, +hy: "
            f"{{ob_{p}({pa}{sep}y) == {ref} : {O}}}, +hz: {ch.hz(x)}) -> {ch.goal(x)}:\n  match y:\n    case {pat}:\n"
            f"      {body}\n")
        return f"{cname}({ch.fixed_args()}{ch.var_args()}, {pf}, {y}, {hy}, hz)"

    def after(self, ch: Chain, n: int, state: tuple) -> str:
        """la_<a>_<n> on the record of the loop's result (its varying fields v_<f>), the invariant on its overlay."""
        key = (ch.p, "after", n, state)
        if key in self.made:
            return self.made[key]
        ch.nb += 1
        name = f"{ch.p}_a{ch.nb}"
        self.made[key] = name
        node = ch.mi.after_loop(n, Record(f"X_{ch.ab}", [ch.fixed.get(q, f"v_{q}") for q in ch.fields]))
        x = f"M.la_{ch.ab}_{n}(M.u_nz(v_cd), {ch.vrec()})"
        body = ch.emit(node, {q: f"v_{q}" for q in ch.var}, "inv", state)
        self.defs.append(f"def {name}({ch.fixed_params()}{ch.var_params()}, +inv: {inv('v_ov', ch.f.K, state)}"
                         f"{ch.hyp_params(x)}) -> {ch.goal(x)}:\n  {body}\n")
        return name


# ------------------------------------------------------------------------------------------------ the helpers
def helpers(actions: list) -> str:
    """The generic store facts every chain uses, and per action the step's overlay and code facts."""
    W, H = "M.W", "M.HSt"
    le = lambda w, r, d: f"{{Nat.is_le({N}({w}), Nat.add({N}({r}), {N}({d}))) == True{{}} : Bool}}"
    out = [
        f"def fr_eq(+o: {H}, +kw: M.SK, +v: {W}, +k: M.SK, +r: {W}, ne1: {{M.sk_eq(kw, k) == False{{}} : Bool}}, "
        f"ne2: {{M.sk_eq(k, kw) == False{{}} : Bool}}, e: {{M.sload(o, k) == r : {W}}}) -> "
        f"{{M.sload(M.sstore(o, kw, v), k) == r : {W}}}:\n"
        f"  Equal.trans({W}, M.sload(M.sstore(o, kw, v), k), M.sload(o, k), r, st_frame(o, kw, v, k, ne1, ne2), e)\n",
        f"def fr_le(+o: {H}, +kw: M.SK, +v: {W}, +k: M.SK, +r: {W}, +d: {W}, ne1: {{M.sk_eq(kw, k) == False{{}} : Bool}}, "
        f"ne2: {{M.sk_eq(k, kw) == False{{}} : Bool}}, e: {le('M.sload(o, k)', 'r', 'd')}) -> "
        f"{le('M.sload(M.sstore(o, kw, v), k)', 'r', 'd')}:\n"
        f"  (%Equal.sym({W}, M.sload(M.sstore(o, kw, v), k), M.sload(o, k), st_frame(o, kw, v, k, ne1, ne2)) : "
        f"{le('_', 'r', 'd')}\n  e)\n",
        f"def wk(+w: {W}, +r: {W}, +d: {W}, e: {{w == r : {W}}}) -> {le('w', 'r', 'd')}:\n"
        f"  (%Equal.sym({W}, w, r, e) : {le('_', 'r', 'd')}\n  n_le_add({N}(r), {N}(d)))\n",
        f"def bnd_hit(+o: {H}, +s: {H}, +k: M.SK, +d: {W}) -> "
        f"{le('M.sload(M.sstore(o, k, M.w_add(M.sload(s, k), d)), k)', 'M.sload(s, k)', 'd')}:\n"
        f"  (%Equal.sym({W}, M.sload(M.sstore(o, k, M.w_add(M.sload(s, k), d)), k), M.w_add(M.sload(s, k), d), "
        f"st_same(o, k, M.w_add(M.sload(s, k), d))) : {le('_', 'M.sload(s, k)', 'd')}\n"
        f"  w_wrap(M.sload(s, k), d))\n",
        f"def le_rw(+a: {W}, +r1: {W}, +r2: {W}, +d1: {W}, +d2: {W}, e: {le('a', 'r1', 'd1')}, er: {{r1 == r2 : {W}}}, "
        f"ed: {{d1 == d2 : {W}}}) -> {le('a', 'r2', 'd2')}:\n"
        f"  (%er : {le('a', '_', 'd2')}\n  (%ed : {le('a', 'r1', '_')}\n  e))\n",
    ]
    return "\n".join(out)


def action_helpers(md: Model, ab: str, fields: list) -> str:
    X = f"M.X_{ab}"
    ff = [f"x_{q}" for q in fields]
    pat = f"{X}{{{', '.join('+' + v for v in ff)}}}"
    rec = f"{X}{{{', '.join(ff)}}}"
    cd = ff[fields.index("cd")]
    ov = ff[fields.index("ov")]
    return (
        f"def cdx_{ab}(x: {X}) -> {{M.o_code(M.xo_{ab}(x)) == M.gx_{ab}_cd(x) : U32}}:\n  match x:\n    case {pat}:\n"
        f"      {{==}}\n\n"
        f"def okz_{ab}(+st: M.HSt, +ar: M.AR_{ab}, +e: M.HEnv, +kh: List<&2, M.HKB>, h: {{U32.is_eq(M.chk_{ab}(st, ar, "
        f"e, kh), 0) == True{{}} : Bool}}) -> {{M.u_nz(M.gx_{ab}_cd(M.xr_{ab}(st, ar, e, kh))) == False{{}} : Bool}}:\n"
        f"  Equal.cong(U32, Bool, z => M.u_nz(z), M.gx_{ab}_cd(M.xr_{ab}(st, ar, e, kh)), 0, Equal.trans(U32, "
        f"M.gx_{ab}_cd(M.xr_{ab}(st, ar, e, kh)), M.o_code(M.xo_{ab}(M.xr_{ab}(st, ar, e, kh))), 0, Equal.sym(U32, "
        f"M.o_code(M.xo_{ab}(M.xr_{ab}(st, ar, e, kh))), M.gx_{ab}_cd(M.xr_{ab}(st, ar, e, kh)), "
        f"cdx_{ab}(M.xr_{ab}(st, ar, e, kh))), u_refl(M.chk_{ab}(st, ar, e, kh), 0, h)))\n\n"
        f"def goc_{ab}(c: Bool, {', '.join('+' + v + ': ' + t for v, t in zip(ff, md.record_types(ab)))}, +g: M.GSt, "
        f"hz: {{c == False{{}} : Bool}}) -> {{M.gh_get_st(M.gh_ok_{ab}(c, {rec}, g)) == {ov} : M.HSt}}:\n"
        f"  match c:\n    case True{{}}:\n      efq({{M.gh_get_st(M.gh_ok_{ab}(True{{}}, {rec}, g)) == {ov} : M.HSt}}, "
        f"true_ne_false(hz))\n    case False{{}}:\n      match g:\n        case M.GSt{{+gs, +gg}}:\n          {{==}}\n\n"
        f"def go_ov_{ab}(x: {X}, +g: M.GSt, hz: {{M.u_nz(M.gx_{ab}_cd(x)) == False{{}} : Bool}}) -> "
        f"{{M.gh_get_st(M.gh_go_{ab}(x, g)) == M.gx_{ab}_ov(x) : M.HSt}}:\n  match x:\n    case {pat}:\n"
        f"      goc_{ab}(M.u_nz({cd}), {', '.join(ff)}, g, hz)\n")


def step_lemma(ch: Chain, name: str) -> str:
    """{name}(g, ar, e, kh, params.., hz): the fact over gh_step(A{ar, e}, g) with st the state g holds."""
    f, ab = ch.f, ch.ab
    top = ch.top()
    F = f"M.xr_{ab}(M.gh_get_st(g), ar, e, kh)"
    s = {"st": "M.gh_get_st(g)"}
    K, G = _sub(f.K, s), tuple(_sub(x, s) for x in f.goal[1:])
    post = f"M.gh_get_st(M.gh_step(M.A_{ab}{{ar, e}}, g, kh))"
    gl = inv(post, K, (f.goal[0],) + G)
    motive = inv("_", K, (f.goal[0],) + G)
    return (f"def {name}(+g: M.GSt, +ar: M.AR_{ab}, +e: M.HEnv, +kh: List<&2, M.HKB>{f.pp()}, +hz: {{M.u_nz("
            f"M.gx_{ab}_cd({F})) == False{{}} : Bool}}) -> {gl}:\n"
            f"  (%Equal.sym(M.HSt, M.gh_get_st(M.gh_go_{ab}({F}, g)), M.gx_{ab}_ov({F}), go_ov_{ab}({F}, g, hz)) : "
            f"{motive}\n  {top}(M.gh_get_st(g), ar, e, kh{f.pa()}, hz))\n")
