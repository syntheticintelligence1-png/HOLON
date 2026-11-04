"""A symbolic stepper over the statement chain of the typed model's actions (holon.sorts.model3), for the DISCH proof
generators (holon.disch.proofs).

holon.sorts.model3 compiles an action's program to a chain of statement definitions over its context record X_<a>:
s_<a>_<i>(x) runs statement i and calls the next statement's s_<a>_<j>; a check is k_<a>_<i>(c, x) (True: the next
statement; False: xf_<a>, the revert with the check's code), a conditional write or event wc_/ec_<a>_<i>(c, x), a call
guard cq_<a>_<i>_<n>(c, x); writes, events and setters are record updates. This module parses those definitions from
the model text (the generated subset: match on a parameter, lets, calls, constructors) and evaluates one statement on a
symbolic record X_<a>{f1, .., fn} (each field a term), stopping at the next statement, at a revert or at the end, and
splitting at every boolean the evaluation gets stuck on (a condition over the record's fields):

  step(a, i, fields) -> Node        Next(j, fields') | Final(fields') | Branch(fn, cond, args, then, else)

A Branch carries the definition fn whose first parameter is matched (fn(cond, args..) is the term Bend reduces the
statement to), so a proof can split on cond with the equation {cond == c} and continue in each case with the same
definition applied to True{} or False{}.

Loops (I68, the loop frames L1): a loop statement lg_<a>_<n>(x) runs lp_<a>_<L>(fuel, d, ls_<a>_<L>(x)), whose body
recurses on the fuel, and continues with la_<a>_<n>(u_nz(code), y) on its result y. The stepper does not unfold it:
it returns Loop(n, L, fuel, d, the record), and after_loop(n, record) steps la_<a>_<n> on a record standing for y. The
loop's own definitions (li, lh, lb, lc, lk, ln, lbk, lx, lz, ls: one iteration, its head and its exits) are stepped
like statements, so that a proof can follow one iteration (holon.disch.proofs.LoopProof); the body's statement chain
inside lb_<a>_<L>(s_<a>_<i>(x)) is Next(i, fields, ctx=lb_<a>_<L>).

Terms are Bend text: a model name is qualified M.<name>; the evaluation only substitutes, it never simplifies, so every
term it returns is what Bend computes the same expression to (by delta and match reduction). Nothing here names a target.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


class NoMirror(ValueError):
    """The stepper cannot follow the program (named)."""


# ------------------------------------------------------------------------------------------------ text helpers
_OPEN = {"(": ")", "{": "}", "[": "]"}


def split_top(s: str, sep: str = ",") -> list[str]:
    """s split at the separators outside brackets (a type's angle brackets, List<&2, U32>, included), each part
    stripped."""
    out, depth, angle, cur = [], 0, 0, []
    for i, ch in enumerate(s):
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
        elif ch == "<" and i > 0 and (s[i - 1].isalnum() or s[i - 1] == "_"):
            angle += 1
        elif ch == ">" and angle > 0 and not (i > 0 and s[i - 1] == "-"):
            angle -= 1
        if ch == sep and depth == 0 and angle == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    tail = "".join(cur).strip()
    if tail or out:
        out.append(tail)
    return out


def _match_close(s: str, i: int) -> int:
    """The index of the bracket closing the one at s[i]."""
    want = _OPEN[s[i]]
    depth = 0
    for j in range(i, len(s)):
        if s[j] in "({[":
            depth += 1
        elif s[j] in ")}]":
            depth -= 1
            if depth == 0:
                if s[j] != want:
                    raise NoMirror(f"unbalanced brackets in {s[:80]}")
                return j
    raise NoMirror(f"unbalanced brackets in {s[:80]}")


_HEAD = re.compile(r"^([A-Za-z_][\w.]*)\s*([({])")


def as_call(s: str):
    """(name, [args], bracket) when s is exactly name(args..) or name{args..}, else None."""
    s = s.strip()
    m = _HEAD.match(s)
    if not m:
        return None
    i = m.end() - 1
    j = _match_close(s, i)
    if j != len(s) - 1:
        return None
    inner = s[i + 1:j]
    return m.group(1), (split_top(inner) if inner.strip() else []), m.group(2)


def strip_annot(s: str) -> str:
    """{e : T} (an annotation) as e."""
    s = s.strip()
    if s.startswith("{") and s.endswith("}") and _match_close(s, 0) == len(s) - 1:
        inner = s[1:-1]
        parts = split_top(inner, ":")
        if len(parts) >= 2:
            return ":".join(parts[:-1]).strip() if len(parts) > 2 else parts[0]
    return s


def subst(term: str, env: dict) -> str:
    """term with every variable of env replaced by its term (identifiers not preceded by . and not followed by ( or {)."""
    if not env:
        return term

    def rep(m):
        n = m.group(0)
        return env[n] if n in env else n
    return re.sub(r"(?<![\w.])[A-Za-z_]\w*(?![\w({])", rep, term)


# ------------------------------------------------------------------------------------------------ definitions
@dataclass
class Def:
    name: str
    params: list            # parameter names (without +/-)
    body: list              # [(indent, text)]


def parse_defs(model_text: str, wanted) -> dict:
    """The definitions of the model text whose names `wanted(name)` accepts."""
    out = {}
    lines = model_text.split("\n")
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        m = re.match(r"^def (\w+)\((.*)\)\s*->.*:\s*$", ln)
        if not m or not wanted(m.group(1)):
            i += 1
            continue
        name = m.group(1)
        params = []
        for p in split_top(m.group(2)):
            pn = p.split(":")[0].strip().lstrip("+-~")
            if pn:
                params.append(pn)
        body = []
        i += 1
        while i < n and (lines[i].startswith(" ") or not lines[i].strip()):
            if lines[i].strip():
                body.append((len(lines[i]) - len(lines[i].lstrip(" ")), lines[i].strip()))
            i += 1
        out[name] = Def(name, params, body)
    return out


# ------------------------------------------------------------------------------------------------ evaluation results
@dataclass
class Next:
    j: int
    fields: list
    ctx: str | None = None  # the loop exit the statement's result goes through (lb_<a>_<L>, a loop body's chain)


@dataclass
class Final:
    fields: list


@dataclass
class Branch:
    fn: str                 # the definition matched on its first parameter (qualified M.<fn>)
    cond: str               # the stuck condition (a term of the record's fields)
    args: list              # the other arguments of fn (terms)
    then: object = None
    other: object = None


@dataclass
class Record:
    name: str               # X_<a>
    fields: list


@dataclass
class Loop:
    n: int                  # the loop statement lg_<a>_<n>
    L: int                  # its loop lp_<a>_<L>
    fuel: str               # the fuel and the initial direction lg passes (terms)
    d: str
    rec: Record             # the record the loop statement runs on


LOOP_PARTS = ("li", "lh", "lb", "lc", "lk", "ln", "lbk", "lx", "lz", "ls")   # one iteration, its head, exits, start


class Mirror:
    """The statement chain of one action of the model."""

    def __init__(self, model_text: str, action_b: str, names: set):
        self.a = action_b
        self.X = f"X_{action_b}"
        self.names = names
        self.loop_pre = tuple(f"{q}_{action_b}_" for q in LOOP_PARTS)
        pre = (f"s_{action_b}_", f"k_{action_b}_", f"wc_{action_b}_", f"ec_{action_b}_", f"cq_{action_b}_",
               f"wr_{action_b}_", f"ev_{action_b}_", f"sx_{action_b}_", f"xf_{action_b}", f"sz_{action_b}",
               f"gx_{action_b}_", f"x0_{action_b}", f"xr_{action_b}", f"lq_{action_b}_", f"la_{action_b}_",
               f"lg_{action_b}_") + self.loop_pre
        self.defs = parse_defs(model_text, lambda nm: nm.startswith(pre))
        m = re.search(rf"(?m)^type {re.escape(self.X)} is Data:\n  {re.escape(self.X)}\{{(.*)\}}$", model_text)
        if not m:
            raise NoMirror(f"no context record {self.X}")
        self.field_names = [p.split(":")[0].strip() for p in split_top(m.group(1))]
        xr = self.defs.get(f"xr_{action_b}")
        if xr is None or not xr.body:
            raise NoMirror(f"no xr_{action_b}")
        c = as_call(xr.body[-1][1])
        if not c or not c[0].startswith(f"s_{action_b}_"):
            raise NoMirror(f"xr_{action_b} does not start a statement chain")
        self.first = int(c[0].rsplit("_", 1)[1])

    def q(self, name: str) -> str:
        return ("M." + name) if name in self.names else name

    def qterm(self, t: str) -> str:
        """A model term (unqualified, as the model text writes it) with the model's names qualified: applications and
        constructors, and a type the model declares passed bare (ite(W, ..), List<&2, KV>)."""
        def sub(m):
            n = m.group(1)
            return ("M." + n if n in self.names else n) + m.group(2)
        t = re.sub(r"(?<![\w.])([A-Za-z_]\w*)(\s*[({])", sub, t)
        return re.sub(r"(?<![\w.])([A-Z]\w*)(?![\w({])", lambda m: "M." + m.group(1) if m.group(1) in self.names
                      else m.group(1), t)

    # -------------------------------------------------------------------------------------- the evaluator
    def x0_fields(self, st: str, ar: str, en: str, tabs: list) -> list:
        """The fields of x0_<a>(st, ar, en, tables..)."""
        d = self.defs.get(f"x0_{self.a}")
        if d is None:
            raise NoMirror(f"no x0_{self.a}")
        env = dict(zip(d.params, [st, ar, en] + list(tabs)))
        c = as_call(d.body[-1][1])
        if not c or c[0] != self.X:
            raise NoMirror(f"x0_{self.a} is not a record")
        return [subst(self.qterm(f), env) for f in c[1]]

    def step(self, i: int, fields: list):
        """Statement i on the record X{fields}: Next, Final or Branch."""
        return self.apply(f"s_{self.a}_{i}", [Record(self.X, list(fields))], top=i)

    def chained(self, fn: str) -> bool:
        """A definition whose result is the rest of the chain's (a statement, a check, a guard, a conditional effect, a
        loop statement's entry and exit)."""
        return fn.startswith((f"s_{self.a}_", f"k_{self.a}_", f"wc_{self.a}_", f"ec_{self.a}_", f"cq_{self.a}_",
                              f"lq_{self.a}_", f"la_{self.a}_")) or fn == f"sz_{self.a}"

    def loop_part(self, fn: str) -> bool:
        """One of a loop's own definitions (LOOP_PARTS), stepped like a statement."""
        return fn.startswith(self.loop_pre)

    def loop_node(self, fn: str, rec) -> Loop:
        """The Loop node of a loop statement lg_<a>_<n>(rec): its body is `+y = lp_<a>_<L>(fuel, d, ls_<a>_<L>(x))`
        then `la_<a>_<n>(u_nz(gx_<a>_cd(y)), y)`."""
        d = self.defs[fn]
        if not isinstance(rec, Record) or len(d.body) != 2 or len(d.params) != 1:
            raise NoMirror(f"{fn}: a loop statement of an unknown shape")
        m = re.fullmatch(r"\+y = (.*)", d.body[0][1])
        c = as_call(m.group(1)) if m else None
        n = int(fn.rsplit("_", 1)[1])
        la = as_call(d.body[1][1])
        if not c or not re.fullmatch(rf"lp_{re.escape(self.a)}_\d+", c[0]) or len(c[1]) != 3 or \
                c[1][2].strip() != f"ls_{self.a}_{c[0].rsplit('_', 1)[1]}({d.params[0]})" or not la or \
                la[0] != f"la_{self.a}_{n}" or [x.strip() for x in la[1]] != [f"u_nz(gx_{self.a}_cd(y))", "y"]:
            raise NoMirror(f"{fn}: a loop statement of an unknown shape")
        return Loop(n, int(c[0].rsplit("_", 1)[1]), self.qterm(c[1][0].strip()), self.qterm(c[1][1].strip()), rec)

    def after_loop(self, n: int, rec: Record):
        """la_<a>_<n> on rec, a record standing for the loop's result (its code field the condition)."""
        cd = rec.fields[self.field_names.index("cd")]
        return self.apply(f"la_{self.a}_{n}", [f"M.u_nz({cd})", rec])

    def apply(self, fn: str, args: list, top: int | None = None, depth: int = 0):
        if depth > 200:
            raise NoMirror(f"{fn}: the evaluation does not end")
        if fn.startswith(f"s_{self.a}_") and top is None:
            j = int(fn.rsplit("_", 1)[1])
            rec = args[0]
            if not isinstance(rec, Record):
                raise NoMirror(f"{fn} applied to a term that is not the record")
            return Next(j, rec.fields)
        d = self.defs.get(fn)
        if d is None:
            raise NoMirror(f"{self.a}: the program calls {fn}, which the stepper does not follow (a loop or a helper)")
        if len(d.params) != len(args):
            raise NoMirror(f"{fn}: {len(args)} arguments for {len(d.params)} parameters")
        env = dict(zip(d.params, args))
        r = self.block(d, d.body, 0, env, depth)
        if self.chained(fn) and isinstance(r, Record):
            return Final(r.fields)            # the chain ended here (a revert, or the end of the program)
        return r

    def block(self, d: Def, body: list, k: int, env: dict, depth: int):
        """Evaluate the statements body[k:] (one indentation level) under env."""
        ind, text = body[k]
        m = re.match(r"^match (\w+):$", text)
        if m:
            v = env.get(m.group(1))
            cases = []
            j = k + 1
            while j < len(body) and body[j][0] > ind:
                if body[j][0] == ind + 2 and body[j][1].startswith("case "):
                    cases.append(j)
                j += 1
            if isinstance(v, Record):
                if len(cases) != 1:
                    raise NoMirror(f"{d.name}: a match on the record with {len(cases)} cases")
                pat = body[cases[0]][1][len("case "):-1]
                c = as_call(pat)
                if not c or c[0] != v.name:
                    raise NoMirror(f"{d.name}: pattern {pat} on {v.name}")
                env2 = dict(env)
                for p, f in zip(c[1], v.fields):
                    p = p.strip().lstrip("+")
                    if p != "_":
                        env2[p] = f
                return self.block(d, body, cases[0] + 1, env2, depth)
            if isinstance(v, str) and v in ("True{}", "False{}"):
                want = f"case {v}:"
                for ci in cases:
                    if body[ci][1] == want:
                        return self.block(d, body, ci + 1, env, depth)
                raise NoMirror(f"{d.name}: no case {v}")
            if isinstance(v, str) and d.params and m.group(1) == d.params[0]:
                # a stuck condition: split (the definition applied to True{} and to False{})
                rest = [env[p] for p in d.params[1:]]
                br = Branch(self.q(d.name), v, [self.render(x) for x in rest])
                br.then = self.apply(d.name, ["True{}"] + rest, depth=depth + 1)
                br.other = self.apply(d.name, ["False{}"] + rest, depth=depth + 1)
                return br
            raise NoMirror(f"{d.name}: a match on {m.group(1)} that is neither the record nor its first parameter")
        m = re.match(r"^\+?(\w+) = (.*)$", text)
        if m:
            env2 = dict(env)
            env2[m.group(1)] = self.value(strip_annot(m.group(2)), env, d, depth)
            return self.block(d, body, k + 1, env2, depth)
        return self.value(text, env, d, depth, final=True)

    def render(self, v) -> str:
        if isinstance(v, Record):
            return f"{self.q(v.name)}{{{', '.join(v.fields)}}}"
        return v

    def value(self, text: str, env: dict, d: Def, depth: int, final: bool = False):
        """A term under env: a record, a statement-level application (evaluated) or a term (text)."""
        text = text.strip()
        if re.fullmatch(r"[A-Za-z_]\w*", text) and text in env:
            return env[text]
        c = as_call(text)
        if c and c[2] == "{" and c[0] == self.X:
            return Record(self.X, [self.render(self.value(x, env, d, depth)) for x in c[1]])
        if c and c[2] == "(":
            fn = c[0]
            stmt = fn.startswith((f"s_{self.a}_", f"k_{self.a}_", f"wc_{self.a}_", f"ec_{self.a}_", f"cq_{self.a}_",
                                  f"wr_{self.a}_", f"ev_{self.a}_", f"sx_{self.a}_", f"lq_{self.a}_",
                                  f"la_{self.a}_")) or fn in (f"xf_{self.a}", f"sz_{self.a}")
            if fn.startswith(f"lg_{self.a}_"):   # a loop statement: not unfolded (Loop)
                return self.loop_node(fn, self.value(c[1][0], env, d, depth) if len(c[1]) == 1 else None)
            if self.loop_part(fn):
                args = [self.value(x, env, d, depth) for x in c[1]]
                if args and isinstance(args[-1], Next) and args[-1].ctx is None and len(args) == 1:
                    return Next(args[-1].j, args[-1].fields, ctx=self.q(fn))   # lb_<a>_<L>(s_<a>_<i>(x))
                if any(isinstance(x, (Next, Final, Branch, Loop)) for x in args):
                    raise NoMirror(f"{fn}: a loop part applied to the rest of a chain")
                return self.apply(fn, args, depth=depth + 1)
            if stmt:
                args = [self.value(x, env, d, depth) for x in c[1]]
                if fn.startswith(f"sx_{self.a}_") or fn.startswith(f"wr_{self.a}_") or \
                        fn.startswith(f"ev_{self.a}_") or fn == f"xf_{self.a}":
                    r = self.apply(fn, args, depth=depth + 1)
                    if not isinstance(r, Record):
                        raise NoMirror(f"{fn} is not a record update")
                    return r
                return self.apply(fn, args, depth=depth + 1)
            if fn.startswith(f"gx_{self.a}_"):
                arg = self.value(c[1][0], env, d, depth)
                if isinstance(arg, Record):
                    return arg.fields[self.field_names.index(fn[len(f"gx_{self.a}_"):])]
        if final:
            raise NoMirror(f"{d.name}: the body ends in {text[:120]}, which is not a statement, a record or a revert")
        return self.render_term(text, env)

    def render_term(self, text: str, env: dict) -> str:
        sub = {k: self.render(v) for k, v in env.items() if isinstance(v, (str, Record))}
        return subst(self.qterm(text), sub)
