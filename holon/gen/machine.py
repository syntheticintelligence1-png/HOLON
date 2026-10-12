"""Machine generator: holon-facts/0.2 state machines -> executable, provable Bend (whitepaper §8.3).

The facts describe a guarded-command machine: typed state fields, records, actions with
`guards` (lets and requires, in source order) and `effects` (parallel field updates).
Every action compiles to

    decide_<a>(reads.., inputs..) -> Dec_<a>      # guards only; `reads` = state fields the guards mention
    exec_<a>(d, fields.., inputs..) -> HSt        # effects, field by field, chosen by the decision
    step_<a>(s, inputs..) = exec_<a>(decide_<a>(..), ..)

This split is what makes non-interference provable (holon.gen.mproofs): a proof generalises
over the decision `d`, so a state component that `decide` never reads and no effect copies
into an observed field is unobservable, by construction of the proof rather than by trust.

Conventions of the generated model:
  * types are prefixed (HSt, H<Record>, HAct, HObs, ..); constructors are globally unique;
  * Nat is unbounded; `-` is truncated subtraction; checked arithmetic is an explicit require;
  * an action that fails a require leaves the state unchanged and logs O_Rev{code};
  * the log is newest-first.

Hashes and oracles as parameters (I12; M2+ milestones, holon.gen.oracles). Given an oracle sidecar, a facts
call ["call", p, x] to the parameter p of a modelled entry applies the model's oracle parameter, never a
builtin: p is an oracle table (Data, so reusable), applied by `ap_p(t, x)`. Every generated function that
evaluates such a call takes the tables it needs as trailing parameters (exec_<a> those of its effects,
decide_<a> and its chain those of its guards, d_<name>, observers and migrations those of their bodies), and
step, run, obs and runs_ok thread the tables of every parameter some action uses (`threaded`, in sidecar
order). Reach is indexed by the threaded tables too. Without a sidecar (M0, M1, and M2+ facts that have none)
the model is exactly as before.

Principal classes (I11; audit M2/1 F-M2-26). An M2+ model (Machine(m2plus=True)) takes its permissions from the
actions' permission guards, never from their labels (holon.diagram.principals.guard_classes; a label/guard
disagreement is a FactsError): `perm(a)` holds for the actions of a permissionless class (no permission guard on
the caller: the class X of DISCH), and every class c gets `perm_c(a, who)`: a is an action of class c submitted by
`who` (any `who` for the environment class, whose actions have no caller). The class's permission predicate stays
the action's own guard, checked by step. M0 and M1 models keep the M1 `perm`, from the label prefix, as bound.
"""
from __future__ import annotations

import re
from pathlib import Path

from .targetlib import Library, LibError

KEYWORDS = {"match", "case", "def", "type", "law", "for", "exs", "import", "as", "do", "return", "is", "where"}

# The generic prelude. Target libraries (holon.gen.targetlib) may add helpers in the slot between
# PRELUDE_HEAD and PRELUDE_TAIL; the generator joins the three in that order.
PRELUDE_HEAD = '''\
def ite(-A: Data, c: Bool, a: A, b: A) -> A:
  match c:
    case True{}:
      a
    case False{}:
      b

def nth_d(-A: Data, xs: List<&2, A>, i: Nat, d: A) -> A:
  match xs i:
    case Nil{} _:
      d
    case Con{h, t} 0n:
      h
    case Con{h, t} 1n+p:
      nth_d(A, t, p, d)

def set_d(-A: Data, xs: List<&2, A>, i: Nat, +v: A, +d: A) -> List<&2, A>:
  match xs i:
    case Nil{} 0n:
      [v]
    case Nil{} 1n+p:
      Con{d, set_d(A, Nil{}, p, v, d)}
    case Con{h, t} 0n:
      Con{v, t}
    case Con{h, t} 1n+p:
      Con{h, set_d(A, t, p, v, d)}

def tail0(-A: Data, xs: List<&2, A>) -> List<&2, A>:
  match xs:
    case Nil{}:
      Nil{}
    case Con{h, t}:
      t

def last_d(-A: Data, xs: List<&2, A>, d: A) -> A:
  match xs:
    case Nil{}:
      d
    case Con{h, t}:
      match t:
        case Nil{}:
          h
        case Con{h2, t2}:
          last_d(A, Con{h2, t2}, d)

def b_nth(xs: List<&2, Nat>, i: Nat) -> Nat:
  nth_d(Nat, xs, i, 0n)

def b_set_nat(xs: List<&2, Nat>, i: Nat, +v: Nat) -> List<&2, Nat>:
  set_d(Nat, xs, i, v, 0n)

def b_mem(+x: Nat, xs: List<&2, Nat>) -> Bool:
  match xs:
    case Nil{}:
      False{}
    case Con{h, t}:
      Bool.or(Nat.is_eq(x, h), b_mem(x, t))

def b_remove(+x: Nat, xs: List<&2, Nat>) -> List<&2, Nat>:
  match xs:
    case Nil{}:
      Nil{}
    case Con{+h, +t}:
      ite(List<&2, Nat>, Nat.is_eq(x, h), b_remove(x, t), Con{h, b_remove(x, t)})

'''

PRELUDE_TAIL = '''\
def b_pair(+a: Nat, +b: Nat) -> Nat:
  Nat.add(Nat.div(Nat.mul(Nat.add(a, b), Nat.add(Nat.add(a, b), 1n)), 2n), b)

def b_enc(xs: List<&2, Nat>) -> Nat:
  match xs:
    case Nil{}:
      0n
    case Con{h, t}:
      1n+b_pair(h, b_enc(t))

def b_zeros_like(xs: List<&2, Nat>) -> List<&2, Nat>:
  match xs:
    case Nil{}:
      Nil{}
    case Con{h, t}:
      Con{0n, b_zeros_like(t)}

def eq_bool(a: Bool, b: Bool) -> Bool:
  match a b:
    case True{} True{}:
      True{}
    case False{} False{}:
      True{}
    case True{} False{}:
      False{}
    case False{} True{}:
      False{}

def eq_list_nat(xs: List<&2, Nat>, ys: List<&2, Nat>) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      True{}
    case Nil{} Con{h, t}:
      False{}
    case Con{h, t} Nil{}:
      False{}
    case Con{x, xt} Con{y, yt}:
      Bool.and(Nat.is_eq(x, y), eq_list_nat(xt, yt))

def is_true(b: Bool) -> Type:
  match b:
    case True{}:
      Unit
    case False{}:
      Empty
'''


class FactsError(Exception):
    pass


def bt(t: str) -> str:
    """IR/facts type -> Bend type."""
    m = re.fullmatch(r"List<(.+)>", t)
    if m:
        return f"List<&2, {bt(m.group(1))}>"
    if t in ("Nat", "Bool"):
        return t
    if t == "State":
        return "HSt"
    if t == "Obs":
        return "HObs"
    if t == "Act":
        return "HAct"
    m = re.fullmatch(r"Tab<(\w+)>", t)   # the oracle table of parameter p (I12)
    if m:
        return f"List<&2, HO_{m.group(1)}>"
    return "H" + t


def elem(t: str) -> str:
    m = re.fullmatch(r"List<(.+)>", t)
    if not m:
        raise FactsError(f"not a list type: {t}")
    return m.group(1)


def bname(v: str) -> str:
    return v + "_" if v in KEYWORDS else v


def fresh(base: str, taken: set) -> str:
    """A generator-internal binder name that no fact name in scope uses (hygiene: an action input
    named `d` must not capture exec's decision binder)."""
    while base in taken:
        base += "_"
    return base


class Machine:
    def __init__(self, facts: dict, path: Path | str | None = None, lib: "Library | None" = None, oracles=None,
                 m2plus: bool = False):
        """`path` locates the facts' target libraries (holon.gen.targetlib); without it, only the
        global libraries in spec/lib apply. `oracles` is the facts' oracle sidecar
        (holon.gen.oracles.Oracles), passed for M2+ milestones only. `m2plus`: the model of a milestone after M1
        (its permissions come from the permission guards; module docstring)."""
        self.f = facts
        self.m2plus = m2plus
        self._pclasses: tuple | None = None
        self.params = facts.get("params", {})
        self.lib = lib if lib is not None else Library.for_facts(path, self.params)
        self.types = {k: [tuple(x) for x in v["fields"]] for k, v in facts["types"].items()}
        self.state = [(n, t) for n, t, *_ in facts["state"]]
        self.stypes = dict(self.state)
        self.shadow = facts.get("shadow", {})
        self.ghost_state = set(facts.get("ghost_state", []))
        self.defs = facts.get("defs", {})
        self.actions = facts["actions"]
        self.helpers: list[str] = []
        self.with_helpers: dict[tuple, str] = {}
        self.reads: dict[str, list[str]] = {}
        # decide chains, for proof generators: action -> {"top": [...], "helpers": [...]}
        self.chains: dict[str, dict] = {}
        if "log" not in self.stypes:
            raise FactsError("a machine needs a log field")
        self.orc = oracles
        self.oparams: dict[str, tuple[str, str]] = dict(oracles.params) if oracles is not None else {}
        self._def_uses: dict[str, set] = {}
        self.tvar: dict[str, str] = {}
        self.action_tabs: dict[str, list[str]] = {}
        self.threaded: list[str] = []
        self.fn_tabs: dict[str, list[str]] = {}
        if self.oparams:
            self._init_oracles()

    # ------------------------------------------------------------ oracle parameters (I12)
    def _init_oracles(self) -> None:
        taken = set(KEYWORDS) | {bname(n) for n, _ in self.state} | {"a", "s", "p", "r", "e", "t", "x", "k", "v", "tr",
                                                                     "rest", "d", "code", "c", "o", "l"}
        for a in self.actions:
            taken |= {bname(n) for n, _ in a["inputs"]} | {bname(g["let"]) for g in a["guards"] if "let" in g}
        for d in self.defs.values():
            taken |= {bname(n) for n, _ in d["params"]}
        for mg in self.f.get("migrations", {}).values():
            taken |= {bname(n) for n, _ in mg.get("inputs", [])}
        names = set(self.f.get("observers", {})) | {"mig_" + n for n in self.f.get("migrations", {})}
        for p, (A, B) in self.oparams.items():
            if p in self.defs:
                raise FactsError(f"oracle parameter {p} is also a facts def")
            if "O_" + p in self.types or "ap_" + p in names:
                raise FactsError(f"oracle parameter {p}: HO_{p} or ap_{p} names another definition")
            if A not in ("Nat", "Bool", "List<Nat>"):
                raise FactsError(f"oracle parameter {p}: no decidable key equality for {A}")
            self.default_of(B)
            self.tvar[p] = fresh(bname(p), taken)
            taken.add(self.tvar[p])
        for a in self.actions:
            es = [g.get("expr", g.get("require")) for g in a["guards"]] + list(a["effects"].values())
            self.action_tabs[a["name"]] = self.ordered(set().union(set(), *(self.uses(e) for e in es)))
        self.threaded = self.ordered(set().union(set(), *self.action_tabs.values()))
        self.fn_tabs = {n: list(self.threaded) for n in ("step", "run", "obs", "runs_ok")}
        for n, o in self.f.get("observers", {}).items():
            self.fn_tabs[n] = self.ordered(self.uses(o["body"]))
        for n, mg in self.f.get("migrations", {}).items():
            self.fn_tabs["mig_" + n] = self.ordered(set().union(set(), *(self.uses(e) for e in mg["effects"].values())))

    def default_of(self, ty: str) -> str:
        if ty == "Nat":
            return "0n"
        if ty == "Bool":
            return "False{}"
        if ty.startswith("List<"):
            return "Nil{}"
        if ty in self.types:
            return f"empty_{ty}()"
        raise FactsError(f"no default value for {ty}")

    def ordered(self, ps) -> list[str]:
        """Parameters in sidecar order."""
        return [p for p in self.oparams if p in ps]

    def def_uses(self, name: str) -> set:
        if name not in self._def_uses:
            self._def_uses[name] = set()   # facts defs do not recurse
            self._def_uses[name] = self.uses(self.defs[name]["body"])
        return self._def_uses[name]

    def uses(self, e) -> set:
        """The oracle parameters an expression applies, through the facts defs it calls."""
        if not self.oparams or not isinstance(e, list) or not e:
            return set()
        op, *a = e
        if op == "call":
            name, *args = a
            out = set().union(set(), *(self.uses(x) for x in args))
            if name in self.defs:
                out |= self.def_uses(name)
            elif name in self.oparams:
                out.add(name)
            return out
        if op == "get":
            return self.uses(a[0])
        if op == "mk":
            return set().union(set(), *(self.uses(x) for x in a[1].values()))
        if op == "with":
            return self.uses(a[1]).union(*(self.uses(x) for x in a[2].values()))
        if op == "list":
            return set().union(set(), *(self.uses(x) for x in a[1:]))
        return set().union(set(), *(self.uses(x) for x in a))

    def tab_env(self, ps) -> dict[str, str]:
        """Typing-environment entries of the tables of parameters ps (their variables)."""
        return {self.tvar[p]: f"Tab<{p}>" for p in self.ordered(ps)}

    def tab_params(self, ps) -> list[str]:
        return [f"+{self.tvar[p]}: {bt(f'Tab<{p}>')}" for p in self.ordered(ps)]

    def tab_args(self, ps) -> list[str]:
        return [self.tvar[p] for p in self.ordered(ps)]

    def gen_oracles(self) -> list[str]:
        """The oracle table type and lookup of every modelled parameter."""
        if not self.oparams:
            return []
        out = ["# oracle parameters (I12; holon.gen.oracles): a parameter p : Fn<A,B> is held as Data, a table of",
               "# HO_p{k, v} entries; ap_p(t, x) is the v of the first entry whose k is x, else the default of B", ""]
        eq = {"Nat": "Nat.is_eq", "Bool": "eq_bool", "List<Nat>": "eq_list_nat"}
        for p, (A, B) in self.oparams.items():
            out += [f"type HO_{p} is Data:", f"  HO_{p}{{k: {bt(A)}, v: {bt(B)}}}", "",
                    f"def ap_{p}(t: List<&2, HO_{p}>, +x: {bt(A)}) -> {bt(B)}:", "  match t:", "    case Nil{}:",
                    f"      {self.default_of(B)}", "    case Con{e, r}:", "      match e:", f"        case HO_{p}{{k, v}}:",
                    f"          ite({bt(B)}, {eq[A]}(x, k), v, ap_{p}(r, x))", ""]
        return out

    # ------------------------------------------------------------ builtins
    def builtin(self, name: str, args: list) -> tuple[str, str]:
        """(bend text, type) of a builtin call, given compiled (text, type) args."""
        txt = [a for a, _ in args]
        ty = [t for _, t in args]

        def need(n):
            if len(args) != n:
                raise FactsError(f"{name} takes {n} arguments")
        if name == "len":
            need(1)
            return f"List.length(&2, {bt(elem(ty[0]))}, {txt[0]})", "Nat"
        if name in ("take", "drop"):
            need(2)
            return f"List.{name}(&2, {bt(elem(ty[0]))}, {txt[0]}, {txt[1]})", ty[0]
        if name == "tail":
            need(1)
            return f"tail0({bt(elem(ty[0]))}, {txt[0]})", ty[0]
        if name == "concat":
            need(2)
            return f"List.append(&2, {bt(elem(ty[0]))}, {txt[0]}, {txt[1]})", ty[0]
        if name == "snoc":
            need(2)
            return f"List.append(&2, {bt(elem(ty[0]))}, {txt[0]}, [{txt[1]}])", ty[0]
        if name == "eq_nats":
            need(2)
            return f"eq_list_nat({txt[0]}, {txt[1]})", "Bool"
        if name in self.lib.builtins:
            try:
                return self.lib.render(name, txt)
            except LibError as e:
                raise FactsError(str(e)) from e
        fixed = {"nth": "Nat", "set_nat": "List<Nat>", "mem": "Bool", "remove": "List<Nat>", "zeros_like": "List<Nat>"}
        for sf, field in self.shadow.items():
            fixed[f"es_{field}"] = self.stypes[sf]
        if name in fixed:
            return f"b_{name}({', '.join(txt)})", fixed[name]
        raise FactsError(f"unknown function {name}")

    # ------------------------------------------------------------ expressions
    def ex(self, e, env: dict[str, str]) -> tuple[str, str]:
        if isinstance(e, bool):
            return ("True{}" if e else "False{}"), "Bool"
        if isinstance(e, int):
            return f"{e}n", "Nat"
        if isinstance(e, str):
            if e in env:
                return bname(e), env[e]
            if e in self.params:
                return f"{self.params[e]}n", "Nat"
            raise FactsError(f"unbound variable {e}")
        if not isinstance(e, list) or not e:
            raise FactsError(f"bad expression {e!r}")
        op, *a = e
        nat2 = {"+": "Nat.add", "-": "Nat.sub"}
        cmp2 = {"<": "Nat.is_lt", "<=": "Nat.is_le", ">": "Nat.is_gt", ">=": "Nat.is_ge", "==": "Nat.is_eq"}
        if op in nat2 or op in cmp2 or op == "!=":
            (x, tx), (y, ty) = self.ex(a[0], env), self.ex(a[1], env)
            if tx != "Nat" or ty != "Nat":
                raise FactsError(f"{op} needs Nat operands: {e}")
            if op in nat2:
                return f"{nat2[op]}({x}, {y})", "Nat"
            if op == "!=":
                return f"Bool.not(Nat.is_eq({x}, {y}))", "Bool"
            return f"{cmp2[op]}({x}, {y})", "Bool"
        if op in ("&&", "||"):
            parts = [self.ex(x, env) for x in a]
            if any(t != "Bool" for _, t in parts):
                raise FactsError(f"{op} needs Bool operands: {e}")
            fn = "Bool.and" if op == "&&" else "Bool.or"
            out = parts[-1][0]
            for p, _ in reversed(parts[:-1]):
                out = f"{fn}({p}, {out})"
            return out, "Bool"
        if op == "!":
            x, tx = self.ex(a[0], env)
            if tx != "Bool":
                raise FactsError(f"! needs Bool: {e}")
            return f"Bool.not({x})", "Bool"
        if op == "?":
            (c, tc), (x, tx), (y, ty) = (self.ex(z, env) for z in a)
            if tc != "Bool" or tx != ty:
                raise FactsError(f"ill-typed conditional {e}")
            return f"ite({bt(tx)}, {c}, {x}, {y})", tx
        if op == "call":
            name, *args = a
            cargs = [self.ex(x, env) for x in args]
            if name in self.defs:
                d = self.defs[name]
                if len(d["params"]) != len(cargs):
                    raise FactsError(f"{name}: arity")
                for (pn, pt), (_, at) in zip(d["params"], cargs):
                    if pt != at:
                        raise FactsError(f"{name}: argument {pn} is {at}, expected {pt}")
                return f"d_{name}({', '.join([x for x, _ in cargs] + self.tab_args(self.def_uses(name)))})", d["type"]
            if name in self.oparams:   # the model's oracle parameter, never a builtin (I12)
                A, B = self.oparams[name]
                if len(cargs) != 1 or cargs[0][1] != A:
                    raise FactsError(f"{name}: the oracle parameter takes one {A}, got {[t for _, t in cargs]}")
                return f"ap_{name}({self.tvar[name]}, {cargs[0][0]})", B
            return self.builtin(name, cargs)
        if op == "get":
            x, tx = self.ex(a[0], env)
            fields = dict(self.types.get(tx, []))
            if a[1] not in fields:
                raise FactsError(f"{tx} has no field {a[1]}")
            return f"g_{tx}_{a[1]}({x})", fields[a[1]]
        if op == "mk":
            ty, vals = a
            parts = []
            for fn, ft in self.types[ty]:
                if fn in vals:
                    x, tx = self.ex(vals[fn], env)
                    if tx != ft:
                        raise FactsError(f"{ty}.{fn} is {ft}, got {tx}")
                    parts.append(x)
                else:
                    parts.append("False{}" if ft == "Bool" else "0n")
            return f"H{ty}{{{', '.join(parts)}}}", ty
        if op == "with":
            ty, base, vals = a
            bx, btyp = self.ex(base, env)
            if btyp != ty:
                raise FactsError(f"with: {btyp} is not {ty}")
            keys = tuple(sorted(vals))
            h = self.with_helper(ty, keys)
            args = []
            for k in keys:
                x, tx = self.ex(vals[k], env)
                if tx != dict(self.types[ty])[k]:
                    raise FactsError(f"with {ty}.{k}: {tx}")
                args.append(x)
            return f"{h}({bx}, {', '.join(args)})", ty
        if op == "list":
            ty, *items = a
            xs = [self.ex(x, env)[0] for x in items]
            return ("[" + ", ".join(xs) + "]" if xs else "Nil{}"), f"List<{ty}>"
        raise FactsError(f"unknown operator {op}")

    def with_helper(self, ty: str, keys: tuple) -> str:
        if (ty, keys) in self.with_helpers:
            return self.with_helpers[(ty, keys)]
        name = f"with_{ty}_{'_'.join(keys)}"
        fields = self.types[ty]
        pat = ", ".join(f"o_{f}" for f, _ in fields)
        new = ", ".join(f if f in keys else f"o_{f}" for f, _ in fields)
        params = ", ".join(f"{k}: {bt(dict(fields)[k])}" for k in keys)
        self.with_helpers[(ty, keys)] = name
        self.helpers.append(f"def {name}(e: H{ty}, {params}) -> H{ty}:\n  match e:\n    case H{ty}{{{pat}}}:\n"
                            f"      H{ty}{{{new}}}\n")
        return name

    # ------------------------------------------------------------ free variables
    def fv(self, e) -> set[str]:
        if isinstance(e, bool) or isinstance(e, int):
            return set()
        if isinstance(e, str):
            return set() if e in self.params else {e}
        op, *a = e
        if op == "call":
            out = set().union(*(self.fv(x) for x in a[1:])) if len(a) > 1 else set()
            if self.oparams:   # the tables a call applies are free in it (I12)
                if a[0] in self.defs:
                    out |= set(self.tab_args(self.def_uses(a[0])))
                elif a[0] in self.oparams:
                    out.add(self.tvar[a[0]])
            return out
        if op == "get":
            return self.fv(a[0])
        if op == "mk":
            return set().union(*(self.fv(x) for x in a[1].values())) if a[1] else set()
        if op == "with":
            return self.fv(a[1]).union(*(self.fv(x) for x in a[2].values()))
        if op == "list":
            return set().union(*(self.fv(x) for x in a[1:])) if len(a) > 1 else set()
        return set().union(*(self.fv(x) for x in a))

    # ------------------------------------------------------------ records, defs
    def gen_types(self) -> list[str]:
        out = []
        for ty, fields in self.types.items():
            out += [f"type H{ty} is Data:", f"  H{ty}{{" + ", ".join(f"{f}: {bt(t)}" for f, t in fields) + "}", ""]
            for f, t in fields:
                pat = ", ".join((f"+{g}" if g == f else g) for g, _ in fields)
                out += [f"def g_{ty}_{f}(e: H{ty}) -> {bt(t)}:", "  match e:", f"    case H{ty}{{{pat}}}:", f"      {f}", ""]
        out += ["type HObs is Data:", "  O_Ok{}", "  O_Rev{code: Nat}", ""]
        out += ["type HSt is Data:", "  HSt{" + ", ".join(f"{n}: {bt(t)}" for n, t in self.state) + "}", ""]
        acts = []
        for a in self.actions:
            ins = ", ".join(f"{bname(n)}: {bt(t)}" for n, t in a["inputs"])
            acts.append(f"  A_{a['name']}{{{ins}}}")
        out += ["type HAct is Data:"] + acts + [""]
        return out

    def gen_record_lib(self) -> list[str]:
        """Empty values of every record type, then the target libraries' record blocks, in order."""
        zero = lambda t: "False{}" if t == "Bool" else ("Nil{}" if t.startswith("List<") else "0n")
        out = []
        for ty, fields in self.types.items():
            out += [f"def empty_{ty}() -> H{ty}:", f"  H{ty}{{" + ", ".join(zero(t) for _, t in fields) + "}", ""]
        for block in self.lib.record_blocks:
            if not all(ty in self.types for ty in block.get("when_types", [])):
                continue
            if block.get("emit") == "shadow_projections":
                out += self.gen_shadow_projections(block["record"])
            else:
                out += block["bend"].split("\n")
        return out

    def gen_shadow_projections(self, record: str) -> list[str]:
        """b_es_<field>: project each shadowed field out of a list of `record` values."""
        out = []
        pat = ", ".join(f for f, _ in self.types[record])
        for sf, field in self.shadow.items():
            val = self.lib.shadow_values.get(field, field)
            out += [f"def b_es_{field}(es: List<&2, H{record}>) -> {bt(self.stypes[sf])}:", "  match es:", "    case Nil{}:",
                    "      Nil{}", "    case Con{e, t}:", "      match e:", f"        case H{record}{{{pat}}}:",
                    f"          Con{{{val}, b_es_{field}(t)}}", ""]
        return out

    def gen_defs(self) -> list[str]:
        out = []
        for name, d in self.defs.items():
            env = {p: t for p, t in d["params"]}
            body, ty = self.ex(d["body"], env)
            if ty != d["type"]:
                raise FactsError(f"def {name}: body is {ty}, declared {d['type']}")
            params = ", ".join([f"+{bname(p)}: {bt(t)}" for p, t in d["params"]] + self.tab_params(self.def_uses(name)))
            out += [f"def d_{name}({params}) -> {bt(d['type'])}:", f"  {body}", ""]
        return out

    # ------------------------------------------------------------ actions
    def gen_action(self, a: dict) -> list[str]:
        name = a["name"]
        inputs = [(n, t) for n, t in a["inputs"]]
        guards = a["guards"]
        effects = a["effects"]
        for f in effects:
            if f not in self.stypes or f == "log":
                raise FactsError(f"{name}: effect on unknown field {f}")
        lets_t: dict[str, str] = {}
        # free variables used by guards (state reads) and by effects (lets carried in the decision)
        guard_fv: set[str] = set()
        let_names = []
        for gd in guards:
            if "let" in gd:
                guard_fv |= self.fv(gd["expr"])
                let_names.append(gd["let"])
            else:
                guard_fv |= self.fv(gd["require"])
        eff_fv = set().union(*(self.fv(e) for e in effects.values())) if effects else set()
        reads = [n for n, _ in self.state if n in guard_fv and n not in let_names]
        self.reads[name] = reads
        carried = [l for l in let_names if l in eff_fv]
        # oracle tables (I12): those the guards apply go to decide and its chain, those the effects apply to exec
        g_tabs = self.ordered(set().union(set(), *(self.uses(g.get("expr", g.get("require"))) for g in guards)))
        e_tabs = self.ordered(set().union(set(), *(self.uses(e) for e in effects.values())))
        # typing environment for guards
        env = {**{n: self.stypes[n] for n in reads}, **dict(inputs), **self.tab_env(g_tabs)}
        dec = f"Dec_{name}"
        rev, ok = f"D_{name}_Rev", f"D_{name}_Ok"
        # type the lets in order
        tenv = dict(env)
        for gd in guards:
            if "let" in gd:
                _, ty = self.ex(gd["expr"], tenv)
                tenv[gd["let"]] = ty
                lets_t[gd["let"]] = ty
            else:
                _, ty = self.ex(gd["require"], tenv)
                if ty != "Bool":
                    raise FactsError(f"{name}: require is {ty}")
        out = [f"type {dec} is Data:", f"  {rev}{{code: Nat}}",
               f"  {ok}{{" + ", ".join(f"{bname(l)}: {bt(lets_t[l])}" for l in carried) + "}", ""]
        # decide chain, built back to front
        chain: list[list[str]] = []
        ok_term = f"{ok}{{" + ", ".join(bname(l) for l in carried) + "}"

        def needed(rest: list, extra: set) -> set:
            s = set(extra)
            for gd in reversed(rest):
                if "let" in gd:
                    s.discard(gd["let"])
                    s |= self.fv(gd["expr"])
                else:
                    s |= self.fv(gd["require"])
            return s

        info = {"helpers": {}, "top": None}

        def seq(start: int, scope: dict, depth: int, owner: str | None = None) -> list[str]:
            """Statements for guards[start:], ending in a helper call or the Ok term."""
            lines = []
            local = dict(scope)
            lets = []
            i = start
            while i < len(guards):
                gd = guards[i]
                if "let" in gd:
                    x, ty = self.ex(gd["expr"], local)
                    lines.append(f"+{bname(gd['let'])} = {x}")
                    lets.append(gd["let"])
                    local[gd["let"]] = ty
                    i += 1
                    continue
                cond, _ = self.ex(gd["require"], local)
                live = needed(guards[i + 1:], set(carried))
                params = [v for v in local if v in live]
                hname = f"dec_{name}_{i}"
                rec = {"lets": list(lets), "let_lines": list(lines), "call": hname, "cond": cond, "cond_expr": gd["require"],
                       "guard_index": i, "args": [bname(v) for v in params]}
                if owner is None:
                    info["top"] = rec
                else:
                    info["helpers"][owner]["next"] = rec
                info["helpers"][hname] = {"params": [(v, local[v]) for v in params], "reason": gd["reason"],
                                          "guard_index": i, "next": None}
                body = seq(i + 1, {v: local[v] for v in params}, depth + 1, hname)
                plist = ", ".join(["c: Bool"] + [f"+{bname(v)}: {bt(local[v])}" for v in params])
                chain.append([f"# {gd.get('src', '')}".replace("?", ""), f"def {hname}({plist}) -> {dec}:", "  match c:",
                              "    case False{}:", f"      {rev}{{{gd['reason']}n}}", "    case True{}:"]
                             + ["      " + l for l in body] + [""])
                lines.append(f"{hname}({', '.join([cond] + [bname(v) for v in params])})")
                return lines
            lines.append(ok_term)
            return lines

        top = seq(0, env, 0)
        self.chains[name] = info
        for h in chain:  # children are appended before their callers: definition order
            out += h
        dparams = ", ".join([f"+{bname(n)}: {bt(t)}" for n, t in [(r, self.stypes[r]) for r in reads] + inputs]
                            + self.tab_params(g_tabs))
        out += [f"def decide_{name}({dparams}) -> {dec}:"] + ["  " + l for l in top] + [""]
        # exec: field-wise effects
        fparams = ", ".join(f"+{bname(n)}: {bt(t)}" for n, t in self.state)
        iparams = ", ".join(f"+{bname(n)}: {bt(t)}" for n, t in inputs)
        allp = ", ".join(p for p in (fparams, iparams, ", ".join(self.tab_params(e_tabs))) if p)
        eenv = {**self.stypes, **dict(inputs), **{l: lets_t[l] for l in carried}}
        new_fields = []
        for n, t in self.state:
            if n == "log":
                new_fields.append("Con{O_Ok{}, log}")
            elif n in effects:
                x, ty = self.ex(effects[n], eenv)
                if ty != t:
                    raise FactsError(f"{name}: effect on {n} is {ty}, field is {t}")
                new_fields.append(x)
            else:
                new_fields.append(bname(n))
        taken = {bname(n) for n, _ in self.state} | {bname(n) for n, _ in inputs} | {bname(l) for l in carried} \
            | set(self.tab_args(g_tabs + e_tabs))
        dv, cv, sv = fresh("d", taken), fresh("code", taken), fresh("s", taken)
        unchanged = ", ".join(f"Con{{O_Rev{{{cv}}}, log}}" if n == "log" else bname(n) for n, _ in self.state)
        out += [f"def exec_{name}({dv}: {dec}, {allp}) -> HSt:", f"  match {dv}:", f"    case {rev}{{{cv}}}:",
                f"      HSt{{{unchanged}}}", f"    case {ok}{{" + ", ".join("+" + bname(l) for l in carried) + "}:",
                f"      HSt{{{', '.join(new_fields)}}}", ""]
        spat = ", ".join("+" + bname(n) for n, _ in self.state)
        dargs = ", ".join([bname(x) for x in reads + [n for n, _ in inputs]] + self.tab_args(g_tabs))
        fargs = ", ".join(bname(n) for n, _ in self.state)
        a_tabs = self.ordered(set(g_tabs) | set(e_tabs))
        iparams = ", ".join(x for x in (iparams, ", ".join(self.tab_params(a_tabs))) if x)
        iargs = ", ".join([bname(n) for n, _ in inputs] + self.tab_args(e_tabs))
        out += [f"def step_{name}({sv}: HSt{', ' + iparams if iparams else ''}) -> HSt:", f"  match {sv}:", f"    case HSt{{{spat}}}:",
                f"      exec_{name}(decide_{name}({dargs}), {fargs}{', ' + iargs if iargs else ''})", ""]
        return out

    def gen_dispatch(self) -> list[str]:
        T = "".join(", " + x for x in self.tab_params(self.threaded))   # the threaded oracle tables (I12)
        TA = "".join(", " + x for x in self.tab_args(self.threaded))
        out = [f"def step(a: HAct, s: HSt{T}) -> HSt:", "  match a:"]
        for a in self.actions:
            ins = [bname(n) for n, _ in a["inputs"]]
            # pattern binders are positional: rename away from a, s (and the tables)
            ins = [fresh(i, {"a", "s"} | set(self.tab_args(self.threaded))) for i in ins]
            args = ins + self.tab_args(self.action_tabs.get(a["name"], []))
            out += [f"    case A_{a['name']}{{{', '.join('+' + i for i in ins)}}}:",
                    f"      step_{a['name']}(s{', ' + ', '.join(args) if args else ''})"]
        out += ["", f"def run(tr: List<&2, HAct>, s: HSt{T}) -> HSt:", "  match tr:", "    case Nil{}:", "      s",
                "    case Con{a, rest}:", f"      run(rest, step(a, s{TA}){TA})", ""]
        spat = ", ".join(bname(n) for n, _ in self.state)
        cleared = ", ".join("Nil{}" if n == "log" else bname(n) for n, _ in self.state)
        out += ["def clear_log(s: HSt) -> HSt:", "  match s:", f"    case HSt{{{spat}}}:", f"      HSt{{{cleared}}}", ""]
        out += ["def log_of(s: HSt) -> List<&2, HObs>:", "  match s:", f"    case HSt{{{spat}}}:", "      log", ""]
        out += ["# observations of tr from s: the log tr produces (newest first)",
                f"def obs(tr: List<&2, HAct>, s: HSt{T}) -> List<&2, HObs>:", f"  log_of(run(tr, clear_log(s){TA}))", ""]
        out += ["def ok_head(l: List<&2, HObs>) -> Bool:", "  match l:", "    case Nil{}:", "      False{}", "    case Con{o, t}:",
                "      match o:", "        case O_Ok{}:", "          True{}", "        case O_Rev{c}:", "          False{}", "",
                "# the last action applied to s succeeded", "def last_ok(s: HSt) -> Bool:", "  ok_head(log_of(s))", "",
                "def all_ok(l: List<&2, HObs>) -> Bool:", "  match l:", "    case Nil{}:", "      True{}", "    case Con{o, t}:",
                "      match o:", "        case O_Ok{}:", "          all_ok(t)", "        case O_Rev{c}:", "          False{}", "",
                "# every action of tr succeeds from s", f"def runs_ok(tr: List<&2, HAct>, s: HSt{T}) -> Bool:",
                f"  all_ok(obs(tr, s{TA}))", "",
                "def no_code(l: List<&2, HObs>, +k: Nat) -> Bool:", "  match l:", "    case Nil{}:", "      True{}",
                "    case Con{o, t}:", "      match o:", "        case O_Ok{}:", "          no_code(t, k)", "        case O_Rev{c}:",
                "          Bool.and(Bool.not(Nat.is_eq(c, k)), no_code(t, k))", "",
                "def eq_obs(a: HObs, b: HObs) -> Bool:", "  match a b:", "    case O_Ok{} O_Ok{}:", "      True{}",
                "    case O_Rev{x} O_Rev{y}:", "      Nat.is_eq(x, y)", "    case O_Ok{} O_Rev{y}:", "      False{}",
                "    case O_Rev{x} O_Ok{}:", "      False{}", "",
                "def eq_obs_list(xs: List<&2, HObs>, ys: List<&2, HObs>) -> Bool:", "  match xs ys:", "    case Nil{} Nil{}:",
                "      True{}", "    case Nil{} Con{h, t}:", "      False{}", "    case Con{h, t} Nil{}:", "      False{}",
                "    case Con{x, xt} Con{y, yt}:", "      Bool.and(eq_obs(x, y), eq_obs_list(xt, yt))", ""]
        for a in self.actions:
            out += [f"def is_{a['name']}(a: HAct) -> Bool:", "  match a:"]
            for b in self.actions:
                pat = ", ".join("_" for _ in b["inputs"])
                out += [f"    case A_{b['name']}{{{pat}}}:", f"      {'True{}' if b is a else 'False{}'}"]
            out.append("")
        # DISCH cost model: cost(tr) counts priced actions, elapsed(tr) sums the delay input
        disch = self.f.get("disch", {})
        cost, delay = disch.get("cost", {}), disch.get("delay", {})
        for fname, pick in (("cost", lambda b: f"{cost[b['name']]}n" if b["name"] in cost else None),
                            ("elapsed", lambda b: bname(delay["input"]) if b["name"] == delay.get("action") else None)):
            out += [f"def {fname}(tr: List<&2, HAct>) -> Nat:", "  match tr:", "    case Nil{}:", "      0n", "    case Con{a, rest}:",
                    "      match a:"]
            for b in self.actions:
                v = pick(b)
                ins = [bname(n) for n, _ in b["inputs"]]
                pat = ", ".join(i if (v and i == v) else "_" for i in ins)
                out += [f"        case A_{b['name']}{{{pat}}}:", f"          Nat.add({v or '0n'}, {fname}(rest))"]
            out.append("")
        for cname, c in self.f.get("consumers", {}).items():
            out += [f"# {c.get('doc', '')}".replace("?", ""), f"def {cname}(a: HAct) -> List<&2, Nat>:", "  match a:"]
            for b in self.actions:
                ins = [n for n, _ in b["inputs"]]
                pat = ", ".join(bname(i) if i == c["input"] else "_" for i in ins)
                out += [f"    case A_{b['name']}{{{pat}}}:", f"      {bname(c['input']) if c['input'] in ins else 'Nil{}'}"]
            out.append("")
        perm = self.permissionless()
        out += ["# actions of a permissionless principal class (no permission guard on the caller; "
                "holon.diagram.principals): the class X of DISCH" if self.m2plus else
                "# actions any principal may take (no role modifier): the permissionless class X of DISCH",
                "def perm(a: HAct) -> Bool:", "  match a:"]
        for b in self.actions:
            pat = ", ".join("_" for _ in b["inputs"])
            out += [f"    case A_{b['name']}{{{pat}}}:", f"      {'True{}' if b['name'] in perm else 'False{}'}"]
        out.append("")
        if self.m2plus:
            out += self.gen_perm_classes()
        return out

    # ------------------------------------------------------------ principal classes (I11; F-M2-26)
    def principal_classes(self) -> tuple[list[dict], dict[str, str]]:
        """(classes, action -> class id), from the permission guards (holon.diagram.principals.guard_classes)."""
        if self._pclasses is None:
            from ..diagram.principals import PrincipalError, guard_classes
            try:
                self._pclasses = guard_classes(self.f)
            except PrincipalError as e:
                raise FactsError(f"principal classes: {e}") from e
        return self._pclasses

    def permissionless(self) -> list[str]:
        """The actions of the permissionless class X of DISCH, in facts order: from the permission guards in an M2+
        model (a class with no guard on its caller); from the principal label (anyone, environment) in M0 and M1
        models, as M1 was bound."""
        if self.m2plus:
            classes, of = self.principal_classes()
            free = {c["id"] for c in classes if c["permissionless"]}
            return [a["name"] for a in self.actions if of[a["name"]] in free]
        return [a["name"] for a in self.actions if a.get("principal", "").startswith(("anyone", "environment"))]

    def perm_class_ids(self) -> list[str]:
        """The class ids c of the generated perm_c (M2+ models only)."""
        return [c["id"] for c in self.principal_classes()[0]] if self.m2plus else []

    def gen_perm_classes(self) -> list[str]:
        """perm_c(a, who) per principal class c: a is an action of class c whose caller input is `who` (any `who`
        for a class without a caller)."""
        classes, of = self.principal_classes()
        names = set(self.defs) | set(self.f.get("observers", {})) | {"perm"}
        by = fresh("who", {bname(n) for a in self.actions for n, _ in a["inputs"]} | {"a"})
        out = []
        for c in classes:
            name = f"perm_{c['id']}"
            if name in names:
                raise FactsError(f"principal class {c['id']}: {name} names another definition")
            if c["caller"] not in (None, "Nat"):
                raise FactsError(f"principal class {c['id']}: caller type {c['caller']} (perm_c compares Nat callers)")
            out += [f"# principal class {c['id']} ({', '.join(c['labels'])}): permission predicate "
                    f"{c['predicate_text'] or 'none'}".replace("?", ""),
                    f"def {name}(a: HAct, {by}: Nat) -> Bool:", "  match a:"]
            for b in self.actions:
                mine = of[b["name"]] == c["id"]
                ins = [n for n, _ in b["inputs"]]
                if mine and c["caller_input"] in ins:
                    pat = ", ".join(bname(n) if n == c["caller_input"] else "_" for n in ins)
                    body = f"Nat.is_eq({bname(c['caller_input'])}, {by})"
                else:
                    pat = ", ".join("_" for _ in ins)
                    body = "True{}" if mine else "False{}"
                out += [f"    case A_{b['name']}{{{pat}}}:", f"      {body}"]
            out.append("")
        return out

    def gen_observers(self) -> list[str]:
        out = []
        spat = ", ".join("+" + bname(n) for n, _ in self.state)
        for name, o in self.f.get("observers", {}).items():
            body, ty = self.ex(o["body"], dict(self.stypes))
            if ty != o["type"]:
                raise FactsError(f"observer {name}: {ty} vs {o['type']}")
            T = "".join(", " + x for x in self.tab_params(self.fn_tabs.get(name, [])))
            out += [f"# {o.get('doc', '')}".replace("?", ""), f"def {name}(s: HSt{T}) -> {bt(ty)}:", "  match s:",
                    f"    case HSt{{{spat}}}:", f"      {body}", ""]
        for name, m in self.f.get("migrations", {}).items():
            ins = [(n, t) for n, t in m.get("inputs", [])]
            env = {**self.stypes, **dict(ins)}
            new = []
            for n, t in self.state:
                if n in m["effects"]:
                    x, ty = self.ex(m["effects"][n], env)
                    if ty != t:
                        raise FactsError(f"migration {name}.{n}")
                    new.append(x)
                else:
                    new.append(bname(n))
            ip = "".join(f", +{bname(n)}: {bt(t)}" for n, t in ins) + \
                "".join(", " + x for x in self.tab_params(self.fn_tabs.get("mig_" + name, [])))
            out += [f"# migration: {m.get('doc', '')}".replace("?", ""), f"def mig_{name}(s: HSt{ip}) -> HSt:", "  match s:",
                    f"    case HSt{{{spat}}}:", f"      HSt{{{', '.join(new)}}}", ""]
        return out

    def literal(self, ty: str, v) -> str:
        if ty == "Nat":
            return f"{int(v)}n"
        if ty == "Bool":
            return "True{}" if v else "False{}"
        if ty.startswith("List<"):
            et = elem(ty)
            items = [self.literal(et, x) for x in v]
            return "[" + ", ".join(items) + "]" if items else "Nil{}"
        if ty in self.types:
            return f"H{ty}{{" + ", ".join(self.literal(ft, v.get(fn, False if ft == 'Bool' else 0)) for fn, ft in self.types[ty]) + "}"
        if ty == "Obs":
            if isinstance(v, dict):
                return "O_Ok{}" if v["$"] == "O_Ok" else f"O_Rev{{{int(v['code'])}n}}"
            return "O_Ok{}" if v == "ok" else f"O_Rev{{{int(v)}n}}"
        raise FactsError(f"no literal for {ty}")

    def gen_initial(self) -> list[str]:
        init = self.f["initial"]
        vals = [self.literal(t, init[n]) for n, t in self.state]
        return ["# initial state: " + init.get("doc", "").replace("?", ""), "def s0() -> HSt:", f"  HSt{{{', '.join(vals)}}}", ""]

    def act_literal(self, act: dict) -> str:
        """Bend literal of an action given as {"op": name, input: value, ..}."""
        a = next((x for x in self.actions if x["name"] == act["op"]), None)
        if a is None:
            raise FactsError(f"unknown action {act['op']}")
        return f"A_{a['name']}{{" + ", ".join(self.literal(t, act[n]) for n, t in a["inputs"]) + "}"

    def trace_literal(self, tr: list) -> str:
        items = [self.act_literal(a) for a in tr]
        return "[" + ", ".join(items) + "]" if items else "Nil{}"

    def gen_reach(self) -> list[str]:
        """The reachable set as an inductive predicate (whitepaper §8.3 R; I8): Reach<s> holds for s0 and
        is closed under step. The index is a parameter carrying its equation (the encoding Bend accepts
        for value-indexed families); emitted for M2+ milestones only, so gen/M0 and gen/M1 are unchanged."""
        if self.threaded:   # indexed by the threaded oracle tables too (I12)
            idx = ", ".join(f"-{self.tvar[p]}: {bt(f'Tab<{p}>')}" for p in self.threaded)
            args = ", ".join(self.tab_args(self.threaded))
            return ["# the reachable states: s0, and one step from a reachable state (I8), for given oracle tables (I12)",
                    f"type Reach<{idx}, -s: HSt> is Type:", "  R0{e: {s == s0() : HSt}}",
                    f"  RStep{{a: HAct, p: HSt, r: Reach<{args}, p>, e: {{s == step(a, p, {args}) : HSt}}}}", ""]
        return ["# the reachable states: s0, and one step from a reachable state (I8)",
                "type Reach<-s: HSt> is Type:", "  R0{e: {s == s0() : HSt}}",
                "  RStep{a: HAct, p: HSt, r: Reach<p>, e: {s == step(a, p) : HSt}}", ""]

    def generate(self, facts_sha256: str, reach: bool = False) -> str:
        body = []
        body += self.gen_types()
        body += self.gen_record_lib()
        body += self.gen_oracles()
        body += self.gen_defs()
        acts = []
        for a in self.actions:
            acts += self.gen_action(a)
        disp = self.gen_dispatch()
        obs = self.gen_observers()
        init = self.gen_initial()
        head = ["# GENERATED by holon.gen.machine from facts; do not edit (fix the generator instead).",
                f"# facts_sha256: {facts_sha256}", f"# target: {self.f['target']['repo']} @ {self.f['target']['commit']}",
                "import Base", ""]
        text = head + [PRELUDE_HEAD + "".join(self.lib.prelude) + PRELUDE_TAIL] + body + self.helpers + acts + disp + obs + init
        if reach:
            text = text + [""] + self.gen_reach()
        return "\n".join(text).rstrip() + "\n"


def generate(facts: dict, facts_sha256: str, path: Path | str | None = None, reach: bool = False, oracles=None) -> str:
    """reach: the model of an M2+ milestone (Reach, and permissions from the permission guards)."""
    return Machine(facts, path, oracles=oracles, m2plus=reach).generate(facts_sha256, reach)
