"""The proof class trace_bound (I65 = I33b, tests_m3/test_o12.py rule O2): linear bounds over the runs of a trace.

A law of this class has the binders `forall p: Trace` then zero or more `forall` Nat binders, no premise, and a claim
that is a conjunction of props {expr: E_i, from: run(p, s0), bind: ...} == true. Each E_i is a Bool combination (&&,
||, !) of Bool state fields and comparisons of linear Nat sums whose atoms are Nat literals, Nat state fields and
params, bound names, and Nat fields of a list element a target-library builtin of kind nth_default reads. A bind is a
Nat binder or a ghost term over (p, s0) (holon.gen.mlaws.Emitter.ghost_term); all of a law's ghost terms are one.

The class proves the conjunction as an inductive invariant of every run from s0:
  - the invariant I(st, g) is the claim's conjuncts over the statement's own ex_ helpers, a conjunct with a Nat
    binder quantified inside it (the binder may only index one list), the ghost's running sum g a parameter;
  - s0 by computation, a quantified binder split as far as the initial list it indexes;
  - one lemma per action over the result of its decision: generalised over the decision when the transport of the
    effects needs no value the decision carries, else down the action's decide chain one guard at a time, with the
    guard's lets inlined, so that on the Ok branch the carried values (a commit's payload) are known terms; a
    reverting step keeps the state and adds 0 to the ghost;
  - each conjunct carried through the action's effects: the Bool atoms its new and old forms read are split (Bend's
    match refines the hypotheses), each remaining comparison by the core library's Nat lemmas and this file's own
    (all proved here or in the core), lists by element predicates (snoc, take, drop, the target library's
    set_default builtins, and the builtins without a kind through the pointwise sidecar next to the target
    library, whose statements are proved here, never assumed); the ghost's share added on a successful step of its
    action;
  - induction on the trace, generalised over the start state and the ghost's running sum.
It searches no strengthening: the claim must be inductive as stated. A law of another shape, or a step it cannot
carry, gets no proof (None); Bend decides every proof it writes. Nothing here names a law, contract or target.
"""
from __future__ import annotations

import itertools
import json
import re
from pathlib import Path

from .machine import Machine, bname, bt, fresh
from .mlaws import ALIAS, EmittedM, q, qualify_model

NAT_CMP = {"<=": "le", "<": "lt"}
BOOL_OPS = ("&&", "||", "!")
CMP_OPS = ("<", "<=", ">", ">=", "==", "!=")


class Fail(Exception):
    """The class cannot carry this law (internal; trace_bound returns None)."""


def _key(e) -> str:
    return json.dumps(e, sort_keys=True)


def _occurs(e, sub) -> bool:
    if _key(e) == _key(sub):
        return True
    if isinstance(e, list):
        return any(_occurs(x, sub) for x in (e[2:] if e and e[0] == "call" else e[1:]) if not isinstance(x, dict)) \
            or any(_occurs(v, sub) for x in e[1:] if isinstance(x, dict) for v in x.values())
    return False


def _replace(e, sub, by):
    """e with every occurrence of the subexpression sub replaced by `by`."""
    if _key(e) == _key(sub):
        return by
    if isinstance(e, list) and e:
        if e[0] == "call":
            return ["call", e[1]] + [_replace(x, sub, by) for x in e[2:]]
        if e[0] == "get":
            return ["get", _replace(e[1], sub, by), e[2]]
        if e[0] == "mk":
            return ["mk", e[1], {k: _replace(v, sub, by) for k, v in e[2].items()}]
        if e[0] == "with":
            return ["with", e[1], _replace(e[2], sub, by), {k: _replace(v, sub, by) for k, v in e[3].items()}]
        return [e[0]] + [_replace(x, sub, by) for x in e[1:]]
    return e


def _subst(e, sub: dict):
    """Variables in `sub` replaced (function, field and type names untouched)."""
    if isinstance(e, str):
        return sub.get(e, e)
    if not isinstance(e, list) or not e:
        return e
    if e[0] == "call":
        return ["call", e[1]] + [_subst(x, sub) for x in e[2:]]
    if e[0] == "get":
        return ["get", _subst(e[1], sub), e[2]]
    if e[0] == "mk":
        return ["mk", e[1], {k: _subst(v, sub) for k, v in e[2].items()}]
    if e[0] == "with":
        return ["with", e[1], _subst(e[2], sub), {k: _subst(v, sub) for k, v in e[3].items()}]
    return [e[0]] + [_subst(x, sub) for x in e[1:]]


def _inline(e, lets: dict):
    """Let names replaced by their (inlined) expressions, inside records too."""
    if isinstance(e, str):
        return _inline(lets[e], lets) if e in lets else e
    if not isinstance(e, list) or not e:
        return e
    if e[0] == "call":
        return ["call", e[1]] + [_inline(x, lets) for x in e[2:]]
    if e[0] == "get":
        return ["get", _inline(e[1], lets), e[2]]
    if e[0] == "mk":
        return ["mk", e[1], {k: _inline(v, lets) for k, v in e[2].items()}]
    if e[0] == "with":
        return ["with", e[1], _inline(e[2], lets), {k: _inline(v, lets) for k, v in e[3].items()}]
    return [e[0]] + [_inline(x, lets) for x in e[1:]]


def _split_top(s: str) -> list[str]:
    """Split a Bend argument list at its top-level commas."""
    out, depth, cur = [], 0, []
    for ch in s:
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        out.append("".join(cur).strip())
    return out


def _split_params(s: str) -> list[str]:
    """Split a Bend parameter list at its top-level commas (generic brackets <..> nest too)."""
    out, depth, cur = [], 0, []
    for ch in s:
        if ch in "({[<":
            depth += 1
        elif ch in ")}]>" and not (ch == ">" and cur and cur[-1] == "-"):
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        out.append("".join(cur).strip())
    return out


def _call_args(s: str, start: int) -> tuple[list[str], int]:
    """The arguments of the call whose opening parenthesis is at s[start], and the index after its close."""
    depth = 0
    for i in range(start, len(s)):
        if s[i] in "({[":
            depth += 1
        elif s[i] in ")}]":
            depth -= 1
            if depth == 0:
                return _split_top(s[start + 1:i]), i + 1
    raise Fail("unbalanced call")


class _Conj:
    def __init__(self, i: int, expr, binds: dict, helper: str, ghost_names: set, nat_names: set):
        self.i, self.expr, self.binds, self.helper = i, expr, binds, helper
        self.order = sorted(binds)                       # the ex_ helper's parameters after the state
        self.ghost = sorted(n for n in binds if n in ghost_names)
        self.kvars = sorted(n for n in binds if n in nat_names)


class TraceBound:
    """One law's proof (render() is the PROOF.bend text)."""

    def __init__(self, em: EmittedM, m: Machine, model_import: str, law: dict, pointwise: dict):
        self.em, self.m, self.imp, self.law, self.pw = em, m, model_import, law, pointwise
        self.lines: list[str] = []
        self.n = 0
        self.emitted: set[str] = set()
        self.parse()

    # ------------------------------------------------------------ the statement
    def parse(self):
        em, m = self.em, self.m
        if em.assume or not em.binders or em.binders[0][0] != "forall" or em.binders[0][2] != "Trace":
            raise Fail("binders: forall p: Trace first, no premise")
        nat = [n for qq, n, t in em.binders[1:] if qq == "forall" and t == "Nat"]
        if len(nat) != len(em.binders) - 1:
            raise Fail("binders after the trace: forall Nat only")
        if m.threaded:
            raise Fail("a model that threads oracle tables")
        self.p = em.binders[0][1]
        st = self.law["statement"]
        c = st["claim"]
        props = c["all"] if "all" in c else [c]
        if len(props) != len(em.claims):
            raise Fail("claim and emitted conjuncts differ")
        fields = set(m.stypes)
        taken = {bname(x) for x in fields} | {bname(n) for a in m.actions for n, _ in a["inputs"]} \
            | {bname(g["let"]) for a in m.actions for g in a["guards"] if "let" in g} | {bname(x) for x in m.params}
        self.taken = set(taken)
        ghosts, self.conj = [], []
        run_from = {"run": {"var": self.p}, "from": {"s0": {}}}
        for i, (pr, (lhs, rhs, ty)) in enumerate(zip(props, em.claims)):
            if set(pr) != {"eq"} or pr["eq"][1] != {"bool": True} or ty != "Bool" or rhs != "True{}":
                raise Fail("a conjunct is not {expr ..} == true")
            t = pr["eq"][0]
            if set(t) - {"expr", "from", "bind"} or t.get("from") != run_from:
                raise Fail("a conjunct is not an expr term over run(p, s0)")
            binds = t.get("bind") or {}
            gn, nn = set(), set()
            for name, b in binds.items():
                if isinstance(b, dict) and "ghost" in b:
                    if b.get("over") != {"var": self.p} or b.get("from") != {"s0": {}}:
                        raise Fail("a ghost term not over (p, s0)")
                    ghosts.append(b)
                    gn.add(name)
                elif b == {"var": b.get("var")} and b.get("var") in nat:
                    if b["var"] != name:
                        raise Fail("a Nat binder bound under another name")
                    nn.add(name)
                else:
                    raise Fail(f"bind {name}: not a Nat binder or a ghost term")
                if bname(name) in taken:
                    raise Fail(f"bind {name} shadows a model name")
            mh = re.fullmatch(r"(ex_[0-9a-f]{12})\(" + re.escape(f"{ALIAS}.run({bname(self.p)}, {ALIAS}.s0())") + r"(.*)\)",
                              lhs)
            if not mh:
                raise Fail("an emitted conjunct is not an ex_ helper over run(p, s0)")
            self.conj.append(_Conj(i, t["expr"], binds, mh.group(1), gn, nn))
        keys = {_key(g) for g in ghosts}
        if len(keys) > 1:
            raise Fail("more than one ghost term")
        self.ghost = ghosts[0] if ghosts else None
        if self.ghost is not None:
            self.gact = next((a for a in m.actions if a["name"] == self.ghost["ghost"]), None)
            if self.gact is None:
                raise Fail("the ghost names no action")
            gh = re.search(r"\b(gh_[0-9a-f]{12})\(" + re.escape(bname(self.p)), "\n".join(x[0] for x in em.claims))
            if not gh:
                raise Fail("no ghost helper in the statement")
            self.gh = gh.group(1)
            self.gh1 = "gh1_" + self.gh[3:]
        else:
            self.gact, self.gh, self.gh1 = None, None, None
        self.G = fresh("gs", taken)                  # the ghost's running sum
        taken.add(self.G)
        for c in self.conj:   # one canonical ghost variable in every conjunct
            c.expr = _subst(c.expr, {n: self.G for n in c.ghost})
            if len(c.kvars) > 1:
                raise Fail("more than one Nat binder in a conjunct")
            if c.kvars:
                c.read = self.index_read(c.expr, c.kvars[0])
        self.hname = [("f" if c.kvars else "h") + str(c.i) for c in self.conj]
        self.taken |= set(self.hname) | {self.G}

    def index_read(self, e, k: str):
        """(nth builtin, list field): the one list a Nat binder indexes, every occurrence of it being that read."""
        reads = set()

        def walk(x, under_read: bool):
            if isinstance(x, str):
                if x == k and not under_read:
                    raise Fail(f"{k} used other than as an index")
                return
            if not isinstance(x, list) or not x:
                return
            if x[0] == "call" and len(x) == 4 and x[3] == k and self.m.lib.kind(x[1]) == "nth_default" \
                    and isinstance(x[2], str) and x[2] in self.m.stypes:
                reads.add((x[1], x[2]))
                return
            for y in (x[2:] if x[0] == "call" else x[1:]):
                if isinstance(y, dict):
                    for v in y.values():
                        walk(v, False)
                else:
                    walk(y, False)
        walk(e, False)
        if len(reads) != 1:
            raise Fail(f"{k} indexes {len(reads)} lists")
        return next(iter(reads))

    # ------------------------------------------------------------ rendering
    def env_base(self) -> dict:
        env = dict(self.m.stypes)
        env[self.G] = "Nat"
        for c in self.conj:
            for k in c.kvars:
                env[k] = "Nat"
        return env

    def r(self, e, env: dict) -> str:
        return qualify_model(self.m, self.m.ex(e, env)[0])

    def ty(self, t: str) -> str:
        return q(bt(t))

    def fresh_name(self, base: str) -> str:
        v = fresh(base, self.taken)
        self.taken.add(v)
        return v

    def helper(self, base: str) -> str:
        self.n += 1
        return f"tb_{base}{self.n}"

    def empty_of(self, T: str) -> str:
        """The default element of record type T: the default of an nth_default builtin over T's lists."""
        for b, spec in sorted(self.m.lib.builtins.items()):
            if spec.get("kind") == "nth_default" and spec.get("type") == T and spec.get("default"):
                return self.r(["call", spec["default"]], {})
        raise Fail(f"no default element of {T}")

    # ------------------------------------------------------------ the invariant
    def comp_type(self, c: _Conj, st: str, g: str) -> str:
        args = []
        for n in c.order:
            args.append(g if n in c.ghost else bname(n))
        body = f"{{Laws.{c.helper}({st}{''.join(', ' + a for a in args)}) == True{{}} : Bool}}"
        if c.kvars:
            return f"@{bname(c.kvars[0])}:Nat -> {body}"
        return body

    def tuple_type(self, parts: list[str]) -> str:
        out = parts[-1]
        for p in reversed(parts[:-1]):
            out = f"({p}) & ({out})"
        return out

    def tuple_val(self, parts: list[str]) -> str:
        out = parts[-1]
        for p in reversed(parts[:-1]):
            out = f"({p}, {out})"
        return out

    def tuple_pat(self, names: list[str]) -> str:
        return self.tuple_val(names)

    # ------------------------------------------------------------ the whole file
    def render(self) -> str:
        m, A = self.m, ALIAS
        L = self.lines
        L += ["# class trace_bound: the claim as an inductive invariant of every run from s0, the ghost's running sum",
              "# a parameter; one lemma per action over its decision; induction on the trace", ""]
        L += LIBRARY
        self.pointwise_lemmas()
        fields = [bname(n) for n, _ in m.state]
        self.FA = ", ".join(fields)
        self.FP = ", ".join(f"+{bname(n)}: {self.ty(t)}" for n, t in m.state)
        st = f"{A}.HSt{{{self.FA}}}"
        # the invariant
        sv, gv = self.fresh_name("st"), self.G
        L += [f"def tb_I(+{sv}: {A}.HSt, +{gv}: Nat) -> Type:",
              f"  {self.tuple_type([self.comp_type(c, sv, gv) for c in self.conj])}", ""]
        self.base()
        # one lemma per action
        steps = {}
        for a in m.actions:
            steps[a["name"]] = self.action(a)
        # the step lemma: the ghost's share added (a law with no ghost carries g unchanged)
        av, s1, hv = self.fresh_name("a"), self.fresh_name("s"), self.fresh_name("inv")
        g_after = (lambda a_, s_: f"Nat.add({gv}, Laws.{self.gh1}({a_}, {s_}))") if self.ghost else (lambda a_, s_: gv)
        L += [f"def tb_step(+{av}: {A}.HAct, +{s1}: {A}.HSt, +{gv}: Nat, {hv}: tb_I({s1}, {gv})) -> "
              f"tb_I({A}.step({av}, {s1}), {g_after(av, s1)}):",
              f"  match {av} {s1}:"]
        for a in m.actions:
            an = a["name"]
            ins = [bname(n) for n, _ in a["inputs"]]
            act = f"{A}.A_{an}{{{', '.join(ins)}}}"
            L.append(f"    case {A}.A_{an}{{{', '.join('+' + i for i in ins)}}} {A}.HSt{{{', '.join('+' + f for f in fields)}}}:")
            L.append(f"      {self.tuple_pat(self.hname)} = {hv}")
            if self.ghost is not None and a is not self.gact:
                L.append(f"      %Equal.sym(Nat, Nat.add({gv}, 0n), {gv}, tb_add_zero({gv})) : "
                         f"tb_I({A}.step({act}, {A}.HSt{{{self.FA}}}), _)")
            L.append(f"      {steps[an]}")
        L.append("")
        # induction on the trace, generalised over the start state and the ghost's running sum
        pv, rv, av2 = self.fresh_name("tr"), self.fresh_name("rest"), self.fresh_name("b")
        if self.ghost:
            gsum = lambda tr, s_: f"Laws.{self.gh}({tr}, {s_})"   # noqa: E731
            L += [f"def tb_run({pv}: List<&2, {A}.HAct>, +{s1}: {A}.HSt, +{gv}: Nat, {hv}: tb_I({s1}, {gv})) -> "
                  f"tb_I({A}.run({pv}, {s1}), Nat.add({gv}, {gsum(pv, s1)})):",
                  f"  match {pv}:", "    case Nil{}:",
                  f"      %Equal.sym(Nat, Nat.add({gv}, 0n), {gv}, tb_add_zero({gv})) : tb_I({s1}, _)", f"      {hv}",
                  f"    case Con{{+{av2}, +{rv}}}:",
                  f"      %tb_add_assoc({gv}, Laws.{self.gh1}({av2}, {s1}), {gsum(rv, f'{A}.step({av2}, {s1})')}) : "
                  f"tb_I({A}.run({rv}, {A}.step({av2}, {s1})), _)",
                  f"      tb_run({rv}, {A}.step({av2}, {s1}), Nat.add({gv}, Laws.{self.gh1}({av2}, {s1})), "
                  f"tb_step({av2}, {s1}, {gv}, {hv}))", ""]
            g_end = gsum(bname(self.p), f"{A}.s0()")
        else:
            L += [f"def tb_run({pv}: List<&2, {A}.HAct>, +{s1}: {A}.HSt, +{gv}: Nat, {hv}: tb_I({s1}, {gv})) -> "
                  f"tb_I({A}.run({pv}, {s1}), {gv}):",
                  f"  match {pv}:", "    case Nil{}:", f"      {hv}", f"    case Con{{+{av2}, +{rv}}}:",
                  f"      tb_run({rv}, {A}.step({av2}, {s1}), {gv}, tb_step({av2}, {s1}, {gv}, {hv}))", ""]
            g_end = "0n"
        # the law: the conjuncts out of the invariant at the binders
        kv = [bname(n) for _, n, _ in self.em.binders[1:]]
        sst = self.fresh_name("sf")
        outs = []
        for c in self.conj:
            args = [self.G if n in c.ghost else bname(n) for n in c.order]
            outs.append(f"{{Laws.{c.helper}({sst}{''.join(', ' + x for x in args)}) == True{{}} : Bool}}")
        L += [f"def tb_out(-{sst}: {A}.HSt, -{gv}: Nat{''.join(f', +{k}: Nat' for k in kv)}, {hv}: tb_I({sst}, {gv})) -> "
              f"{self.tuple_type(outs)}:",
              f"  {self.tuple_pat(self.hname)} = {hv}",
              f"  {self.tuple_val([(f'{h}({bname(c.kvars[0])})' if c.kvars else h) for c, h in zip(self.conj, self.hname)])}",
              ""]
        L += [f"def Laws.{self.em.name}({', '.join([bname(self.p)] + kv)}):",
              f"  tb_out({A}.run({bname(self.p)}, {A}.s0()), {g_end}{''.join(', ' + k for k in kv)}, "
              f"tb_run({bname(self.p)}, {A}.s0(), 0n, tb_base()))"]
        head = ["# GENERATED by holon.gen.mproofs; untrusted, accepted only if Bend checks it.", "import Base",
                f"import {self.imp} as {A}"]
        base = self.imp.rsplit("/model/", 1)[0]
        head += [f"import {base}/core/PROOF.bend as CP", f"import {base}/core/LAWS.bend as C", "import ./LAWS.bend as Laws", ""]
        return "\n".join(head + L) + "\n"

    # ------------------------------------------------------------ s0
    def base(self):
        m, A, L = self.m, ALIAS, self.lines
        parts = []
        for c in self.conj:
            if not c.kvars:
                parts.append("{==}")
                continue
            k = bname(c.kvars[0])
            nth, xs = c.read
            init = (m.f.get("initial") or {}).get(xs)
            depth = len(init) if isinstance(init, list) else 0
            name = self.helper("base")
            args = [("0n" if n in c.ghost else bname(n)) for n in c.order]
            L.append(f"def {name}({k}: Nat) -> {{Laws.{c.helper}({A}.s0(){''.join(', ' + x for x in args)}) == True{{}} : Bool}}:")
            body, ind, cur = [], 2, k
            for d in range(depth):
                nxt = f"{k}{d + 1}"
                body += [" " * ind + f"match {cur}:", " " * (ind + 2) + "case 0n:", " " * (ind + 4) + "{==}",
                         " " * (ind + 2) + f"case 1n+{nxt}:"]
                ind += 4
                cur = nxt
            body.append(" " * ind + "{==}")
            L += body + [""]
            parts.append(f"{k} => {name}({k})")
        L += ["def tb_base() -> tb_I(" + f"{A}.s0(), 0n):", f"  {self.tuple_val(parts)}", ""]

    # ------------------------------------------------------------ actions
    def action(self, a: dict) -> str:
        """The proof text of tb_step's case for action a (its decision lemma applied), emitting the lemmas."""
        an, A = a["name"], ALIAS
        ins = [bname(n) for n, _ in a["inputs"]]
        reads = [bname(r) for r in self.m.reads[an]]
        carried = _carried(self.m, a)
        try:
            mark = len(self.lines)
            name = self.decision_lemma(a, inline=False)
            return f"{name}({A}.decide_{an}({', '.join(reads + ins)}), {self.FA}{''.join(', ' + i for i in ins)}, " \
                   f"{self.G}, {', '.join(self.hname)})"
        except Fail:
            del self.lines[mark:]
            if not carried or a["name"] not in self.m.chains or self.m.chains[a["name"]]["top"] is None:
                raise
        top = self.m.chains[an]["top"]
        first = self.chain_lemmas(a)
        lets = {g["let"]: g["expr"] for g in a["guards"] if "let" in g}
        env = {**self.m.stypes, **dict(a["inputs"])}
        cond = self.r(_inline(top["cond_expr"], lets), env)
        return f"{first}({cond}, {self.FA}{''.join(', ' + i for i in ins)}, {self.G}, {', '.join(self.hname)}, {{==}})"

    def hyp_params(self) -> str:
        out = []
        st = f"{ALIAS}.HSt{{{self.FA}}}"
        for c, h in zip(self.conj, self.hname):
            t = self.comp_type(c, st, self.G)
            out.append(f"{h}: {t}" if c.kvars else f"+{h}: {t}")
        return ", ".join(out)

    def gnew(self, a: dict, exec_term: str) -> str:
        if self.ghost is None or a is not self.gact:
            return self.G
        ins = [bname(n) for n, _ in a["inputs"]]
        e = self.r(self.ghost["add"], {**self.m.stypes, **dict(a["inputs"])})
        return f"Nat.add({self.G}, {ALIAS}.ite(Nat, {ALIAS}.last_ok({exec_term}), {e}, 0n))"

    def rev_value(self, a: dict, exec_term: str) -> list[str]:
        val = self.tuple_val(self.hname)
        if self.ghost is None or a is not self.gact:
            return [val]
        return [f"%Equal.sym(Nat, Nat.add({self.G}, 0n), {self.G}, tb_add_zero({self.G})) : tb_I({exec_term}, _)", val]

    def decision_lemma(self, a: dict, inline: bool) -> str:
        """tb_x_<a>: the invariant after exec_<a>, generalised over the decision."""
        an, A = a["name"], ALIAS
        ins = [(bname(n), t) for n, t in a["inputs"]]
        IP = "".join(f", +{n}: {self.ty(t)}" for n, t in ins)
        IA = "".join(", " + n for n, _ in ins)
        d = self.fresh_name("d")
        ex = lambda dd: f"{A}.exec_{an}({dd}, {self.FA}{IA})"   # noqa: E731
        name = f"tb_x_{an}"
        carried = _carried(self.m, a)
        lt = _let_types(self.m, a)
        okpat = f"{A}.D_{an}_Ok{{{', '.join('+' + bname(c) for c in carried)}}}"
        code = self.fresh_name("code")
        env = {**self.m.stypes, **dict(a["inputs"]), **{c: lt[c] for c in carried}}
        ok = self.ok_proof(a, dict(a["effects"]), env)
        head = [f"def {name}({d}: {A}.Dec_{an}, {self.FP}{IP}, +{self.G}: Nat, {self.hyp_params()}) -> "
                f"tb_I({ex(d)}, {self.gnew(a, ex(d))}):",
                f"  match {d}:", f"    case {A}.D_{an}_Rev{{{code}}}:"]
        head += ["      " + x for x in self.rev_value(a, ex(f'{A}.D_{an}_Rev{{{code}}}'))]
        head += [f"    case {okpat}:"] + ["      " + x for x in ok] + [""]
        self.lines += head
        return name

    def chain_lemmas(self, a: dict) -> str:
        """tb_w_<a>_<i>: the invariant down the decide chain of <a>, its lets inlined, each guard's equation kept (Bend's
        convoy: node i takes {C_i == c} and matches c, which refines it to {C_i == True} on the way on, and passes the
        equations of the guards before it). On the Ok branch every guard's equation is a fact the transport may use.
        Returns the first lemma."""
        an, A, m = a["name"], ALIAS, self.m
        info = m.chains[an]
        lets = {g["let"]: g["expr"] for g in a["guards"] if "let" in g}
        env = {**m.stypes, **dict(a["inputs"])}
        ins = [(bname(n), t) for n, t in a["inputs"]]
        IP = "".join(f", +{n}: {self.ty(t)}" for n, t in ins)
        IA = "".join(", " + n for n, _ in ins)
        effects = {f: _inline(e, lets) for f, e in a["effects"].items()}
        path, conds, rec = [], [], info["top"]
        while rec is not None:
            path.append(rec["call"])
            conds.append(_inline(rec["cond_expr"], lets))
            rec = info["helpers"][rec["call"]]["next"]
        c = self.fresh_name("c")   # each lemma's own scrutinee (the names are local to each lemma)
        qs = [self.fresh_name(f"q{i}") for i in range(len(path))]
        guards = list(zip(conds, qs))
        ok = self.ok_proof(a, effects, env, guards)
        names = [f"tb_w_{an}_{i}" for i in range(len(path))]
        blocks = []
        for i, hname in enumerate(path):
            h = info["helpers"][hname]
            args = [self.r(_inline(v, lets), env) for v, _ in h["params"]]
            dec = f"{A}.{hname}({', '.join([c] + args)})"
            ex = f"{A}.exec_{an}({dec}, {self.FA}{IA})"
            code_rev = f"{A}.exec_{an}({A}.{hname}(False{{}}{''.join(', ' + x for x in args)}), {self.FA}{IA})"
            qp = "".join(f", +{q}: {{{self.r(cj, env)} == True{{}} : Bool}}" for cj, q in guards[:i])
            qp += f", +{qs[i]}: {{{self.r(conds[i], env)} == {c} : Bool}}"
            lines = [f"def {names[i]}({c}: Bool, {self.FP}{IP}, +{self.G}: Nat, {self.hyp_params()}{qp}) -> "
                     f"tb_I({ex}, {self.gnew(a, ex)}):",
                     f"  match {c}:", "    case False{}:"]
            lines += ["      " + x for x in self.rev_value(a, code_rev)]
            lines.append("    case True{}:")
            nxt = h["next"]
            if nxt is not None:
                cond = self.r(conds[i + 1], env)
                lines.append(f"      {names[i + 1]}({cond}, {self.FA}{IA}, {self.G}, {', '.join(self.hname)}, "
                             f"{', '.join(qs[:i + 1])}, {{==}})")
            else:
                lines += ["      " + x for x in ok]
            blocks.append(lines + [""])
        for b in reversed(blocks):   # callees first
            self.lines += b
        return names[0]

    # ------------------------------------------------------------ the Ok branch: each conjunct carried
    def ok_proof(self, a: dict, effects: dict, env: dict, guards: list | None = None) -> list[str]:
        ghost_act = self.ghost is not None and a is self.gact
        delta = self.ghost["add"] if ghost_act else None
        parts = []
        for c, h in zip(self.conj, self.hname):
            parts.append(_Carry(self, a, effects, env, delta, guards or []).component(c, h))
        return [self.tuple_val(parts)]

    # ------------------------------------------------------------ the pointwise sidecar, proved here
    def pointwise_lemmas(self):
        self.pwinfo = {}
        for b, spec in sorted(self.pw.items()):
            try:
                self.pwinfo[b] = _GoFn(self, b, spec)
            except Fail:
                continue


class _GoFn:
    """A kindless builtin b(xs, args..) = go(xs, acc0, args..) of the target library's prelude, whose head element
    is ite(T, cond, new, old) (the pointwise sidecar's shape), and the lemmas proving its sidecar statements."""

    def __init__(self, tb: TraceBound, name: str, spec: dict):
        self.tb, self.name, self.spec = tb, name, spec
        m = tb.m
        b = m.lib.builtins.get(name)
        if not b or b.get("kind") is not None:
            raise Fail(f"{name} is not a kindless builtin")
        text = "\n".join(list(m.lib.prelude) + [blk["bend"] for blk in m.lib.record_blocks if "bend" in blk])
        go = spec["go"]
        fn = b["bend"].split("(", 1)[0]   # the builtin's Bend function, from its template
        top = re.search(rf"^def {re.escape(fn)}\((.*)\) -> .*:\n  {re.escape(go)}\((.*)\)$", text, re.M)
        mdef = re.search(rf"^def {re.escape(go)}\((.*)\) -> List<&2, H(\w+)>:\n((?:  .*\n?)+)", text, re.M)
        if not top or not mdef:
            raise Fail(f"{go}: not found in the prelude")
        self.elem = mdef.group(2)
        if self.elem != spec["elem"]:
            raise Fail(f"{go}: element type {self.elem}")
        self.params = _split_params(mdef.group(1))   # "es: List<&2, HEntry>", "+pos: Nat", ..
        self.pnames = [x.split(":")[0].lstrip("+-").strip() for x in self.params]
        body = mdef.group(3)
        mcon = re.search(r"case Con\{(\w+), (\w+)\}:\n((?:      .*\n?)+)", body)
        if not mcon:
            raise Fail(f"{go}: no Con case")
        self.e, self.t = mcon.group(1), mcon.group(2)
        rest = mcon.group(3)
        mrec = re.search(rf"match {self.e}:\n\s+case H{self.elem}\{{(.*)\}}:\n\s+(Con\{{.*\}})", rest)
        self.fieldpat = None
        if mrec:
            self.fieldpat = [x.strip().lstrip("+") for x in _split_top(mrec.group(1))]
            con = mrec.group(2)
        else:
            mc = re.search(r"(Con\{.*\})", rest)
            if not mc:
                raise Fail(f"{go}: no Con result")
            con = mc.group(1)
        parts = _split_top(con[4:-1])
        if len(parts) != 2 or not parts[0].startswith(f"ite(H{self.elem}, ") or not parts[1].startswith(f"{go}("):
            raise Fail(f"{go}: the head is not ite(..)")
        ite_args, _ = _call_args(parts[0], 3)
        if len(ite_args) != 4:
            raise Fail(f"{go}: ite arity")
        self.cond, self.new, self.old = ite_args[1], ite_args[2], ite_args[3]
        self.rec, _ = _call_args(parts[1], len(go))
        top_params = _split_params(top.group(1))
        self.top_args = _split_top(top.group(2))
        self.top_pnames = [x.split(":")[0].lstrip("+-").strip() for x in top_params]
        self.go = go
        tb.lines += self.lemmas()

    # the go call over the builtin's own arguments (as written by the facts' call)
    def go_args(self, args: list[str]) -> list[str]:
        sub = dict(zip(self.top_pnames, args))
        return [sub.get(x, x) for x in self.top_args]

    def qual(self, s: str) -> str:
        return qualify_model(self.tb.m, s)

    def lemmas(self) -> list[str]:
        A, tb, T = ALIAS, self.tb, self.elem
        out = [f"# pointwise sidecar of {self.name} ({self.go}): proved by induction on the list, never assumed"]
        rtypes = dict(tb.m.types[T])
        fnames = [f for f, _ in tb.m.types[T]]
        empty = self.tb.empty_of(T)
        params = ", ".join([f"{self.pnames[0]}: List<&2, {A}.H{T}>"]
                           + [self.qual(x if x.lstrip().startswith("+") else "+" + x.strip()) for x in self.params[1:]])
        names = self.pnames
        goc = lambda xs, rest: f"{A}.{self.go}({', '.join([xs] + rest)})"   # noqa: E731
        rec_args = [self.qual(x) for x in self.rec[1:]]
        nth = lambda xs, k: f"{A}.nth_d({A}.H{T}, {xs}, {k}, {empty})"   # noqa: E731
        kind = self.spec.get("else")
        if self.fieldpat is not None:
            new_f = dict(zip(fnames, _split_top(self.new[self.new.index("{") + 1:-1])))
            old_f = dict(zip(fnames, _split_top(self.old[self.old.index("{") + 1:-1])))
        else:
            new_f = old_f = None
        self.stmts = {}
        for f, how in sorted((self.spec.get("fields") or {}).items()):
            if "le_add" not in how or rtypes.get(f) != "Nat" or new_f is None:
                raise Fail(f"{self.name}.{f}: unsupported statement")
            wname = self.top_pnames[how["le_add"]]
            if wname not in self.top_args:
                raise Fail(f"{self.name}: le_add argument not passed to {self.go}")
            wgo = self.pnames[self.top_args.index(wname)]   # the go function's own parameter at that position
            k = "k"
            get = lambda xs, fl=f: f"{A}.g_{T}_{fl}({nth(xs, k)})"   # noqa: E731
            nm = f"tb_pw_{self.name}_le_{f}"
            hd = nm + "_hd"
            fv = [x for x in self.fieldpat]
            fpos = fnames.index(f)
            nv, ov = new_f[f].strip(), old_f[f].strip()
            fvar = fv[fpos]
            def leaf(val: str) -> str:
                if val == f"Nat.add({fvar}, {wgo})":
                    return f"C.core_le_refl(Nat.add({fvar}, {wgo}))"
                if val == fvar:
                    return f"C.core_le_add_self({fvar}, {wgo})"
                raise Fail(f"{self.name}.{f}: element value {val}")
            cv = tb.fresh_name("c")
            hparams = ", ".join([f"{cv}: Bool"] + [f"+{x}: {self.qual(bt(rtypes[fn]))}" for x, fn in zip(fv, fnames)]
                                + [self.qual(x if x.strip().startswith("+") else "+" + x.strip()) for x in self.params[1:]])
            out += [f"def {hd}({hparams}) -> {{Nat.is_le({A}.g_{T}_{f}({A}.ite({A}.H{T}, {cv}, {self.qual(self.new)}, "
                    f"{self.qual(self.old)})), Nat.add({fvar}, {wgo})) == True{{}} : Bool}}:",
                    f"  match {cv}:", "    case True{}:", f"      {leaf(nv)}", "    case False{}:", f"      {leaf(ov)}", ""]
            out += [f"def {nm}({params}, {k}: Nat) -> {{Nat.is_le({get(goc(names[0], names[1:]))}, "
                    f"Nat.add({get(names[0])}, {wgo})) == True{{}} : Bool}}:",
                    f"  match {names[0]}:", "    case Nil{}:", f"      C.core_le_zero({wgo})",
                    f"    case Con{{{self.e}, {self.t}}}:", f"      match {self.e}:",
                    f"        case {A}.H{T}{{{', '.join('+' + x for x in fv)}}}:",
                    f"          match {k}:", "            case 0n:",
                    f"              {hd}({self.qual(self.cond)}, {', '.join(fv)}, {', '.join(names[1:])})",
                    f"            case 1n+{k}q:",
                    f"              {nm}({self.t}, {', '.join(rec_args)}, {k}q)", ""]
            self.stmts[("le", f)] = (nm, wname)
        if kind == "eq":
            if new_f is None:
                raise Fail(f"{self.name}: eq needs a record match")
            fv = list(self.fieldpat)
            for f, ty in tb.m.types[T]:
                if f in (self.spec.get("fields") or {}) or ty != "Nat":
                    continue
                if new_f[f].strip() != fv[fnames.index(f)] or old_f[f].strip() != fv[fnames.index(f)]:
                    continue
                k = "k"
                nm = f"tb_pw_{self.name}_eq_{f}"
                hd = nm + "_hd"
                cv = tb.fresh_name("c")
                hparams = ", ".join([f"{cv}: Bool"] + [f"+{x}: {self.qual(bt(rtypes[fn]))}" for x, fn in zip(fv, fnames)]
                                    + [self.qual(x if x.strip().startswith("+") else "+" + x.strip()) for x in self.params[1:]])
                out += [f"def {hd}({hparams}) -> {{{A}.g_{T}_{f}({A}.ite({A}.H{T}, {cv}, {self.qual(self.new)}, "
                        f"{self.qual(self.old)})) == {fv[fnames.index(f)]} : Nat}}:",
                        f"  match {cv}:", "    case True{}:", "      {==}", "    case False{}:", "      {==}", ""]
                get = lambda xs, fl=f: f"{A}.g_{T}_{fl}({nth(xs, k)})"   # noqa: E731
                out += [f"def {nm}({params}, {k}: Nat) -> {{{get(goc(names[0], names[1:]))} == {get(names[0])} : Nat}}:",
                        f"  match {names[0]}:", "    case Nil{}:", "      {==}",
                        f"    case Con{{{self.e}, {self.t}}}:", f"      match {self.e}:",
                        f"        case {A}.H{T}{{{', '.join('+' + x for x in fv)}}}:",
                        f"          match {k}:", "            case 0n:",
                        f"              {hd}({self.qual(self.cond)}, {', '.join(fv)}, {', '.join(names[1:])})",
                        f"            case 1n+{k}q:",
                        f"              {nm}({self.t}, {', '.join(rec_args)}, {k}q)", ""]
                self.stmts[("eq", f)] = nm
        elif kind == "eq_or_default":
            if self.fieldpat is not None:
                raise Fail(f"{self.name}: eq_or_default over a record match")
            if self.qual(self.new) != empty and self.qual(self.old) != empty:
                raise Fail(f"{self.name}: neither branch is the default")
            nm = f"tb_pw_{self.name}_at"
            pv, hk, hdv, k = "P", "hk", "hdf", "k"
            new_is_empty = self.qual(self.new) == empty
            keep = self.old if new_is_empty else self.new
            if keep != self.e:
                raise Fail(f"{self.name}: the kept branch is not the element")
            ha, hb = (hdv, hk) if new_is_empty else (hk, hdv)
            out += [f"def {nm}(-{pv}: {A}.H{T} -> Bool, {params}, {k}: Nat, +{hk}: {{{pv}({nth(names[0], k)}) == True{{}} : Bool}}, "
                    f"+{hdv}: {{{pv}({empty}) == True{{}} : Bool}}) -> {{{pv}({nth(goc(names[0], names[1:]), k)}) == True{{}} : Bool}}:",
                    f"  match {names[0]} {k}:", "    case Nil{} _:", f"      {hdv}",
                    f"    case Con{{{self.e}, {self.t}}} 0n:",
                    f"      tb_ite_P({A}.H{T}, {pv}, {self.qual(self.cond)}, {self.qual(self.new)}, {self.qual(self.old)}, {ha}, {hb})",
                    f"    case Con{{{self.e}, {self.t}}} 1n+{k}q:",
                    f"      {nm}({pv}, {self.t}, {', '.join(rec_args)}, {k}q, {hk}, {hdv})", ""]
            self.stmts[("eqd",)] = nm
        return out


def _carried(m: Machine, a: dict) -> list[str]:
    lets = [g["let"] for g in a["guards"] if "let" in g]
    eff = set().union(*(m.fv(e) for e in a["effects"].values())) if a["effects"] else set()
    return [x for x in lets if x in eff]


def _let_types(m: Machine, act: dict) -> dict:
    env, out = {**m.stypes, **dict(act["inputs"])}, {}
    for g in act["guards"]:
        if "let" in g:
            out[g["let"]] = m.ex(g["expr"], {**env, **out})[1]
    return out


def _is(e, op: str) -> bool:
    return isinstance(e, list) and len(e) == 3 and e[0] == op


class _Carry:
    """One action's Ok branch: each conjunct of the invariant carried through the effects (old state -> new)."""

    def __init__(self, tb: TraceBound, a: dict, effects: dict, env: dict, delta, guards: list):
        self.tb, self.m, self.a = tb, tb.m, a
        self.guards = guards   # [(the inlined guard, the name of its equation {guard == True})] on a chain's Ok branch
        self.new = effects
        self.env = {**env, **tb.env_base()}
        self.delta = delta
        self.gnew = ["+", tb.G, delta] if delta is not None else tb.G

    def r(self, e, env: dict | None = None) -> str:
        return self.tb.r(e, env or self.env)

    def subst_new(self, e):
        sub = dict(self.new)
        if self.delta is not None:
            sub[self.tb.G] = self.gnew
        return _subst(e, sub)

    # ---------------------------------------------------------------- one conjunct
    def component(self, c: _Conj, h: str) -> str:
        fields = set(self.m.stypes)
        reads = self.m.fv(c.expr)
        touched = (reads & fields & set(self.new)) or (self.delta is not None and self.tb.G in reads)
        if not touched:
            return h
        if c.kvars:
            return self.list_component(c, h)
        hyps = [(cc.expr, hh) for cc, hh in zip(self.tb.conj, self.tb.hname) if not cc.kvars]
        return self.prove_bool(self.subst_new(c.expr), hyps, self.env)

    def list_component(self, c: _Conj, h: str) -> str:
        tb, m, A = self.tb, self.m, ALIAS
        nth_f, xs = c.read
        k = c.kvars[0]
        rec = m.lib.builtins[nth_f]["type"]
        x = tb.fresh_name("el")
        envx = {**self.env, x: rec}
        old_read = ["call", nth_f, xs, k]
        pold = _replace(c.expr, old_read, x)
        enew = self.subst_new(c.expr)
        lnew = self.new.get(xs, xs)
        new_read = ["call", nth_f, lnew, k]
        pnew = _replace(enew, new_read, x)
        if _occurs(pnew, k) or _occurs(pold, k):
            raise Fail(f"{k} survives outside the list read")
        dflt = ["call", m.lib.default_of(nth_f)]
        lam = f"(+{x} => {self.r(pnew, envx)})"
        At = f"{A}.H{rec}"
        hyps = [(cc.expr, hh) for cc, hh in zip(tb.conj, tb.hname) if not cc.kvars]
        # every old element carried to the new predicate (hx_at(i): a proof at index i; hx: the function)
        if _key(pnew) == _key(pold):
            def hx_at(i: str) -> str:
                return f"{h}({i})"
            hx = h
        else:
            j = tb.fresh_name("j")
            envj = {**self.env, j: "Nat"}
            goal = _replace(pnew, x, ["call", nth_f, xs, j])
            fact = _replace(pold, x, ["call", nth_f, xs, j])
            fname = tb.fresh_name("hj")
            hname, hargs = self.bool_helper(goal, hyps + [(fact, fname)], envj, param_order=[j])

            def hx_at(i: str, hname=hname, hargs=hargs, j=bname(j), fname=fname) -> str:
                out = [f"{h}({i})" if a == fname else re.sub(rf"\b{re.escape(j)}\b", i, a) for a in hargs]
                return f"{hname}({', '.join(out)})"
            hx = f"(+{bname(j)} => {hx_at(bname(j))})"

        def elem(e) -> str:   # P(e) for a new or default element, from the other conjuncts
            return self.prove_bool(_replace(pnew, x, e), hyps, self.env)
        if _key(lnew) == _key(xs):
            return hx if hx == h else f"(+{bname(k)} => {hx_at(bname(k))})"
        kv = bname(k)
        if isinstance(lnew, list) and lnew[0] == "call" and lnew[1] in ("snoc", "take", "drop") and _key(lnew[2]) == _key(xs):
            if lnew[1] == "snoc":
                return (f"(+{kv} => tb_append1_all({At}, {lam}, {self.r(xs)}, {self.r(lnew[3])}, {self.r(dflt)}, {hx}, "
                        f"{elem(lnew[3])}, {elem(dflt)}, {kv}))")
            fn = "tb_take_all" if lnew[1] == "take" else "tb_drop_all"
            return f"(+{kv} => {fn}({At}, {lam}, {self.r(xs)}, {self.r(lnew[3])}, {self.r(dflt)}, {hx}, {elem(dflt)}, {kv}))"
        if isinstance(lnew, list) and lnew[0] == "call" and lnew[1] in tb.pwinfo and _key(lnew[2]) == _key(xs):
            g = tb.pwinfo[lnew[1]]
            args = [self.r(z) for z in lnew[2:]]
            gargs = g.go_args(args)
            if ("eqd",) in g.stmts:
                return f"(+{kv} => {g.stmts[('eqd',)]}({lam}, {', '.join(gargs)}, {kv}, {hx_at(kv)}, {elem(dflt)}))"
            return self.fields_component(c, h, g, lnew, nth_f, xs, k, rec, pnew, pold, x, gargs)
        raise Fail(f"list effect {lnew!r}")

    def fields_component(self, c, h, g, lnew, nth_f, xs, k, rec, pnew, pold, x, gargs) -> str:
        """A builtin with per-field pointwise statements (le_add on some fields, eq on the rest): rewrite the eq
        fields of the new element to the old element's, then close the comparison with the le_add statements."""
        tb, A = self.tb, ALIAS
        kv = bname(k)
        ynew, yold = ["call", nth_f, lnew, k], ["call", nth_f, xs, k]
        goal = _replace(pnew, x, ynew)
        hk = tb.fresh_name("hk")
        fact_old = _replace(pold, x, yold)
        facts = [(fact_old, hk)]
        rewrites = []
        fields_new = sorted({e[2] for e in _gets(goal, ynew)})
        cur = goal
        for f in fields_new:
            if ("le", f) in g.stmts:
                nm, wname = g.stmts[("le", f)]
                w = lnew[2 + g.top_pnames.index(wname)]
                facts.append((["<=", ["get", ynew, f], ["+", ["get", yold, f], w]], f"{nm}({', '.join(gargs)}, {kv})"))
                continue
            if ("eq", f) not in g.stmts:
                raise Fail(f"{lnew[1]}.{f}: no pointwise statement")
            hole = "tb_hole"
            motive = self.r(_replace(cur, ["get", ynew, f], hole), {**self.env, hole: "Nat"}).replace(hole, "_")
            gnew_t, gold_t = self.r(["get", ynew, f]), self.r(["get", yold, f])
            rewrites.append(f"%Equal.sym(Nat, {gnew_t}, {gold_t}, {g.stmts[('eq', f)]}({', '.join(gargs)}, {kv})) : "
                            f"{{{motive} == True{{}} : Bool}}")
            cur = _replace(cur, ["get", ynew, f], ["get", yold, f])
        cur = self.simp(cur, {})
        if not (isinstance(cur, list) and cur[0] == "<="):
            raise Fail("not a comparison after the pointwise rewrites")
        proof = self.le(cur[1], cur[2], facts)
        if proof is None:
            raise Fail(f"pointwise comparison not carried: {json.dumps(cur)[:300]}")
        name = tb.helper("e")
        free = sorted((self.m.fv(goal) | self.m.fv(fact_old)) - {k})
        params = [f"+{kv}: Nat"] + [f"+{bname(v)}: {tb.ty(self.env[v])}" for v in free] \
            + [f"+{hk}: {{{self.r(fact_old)} == True{{}} : Bool}}"]
        tb.lines += [f"def {name}({', '.join(params)}) -> {{{self.r(goal)} == True{{}} : Bool}}:"] \
            + ["  " + x for x in rewrites] + [f"  {proof}", ""]
        return f"(+{kv} => {name}({', '.join([kv] + [bname(v) for v in free] + [f'{h}({kv})'])}))"

    def has_cmp(self, e) -> bool:
        """A guard worth carrying as a fact: it compares Nats somewhere in its Bool structure."""
        if isinstance(e, list) and e and e[0] in ("<=", "<"):
            return True
        if isinstance(e, list) and e and e[0] in ("&&", "||", "!"):
            return any(self.has_cmp(z) for z in e[1:])
        return False

    # ---------------------------------------------------------------- Bool structure: split the atoms
    def atoms(self, e, out: dict, arith: bool):
        if isinstance(e, bool) or isinstance(e, int):
            return
        if isinstance(e, list) and e and e[0] in ("&&", "||"):
            for z in e[1:]:
                self.atoms(z, out, arith)
            return
        if isinstance(e, list) and e and e[0] == "!":
            self.atoms(e[1], out, arith)
            return
        if isinstance(e, list) and e and e[0] in CMP_OPS:
            if arith:
                for z in e[1:]:
                    self.term_atoms(z, out)
                return
            out[_key(e)] = e
            return
        if isinstance(e, list) and e and e[0] == "?":
            self.atoms(e[1], out, False)
            self.atoms(e[2], out, arith)
            self.atoms(e[3], out, arith)
            return
        out[_key(e)] = e

    def term_atoms(self, e, out: dict):
        if not isinstance(e, list) or not e:
            return
        if e[0] == "?":
            self.atoms(e[1], out, False)
            self.term_atoms(e[2], out)
            self.term_atoms(e[3], out)
            return
        for z in (e[2:] if e[0] == "call" else e[1:]):
            if isinstance(z, dict):
                for v in z.values():
                    self.term_atoms(v, out)
            else:
                self.term_atoms(z, out)

    def simp(self, e, sig: dict):
        k = _key(e)
        if k in sig:
            return sig[k]
        if not isinstance(e, list) or not e:
            return e
        op = e[0]
        if op == "!":
            v = self.simp(e[1], sig)
            return (not v) if isinstance(v, bool) else ["!", v]
        if op in ("&&", "||"):
            unit, zero = (True, False) if op == "&&" else (False, True)
            xs = []
            for z in e[1:]:
                v = self.simp(z, sig)
                if v is zero:
                    return zero
                if v is not unit:
                    xs.append(v)
            if not xs:
                return unit
            return xs[0] if len(xs) == 1 else [op] + xs
        if op == "?":
            cv = self.simp(e[1], sig)
            if isinstance(cv, bool):
                return self.simp(e[2] if cv else e[3], sig)
            return ["?", cv, self.simp(e[2], sig), self.simp(e[3], sig)]
        if op == "get":
            base = self.simp(e[1], sig)
            if isinstance(base, list) and base and base[0] == "mk" and e[2] in base[2]:
                return self.simp(base[2][e[2]], sig)
            if isinstance(base, list) and base and base[0] == "with":
                return self.simp(base[3][e[2]], sig) if e[2] in base[3] else self.simp(["get", base[2], e[2]], sig)
            if isinstance(base, list) and len(base) == 2 and base[0] == "call" and self.m.lib.kind(base[1]) == "default":
                rt = self.m.lib.builtins[base[1]]["type"]
                ft = dict(self.m.types.get(rt, [])).get(e[2])
                if ft == "Nat":
                    return 0
                if ft == "Bool":
                    return False
            return ["get", base, e[2]]
        if op == "call":
            return ["call", e[1]] + [self.simp(z, sig) for z in e[2:]]
        if op == "mk":
            return ["mk", e[1], {f: self.simp(v, sig) for f, v in e[2].items()}]
        if op == "with":
            return ["with", e[1], self.simp(e[2], sig), {f: self.simp(v, sig) for f, v in e[3].items()}]
        return [op] + [self.simp(z, sig) for z in e[1:]]

    def prove_bool(self, goal, hyps: list, env: dict) -> str:
        name, args = self.bool_helper(goal, hyps, env)
        return f"{name}({', '.join(args)})"

    def bool_helper(self, goal, hyps: list, env: dict, param_order: list | None = None) -> tuple[str, list]:
        """(helper name, call arguments): a helper def proving {goal == True} from hyps [(expr, proof name)] that
        splits every Bool atom the goal and the hypotheses read (Bend's match refines the hypotheses), each case
        closed by computation, by a hypothesis that became False, or by the comparison rules."""
        tb = self.tb
        found: dict = {}
        self.atoms(goal, found, True)
        for H, _ in hyps:
            self.atoms(H, found, True)
        hyps = list(hyps) + [g for g in self.guards if self.has_cmp(g[0])]   # facts, never split
        alist = sorted(found.items())
        names, absd = {}, {}
        for key, e in alist:
            if isinstance(e, str) and e in env:
                names[key] = e
            else:
                names[key] = tb.fresh_name("b")
                absd[key] = e

        def abstract(z):
            for key, e in absd.items():
                z = _replace(z, e, names[key])
            return z
        GA = abstract(goal)
        HA = [(abstract(H), h) for H, h in hyps]
        env2 = {**env, **{names[key]: "Bool" for key, _ in alist}}
        fv = self.m.fv(GA)
        for H, _ in HA:
            fv |= self.m.fv(H)
        avars = {names[key] for key, _ in alist}
        lead = [v for v in (param_order or []) if v in fv and v not in avars]
        free = lead + sorted(v for v in fv if v not in avars and v not in lead)
        name = tb.helper("c")
        r2 = lambda z: self.tb.r(z, env2)   # noqa: E731
        params = [f"{bname(names[key])}: Bool" for key, _ in alist] + [f"+{bname(v)}: {tb.ty(env2[v])}" for v in free] \
            + [f"+{h}: {{{r2(H)} == True{{}} : Bool}}" for H, h in HA]
        lines = [f"def {name}({', '.join(params)}) -> {{{r2(GA)} == True{{}} : Bool}}:"]
        cases = list(itertools.product([True, False], repeat=len(alist))) if alist else [()]
        if alist:
            lines.append(f"  match {' '.join(bname(names[key]) for key, _ in alist)}:")
        ind = "      " if alist else "  "
        for vals in cases:
            sig = {_key(names[key]): v for (key, _), v in zip(alist, vals)}
            gs = self.simp(GA, sig)
            hs = [(self.simp(H, sig), h) for H, h in HA]
            if alist:
                lines.append(f"    case {' '.join('True{}' if v else 'False{}' for v in vals)}:")
            if gs is True:
                proof = "{==}"
            else:
                bad = next((h for H, h in hs if H is False), None)
                if bad is not None:
                    gtxt = "False{}" if gs is False else r2(gs)
                    proof = f"CP.core_efq({{{gtxt} == True{{}} : Bool}}, C.core_false_ne_true({bad}))"
                elif gs is False:
                    raise Fail("a case of the goal is False")
                else:
                    proof = self.prove_prop(gs, [(H, h) for H, h in hs if not isinstance(H, bool)], env2)
                    if proof is None:
                        raise Fail(f"not carried: {json.dumps(gs)[:300]}")
            lines.append(ind + proof)
        tb.lines += lines + [""]
        args = []
        for key, e in alist:
            args.append(bname(e) if key not in absd else self.tb.r(e, env))
        args += [bname(v) for v in free] + [h for _, h in HA]
        return name, args

    # ---------------------------------------------------------------- propositions and comparisons
    def prove_prop(self, g, facts: list, env: dict) -> str | None:
        r2 = lambda z: self.tb.r(z, env)   # noqa: E731
        for H, h in facts:
            if _key(H) == _key(g):
                return h
        if _is(g, "<="):
            return self.le(g[1], g[2], facts, env)
        if isinstance(g, list) and g and g[0] == "&&" and len(g) == 3:
            pl, pr = self.prove_prop(g[1], facts, env), self.prove_prop(g[2], facts, env)
            if pl and pr:
                return f"C.core_and_intro({r2(g[1])}, {r2(g[2])}, {pl}, {pr})"
        return None

    def le(self, S, T, facts: list, env: dict | None = None, depth: int = 0) -> str | None:
        """A proof of {Nat.is_le(S, T) == True} from the comparison facts [(expr, proof)], or None."""
        env = env or self.env
        r2 = lambda z: self.tb.r(z, env)   # noqa: E731
        if depth > 8:
            return None
        cmp = [(H, h) for H, h in facts if _is(H, "<=")]
        for H, h in cmp:
            if _key(H[1]) == _key(S) and _key(H[2]) == _key(T):
                return h
        if _key(S) == _key(T):
            return f"C.core_le_refl({r2(S)})"
        if S == 0:
            return f"C.core_le_zero({r2(T)})"
        rd = self.list_read(S)
        if rd is not None:
            p = self.read_rule(S, T, facts, env, rd, depth)
            if p:
                return p
        if _is(T, "+") and _key(T[1]) == _key(S):
            return f"C.core_le_add_self({r2(S)}, {r2(T[2])})"
        if _is(S, "+") and _is(T, "+") and _key(S[1]) == _key(T[1]):
            p = self.le(S[2], T[2], facts, env, depth + 1)
            if p:
                return f"C.core_le_add_l({r2(S[1])}, {r2(S[2])}, {r2(T[2])}, {p})"
        if _is(S, "+") and _is(T, "+") and _key(S[2]) == _key(T[2]):
            p = self.le(S[1], T[1], facts, env, depth + 1)
            if p:
                return f"tb_le_add_r({r2(S[1])}, {r2(T[1])}, {r2(S[2])}, {p})"
        if _is(T, "+") and _is(T[2], "+"):
            T2 = ["+", ["+", T[1], T[2][1]], T[2][2]]
            p = self.le(S, T2, facts, env, depth + 1)
            if p:
                return f"tb_le_assoc_r({r2(S)}, {r2(T[1])}, {r2(T[2][1])}, {r2(T[2][2])}, {p})"
        if _is(S, "-") and _is(S[1], "+"):
            w, s, t = S[1][1], S[1][2], S[2]
            pst = self.le(s, t, facts, env, depth + 1)
            if pst:
                pw = self.le(w, T, facts, env, depth + 1)
                if pw:
                    return f"C.core_le_trans({r2(S)}, {r2(w)}, {r2(T)}, tb_sub_le({r2(w)}, {r2(s)}, {r2(t)}, {pst}), {pw})"
        for H, h in cmp:
            if _key(H[1]) == _key(S) and _key(H[2]) != _key(T):
                rest = [f for f in facts if f[1] != h]
                p = self.le(H[2], T, rest, env, depth + 1)
                if p:
                    return f"C.core_le_trans({r2(S)}, {r2(H[2])}, {r2(T)}, {h}, {p})"
        if _is(T, "+"):
            p = self.le(S, T[2], facts, env, depth + 1)
            if p:
                return f"C.core_le_add_left({r2(T[1])}, {r2(S)}, {r2(T[2])}, {p})"
            p = self.le(S, T[1], facts, env, depth + 1)
            if p:
                return f"C.core_le_trans({r2(S)}, {r2(T[1])}, {r2(T)}, {p}, C.core_le_add_self({r2(T[1])}, {r2(T[2])}))"
        return None

    def list_read(self, e):
        """The first read get(nth(L, i), f) in e of a list L that is not a state field (a list an effect built)."""
        if not isinstance(e, list) or not e:
            return None
        if e[0] == "get" and isinstance(e[1], list) and len(e[1]) == 4 and e[1][0] == "call" \
                and self.m.lib.kind(e[1][1]) == "nth_default" and not isinstance(e[1][2], str):
            return e[1]
        for z in (e[2:] if e[0] == "call" else e[1:]):
            if isinstance(z, list):
                got = self.list_read(z)
                if got is not None:
                    return got
        return None

    def read_rule(self, S, T, facts, env, rd, depth) -> str | None:
        """S reads element i of a list an effect built: the comparison as a predicate of that element, carried by the
        list builtin's lemma (set_default: the new value, the old element, the default; a kindless builtin: its
        pointwise sidecar)."""
        tb, m, A = self.tb, self.m, ALIAS
        nth_f, L, i = rd[1], rd[2], rd[3]
        rec = m.lib.builtins[nth_f]["type"]
        x = tb.fresh_name("el")
        envx = {**env, x: rec}
        P = ["<=", _replace(S, rd, x), _replace(T, rd, x)]
        lam = f"(+{x} => {tb.r(P, envx)})"
        dflt = ["call", m.lib.default_of(nth_f)]
        At = f"{A}.H{rec}"

        def at(e):
            g = self.simp(_replace(P, x, e), {})
            if g is True:
                return "{==}"
            if not _is(g, "<="):
                return None
            return self.le(g[1], g[2], facts, env, depth + 1)
        if isinstance(L, list) and L[0] == "call" and m.lib.kind(L[1]) == "set_default" \
                and m.lib.default_of(L[1]) == m.lib.default_of(nth_f):
            xs, j, v = L[2], L[3], L[4]
            if _key(j) == _key(i):
                pv = at(v)
                return None if pv is None else \
                    f"tb_set_same_at({At}, {lam}, {tb.r(xs, env)}, {tb.r(j, env)}, {tb.r(v, env)}, {tb.r(dflt, env)}, {tb.r(dflt, env)}, {pv})"
            po, pv, pd = at(["call", nth_f, xs, i]), at(v), at(dflt)
            if None in (po, pv, pd):
                return None
            return (f"tb_set_at({At}, {lam}, {tb.r(xs, env)}, {tb.r(j, env)}, {tb.r(i, env)}, {tb.r(v, env)}, "
                    f"{tb.r(dflt, env)}, {po}, {pv}, {pd})")
        if isinstance(L, list) and L[0] == "call" and L[1] in tb.pwinfo and ("eqd",) in tb.pwinfo[L[1]].stmts:
            g = tb.pwinfo[L[1]]
            po, pd = at(["call", nth_f, L[2], i]), at(dflt)
            if None in (po, pd):
                return None
            gargs = g.go_args([tb.r(z, env) for z in L[2:]])
            return f"{g.stmts[('eqd',)]}({lam}, {', '.join(gargs)}, {tb.r(i, env)}, {po}, {pd})"
        return None


def _gets(e, base) -> list:
    """The reads ["get", base, f] in e."""
    out = []
    if isinstance(e, list) and e:
        if e[0] == "get" and _key(e[1]) == _key(base):
            out.append(e)
        for z in (e[2:] if e[0] == "call" else e[1:]):
            if isinstance(z, dict):
                for v in z.values():
                    out += _gets(v, base)
            else:
                out += _gets(z, base)
    return out


LIBRARY = """\
# ---- Nat
def tb_add_zero(x: Nat) -> {Nat.add(x, 0n) == x : Nat}:
  match x:
    case 0n:
      {==}
    case 1n+p:
      %tb_add_zero(p) : {1n+Nat.add(p, 0n) == 1n+_ : Nat}
      {==}

def tb_add_assoc(+x: Nat, +y: Nat, +z: Nat) -> {Nat.add(Nat.add(x, y), z) == Nat.add(x, Nat.add(y, z)) : Nat}:
  match x:
    case 0n:
      {==}
    case 1n+p:
      %tb_add_assoc(p, y, z) : {1n+Nat.add(Nat.add(p, y), z) == 1n+_ : Nat}
      {==}

def tb_add_succ(+x: Nat, +y: Nat) -> {Nat.add(x, 1n+y) == 1n+Nat.add(x, y) : Nat}:
  match x:
    case 0n:
      {==}
    case 1n+p:
      %tb_add_succ(p, y) : {1n+Nat.add(p, 1n+y) == 1n+_ : Nat}
      {==}

def tb_sub_le0(+w: Nat, +t: Nat) -> {Nat.is_le(Nat.sub(w, t), w) == True{} : Bool}:
  match w:
    case 0n:
      {==}
    case 1n+wp:
      match t:
        case 0n:
          C.core_le_refl(1n+wp)
        case 1n+tp:
          C.core_le_succ(Nat.sub(wp, tp), wp, tb_sub_le0(wp, tp))

# (w + s) - t <= w when s <= t
def tb_sub_le(+w: Nat, +s: Nat, +t: Nat, +e: {Nat.is_le(s, t) == True{} : Bool}) -> {Nat.is_le(Nat.sub(Nat.add(w, s), t), w) == True{} : Bool}:
  match s:
    case 0n:
      %Equal.sym(Nat, Nat.add(w, 0n), w, tb_add_zero(w)) : {Nat.is_le(Nat.sub(_, t), w) == True{} : Bool}
      tb_sub_le0(w, t)
    case 1n+sp:
      match t:
        case 0n:
          CP.core_efq({Nat.is_le(Nat.sub(Nat.add(w, 1n+sp), 0n), w) == True{} : Bool}, C.core_false_ne_true(e))
        case 1n+tp:
          %Equal.sym(Nat, Nat.add(w, 1n+sp), 1n+Nat.add(w, sp), tb_add_succ(w, sp)) : {Nat.is_le(Nat.sub(_, 1n+tp), w) == True{} : Bool}
          tb_sub_le(w, sp, tp, e)

# a <= b gives a + d <= b + d
def tb_le_add_r(+a: Nat, +b: Nat, +d: Nat, +e: {Nat.is_le(a, b) == True{} : Bool}) -> {Nat.is_le(Nat.add(a, d), Nat.add(b, d)) == True{} : Bool}:
  match a:
    case 0n:
      C.core_le_add_left(b, d, d, C.core_le_refl(d))
    case 1n+ap:
      match b:
        case 0n:
          CP.core_efq({Nat.is_le(Nat.add(1n+ap, d), Nat.add(0n, d)) == True{} : Bool}, C.core_false_ne_true(e))
        case 1n+bp:
          tb_le_add_r(ap, bp, d, e)

def tb_le_assoc_r(+a: Nat, +x: Nat, +y: Nat, +z: Nat, +e: {Nat.is_le(a, Nat.add(Nat.add(x, y), z)) == True{} : Bool}) -> {Nat.is_le(a, Nat.add(x, Nat.add(y, z))) == True{} : Bool}:
  %tb_add_assoc(x, y, z) : {Nat.is_le(a, _) == True{} : Bool}
  e

# ---- an element predicate through ite and the list builtins
def tb_ite_P(-A: Data, -P: A -> Bool, c: Bool, +a: A, +b: A, +ha: {P(a) == True{} : Bool}, +hb: {P(b) == True{} : Bool}) -> {P(M.ite(A, c, a, b)) == True{} : Bool}:
  match c:
    case True{}:
      ha
    case False{}:
      hb

def tb_append1_all(-A: Data, -P: A -> Bool, xs: List<&2, A>, +e: A, +d: A, hx: @k:Nat -> {P(M.nth_d(A, xs, k, d)) == True{} : Bool}, +he: {P(e) == True{} : Bool}, +hd: {P(d) == True{} : Bool}, k: Nat) -> {P(M.nth_d(A, List.append(&2, A, xs, [e]), k, d)) == True{} : Bool}:
  match xs k:
    case Nil{} 0n:
      he
    case Nil{} 1n+kq:
      hd
    case Con{h, t} 0n:
      hx(0n)
    case Con{h, t} 1n+kq:
      tb_append1_all(A, P, t, e, d, (j => hx(1n+j)), he, hd, kq)

def tb_take_all(-A: Data, -P: A -> Bool, xs: List<&2, A>, n: Nat, +d: A, hx: @k:Nat -> {P(M.nth_d(A, xs, k, d)) == True{} : Bool}, +hd: {P(d) == True{} : Bool}, k: Nat) -> {P(M.nth_d(A, List.take(&2, A, xs, n), k, d)) == True{} : Bool}:
  match xs n k:
    case Nil{} _ _:
      hd
    case Con{h, t} 0n _:
      hd
    case Con{h, t} 1n+np 0n:
      hx(0n)
    case Con{h, t} 1n+np 1n+kq:
      tb_take_all(A, P, t, np, d, (j => hx(1n+j)), hd, kq)

def tb_drop_all(-A: Data, -P: A -> Bool, xs: List<&2, A>, n: Nat, +d: A, hx: @k:Nat -> {P(M.nth_d(A, xs, k, d)) == True{} : Bool}, +hd: {P(d) == True{} : Bool}, k: Nat) -> {P(M.nth_d(A, List.drop(&2, A, xs, n), k, d)) == True{} : Bool}:
  match xs n:
    case Nil{} _:
      hd
    case Con{h, t} 0n:
      hx(k)
    case Con{h, t} 1n+np:
      tb_drop_all(A, P, t, np, d, (j => hx(1n+j)), hd, k)

def tb_set_same_at(-A: Data, -P: A -> Bool, xs: List<&2, A>, i: Nat, +v: A, +d: A, +d2: A, +hv: {P(v) == True{} : Bool}) -> {P(M.nth_d(A, M.set_d(A, xs, i, v, d), i, d2)) == True{} : Bool}:
  match xs i:
    case Nil{} 0n:
      hv
    case Nil{} 1n+ip:
      tb_set_same_at(A, P, Nil{}, ip, v, d, d2, hv)
    case Con{h, t} 0n:
      hv
    case Con{h, t} 1n+ip:
      tb_set_same_at(A, P, t, ip, v, d, d2, hv)

def tb_set_at(-A: Data, -P: A -> Bool, xs: List<&2, A>, i: Nat, j: Nat, +v: A, +d: A, +hj: {P(M.nth_d(A, xs, j, d)) == True{} : Bool}, +hv: {P(v) == True{} : Bool}, +hd: {P(d) == True{} : Bool}) -> {P(M.nth_d(A, M.set_d(A, xs, i, v, d), j, d)) == True{} : Bool}:
  match xs i j:
    case Nil{} 0n 0n:
      hv
    case Nil{} 0n 1n+jq:
      hd
    case Nil{} 1n+ip 0n:
      hd
    case Nil{} 1n+ip 1n+jq:
      tb_set_at(A, P, Nil{}, ip, jq, v, d, hj, hv, hd)
    case Con{h, t} 0n 0n:
      hv
    case Con{h, t} 0n 1n+jq:
      hj
    case Con{h, t} 1n+ip 0n:
      hj
    case Con{h, t} 1n+ip 1n+jq:
      tb_set_at(A, P, t, ip, jq, v, d, hj, hv, hd)

""".replace("M.", ALIAS + ".").splitlines()


def pointwise_for(m: Machine) -> dict:
    """The pointwise sidecars next to the model's target libraries (X.lib.json -> X.pointwise.json), merged."""
    out: dict = {}
    for p in getattr(m.lib, "sources", []) or []:
        sp = Path(p).with_name(Path(p).name.replace(".lib.json", ".pointwise.json"))
        if sp.is_file():
            doc = json.loads(sp.read_text(encoding="utf-8"))
            for b, spec in (doc.get("builtins") or {}).items():
                out[b] = spec
    return out


def trace_bound(em: EmittedM, m: Machine, model_import: str) -> str | None:
    """The class's proof of the law emitted as em over the model m, or None when the law is not of its shape or a step
    cannot be carried (module docstring)."""
    law = getattr(em, "law", None)
    if not isinstance(law, dict) or law.get("ir_version") != "holon-ir/0.3":
        return None
    try:
        return TraceBound(em, m, model_import, law, pointwise_for(m)).render()
    except Fail:
        return None
