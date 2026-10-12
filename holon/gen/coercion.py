"""coercion_guard: the proof class of SORT-site laws whose obligation a passed condition implies (BUILD_PLAN I15;
whitepaper §7.8 realize, Thm 6.18 localization). Untrusted like every generator: a proof counts only if Bend
accepts it.

A SORT-site law states `site_<x>(a, s[, tables]) == True` for every action a and state s (holon.sorts.sites: the
ghost predicate of the instrumented model). Its proof mirrors the ghost section of the model text it is checked
against, definition by definition, so the generator reads that text (never the facts, the derivation or a site
name):

  site_<x>        `match a`: an action that is no entry point computes True{} (`{==}`); an entry point calls the
                  lemma of its chain head.
  gs_<x>_<a>      `match s` on the state record, the lets as written, then the body.
  gs_<x>_<a>_<i>  a decision helper (`match c`): its lemma takes the condition c the caller computed and, when a
                  hit below uses it, the equation `e: {<condition> == c}`; after `match c` the False case is the
                  stopped action (`{==}`) and in the True case `e` states that the condition held.
  gs_<x>_<a>_k<i> a continuation (the chain after a hit that is not the action's last).
  gd_<x>_<f>      a definition ghost: proved for every argument, with no fact from the caller.

Bodies are proved by their shape: `True{}` by `{==}`; `Bool.and(X, Y)` by core_and_intro of the two proofs;
`ite(Bool, C, X, Y)` by a helper that takes C as a parameter with its equation and matches it (X under C == True,
Y under C == False); a call of a ghost definition by that definition's lemma; and a hit's obligation
`Nat.is_le(subtrahend, minuend)` from ONE fact the evaluation has passed (the equation of an earlier decision, or
of an enclosing ite: a require before the hit or a path condition of the occurrence), never two combined: zero or
more Bool.and projections of that fact (single-expression model definitions such as an in-window predicate unfold
by computation), then one comparison lemma of the core library (holon.gen.core.CATALOG: a lemma whose one
hypothesis matches the fact and whose claim matches the obligation). Facts are tried in the order the evaluation
passed them (outer decisions first, in guard order). Equations are Type, not Data, so each is used once: a fact
moves to the one sub-proof that uses it; a proof that needs one fact twice is not generated. Lemmas are called
through the imported core (`C.`). The proof never assumes reachability: its lemmas hold for every state, which is
why the Reach evidence of the law is not used.

`proof(...)` returns the PROOF.bend text, or raises NoProof with the hit it could not discharge (the class does not
apply; holon.mpipeline records why).
"""
from __future__ import annotations

import re

from .core import CATALOG

GHOST_MARKER = "# ---- ghost: SORT-site instrumentation (holon.sorts.sites)"
ALIAS = "M"


class NoProof(Exception):
    """The class does not apply: some hit has no passed condition that implies its obligation."""


# ---------------------------------------------------------------- terms
_TOK = re.compile(r"\s*(&\d+|\d+n\+|\d+n|\d+|[A-Za-z_][\w.]*\{\}|[A-Za-z_][\w.]*|[(),])")


def parse(text: str):
    """A term of the ghost section: ("app", f, (args..)) or ("id", name) (variables, type names, literals)."""
    toks, pos, text = [], 0, text.strip()
    while pos < len(text):
        m = _TOK.match(text, pos)
        if not m or m.end() == pos:
            raise NoProof(f"cannot read the term {text[pos:pos + 40]!r}")
        toks.append(m.group(1))
        pos = m.end()
    i = 0

    def term():
        nonlocal i
        if i >= len(toks):
            raise NoProof(f"truncated term {text!r}")
        t = toks[i]
        i += 1
        if t in ("(", ")", ","):
            raise NoProof(f"unexpected {t!r} in {text!r}")
        if t.endswith("n+"):   # successor syntax 1n+x
            return ("app", t, (term(),))
        if i < len(toks) and toks[i] == "(":
            i += 1
            args = []
            if toks[i] != ")":
                args.append(term())
                while toks[i] == ",":
                    i += 1
                    args.append(term())
            if toks[i] != ")":
                raise NoProof(f"expected ) in {text!r}")
            i += 1
            return ("app", t, tuple(args))
        return ("id", t)
    out = term()
    if i != len(toks):
        raise NoProof(f"trailing tokens in {text!r}")
    return out


def render(t, qual=None) -> str:
    """Bend text of a term; `qual` maps a model name to its qualified spelling."""
    if t[0] == "id":
        return qual(t[1], False) if qual else t[1]
    f = qual(t[1], True) if qual else t[1]
    if f.endswith("n+"):
        return f + render(t[2][0], qual)
    return f"{f}({', '.join(render(a, qual) for a in t[2])})"


def free(t) -> list[str]:
    """Identifiers of a term in first-occurrence order (variables, and names the caller filters)."""
    out: list[str] = []

    def go(x):
        if x[0] == "id":
            if x[1] not in out:
                out.append(x[1])
        else:
            for a in x[2]:
                go(a)
    go(t)
    return out


def subst(t, env: dict):
    if t[0] == "id":
        return env.get(t[1], t)
    return ("app", t[1], tuple(subst(a, env) for a in t[2]))


# ---------------------------------------------------------------- the ghost section
class Def:
    def __init__(self, name: str, params: list, kind: str, lets: list, body, pattern: str | None = None,
                 cases: dict | None = None, scrut: str | None = None):
        self.name, self.params, self.kind, self.lets, self.body = name, params, kind, lets, body
        self.pattern, self.cases, self.scrut = pattern, cases or {}, scrut

    def ptypes(self) -> dict:
        return {n: t for _, n, t in self.params}


def split_params(text: str) -> list[tuple[str, str, str]]:
    out, depth, cur = [], 0, ""
    for ch in text:
        depth += ch in "(<{"
        depth -= ch in ")>}"
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    res = []
    for p in out:
        name, ty = p.split(":", 1)
        name = name.strip()
        mode = name[0] if name[0] in "+-" else ""
        res.append((mode, name.lstrip("+-"), ty.strip()))
    return res


_HEAD = re.compile(r"^def (\w+)\((.*)\) -> (.+):$")


def parse_ghost(model_text: str) -> dict[str, Def]:
    """The definitions after GHOST_MARKER, by name."""
    if GHOST_MARKER not in model_text:
        raise NoProof("the model has no ghost section")
    lines = model_text.split(GHOST_MARKER, 1)[1].splitlines()
    blocks, cur = [], None
    for ln in lines:
        if ln.startswith("def "):
            cur = [ln]
            blocks.append(cur)
        elif cur is not None and ln.startswith(" "):
            cur.append(ln)
        elif cur is not None and ln.strip() == "":
            cur = None
    out = {}
    for b in blocks:
        m = _HEAD.match(b[0])
        if not m or m.group(3) != "Bool":
            continue
        name, params = m.group(1), split_params(m.group(2))
        body = [x for x in b[1:] if x.strip()]
        out[name] = _parse_body(name, params, body)
    return out


def _lets_and_expr(lines: list[str]) -> tuple[list, object]:
    lets = []
    for ln in lines[:-1]:
        mm = re.match(r"^\s*\+?(\w+)\s*=\s*(.+)$", ln)
        if not mm:
            raise NoProof(f"cannot read the ghost line {ln.strip()!r}")
        lets.append((mm.group(1), parse(mm.group(2))))
    return lets, parse(lines[-1])


def _parse_body(name: str, params: list, body: list[str]) -> Def:
    first = body[0].strip()
    mm = re.match(r"^match (\w+):$", first)
    if not mm:
        lets, expr = _lets_and_expr(body)
        return Def(name, params, "straight", lets, expr)
    scrut = mm.group(1)
    ptype = next((t for _, n, t in params if n == scrut), None)
    # cases: "case PAT:" at the indentation of body[1]
    ind = len(body[1]) - len(body[1].lstrip())
    cases, cur = [], None
    for ln in body[1:]:
        if len(ln) - len(ln.lstrip()) == ind and ln.strip().startswith("case "):
            cur = [ln.strip()[5:-1], []]
            cases.append(cur)
        else:
            cur[1].append(ln)
    if ptype == "HAct":
        return Def(name, params, "dispatch", [], None, cases={p: _lets_and_expr(ls)[1] for p, ls in cases},
                   scrut=scrut)
    if ptype == "HSt":
        if len(cases) != 1:
            raise NoProof(f"{name}: a state match with {len(cases)} cases")
        lets, expr = _lets_and_expr(cases[0][1])
        return Def(name, params, "state", lets, expr, pattern=cases[0][0], scrut=scrut)
    if ptype == "Bool" and [p for p, _ in cases] == ["False{}", "True{}"]:
        stop = _lets_and_expr(cases[0][1])[1]
        lets, expr = _lets_and_expr(cases[1][1])
        return Def(name, params, "decision", lets, expr, cases={"False{}": stop}, scrut=scrut)
    raise NoProof(f"{name}: a ghost definition of an unknown shape")


# ---------------------------------------------------------------- core lemmas as patterns
def _bool_eq(text: str):
    """{P == True{}|False{} : Bool} -> (P term, polarity), else None."""
    m = re.fullmatch(r"\{(.*) == (True|False)\{\} : Bool\}", text.strip())
    return (parse(m.group(1)), m.group(2) == "True") if m else None


def _lemmas():
    """(projections, comparisons) of the core catalog, as (name, binders, hypothesis pattern, claim pattern)."""
    proj, comp = [], []
    for name, bs, hs, claim, cls in CATALOG:
        if cls == "absurd" or len(hs) != 1:
            continue
        h, c = _bool_eq(hs[0][1]), _bool_eq(claim)
        if h is None or c is None or not c[1]:
            continue
        names = [n for _, n, _ in bs]
        entry = (name, names, h, c)
        if h[0][0] == "app" and h[0][1] == "Bool.and" and h[1] and c[0][0] == "id" and c[0][1] in names:
            proj.append(entry)
        elif c[0][0] == "app" and c[0][1] == "Nat.is_le":
            comp.append(entry)
    return proj, comp


def match(pat, t, pv: set, sub: dict) -> dict | None:
    if pat[0] == "id" and pat[1] in pv:
        if pat[1] in sub:
            return sub if sub[pat[1]] == t else None
        return {**sub, pat[1]: t}
    if pat[0] != t[0]:
        return None
    if pat[0] == "id":
        return sub if pat == t else None
    if pat[1] != t[1] or len(pat[2]) != len(t[2]):
        return None
    for p, x in zip(pat[2], t[2]):
        sub = match(p, x, pv, sub)
        if sub is None:
            return None
    return sub


# ---------------------------------------------------------------- the proof
class Fact:
    """An equation {cond == pol} in scope, by the name of its proof term."""

    def __init__(self, fid: int, cond, pol: bool, name: str):
        self.id, self.cond, self.pol, self.name = fid, cond, pol, name


class Gen:
    def __init__(self, model_text: str, x: str, ref=None, mode: str | None = None):
        self.ref = ref or (lambda n: f"C.{n}")
        # canary modes (holon.mcanary, gate G4): "drop" replaces the first lemma-derived obligation by `{==}`, "force"
        # discharges an obligation no passed condition implies by `{==}`; Bend must reject either for a semantic reason
        self.mode = mode
        self.altered: list[str] = []
        self.ghost = parse_ghost(model_text)
        self.defs = set(re.findall(r"(?m)^def (\w+)\(", model_text))
        self.types = set(re.findall(r"(?m)^type (\w+)", model_text))
        self.ctors, self.fields = self._ctors(model_text)
        self.simple = self._simple_defs(model_text)
        self.x = x
        self.out: list[str] = []
        self.names: set = set()
        self.done_defs: dict = {}
        self.n_fact = 0
        self.proj, self.comp = _lemmas()
        self.used_lemmas: list[str] = []
        self.notes: list[str] = []

    @staticmethod
    def _ctors(text: str) -> tuple[set, dict]:
        """Constructor names of the model's types, and each constructor's field types."""
        ctors, fields = set(), {}
        for blk in re.finditer(r"(?m)^type [^\n]*:\n((?:  [^\n]*\n)+)", text):
            for m in re.finditer(r"(?m)^  (\w+)\{(.*)\}$", blk.group(1)):
                ctors.add(m.group(1))
                fs = {}
                for part in split_params(m.group(2)) if m.group(2).strip() else []:
                    fs[part[1]] = part[2]
                fields[m.group(1)] = fs
        return ctors, fields

    @staticmethod
    def _simple_defs(text: str) -> dict:
        """Single-expression model definitions (no match), for unfolding a fact by computation."""
        out = {}
        for m in re.finditer(r"(?m)^def (\w+)\((.*)\) -> .+:\n  (?!match )(.+)\n", text):
            try:
                out[m.group(1)] = ([n for _, n, _ in split_params(m.group(2))], parse(m.group(3)))
            except (NoProof, ValueError):
                continue
        return out

    # ------------------------------------------------------------ names
    def qual(self, name: str, call: bool) -> str:
        if call:
            return f"{ALIAS}.{name}" if name in self.defs else name
        return f"{ALIAS}.{name}" if name in self.types or name in self.ctors else name

    def r(self, t) -> str:
        return render(t, self.qual)

    def qtype(self, ty: str) -> str:
        return re.sub(r"(?<![\w.])([A-Za-z_]\w*)", lambda m: self.qual(m.group(1), False), ty)

    def fresh(self, base: str) -> str:
        n, i = base, 1
        while n in self.names or n in self.defs:
            i += 1
            n = f"{base}_{i}"
        self.names.add(n)
        return n

    @staticmethod
    def local(base: str, taken) -> str:
        n, i = base, 0
        while n in taken:
            i += 1
            n = f"{base}{i}"
        return n

    def new_fact(self, cond, pol: bool, name: str) -> Fact:
        self.n_fact += 1
        return Fact(self.n_fact, cond, pol, name)

    # ------------------------------------------------------------ scope helpers
    @staticmethod
    def expand(t, lets: dict):
        """t with let-bound names replaced by their definitions (recursively)."""
        if t[0] == "id":
            return Gen.expand(lets[t[1]], lets) if t[1] in lets else t
        return ("app", t[1], tuple(Gen.expand(a, lets) for a in t[2]))

    def unfold(self, t):
        """One step of computation on a call of a single-expression model definition, else None."""
        if t[0] == "app" and t[1] in self.simple:
            ps, body = self.simple[t[1]]
            if len(ps) == len(t[2]):
                return subst(body, dict(zip(ps, t[2])))
        return None

    # ------------------------------------------------------------ one obligation from one fact
    def derive(self, goal, facts: list[Fact], lets: dict):
        """A proof of {goal == True} from ONE fact (projections, then one comparison lemma), and the fact used."""
        g = self.expand(goal, lets)
        for f in facts:
            for ty, term, path in self.projections(self.expand(f.cond, lets), f.pol, f.name):
                if ty == (g, True):
                    return term, f, path + ["fact"]
                for name, names, (hp, hpol), (cp, _) in self.comp:
                    if hpol != ty[1]:
                        continue
                    sub = match(hp, ty[0], set(names), {})
                    if sub is None:
                        continue
                    sub = match(cp, g, set(names), sub)
                    if sub is None or set(names) - set(sub):
                        continue
                    args = [self.r(sub[n]) for n in names]
                    return f"{self.ref(name)}({', '.join(args + [term])})", f, path + [name]
        return None

    def projections(self, cond, pol: bool, term: str, depth: int = 0):
        """(type (cond, pol), proof term, lemma path) of the fact and of every Bool.and projection of it, the
        fact's own definitions unfolded by computation where that exposes a conjunction."""
        yield (cond, pol), term, []
        if depth > 6 or not pol:
            return
        c = cond
        for _ in range(4):
            if c[0] == "app" and c[1] == "Bool.and" and len(c[2]) == 2:
                break
            c = self.unfold(c)
            if c is None:
                return
        for name, names, (hp, _), (cp, _) in self.proj:
            sub = match(hp, c, set(names), {})
            if sub is None or set(names) - set(sub):
                continue
            part = sub[cp[1]]
            args = [self.r(sub[n]) for n in names]
            for ty, t2, path in self.projections(part, True, f"{self.ref(name)}({', '.join(args + [term])})", depth + 1):
                yield ty, t2, [name] + path

    # ------------------------------------------------------------ bodies
    def prove(self, t, facts: list[Fact], lets: dict, scope: dict, where: str) -> tuple[str, set]:
        """(proof term of {t == True{}}, ids of the facts it uses) in a scope (params name -> type, lets)."""
        if t == ("id", "True{}"):
            return "{==}", set()
        if t[0] != "app":
            raise NoProof(f"{where}: cannot prove {render(t)} == True")
        f = t[1]
        if f == "Bool.and" and len(t[2]) == 2:
            x, y = t[2]
            px, ux = self.prove(x, facts, lets, scope, where)
            py, uy = self.prove(y, [h for h in facts if h.id not in ux], lets, scope, where)
            self.lemma_used("core_and_intro")
            return f"{self.ref('core_and_intro')}({self.r(x)}, {self.r(y)}, {px}, {py})", ux | uy
        if f == "ite" and len(t[2]) == 4 and t[2][0] == ("id", "Bool"):
            return self.ite(t, facts, lets, scope, where)
        if f == "Nat.is_le":
            got = self.derive(t, facts, lets)
            if got is None:
                if self.mode == "force":
                    self.altered.append(render(self.expand(t, lets)))
                    return "{==}", set()
                raise NoProof(f"{where}: no passed condition implies {render(t)}")
            term, fact, path = got
            if self.mode == "drop" and not self.altered and any(x != "fact" for x in path):
                self.altered.append(render(self.expand(t, lets)))
                return "{==}", set()
            for p in path:
                if p != "fact":
                    self.lemma_used(p)
            self.notes.append(f"{where}: {render(self.expand(t, lets))} from {render(fact.cond)} == "
                              f"{'True' if fact.pol else 'False'} by {' -> '.join(path)}")
            return term, {fact.id}
        if f in self.ghost:
            return self.call(t, facts, lets, scope, where)
        raise NoProof(f"{where}: cannot prove {render(t)} == True")

    def lemma_used(self, name: str) -> None:
        if name not in self.used_lemmas:
            self.used_lemmas.append(name)

    # ------------------------------------------------------------ helpers with their own match
    def hyp_params(self, hyps: list, taken: set) -> tuple[list, dict]:
        """Fresh parameter names for carried facts: (signature parts, fact id -> name)."""
        sig, names = [], {}
        for h in hyps:
            n = self.local("h", taken)
            taken.add(n)
            names[h.id] = n
            sig.append(f"{n}: {{{self.r(h.cond)} == {'True' if h.pol else 'False'}{{}} : Bool}}")
        return sig, names

    def ite(self, t, facts, lets, scope, where) -> tuple[str, set]:
        """ite(Bool, C, X, Y) == True through a helper that takes C as a parameter, with C's equation when a branch
        uses it, and matches it."""
        _, c, xb, yb = t[2]
        name = self.fresh(f"cg_ite_{self.x}")
        ce, xe, ye = (self.expand(z, lets) for z in (c, xb, yb))
        inner = self.carry(facts, lets, {})
        vars0 = [v for v in free(("app", "_", (ce, xe, ye))) if v in scope]
        taken = set(scope)
        cv, ev = self.local("c", taken), self.local("e", taken | {"c"})
        taken |= {cv, ev}
        own_t = self.new_fact(ce, True, ev)
        own_f = Fact(own_t.id, ce, False, ev)
        names_in = {h.id: f"__h{h.id}__" for h in inner}
        inner_named = [Fact(h.id, h.cond, h.pol, names_in[h.id]) for h in inner]
        body_t, ut = self.prove(xe, inner_named + [own_t], {}, scope, where)
        body_f, uf = self.prove(ye, inner_named + [own_f], {}, scope, where)
        used = (ut | uf) - {own_t.id}
        hyps = [h for h in inner if h.id in used]
        vars_ = list(vars0)
        for h in hyps:
            for v in free(h.cond):
                if v in scope and v not in vars_:
                    vars_.append(v)
        hsig, hnames = self.hyp_params(hyps, taken)
        for fid, n in hnames.items():
            body_t, body_f = body_t.replace(names_in[fid], n), body_f.replace(names_in[fid], n)
        own_used = own_t.id in (ut | uf)
        sig = [f"{cv}: Bool"] + [f"+{v}: {self.qtype(scope[v])}" for v in vars_]
        if own_used:
            sig.append(f"{ev}: {{{self.r(ce)} == {cv} : Bool}}")
        sig += hsig
        self.out += [f"def {name}({', '.join(sig)}) -> {{{ALIAS}.ite(Bool, {cv}, {self.r(xe)}, {self.r(ye)}) == True{{}} : Bool}}:",
                     f"  match {cv}:", "    case True{}:", f"      {body_t}", "    case False{}:", f"      {body_f}", ""]
        args = [self.r(ce)] + vars_ + (["{==}"] if own_used else []) + [h.name for h in hyps]
        return f"{name}({', '.join(args)})", used

    def carry(self, facts: list, lets: dict, rename: dict) -> list:
        """The scope's facts as a callee sees them: lets that are not passed expanded, passed names renamed
        (caller name -> callee parameter). Names are the caller's (the caller supplies the proofs)."""
        keep = {k: v for k, v in lets.items() if k not in rename}
        ren = {k: ("id", v) for k, v in rename.items()}
        return [Fact(h.id, subst(self.expand(h.cond, keep), ren), h.pol, h.name) for h in facts]

    def call(self, t, facts, lets, scope, where) -> tuple[str, set]:
        """A call of a ghost definition: the callee's lemma (decision helpers and continuations carry facts)."""
        d = self.ghost[t[1]]
        args = list(t[2])
        if d.kind == "straight" and not d.name.startswith("gs_"):   # a definition ghost: for every argument
            lem = self.def_lemma(d)
            return f"{lem}({', '.join(self.r(a) for a in args)})", set()
        if d.kind not in ("decision", "straight"):
            raise NoProof(f"{where}: an unexpected call of {d.name}")
        if len(d.params) != len(args):
            raise NoProof(f"{where}: {d.name} called with {len(args)} arguments")
        rename = {}
        for (_, p, _), a in zip(d.params, args):
            if a[0] == "id" and (a[1] in scope or a[1] in lets):
                rename[a[1]] = p
        inner = self.carry(facts, lets, rename)
        own = None
        if d.kind == "decision":
            cond = self.carry([Fact(0, args[0], True, "")], lets, rename)[0].cond
            own = self.new_fact(cond, True, "")
        lem, used, extras, hyps = self.helper_lemma(d, inner, own, scope, where)
        call_args = [self.r(a) for a in args] + extras
        if own is not None and own.id in used:
            call_args.append("{==}")
        call_args += [h.name for h in hyps]
        return f"{lem}({', '.join(call_args)})", {h.id for h in hyps}

    def helper_lemma(self, d: Def, inner: list, own, caller_scope: dict, where: str):
        """The lemma of a decision helper or continuation, {M.<d>(params) == True{}}: (name, fact ids used (own
        included), extra parameters (caller variables a carried fact mentions), carried facts used)."""
        name = self.fresh("cg_" + d.name[len("gs_"):])
        scope = d.ptypes()
        taken = set(scope) | {v for v, _ in d.lets}
        ev = self.local("e", taken)
        taken.add(ev)
        names_in = {h.id: f"__h{h.id}__" for h in inner}
        local = [Fact(h.id, h.cond, h.pol, names_in[h.id]) for h in inner]
        if own is not None:
            local.append(Fact(own.id, own.cond, True, ev))   # guard order: the outer decisions first
        proof, used = self.prove(d.body, local, dict(d.lets), scope, d.name)
        own_used = own is not None and own.id in used
        hyps = [h for h in inner if h.id in used]
        extras: list[str] = []
        for h in ([own] if own_used else []) + hyps:
            for v in free(h.cond):
                if v in scope or v in extras or not self._is_var(v):
                    continue
                if v not in caller_scope:
                    raise NoProof(f"{where}: a fact mentions {v}, which is not in scope at {d.name}")
                extras.append(v)
        taken |= set(extras)
        hsig, hnames = self.hyp_params(hyps, taken)
        for fid, n in hnames.items():
            proof = proof.replace(names_in[fid], n)
        sig = [f"{'+' if mode == '+' else ''}{n}: {self.qtype(ty)}" for mode, n, ty in d.params]
        sig += [f"+{v}: {self.qtype(caller_scope[v])}" for v in extras]
        if own_used:
            sig.append(f"{ev}: {{{self.r(own.cond)} == {d.scrut} : Bool}}")
        sig += hsig
        ret = f"{{{ALIAS}.{d.name}({', '.join(n for _, n, _ in d.params)}) == True{{}} : Bool}}"
        lines = [f"def {name}({', '.join(sig)}) -> {ret}:"]
        body = [f"+{v} = {self.r(e)}" for v, e in d.lets] + [proof]
        if d.kind == "decision":
            lines += [f"  match {d.scrut}:", "    case False{}:", "      {==}", "    case True{}:"]
            lines += [f"      {x}" for x in body]
        else:
            lines += [f"  {x}" for x in body]
        self.out += lines + [""]
        return name, used, extras, hyps

    def _is_var(self, v: str) -> bool:
        return not (v in ("True{}", "False{}", "Bool", "Nat") or v.endswith("{}") or re.fullmatch(r"\d+n?|&\d+", v)
                    or v in self.types or v in self.ctors)

    def def_lemma(self, d: Def) -> str:
        """The lemma of a definition ghost gd_<x>_<f>: {M.gd(params) == True{}} for every argument."""
        if d.name in self.done_defs:
            return self.done_defs[d.name]
        name = self.fresh("cgd_" + d.name[len("gd_"):])
        self.done_defs[d.name] = name
        proof, _ = self.prove(d.body, [], dict(d.lets), d.ptypes(), d.name)
        sig = [f"{'+' if mode == '+' else ''}{n}: {self.qtype(ty)}" for mode, n, ty in d.params]
        ret = f"{{{ALIAS}.{d.name}({', '.join(n for _, n, _ in d.params)}) == True{{}} : Bool}}"
        self.out += [f"def {name}({', '.join(sig)}) -> {ret}:"] + [f"  +{v} = {self.r(e)}" for v, e in d.lets] \
            + [f"  {proof}", ""]
        return name

    def entry_lemma(self, d: Def) -> str:
        """The lemma of an entry point's chain head gs_<x>_<a>: match the state, the lets, the body."""
        name = self.fresh("cg_" + d.name[len("gs_"):])
        scope = {n: ty for _, n, ty in d.params}
        pm = re.match(r"^(\w+)\{(.*)\}$", d.pattern)
        st = scope.get(d.scrut)
        if not pm or pm.group(1) != st or st not in self.fields:
            raise NoProof(f"{d.name}: an unexpected state pattern {d.pattern}")
        ftypes = self.fields[st]
        for fld in pm.group(2).split(","):
            fn = fld.strip().lstrip("+")
            if fn not in ftypes:
                raise NoProof(f"{d.name}: the state has no field {fn}")
            scope[fn] = ftypes[fn]
        proof, _ = self.prove(d.body, [], dict(d.lets), scope, d.name)
        sig = [f"{'+' if mode == '+' else ''}{n}: {self.qtype(ty)}" for mode, n, ty in d.params]
        ret = f"{{{ALIAS}.{d.name}({', '.join(n for _, n, _ in d.params)}) == True{{}} : Bool}}"
        self.out += [f"def {name}({', '.join(sig)}) -> {ret}:", f"  match {d.scrut}:",
                     f"    case {self.qtype(d.pattern)}:"] + [f"      +{v} = {self.r(e)}" for v, e in d.lets] \
            + [f"      {proof}", ""]
        return name


def canary_proof(model_text: str, site_call: str, law_name: str, law_params: list[str], header: list[str], ref,
                 mode: str) -> tuple[str, list[str]]:
    """(PROOF.bend text, the obligations altered) of a G4 canary built by this generator: mode "drop" (the first
    obligation a core lemma discharges is closed by `{==}` instead) or "force" (obligations no passed condition implies
    are closed by `{==}`). NoProof when nothing would be altered."""
    text, _, _, g = _proof(model_text, site_call, law_name, law_params, header, ref, mode)
    if not g.altered:
        raise NoProof(f"canary mode {mode}: no obligation to alter")
    return text, g.altered


def proof(model_text: str, site_call: str, law_name: str, law_params: list[str], header: list[str], ref=None
          ) -> tuple[str, list[str], list[str]]:
    text, used, notes, _ = _proof(model_text, site_call, law_name, law_params, header, ref, None)
    return text, used, notes


def _proof(model_text: str, site_call: str, law_name: str, law_params: list[str], header: list[str], ref,
           mode: str | None):
    """(PROOF.bend text, core lemmas called, one note per discharged obligation) of a SORT-site law.

    site_call: the claim's left side as the emitter wrote it, `M.site_<x>(a, s[, tables])`; law_params: the law's
    binder names in order (the parameters of Laws.<law_name>); header: the import lines."""
    m = re.fullmatch(rf"{ALIAS}\.(site_\w+)\((.*)\)", site_call.strip())
    if not m:
        raise NoProof(f"the claim {site_call!r} is not a site term")
    g = Gen(model_text, m.group(1)[len("site_"):], ref, mode)
    top = g.ghost.get(m.group(1))
    if top is None or top.kind != "dispatch":
        raise NoProof(f"the model defines no ghost predicate {m.group(1)}")
    actual = [a.strip() for a in m.group(2).split(",")]
    formal = [n for _, n, _ in top.params]
    if len(actual) != len(formal) or not all(re.fullmatch(r"\w+", a) for a in actual):
        raise NoProof(f"the claim applies {m.group(1)} to {actual}, not to the law's binders")
    ren = dict(zip(formal, actual))
    act = ren[top.scrut]
    cases = []
    for pat, body in top.cases.items():
        if body == ("id", "True{}"):
            cases.append((pat, "{==}"))
            continue
        if body[0] != "app" or body[1] not in g.ghost or g.ghost[body[1]].kind != "state":
            raise NoProof(f"{m.group(1)}: case {pat} is neither True{{}} nor an entry point's chain")
        lem = g.entry_lemma(g.ghost[body[1]])
        args = [render(subst(a, {k: ("id", v) for k, v in ren.items()})) for a in body[2]]
        cases.append((pat, f"{lem}({', '.join(args)})"))
    if mode is None and not any(n != "core_and_intro" for n in g.used_lemmas):
        raise NoProof("no hit rests on a passed condition: nothing for a coercion guard to discharge")
    lines = list(header) + ["# class coercion_guard: the ghost chain of every entry point mirrored; at each hit ONE passed",
                            "# condition (zero or more Bool.and projections, then one comparison lemma of the imported core)",
                            "# implies the obligation; no reachability is assumed (every lemma holds for every state)."]
    lines += [f"#   {n}" for n in g.notes] + [""] + g.out
    lines += [f"def Laws.{law_name}({', '.join(law_params)}):", f"  match {act}:"]
    for pat, body in cases:
        lines += [f"    case {g.qtype(pat)}:", f"      {body}"]
    return "\n".join(lines) + "\n", g.used_lemmas, g.notes, g
