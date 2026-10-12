"""Law emitter for holon-ir/0.2 and 0.3 (state-machine laws): IR -> LAWS.bend.

Statement forms (all hashed, all frozen):
  binders  [{"q": "forall"|"exists", "name", "type"}]   types: State, Trace, Act, Nat, Bool, Fn<A,B> (0.3)
  assume   [prem]   hypotheses of a forall law (visible premise binders, never dropped)
  claim    prop | {"all": [prop, ..]}
  prop     {"eq": [term, term]}  {"neq": [term, term]} (0.3)
  prem     prop | {"cf": {"fn": h, "set": [term, ..]}} (0.3)
  term     {"var"} {"nat"} {"bool"} {"nats": [..]} {"s0": {}} {"run": T, "from": S} {"step": A, "from": S}
           {"obs": T, "from": S} {"trace": [A..]} {"cat": [T, T]} {"act": name, "args": {input: term}}
           {"proj": [fields], "of": S} {"obsv": name, "of": S} {"mig": name, "of": S, "args": [..]}
           {"fn": name, "args": [..]} {"plus": [a, b]} {"app": h, "args": [..]} (0.3)

holon-ir/0.3 (I7, whitepaper §8.9, §8.5):
  * A Fn<A,B> binder is emitted erased (`for -h: A -> B`). Bend functions are Type, never Data, so a
    binder of function type can be affine or erased but never reusable; a statement that applies h at
    two points can only reason through equations about h (probe bend/notes/p_ir03_fn_verdict).
  * An inequality a != b, and each pair {a, b} of a collision-freedom premise CF(h, S) (h(a) != h(b)),
    is rendered in decidable form `eq_T(a, b) == False{}` through the type's equality function
    (Nat.is_eq, M.eq_bool, M.eq_list_nat); the probe proves both forms agree on Nat. CF over a
    non-finite set is rejected before emission (holon.ir.check_premises).
  * IR builtins: eq_nat -> Nat.is_eq, eq_bool -> M.eq_bool, eq_nats -> M.eq_list_nat.
  * A counter-law of a conjunction states the negation of one conjunct (the failing one, chosen by
    evaluation at the witness): it implies the negation of the conjunction.
  * The negation of an existential law (for all binders, not claim) is emitted with negate=True; it is
    decided in place of the existential, which is never REFUTED (holon.mpipeline).

`proj` is the relation of a non-interference law: the state with the named fields erased.
Its View type and projection are emitted into LAWS.bend: they are part of the statement,
so a proof file can neither define nor change them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .machine import Machine, bt, bname

ALIAS = "M"


class Unsupported(Exception):
    pass


# IR builtins (holon-ir/0.3): name -> (Bend function, argument types, result type)
BUILTINS = {"eq_nat": ("Nat.is_eq", ["Nat", "Nat"], "Bool"),
            "eq_bool": (f"{ALIAS}.eq_bool", ["Bool", "Bool"], "Bool"),
            "eq_nats": (f"{ALIAS}.eq_list_nat", ["List<Nat>", "List<Nat>"], "Bool")}
# decidable equality per IR type: the builtin that renders a != b as eq(a, b) == False{}
EQ_OF = {"Nat": "eq_nat", "Bool": "eq_bool", "List<Nat>": "eq_nats"}


def fn_sig(t: str) -> tuple[str, str] | None:
    """Fn<A,B> -> (A, B), splitting at the top-level comma; None for any other type."""
    if not (t.startswith("Fn<") and t.endswith(">")):
        return None
    inner, depth = t[3:-1], 0
    for i, ch in enumerate(inner):
        depth += ch == "<"
        depth -= ch == ">"
        if ch == "," and depth == 0:
            return inner[:i].strip(), inner[i + 1:].strip()
    raise Unsupported(f"function type {t}")


_MODEL_FN = re.compile(r"(?<![\w.])(d_\w+|g_\w+|b_\w+|with_\w+|dec_\w+|decide_\w+|nth_d|set_d|ite|tail0|last_d|"
                       r"empty_\w+|eq_bool|eq_list_nat)\(")


def q(t: str) -> str:
    """Qualify generated model types and functions with the model alias."""
    t = re.sub(r"(?<![\w.])H([A-Z]\w*)", rf"{ALIAS}.H\1", t)
    t = re.sub(r"(?<![\w.])(O_Ok|O_Rev|A_\w+|D_\w+)\{", rf"{ALIAS}.\1{{", t)
    return _MODEL_FN.sub(rf"{ALIAS}.\1(", t)


@dataclass
class EmittedM:
    name: str
    text: str
    binders: list            # [(q, name, type)]
    assume: list             # [(lhs, rhs, type)] Bend texts
    claims: list             # [(lhs, rhs, type)]
    views: dict = field(default_factory=dict)   # view name -> erased fields


def reach_name(n: str) -> str:
    """The Bend binder of a Reach binder's evidence."""
    return "r_" + bname(n)


def law_name(law_id: str, counter: bool = False) -> str:
    return ("cl_" if counter else "") + law_id.lower()


class Emitter:
    def __init__(self, m: Machine):
        self.m = m
        self.views: dict[str, list] = {}
        fn_types = {"last_ok": "Bool", "runs_ok": "Bool", "no_code": "Bool", "perm": "Bool", "cost": "Nat", "elapsed": "Nat"}
        for a in m.actions:
            fn_types[f"is_{a['name']}"] = "Bool"
        for c in m.f.get("consumers", {}):
            fn_types[c] = "List<Nat>"
        self.fn_types = fn_types

    # ------------------------------------------------------------ types
    def ty(self, t: str) -> str:
        sig = fn_sig(t)
        if sig:
            return f"{self.ty(sig[0])} -> {self.ty(sig[1])}"
        return {"State": f"{ALIAS}.HSt", "Trace": f"List<&2, {ALIAS}.HAct>", "Act": f"{ALIAS}.HAct", "Nat": "Nat",
                "Bool": "Bool", "List<Nat>": "List<&2, Nat>", "Obs": f"List<&2, {ALIAS}.HObs>"}.get(t) or t

    def view(self, fields: list) -> str:
        for f in fields:
            if f not in self.m.stypes or f == "log":
                raise Unsupported(f"cannot erase {f}")
        name = "V_" + "_".join(sorted(fields))
        self.views[name] = sorted(fields)
        return name

    # ------------------------------------------------------------ terms
    def term(self, t: dict, env: dict, types: dict) -> tuple[str, str]:
        if "var" in t:
            return env[t["var"]], types[t["var"]]
        if "nat" in t:
            return f"{int(t['nat'])}n", "Nat"
        if "bool" in t:
            return ("True{}" if t["bool"] else "False{}"), "Bool"
        if "nats" in t:
            xs = [f"{int(x)}n" for x in t["nats"]]
            return ("[" + ", ".join(xs) + "]" if xs else "Nil{}"), "List<Nat>"
        if "s0" in t:
            return f"{ALIAS}.s0()", "State"
        if "run" in t:
            tr, tt = self.term(t["run"], env, types)
            s, ts = self.term(t["from"], env, types)
            self.expect(tt, "Trace", t)
            self.expect(ts, "State", t)
            return f"{ALIAS}.run({tr}, {s})", "State"
        if "step" in t:
            a, ta = self.term(t["step"], env, types)
            s, ts = self.term(t["from"], env, types)
            self.expect(ta, "Act", t)
            self.expect(ts, "State", t)
            return f"{ALIAS}.step({a}, {s})", "State"
        if "obs" in t:
            tr, tt = self.term(t["obs"], env, types)
            s, ts = self.term(t["from"], env, types)
            self.expect(tt, "Trace", t)
            self.expect(ts, "State", t)
            return f"{ALIAS}.obs({tr}, {s})", "Obs"
        if "trace" in t:
            items = []
            for a in t["trace"]:
                x, ta = self.term(a, env, types)
                self.expect(ta, "Act", t)
                items.append(x)
            return ("[" + ", ".join(items) + "]" if items else "Nil{}"), "Trace"
        if "cat" in t:
            (x, tx), (y, ty_) = (self.term(z, env, types) for z in t["cat"])
            self.expect(tx, "Trace", t)
            self.expect(ty_, "Trace", t)
            return f"List.append(&2, {ALIAS}.HAct, {x}, {y})", "Trace"
        if "act" in t:
            a = next((x for x in self.m.actions if x["name"] == t["act"]), None)
            if a is None:
                raise Unsupported(f"unknown action {t['act']}")
            args = []
            for n, ity in a["inputs"]:
                if n not in t["args"]:
                    raise Unsupported(f"{t['act']}: missing input {n}")
                x, tx = self.term(t["args"][n], env, types)
                self.expect(tx, ity, t)
                args.append(x)
            if set(t["args"]) - {n for n, _ in a["inputs"]}:
                raise Unsupported(f"{t['act']}: unknown inputs")
            return f"{ALIAS}.A_{a['name']}{{{', '.join(args)}}}", "Act"
        if "proj" in t:
            s, ts = self.term(t["of"], env, types)
            self.expect(ts, "State", t)
            v = self.view(t["proj"])
            return f"proj_{v}({s})", v
        if "obsv" in t:
            o = self.m.f.get("observers", {}).get(t["obsv"])
            if o is None:
                raise Unsupported(f"unknown observer {t['obsv']}")
            s, ts = self.term(t["of"], env, types)
            self.expect(ts, "State", t)
            return f"{ALIAS}.{t['obsv']}({s})", o["type"]
        if "mig" in t:
            mg = self.m.f.get("migrations", {}).get(t["mig"])
            if mg is None:
                raise Unsupported(f"unknown migration {t['mig']}")
            s, ts = self.term(t["of"], env, types)
            self.expect(ts, "State", t)
            args = []
            for (n, ity), x in zip(mg.get("inputs", []), t.get("args", [])):
                xt, tx = self.term(x, env, types)
                self.expect(tx, ity, t)
                args.append(xt)
            if len(args) != len(mg.get("inputs", [])):
                raise Unsupported(f"{t['mig']}: arity")
            return f"{ALIAS}.mig_{t['mig']}({', '.join([s] + args)})", "State"
        if "app" in t:
            h = t["app"]
            sig = fn_sig(types.get(h, ""))
            if sig is None:
                raise Unsupported(f"application of {h}, which is not a Fn binder")
            if len(t["args"]) != 1:
                raise Unsupported(f"{h}: Fn<A,B> takes one argument")
            x, tx = self.term(t["args"][0], env, types)
            self.expect(tx, sig[0], t)
            return f"{env[h]}({x})", sig[1]
        if "fn" in t and t["fn"] in BUILTINS:
            bfn, ats, rt = BUILTINS[t["fn"]]
            if len(t["args"]) != len(ats):
                raise Unsupported(f"{t['fn']}: arity")
            xs = []
            for x, at in zip(t["args"], ats):
                xt, tx = self.term(x, env, types)
                self.expect(tx, at, t)
                xs.append(xt)
            return f"{bfn}({', '.join(xs)})", rt
        if "fn" in t:
            name = t["fn"]
            if name not in self.fn_types:
                raise Unsupported(f"unknown model function {name}")
            args = [self.term(x, env, types)[0] for x in t["args"]]
            return f"{ALIAS}.{name}({', '.join(args)})", self.fn_types[name]
        if "plus" in t:
            (x, tx), (y, ty_) = (self.term(z, env, types) for z in t["plus"])
            self.expect(tx, "Nat", t)
            self.expect(ty_, "Nat", t)
            return f"Nat.add({x}, {y})", "Nat"
        raise Unsupported(f"term {t}")

    @staticmethod
    def expect(got: str, want: str, t) -> None:
        if got != want:
            raise Unsupported(f"ill-typed term (got {got}, want {want}): {t}")

    def prop(self, p: dict, env: dict, types: dict) -> tuple[str, str, str]:
        if set(p) == {"neq"}:
            return self.prop(self.decidable_ne(p["neq"][0], p["neq"][1], env, types), env, types)
        if set(p) != {"eq"}:
            raise Unsupported(f"proposition {p}")
        (a, ta), (b, tb) = (self.term(x, env, types) for x in p["eq"])
        if ta != tb:
            raise Unsupported(f"equation sides differ in type: {ta} / {tb}")
        return a, b, ta

    def decidable_ne(self, a: dict, b: dict, env: dict, types: dict) -> dict:
        """a != b as the IR equation eq_T(a, b) == false (T's decidable equality)."""
        ta = self.term(a, env, types)[1]
        if ta not in EQ_OF:
            raise Unsupported(f"no decidable equality for {ta}")
        return {"eq": [{"fn": EQ_OF[ta], "args": [a, b]}, {"bool": False}]}

    def premise_props(self, p: dict, env: dict, types: dict) -> list:
        """A premise as Bend equations: one, or one per pair of a CF set (in set order)."""
        if set(p) == {"cf"}:
            cf = p["cf"]
            if not isinstance(cf.get("set"), list) or not cf["set"]:
                raise Unsupported(f"cf over {cf.get('set')!r}: global injectivity is not a premise")
            if fn_sig(types.get(cf["fn"], "")) is None:
                raise Unsupported(f"cf over {cf['fn']}, which is not a Fn binder")
            S = cf["set"]
            app = lambda x: {"app": cf["fn"], "args": [x]}  # noqa: E731
            return [self.prop(self.decidable_ne(app(S[i]), app(S[j]), env, types), env, types)
                    for i in range(len(S)) for j in range(i + 1, len(S))]
        return [self.prop(p, env, types)]

    def bend_ty(self, t: str) -> str:
        return t if t.startswith("V_") else self.ty(t)

    def claims(self, st: dict, env: dict, types: dict) -> list:
        c = st["claim"]
        ps = c["all"] if "all" in c else [c]
        out = []
        for p in ps:
            out += self.premise_props(p, env, types)   # a cf claim (an inhabitant's) is one equation per pair
        return out

    # ------------------------------------------------------------ statement helpers
    def view_defs(self) -> list[str]:
        out = []
        for v, erased in sorted(self.views.items()):
            kept = [(n, t) for n, t in self.m.state if n not in erased]
            out += [f"# the relation: states equal outside {', '.join(erased)}",
                    f"type {v} is Data:", f"  {v}{{" + ", ".join(f"{bname(n)}: {q(bt(t))}" for n, t in kept) + "}", "",
                    f"def proj_{v}(s: {ALIAS}.HSt) -> {v}:", "  match s:",
                    f"    case {ALIAS}.HSt{{{', '.join(bname(n) for n, _ in self.m.state)}}}:",
                    f"      {v}{{{', '.join(bname(n) for n, _ in kept)}}}", ""]
        return out

    def emit(self, law: dict, model_import: str, counter: bool = False, note: str = "",
             conjunct: int | None = None, negate: bool = False) -> EmittedM:
        """counter: the counter-law (of conjunct `conjunct` for a conjunction); negate: the negation
        (for all binders, not claim) of an existential law, named <law_id>_neg."""
        st = law["statement"]
        binders = [(b["q"], b["name"], b["type"]) for b in st["binders"]]
        types = {n: ("State" if t == "Reach" else t) for _, n, t in binders}   # a Reach binder is a state
        env = {n: bname(n) for _, n, _ in binders}
        has_exists = any(qq == "exists" for qq, _, _ in binders)
        if has_exists and (counter or st.get("assume")):
            raise Unsupported("an existential law is never refuted (its negation is decided instead) and takes no premises")
        if negate:
            if not has_exists or any(qq == "forall" for qq, _, _ in binders):
                raise Unsupported("negation is generated for purely existential laws")
            return self.emit_negation(law, model_import, note)
        assume = [x for p in st.get("assume", []) for x in self.premise_props(p, env, types)]
        claims = self.claims(st, env, types)
        if counter and len(claims) != 1:
            if conjunct is None or not 0 <= conjunct < len(claims):
                raise Unsupported("counter-law of a conjunction needs its failing conjunct")
            claims = [claims[conjunct]]
        name = law_name(law["law_id"], counter)
        lines = ["# GENERATED by holon.gen.mlaws from the frozen law IR; do not edit.",
                 f"# law_id: {law['law_id']}   statement_hash: {note}", "import Base", f"import {model_import} as {ALIAS}", ""]
        lines += self.view_defs()
        body = [f"law {name}:"]
        for qq, n, t in binders:
            kw = "exs" if (counter or qq == "exists") else "for"
            if t == "Reach":   # the state, then its reachability evidence (I8)
                body.append(f"  {kw} {'' if kw == 'exs' else '+'}{bname(n)}: {ALIAS}.HSt")
                body.append(f"  {kw} {reach_name(n)}: {ALIAS}.Reach<{bname(n)}>")
                continue
            mode = "" if kw == "exs" else ("-" if fn_sig(t) else "+")
            body.append(f"  {kw} {mode}{bname(n)}: {self.bend_ty(t)}")
        for i, (a, b, t) in enumerate(assume):
            body.append(f"  {'exs' if counter else 'for'} h{i}: {{{a} == {b} : {self.bend_ty(t)}}}")
        if counter:
            a, b, t = claims[0]
            body.append(f"  {{{a} != {b} : {self.bend_ty(t)}}}")
        else:
            for i, (a, b, t) in enumerate(claims[:-1]):
                body.append(f"  exs c{i}: {{{a} == {b} : {self.bend_ty(t)}}}")
            a, b, t = claims[-1]
            body.append(f"  {{{a} == {b} : {self.bend_ty(t)}}}")
        lines += body
        return EmittedM(name, "\n".join(lines) + "\n", binders, assume, claims, dict(self.views))

    def negation_ir(self, law: dict) -> dict:
        """The negation of a purely existential law as IR: the same binders made universal, and the
        claim's conjuncts tested by their decidable equalities, whose conjunction is false."""
        st = law["statement"]
        types = {b["name"]: b["type"] for b in st["binders"]}
        env = {n: bname(n) for n in types}
        c = st["claim"]
        ps = c["all"] if "all" in c else [c]
        tests = []
        for p in ps:
            if set(p) != {"eq"}:
                raise Unsupported(f"negation of {sorted(p)}")
            ta = self.term(p["eq"][0], env, types)[1]
            if ta not in EQ_OF:
                raise Unsupported(f"no decidable equality for {ta}")
            tests.append({"fn": EQ_OF[ta], "args": p["eq"]})
        if len(tests) != 1:
            raise Unsupported("negation of a conjunction")
        neg = {k: v for k, v in law.items() if k not in ("notes",)}
        neg["law_id"] = law["law_id"] + "_neg"
        neg["statement"] = {"binders": [dict(b, q="forall") for b in st["binders"]], "assume": [],
                            "claim": {"eq": [tests[0], {"bool": False}]}, "scope": st.get("scope", {"kind": "unbounded"})}
        neg["notes"] = f"generated negation of {law['law_id']} (holon.gen.mlaws.negation_ir)"
        return neg

    def emit_negation(self, law: dict, model_import: str, note: str) -> EmittedM:
        return Emitter(self.m).emit(self.negation_ir(law), model_import, note=note)


# ---------------------------------------------------------------- witness literals
# Fn witnesses (holon-ir/0.3): the explorer's small function family, as Bend lambdas
FN_LITERALS = {"id": "x => x", "zero": "x => 0n", "succ": "x => 1n+x"}


def reach_chain(m: Machine, trace: list) -> str:
    """Reach evidence for run(trace, s0): R0 at s0, then one RStep per action, each equation by computation."""
    acts = [value_literal(m, "Act", a) for a in trace]
    r = f"{ALIAS}.R0{{{{==}}}}"
    for i, a in enumerate(acts):
        prev = value_literal(m, "State", {"run": trace[:i]})
        r = f"{ALIAS}.RStep{{{a}, {prev}, {r}, {{==}}}}"
    return r


def binder_parts(m: Machine, ty: str, v) -> list[str]:
    """The proof-tuple parts a witness contributes for one binder: a Reach binder gives its state and
    its evidence chain; any other binder gives its value."""
    if ty == "Reach":
        if not (isinstance(v, dict) and set(v) == {"run"}):
            raise Unsupported("a Reach witness is a trace from s0")
        return [value_literal(m, "State", v), reach_chain(m, v["run"])]
    return [value_literal(m, ty, v)]


def value_literal(m: Machine, ty: str, v) -> str:
    """Bend literal (in the LAWS/PROOF module, model alias M) of a witness value."""
    if ty == "Reach":
        return binder_parts(m, ty, v)[0]
    if fn_sig(ty):
        if fn_sig(ty) != ("Nat", "Nat") or not isinstance(v, dict) or v.get("lam") not in FN_LITERALS:
            raise Unsupported(f"no witness literal for {ty} = {v!r}")
        return f"({FN_LITERALS[v['lam']]})"
    if ty == "Nat":
        return f"{int(v)}n"
    if ty == "Bool":
        return "True{}" if v else "False{}"
    if ty == "Act":
        return q(m.act_literal(v))
    if ty == "Trace":
        items = [value_literal(m, "Act", a) for a in v]
        return "[" + ", ".join(items) + "]" if items else "Nil{}"
    if ty == "State":
        if set(v) == {"run"}:
            return f"{ALIAS}.run({value_literal(m, 'Trace', v['run'])}, {ALIAS}.s0())"
        if set(v) == {"state"}:
            st = v["state"]
            return q(f"HSt{{{', '.join(m.literal(t, st[n]) for n, t in m.state)}}}")
        raise Unsupported("state witnesses are a trace from the initial state or a full state")
    raise Unsupported(f"no witness literal for {ty}")
