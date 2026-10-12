"""Law emitter for holon-ir/0.2 (state-machine laws): IR -> LAWS.bend.

Statement forms (all hashed, all frozen):
  binders  [{"q": "forall"|"exists", "name", "type"}]   types: State, Trace, Act, Nat, Bool
  assume   [prop]   hypotheses of a forall law (visible premise binders, never dropped)
  claim    prop | {"all": [prop, ..]}
  prop     {"eq": [term, term]}
  term     {"var"} {"nat"} {"bool"} {"nats": [..]} {"s0": {}} {"run": T, "from": S} {"step": A, "from": S}
           {"obs": T, "from": S} {"trace": [A..]} {"cat": [T, T]} {"act": name, "args": {input: term}}
           {"proj": [fields], "of": S} {"obsv": name, "of": S} {"mig": name, "of": S, "args": [..]}
           {"fn": name, "args": [..]} {"plus": [a, b]}

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
        if set(p) != {"eq"}:
            raise Unsupported(f"proposition {p}")
        (a, ta), (b, tb) = (self.term(x, env, types) for x in p["eq"])
        if ta != tb:
            raise Unsupported(f"equation sides differ in type: {ta} / {tb}")
        return a, b, ta

    def bend_ty(self, t: str) -> str:
        return t if t.startswith("V_") else self.ty(t)

    def claims(self, st: dict, env: dict, types: dict) -> list:
        c = st["claim"]
        ps = c["all"] if "all" in c else [c]
        return [self.prop(p, env, types) for p in ps]

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

    def emit(self, law: dict, model_import: str, counter: bool = False, note: str = "") -> EmittedM:
        st = law["statement"]
        binders = [(b["q"], b["name"], b["type"]) for b in st["binders"]]
        types = {n: t for _, n, t in binders}
        env = {n: bname(n) for _, n, _ in binders}
        has_exists = any(qq == "exists" for qq, _, _ in binders)
        if has_exists and (counter or st.get("assume")):
            raise Unsupported("exists laws with premises or counter-laws of exists laws are not in holon-ir/0.2 M1")
        assume = [self.prop(p, env, types) for p in st.get("assume", [])]
        claims = self.claims(st, env, types)
        if counter and len(claims) != 1:
            raise Unsupported("counter-law of a conjunction")
        name = law_name(law["law_id"], counter)
        lines = ["# GENERATED by holon.gen.mlaws from the frozen law IR; do not edit.",
                 f"# law_id: {law['law_id']}   statement_hash: {note}", "import Base", f"import {model_import} as {ALIAS}", ""]
        lines += self.view_defs()
        body = [f"law {name}:"]
        for qq, n, t in binders:
            kw = "exs" if (counter or qq == "exists") else "for"
            body.append(f"  {kw} {'' if kw == 'exs' else '+'}{bname(n)}: {self.bend_ty(t)}")
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


# ---------------------------------------------------------------- witness literals
def value_literal(m: Machine, ty: str, v) -> str:
    """Bend literal (in the LAWS/PROOF module, model alias M) of a witness value."""
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
