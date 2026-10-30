"""tag_exact (I68, rule S10 of tests_m3/test_structural_keys.py): a SORT tag law (I30, subform as_member) proved by a
Reach induction of the kept-register invariant over the structural store.

At a member read of a union register F at key K (the law's hits: cz_<x>_<a>), the coercion holds when F's companion
tag at K is the member the read assumes, member_fn(e). The read's own checks say that F[K] is not zero and that e is
the word of a register V at the same key (V: the family the check compares e with). The invariant is

  I(st, gc, k) := not nz(F[k]) or tg_eq(gc[k], member_fn(V[k]))          (nz: the read's own non-zero check)

for every key k, over the structural store (F[k], V[k] the words at F's and V's keys with step key k) and F's
companion map gc. The proof file holds:

  - ti(st, gc, k), the invariant; ti_reach(kh, s, r, k): I at every reachable state, by induction on Reach (the state
    index erased): R0 by computation (the deployment's s0), RStep by ti_step;
  - ti_step(a, p, kh, k, h): one lemma per action, its program mirrored statement by statement as a DISCH frame route
    (holon.disch.proofs.ActionProof) whose B is I at k: stores at other families framed by evaluation, a store in F's
    or V's family split on its key word (w_eq(k', k): the equal case transports the stored words, the other frames
    them), passed checks that read F or V carried down the chain (the convoy), loops by their frames, and at the end
    the ghost effect on gc (gk_same_k / gk_frame under the split's fact), the checks' and the split's equalities
    rewritten in, and I before the step (or a tag's reflexivity);
  - hit_<a>: the coercion at each hit from I at K, the non-zero check and the version check carried to the hit
    (cm_tg_<a>: the member check holds when the companion's tag is the member); Laws.<name> dispatches on the action.

A step lemma that does not apply leaves the law UNKNOWN, naming the action whose step lemma fails (NoProof). Nothing
here names a target: F, V, the member function and the checks are read from the typed model's ghost terms.
"""
from __future__ import annotations

import itertools
import re

from ..disch import order as ORDER
from ..disch import proofs as DP
from ..disch.lemmas import library
from ..disch.mirror import Final, NoMirror, as_call, split_top
from ..gen.mlaws import law_name
from ..machine_bend import bname
from ..rules.sort import ghost_x
from .proofs3 import PHEADER, model_names, tabs_binders


class NoProof(ValueError):
    """tag_exact does not apply (named)."""


def _close(t: str, i: int) -> int:
    """The index of the bracket closing the one at t[i]."""
    return DP._match_close(t, i)


def _norm(t: str) -> str:
    """Definitional simplification the comparisons of texts rely on: a payload of a wrap, M.pay_T(M.T{x}), is x."""
    while True:
        m = re.search(r"M\.pay_(\w+)\(M\.\1\{", t)
        if not m:
            return t
        i = m.end() - 1                      # the wrap's brace
        j = _close(t, i)
        if j + 1 >= len(t) or t[j + 1] != ")":
            return t
        t = t[:m.start()] + t[i + 1:j] + t[j + 2:]


_LOCAL = re.compile(r"(?<![\w.])(v_\w+|tw\d+)(?![\w{])")


def _local(t: str) -> bool:
    """Does a word name a lemma's own variables (a varying field v_<f>, a transported word tw<j>)? Such a word is
    passed to the next statement's lemma as its parameter tw<j>, never as text."""
    return _LOCAL.search(t) is not None


def _qx(t: str) -> str:
    """A ghost term of the hit's record (x_ar, x_en, x_st) as a term of the context (ar, e, st)."""
    return re.sub(r"(?<![\w.])x_(ar|en|st)(?![\w{])", lambda m: {"ar": "ar", "en": "e", "st": "st"}[m.group(1)], t)


class Spec:
    """What the law's ghost terms say: the union register F (its base slot, its companion field), the version register
    V, the member function, and per hit action its key, its member check and its non-zero and version checks."""

    def __init__(self, law: dict, model_text: str):
        self.text = model_text
        self.x = x = ghost_x(law["law_id"])
        self.names = model_names(model_text)
        m = re.search(rf"(?ms)^def coerce_{re.escape(x)}\(.*?(?=^def |^# |\Z)", model_text)
        if not m:
            raise NoProof(f"the typed model defines no coerce_{x}")
        self.hits = re.findall(rf"case A_(\w+)\{{ar, en\}}:\n      cz_{re.escape(x)}_\1\(", m.group(0))
        if not self.hits:
            raise NoProof(f"coerce_{x} has no hit")
        self.F = self.mt = self.fbase = self.vbase = None
        self.per_hit: dict = {}
        for a in self.hits:
            self.per_hit[a] = self._hit(a)
        # the companion map's field of GSt (gh_get_F reads it)
        g = re.search(rf"(?m)^def gh_get_{re.escape(self.F)}\(e: GSt\) -> [^\n]*:\n  match e:\n    case GSt\{{[^\n]*\}}:\n"
                      rf"      (\w+)$", model_text)
        if not g:
            raise NoProof(f"no getter gh_get_{self.F} of the augmented state")
        self.gvar = f"g_{g.group(1)}"

    def _hit(self, a: str) -> dict:
        x = self.x
        cz = re.search(rf"(?ms)^def cz_{re.escape(x)}_{re.escape(a)}\(x: X_{re.escape(a)}, \+g: GSt\) -> Bool:\n"
                       rf"  match x:\n    case X_\w+\{{.*?\}}:\n      (.*?)\n", self.text)
        if not cz:
            raise NoProof(f"cz_{x}_{a} is not of the known shape")
        c = as_call(cz.group(1))
        if not c or c[0] != "Bool.or" or len(c[1]) != 2:
            raise NoProof(f"cz_{x}_{a} is not a disjunction")
        cm = as_call(c[1][1])
        if not cm or len(cm[1]) != 3 or not cm[0].startswith(f"cm_{x}_"):
            raise NoProof(f"cz_{x}_{a}: no member check")
        mt, r, t = (y.strip() for y in cm[1])
        gk = as_call(t)
        gg = as_call(gk[1][0]) if gk and gk[0] == "gk_get" and len(gk[1]) == 2 else None
        if not gg or not gg[0].startswith("gh_get_") or [y.strip() for y in gg[1]] != ["g"]:
            raise NoProof(f"cz_{x}_{a}: the tag is not a companion map's read")
        F, key = gg[0][len("gh_get_"):], gk[1][1].strip()
        rr = as_call(r)
        if not rr or len(rr[1]) != 1:
            raise NoProof(f"cz_{x}_{a}: the read value is not a wrap of one word")
        mm = re.fullmatch(rf"sload\(x_st, (SK\{{(W\{{[\d, ]+\}}), w0\(\), \[SP_m\{{{re.escape(key)}, w0\(\)\}}\]\}})\)",
                          rr[1][0].strip())
        if not mm:
            raise NoProof(f"cz_{x}_{a}: the read is not the pre-state's word of a mapping at the tag's key")
        mi = re.fullmatch(r"ite\(Tag, w_eq\((.*), (W\{[\d, ]+\})\), (TG_\w+)\{\}, (TG_\w+)\{\}\)", mt)
        if not mi:
            raise NoProof(f"cz_{x}_{a}: the member function is not a choice on one word")
        arg = mi.group(1).strip()
        for name, have, want in (("register", self.F, F), ("member function", self.mt, mi.group(2, 3, 4)),
                                 ("base slot", self.fbase, mm.group(2))):
            if have is not None and have != want:
                raise NoProof(f"the hits read different unions ({name})")
        self.F, self.mt, self.fbase = F, mi.group(2, 3, 4), mm.group(2)
        # the action's checks (s_<a>_i ends in k_<a>_i(condition, record))
        conds = []
        for q in re.finditer(rf"(?m)^      k_{re.escape(a)}_\d+\((.*)\)$", self.text):
            args = split_top(q.group(1))
            if len(args) == 2:
                conds.append(args[0].strip())
        read = f"sload(x_st, {mm.group(1)})"
        nz = [q for q in conds if read in q and "W{0, 0, 0, 0, 0, 0, 0, 0}" in q
              and re.match(r"(ne_\w+|Bool\.not|w_nz)\(", q)]
        if len(nz) != 1:
            raise NoProof(f"{a}: {len(nz)} checks of the program say F[K] is not zero (one wanted)")
        vk = re.escape(key)
        ver = []
        for q in conds:
            v = re.fullmatch(rf"w_eq\({re.escape(arg)}, sload\(x_st, SK\{{(W\{{[\d, ]+\}}), w0\(\), \[SP_m\{{{vk}, "
                             rf"w0\(\)\}}\]\}}\)\)", q) or \
                re.fullmatch(rf"w_eq\(sload\(x_st, SK\{{(W\{{[\d, ]+\}}), w0\(\), \[SP_m\{{{vk}, w0\(\)\}}\]\}}\), "
                             rf"{re.escape(arg)}\)", q)
            if v and v.group(1) != self.fbase:
                ver.append((v.group(1), q))
        if len({b for b, _q in ver}) != 1:
            raise NoProof(f"{a}: no check compares the member function's argument with one register at the read's key "
                          "(the version check)")
        if self.vbase is not None and self.vbase != ver[0][0]:
            raise NoProof("the hits check different version registers")
        self.vbase = ver[0][0]
        sig = re.search(rf"(?m)^def {re.escape(cm[0])}\(m: Tag, \+r: (\w+), \+t: Tag\) -> Bool:", self.text)
        if not sig:
            raise NoProof(f"{cm[0]} is not of the known shape")
        return {"key": key, "arg": arg, "r": r, "nz": nz[0], "fkey": mm.group(1), "cm": cm[0], "rtype": sig.group(1)}

    def q(self, t: str) -> str:
        """A model term qualified (applications, constructors and bare types of the model)."""
        t = re.sub(r"(?<![\w.])([A-Za-z_]\w*)(\s*[({])", lambda m: ("M." + m.group(1) if m.group(1) in self.names
                                                                   else m.group(1)) + m.group(2), t)
        return re.sub(r"(?<![\w.])([A-Z]\w*)(?![\w({])", lambda m: "M." + m.group(1) if m.group(1) in self.names
                      else m.group(1), t)

    def kf(self, k: str) -> str:
        return self.q(f"SK{{{self.fbase}, w0(), [SP_m{{@K@, w0()}}]}}").replace("@K@", k)

    def kv(self, k: str) -> str:
        return self.q(f"SK{{{self.vbase}, w0(), [SP_m{{@K@, w0()}}]}}").replace("@K@", k)

    def cond_b(self, w: str) -> str:
        """The member function's choice on the word w."""
        return f"M.w_eq({w}, {self.q(self.mt[0])})"

    def mf(self, w: str) -> str:
        return f"M.ite(M.Tag, {self.cond_b(w)}, M.{self.mt[1]}{{}}, M.{self.mt[2]}{{}})"

    def nz_text(self, h: dict) -> str:
        """A hit's non-zero check with its read of F as @READ@ (qualified)."""
        return self.q(h["nz"].replace(f"sload(x_st, {h['fkey']})", "@READ@"))

    def nzt(self, st: str, k: str) -> str:
        """F[k] not zero over the store st, as the first hit's check states it."""
        return self.nz_text(self.per_hit[self.hits[0]]).replace("@READ@", f"M.sload({st}, {self.kf(k)})")

    def inv(self, st: str, gc: str, k: str) -> str:
        return (f"Bool.or(Bool.not({self.nzt(st, k)}), M.tg_eq(M.gk_get({gc}, {k}), "
                f"{self.mf(f'M.sload({st}, {self.kv(k)})')}))")


# ------------------------------------------------------------------------------------------------ the ghost map
GHOST_LEMMAS = """# the companion map: a write at kw is read back at a key equal to kw, and leaves a key different from kw
def gk_same_c(c: Bool, +hv: M.Tag, +k: M.W, +v: M.Tag, +t: List<&2, M.GKT>, ih: {M.gk_get(M.gk_put(t, k, v, False{}), k) == v : M.Tag}) -> {M.ite(M.Tag, c, M.ite(M.Tag, Bool.and(c, Bool.not(False{})), v, hv), M.gk_get(M.gk_put(t, k, v, Bool.or(False{}, c)), k)) == v : M.Tag}:
  match c:
    case True{}:
      {==}
    case False{}:
      ih

def gk_same(xs: List<&2, M.GKT>, +k: M.W, +v: M.Tag) -> {M.gk_get(M.gk_put(xs, k, v, False{}), k) == v : M.Tag}:
  match xs:
    case Nil{}:
      (%Equal.sym(Bool, M.w_eq(k, k), True{}, w_eq_self(k)) : {M.ite(M.Tag, _, v, M.TG_bot{}) == v : M.Tag}
      {==})
    case Con{h, +t}:
      match h:
        case M.GKT{+hk, +hv}:
          gk_same_c(M.w_eq(hk, k), hv, k, v, t, gk_same(t, k, v))

def gk_same_k(xs: List<&2, M.GKT>, +kw: M.W, +v: M.Tag, +k: M.W, e: {M.w_eq(kw, k) == True{} : Bool}) -> {M.gk_get(M.gk_set(xs, kw, v), k) == v : M.Tag}:
  (%w_refl(kw, k, e) : {M.gk_get(M.gk_set(xs, kw, v), _) == v : M.Tag}
  gk_same(xs, kw, v))

def gk_fr_c(c: Bool, +hk: M.W, +hv: M.Tag, +kw: M.W, +v: M.Tag, +d: Bool, +k: M.W, +y1: M.Tag, +y2: M.Tag, ec: {M.w_eq(hk, k) == c : Bool}, ne: {M.w_eq(k, kw) == False{} : Bool}, ih: {y1 == y2 : M.Tag}) -> {M.ite(M.Tag, c, M.ite(M.Tag, Bool.and(M.w_eq(hk, kw), Bool.not(d)), v, hv), y1) == M.ite(M.Tag, c, hv, y2) : M.Tag}:
  match c:
    case True{}:
      (%Equal.sym(M.W, hk, k, w_refl(hk, k, ec)) : {M.ite(M.Tag, Bool.and(M.w_eq(_, kw), Bool.not(d)), v, hv) == hv : M.Tag}
      (%Equal.sym(Bool, M.w_eq(k, kw), False{}, ne) : {M.ite(M.Tag, Bool.and(_, Bool.not(d)), v, hv) == hv : M.Tag}
      {==}))
    case False{}:
      ih

def gk_frame(xs: List<&2, M.GKT>, +kw: M.W, +v: M.Tag, +d: Bool, +k: M.W, +ne1: {M.w_eq(kw, k) == False{} : Bool}, +ne2: {M.w_eq(k, kw) == False{} : Bool}) -> {M.gk_get(M.gk_put(xs, kw, v, d), k) == M.gk_get(xs, k) : M.Tag}:
  match xs:
    case Nil{}:
      match d:
        case True{}:
          {==}
        case False{}:
          (%Equal.sym(Bool, M.w_eq(kw, k), False{}, ne1) : {M.ite(M.Tag, _, v, M.TG_bot{}) == M.TG_bot{} : M.Tag}
          {==})
    case Con{h, +t}:
      match h:
        case M.GKT{+hk, +hv}:
          gk_fr_c(M.w_eq(hk, k), hk, hv, kw, v, d, k, M.gk_get(M.gk_put(t, kw, v, Bool.or(d, M.w_eq(hk, kw))), k), M.gk_get(t, k), {==}, ne2, gk_frame(t, kw, v, Bool.or(d, M.w_eq(hk, kw)), k, ne1, ne2))

# a disjunction with True; the right part of an implication whose left part holds
def or_t(x: Bool) -> {Bool.or(x, True{}) == True{} : Bool}:
  match x:
    case True{}:
      {==}
    case False{}:
      {==}

def or_r(p: Bool, +q: Bool, h: {Bool.or(Bool.not(p), q) == True{} : Bool}, hp: {p == True{} : Bool}) -> {q == True{} : Bool}:
  match p:
    case True{}:
      h
    case False{}:
      efq({q == True{} : Bool}, false_ne_true(hp))
"""


def tag_names(model_text: str) -> list[str]:
    m = re.search(r"(?m)^type Tag is Data:\n((?:  \w+\{\}\n)+)", model_text)
    return re.findall(r"(?m)^  (\w+)\{\}", m.group(1)) if m else []


def tg_self(tags: list) -> str:
    """A tag equals itself (by cases on the model's tags)."""
    return ("def tg_self(t: M.Tag) -> {M.tg_eq(t, t) == True{} : Bool}:\n  match t:\n"
            + "".join(f"    case M.{t}{{}}:\n      {{==}}\n" for t in tags))


def cm_lemma(spec: Spec, a: str, tags: list) -> str:
    """cm_tg_<a>: the hit's member check holds of the member function's tag on b when the companion's tag t is that
    tag (by cases on b and t; a tag that is not the member makes the hypothesis False == True)."""
    h = spec.per_hit[a]
    _lit, A, B = spec.mt
    m = f"M.ite(M.Tag, b, M.{A}{{}}, M.{B}{{}})"
    rows = []
    for bv, want in (("True", A), ("False", B)):
        for t in tags:
            goal = f"{{M.{h['cm']}(M.{want}{{}}, r, M.{t}{{}}) == True{{}} : Bool}}"
            rows.append(f"    case {bv}{{}} M.{t}{{}}:\n      " + ("{==}" if t == want else
                                                                    f"efq({goal}, false_ne_true(h))") + "\n")
    return (f"def cm_tg_{bname(a)}(b: Bool, +r: M.{h['rtype']}, t: M.Tag, h: {{M.tg_eq(t, {m}) == True{{}} : Bool}}) -> "
            f"{{M.{h['cm']}({m}, r, t) == True{{}} : Bool}}:\n  match b t:\n" + "".join(rows))


# ------------------------------------------------------------------------------------------------ the step lemmas
class _Sec:
    """The parts of a DISCH section holon.disch.proofs.Gen reads (names and tables), for a law with no section."""

    def __init__(self, model_text: str, hashes: list):
        self.names = model_names(model_text)
        self.tabs = [n for n, _h in tabs_binders(hashes)]
        self.blk: dict = {}


class TagStep(DP.ActionProof):
    """One action's step lemma: I at k after the step from I at k before it (a frame route whose B is I)."""

    def __init__(self, g: DP.Gen, spec: Spec, action: str, prefix: str):
        self._common(g, action, "frame", prefix)
        self.spec = spec
        self.tag = None
        self.time = False
        self.T = "t"
        self.keys = [spec.kf("k"), spec.kv("k")]
        self.b_code = spec.inv("st", spec.gvar, "k")
        self.splits = True
        self.loop_extra = [("k", "M.W")]

    def fixed_params(self) -> str:
        return super().fixed_params() + ", +k: M.W"

    def fixed_args(self) -> str:
        return super().fixed_args() + ", k"

    def hb_param(self) -> str:
        return f", +hb: {{ti(st, {self.spec.gvar}, k) == True{{}} : Bool}}"

    # a transported word that names the lemma's own variables crosses into the next statement's lemma as tw<j>
    def stmt(self, i: int, state: tuple = (), conds: tuple = ()) -> str:
        return super().stmt(i, tuple(f"tw{j}" if _local(s) else s for j, s in enumerate(state)), conds)

    def hyp_params(self, state: tuple = ()) -> str:
        return "".join(f", +tw{j}: M.W" for j, s in enumerate(state) if s == f"tw{j}") + super().hyp_params(state)

    def call(self, name: str, vals: dict, invs: list, carried: tuple = ()) -> str:
        args = (self.fixed_args() + "".join(f", {vals[f]}" for f in self.var_fields)
                + "".join(f", {r}" for _x, r in invs if _local(r)) + self.hb_arg()
                + "".join(f", {x}" for x, _r in invs) + "".join(f", {x}" for x, _c in carried))
        return f"{name}({args})"

    def local_params(self, invs: list) -> tuple[str, str]:
        names = sorted({n for _x, r in invs for n in re.findall(r"(?<![\w.])(tw\d+)(?![\w{])", r)})
        return "".join(f", +{n}: M.W" for n in names), "".join(f", {n}" for n in names)

    def loop(self, node, cur: dict, invs: list, carried: tuple = ()) -> str:
        vals = self.check_fixed(node.rec.fields)
        if any(_local(r) for _x, r in self.frame_invs(cur["ov"], vals["ov"], invs, carried)):
            raise NoProof(f"{self.action}: a loop after a store at F's or V's key (a transported word through a loop "
                          "frame is not built)")
        return super().loop(node, cur, invs, carried)

    def goal(self, x: str) -> str:
        G, F = self.g.g_term(), self.spec.F
        return (f"{{ti(M.gh_get_st(M.gh_go_{self.ab}({x}, {G})), M.gh_get_{F}(M.gh_go_{self.ab}({x}, {G})), k) == "
                f"True{{}} : Bool}}")

    def convoy(self, br, carried: tuple) -> bool:
        """The passed checks that read F's or V's family (the version check, the non-zero check) and no varying
        field are carried down the chain."""
        if not br.fn.startswith(f"M.k_{self.ab}_") or len(carried) >= 6 or re.search(r"(?<![\w.])v_\w+", br.cond):
            return False
        sp = self.spec
        return any(f"M.sload(st, M.SK{{{sp.q(b)}," in br.cond for b in (sp.fbase, sp.vbase))

    def emit(self, node, cur: dict, invs: list, nonzero: str | None = None, carried: tuple = ()) -> str:
        try:
            if isinstance(node, Final):
                vals = self.check_fixed(node.fields)
                cd = vals["cd"].strip()
                if re.fullmatch(r"\d+", cd) and int(cd) != 0:
                    return "hb"
                if nonzero is not None and nonzero.strip() == cd:
                    # a code the enclosing branch's equation ec says is not 0 (a loop's exit): the step reverts
                    rec, G = f"M.X_{self.ab}{{{', '.join(node.fields)}}}", self.g.g_term()
                    ok = f"M.gh_ok_{self.ab}(_, {rec}, {G})"
                    return (f"(%Equal.sym(Bool, M.u_nz({cd}), True{{}}, ec) : {{ti(M.gh_get_st({ok}), "
                            f"M.gh_get_{self.spec.F}({ok}), k) == True{{}} : Bool}}\n      hb)")
                new_invs = self.frame_invs(cur["ov"], vals["ov"], invs, carried)
                return self.tag_end(node, vals, new_invs, carried)
            return super().emit(node, cur, invs, nonzero, carried)
        except DP.NeedSplit as ns:
            return self.split(node, cur, invs, carried, ns.x, ns.y)

    def node_goal(self, node) -> str:
        X = f"M.X_{self.ab}"
        if isinstance(node, DP.Next):
            return self.goal(f"M.s_{self.ab}_{node.j}({X}{{{', '.join(node.fields)}}})")
        if isinstance(node, Final):
            return self.goal(f"{X}{{{', '.join(node.fields)}}}")
        if isinstance(node, DP.Loop):
            return self.goal(f"M.lg_{self.ab}_{node.n}({X}{{{', '.join(node.rec.fields)}}})")
        raise NoProof(f"{self.action}: a key split at a node of kind {type(node).__name__}")

    def split(self, node, cur: dict, invs: list, carried: tuple, x: str, y: str) -> str:
        """The goal at node by cases on w_eq(x, y), each case carrying its fact (the key split of a store or of the
        ghost's write in F's or V's family)."""
        if _local(x) or _local(y):
            raise NoProof(f"{self.action}: a key split on a word that varies along the program ({x[:80]} against "
                          f"{y[:80]}) is not built")
        self.br_count += 1
        name = f"{self.p}_sp{self.br_count}"
        inner = tuple((f"hc{q}", c) for q, (_p, c) in enumerate(carried))
        eq = f"M.w_eq({x}, {y})"
        t_term = self.emit(node, cur, invs, carried=inner + (("ec", eq),))
        f_term = self.emit(node, cur, invs, carried=inner + ((f"f_not({eq}, ec)", f"Bool.not({eq})"),))
        ip = "".join(f", +{q}: {{M.sload({cur['ov']}, {k}) == {r} : M.W}}" for (q, r), k in zip(invs, self.keys))
        lp, la = self.local_params(invs)
        self.defs.append(f"def {name}(c: Bool, {self.fixed_params()}{self.var_params()}{lp}{self.hb_param()}{ip}"
                         f"{self.carried_params([c for _p, c in carried])}, +ec: {{{eq} == c : Bool}}) -> "
                         f"{self.node_goal(node)}:\n  match c:\n    case True{{}}:\n      {t_term}\n"
                         f"    case False{{}}:\n      {f_term}\n")
        args = (self.fixed_args() + "".join(f", {cur[f]}" for f in self.var_fields) + la + self.hb_arg()
                + "".join(f", {q}" for q, _r in invs) + "".join(f", {p}" for p, _c in carried))
        return f"{name}({eq}, {args}, {{==}})"

    # ------------------------------------------------------------------ the end of a path
    def ghost(self) -> tuple[str, str] | None:
        """(key, tag) of the action's write of F's companion (gh_eff_<a>), or None when it leaves the map."""
        d = re.search(rf"(?ms)^def gh_eff_{re.escape(self.ab)}\(x: X_\w+, \+g: GSt\) -> GSt:\n(.*?)(?=^def |^# |\Z)",
                      self.g.text)
        if not d:
            raise NoProof(f"{self.action}: no ghost effect gh_eff_{self.ab}")
        F = re.escape(self.spec.F)
        body = d.group(1)
        if not re.search(rf"gh_set_{F}\(", body):
            return None
        sets = re.findall(rf"gh_set_{F}\(g\w*, gk_set\(gh_get_{F}\(g\w*\), (.*)\)\) : GSt\}}$", body, re.M)
        if len(sets) != 1 or len(re.findall(rf"gh_set_{F}\(", body)) != 1:
            raise NoProof(f"{self.action}: its ghost effect writes F's companion other than by one gk_set")
        parts = split_top(sets[0])
        if len(parts) != 2:
            raise NoProof(f"{self.action}: its ghost effect's write is not of the known shape")
        out = []
        for p in parts:
            t = re.sub(rf"(?<![\w.])gh_get_{F}\(g\w*\)", "@GC@", _qx(p.strip()))
            if re.search(r"(?<![\w.@])(x_\w+|g\d*)(?![\w({])", t):
                raise NoProof(f"{self.action}: its ghost write reads more than its arguments and F's companion")
            out.append(self.spec.q(t).replace("@GC@", self.spec.gvar))
        return out[0], out[1]

    def tag_end(self, node, vals: dict, invs: list, carried: tuple) -> str:
        """I at k after a path that ends without a literal revert: by cases on the code (a revert keeps the state and
        the map), then the post-state's words at F's and V's keys (the invariants), the companion's read (the split's
        fact), the passed checks' equalities and the split's key equality rewritten in, and I before the step."""
        sp = self.spec
        ov = vals["ov"]
        gh = self.ghost()
        gv = sp.gvar
        gc = f"M.gk_set({gv}, {gh[0]}, {gh[1]})" if gh else gv
        fact = None
        if gh is not None:
            fact = self.split_fact((gh[0], "k"), carried)
            if fact is None:
                raise DP.NeedSplit(gh[0], "k")
        steps = []      # (proof of {a == b}, a, b): a rewritten into b wherever it occurs (outermost goal first)
        for j, ((_x, r), k) in enumerate(zip(invs, self.keys)):
            steps.append((f"inv{j}", f"M.sload({ov}, {k})", r))
        if gh is not None:
            read = f"M.gk_get({gc}, k)"
            if fact[0] == "eq":
                steps.append((f"gk_same_k({gv}, {gh[0]}, {gh[1]}, k, {fact[1]})", read, gh[1]))
            else:
                steps.append((f"gk_frame({gv}, {gh[0]}, {gh[1]}, False{{}}, k, {fact[1]}, "
                              f"w_ne_sym({gh[0]}, k, {fact[1]}))", read, f"M.gk_get({gv}, k)"))
        # the passed checks' word equalities (the convoy), then the split's key equality
        keqs = []
        for pc, cond in carried:
            m = re.fullmatch(r"M\.w_eq\((.*)\)", cond.strip())
            parts = split_top(m.group(1)) if m else []
            if len(parts) != 2:
                continue
            a, b = parts
            if b == "k" and DP.literal_word(a) is None:
                keqs.append((f"w_refl({a}, k, {pc})", a, "k"))
                continue
            steps.append((f"w_refl({a}, {b}, {pc})", a, b))
        steps += keqs
        body = self.rewrites(sp.inv(ov, gc, "k"), steps)
        X = f"M.X_{self.ab}"
        rec = f"{X}{{{', '.join(node.fields)}}}"
        G = self.g.g_term()
        self.br_count += 1
        name = f"{self.p}_te{self.br_count}"
        ip = "".join(f", +inv{j}: {{M.sload({ov}, {k}) == {r} : M.W}}"
                     for j, ((_x, r), k) in enumerate(zip(invs, self.keys)))
        lp, la = self.local_params(invs)
        goal = (f"{{ti(M.gh_get_st(M.gh_ok_{self.ab}(c, {rec}, {G})), M.gh_get_{sp.F}(M.gh_ok_{self.ab}(c, {rec}, {G})), "
                f"k) == True{{}} : Bool}}")
        self.defs.append(f"def {name}(c: Bool, {self.fixed_params()}{self.var_params()}{lp}{self.hb_param()}{ip}"
                         f"{self.carried_params([c for _p, c in carried])}) -> {goal}:\n  match c:\n"
                         f"    case True{{}}:\n      hb\n    case False{{}}:\n      {body}\n")
        args = (self.fixed_args() + "".join(f", v_{f}" for f in self.var_fields) + la + self.hb_arg()
                + "".join(f", {x}" for x, _r in invs) + "".join(f", {p}" for p, _c in carried))
        return f"{name}(M.u_nz({vals['cd']}), {args})"

    def rewrites(self, start: str, steps: list) -> str:
        """The proof of {start == True}: each step turns a into b wherever a occurs in the current text (skipped when
        a does not occur), then I before the step, a tag's reflexivity or a case split finishes."""
        texts = [_norm(start)]
        used = []
        for prf, a, b in steps:
            a, b = _norm(a), _norm(b)
            if a == b or a not in texts[-1]:
                continue
            used.append((prf, a, b))
            texts.append(texts[-1].replace(a, b))
        body = self.finish(texts[-1], _norm(self.b_code))
        for i in range(len(used) - 1, -1, -1):
            prf, a, b = used[i]
            ty = "M.Tag" if a.startswith("M.gk_get(") else "M.W"
            body = (f"(%Equal.sym({ty}, {a}, {b}, {prf}) : {{{texts[i].replace(a, '_')} == True{{}} : Bool}}\n"
                    f"      {body})")
        return body

    def finish(self, text: str, hb_text: str) -> str:
        if text == hb_text:
            return "hb"
        i = text.find("M.tg_eq(")
        while i >= 0:
            j = _close(text, i + len("M.tg_eq"))
            atom = text[i:j + 1]
            c = as_call(atom)
            if c and len(c[1]) == 2 and c[1][0].strip() == c[1][1].strip():
                rest = text.replace(atom, "True{}")
                mo = re.fullmatch(r"Bool\.or\((.*), True\{\}\)", rest)
                tail = f"or_t({mo.group(1)})" if mo and len(split_top(mo.group(1))) == 1 else "{==}"
                return (f"(%Equal.sym(Bool, {atom}, True{{}}, tg_self({c[1][0].strip()})) : "
                        f"{{{text.replace(atom, '_')} == True{{}} : Bool}}\n      {tail})")
            i = text.find("M.tg_eq(", j)
        # a case split over the atoms of I before the step and of the goal (closed atoms left to evaluation)
        atoms: list = []
        so = DP.skeleton(hb_text, atoms, keep=DP._closed)
        sn = DP.skeleton(text, atoms, keep=DP._closed)
        if len(atoms) > 8:
            raise NoProof(f"{self.action}: the step's end has too many atoms for a case split")
        self.br_count += 1
        nm = f"{self.p}_tc{self.br_count}"
        vs = [f"v{i}" for i in range(len(atoms))]
        rows = [f"def {nm}(" + "".join(f"{x}: Bool, " for x in vs) + f"hb: {{{so} == True{{}} : Bool}}) -> "
                f"{{{sn} == True{{}} : Bool}}:\n"]
        if not vs:
            rows.append("  {==}\n")
        else:
            rows.append(f"  match {' '.join(vs)}:\n")
            for vals in itertools.product([True, False], repeat=len(vs)):
                val = dict(enumerate(vals))
                pat = " ".join("True{}" if v else "False{}" for v in vals)
                inst = re.sub(r"(?<![\w.])v(\d+)(?![\w{])", lambda q: "True{}" if val[int(q.group(1))] else "False{}",
                              sn)
                if DP._bev_open(so, val) is False:
                    rows.append(f"    case {pat}:\n      efq({{{inst} == True{{}} : Bool}}, false_ne_true(hb))\n")
                else:
                    rows.append(f"    case {pat}:\n      {{==}}\n")
        self.defs.append("".join(rows))
        return f"{nm}({''.join(a + ', ' for a in atoms)}hb)"


# ------------------------------------------------------------------------------------------------ the hit
class TagHit(DP.ActionProof):
    """The coercion at a hit action: its program mirrored; at the end of a path that passes its checks, the member
    check from I at the read's key, the non-zero check and the version check carried there."""

    def __init__(self, g: DP.Gen, spec: Spec, action: str, prefix: str):
        self._common(g, action, "revert", prefix)
        self.spec = spec
        self.tag = None
        self.time = False
        self.T = "t"
        self.keys = []
        self.b_code = "True{}"
        h = spec.per_hit[action]
        self.h = h
        self.key = spec.q(_qx(h["key"]))
        self.arg = spec.q(_qx(h["arg"]))
        self.r = spec.q(_qx(h["r"]))
        self.vread = f"M.sload(st, {spec.kv(self.key)})"
        self.nz = spec.nz_text(h).replace("@READ@", f"M.sload(st, {spec.kf(self.key)})")
        self.tg = f"M.tg_eq(M.gk_get({spec.gvar}, {self.key}), {spec.mf(self.vread)})"
        self.vchecks = (f"M.w_eq({self.arg}, {self.vread})", f"M.w_eq({self.vread}, {self.arg})")

    def fixed_params(self) -> str:
        return super().fixed_params() + self.g.g_params()

    def fixed_args(self) -> str:
        return super().fixed_args() + self.g.g_args()

    def hb_param(self) -> str:
        return f", +hb: {{ti(st, {self.spec.gvar}, {self.key}) == True{{}} : Bool}}"

    def goal(self, x: str) -> str:
        return f"{{M.cz_{self.spec.x}_{self.ab}({x}, {self.g.g_term()}) == True{{}} : Bool}}"

    def convoy(self, br, carried: tuple) -> bool:
        c = br.cond.strip()
        return br.fn.startswith(f"M.k_{self.ab}_") and len(carried) < 6 and (c == self.nz or c in self.vchecks)

    def contradiction(self, br):
        return None

    def emit(self, node, cur: dict, invs: list, nonzero: str | None = None, carried: tuple = ()) -> str:
        if isinstance(node, Final):
            vals = self.check_fixed(node.fields)
            cd = vals["cd"].strip()
            if re.fullmatch(r"\d+", cd) and int(cd) != 0:
                return "{==}"
            if nonzero is not None and nonzero.strip() == cd:
                # a code the enclosing branch's equation ec says is not 0 (a loop's exit): the coercion holds by it
                return (f"(%Equal.sym(Bool, M.u_nz({cd}), True{{}}, ec) : {{Bool.or(Bool.not(Bool.not(_)), "
                        f"{self.cm(self.arg)}) == True{{}} : Bool}}\n      {{==}})")
            return self.at_hit(vals, carried)
        return super().emit(node, cur, invs, nonzero, carried)

    def cm(self, w: str) -> str:
        """The hit's member check of the member function's tag on w (the companion's tag read at the key)."""
        return f"M.{self.h['cm']}({self.spec.mf(w)}, {self.r}, M.gk_get({self.spec.gvar}, {self.key}))"

    def at_hit(self, vals: dict, carried: tuple) -> str:
        sp = self.spec
        hnz = next((p for p, c in carried if c.strip() == self.nz), None)
        hv = next(((p, c.strip() == self.vchecks[1]) for p, c in carried if c.strip() in self.vchecks), None)
        if hnz is None or hv is None:
            raise NoProof(f"{self.action}: a path to the hit passes no non-zero check or no version check")
        ev = (f"Equal.sym(M.W, {self.vread}, {self.arg}, w_refl({self.vread}, {self.arg}, {hv[0]}))" if hv[1] else
              f"w_refl({self.arg}, {self.vread}, {hv[0]})")
        tgt = f"M.gk_get({sp.gvar}, {self.key})"
        cm = self.cm
        htg = f"or_r({self.nz}, {self.tg}, hb, {hnz})"
        hcm = f"cm_tg_{self.ab}({sp.cond_b(self.vread)}, {self.r}, {tgt}, {htg})"
        u = f"Bool.not(Bool.not(M.u_nz({vals['cd']})))"
        return (f"(%Equal.sym(M.W, {self.arg}, {self.vread}, {ev}) : {{Bool.or({u}, {cm('_')}) == True{{}} : Bool}}\n"
                f"      (%Equal.sym(Bool, {cm(self.vread)}, True{{}}, {hcm}) : {{Bool.or({u}, _) == True{{}} : Bool}}\n"
                f"      or_t({u})))")


# ------------------------------------------------------------------------------------------------ the file
def tag_exact(law: dict, mm, model_text: str, model_import: str, laws_import: str, hashes: list) -> str:
    """The proof file of a SORT tag law by tag_exact; NoProof names what does not apply (the failing step lemma)."""
    if law.get("subform") != "as_member":
        raise NoProof("tag_exact decides as_member laws")
    if "\ntype SK is Data:\n" not in model_text:
        raise NoProof("tag_exact needs the structural store (holon-model-m3/0.3): a raw store's mapping slots go "
                      "through the law's hash parameter, which the statement leaves unconstrained")
    spec = Spec(law, model_text)
    tags = tag_names(model_text)
    if "TG_bot" not in tags or len(tags) != 3 or set(tags) != {"TG_bot", spec.mt[1], spec.mt[2]}:
        raise NoProof("the companion's tags are not the member function's two members and bottom")
    s0 = re.search(r"(?ms)^def s0\(\) -> HSt:\n(.*?)(?=^def |^# |\Z)", model_text)
    if s0 is None:
        raise NoProof("the typed model defines no deployment state s0")
    if any(f"SK{{{b}, " in s0.group(1) for b in (spec.fbase, spec.vbase)):
        raise NoProof("the invariant at s0 (R0): the deployment's state holds keys of F's or V's family, which an "
                      "evaluation at a key variable cannot decide (a key split over the deployment is not built)")
    g = DP.Gen(model_text, _Sec(model_text, hashes), {})
    tnames = [n for n, _h in tabs_binders(hashes)]
    targs = "".join(f", {n}" for n in tnames)
    tparams = "".join(f", +{n}: List<&2, M.HKB>" for n in tnames)
    F = spec.F
    acts = re.findall(r"(?m)^  A_(\w+)\{ar: AR_\w+, en: HEnv\}$", model_text)
    if not acts:
        raise NoProof("the model declares no action constructors")
    defs: list = []
    step_cases = []
    for i, ab in enumerate(acts):
        ap = TagStep(g, spec, ab, f"t{i}")
        try:
            term = ap.term()
        except (DP.NoProof, NoMirror, NoProof) as e:
            raise NoProof(f"the step lemma of {ab} fails: {e}") from e
        defs += ap.defs
        name = f"t{i}_step"
        defs.append(f"def {name}({ap.fixed_params()}{ap.hb_param()}) -> {ap.goal(f'M.xr_{ab}(st, ar, e{targs})')}:\n"
                    f"  {term}\n")
        step_cases.append(f"        case M.A_{ab}{{+ar, +en}}:\n          {name}(st, ar, en{targs}, M.w0(){g.g_args()}, k, h)\n")
    gpat = "M.GSt{" + ", ".join(["+st"] + [f"+g_{f}" for f in g.gst[1:]]) + "}"
    gterm = "M.GSt{" + ", ".join(["st"] + [f"g_{f}" for f in g.gst[1:]]) + "}"
    ti = lambda s: f"ti(M.gh_get_st({s}), M.gh_get_{F}({s}), k)"   # noqa: E731
    defs.append(f"def ti_step(+p: M.GSt, a: M.HAct{tparams}, +k: M.W, h: {{{ti('p')} == True{{}} : Bool}}) -> "
                f"{{{ti(f'M.gh_step(a, p{targs})')} == True{{}} : Bool}}:\n  match p:\n    case {gpat}:\n"
                f"      match a:\n" + "".join(step_cases))
    rparams = ", ".join([f"+{n}: List<&2, M.HKB>" for n in tnames] + ["-s: M.GSt", f"r: M.Reach<{', '.join(tnames + ['s'])}>",
                                                                         "+k: M.W"])
    defs.append(f"def ti_reach({rparams}) -> {{{ti('s')} == True{{}} : Bool}}:\n  match r:\n    case M.R0{{e}}:\n"
                f"      (%Equal.sym(M.GSt, s, M.gh_s0(), e) : {{{ti('_')} == True{{}} : Bool}}\n      {{==}})\n"
                f"    case M.RStep{{+a, +p, rp, e}}:\n"
                f"      (%Equal.sym(M.GSt, s, M.gh_step(a, p{targs}), e) : {{{ti('_')} == True{{}} : Bool}}\n"
                f"      ti_step(p, a{targs}, k, ti_reach({', '.join(tnames + ['p', 'rp', 'k'])})))\n")
    hit_keys = {}
    cms = []
    for a in spec.hits:
        ab = bname(a)
        hp = TagHit(g, spec, a, f"h_{ab}")
        try:
            term = hp.term()
        except (DP.NoProof, NoMirror, NoProof) as e:
            raise NoProof(f"the coercion at {a} fails: {e}") from e
        cms.append(cm_lemma(spec, a, tags))
        defs += hp.defs
        defs.append(f"def hit_{ab}({hp.fixed_params()}{hp.hb_param()}) -> {hp.goal(f'M.xr_{ab}(st, ar, e{targs})')}:\n"
                    f"  {term}\n")
        hit_keys[ab] = hp.key
    rows = []
    for ab in acts:
        if ab not in hit_keys:
            rows.append(f"        case M.A_{ab}{{_, _}}:\n          {{==}}\n")
            continue
        reach = f"ti_reach({', '.join(tnames + [gterm, 'r_s', hit_keys[ab]])})"
        rows.append(f"        case M.A_{ab}{{+ar, +en}}:\n          hit_{ab}(st, ar, en{targs}, M.w0(){g.g_args()}, "
                    f"{reach})\n")
    params = ", ".join(tnames + ["s", "r_s", "a"])
    main = (f"def Laws.{law_name(law['law_id'])}({params}):\n  match s:\n    case {gpat}:\n      match a:\n"
            + "".join(rows))
    inv = f"def ti(+st: M.HSt, +gc: List<&2, M.GKT>, +k: M.W) -> Bool:\n  {spec.inv('st', 'gc', 'k')}\n"
    head = [PHEADER, "import Base", f"import {model_import} as M", f"import {laws_import} as Laws", "",
            f"# class tag_exact: a Reach induction of the kept-register invariant (F = {F}, V at {spec.vbase}), one",
            "# step lemma per action over the structural store, and the coercion at each hit from the invariant.",
            library(True), ORDER.text("M.", True), GHOST_LEMMAS, tg_self(tags)] + cms + [inv]
    return "\n".join(head + defs + [main])
