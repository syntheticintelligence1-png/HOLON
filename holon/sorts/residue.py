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


class Stuck(NoProof):
    """(a probe) A store whose key meets the fact's key in a word pair no evaluation decides."""

    def __init__(self, kw: str, v: str, at: tuple):
        super().__init__(f"a store at {kw[:120]} meets the key")
        self.kw, self.v, self.at = kw, v, at


PROBE: list = []      # non-empty while a probe runs: Chain.conclude records end states, a stuck store raises Stuck


def _sub(t: str, ren: dict) -> str:
    """t with the identifiers of ren renamed (whole names, not fields or qualified names)."""
    if not ren:
        return t
    pat = re.compile(r"(?<![\w.])(" + "|".join(re.escape(k) for k in ren) + r")(?![\w{])")
    return pat.sub(lambda m: ren[m.group(1)], t)


def _strip(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip())


def fuel_lit(t: str) -> str:
    """A loop's fuel U32.to_nat(n) written as the Nat literal n: the same value, but the checker compares two literals
    at once where it would walk two unary numerals built apart (a conversion at a loop statement compares the
    model's fuel with the proof's)."""
    m = re.fullmatch(r"U32\.to_nat\((\d+)\)", t.strip())
    return f"{int(m.group(1))}n" if m else t.strip()


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
                if PROBE:
                    raise Stuck(kw, v, at)
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
        if PROBE:
            PROBE[-1].add(state)
            return "{==}"
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

    def acc(self, ch: Chain, L: int):
        key = (ch.p, "acc", L)
        if key not in self.made:
            try:
                self.made[key] = Acc(self.md, ch, L, self.defs)
            except NoProof as e:
                self.made[key] = e
        return self.made[key]

    def at(self, ch: Chain, node: Loop, cur: dict, pf: str, state: tuple) -> str:
        if ch.f.goal[0] == "le" and state[0] == "eq":
            acc = self.acc(ch, node.L)
            if isinstance(acc, Acc):
                return self.at_acc(ch, acc, node, pf, state)
        if state[0] != "eq":
            raise NoProof(f"{ch.ab}: its loop {node.L} meets a bounded fact (an accumulating loop is not built here)")
        vals = ch.vals(node.rec.fields)
        p, cx = self.lemmas(ch, node.L)
        f, ab, X, O = ch.f, ch.ab, ch.X, f"Ob_{p}"
        pa = (f.pa() + "".join(f", {c}" for c, _n, _t in cx))[2:]
        sep = ", " if pa else ""
        ov = vals["ov"]
        ls = f"M.ls_{ab}_{node.L}({ch.rec(vals)})"
        y = f"M.lp_{ab}_{node.L}({fuel_lit(node.fuel)}, {node.d}, {ls})"
        ref = f"{O}{{st, ar, e, kh, M.sload({ov}, {f.K})}}"
        hy = f"{p}_lp({fuel_lit(node.fuel)}, {node.d}, {pa}{sep}{ls}, {ref}, {{==}})"
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

    def rewrite_fixed(self, ch: Chain, O: str, obq: str, ref: str, getter: str, inner: str, la, hz: str):
        """(hz rewritten to the context's fixed fields, the goal's proof from inner with them rewritten back)."""
        ab, X = ch.ab, ch.X
        fx = [("st", "M.HSt"), ("ar", f"M.AR_{ab}"), ("en", "M.HEnv"), ("kh", "List<&2, M.HKB>")]
        eqs = {q: (t, f"Equal.cong({O}, {t}, z => {getter}_g{i}(z), {obq}, {ref}, hy)") for i, (q, t) in enumerate(fx)}
        ctxn = {q: FX[q] for q, _t in fx}
        cur_f = {q: f"y_{q}" for q in ch.fields}
        for q, _t in fx:
            holes = dict(cur_f)
            holes[q] = "_"
            r = f"{X}{{{', '.join(holes[z] for z in ch.fields)}}}"
            hz = f"(%{eqs[q][1]} : {ch.hz(la(r))}\n        {hz})"
            cur_f[q] = ctxn[q]
        body = inner.replace("@HZ@", hz)
        cur_f = {q: ctxn.get(q, f"y_{q}") for q in ch.fields}
        for q, t in reversed(fx):
            holes = dict(cur_f)
            holes[q] = "_"
            r = f"{X}{{{', '.join(holes[z] for z in ch.fields)}}}"
            body = f"(%Equal.sym({t}, y_{q}, {ctxn[q]}, {eqs[q][1]}) : {ch.goal(la(r))}\n        {body})"
            cur_f[q] = f"y_{q}"
        return body, eqs

    def at_acc(self, ch: Chain, acc: Acc, node: Loop, pf: str, state: tuple) -> str:
        """The accumulating loop: its observation from the start (inv at it = 0, the shadow the pre-state), through
        the fuel induction, then the continuation from the bound its invariant gives."""
        acc.lemmas()
        vals = ch.vals(node.rec.fields)
        ab, X, q, O, ob = ch.ab, ch.X, acc.q, acc.n("Ob"), acc.n("ob")
        OV, CD = vals["ov"], vals["cd"]
        ls = f"M.ls_{ab}_{node.L}({ch.rec(vals)})"
        y = f"M.lp_{ab}_{node.L}({fuel_lit(node.fuel)}, {node.d}, {ls})"
        inv0 = f"{acc.n('inv')}({q}, st, {OV}, st, M.w0())"
        oT = f"{O}{{st, ar, e, kh, True{{}}}}"
        h0 = (f"(%Equal.sym(Bool, Bool.or(M.u_nz({CD}), {inv0}), True{{}}, or_r(M.u_nz({CD}), {inv0}, "
              f"{acc.n('init')}({q}, st, {OV}, {pf}))) : {{{O}{{st, ar, e, kh, _}} == {oT} : {O}}}\n        {{==}})")
        hy = f"{acc.p}_lp({fuel_lit(node.fuel)}, {node.d}, {q}, {ls}, st, ar, e, kh, {h0})"
        ch.nb += 1
        cname = f"{ch.p}_c{ch.nb}"
        aname = self.after_acc(ch, acc, node.n)
        ys = [f"y_{z}" for z in ch.fields]
        pat = f"{X}{{{', '.join('+' + v for v in ys)}}}"
        yrec = f"{X}{{{', '.join(ys)}}}"
        obq = f"{ob}({q}, {yrec})"
        la = lambda r: f"M.la_{ab}_{node.n}(M.u_nz(y_cd), {r})"
        hiy0 = f"Equal.cong({O}, Bool, z => {ob}_g4(z), {obq}, {oT}, hy)"
        hiy = (f"(%Equal.cong({O}, M.HSt, z => {ob}_g0(z), {obq}, {oT}, hy) : {{Bool.or(M.u_nz(y_cd), "
               f"{acc.n('inv')}({q}, _, y_ov, y_{acc.SH}, y_{acc.IX})) == True{{}} : Bool}}\n        {hiy0})")
        inner = f"{aname}({ch.fixed_args()}" + "".join(f", y_{z}" for z in ch.var) + f", {hiy}, @HZ@)"
        body, _eqs = self.rewrite_fixed(ch, O, obq, oT, ob, inner, la, "hz")
        x = f"M.la_{ab}_{node.n}(M.u_nz(M.gx_{ab}_cd(y)), y)"
        self.defs.append(
            f"def {cname}({ch.fixed_params()}, +y: {X}, +hy: {{{ob}({q}, y) == {oT} : {O}}}, +hz: {ch.hz(x)}) -> "
            f"{ch.goal(x)}:\n  match y:\n    case {pat}:\n      {body}\n")
        return f"{cname}({ch.fixed_args()}, {y}, {hy}, hz)"

    def after_acc(self, ch: Chain, acc: Acc, n: int) -> str:
        key = (ch.p, "after_acc", n)
        if key in self.made:
            return self.made[key]
        ch.nb += 1
        name = f"{ch.p}_aa{ch.nb}"
        self.made[key] = name
        rv = [ch.fixed.get(z, f"v_{z}") for z in ch.fields]
        node = ch.mi.after_loop(n, Record(f"X_{ch.ab}", rv))
        if not isinstance(node, Branch) or not isinstance(node.other, Next):
            raise NoProof(f"{ch.ab}: its loop statement {n} does not continue to a next statement")
        REC = ch.vrec()
        la = lambda c: f"M.la_{ch.ab}_{n}({c}, {REC})"
        q = acc.q
        invv = f"{acc.n('inv')}({q}, st, v_ov, v_{acc.SH}, v_{acc.IX})"
        hI = f"+hI: {{Bool.or(M.u_nz(v_cd), {invv}) == True{{}} : Bool}}"
        bnd = (f"{acc.n('bnd')}({q}, st, v_ov, v_{acc.SH}, v_{acc.IX}, (%ec : {{Bool.or(_, {invv}) == True{{}} : Bool}}\n"
               f"      hI))")
        nxt = ch.call(ch.stmt(node.other.j, ch.f.goal), ch.vals(node.other.fields), bnd)
        self.defs.append(
            f"def {name}c(c: Bool, {ch.fixed_params()}{ch.var_params()}, {hI}, +ec: {{M.u_nz(v_cd) == c : Bool}}, "
            f"+hz: {ch.hz(la('c'))}) -> {ch.goal(la('c'))}:\n  match c:\n    case True{{}}:\n"
            f"      efq({ch.goal(la('True{}'))}, true_ne_false(Equal.trans(Bool, True{{}}, M.u_nz(v_cd), False{{}}, "
            f"Equal.sym(Bool, M.u_nz(v_cd), True{{}}, ec), hz)))\n    case False{{}}:\n      {nxt}\n")
        self.defs.append(
            f"def {name}({ch.fixed_params()}{ch.var_params()}, {hI}, +hz: {ch.hz(la('M.u_nz(v_cd)'))}) -> "
            f"{ch.goal(la('M.u_nz(v_cd)'))}:\n  {name}c(M.u_nz(v_cd), {ch.fixed_args()}{ch.var_args()}, hI, {{==}}, hz)\n")
        return name

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
        "def neq_r(+a: Nat) -> {Nat.is_eq(a, a) == True{} : Bool}:\n"
        "  (%Equal.sym(Cmp, Nat.cmp(a, a), EQ{}, n_cmp_refl(a)) : {Cmp.is_eq(_) == True{} : Bool}\n  {==})\n",
        "def neq_t(a: Nat, b: Nat, e: {Nat.is_eq(a, b) == True{} : Bool}) -> {a == b : Nat}:\n  match a b:\n"
        "    case 0n 0n:\n      {==}\n    case 0n 1n+q:\n      efq({0n == 1n+q : Nat}, false_ne_true(e))\n"
        "    case 1n+p 0n:\n      efq({1n+p == 0n : Nat}, false_ne_true(e))\n"
        "    case 1n+p 1n+q:\n      Equal.cong(Nat, Nat, z => 1n+z, p, q, neq_t(p, q, e))\n",
        "def neq_i(+a: Nat, +b: Nat, e: {a == b : Nat}) -> {Nat.is_eq(a, b) == True{} : Bool}:\n"
        "  (%Equal.sym(Nat, a, b, e) : {Nat.is_eq(_, b) == True{} : Bool}\n  neq_r(b))\n",
        f"def weq_i(+a: {W}, +b: {W}, e: {{a == b : {W}}}) -> {{M.w_eq(a, b) == True{{}} : Bool}}:\n"
        f"  (%Equal.sym({W}, a, b, e) : {{M.w_eq(_, b) == True{{}} : Bool}}\n  w_eq_self(b))\n",
        "def or_l(a: Bool, +b: Bool, +e: {a == True{} : Bool}) -> {Bool.or(a, b) == True{} : Bool}:\n  match a:\n"
        "    case True{}:\n      {==}\n    case False{}:\n      efq({Bool.or(False{}, b) == True{} : Bool}, false_ne_true(e))\n",
        "def or_r(a: Bool, +b: Bool, +e: {b == True{} : Bool}) -> {Bool.or(a, b) == True{} : Bool}:\n  match a:\n"
        "    case True{}:\n      {==}\n    case False{}:\n      e\n",
        "def val_up(a: Bool, +l: Bool, +t1: Bool, +t2: Bool, +e: {Bool.or(a, Bool.and(l, t1)) == True{} : Bool}, "
        "f: {t1 == True{} : Bool} -> {t2 == True{} : Bool}) -> {Bool.or(a, Bool.and(l, t2)) == True{} : Bool}:\n"
        "  match a:\n    case True{}:\n      {==}\n    case False{}:\n"
        "      and_intro(l, t2, and_l(l, t1, e), f(and_r(l, t1, e)))\n",
        "def val_hit(a: Bool, +l: Bool, +t1: Bool, +x: Bool, ea: {a == True{} : Bool} -> {x == True{} : Bool}, "
        "eb: {Bool.and(l, t1) == True{} : Bool} -> {x == True{} : Bool}, e: {Bool.or(a, Bool.and(l, t1)) == True{} : "
        "Bool}) -> {x == True{} : Bool}:\n  match a:\n    case True{}:\n      ea({==})\n    case False{}:\n      eb(e)\n",
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


# ------------------------------------------------------------------------------------------------ accumulating loops
W1 = "M.W{1, 0, 0, 0, 0, 0, 0, 0}"
LOOP_PARTS = ("li", "lh", "lb", "lc", "lk", "ln", "lbk", "lx", "lz", "ls")


class Acc:
    """A loop that adds D to the word at its key K(c0 + it) of the overlay and of a shadow store it reads, once per
    iteration, it stepping by one under the checked increment of c0 + it (holon.sorts.residue_lemmas' ks_*): the
    word at the fact's key k grows by at most D over the whole loop. The invariant (inv_<p>, over the record's own
    pre-state s, overlay ov, shadow c1 and index it) is

      N(c0 + it) == N(c0) + N(it),  ov and c1 agree at k,  and c1 holds at k the pre-state's word, or a word at most
      N(pre-state's) + N(D) with N(k) < N(c0 + it) (k already met)

    or the record's code is not 0 (a revert ends the loop). It is the last component of the loop's observation, the
    others the record's fixed fields, kept by every iteration and by induction on the fuel."""

    def __init__(self, md: Model, ch: "Chain", L: int, defs: list):
        self.md, self.ch, self.L, self.defs = md, ch, L, defs
        f = ch.f
        if f.goal[0] != "le" or len(f.params) != 1 or f.params[0][1] != "M.W":
            raise NoProof(f"{ch.ab}: an accumulating loop needs a bounded fact at a key of one word")
        self.q = f.params[0][0]
        self.K, self.D = f.K, f.goal[2]
        if f.goal[1] != f"M.sload(st, {self.K})":
            raise NoProof(f"{ch.ab}: the bounded fact is not over the pre-state's word")
        ab, mi = ch.ab, ch.mi
        self.ab, self.p, self.X = ab, f"{ch.p}A{L}", ch.X
        vals = [ch.fixed.get(q, f"v_{q}") for q in ch.fields]
        lc = mi.apply(f"lb_{ab}_{L}", [Record(f"X_{ab}", vals)])
        if not isinstance(lc, Branch) or not isinstance(lc.other, Record) or lc.cond.strip() != "M.u_nz(v_cd)":
            raise NoProof(f"{ab}: its loop {L}'s step is not of the known shape (lb, lc)")
        ln = dict(zip(ch.fields, [x.strip() for x in lc.other.fields]))
        self.IX = self.SH = None
        for q, v in ln.items():
            if v == f"M.w_add(v_{q}, M.w_u(1))":
                self.IX = q
            c = as_call(v)
            if c and c[0] == "M.ite" and len(c[1]) == 4 and c[1][0].strip() == "M.HSt" and c[1][3].strip() == f"v_{q}":
                self.SH, self.COND = q, _strip(c[1][1])
                s = as_call(c[1][2].strip())
                if not s or s[0] != "M.sstore" or s[1][0].strip() != f"v_{q}":
                    raise NoProof(f"{ab}: its loop {L}'s shadow store is not of the known shape")
                self.KEYW, self.VAL = _strip(s[1][1]), _strip(s[1][2])
        if self.IX is None or self.SH is None:
            raise NoProof(f"{ab}: its loop {L} has no index stepping by one and shadow store")
        from ..disch.proofs import sk_parts
        pk, pf = sk_parts(self.KEYW), sk_parts(self.K)
        if not pk or not pf or pk[:2] != pf[:2] or len(pk[2]) != 1 or len(pf[2]) != 1 or pk[2][0][1] != pf[2][0][1] \
                or pf[2][0][0] != self.q:
            raise NoProof(f"{ab}: its loop {L} stores at {self.KEYW[:120]}, not the fact's key at another word")
        self.KW = _strip(pk[2][0][0])
        c = as_call(self.KW)
        if not c or c[0] != "M.w_add" or c[1][1].strip() != f"v_{self.IX}" or re.search(r"(?<![\w.])v_\w+", c[1][0]):
            raise NoProof(f"{ab}: its loop {L}'s key word is not c0 + its index")
        self.C0 = _strip(c[1][0])
        if _strip(norm_value(self.VAL)) != _strip(f"M.w_add(M.sload(v_{self.SH}, {self.KEYW}), {self.D})"):
            raise NoProof(f"{ab}: its loop {L} stores {self.VAL[:120]}, not the shadow's word plus the fact's bound")
        ls = mi.apply(f"ls_{ab}_{L}", [Record(f"X_{ab}", vals)])
        lsd = dict(zip(ch.fields, [x.strip() for x in ls.fields])) if isinstance(ls, (Record, Final)) else {}
        if lsd.get(self.SH) != "st" or lsd.get(self.IX) != "M.w0()" or lsd.get("ov") != "v_ov" or lsd.get("cd") != "v_cd":
            raise NoProof(f"{ab}: its loop {L} does not start its shadow at the pre-state and its index at 0")
        self.nb = 0
        self.made = False

    # names and terms
    def n(self, s: str) -> str:
        return f"{s}_{self.p}"

    def kat(self, w: str) -> str:
        return _sub(self.K, {self.q: w})

    def lemmas(self) -> None:
        if self.made:
            return
        self.made = True
        q, K, p = self.q, self.K, self.p
        c0, kw, dd, invw, inv_ = self.n("c0"), self.n("kw"), self.n("dd"), self.n("invw"), self.n("inv")
        J = lambda s, it: f"Nat.is_eq({N}({kw}({s}, {it})), Nat.add({N}({c0}({s})), {N}({it})))"
        SY = lambda wo, wc: f"M.w_eq({wo}, {wc})"
        A = lambda s: f"M.sload({s}, {K})"
        EQA = lambda wc, s: f"M.w_eq({wc}, {A(s)})"
        LE = lambda wc, s: f"Nat.is_le({N}({wc}), Nat.add({N}({A(s)}), {N}({dd}({s}))))"
        LT = lambda s, it: f"Nat.is_lt({N}({q}), {N}({kw}({s}, {it})))"
        VL = lambda wc, s, it: f"Bool.or({EQA(wc, s)}, Bool.and({LE(wc, s)}, {LT(s, it)}))"
        it1 = f"M.w_add(it, {W1})"
        X = self.X
        d = [f"def {c0}(+s: M.HSt) -> M.W:\n  {_sub(self.C0, {'st': 's'})}\n",
             f"def {kw}(+s: M.HSt, +it: M.W) -> M.W:\n  M.w_add({c0}(s), it)\n",
             f"def {dd}(+s: M.HSt) -> M.W:\n  {_sub(self.D, {'st': 's'})}\n",
             f"def {invw}(+{q}: M.W, +s: M.HSt, +wo: M.W, +wc: M.W, +it: M.W) -> Bool:\n"
             f"  Bool.and({J('s', 'it')}, Bool.and({SY('wo', 'wc')}, {VL('wc', 's', 'it')}))\n",
             f"def {inv_}(+{q}: M.W, +s: M.HSt, +ov: M.HSt, +c1: M.HSt, +it: M.W) -> Bool:\n"
             f"  {invw}({q}, s, M.sload(ov, {K}), M.sload(c1, {K}), it)\n"]
        hdr = (f"+{q}: M.W, +s: M.HSt, +wo: M.W, +wc: M.W, +it: M.W, +hI: {{{invw}({q}, s, wo, wc, it) == True{{}} : "
               f"Bool}}, +ok: {{M.w_add_ok({kw}(s, it), {W1}) == True{{}} : Bool}}")
        lets = (f"  +hJ = and_l({J('s', 'it')}, Bool.and({SY('wo', 'wc')}, {VL('wc', 's', 'it')}), hI)\n"
                f"  +hR = and_r({J('s', 'it')}, Bool.and({SY('wo', 'wc')}, {VL('wc', 's', 'it')}), hI)\n"
                f"  +hS = and_l({SY('wo', 'wc')}, {VL('wc', 's', 'it')}, hR)\n"
                f"  +hV = and_r({SY('wo', 'wc')}, {VL('wc', 's', 'it')}, hR)\n"
                f"  +Je = neq_t({N}({kw}(s, it)), Nat.add({N}({c0}(s)), {N}(it)), hJ)\n")
        jn = (f"neq_i({N}({kw}(s, {it1})), Nat.add({N}({c0}(s)), {N}({it1})), ks_j({c0}(s), it, Je, ok))")
        kss = f"ks_s({c0}(s), it, Je, ok)"
        ltup = (f"h => (%Equal.sym(Nat, {N}({kw}(s, {it1})), Nat.add({N}({kw}(s, it)), {N}({W1})), {kss}) : "
                f"{{Nat.is_lt({N}({q}), _) == True{{}} : Bool}}\n    lt_up({N}({q}), {N}({kw}(s, it)), h))")
        # the index steps, the key is not met (or not written)
        d.append(f"def {self.n('stn')}({hdr}) -> {{{invw}({q}, s, wo, wc, {it1}) == True{{}} : Bool}}:\n{lets}"
                 f"  and_intro({J('s', it1)}, Bool.and({SY('wo', 'wc')}, {VL('wc', 's', it1)}), {jn}, "
                 f"and_intro({SY('wo', 'wc')}, {VL('wc', 's', it1)}, hS, val_up({EQA('wc', 's')}, {LE('wc', 's')}, "
                 f"{LT('s', 'it')}, {LT('s', it1)}, hV, {ltup})))\n")
        # the key is met: the word becomes wc + D, at most the pre-state's + D, and k < c0 + it + 1
        VW = f"M.w_add(wc, {dd}(s))"
        lsucc = (f"(%Equal.sym(Nat, {N}({kw}(s, {it1})), Nat.add({N}({kw}(s, it)), {N}({W1})), {kss}) : "
                 f"{{Nat.is_lt({N}({q}), _) == True{{}} : Bool}}\n  (%Equal.sym(M.W, {kw}(s, it), {q}, e) : "
                 f"{{Nat.is_lt({N}({q}), Nat.add({N}(_), {N}({W1}))) == True{{}} : Bool}}\n  lt_succ({N}({q}))))")
        casea = (f"h1 => (%Equal.sym(M.W, wc, {A('s')}, w_refl(wc, {A('s')}, h1)) : {{Nat.is_le({N}(M.w_add(_, {dd}(s))), "
                 f"Nat.add({N}({A('s')}), {N}({dd}(s)))) == True{{}} : Bool}}\n    w_wrap({A('s')}, {dd}(s)))")
        caseb = (f"h2 => efq({{{LE(VW, 's')} == True{{}} : Bool}}, false_ne_true(Equal.trans(Bool, False{{}}, "
                 f"Nat.is_lt({N}({q}), {N}({q})), True{{}}, Equal.sym(Bool, Nat.is_lt({N}({q}), {N}({q})), False{{}}, "
                 f"lt_irr({N}({q}))), (%e : {{Nat.is_lt({N}({q}), {N}(_)) == True{{}} : Bool}}\n    "
                 f"and_r({LE('wc', 's')}, {LT('s', 'it')}, h2)))))")
        lep = f"val_hit({EQA('wc', 's')}, {LE('wc', 's')}, {LT('s', 'it')}, {LE(VW, 's')}, {casea}, {caseb}, hV)"
        d.append(f"def {self.n('hit')}({hdr}, +e: {{{kw}(s, it) == {q} : M.W}}) -> {{{invw}({q}, s, {VW}, {VW}, {it1}) "
                 f"== True{{}} : Bool}}:\n{lets}"
                 f"  and_intro({J('s', it1)}, Bool.and({SY(VW, VW)}, {VL(VW, 's', it1)}), {jn}, "
                 f"and_intro({SY(VW, VW)}, {VL(VW, 's', it1)}, w_eq_self({VW}), or_r({EQA(VW, 's')}, "
                 f"Bool.and({LE(VW, 's')}, {LT('s', it1)}), and_intro({LE(VW, 's')}, {LT('s', it1)}, {lep}, {lsucc}))))\n")
        # the step with the store: by cases on the key word meeting k
        Kw = self.kat(f"{kw}(s, it)")
        V = lambda key: f"M.w_add(M.sload(c1, {key}), {dd}(s))"
        RO = f"M.sload(M.sstore(ov, {Kw}, {V(Kw)}), {K})"
        RC = f"M.sload(M.sstore(c1, {Kw}, {V(Kw)}), {K})"
        goal_w = f"{{{invw}({q}, s, {RO}, {RC}, {it1}) == True{{}} : Bool}}"
        hw = (f"+{q}: M.W, +s: M.HSt, +ov: M.HSt, +c1: M.HSt, +it: M.W, +hI: {{{inv_}({q}, s, ov, c1, it) == True{{}} : "
              f"Bool}}, +ok: {{M.w_add_ok({kw}(s, it), {W1}) == True{{}} : Bool}}")
        ne1, ne2 = sk_ne_proof(Kw, K, "ec"), sk_ne_proof(K, Kw, f"w_ne_sym({kw}(s, it), {q}, ec)")
        if ne1 is None or ne2 is None:
            raise NoProof(f"{self.ab}: no key inequality for its loop's key")
        Kh = self.kat("_")
        VQ = V(K)
        hit = (f"(%Equal.sym(M.W, M.sload(M.sstore(ov, {K}, {VQ}), {K}), {VQ}, st_same(ov, {K}, {VQ})) : "
               f"{{{invw}({q}, s, _, M.sload(M.sstore(c1, {K}, {VQ}), {K}), {it1}) == True{{}} : Bool}}\n"
               f"        (%Equal.sym(M.W, M.sload(M.sstore(c1, {K}, {VQ}), {K}), {VQ}, st_same(c1, {K}, {VQ})) : "
               f"{{{invw}({q}, s, {VQ}, _, {it1}) == True{{}} : Bool}}\n"
               f"        {self.n('hit')}({q}, s, M.sload(ov, {K}), M.sload(c1, {K}), it, hI, ok, e)))")
        d.append(
            f"def {self.n('stwc')}(c: Bool, {hw}, +ec: {{M.w_eq({kw}(s, it), {q}) == c : Bool}}) -> {goal_w}:\n"
            f"  match c:\n    case True{{}}:\n      +e = w_refl({kw}(s, it), {q}, ec)\n"
            f"      (%Equal.sym(M.W, {kw}(s, it), {q}, e) : {{{invw}({q}, s, M.sload(M.sstore(ov, {Kh}, {V(Kh)}), {K}), "
            f"M.sload(M.sstore(c1, {Kh}, {V(Kh)}), {K}), {it1}) == True{{}} : Bool}}\n      {hit})\n"
            f"    case False{{}}:\n"
            f"      (%Equal.sym(M.W, {RO}, M.sload(ov, {K}), st_frame(ov, {Kw}, {V(Kw)}, {K}, {ne1}, {ne2})) : "
            f"{{{invw}({q}, s, _, {RC}, {it1}) == True{{}} : Bool}}\n"
            f"      (%Equal.sym(M.W, {RC}, M.sload(c1, {K}), st_frame(c1, {Kw}, {V(Kw)}, {K}, {ne1}, {ne2})) : "
            f"{{{invw}({q}, s, M.sload(ov, {K}), _, {it1}) == True{{}} : Bool}}\n"
            f"      {self.n('stn')}({q}, s, M.sload(ov, {K}), M.sload(c1, {K}), it, hI, ok)))\n")
        d.append(f"def {self.n('stw')}({hw}) -> {goal_w}:\n"
                 f"  {self.n('stwc')}(M.w_eq({kw}(s, it), {q}), {q}, s, ov, c1, it, hI, ok, {{==}})\n")
        # the start and the end
        w0 = "M.w0()"
        d.append(f"def {self.n('init')}(+{q}: M.W, +s: M.HSt, +ov: M.HSt, +e: {{M.sload(ov, {K}) == {A('s')} : M.W}}) -> "
                 f"{{{inv_}({q}, s, ov, s, {w0}) == True{{}} : Bool}}:\n"
                 f"  and_intro({J('s', w0)}, Bool.and({SY(f'M.sload(ov, {K})', A('s'))}, {VL(A('s'), 's', w0)}), "
                 f"neq_i({N}({kw}(s, {w0})), Nat.add({N}({c0}(s)), {N}({w0})), ks_0({c0}(s))), "
                 f"and_intro({SY(f'M.sload(ov, {K})', A('s'))}, {VL(A('s'), 's', w0)}, weq_i(M.sload(ov, {K}), {A('s')}, e), "
                 f"or_l({EQA(A('s'), 's')}, Bool.and({LE(A('s'), 's')}, {LT('s', w0)}), w_eq_self({A('s')}))))\n")
        wo, wc = f"M.sload(ov, {K})", f"M.sload(c1, {K})"
        d.append(f"def {self.n('bnd')}(+{q}: M.W, +s: M.HSt, +ov: M.HSt, +c1: M.HSt, +it: M.W, +hI: {{{inv_}({q}, s, ov, c1, "
                 f"it) == True{{}} : Bool}}) -> {{{LE(wo, 's')} == True{{}} : Bool}}:\n"
                 f"  +hR = and_r({J('s', 'it')}, Bool.and({SY(wo, wc)}, {VL(wc, 's', 'it')}), hI)\n"
                 f"  +hS = and_l({SY(wo, wc)}, {VL(wc, 's', 'it')}, hR)\n"
                 f"  +hV = and_r({SY(wo, wc)}, {VL(wc, 's', 'it')}, hR)\n"
                 f"  (%Equal.sym(M.W, {wo}, {wc}, w_refl({wo}, {wc}, hS)) : {{Nat.is_le({N}(_), Nat.add({N}({A('s')}), "
                 f"{N}({dd}(s)))) == True{{}} : Bool}}\n"
                 f"  val_hit({EQA(wc, 's')}, {LE(wc, 's')}, {LT('s', 'it')}, {LE(wc, 's')}, h1 => wk({wc}, {A('s')}, "
                 f"{dd}(s), w_refl({wc}, {A('s')}, h1)), h2 => and_l({LE(wc, 's')}, {LT('s', 'it')}, h2), hV))\n")
        # the observation and the fuel induction
        ab, L, O, ob = self.ab, self.L, self.n("Ob"), self.n("ob")
        fields = self.ch.fields
        tys = ["M.HSt", f"M.AR_{ab}", "M.HEnv", "List<&2, M.HKB>", "Bool"]
        pat = f"{X}{{{', '.join('+x_' + z for z in fields)}}}"
        xrec = f"{X}{{{', '.join('x_' + z for z in fields)}}}"
        d.append(f"type {O} is Data:\n  {O}{{{', '.join(f'f{i}: {t}' for i, t in enumerate(tys))}}}\n")
        d.append(f"def {ob}(+{q}: M.W, r: {X}) -> {O}:\n  match r:\n    case {pat}:\n"
                 f"      {O}{{x_st, x_ar, x_en, x_kh, Bool.or(M.u_nz(x_cd), {inv_}({q}, x_st, x_ov, x_{self.SH}, "
                 f"x_{self.IX}))}}\n")
        gs = ", ".join(f"+a{i}" for i in range(5))
        for i, t in enumerate(tys):
            d.append(f"def {ob}_g{i}(o: {O}) -> {t}:\n  match o:\n    case {O}{{{gs}}}:\n      a{i}\n")
        oo = f"{O}{{o0, o1, o2, o3, True{{}}}}"
        op = f"+o0: M.HSt, +o1: M.AR_{ab}, +o2: M.HEnv, +o3: List<&2, M.HKB>"
        self.defs.extend(d)
        # one iteration: the tree of li, each leaf's observation
        ch = self.ch
        vals = [ch.fixed.get(z, f"v_{z}") for z in fields]
        node = ch.mi.apply(f"li_{ab}_{L}", [Record(f"X_{ab}", vals)])
        body = self.emit(node, [])
        rec = f"{X}{{{', '.join(vals)}}}"
        self.defs.append(f"def {p}_top({self.scope_params()}) -> {self.goal(f'M.li_{ab}_{L}({rec})')}:\n  {body}\n")
        hI = f"Equal.cong({O}, Bool, z => {ob}_g4(z), {ob}({q}, {xrec}), {oo}, h)"
        var = [z for z in fields if z not in self.ch.fixed]
        self.defs.append(
            f"def {p}_li(+{q}: M.W, +x: {X}, {op}, +h: {{{ob}({q}, x) == {oo} : {O}}}) -> {{{ob}({q}, M.li_{ab}_{L}(x)) == "
            f"{oo} : {O}}}:\n  match x:\n    case {pat}:\n"
            f"      Equal.trans({O}, {ob}({q}, M.li_{ab}_{L}({xrec})), {O}{{x_st, x_ar, x_en, x_kh, True{{}}}}, {oo}, "
            f"{p}_top(x_st, x_ar, x_en, x_kh, {q}" + "".join(f", x_{z}" for z in var) + f", {hI}), "
            f"(%{hI} : {{{O}{{x_st, x_ar, x_en, x_kh, _}} == {oo} : {O}}}\n      h))\n")
        ld = f"M.gx_{ab}_ld{L}"
        self.defs.append(
            f"def {p}_lp(f: Nat, +d: Nat, +{q}: M.W, +x: {X}, {op}, +h: {{{ob}({q}, x) == {oo} : {O}}}) -> "
            f"{{{ob}({q}, M.lp_{ab}_{L}(f, d, x)) == {oo} : {O}}}:\n"
            f"  match f:\n    case 0n:\n      match d:\n        case 0n:\n          h\n        case 1n+q:\n"
            f"          match q:\n            case 0n:\n              match x:\n                case {pat}:\n"
            f"                  (%{hI} : {{{O}{{x_st, x_ar, x_en, x_kh, _}} == {oo} : {O}}}\n                  h)\n"
            f"            case 1n+s:\n              h\n"
            f"    case 1n+r:\n      match d:\n        case 0n:\n          h\n        case 1n+q:\n"
            f"          match q:\n            case 0n:\n"
            f"              {p}_lp(r, {ld}(M.li_{ab}_{L}(x)), {q}, M.li_{ab}_{L}(x), o0, o1, o2, o3, "
            f"{p}_li({q}, x, o0, o1, o2, o3, h))\n            case 1n+s:\n              h\n")

    # the iteration's lemmas
    def scope_params(self, carried: list = ()) -> str:
        ch = self.ch
        out = f"+st: M.HSt, +ar: M.AR_{self.ab}, +e: M.HEnv, +kh: List<&2, M.HKB>, +{self.q}: M.W{ch.var_params()}"
        out += (f", +hI: {{Bool.or(M.u_nz(v_cd), {self.n('inv')}({self.q}, st, v_ov, v_{self.SH}, v_{self.IX})) == "
                f"True{{}} : Bool}}")
        return out + "".join(f", +hc{i}: {{{c} == {'True' if v else 'False'}{{}} : Bool}}"
                             for i, (_fn, c, v, _nm) in enumerate(carried))

    def scope_args(self, carried: list = ()) -> str:
        return f"st, ar, e, kh, {self.q}{self.ch.var_args()}, hI" + "".join(f", {nm}" for _f, _c, _v, nm in carried)

    def goal(self, x: str) -> str:
        head = re.match(r"M\.(\w+)\(", x.strip())
        own = head is not None and head.group(1).startswith(tuple(f"{z}_{self.ab}_" for z in LOOP_PARTS))
        t = x if own else f"M.lb_{self.ab}_{self.L}({x})"
        return f"{{{self.n('ob')}({self.q}, {t}) == {self.n('Ob')}{{st, ar, e, kh, True{{}}}} : {self.n('Ob')}}}"

    def emit(self, node, carried: list) -> str:
        mi, ab = self.ch.mi, self.ab
        if isinstance(node, Branch):
            return self.branch(node, carried)
        if isinstance(node, Next):
            return self.emit(mi.step(node.j, list(node.fields)), carried)
        if isinstance(node, Final):
            return self.emit(mi.apply(f"lb_{ab}_{self.L}", [Record(f"X_{ab}", list(node.fields))]), carried)
        if isinstance(node, Record):
            return self.leaf(node, carried)
        raise NoProof(f"{ab}: its loop {self.L} holds a {type(node).__name__} the accumulating route does not step")

    def branch(self, br: Branch, carried: list) -> str:
        self.nb += 1
        name = f"{self.p}_b{self.nb}"
        x = f"{br.fn}(c, {', '.join(br.args)})"
        inner = [(f, c, v, f"hc{i}") for i, (f, c, v, _nm) in enumerate(carried)]
        cond = _strip(br.cond)
        lit = re.fullmatch(r"M\.u_nz\((\d+)\)", cond)
        arms = []
        for val, sub in ((True, br.then), (False, br.other)):
            if lit and (int(lit.group(1)) != 0) != val:
                g = self.goal(f"{br.fn}({'True' if val else 'False'}{{}}, {', '.join(br.args)})")
                arms.append(f"efq({g}, {'false_ne_true' if val else 'true_ne_false'}(ec))")
            else:
                arms.append(self.emit(sub, inner + [(br.fn, cond, val, "ec")]))
        self.defs.append(f"def {name}(c: Bool, {self.scope_params(carried)}, +ec: {{{br.cond} == c : Bool}}) -> "
                         f"{self.goal(x)}:\n  match c:\n    case True{{}}:\n      {arms[0]}\n    case False{{}}:\n"
                         f"      {arms[1]}\n")
        return f"{name}({br.cond}, {self.scope_args(carried)}, {{==}})"

    def fact(self, carried: list, fn_part: str):
        for f, c, v, nm in carried:
            if f.startswith(f"M.{fn_part}_{self.ab}_"):
                yield c, v, nm

    def leaf(self, rec: Record, carried: list) -> str:
        ch, q = self.ch, self.q
        d = dict(zip(ch.fields, [x.strip() for x in rec.fields]))
        for z, want in ch.fixed.items():
            if d[z] != want:
                raise NoProof(f"{self.ab}: its loop changes its context's {z}")
        O = self.n("Ob")
        cd = d["cd"]
        if re.fullmatch(r"\d+", cd) and int(cd) != 0:
            return "{==}"
        invl = f"{self.n('inv')}({q}, st, {d['ov']}, {d[self.SH]}, {d[self.IX]})"
        ob1 = lambda hole: f"{{{O}{{st, ar, e, kh, {hole}}} == {O}{{st, ar, e, kh, True{{}}}} : {O}}}"
        lc = list(self.fact(carried, "lc"))
        if cd != "v_cd":
            raise NoProof(f"{self.ab}: its loop sets its code to {cd[:60]}")
        if lc and lc[0][1]:
            return f"(%Equal.sym(Bool, M.u_nz(v_cd), True{{}}, {lc[0][2]}) : {ob1(f'Bool.or(_, {invl})')}\n      {{==}})"
        if not lc:
            if (d["ov"], d[self.SH], d[self.IX]) != ("v_ov", f"v_{self.SH}", f"v_{self.IX}"):
                raise NoProof(f"{self.ab}: its loop leaves an iteration with its overlay changed and no step")
            return (f"(%Equal.sym(Bool, Bool.or(M.u_nz(v_cd), {invl}), True{{}}, hI) : {ob1('_')}\n      {{==}})")
        # the step: the guard held, the write's condition c4, the increment's check passed
        elc = lc[0][2]
        g = list(self.fact(carried, "lh"))
        if not g or not g[0][1]:
            raise NoProof(f"{self.ab}: its loop steps without its guard")
        G, eg = g[0][0], g[0][2]
        wc = [(c, v, nm) for c, v, nm in self.fact(carried, "wc") if c == _strip(f"Bool.and({G}, {self.COND})")]
        k3 = [(c, v, nm) for c, v, nm in self.fact(carried, "k")
              if c == _strip(f"Bool.or(Bool.not({G}), M.w_add_ok({self.KW}, {W1}))") and v]
        if len(wc) != 1 or len(k3) != 1:
            raise NoProof(f"{self.ab}: its loop's write is not under its guard and the shadow's condition, or its "
                          "index's increment is not checked")
        c4, ewc, ek3 = wc[0][1], wc[0][2], k3[0][2]
        store = f"M.sstore(v_ov, {self.KEYW}, {self.VAL})"
        if d["ov"] != (store if c4 else "v_ov"):
            raise NoProof(f"{self.ab}: its loop's overlay at the step is not the shadow's store")
        if d[self.IX] != f"M.w_add(v_{self.IX}, M.w_u(1))":
            raise NoProof(f"{self.ab}: its loop's index does not step by one")
        c1 = as_call(d[self.SH])
        a1, b1 = c1[1][2].strip(), c1[1][3].strip()
        hi0 = f"(%{elc} : {{Bool.or(_, {self.n('inv')}({q}, st, v_ov, v_{self.SH}, v_{self.IX})) == True{{}} : Bool}}\n      hI)"
        ok = f"(%{eg} : {{Bool.or(Bool.not(_), M.w_add_ok({self.KW}, {W1})) == True{{}} : Bool}}\n      {ek3})"
        econd = f"(%{eg} : {{Bool.and(_, {self.COND}) == {'True' if c4 else 'False'}{{}} : Bool}}\n      {ewc})"
        if c4:
            s = f"{self.n('stw')}({q}, st, v_ov, v_{self.SH}, v_{self.IX}, {hi0}, {ok})"
        else:
            s = (f"{self.n('stn')}({q}, st, M.sload(v_ov, {self.K}), M.sload(v_{self.SH}, {self.K}), v_{self.IX}, "
                 f"{hi0}, {ok})")
        cv = "True{}" if c4 else "False{}"
        step1 = (f"(%Equal.sym(Bool, {self.COND}, {cv}, {econd}) : {{{self.n('inv')}({q}, st, {d['ov']}, "
                 f"M.ite(M.HSt, _, {a1}, {b1}), {d[self.IX]}) == True{{}} : Bool}}\n      {s})")
        big = f"(%Equal.sym(Bool, M.u_nz(v_cd), False{{}}, {elc}) : {{Bool.or(_, {invl}) == True{{}} : Bool}}\n      {step1})"
        return f"(%Equal.sym(Bool, Bool.or(M.u_nz(v_cd), {invl}), True{{}}, {big}) : {ob1('_')}\n      {{==}})"


# ------------------------------------------------------------------------------------------------ the law
class Plan:
    """The facts a law needs: per (action, key) a chain and its step lemma, generated once."""

    def __init__(self, md: Model, defs: list):
        self.md, self.defs = md, defs
        self.loops = Loops(md, defs)
        self.steps: dict = {}
        self.n = 0

    def probe(self, ab: str, key: str, params: list) -> tuple:
        """("states", {end states}) of the key through the action, or ("stuck", Stuck): a dry run, nothing kept."""
        fact = Fact(key, params, ("eq", f"M.sload(st, {key})"))
        scratch: list = []
        ch = Chain(self.md, ab, fact, "probe", scratch, Loops(self.md, scratch))
        PROBE.append(set())
        try:
            ch.top()
            return "states", PROBE[-1]
        except Stuck as e:
            return "stuck", e
        finally:
            PROBE.pop()

    def fact(self, ab: str, key: str, params: list, bound_ok: bool) -> Fact:
        """The fact of the key through the action: kept or transported (one end state), or bounded by the budget a
        split store or an accumulating loop adds (bound_ok)."""
        kind, r = self.probe(ab, key, params)
        if kind == "states":
            if len(r) != 1:
                raise NoProof(f"{ab}: the word at {key[:120]} differs by path ({len(r)} end states)")
            return Fact(key, params, next(iter(r)))
        if not bound_ok:
            raise NoProof(f"{ab}: it stores at {r.kw[:120]}, which meets {key[:120]} when {r.at[0][:80]} == "
                          f"{r.at[1][:80]}, and the conjunct keeps the word")
        v = as_call(norm_value(r.v))
        rd = as_call(v[1][0].strip()) if v and v[0] == "M.w_add" and len(v[1]) == 2 else None
        if not rd or rd[0] != "M.sload" or _strip(rd[1][1]) != _strip(r.kw):
            raise NoProof(f"{ab}: its store at {r.kw[:120]} is not a sum w_add(sload(.., key), D): no bound")
        D = _strip(v[1][1])
        if re.search(r"(?<![\w.])v_\w+", D):
            raise NoProof(f"{ab}: the bound its store adds reads its own context ({D[:120]})")
        return Fact(key, params, ("le", f"M.sload(st, {_strip(key)})", D))

    def step(self, ab: str, fact: Fact) -> str:
        """The step lemma of the fact (generated once): {name}(g, ar, e, kh, params.., hz)."""
        key = (ab, fact.K, fact.goal)
        if key not in self.steps:
            self.n += 1
            p = f"r{self.n}"
            ch = Chain(self.md, ab, fact, p, self.defs, self.loops)
            text = step_lemma(ch, f"{p}_g")
            self.defs.append(text)
            self.steps[key] = f"{p}_g"
        return self.steps[key]


def _claims(law: dict) -> list:
    c = law["statement"]["claim"]
    return list(c["all"]) if isinstance(c, dict) and "all" in c else [c]


def _is_wnat_read(t) -> bool:
    return isinstance(t, dict) and set(t) == {"wnat"} and isinstance(t["wnat"], dict) and "sread" in t["wnat"]


def prove(law: dict, facts: dict, model_text: str, tables: list, model_import: str, laws_import: str):
    """(PROOF.bend text, a note) of the law, or NoProof."""
    if law.get("ir_version") != "holon-ir/0.3" or law.get("subform") != C3.SUBFORM:
        raise NoProof("not a typed contract law (holon-ir/0.3, intended_weak)")
    if list(tables) != ["kh"]:
        raise NoProof(f"the law's hash tables are {tables}, not keccak256 alone")
    md = Model(model_text)
    st = law["statement"]
    tys = {b["name"]: b["type"] for b in st.get("binders") or []}
    reach = [n for n, ty in tys.items() if ty == "Reach"]
    acts = [n for n, ty in tys.items() if ty == "Act"]
    if len(reach) != 1 or len(acts) != 2 or any(ty not in ("Reach", "Act", "Word") for ty in tys.values()):
        raise NoProof("the law's binders are not one Reach, two Act and Words")
    s = reach[0]
    # the premises: is[A](x), ok(x, s), is[B](y), ok(y, step(x, s))
    isa, oks = {}, {}
    for p in st.get("assume") or []:
        a, b = p.get("eq") or [None, None]
        if b != {"bool": True} or not isinstance(a, dict):
            raise NoProof("a premise that is not a boolean term made true")
        if set(a) == {"is", "act"}:
            isa[a["act"]["var"]] = a["is"]
        elif set(a) == {"ok", "from"}:
            oks[a["ok"]["var"]] = a["from"]
        else:
            raise NoProof(f"a premise {sorted(a)} (residue_bound takes is[A] and ok premises)")
    order = [x for x in acts if oks.get(x) == {"var": s}]
    if len(order) != 1:
        raise NoProof("no first action ok at s")
    x = order[0]
    y = [a for a in acts if a != x][0]
    if oks.get(y) != {"from": {"var": s}, "step": {"var": x}} or set(isa) != {x, y}:
        raise NoProof("the second action is not ok after the first")
    A, B = bname(isa[x]), bname(isa[y])
    for ab in (A, B):
        if f"def xr_{ab}(" not in model_text:
            raise NoProof(f"the typed model has no action {ab}")
    S1 = {"step": {"var": x}, "from": {"var": s}}
    S2 = {"step": {"var": y}, "from": S1}
    words = [n for n, ty in tys.items() if ty == "Word"]
    # the law's terms as the law file states them (helpers ct_.., args s, x, y, words, kh)
    tm = C3.Terms(law, facts, tables)
    prem = [tm.prop(p) for p in st.get("assume") or []]
    cl = [tm.prop(p) for p in _claims(law)]
    targs = tm.args()
    Sx, Xx, Yx = "M.GSt{st0, g1}", f"M.A_{A}{{ar1, en1}}", f"M.A_{B}{{ar2, en2}}"
    sub_args = ", ".join({bname(s): Sx, bname(x): Xx, bname(y): Yx}.get(a.strip(), a.strip()) for a in targs.split(","))
    lawt = lambda txt: re.sub(r"(?<![\w.])(ct_[0-9a-f]+)\(" + re.escape(targs) + r"\)", lambda m: f"Laws.{m.group(1)}({sub_args})", txt)
    # a key: the read's SK with each step word a param of the chains (its value at the law)
    env_of = {bname(x): "en1", bname(y): "en2"}

    def word(t) -> str:
        if isinstance(t, dict) and "var" in t and tys.get(t["var"]) == "Word":
            return bname(t["var"])
        if isinstance(t, dict) and set(t) == {"env", "of"}:
            if t["env"] not in C3.ENV_FIELDS:
                raise NoProof(f"env {t['env']!r}")
            return f"M.ge_e_{t['env']}({env_of[bname(t['of']['var'])]})"
        raise NoProof(f"a key word that is not a Word binder or an env word: {json.dumps(t)[:120]}")

    def read(t, frm) -> tuple:
        """(key template over params q0.., [(param, value)]) of a whole-word sread at the state frm."""
        if t.get("from") != frm:
            raise NoProof(f"a read at another state than expected: {json.dumps(t)[:120]}")
        tm2 = C3.Terms(law, facts, tables)
        tm2.word = word
        tm2.state = lambda _t: "S"
        w = tm2.sread(t)
        c = as_call(w)
        if not c or c[0] != "M.sload" or _strip(c[1][0]) != "M.gh_get_st(S)":
            raise NoProof(f"a read of a packed field ({w[:120]}): whole words only")
        from ..disch.proofs import sk_parts
        k = _strip(c[1][1])
        parts = sk_parts(k)
        if parts is None:
            raise NoProof(f"a key that is not structural: {k[:120]}")
        b, o, steps = parts
        params, vals = [], []
        for i, (kw, o2) in enumerate(steps):
            params.append(f"q{i}")
            vals.append(kw)
        tmpl = f"M.SK{{{b}, {o}, " + ("[" + ", ".join(f"M.SP_m{{q{i}, {o2}}}" for i, (_k, o2) in enumerate(steps)) + "]"
                                       if steps else "Nil{}") + "}"
        return _strip(tmpl), [(p_, "M.W") for p_ in params], vals

    defs: list = []
    plan = Plan(md, defs)
    comp = {"st": "M.gh_get_st(M.GSt{st0, g1})", "ar": "ar1", "e": "en1", "kh": "kh"}
    G1 = f"M.gh_step({Xx}, {Sx}, kh)"
    hzA, hzB = "hzA", "hzB"
    stepA = lambda name, pv: f"{name}({Sx}, ar1, en1, kh{''.join(', ' + v for v in pv)}, {hzA})"
    stepB = lambda name, pv: f"{name}({G1}, ar2, en2, kh{''.join(', ' + v for v in pv)}, {hzB})"
    st0t, st1t = comp["st"], f"M.gh_get_st({G1})"
    st2t = f"M.gh_get_st(M.gh_step({Yx}, {G1}, kh))"
    comps, notes = [], []

    def through(t: str) -> tuple:
        """t, a term of B's pre-state (S1), read at the state A leaves: (its value as a term of A's context, a proof of
        {t at st1 == the value} at the composition, None when t reads nothing), each read through A's fact at its key."""
        t = _strip(t)
        if not re.search(r"(?<![\w.])S1(?![\w{])", t):
            return t, None
        c = as_call(t)
        if not c or c[0] != "M.sload" or _strip(c[1][0]) != "S1":
            raise NoProof(f"a bound that is not a read of the state ({t[:120]})")
        from ..disch.proofs import sk_parts
        parts = sk_parts(_strip(c[1][1]))
        if parts is None:
            raise NoProof(f"a bound read at a key that is not structural ({t[:120]})")
        b, o, steps = parts
        vals_, proofs = [], []
        for kw, _o2 in steps:
            v, pv = through(kw)
            vals_.append(v)
            proofs.append(pv)
        live = [i for i, pv in enumerate(proofs) if pv is not None]
        if len(live) > 1:
            raise NoProof("a bound read whose key reads the state twice")
        sk = lambda ws: f"M.SK{{{b}, {o}, " + ("[" + ", ".join(f"M.SP_m{{{w}, {o2}}}" for w, (_k, o2) in zip(ws, steps))
                                               + "]" if steps else "Nil{}") + "}"
        key2 = sk(vals_)
        f = plan.fact(A, key2, [], False)
        if f.goal[0] != "eq":
            raise NoProof("a bound read through a bounded fact")
        pf = stepA(plan.step(A, f), [])
        if not live:
            return f.goal[1], pf
        i = live[0]
        cw = lambda w: _comp_s1(w, st1t, comp)
        hole = sk([("z" if j == i else cw(w)) for j, w in enumerate(vals_)])
        pk = f"Equal.cong(M.W, M.W, z => M.sload({st1t}, {hole}), {cw(steps[i][0])}, {cw(vals_[i])}, {proofs[i]})"
        lhs, mid = f"M.sload({st1t}, {cw(sk([w for w, _o in steps]))})", f"M.sload({st1t}, {cw(key2)})"
        return f.goal[1], f"Equal.trans(M.W, {lhs}, {mid}, {cw(f.goal[1])}, {pk}, {pf})"

    for j, (prop, (a_t, b_t, ty)) in enumerate(zip(_claims(law), cl)):
        a, b = prop["eq"]
        if ty == "Nat" and _is_wnat_read(a) and _is_wnat_read(b):
            post, pre, T = a["wnat"], b["wnat"], None
        elif isinstance(a, dict) and set(a) == {"cmp", "args"} and a["cmp"] == "<=" and b == {"bool": True}:
            l_, r_ = a["args"]
            pl = r_.get("plus") if isinstance(r_, dict) else None
            if not (_is_wnat_read(l_) and pl and len(pl) == 2 and _is_wnat_read(pl[0]) and isinstance(pl[1], dict)
                    and set(pl[1]) == {"wnat"}):
                raise NoProof(f"conjunct {j}: not N(read after) <= N(read before) + N(T)")
            post, pre, T = l_["wnat"], pl[0]["wnat"], pl[1]["wnat"]
        else:
            raise NoProof(f"conjunct {j}: not a kept or bounded word")
        if {k_: v_ for k_, v_ in post.items() if k_ != "from"} != {k_: v_ for k_, v_ in pre.items() if k_ != "from"}:
            raise NoProof(f"conjunct {j}: the reads before and after are not at the same key")
        K, params, pvals = read(post, S2)
        read(pre, {"var": s})
        pv_c = pvals    # the params' values at the composition (words of the law's binders and env)
        fB = plan.fact(B, K, params, T is not None)
        fA = plan.fact(A, K, params, T is not None)
        Kc = _sub(K, dict(zip([p_ for p_, _t in params], pv_c)))
        r0 = f"M.sload({st0t}, {Kc})"
        r1 = f"M.sload({st1t}, {Kc})"
        r2 = f"M.sload({st2t}, {Kc})"
        if fB.goal != ("eq", f"M.sload(st, {K})") and fB.goal[0] == "eq":
            raise NoProof(f"conjunct {j}: {B} writes the key {K[:120]} ({fB.goal[1][:120]})")
        if fA.goal != ("eq", f"M.sload(st, {K})") and fA.goal[0] == "eq":
            raise NoProof(f"conjunct {j}: {A} writes the key {K[:120]} ({fA.goal[1][:120]})")
        gB, gA = stepB(plan.step(B, fB), pv_c), stepA(plan.step(A, fA), pv_c)
        name = f"cj{j}"
        if T is None:
            if fB.goal[0] != "eq" or fA.goal[0] != "eq":
                raise NoProof(f"conjunct {j}: the word is kept but a step adds to it")
            body = (f"Equal.cong(M.W, Nat, z => {N}(z), {r2}, {r0}, Equal.trans(M.W, {r2}, {r1}, {r0}, {gB}, {gA}))")
            notes.append(f"conjunct {j}: kept by {B} and {A}")
        else:
            if T.get("env") is not None:
                if T.get("of") != {"var": x}:
                    raise NoProof(f"conjunct {j}: the bound is an env word of another action than the first")
                Tt = f"M.ge_e_{T['env']}(e)"
            else:
                Tk, _tp, _tv = read(T, {"var": s})
                if _tp:
                    raise NoProof(f"conjunct {j}: a bound read at a mapping key")
                Tt = f"M.sload(st, {Tk})"
            Tc = _sub(Tt, comp)
            if fB.goal[0] == "eq" and fA.goal[0] == "eq":
                body = (f"(%Equal.sym(M.W, {r2}, {r0}, Equal.trans(M.W, {r2}, {r1}, {r0}, {gB}, {gA})) : "
                        f"{{Nat.is_le({N}(_), Nat.add({N}({r0}), {N}({Tc}))) == True{{}} : Bool}}\n  "
                        f"n_le_add({N}({r0}), {N}({Tc})))")
                notes.append(f"conjunct {j}: kept by {B} and {A}")
            elif fB.goal[0] == "eq" and fA.goal[0] == "le":
                if _strip(fA.goal[2]) != _strip(Tt):
                    raise NoProof(f"conjunct {j}: {A} adds {fA.goal[2][:120]}, the claim allows {Tt[:120]}")
                body = (f"(%Equal.sym(M.W, {r2}, {r1}, {gB}) : {{Nat.is_le({N}(_), Nat.add({N}({r0}), {N}({Tc}))) == "
                        f"True{{}} : Bool}}\n  {gA})")
                notes.append(f"conjunct {j}: kept by {B}, bounded by {A}'s accumulating loop")
            elif fB.goal[0] == "le" and fA.goal[0] == "eq":
                D = fB.goal[2]
                val, pd = through(_sub(D, {"st": "S1"}))
                if _strip(val) != _strip(Tt):
                    raise NoProof(f"conjunct {j}: {B} adds {D[:120]}, which is {val[:120]} after {A}, not the claim's "
                                  f"{Tt[:120]}")
                Dc = _sub(D, {"st": st1t})
                body = f"le_rw({r2}, {r1}, {r0}, {Dc}, {Tc}, {gB}, {gA}, {pd})"
                notes.append(f"conjunct {j}: bounded by {B}'s split store, its bound transported through {A}")
            else:
                raise NoProof(f"conjunct {j}: both steps add to the word")
        comps.append((name, lawt(f"{{{a_t} == {b_t} : {ty}}}"), body))
    # the assembly
    hdr = (f"+kh: List<&2, M.HKB>, +st0: M.HSt, +g1: {_gst_rest(md)}, +ar1: M.AR_{A}, +en1: M.HEnv, +ar2: M.AR_{B}, "
           f"+en2: M.HEnv" + "".join(f", +{bname(w)}: M.W" for w in words) +
           f", +hzA: {{M.u_nz(M.gx_{A}_cd(M.xr_{A}({st0t}, ar1, en1, kh))) == False{{}} : Bool}}"
           f", +hzB: {{M.u_nz(M.gx_{B}_cd(M.xr_{B}({st1t}, ar2, en2, kh))) == False{{}} : Bool}}")
    cargs = "kh, st0, g1, ar1, en1, ar2, en2" + "".join(f", {bname(w)}" for w in words) + ", hzA, hzB"
    for name, ty, body in comps:
        defs.append(f"def {name}({hdr}) -> {ty}:\n  {body}\n")
    out = [HEADER, f"# law_id: {law['law_id']}   proof class: {CLASS}", "import Base", f"import {model_import} as M",
           f"import {laws_import} as Laws", "", DL.library(True), ORDER.text("M.", True),
           RL.library("M.", "Laws.c3_shn", "Laws.c3_wnat"), helpers([]),
           action_helpers(md, A, md.mirror(A).field_names)]
    if B != A:
        out.append(action_helpers(md, B, md.mirror(B).field_names))
    out += defs
    out.append(_law_proof(law, tm, md, A, B, s, x, y, words, prem, cl, lawt, comps, cargs, Sx, Xx, Yx))
    return "\n".join(out) + "\n", "; ".join(notes)


def _comp_s1(t: str, st1t: str, comp: dict) -> str:
    """A term of B's pre-state placeholder S1 and A's context, at the composition."""
    return _sub(_sub(t, comp), {"S1": st1t})


def _gst_rest(md: Model) -> str:
    m = re.search(r"(?m)^type GSt is Data:\n  GSt\{(.*)\}$", md.text)
    fs = [x.split(":", 1) for x in split_top(m.group(1))] if m else []
    if len(fs) != 2 or fs[0][0].strip() != "st":
        raise NoProof("the augmented state GSt is not {st, one table}")
    return md.mtype(fs[1][1].strip())


def _law_proof(law, tm, md, A, B, s, x, y, words, prem, cl, lawt, comps, cargs, Sx, Xx, Yx) -> str:
    """Laws.<law>(..): open s, x, y; other actions contradict is[A](x) or is[B](y); the conjuncts' lemmas paired."""
    params = ["kh"]
    for n, ty in tm.binders:
        params += [bname(n), f"r_{bname(n)}"] if ty == "Reach" else [bname(n)]
    params += [f"h{i}" for i in range(len(prem))]
    hisx = hisy = hokx = hoky = None
    for i, p in enumerate(law["statement"]["assume"]):
        a = p["eq"][0]
        if set(a) == {"is", "act"}:
            if a["act"]["var"] == x:
                hisx = f"h{i}"
            else:
                hisy = f"h{i}"
        elif a["from"] == {"var": s}:
            hokx = f"h{i}"
        else:
            hoky = f"h{i}"
    acts = re.findall(r"(?m)^  (A_\w+)\{ar: AR_\w+, en: HEnv\}$", md.text)

    def tup(items):
        return items[0] if len(items) == 1 else f"({items[0]}, {tup(items[1:])})"

    def other(sv, xv, yv, e):
        sub = lambda t: re.sub(r"Laws\.(ct_[0-9a-f]+)\(M\.GSt\{st0, g1\}, M\.A_\w+\{ar1, en1\}, M\.A_\w+\{ar2, en2\}",
                               lambda m: f"Laws.{m.group(1)}({sv}, {xv}, {yv}", t)
        return tup([f"efq({sub(ty)}, ez)" for _n, ty, _b in comps])

    sp = "  "
    lines = [f"def Laws.{C3.law_name(law['law_id'])}({', '.join(params)}):",
             f"{sp}match {bname(s)}:", f"{sp * 2}case M.GSt{{+st0, +g1}}:", f"{sp * 3}match {bname(x)}:"]
    for a in acts:
        if a == f"A_{A}":
            lines += [f"{sp * 4}case M.{a}{{+ar1, +en1}}:", f"{sp * 5}match {bname(y)}:"]
            for b in acts:
                if b == f"A_{B}":
                    lines += [f"{sp * 6}case M.{b}{{+ar2, +en2}}:",
                              f"{sp * 7}+hzA = okz_{A}(M.gh_get_st({Sx}), ar1, en1, kh, {hokx})",
                              f"{sp * 7}+hzB = okz_{B}(M.gh_get_st(M.gh_step({Xx}, {Sx}, kh)), ar2, en2, kh, {hoky})",
                              f"{sp * 7}{tup([f'{n}({cargs})' for n, _t, _b in comps])}"]
                else:
                    lines += [f"{sp * 6}case M.{b}{{+b1, +b2}}:", f"{sp * 7}+ez = false_ne_true({hisy})",
                              f"{sp * 7}{other(Sx, Xx, f'M.{b}{{b1, b2}}', 'ez')}"]
        else:
            lines += [f"{sp * 4}case M.{a}{{+a1, +a2}}:", f"{sp * 5}+ez = false_ne_true({hisx})",
                      f"{sp * 5}{other(Sx, f'M.{a}{{a1, a2}}', bname(y), 'ez')}"]
    return "\n".join(lines) + "\n"
