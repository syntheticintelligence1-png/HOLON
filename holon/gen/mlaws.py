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

Hashes and oracles as parameters (I12; holon.gen.oracles). Over a model generated with an oracle sidecar
(M2+ milestones), a Fn<A,B> binder named like a modelled parameter p *is* that parameter: it is emitted as
the oracle table it ranges over (`for +p: List<&2, M.HO_p>`, Data, so reusable), `{"app": p, ..}` is the
lookup `M.ap_p(p, x)`, and every run/step/obs/obsv/mig/runs_ok term passes the tables the model function
takes (Machine.fn_tabs), each the law's binder of that name; a statement that needs a table it does not
bind is Unsupported. A premise {"hyp": {"name": H}} is rendered from H's predicate in the sidecar: its
premises, over the law's binder of H's parameter, each emitted like any other premise. A Fn binder that is
no modelled parameter keeps its I7 meaning (an erased function binder). Witness values of a parameter are
tables: a sidecar instance (resolve_param: the instance function, inst_<entry>, defined in the proof file
from the entry's template, applied at the points the statement queries) or an explicit table.

`proj` is the relation of a non-interference law: the state with the named fields erased.
Its View type and projection are emitted into LAWS.bend: they are part of the statement,
so a proof file can neither define nor change them.

I24 (rule PAR's sub-forms recompute, consumer and init): the expr term {"expr": E, "from": S [, "action": A, "on": T]
[, "bind": {name: term}]} is the value of facts expression E in state S, A's inputs taken from T (when T is an A; the
default value of E's type otherwise), the bound names shadowing inputs. It is emitted as a call of a statement helper
ex_<hash>(S[, T][, bound values]) defined in LAWS.bend from E by the model's own expression compiler
(holon.gen.machine.Machine.ex), like a proj view.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .machine import Machine, bt, bname, fresh

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
                       r"empty_\w+|eq_bool|eq_list_nat|ap_\w+)\(")


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
        for c in m.perm_class_ids():   # M2+ models: perm_<class>(a, who) (holon.gen.machine, F-M2-26)
            fn_types[f"perm_{c}"] = "Bool"
        self.fn_types = fn_types
        self.exprs: dict[str, tuple[str, str]] = {}   # I24 expr terms: helper name -> (unqualified def text, type)

    # ------------------------------------------------------------ oracle parameters (I12)
    def is_param(self, n: str, types: dict) -> bool:
        """Is binder n a modelled oracle parameter of the model (a Fn binder named like one)?"""
        t = types.get(n, "")
        if n not in self.m.oparams or not fn_sig(t):
            return False
        if fn_sig(t) != self.m.oparams[n]:
            raise Unsupported(f"binder {n}: {t} is named like the oracle parameter {n} of another type")
        return True

    def tabs(self, fn: str, env: dict, types: dict) -> str:
        """The oracle tables model function `fn` takes, as trailing arguments: the law's binders of those names."""
        out = ""
        for p in self.m.fn_tabs.get(fn, []):
            if not self.is_param(p, types):
                raise Unsupported(f"{fn} runs the parametric model, but the statement binds no oracle parameter {p}")
            out += f", {env[p]}"
        return out

    def hyp_props(self, name: str, env: dict, types: dict) -> list:
        """A {"hyp": {"name": H}} premise: H's predicate from the oracle sidecar, over the law's binder of H's
        parameter, as Bend equations."""
        orc = self.m.orc
        e = orc.hyp_entry(name) if orc is not None else None
        if e is None:
            raise Unsupported(f"hyp premise {name!r} names no modelled kind-hyp hypothesis of the oracle sidecar")
        if not self.is_param(e["parameter"]["name"], types):
            raise Unsupported(f"hyp premise {name!r} constrains {e['parameter']['name']}, which the statement does not bind")
        return [x for q_ in e["hypothesis"]["predicate"] for x in self.premise_props(q_, env, types)]

    # ------------------------------------------------------------ types
    def ty(self, t: str) -> str:
        sig = fn_sig(t)
        if sig:
            return f"{self.ty(sig[0])} -> {self.ty(sig[1])}"
        if re.fullmatch(r"Bytes\([0-9]+\)", t):   # in the 0.3 schema, with no model type yet (audit F-M2-18)
            raise Unsupported(f"{t}: Bytes(n) binders have no emitter mapping")
        if t in self.m.types:   # a record ref: the facts record type (holon.ir.check_binder_types)
            return f"{ALIAS}.H{t}"
        return {"State": f"{ALIAS}.HSt", "Trace": f"List<&2, {ALIAS}.HAct>", "Act": f"{ALIAS}.HAct", "Nat": "Nat",
                "Bool": "Bool", "List<Nat>": "List<&2, Nat>", "Obs": f"List<&2, {ALIAS}.HObs>"}.get(t) or t

    def scope_props(self, st: dict, binders: list, env: dict) -> tuple[list, list]:
        """statement.scope (0.3, whitepaper §8.6; audit F-M2-01) as equations: (premises, claim conjuncts).
        bounded{H}: every universal Trace binder p gets the premise len(p) <= H, every existential one the claim
        conjunct len(p) <= H, so the kernel checks the horizon and a witness longer than H cannot refute the law.
        at_state{ref} needs the referenced state, which nothing resolves yet: Unsupported, as is bounded{H} over a
        Reach binder (Reach carries no step count) or over a statement without a Trace binder (nothing to bound)."""
        sc = st.get("scope") or {"kind": "unbounded"}
        kind = sc.get("kind", "unbounded")
        if kind == "unbounded":
            return [], []
        if kind == "at_state":
            raise Unsupported(f"scope at_state{{{sc.get('ref')}}}: the referenced state is not resolved by any generator yet")
        if kind != "bounded" or not isinstance(sc.get("H"), int) or isinstance(sc.get("H"), bool) or sc["H"] < 0:
            raise Unsupported(f"scope {sc}")
        if any(t == "Reach" for _, _, t in binders):
            raise Unsupported("bounded scope over a Reach binder: Reach carries no step count")
        traces = [(qq, n) for qq, n, t in binders if t == "Trace"]
        if not traces:
            raise Unsupported("bounded scope bounds Trace binders, and the statement has none")
        eq = lambda n: (f"Nat.is_le(List.length(&2, {ALIAS}.HAct, {env[n]}), {int(sc['H'])}n)", "True{}", "Bool")  # noqa: E731
        return [eq(n) for qq, n in traces if qq == "forall"], [eq(n) for qq, n in traces if qq == "exists"]

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
        if "expr" in t:
            return self.expr_term(t, env, types)
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
            return f"{ALIAS}.run({tr}, {s}{self.tabs('run', env, types)})", "State"
        if "step" in t:
            a, ta = self.term(t["step"], env, types)
            s, ts = self.term(t["from"], env, types)
            self.expect(ta, "Act", t)
            self.expect(ts, "State", t)
            return f"{ALIAS}.step({a}, {s}{self.tabs('step', env, types)})", "State"
        if "obs" in t:
            tr, tt = self.term(t["obs"], env, types)
            s, ts = self.term(t["from"], env, types)
            self.expect(tt, "Trace", t)
            self.expect(ts, "State", t)
            return f"{ALIAS}.obs({tr}, {s}{self.tabs('obs', env, types)})", "Obs"
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
            return f"{ALIAS}.{t['obsv']}({s}{self.tabs(t['obsv'], env, types)})", o["type"]
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
            return f"{ALIAS}.mig_{t['mig']}({', '.join([s] + args)}{self.tabs('mig_' + t['mig'], env, types)})", "State"
        if "app" in t:
            h = t["app"]
            sig = fn_sig(types.get(h, ""))
            if sig is None:
                raise Unsupported(f"application of {h}, which is not a Fn binder")
            if len(t["args"]) != 1:
                raise Unsupported(f"{h}: Fn<A,B> takes one argument")
            x, tx = self.term(t["args"][0], env, types)
            self.expect(tx, sig[0], t)
            if self.is_param(h, types):   # the oracle table's lookup (I12)
                return f"{ALIAS}.ap_{h}({env[h]}, {x})", sig[1]
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
            return f"{ALIAS}.{name}({', '.join(args)}{self.tabs(name, env, types)})", self.fn_types[name]
        if "plus" in t:
            (x, tx), (y, ty_) = (self.term(z, env, types) for z in t["plus"])
            self.expect(tx, "Nat", t)
            self.expect(ty_, "Nat", t)
            return f"Nat.add({x}, {y})", "Nat"
        if ("site" in t or "at_site" in t) and "on" in t and "from" in t:
            # a SORT-site term (I15): the ghost predicate site_<x> of the instrumented model (holon.sorts.sites),
            # applied to the action, the state and the oracle tables the model threads. {"at_site": ID, ..} is its
            # at_site premise hit_<x> (never a frozen law's term: holon.inhabit states non-vacuity with it)
            from ..sorts.sites import SiteError, ghost_x, law_id as site_law_id
            sid = t.get("site", t.get("at_site"))
            a, ta = self.term(t["on"], env, types)
            s, ts = self.term(t["from"], env, types)
            self.expect(ta, "Act", t)
            self.expect(ts, "State", t)
            try:
                x = ghost_x(site_law_id(sid))
            except (SiteError, ValueError) as e:
                raise Unsupported(f"site term {sid!r}: {e}") from e
            tabs = ""
            for p in self.m.threaded:
                if not self.is_param(p, types):
                    raise Unsupported(f"site {sid} runs the parametric model, but the statement binds no oracle "
                                      f"parameter {p}")
                tabs += f", {env[p]}"
            return f"{ALIAS}.{'site' if 'site' in t else 'hit'}_{x}({a}, {s}{tabs})", "Bool"
        raise Unsupported(f"term {t}")

    # ------------------------------------------------------------ I24: expr terms
    def expr_term(self, t: dict, env: dict, types: dict) -> tuple[str, str]:
        """{"expr": E, "from": S [, "action": A, "on": T] [, "bind": {name: term}]}: the value of facts expression E in
        state S, the inputs of action A taken from the action T (when T is an A; the default value of E's type
        otherwise), the names in bind bound to those IR terms (they shadow inputs). Emitted as a call of a statement
        helper ex_<hash>(S[, T][, bind values in name order]) defined in LAWS.bend (expr_defs), like a proj view: part
        of the statement, so a proof file can neither define nor change it."""
        if set(t) - {"expr", "from", "action", "on", "bind"} or "from" not in t:
            raise Unsupported(f"expr term {sorted(t)}")
        if ("action" in t) != ("on" in t):
            raise Unsupported("an expr term names its action A and the action term T together")
        s, ts = self.term(t["from"], env, types)
        self.expect(ts, "State", t)
        args, act = [s], None
        if "action" in t:
            act = next((x for x in self.m.actions if x["name"] == t["action"]), None)
            if act is None:
                raise Unsupported(f"unknown action {t['action']}")
            a, ta = self.term(t["on"], env, types)
            self.expect(ta, "Act", t)
            args.append(a)
        binds = []
        bind = t.get("bind") or {}
        if not isinstance(bind, dict):
            raise Unsupported("bind is an object of IR terms")
        for n in sorted(bind):
            x, tx = self.term(bind[n], env, types)
            args.append(x)
            binds.append((n, tx))
        name, ty = self.expr_helper(t["expr"], act, binds)
        return f"{name}({', '.join(args)})", ty

    def expr_helper(self, e, act: dict | None, binds: list) -> tuple[str, str]:
        """(name, IR type) of the statement helper of expression e (machine.Machine.ex over the state fields, the
        action's inputs and the bound names, in that order of shadowing)."""
        import hashlib
        import json as _json
        from .machine import FactsError
        key = _json.dumps({"expr": e, "action": act["name"] if act else None, "bind": [list(b) for b in binds]},
                          sort_keys=True, separators=(",", ":"))
        name = "ex_" + hashlib.sha256(key.encode()).hexdigest()[:12]
        if name in self.exprs:
            return name, self.exprs[name][1]
        m = self.m
        inputs = list(act["inputs"]) if act else []
        bound = {n for n, _ in binds}
        tenv: dict[str, str] = {n: t for n, t in m.state}
        tenv.update({n: t for n, t in inputs})
        tenv.update({n: t for n, t in binds})
        if m.uses(e):
            raise Unsupported(f"expr {e}: applies an oracle parameter")
        nh = len(m.helpers)
        try:
            body, ety = m.ex(e, tenv)
        except FactsError as err:
            raise Unsupported(f"expr {e}: {err}") from err
        if len(m.helpers) != nh:   # a record helper the generated model does not define
            del m.helpers[nh:]
            raise Unsupported(f"expr {e}: needs a record helper the model does not define")
        free = m.fv(e)
        taken = {bname(n) for n in tenv} | {"st", "act"}
        st_v, act_v = fresh("st", taken - {"st"}), fresh("act", taken - {"act"})
        taken |= {st_v, act_v}
        shadow_in = {n for n, _ in inputs} | bound

        def pvar(n: str, shadowed: bool) -> str:
            if not shadowed:
                return "+" + bname(n)
            v = fresh("u_" + n, taken)
            taken.add(v)
            return "+" + v
        params = [f"+{st_v}: HSt"] + ([f"+{act_v}: HAct"] if act else []) + [f"+{bname(n)}: {bt(t)}" for n, t in binds]
        lines = [f"# the expr term {_json.dumps(e, separators=(',', ':'))} in state {st_v}"
                 + (f", the inputs of {act['name']} taken from {act_v}" if act else "")
                 + (f", {', '.join(n for n, _ in binds)} bound by the statement" if binds else ""),
                 f"def {name}({', '.join(params)}) -> {bt(ety)}:"]
        ind = 2
        if any(n in free and n not in shadow_in for n, _ in m.state):
            pat = ", ".join(pvar(n, n in shadow_in) for n, _ in m.state)
            lines += [" " * ind + f"match {st_v}:", " " * (ind + 2) + f"case HSt{{{pat}}}:"]
            ind += 4
        if act:
            lines.append(" " * ind + f"match {act_v}:")
            for a in m.actions:
                pat = ", ".join(pvar(n, (n in bound) or a is not act) for n, _ in a["inputs"])
                lines.append(" " * (ind + 2) + f"case A_{a['name']}{{{pat}}}:")
                lines.append(" " * (ind + 4) + (body if a is act else m.default_of(ety)))
        else:
            lines.append(" " * ind + body)
        self.exprs[name] = ("\n".join(lines) + "\n", ety)
        return name, ety

    def expr_defs(self, qualified: bool = True) -> list[str]:
        """The statement helpers of the expr terms emitted so far (qualified for a LAWS.bend importing the model as
        M; unqualified to append to the model itself, for the refuter)."""
        out = []
        for name in sorted(self.exprs):
            text = self.exprs[name][0]
            out += (qualify_model(self.m, text) if qualified else text).rstrip("\n").split("\n") + [""]
        return out

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
        """A premise as Bend equations: one, one per pair of a CF set (in set order), or those of a hypothesis'
        predicate (I12)."""
        if set(p) == {"hyp"}:
            return self.hyp_props(p["hyp"].get("name"), env, types)
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

    def binder_ty(self, n: str, t: str, types: dict) -> str:
        """A binder's Bend type: an oracle parameter is its table (I12)."""
        if self.is_param(n, types):
            return f"List<&2, {ALIAS}.HO_{n}>"
        return self.bend_ty(t)

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
        # oracle tables first (I12, I15): a Reach binder's evidence is indexed by them, so they are bound before it
        # wherever the IR lists them. Only when every binder has one quantifier (they commute); em.binders keeps the
        # emitted order
        if len({qq for qq, _, _ in binders}) == 1:
            binders = ([x for x in binders if self.is_param(x[1], types)]
                       + [x for x in binders if not self.is_param(x[1], types)])
        has_exists = any(qq == "exists" for qq, _, _ in binders)
        if has_exists and (counter or st.get("assume")):
            raise Unsupported("an existential law is never refuted (its negation is decided instead) and takes no premises")
        if negate:
            if not has_exists or any(qq == "forall" for qq, _, _ in binders):
                raise Unsupported("negation is generated for purely existential laws")
            return self.emit_negation(law, model_import, note)
        scope_prem, scope_conj = self.scope_props(st, binders, env)
        assume = [x for p in st.get("assume", []) for x in self.premise_props(p, env, types)] + scope_prem
        claims = scope_conj + self.claims(st, env, types)
        if counter and len(claims) != 1:
            if conjunct is None or not 0 <= conjunct < len(claims):
                raise Unsupported("counter-law of a conjunction needs its failing conjunct")
            claims = [claims[conjunct]]
        name = law_name(law["law_id"], counter)
        lines = ["# GENERATED by holon.gen.mlaws from the frozen law IR; do not edit.",
                 f"# law_id: {law['law_id']}   statement_hash: {note}", "import Base", f"import {model_import} as {ALIAS}", ""]
        lines += self.view_defs()
        lines += self.expr_defs()
        body = [f"law {name}:"]
        for qq, n, t in binders:
            kw = "exs" if (counter or qq == "exists") else "for"
            if t == "Reach":   # the state, then its reachability evidence (I8), for the law's oracle tables (I12)
                idx = "".join(f"{x.lstrip(', ')}, " for x in [self.tabs("step", env, types)] if x)
                body.append(f"  {kw} {'' if kw == 'exs' else '+'}{bname(n)}: {ALIAS}.HSt")
                body.append(f"  {kw} {reach_name(n)}: {ALIAS}.Reach<{idx}{bname(n)}>")
                continue
            param = self.is_param(n, types)
            mode = "" if kw == "exs" else ("-" if fn_sig(t) and not param else "+")
            body.append(f"  {kw} {mode}{bname(n)}: {self.binder_ty(n, t, types)}")
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


def reach_chain(m: Machine, trace: list, tabs: str = "") -> str:
    """Reach evidence for run(trace, s0): R0 at s0, then one RStep per action, each equation by computation.
    tabs: the oracle tables the model threads (I12), as trailing arguments `, t1, t2`."""
    acts = [value_literal(m, "Act", a) for a in trace]
    r = f"{ALIAS}.R0{{{{==}}}}"
    for i, a in enumerate(acts):
        prev = value_literal(m, "State", {"run": trace[:i]}, tabs)
        r = f"{ALIAS}.RStep{{{a}, {prev}, {r}, {{==}}}}"
    return r


def binder_parts(m: Machine, ty: str, v, tabs: str = "") -> list[str]:
    """The proof-tuple parts a witness contributes for one binder: a Reach binder gives its state and
    its evidence chain; any other binder gives its value."""
    if ty == "Reach":
        if not (isinstance(v, dict) and set(v) == {"run"}):
            raise Unsupported("a Reach witness is a trace from s0")
        return [value_literal(m, "State", v, tabs), reach_chain(m, v["run"], tabs)]
    return [value_literal(m, ty, v, tabs)]


def resolve_param(m: Machine, p: str, v, points: list | None, defs: dict) -> dict:
    """A recorded witness value of oracle parameter p, as the table the proof supplies (I12):
    {"instance": entry id} is the entry's instance function (its def added to `defs`, name -> text) applied at
    `points` (the points the statement queries); {"table": [[k, v], ..]} is that explicit table."""
    if not isinstance(v, dict):
        raise Unsupported(f"no witness literal for parameter {p} = {v!r}")
    if "table" in v:
        return {"$param": p, "$table": [list(x) for x in v["table"]], "$inst": None}
    if "instance" not in v or m.orc is None:
        raise Unsupported(f"no witness literal for parameter {p} = {v!r}")
    from .oracles import inst_name
    e = m.orc.by_id.get(v["instance"])
    if e is None or e.get("status") != "modelled" or e["parameter"]["name"] != p or e not in m.orc.instances(p):
        raise Unsupported(f"{v['instance']!r} is no modelled instance of parameter {p}")
    name = inst_name(e["id"])
    if points:   # the empty table needs no instance applied
        defs[name] = instance_def(m, e, name, qualified=True)
    return {"$param": p, "$table": [[k, None] for k in (points or [])], "$inst": name}


def resolve_witness(m: Machine, binders, w: dict, points: dict | None) -> dict:
    """A recorded witness with every oracle parameter's value resolved to the table the proof supplies
    (resolve_param), the instance defs it needs under "$defs". points: {parameter: [point, ..]}."""
    out, defs = dict(w), {}
    for _, n, t in binders:
        if n in m.oparams and fn_sig(t) and n in w:
            out[n] = resolve_param(m, n, w[n], (points or {}).get(n, []), defs)
    if defs:
        out["$defs"] = defs
    return out


def instance_def(m: Machine, e: dict, name: str, qualified: bool) -> str:
    """The Bend def of an entry's concrete instance, from its template (facts parameters from the machine).
    qualified: for a law or proof file that imports the model as M (model names get the alias)."""
    from .oracles import render_template
    A, B = m.oparams[e["parameter"]["name"]]
    body = render_template(e["instance"]["bend"], ["x"], m.params)
    sig = f"def {name}(x: {bt(A)}) -> {bt(B)}:"
    if qualified:
        body, sig = qualify_model(m, body), q(sig)
    return f"# the concrete instance of {e['id']} (oracle sidecar)\n{sig}\n  {body}\n"


def qualify_model(m: Machine, text: str) -> str:
    """Qualify, with the model alias, every call of a top-level definition of the generated model (prelude,
    target libraries, record helpers) and every generated type or constructor."""
    names = model_names(m)
    out = q(text)
    return re.sub(r"(?<![\w.])([A-Za-z_]\w*)\(", lambda mm: (f"{ALIAS}.{mm.group(1)}(" if mm.group(1) in names
                                                         else mm.group(0)), out)


def model_names(m: Machine) -> set:
    if getattr(m, "_model_names", None) is None:
        from .machine import PRELUDE_HEAD, PRELUDE_TAIL
        text = PRELUDE_HEAD + "".join(m.lib.prelude) + PRELUDE_TAIL + "\n".join(Machine(m.f, lib=m.lib).gen_record_lib())
        m._model_names = set(re.findall(r"^def\s+(\w+)\(", text, re.M))
    return m._model_names


def witness_tabs(m: Machine, binders, resolved: dict) -> str:
    """The table literals of the threaded parameters, from a resolved witness (for run terms in witnesses)."""
    lit = {n: value_literal(m, t, resolved[n]) for _, n, t in binders
           if isinstance(resolved.get(n), dict) and "$param" in resolved[n]}
    return "".join(f", {lit[p]}" for p in m.threaded if p in lit)


def value_literal(m: Machine, ty: str, v, tabs: str = "") -> str:
    """Bend literal (in the LAWS/PROOF module, model alias M) of a witness value. tabs: the threaded oracle
    tables, for states given as runs from s0 (I12)."""
    if ty == "Reach":
        return binder_parts(m, ty, v, tabs)[0]
    if fn_sig(ty) and isinstance(v, dict) and "$param" in v:   # an oracle table (I12; resolve_param)
        p = v["$param"]
        A, B = m.oparams[p]
        items = []
        for k, val in v["$table"]:
            kl = value_literal(m, A, k)
            items.append(f"{ALIAS}.HO_{p}{{{kl}, {v['$inst'] + '(' + kl + ')' if v['$inst'] else value_literal(m, B, val)}}}")
        return "[" + ", ".join(items) + "]" if items else "Nil{}"
    if fn_sig(ty):
        if fn_sig(ty) != ("Nat", "Nat") or not isinstance(v, dict) or v.get("lam") not in FN_LITERALS:
            raise Unsupported(f"no witness literal for {ty} = {v!r}")
        return f"({FN_LITERALS[v['lam']]})"
    if ty == "Nat":
        return f"{int(v)}n"
    if ty == "Bool":
        return "True{}" if v else "False{}"
    if ty == "List<Nat>":
        return "[" + ", ".join(f"{int(x)}n" for x in v) + "]" if v else "Nil{}"
    if ty == "Act":
        return q(m.act_literal(v))
    if ty == "Trace":
        items = [value_literal(m, "Act", a) for a in v]
        return "[" + ", ".join(items) + "]" if items else "Nil{}"
    if ty == "State":
        if set(v) == {"run"}:
            return f"{ALIAS}.run({value_literal(m, 'Trace', v['run'])}, {ALIAS}.s0(){tabs})"
        if set(v) == {"state"}:
            st = v["state"]
            return q(f"HSt{{{', '.join(m.literal(t, st[n]) for n, t in m.state)}}}")
        raise Unsupported("state witnesses are a trace from the initial state or a full state")
    raise Unsupported(f"no witness literal for {ty}")
