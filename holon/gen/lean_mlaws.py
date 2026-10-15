"""Lean statements of machine laws (I43 rule L3, kinds machine and machine_oracle), rendered from the IR alone.

Binders in IR order with the oracle parameters first (Lean functions, the IR's reading of Fn<A,B>); a Reach binder
as a state and the hypothesis Model.Reach <parameters> <state>, the quantifier group closed at each such hypothesis;
premises as hypotheses (as I9); claim eq/neq as =/≠ and a conjunction as ∧; terms as the interface's functions
(Model.<name>), a view equation through view_<..>. A PROVED law is `theorem <law id> : <statement>`; a REFUTED law is
`theorem <law id>_counter : ∃ <binders>, <premises> ∧ <negated claim>` and `theorem <law id>_refuted : ¬
(<statement>)`. Whitespace aside, every text equals the frozen one.

Terms, as (Lean text, IR type): var (its binder v_<name>), nat, bool, nats, s0, run/step/obs from a state, a trace
literal, cat of two traces, an action term (its arguments in the action's input order), proj (a view: the fields it
erases, sorted, joined by "__"), obsv, mig, fn (the model functions last_ok, runs_ok, no_code, perm, cost, elapsed,
is_<a> and the consumers), plus, app (an oracle binder applied) and site (holon.gen.lean_sites names the predicate). A
model function that takes the oracle parameters (step, run, obs, runs_ok, the site predicates, and an observer or
migration whose body reaches them) gets the law's parameter binders first. One pair of outer parentheses around a
whole application is dropped at the top of each side of a relation and in a trace's elements; an empty list carries
its type ascription.

Imports neither holon.gen.mlaws nor holon.gen.machine (rule L1).
"""
from __future__ import annotations

import copy
import json
import re

from .lean_common import Unsupported, ident
from .lean_machine import Ctx, fn_type, lean_base

_SCALAR = {"State": "Model.St", "Trace": "List Model.Act", "Act": "Model.Act", "Nat": "Nat", "Bool": "Bool",
           "List<Nat>": "List Nat"}


def strip(s: str) -> str:
    """Drop one pair of outer parentheses that encloses a whole application (never a type ascription `(x : T)`)."""
    if not (s.startswith("(") and s.endswith(")")):
        return s
    depth = 0
    for i, ch in enumerate(s):
        depth += ch in "([{"
        depth -= ch in ")]}"
        if depth == 0 and i < len(s) - 1:
            return s
        if depth == 1 and s.startswith(" : ", i):
            return s
    return s[1:-1]


def view_key(fields: list[str]) -> str:
    """A proj term's view key: its erased fields, sorted, joined by "__"."""
    return "__".join(ident("", f) for f in sorted(fields))


class Render:
    """The IR of one law as Lean text over ctx's interface (names qualified Model.<name>)."""

    def __init__(self, ctx: Ctx):
        self.ctx = ctx
        self.views: set[str] = set()
        self.sites: set[str] = set()

    # ------------------------------------------------------------------ binders
    def ty(self, t: str) -> str:
        if t.startswith("Fn<"):
            a, b = fn_type(t)
            return f"{lean_base(a)} → {lean_base(b)}"
        if t in _SCALAR:
            return _SCALAR[t]
        if t in self.ctx.records:
            return "Model." + ident("T_", t)
        raise Unsupported(f"binder type {t}")

    def binders(self, law: dict) -> tuple[list[tuple[str, str, str, str | None]], dict]:
        """[(quantifier, Lean name, Lean type, Reach hypothesis or None)] with the oracle parameters first, and the
        environment {IR name: (Lean name, IR type) | (Lean name, "Fn", (A, B))}."""
        bs = law["statement"]["binders"]
        if any(b["q"] not in ("forall", "exists") for b in bs):
            raise Unsupported("binder quantifier")
        if len({b["q"] for b in bs}) > 1:
            raise Unsupported("mixed quantifiers")
        params = self.ctx.params
        first = [b for b in bs if b["name"] in params and b["type"].replace(" ", "") == params[b["name"]].replace(" ", "")]
        env: dict = {}
        out = []
        for b in first + [b for b in bs if b not in first]:
            name, t = ident("v_", b["name"]), b["type"]
            if t.startswith("Fn<"):
                env[b["name"]] = (name, "Fn", fn_type(t))
                out.append((b["q"], name, self.ty(t), None))
            elif t == "Reach":
                if self.ctx.kind != "machine_oracle":
                    raise Unsupported("a Reach binder over a model without oracle parameters")
                if any(p not in env or env[p][1] != "Fn" for p in params):
                    raise Unsupported("a Reach binder without the oracle parameters bound")
                env[b["name"]] = (name, "State")
                pa = " ".join(env[p][0] for p in params)
                out.append((b["q"], name, "Model.St", f"Model.Reach {pa} {name}"))
            else:
                env[b["name"]] = (name, t)
                out.append((b["q"], name, self.ty(t), None))
        return out, env

    # ------------------------------------------------------------------ terms
    def parametric(self, name: str) -> bool:
        """Does model function `name` take the oracle parameters first?"""
        c = self.ctx
        if not c.params:
            return False
        if name in ("step", "run", "obs", "fn_runs_ok") or name.startswith(("site_", "hit_")):
            return True
        if name.startswith("ob_"):
            return c.reaches(c.observers[name[3:]]["body"])
        if name.startswith("mig_"):
            return any(c.reaches(x) for x in c.migrations[name[4:]]["effects"].values())
        return False

    def call(self, name: str, args: list[str], env: dict) -> str:
        head = f"Model.{name}"
        if self.parametric(name):
            for p in self.ctx.params:
                if p not in env or env[p][1] != "Fn":
                    raise Unsupported(f"{name} runs the parametric model, but the statement binds no parameter {p}")
                head += f" {env[p][0]}"
        return "(" + " ".join([head] + args) + ")"

    def expect(self, t: dict, want: str, env: dict) -> str:
        x, xt = self.term(t, env)
        if xt != want:
            raise Unsupported(f"a {xt} where {want} is expected: {json.dumps(t)[:120]}")
        return x

    def term(self, t: dict, env: dict) -> tuple[str, str]:
        c = self.ctx
        if not isinstance(t, dict):
            raise Unsupported(f"term {t!r}")
        keys = set(t)
        if "var" in t:
            v = env.get(t["var"])
            if v is None:
                raise Unsupported(f"unbound {t['var']}")
            return v[0], v[1]
        if keys == {"nat"}:
            return str(int(t["nat"])), "Nat"
        if keys == {"bool"}:
            return ("true" if t["bool"] else "false"), "Bool"
        if keys == {"nats"}:
            xs = [str(int(x)) for x in t["nats"]]
            return ("[" + ", ".join(xs) + "]" if xs else "([] : List Nat)"), "List<Nat>"
        if keys == {"s0"}:
            return "Model.s0", "State"
        if keys == {"run", "from"}:
            return self.call("run", [self.expect(t["run"], "Trace", env), self.expect(t["from"], "State", env)],
                             env), "State"
        if keys == {"step", "from"}:
            return self.call("step", [self.expect(t["step"], "Act", env), self.expect(t["from"], "State", env)],
                             env), "State"
        if keys == {"obs", "from"}:
            return self.call("obs", [self.expect(t["obs"], "Trace", env), self.expect(t["from"], "State", env)],
                             env), "Obs"
        if keys == {"trace"}:
            xs = [strip(self.expect(a, "Act", env)) for a in t["trace"]]
            return ("[" + ", ".join(xs) + "]" if xs else "([] : List Model.Act)"), "Trace"
        if keys == {"cat"}:
            if len(t["cat"]) != 2:
                raise Unsupported("cat of other than two traces")
            x, y = (self.expect(z, "Trace", env) for z in t["cat"])
            return f"({x} ++ {y})", "Trace"
        if keys == {"act", "args"}:
            act = c.actions.get(t["act"])
            if act is None or set(t["args"]) != {n for n, _ in act["inputs"]}:
                raise Unsupported(f"action term {t['act']}")
            args = [self.expect(t["args"][n], it, env) for n, it in act["inputs"]]
            head = "Model." + c.ctor(t["act"])
            return (f"({head} {' '.join(args)})" if args else head), "Act"
        if keys == {"proj", "of"}:
            if not t["proj"] or any(x not in c.stypes or x == "log" for x in t["proj"]):
                raise Unsupported(f"proj {t['proj']}")
            v = view_key(t["proj"])
            self.views.add(v)
            return f"(Model.view_{v} {self.expect(t['of'], 'State', env)})", f"V_{v}"
        if keys == {"obsv", "of"}:
            o = c.observers.get(t["obsv"])
            if o is None:
                raise Unsupported(f"observer {t['obsv']}")
            return self.call(ident("ob_", t["obsv"]), [self.expect(t["of"], "State", env)], env), o["type"]
        if "mig" in t and keys <= {"mig", "of", "args"}:
            md = c.migrations.get(t["mig"])
            if md is None or len(t.get("args", [])) != len(md.get("inputs", [])):
                raise Unsupported(f"migration {t['mig']}")
            s = self.expect(t["of"], "State", env)
            args = [self.expect(x, it, env) for (_, it), x in zip(md.get("inputs", []), t.get("args", []))]
            return self.call(ident("mig_", t["mig"]), [s] + args, env), "State"
        if keys == {"fn", "args"}:
            return self.fn(t["fn"], t["args"], env)
        if keys == {"plus"}:
            if len(t["plus"]) != 2:
                raise Unsupported("plus of other than two terms")
            x, y = (self.expect(z, "Nat", env) for z in t["plus"])
            return f"({x} + {y})", "Nat"
        if keys == {"app", "args"}:
            h = env.get(t["app"])
            if h is None or h[1] != "Fn" or len(t["args"]) != 1:
                raise Unsupported(f"application of {t['app']}")
            a, b = h[2]
            return f"({h[0]} {self.expect(t['args'][0], a, env)})", b
        if keys == {"site", "on", "from"}:
            if c.kind != "machine_oracle":
                raise Unsupported("a site term over a model without oracle parameters")
            from .lean_sites import site_name
            n = site_name(t["site"])
            self.sites.add(n)
            return self.call(n, [self.expect(t["on"], "Act", env), self.expect(t["from"], "State", env)], env), "Bool"
        raise Unsupported(f"term {sorted(t)}")

    def fn(self, name: str, args: list, env: dict) -> tuple[str, str]:
        c = self.ctx
        disch = c.facts.get("disch") or {}
        sig = {"last_ok": (["State"], "Bool"), "runs_ok": (["Trace", "State"], "Bool"),
               "no_code": (["Obs", "Nat"], "Bool"), "perm": (["Act"], "Bool")}
        if disch.get("cost") is not None:
            sig["cost"] = (["Trace"], "Nat")
        if disch.get("delay") is not None:
            sig["elapsed"] = (["Trace"], "Nat")
        sig |= {f"is_{a}": (["Act"], "Bool") for a in c.actions}
        sig |= {k: (["Act"], "List<Nat>") for k in c.consumers}
        if name not in sig or len(args) != len(sig[name][0]):
            raise Unsupported(f"model function {name}")
        xs = [self.expect(x, ty, env) for x, ty in zip(args, sig[name][0])]
        return self.call(ident("fn_", name), xs, env), sig[name][1]

    # ------------------------------------------------------------------ propositions
    def prop(self, p: dict, env: dict, negate: bool = False) -> str:
        if set(p) not in ({"eq"}, {"neq"}):
            raise Unsupported(f"premise or claim {sorted(p)}")
        op = "eq" if "eq" in p else "neq"
        if len(p[op]) != 2:
            raise Unsupported(f"{op} of other than two terms")
        x, xt = self.term(p[op][0], env)
        y, yt = self.term(p[op][1], env)
        if xt != yt:
            raise Unsupported(f"{op} of {xt} and {yt}")
        rel = "=" if (op == "eq") != negate else "≠"
        return f"{strip(x)} {rel} {strip(y)}"

    def claim(self, cl: dict, env: dict, negate: bool = False) -> str:
        if set(cl) == {"all"}:
            body = " ∧ ".join(self.prop(p, env) for p in cl["all"])
            return f"¬ ({body})" if negate else body
        return self.prop(cl, env, negate)

    @staticmethod
    def quant(q: str, bs: list, inner: str, conn: str) -> str:
        """q (b1 : T1) .. (bk : Tk), H conn q ..: one binder group up to each Reach hypothesis."""
        out, cur = [], []
        for _, name, ty, hyp in bs:
            cur.append(f"({name} : {ty})")
            if hyp:
                out.append(f"{q} {' '.join(cur)}, {hyp} {conn} ")
                cur = []
        if cur:
            out.append(f"{q} {' '.join(cur)}, ")
        return "".join(out) + inner

    def body(self, law: dict, counter: bool = False, flip: bool = False) -> str:
        """The law's proposition; counter: its counter-law (the negated claim, or with flip the claim itself)."""
        st = law["statement"]
        if (st.get("scope") or {"kind": "unbounded"}).get("kind", "unbounded") != "unbounded":
            raise Unsupported(f"scope {st['scope']}")
        bs, env = self.binders(law)
        prem = [self.prop(p, env) for p in st.get("assume", [])]
        q = bs[0][0] if bs else "forall"
        if q == "exists":
            if counter:
                raise Unsupported("the counter-law of an existential law")
            return self.quant("∃", bs, " ∧ ".join(prem + [self.claim(st["claim"], env)]), "∧")
        if counter:
            return self.quant("∃", bs, " ∧ ".join(prem + [self.claim(st["claim"], env, negate=not flip)]), "∧")
        return self.quant("∀", bs, " → ".join(prem + [self.claim(st["claim"], env)]), "→")


def law_id(law: dict) -> str:
    lid = law.get("law_id")
    if not isinstance(lid, str):
        raise Unsupported("a law without a law_id")
    return ident("", lid)


def statements(law: dict, status: str, ctx: Ctx, flip: bool = False) -> list[tuple[str, str]]:
    """[(theorem name, statement text)]: the law's theorem (PROVED), or its counter-law and refutation (REFUTED).
    flip=True renders a REFUTED law's counter-law with its claim's relation flipped (G7's flip canary)."""
    lid = law_id(law)
    r = Render(ctx)
    if status == "PROVED":
        if flip:
            raise Unsupported("the flip canary is a REFUTED law's")
        return [(lid, f"theorem {lid} : {r.body(law)}")]
    if status == "REFUTED":
        return [(f"{lid}_counter", f"theorem {lid}_counter : {r.body(law, counter=True, flip=flip)}"),
                (f"{lid}_refuted", f"theorem {lid}_refuted : ¬ ({r.body(law)})")]
    raise Unsupported(f"no statement for status {status}")


def _claim_props(claim: dict) -> list[dict]:
    return list(claim["all"]) if set(claim) == {"all"} else [claim]


def perturbed_nat(law: dict) -> tuple[dict, int, int] | None:
    """G7's perturb rule for a machine law: a copy of the law whose claim's first Nat equation (the claim, or the
    members of its "all" list in order; the first eq whose right side is a Nat literal) has its constant k replaced
    by k + 1, with k and k + 1; None when the claim has no such equation."""
    out = copy.deepcopy(law)
    for p in _claim_props(out["statement"]["claim"]):
        if set(p) == {"eq"} and len(p["eq"]) == 2 and set(p["eq"][1]) == {"nat"}:
            k = int(p["eq"][1]["nat"])
            p["eq"][1] = {"nat": k + 1}
            return out, k, k + 1
    return None


def views(law: dict) -> list[str]:
    """The views a law's statement names: every proj term's field set, sorted and joined by "__"."""
    out: set[str] = set()

    def walk(x):
        if isinstance(x, dict):
            if set(x) == {"proj", "of"} and isinstance(x["proj"], list):
                out.add(view_key(x["proj"]))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(law["statement"])
    return sorted(out)


def site_ids(law: dict) -> list[str]:
    """Every site id of a law's statement (its {"site": id, ...} terms), in pre-order."""
    out: list[str] = []

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("site"), str):
                out.append(x["site"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(law["statement"])
    return out


def value(ctx: Ctx, t: str, v) -> str:
    """A witness value of IR type t as a Lean term over the interface (Model.-qualified): Nat, Bool, List<Nat>, an
    action {"op": name, <input>: value}, a trace (a list of actions)."""
    if t == "Nat":
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise Unsupported(f"Nat witness {v!r}")
        return str(v)
    if t == "Bool":
        if not isinstance(v, bool):
            raise Unsupported(f"Bool witness {v!r}")
        return "true" if v else "false"
    if t == "List<Nat>":
        xs = [value(ctx, "Nat", x) for x in v]
        return "[" + ", ".join(xs) + "]" if xs else "([] : List Nat)"
    if t == "Act":
        if not isinstance(v, dict) or v.get("op") not in ctx.actions:
            raise Unsupported(f"action witness {json.dumps(v)[:80]}")
        act = ctx.actions[v["op"]]
        if set(v) - {"op"} != {n for n, _ in act["inputs"]}:
            raise Unsupported(f"action witness {v['op']} with inputs {sorted(set(v) - {'op'})}")
        args = [value(ctx, it, v[n]) for n, it in act["inputs"]]
        head = "Model." + ctx.ctor(v["op"])
        return f"({head} {' '.join(args)})" if args else head
    if t == "Trace":
        if not isinstance(v, list):
            raise Unsupported("a trace witness that is not a list")
        xs = [strip(value(ctx, "Act", a)) for a in v]
        return "[" + ", ".join(xs) + "]" if xs else "([] : List Model.Act)"
    if re.fullmatch(r"List<.+>", t) or t in ctx.records:
        raise Unsupported(f"a witness of type {t}")
    raise Unsupported(f"a witness of type {t}")
