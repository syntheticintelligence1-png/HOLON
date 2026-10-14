"""Proof search for the equivalence classes F32 adds (docs/HUMAN_ANSWERS.md Q31; holon.gen.equivalence).

One engine, three generic proof classes over a goal {L == R : T} of the pair module (L the old side, R the new one),
every step written as Bend text that the kernel checks (bend2 and BendTT); nothing here is trusted:

  rewrite        both sides are put in normal form (holon.gen.eqterms: a call unfolds when its own match tree reduces)
                 and rewritten with proven equalities: the Base library (holon.gen.eqlib.RULES, simplifying, used
                 anywhere), the lemma of every changed callee already proven equal (o__g -> g), the induction
                 hypothesis, and the lemmas the two classes below discover. Each rewrite is one `%e : motive` line
                 whose motive is the current goal with the rewritten instance as `_`.
  case split     (class b) a Bool condition a stuck match waits on is split both ways in a helper definition
  with           (c: Bool, e: {cond == c}); in the True case a reflection lemma turns the condition into an equality
  reflection     (U32.is_eq(a, b) -> a == b from the library; for a model definition deciding the equality of a
                 record field by field, like a word equality, the reflection lemma is derived and proved here) and
                 the goal is rewritten with it.
  lemma          (class c) where the two sides still differ, the differing subterms are generalized into a lemma for
  discovery      all values of its parameters (common subterms and variables become parameters), tested on generated
                 values, then proved by the same engine, by induction when one of its sides recurses: an accumulator
                 argument fixed at a constructor (a `done` flag at True{}) gives one such lemma per constructor value,
                 discovered from the definition's shape, never named. A proved lemma closes every instance of the
                 same difference.

Variables are opened (matched) when a definition of the model waits on them: a record, a list, a Bool; a U32 or a
Word only when a model definition reads its bits (bit by bit definitions), never for Base arithmetic.

The engine names no model, definition or target: everything comes from the two model texts and Base.
"""
from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass, field

from . import eqterms as E
from . import eqlib as L

ALIAS = "P"
DEBUG = False


class Fail(Exception):
    pass


# ------------------------------------------------------------------ types
class Types:
    def __init__(self, defs: dict, types: dict):
        self.defs = defs
        self.types = types
        self.ctor_of = {}
        for t in types.values():
            for c, fs in t.ctors:
                self.ctor_of[c] = t

    @staticmethod
    def head(ty: str):
        ty = ty.strip().lstrip("+")
        m = re.match(r"([A-Za-z_][\w.]*)\s*(?:<(.*)>|\((.*)\))?$", ty)
        if not m:
            raise Fail(f"type {ty!r}")
        from .equivalence import split_top
        args = split_top(m.group(2)) if m.group(2) is not None else ([m.group(3)] if m.group(3) is not None else [])
        return m.group(1), args

    def ctors(self, ty: str):
        """[(ctor, [(field, field type)])] of a type text."""
        name, args = self.head(ty)
        if name == "Bool":
            return [("True", []), ("False", [])]
        if name == "Cmp":
            return [("LT", []), ("EQ", []), ("GT", [])]
        if name == "List":
            el = args[-1]
            return [("Nil", []), ("Con", [("head", el), ("tail", ty)])]
        if name == "U32":
            return [("U32", [("data", "Word(32n)")])]
        if name == "Word":
            m = re.fullmatch(r"(\d+)n", args[0].strip()) if args else None
            if not m:
                raise Fail(f"Word of an unknown width {ty!r}")
            k = int(m.group(1))
            return [("WNil", [])] if k == 0 else [("WCon", [("head", "Bool"), ("tail", f"Word({k - 1}n)")])]
        t = self.types.get(name)
        if t is None or t.params:
            raise Fail(f"no constructors for {ty!r}")
        return [(c, list(fs)) for c, fs in t.ctors]

    def finite(self, ty: str, seen=()) -> bool:
        name, _ = self.head(ty)
        if name in ("Bool", "Cmp"):
            return True
        t = self.types.get(name)
        if t is None or t.params or name in seen or t.kind != "Data":
            return False
        return all(self.finite(ft, seen + (name,)) for _, fs in t.ctors for _, ft in fs)

    def of(self, t, ctx: dict):
        """The type text of a term (None when unknown)."""
        k = t[0]
        if k == "var":
            return ctx.get(t[1])
        if k == "u32":
            return "U32"
        if k in ("nat", "nsucc"):
            return "Nat"
        if k == "ctor":
            c = t[1]
            if c in ("True", "False"):
                return "Bool"
            if c in ("LT", "EQ", "GT"):
                return "Cmp"
            if c == "U32":
                return "U32"
            if c == "Con":
                h = self.of(t[2][0], ctx)
                if h is None:
                    return self.of(t[2][1], ctx)
                return f"List<&2, {h}>"
            if c == "Nil":
                return None
            if c == "WCon":
                n = 1
                w = t[2][1]
                while w[0] == "ctor" and w[1] == "WCon":
                    n += 1
                    w = w[2][1]
                if w[0] == "ctor" and w[1] == "WNil":
                    return f"Word({n}n)"
                tw = self.of(w, ctx)
                m = re.fullmatch(r"Word\((\d+)n\)", tw or "")
                return f"Word({int(m.group(1)) + n}n)" if m else None
            td = self.ctor_of.get(c)
            return td.name if td is not None and not td.params else None
        if k == "app":
            d = self.defs.get(t[1])
            if d is None:
                return None
            sub = {}
            for (q, n, pty), a in zip(d.params, t[2]):
                if a[0] == "ty":
                    sub[n] = a[1]
                elif a[0] == "nat" and pty.strip() == "Nat":
                    sub[n] = E.show(a)
            ret = d.ret
            for n, v in sub.items():
                ret = re.sub(r"(?<![\w.])" + re.escape(n) + r"(?![\w])", v, ret)
            return ret
        return None


# ------------------------------------------------------------------ values for testing a conjecture
POOL = [0, 1, 2, 3, 255, 256, 57005, 4294967295, 2147483648, 65535]


class Gen:
    def __init__(self, types: Types, seed: str):
        self.T = types
        self.rng = random.Random(int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16))
        self.seen: dict = {}

    def value(self, ty: str, depth: int = 0):
        key = ty.replace(" ", "")
        if self.seen.get(key) and self.rng.random() < 0.4:
            return self.rng.choice(self.seen[key])
        v = self._fresh(ty, depth)
        self.seen.setdefault(key, []).append(v)
        return v

    def _fresh(self, ty, depth):
        name, args = self.T.head(ty)
        if name == "U32":
            x = self.rng.random()
            return ("u32", self.rng.choice([0, 1]) if x < 0.4 else self.rng.choice(POOL) if x < 0.8
                    else self.rng.getrandbits(32))
        if name == "Nat":
            return ("nat", self.rng.choice([0, 1, 2, 3, 5, 8, 31, 32]))
        if name == "Word":
            k = int(re.fullmatch(r"(\d+)n", args[0].strip()).group(1))
            return E.word_of(self.rng.getrandbits(k) if k else 0, k)
        if name == "List":
            n = 0 if depth > 3 else self.rng.choice([0, 1, 2, 2, 3, 4])
            out = E.NIL
            for x in [self.value(args[-1], depth + 1) for _ in range(n)]:
                out = ("ctor", "Con", (x, out))
            return out
        cs = self.T.ctors(ty)
        if depth > 5:
            flat = [c for c in cs if all(self.T.head(ft)[0] != name for _, ft in c[1])]
            cs = flat or cs
        c, fs = self.rng.choice(cs)
        return E.canon(("ctor", c, tuple(self.value(ft, depth + 1) for _, ft in fs)))


# ------------------------------------------------------------------ rules
@dataclass
class Rule:
    name: str                 # the lemma (a def name) proving {lhs == rhs}
    params: list              # [(name, type)] in the lemma's argument order (pattern variables)
    lhs: tuple                # normal-form pattern
    rhs: tuple
    ty: str                   # the equated type
    extra: str = ""           # arguments after the pattern variables (none for library rules)


def match(p, t, env, pvars) -> bool:
    if p[0] == "var" and p[1] in pvars:
        if p[1] in env:
            return env[p[1]] == t
        env[p[1]] = t
        return True
    if p[0] != t[0]:
        return False
    if p[0] in ("app", "ctor"):
        return p[1] == t[1] and len(p[2]) == len(t[2]) and all(match(a, b, env, pvars) for a, b in zip(p[2], t[2]))
    if p[0] == "tup":
        return len(p[1]) == len(t[1]) and all(match(a, b, env, pvars) for a, b in zip(p[1], t[1]))
    if p[0] == "nsucc":
        return p[1] == t[1] and match(p[2], t[2], env, pvars)
    return p == t


def _symbols(t):
    return [x[1] if x[0] in ("app", "ctor") else (x[0] if x[0] == "var" else E.show(x)) for x in E.subterms(t)]


# ------------------------------------------------------------------ the prover
@dataclass
class VarInfo:
    ty: str
    parent: str | None = None
    rec: bool = False         # a recursive field of its parent (a list's tail)
    depth: int = 0
    idx: int = 0              # binder order inside the def that binds it


@dataclass
class Subject:
    """What the induction hypothesis is about: the lemma being proved (its statement, by its parameters)."""
    name: str
    params: list              # [name]
    lhs: tuple
    rhs: tuple
    ty: str


@dataclass
class Def:
    name: str
    params: list              # [(q, name, type)]
    goal: str
    body: list                # lines (indented 2)
    ihs: list = field(default_factory=list)   # [(param name, eq text, instance key)]


class Prover:
    def __init__(self, defs: dict, types: dict, prefix: str, opaque: set, callee_lemmas: dict, budget: int = 200,
                 conj_depth: int = 3, tag: str = "q", libraries: tuple = ()):
        self.defs = defs
        self.T = Types(defs, types)
        self.ev = E.Evaluator(defs, types)
        self.ev_opaque = E.Evaluator({k: v for k, v in defs.items() if k not in opaque}, types)
        self.ev_full = E.Evaluator(defs, types)
        self.prefix = prefix               # "P.o__" : the old side's renamed names
        self.callee = callee_lemmas        # {qualified new name P.g: lemma name} proving {P.o__g(..) == P.g(..)}
        self.rules = []
        lib_rules = list(L.RULES) + [r for lib in libraries for r in lib.RULES]
        lib_reflect = list(L.REFLECT) + [r for lib in libraries for r in lib.REFLECT]
        for name, ps, lhs, rhs in lib_rules:
            pv = {n for n, _ in ps}
            lt, rt = E.parse(lhs), E.parse(rhs)
            ty = self.T.of(lt, dict(ps)) or "Bool"
            self.rules.append(Rule(name, ps, self.ev.nf(lt), self.ev.nf(rt), ty))
        self.reflect = {}
        for name, ps, cond, (x, y) in lib_reflect:
            self.reflect[name] = (ps, self.ev.nf(E.parse(cond)), E.parse(x), E.parse(y), self.T.of(E.parse(x), dict(ps)))
        self.conj_rules: list = []
        self.out: list = []                # emitted defs (text), in order
        self.n = 0
        self.tag = tag
        self.budget = budget
        self.conj_depth = conj_depth
        self.steps = 0
        self.log: list = []
        self.stats = {"split": 0, "reflect": 0, "lemma": 0, "lemma_ih": 0, "ih": 0, "bits": 0, "rules": set()}
        self.lib_names = {n for n, *_ in L.RULES} | {n for n, *_ in L.REFLECT}

    def label(self) -> str:
        """The proof's class, by the mechanisms it used (holon.gen.equivalence reports it per lemma)."""
        st = self.stats
        parts = []
        if st["split"]:
            parts.append("case split" + (" with reflection" if st["reflect"] else ""))
        if st["lemma"]:
            parts.append("lemma discovery" + (" with induction (accumulator specialization)" if st["lemma_ih"] else ""))
        if st["ih"]:
            parts.append("induction")
        if st["bits"]:
            parts.append("bit by bit")
        base = sorted(r for r in st["rules"] if r in self.lib_names)
        other = sorted(r for r in st["rules"] if r not in self.lib_names)
        if base:
            parts.append("Base library")
        if other:
            parts.append("prelude library")
        return "eqprove: " + (", ".join(parts) if parts else "rewrite")

    def snapshot(self):
        st = {k: (set(v) if isinstance(v, set) else v) for k, v in self.stats.items()}
        return (len(self.out), len(self.conj_rules), dict(self.__dict__.get("_refl", {})), st)

    def restore(self, snap):
        del self.out[snap[0]:]
        del self.conj_rules[snap[1]:]
        self.__dict__["_refl"] = snap[2]
        self.stats = snap[3]

    # -- names
    def fresh(self, base="v"):
        self.n += 1
        return f"{base}_{self.n}"

    def nf(self, t):
        return E.canon(self.ev_opaque.nf(t))

    # -- printing
    def eq(self, l, r, ty):
        return f"{{{E.show(l)} == {E.show(r)} : {ty}}}"

    def motive(self, g, inst):
        return f"{{{E.show_hole(g[0], inst)} == {E.show_hole(g[1], inst)} : {g[2]}}}"

    # ------------------------------------------------------------------ public: prove a lemma
    def prove_lemma(self, name: str, params: list, lhs, rhs, ty: str, subject: Subject | None = None,
                    depth: int = 0) -> str:
        """Bend text of `def name(params) -> {lhs == rhs : ty}` (plus its helpers, before it), or raises Fail."""
        ctx = {}
        for i, (n, t) in enumerate(params):
            ctx[n] = VarInfo(t, idx=i)
        subj = subject or Subject(name, [n for n, _ in params], lhs, rhs, ty)
        st = State(self, ctx, subj, main=True, depth=depth, owner=name)
        body = st.solve((lhs, rhs, ty), 2)
        if st.ih_req:
            raise Fail("the main definition requested its own hypothesis as a parameter")
        ps = ", ".join(f"+{n}: {t}" for n, t in params)
        return f"def {name}({ps}) -> {{{E.show(lhs)} == {E.show(rhs)} : {ty}}}:\n" + "\n".join(body) + "\n"


class State:
    """Proof search inside one definition (the lemma or a helper)."""

    def __init__(self, pv: Prover, ctx: dict, subj: Subject, main: bool, depth: int, owner: str):
        self.pv = pv
        self.ctx = ctx                     # name -> VarInfo
        self.subj = subj
        self.main = main
        self.depth = depth
        self.owner = owner
        self.ih_req: list = []             # [(param name, eq text, proof at the main def)]
        self.local = [0, 4000 if depth == 0 else 300]   # solve steps of this lemma (shared with its helpers)
        self.top_idx = max((v.idx for v in ctx.values()), default=-1)

    # -- context
    def tyctx(self):
        return {n: v.ty for n, v in self.ctx.items()}

    def descendant(self, v: str, of: str) -> bool:
        x = self.ctx.get(v)
        while x is not None and x.parent is not None:
            if x.parent == of:
                return True
            x = self.ctx.get(x.parent)
        return False

    # ------------------------------------------------------------------ the loop
    def solve(self, g, ind, allow=None, stmts=False):
        pv = self.pv
        pv.steps += 1
        self.local[0] += 1
        if pv.steps > pv.budget * 100 or self.local[0] > self.local[1]:
            raise Fail("search budget exhausted")
        lines = []
        conj_rounds = 0
        while True:
            g = (pv.nf(g[0]), pv.nf(g[1]), g[2])
            if DEBUG:
                print("SOLVE", self.local[0], E.show(g[0])[:200], "  ==  ", E.show(g[1])[:200])
            if g[0] == g[1]:
                return lines + [" " * ind + "{==}"]
            # open a variable a model definition (or a Word computation) waits on, on both sides first
            v = self.blocking_var(g, recursive=False, common=True)
            if v is not None:
                return lines + self.open_var(g, v, ind, allow, stmts)
            g, ls = self.rewrite(g, ind)
            if ls:
                lines += ls
                stmts = True
                continue
            v = self.blocking_var(g, recursive=False)
            if v is not None:
                return lines + self.open_var(g, v, ind, allow, stmts)
            # lemma discovery at the differences
            if self.depth < pv.conj_depth and conj_rounds < 8:
                conj_rounds += 1
                if self.conjecture(g):
                    continue
                conj_rounds = 8
            # case split on a condition both sides wait on, then on any
            cond = self.condition(g, shared=True)
            if cond is not None:
                return lines + self.helper(g, ind, kind="split", cond=cond)
            v = self.deep_var(g)
            if v is not None:
                return lines + self.open_var(g, v, ind, allow, stmts)
            cond = self.condition(g)
            if cond is not None:
                return lines + self.helper(g, ind, kind="split", cond=cond)
            v = self.blocking_var(g, recursive=True)
            if v is not None:
                return lines + self.open_var(g, v, ind, allow, stmts)
            break
        raise Fail(f"no class applies: {E.show(g[0])[:300]}  ==  {E.show(g[1])[:300]}")

    # ------------------------------------------------------------------ opening variables
    def spine(self, t, top=False):
        """(kind, call, value) along the spine of t: ("var", call, v) for a call stuck on a variable v, ("cond", call,
        c) for an atomic Bool condition c a call waits on (a Bool term stuck on something that is not a Bool). At the
        top of a goal side a call stuck on a variable opens the variable; inside, a Bool call stuck so is a condition."""
        tc = self.tyctx()
        ev = self.pv.ev_opaque
        if t[0] == "app":
            sc = ev.stuck_on(t[1], t[2])
            if sc is None:
                return
            is_bool = self.pv.T.of(t, tc) == "Bool"
            sc_bool = self.pv.T.of(sc, tc) == "Bool"
            if sc[0] == "var":
                if is_bool and not top and not sc_bool:
                    yield ("cond", t, t)
                else:
                    yield ("var", t, sc)
            elif sc_bool:
                inner = list(self.spine(sc, top=False))
                yield from (inner or [("cond", t, sc)])
            elif is_bool and not top:
                yield ("cond", t, t)
            else:
                yield from self.spine(sc, top=False)
        elif t[0] == "ctor":
            for a in t[2]:
                yield from self.spine(a, top=top)
        elif t[0] == "tup":
            for a in t[1]:
                yield from self.spine(a, top=top)

    def stuck_calls(self, t):
        out = []
        for s in E.subterms(t):
            if s[0] == "app":
                sc = self.pv.ev_opaque.stuck_on(s[1], s[2])
                if sc is not None:
                    out.append((s, sc))
        return out

    def blocking_vars(self, g, recursive: bool):
        """[(side, var)] for the variables model definitions wait on along the spines of the differences (side 0: the
        old side, 1: the new one), in order."""
        out = []
        for l, r in self.diffs(g[0], g[1]):
            whole = (l, r) == (g[0], g[1])
            for k, side in ((0, l), (1, r)):
                for kind, call, sc in self.spine(side, top=whole):
                    if kind != "var" or sc[1] not in self.ctx:
                        continue
                    info = self.ctx[sc[1]]
                    name, _ = Types.head(info.ty)
                    model_call = call[1].startswith(ALIAS + ".")
                    if name in ("U32", "Nat") and not model_call:
                        continue
                    if name in ("Bool", "Cmp") and not model_call and not recursive:
                        continue
                    if name == "Word" and not (model_call or info.parent is not None):
                        continue
                    if info.rec and not recursive:
                        continue
                    if info.rec and info.depth > 6:
                        continue
                    if name != "Nat":
                        try:
                            self.pv.T.ctors(info.ty)
                        except Fail:
                            continue
                    out.append((k, sc[1]))
        return out

    def blocking_var(self, g, recursive: bool, common: bool = False):
        bv = self.blocking_vars(g, recursive)
        if common:
            both = [v for k, v in bv if k == 0 and (1, v) in bv]
            return both[0] if both else None
        for want in (0, 1):
            for k, v in bv:
                if k == want:
                    return v
        return None

    def deep_var(self, g):
        """A variable of a type with several constructors that a model definition anywhere in a difference waits on
        (an argument of a call that is itself stuck elsewhere)."""
        for l, r in self.diffs(g[0], g[1]):
            for side in (r, l):
                for call, sc in self.stuck_calls(side):
                    if sc[0] != "var" or sc[1] not in self.ctx or not call[1].startswith(ALIAS + "."):
                        continue
                    info = self.ctx[sc[1]]
                    if info.rec:
                        continue
                    try:
                        if len(self.pv.T.ctors(info.ty)) < 2:
                            continue
                    except Fail:
                        continue
                    return sc[1]
        return None

    def is_param(self, v):
        return 0 <= self.ctx[v].idx <= self.top_idx

    def open_var(self, g, v, ind, allow, stmts):
        """Match v here when Bend allows it (no statement yet; v a parameter after every matched parameter, or a
        field of the variable matched last), else in a helper definition."""
        info = self.ctx[v]
        allow = allow if allow is not None else (0, frozenset())
        ok = (self.is_param(v) and info.idx >= allow[0]) or v in allow[1]
        if stmts or not ok:
            return self.helper(g, ind, kind="open", var=v)
        name, _ = Types.head(info.ty)
        if name in ("U32", "Word"):
            self.pv.stats["bits"] += 1
        lines = [" " * ind + f"match {v}:"]
        if name == "Nat":
            alts = [(("nat", 0), "0n", []), (None, None, [("Nat", True)])]
            cases = []
            p = self.pv.fresh("v")
            cases.append(("0n", ("nat", 0), {}))
            cases.append((f"1n+{p}", ("nsucc", 1, ("var", p)), {p: VarInfo("Nat", v, True, info.depth + 1)}))
        else:
            cases = []
            for c, fs in self.pv.T.ctors(info.ty):
                names = [self.pv.fresh("v") for _ in fs]
                term = E.canon(("ctor", c, tuple(("var", n) for n in names)))
                pat = f"{c}{{{', '.join('+' + n for n in names)}}}"
                vi = {}
                for n, (_, ft) in zip(names, fs):
                    rec = Types.head(ft)[0] == name and name not in ("Word",)
                    vi[n] = VarInfo(ft, v, rec, info.depth + (1 if rec else 0))
                cases.append((pat, term, vi))
        for pat, term, vi in cases:
            base = max([x.idx for x in self.ctx.values()] + [self.top_idx]) + 1
            for k, n in enumerate(vi):
                vi[n].idx = base + k
            self.ctx.update(vi)
            sub = {v: term}
            g2 = (E.subst(g[0], sub), E.subst(g[1], sub), g[2])
            lines.append(" " * (ind + 2) + f"case {pat}:")
            nxt = (info.idx + 1 if self.is_param(v) else 10 ** 9, frozenset(vi))
            lines += self.solve(g2, ind + 4, allow=nxt, stmts=False)
        return lines

    # ------------------------------------------------------------------ rewriting
    def rewrite(self, g, ind):
        lines = []
        seen = set()
        for _ in range(400):
            step = self.find_rewrite(g)
            if step is None:
                return g, lines
            if (g[0], g[1]) in seen:
                raise Fail("the rewrites cycle")
            seen.add((g[0], g[1]))
            proof, inst, new = step
            if DEBUG:
                print("REWRITE", proof[:160], "|", E.show(inst)[:160], "->", E.show(new)[:160])
            lines.append(" " * ind + f"%{proof} : {self.pv.motive(g, inst)}")
            g = (self.pv.nf(E.replace(g[0], inst, new)), self.pv.nf(E.replace(g[1], inst, new)), g[2])
        raise Fail("too many rewrites")

    def find_rewrite(self, g):
        pv = self.pv
        tc = self.tyctx()
        # (a) changed callees proven equal: o__g(args) -> g(args)
        for side in (g[0], g[1]):
            for s in E.subterms(side):
                if s[0] == "app" and s[1].startswith(pv.prefix):
                    new_name = ALIAS + "." + s[1][len(pv.prefix):]
                    lem = pv.callee.get(new_name)
                    if lem and new_name != self.subj_new():
                        ty = pv.T.of(s, tc)
                        new = ("app", new_name, s[2])
                        if ty:
                            args = ", ".join(E.show(a) for a in s[2])
                            return (f"Equal.sym({ty}, {E.show(s)}, {E.show(new)}, {lem}({args}))", s, new)
        # (b) the induction hypothesis
        ih = self.ih_rewrite(g)
        if ih is not None:
            return ih
        # (c) library rules, innermost first
        for side in (g[0], g[1]):
            for path, s in sorted(E.positions(side), key=lambda x: -len(x[0])):
                if s[0] not in ("app",):
                    continue
                for r in pv.rules:
                    env = {}
                    if match(r.lhs, s, env, {n for n, _ in r.params}):
                        if any(n not in env for n, _ in r.params):
                            continue
                        new = E.subst(r.rhs, env)
                        args = ", ".join(E.show(env[n]) for n, _ in r.params)
                        pv.stats["rules"].add(r.name)
                        return (f"Equal.sym({r.ty}, {E.show(s)}, {E.show(new)}, {r.name}({args}))", s, new)
        # (d) discovered lemmas: an instance of a lemma's new-side form becomes its old-side form, anywhere; a lemma
        # whose sides are the same symbols rearranged (commutation, association) only where it closes a difference
        dif = None
        for cr in pv.conj_rules:
            pvars = {n for n, _ in cr.params}
            perm = sorted(_symbols(cr.lhs)) == sorted(_symbols(cr.rhs))
            if perm:
                dif = dif if dif is not None else self.diffs(g[0], g[1])
                for l, r in dif:
                    env = {}
                    if match(cr.rhs, r, env, pvars) and all(n in env for n, _ in cr.params) and E.subst(cr.lhs, env) == l:
                        args = ", ".join(E.show(env[n]) for n, _ in cr.params)
                        return (f"{cr.name}({args})", r, l)
                continue
            for side in (g[1], g[0]):
                for t in E.subterms(side):
                    env = {}
                    if match(cr.rhs, t, env, pvars) and all(n in env for n, _ in cr.params):
                        new = E.subst(cr.lhs, env)
                        if new == t:
                            continue
                        args = ", ".join(E.show(env[n]) for n, _ in cr.params)
                        return (f"{cr.name}({args})", t, new)
        return None

    def subj_new(self):
        s = self.subj
        return s.rhs[1] if s.rhs[0] == "app" else None

    def ih_rewrite(self, g):
        """An instance of the subject's statement at structurally smaller arguments."""
        s = self.subj
        pvars = set(s.params)
        dirs = ((s.lhs, s.rhs, False),) if s.lhs[0] == "app" else ((s.rhs, s.lhs, True),)
        for pat, other, flip in dirs:
            if pat[0] != "app":
                continue
            for side in (g[0], g[1]):
                for t in E.subterms(side):
                    env = {}
                    if t[0] != "app" or not match(pat, t, env, pvars) or any(n not in env for n in s.params):
                        continue
                    if not self.smaller([env[n] for n in s.params]):
                        continue
                    new = E.subst(other, env)
                    args = [env[n] for n in s.params]
                    eq = f"{{{E.show(E.subst(s.lhs, env))} == {E.show(E.subst(s.rhs, env))} : {s.ty}}}"
                    proof = self.ih_proof(args, eq)
                    self.pv.stats["ih"] += 1
                    if self.depth > 0:
                        self.pv.stats["lemma_ih"] += 1
                    if not flip:   # replace an instance of lhs by rhs: {rhs == lhs}
                        return (f"Equal.sym({s.ty}, {E.show(t)}, {E.show(new)}, {proof})", t, new)
                    return (proof, t, new)
        return None

    def smaller(self, args) -> bool:
        for a, p in zip(args, self.subj.params):
            if a == ("var", p):
                continue
            return a[0] == "var" and self.descendant(a[1], p)
        return False

    def ih_proof(self, args, eq) -> str:
        call = f"{self.subj.name}({', '.join(E.show(a) for a in args)})"
        if self.main:
            return call
        for n, e, _ in self.ih_req:
            if e == eq:
                return n
        n = self.pv.fresh("ih")
        self.ih_req.append((n, eq, call))
        return n

    # ------------------------------------------------------------------ differences and lemma discovery
    def diffs(self, l, r):
        if l == r:
            return []
        if l[0] == r[0] and l[0] in ("ctor", "app") and l[1] == r[1] and len(l[2]) == len(r[2]):
            out = []
            for a, b in zip(l[2], r[2]):
                out += self.diffs(a, b)
            return out if l[0] == "ctor" else out + [(l, r)]
        if l[0] == r[0] == "tup" and len(l[1]) == len(r[1]):
            out = []
            for a, b in zip(l[1], r[1]):
                out += self.diffs(a, b)
            return out
        return [(l, r)]

    def candidate_pairs(self, g):
        """Differences worth a lemma, the smallest first: where the two sides differ, and inside them, between
        subterms with the same head on both sides (aligned by their head, wherever they sit)."""
        out = []
        for l, r in self.diffs(g[0], g[1]):
            out.append((l, r))
        ls = [t for t in dict.fromkeys(E.subterms(g[0])) if t[0] == "app"]
        rs = [t for t in dict.fromkeys(E.subterms(g[1])) if t[0] == "app"]
        byhead = {}
        for t in rs:
            byhead.setdefault((t[1], len(t[2])), []).append(t)
        for s_ in ls:
            for t in byhead.get((s_[1], len(s_[2])), [])[:20]:
                if s_ != t:
                    out += self.diffs(s_, t)
                if len(out) > 400:
                    break
        seen, uniq = set(), []
        for p in out:
            if p not in seen:
                seen.add(p)
                uniq.append(p)
        return sorted(uniq, key=lambda p: E.size(p[0]) + E.size(p[1]))

    def conjecture(self, g) -> bool:
        pv = self.pv
        tc = self.tyctx()
        tried = pv.__dict__.setdefault("_tried", set())
        attempts = 0
        for l, r in self.candidate_pairs(g):
            if E.size(l) > 120 or E.size(r) > 120:
                continue
            if not set(E.free_vars(l)) & set(E.free_vars(r)):
                continue
            ty = pv.T.of(l, tc) or pv.T.of(r, tc)
            if ty is None:
                continue
            whole = (l, r) == (g[0], g[1])
            for params, cl, cr, abstracted in self.generalizations(l, r, tc):
                if whole and not abstracted:
                    continue
                key = (E.show(cl), E.show(cr))
                if key in tried:
                    continue
                tried.add(key)
                if not self.test(params, cl, cr):
                    continue
                attempts += 1
                if attempts > 6:
                    return False
                name = f"{self.owner.split('__')[0]}__c{pv.n + 1}"
                pv.n += 1
                snap = pv.snapshot()
                try:
                    text = pv.prove_lemma(name, params, cl, cr, ty, depth=self.depth + 1)
                except Fail as e:
                    pv.restore(snap)
                    pv.log.append(f"lemma {E.show(cl)[:120]} == {E.show(cr)[:120]}: {e}")
                    continue
                pv.out.append(text)
                pv.conj_rules.append(Rule(name, params, cl, cr, ty))
                pv.stats["lemma"] += 1
                return True
        return False

    def generalizations(self, l, r, tc):
        """Candidate lemmas for a difference: (params, left, right), the most general first."""
        out = []
        common = []
        rs = set(E.subterms(r))
        for s in E.subterms(l):
            if s in rs and s[0] in ("app", "var") and s not in common and self.pv.T.of(s, tc) is not None:
                if not any(s in set(E.subterms(c)) for c in common):
                    common.append(s)
        for abstract in (common, []):
            sub, params, cl, cr = {}, [], l, r
            for s in abstract:
                if s[0] == "var":
                    continue
                n = self.pv.fresh("g")
                cl, cr = E.replace(cl, s, ("var", n)), E.replace(cr, s, ("var", n))
                params.append((n, self.pv.T.of(s, tc)))
            for v in E.free_vars(cl) + [x for x in E.free_vars(cr) if x not in E.free_vars(cl)]:
                if v in tc and v not in [p for p, _ in params]:
                    params.append((v, tc[v]))
            if any(t is None for _, t in params):
                continue
            # rename the variables of the lemma apart from the context
            ren = {}
            ps2 = []
            for n, t in params:
                m = self.pv.fresh("p")
                ren[n] = ("var", m)
                ps2.append((m, t))
            cand = (ps2, E.subst(cl, ren), E.subst(cr, ren))
            cand = cand + (any(x[0] != "var" for x in abstract),)
            if all(E.show(c[1]) != E.show(cand[1]) or E.show(c[2]) != E.show(cand[2]) for c in out):
                out.append(cand)
        return out

    def test(self, params, cl, cr, n: int = 64) -> bool:
        gen = Gen(self.pv.T, E.show(cl) + "==" + E.show(cr))
        for _ in range(n):
            gen.seen = {}
            try:
                env = {p: gen.value(t) for p, t in params}
                a = E.canon(self.pv.ev_full.eval(cl, env))
                b = E.canon(self.pv.ev_full.eval(cr, env))
            except (Fail, E.TermError, RecursionError):
                return False
            if a != b:
                return False
            if any(x[0] == "app" for x in E.subterms(a)):
                return False
        return True

    # ------------------------------------------------------------------ case split with reflection
    def condition(self, g, shared=False):
        if shared:
            subl, subr = set(E.subterms(g[0])), set(E.subterms(g[1]))
            for c in self._conditions(g):
                if c in subl and c in subr and c[0] != "var":
                    return c
            return None
        for c in self._conditions(g):
            return c
        return None

    def _conditions(self, g):
        for l, r in self.diffs(g[0], g[1]):
            whole = (l, r) == (g[0], g[1])
            for side in (l, r):
                for kind, call, sc in self.spine(side, top=whole):
                    if kind == "cond":
                        yield sc
                    if kind == "var" and self.tyctx().get(sc[1]) == "Bool":
                        yield sc
        return None

    def helper(self, g, ind, kind, var=None, cond=None):
        """A helper definition taking the goal's free variables (and, for a split, c and e); its call."""
        pv = self.pv
        tc = self.tyctx()
        free = [n for n in E.free_vars(g[0]) + E.free_vars(g[1]) if n in self.ctx]
        free = list(dict.fromkeys(free + ([var] if var and var not in free else [])))
        name = f"{self.owner.split('__')[0]}__h{pv.n + 1}"
        pv.n += 1
        ctx = {}
        for i, n in enumerate(free):
            vi = self.ctx[n]
            ctx[n] = VarInfo(vi.ty, vi.parent, vi.rec, vi.depth, i)
        for n, vi in self.ctx.items():   # ancestry, for the induction hypothesis
            if n not in ctx:
                ctx[n] = VarInfo(vi.ty, vi.parent, vi.rec, vi.depth, -1)
        st = State(pv, ctx, self.subj, main=False, depth=self.depth, owner=self.owner)
        st.local = self.local
        st.top_idx = len(free) - 1
        goal = f"{{{E.show(g[0])} == {E.show(g[1])} : {g[2]}}}"
        if kind == "open":
            body = st.open_var(g, var, 2, None, stmts=False)
            extra_params, extra_args = [], []
        else:
            pv.stats["split"] += 1
            c, e = pv.fresh("c"), pv.fresh("e")
            ctx[c] = VarInfo("Bool", idx=len(free) + 100)
            body = [f"  match {c}:"]
            for val in ("True", "False"):
                body.append(f"    case {val}{{}}:")
                body += st.branch(g, cond, val, e, 6)
            extra_params = [("", c, "Bool"), ("+", e, f"{{{E.show(cond)} == {c} : Bool}}")]
            extra_args = [E.show(cond), "{==}"]
        ps = [("+", n, ctx[n].ty) for n in free] + [("+", n, eq.replace("\x00", "")) for n, eq, _ in st.ih_req]
        ps += extra_params
        head = f"def {name}({', '.join(q + n + ': ' + t for q, n, t in ps)}) -> {goal}:"
        pv.out.append(head + "\n" + "\n".join(body) + "\n")
        ih_args = [self.ih_pass(eq, call) for _, eq, call in st.ih_req]
        args = free + ih_args + extra_args
        return [" " * ind + f"{name}({', '.join(args)})"]

    def ih_pass(self, eq, call):
        if self.main:
            return call
        for n, e, _ in self.ih_req:
            if e == eq:
                return n
        n = self.pv.fresh("ih")
        self.ih_req.append((n, eq, call))
        return n

    def branch(self, g, cond, val, e, ind):
        pv = self.pv
        lines = [" " * ind + f"%Equal.sym(Bool, {E.show(cond)}, {val}{{}}, {e}) : {pv.motive(g, cond)}"]
        b = ("ctor", val, ())
        g = (pv.nf(E.replace(g[0], cond, b)), pv.nf(E.replace(g[1], cond, b)), g[2])
        if val == "True":
            eqv = self.reflection(cond, e)
            if eqv is not None:
                pv.stats["reflect"] += 1
                x, y, ty, proof = eqv
                tgt, by, pf = (x, y, f"Equal.sym({ty}, {E.show(x)}, {E.show(y)}, {proof})")
                if x[0] != "var" and y[0] == "var":
                    tgt, by, pf = y, x, proof
                if any(tgt in set(E.subterms(s)) for s in g[:2]):
                    lines.append(" " * ind + f"%{pf} : {pv.motive(g, tgt)}")
                    g = (pv.nf(E.replace(g[0], tgt, by)), pv.nf(E.replace(g[1], tgt, by)), g[2])
        return lines + self.solve(g, ind, allow=(10 ** 9, frozenset()), stmts=True)

    def reflection(self, cond, e):
        """(x, y, type, proof of {x == y}) from e : {cond == True{}}, or None."""
        pv = self.pv
        for name, (ps, pat, x, y, ty) in pv.reflect.items():
            env = {}
            if match(pat, cond, env, {n for n, _ in ps}) and all(n in env for n, _ in ps):
                args = ", ".join(E.show(env[n]) for n, _ in ps)
                return E.subst(x, env), E.subst(y, env), self.pv.T.of(E.subst(x, env), self.tyctx()) or ty, \
                    f"{name}({args}, {e})"
        if cond[0] == "app" and cond[1].startswith(ALIAS + ".") and len(cond[2]) == 2:
            lem = pv.derive_reflection(cond[1])
            if lem is not None:
                ty = pv.T.of(cond[2][0], self.tyctx())
                return cond[2][0], cond[2][1], ty, f"{lem}({E.show(cond[2][0])}, {E.show(cond[2][1])}, {e})"
        return None


def _derive_reflection(self, f: str):
    """For a model definition f(a: T, b: T) -> Bool over a one-constructor record T whose body, the fields opened, is
    a conjunction that compares each pair of fields with a reflective test: the lemma {f(a, b) == True{}} -> a == b,
    proved here (and kept); None when f has another shape."""
    cache = self.__dict__.setdefault("_refl", {})
    if f in cache:
        return cache[f]
    cache[f] = None
    d = self.defs.get(f)
    if d is None or len(d.params) != 2 or d.ret.strip() != "Bool" or d.params[0][2] != d.params[1][2]:
        return None
    ty = d.params[0][2]
    try:
        cs = self.T.ctors(ty)
    except Fail:
        return None
    if len(cs) != 1:
        return None
    c, fs = cs[0]
    an = [self.fresh("a") for _ in fs]
    bn = [self.fresh("b") for _ in fs]
    at = ("ctor", c, tuple(("var", x) for x in an))
    bt = ("ctor", c, tuple(("var", x) for x in bn))
    body = E.canon(self.ev_full.nf(("app", f, (at, bt))))
    # the conjunction's atoms, each with its projection proof from e
    atoms = []

    def walk(t, proof):
        if t[0] == "app" and t[1] == "Bool.and" and len(t[2]) == 2:
            x, y = t[2]
            walk(x, f"{L.AND_PROJ[0]}({E.show(x)}, {E.show(y)}, {proof})")
            walk(y, f"{L.AND_PROJ[1]}({E.show(x)}, {E.show(y)}, {proof})")
        else:
            atoms.append((t, proof))
    walk(body, "e")
    pairs = {}
    for t, proof in atoms:
        hit = None
        for name, (ps, pat, x, y, rty) in self.reflect.items():
            env = {}
            if match(pat, t, env, {n for n, _ in ps}) and all(n in env for n, _ in ps):
                hit = (E.subst(x, env), E.subst(y, env), f"{name}({', '.join(E.show(env[n]) for n, _ in ps)}, {proof})")
                break
        if hit is None:
            return None
        pairs[(hit[0], hit[1])] = hit[2]
    lines = []
    goal_l, goal_r = at, bt
    for (fa, fb), (_, ft) in zip(zip(an, bn), fs):
        key = (("var", fa), ("var", fb))
        if key not in pairs:
            return None
        g = (goal_l, goal_r, ty)
        mot = f"{{{E.show_hole(goal_l, ('var', fa))} == {E.show(goal_r)} : {ty}}}"
        lines.append(f"      %Equal.sym({ft}, {fa}, {fb}, {pairs[key]}) : {mot}")
        goal_l = E.replace(goal_l, ("var", fa), ("var", fb))
    name = f"{self.tag}__r_{f.split('.')[-1]}"
    pa = ", ".join("+" + x for x in an)
    pb = ", ".join("+" + x for x in bn)
    text = (f"def {name}(+a: {ty}, +b: {ty}, +e: {{{f}(a, b) == True{{}} : Bool}}) -> {{a == b : {ty}}}:\n"
            f"  match a b:\n    case {c}{{{pa}}} {c}{{{pb}}}:\n" + "\n".join(lines) + "\n      {==}\n")
    self.out.append(text)
    cache[f] = name
    return name


Prover.derive_reflection = _derive_reflection
