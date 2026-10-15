"""The Lean model of a holon-facts/0.2 machine document (I43 rule L1, kinds machine and machine_oracle; rules L2, L4).

The model reads the facts document itself, never holon.gen.machine (the Bend emitter), and the target library
through its Lean twin: hand-written target input next to the Bend library, in files <lib dir>/*.lean.json (outside
the *.lib.json glob of the generator closures). Inside `namespace Model`, in order:

  - the frozen data types, verbatim: Obs, T_<record>, St, Act (deriving DecidableEq);
  - the generic helpers, the zero records, the twin's declarations and the facts definitions, in dependency order;
  - per action the decision over the fields its guards read, its execution, its step; then step, run (a left
    fold), s0, obs, fn_runs_ok, fn_last_ok, fn_no_code, fn_perm, fn_cost, fn_elapsed, fn_is_<a>, the consumers, the
    observers ob_<o> and the migrations mig_<m>;
  - for machine_oracle the oracle parameters p_<name> first in every function whose evaluation reaches them (step,
    run, obs and fn_runs_ok always), and the site declarations holon.gen.lean_sites writes;
  - the frozen statement-level declarations, verbatim: the views V_<..> and view_<..>, and Reach (after step, s0).

Every function is structurally recursive and every condition a Bool (Nat.ble, Nat.blt, Nat.beq, &&, ||, !, bif), so
the differential samples reduce by decide. Names: the interface's fixed prefixes (rule L2); internal declarations use
prefixes that collide with no name of the frozen texts:

  hl_<name>       the generic list and Nat helpers (the Bend prelude read again)
  hz_<record>     the zero value of a record type (Nat 0, Bool false, the empty list)
  hs_<field>      the projection of a shadowed field out of a list of records (the facts' "shadow" section)
  tw_<name>       the twin's own declarations
  d_<def>         a facts definition; its parameters x_<param>
  Dc_<a>          the decision of action a (rev code | ok <carried lets>); dec_<a>, exe_<a>, stp_<a>
  r_<field>       a state field as a decision's argument; i_<input> an action or migration input; l_<let> a let

The semantics are the Bend model's (holon.gen.machine's module docstring): Nat is unbounded and - truncates; a
require that fails leaves the state unchanged but for the log, which gains `rev <reason>` (newest first); a decision
that passes applies every effect, each computed from the pre-state, and logs `ok`; fn_perm comes from the principal
label (machine) or from the permission guards, the requires that test the caller input once lets are substituted
(machine_oracle, the M2+ reading); obs runs a trace from the state with its log cleared and returns the log.

Ctx is the compiled document (names, types, the expression compiler), which lean_mlaws, lean_mproofs and lean_sites
build on.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .lean_common import Model, Unsupported, ident

LEAN_LIB_VERSION = "holon-lean-lib/0.1"
CALLER = "who"          # the caller input of a facts-0.2 action (the format's own word)
_FN = re.compile(r"Fn<(.+),(.+)>")
_LIST = re.compile(r"List<(.+)>")
_TOKEN = re.compile(r"\$\{(\w+):(\w+):([^{}]*)\}|\$(args|\d)")
_DECL = re.compile(r"(?:noncomputable\s+)?(?:def|theorem|structure|inductive|abbrev)\s+([A-Za-z_][A-Za-z0-9_]*)")

# the generic helpers: the Bend prelude (holon.gen.machine PRELUDE_HEAD/TAIL) read again, structurally recursive
PRELUDE = (
    "def hl_nthD {α : Type} : List α → Nat → α → α\n  | [], _, d => d\n  | h :: _, 0, _ => h\n"
    "  | _ :: t, i + 1, d => hl_nthD t i d",
    "def hl_setD {α : Type} : List α → Nat → α → α → List α\n  | [], 0, v, _ => [v]\n"
    "  | [], i + 1, v, d => d :: hl_setD [] i v d\n  | _ :: t, 0, v, _ => v :: t\n"
    "  | h :: t, i + 1, v, d => h :: hl_setD t i v d",
    "def hl_lastD {α : Type} : List α → α → α\n  | [], d => d\n  | [h], _ => h\n  | _ :: t, d => hl_lastD t d",
    "def hl_mem (x : Nat) : List Nat → Bool\n  | [] => false\n  | h :: t => Nat.beq x h || hl_mem x t",
    "def hl_remove (x : Nat) : List Nat → List Nat\n  | [] => []\n"
    "  | h :: t => bif Nat.beq x h then hl_remove x t else h :: hl_remove x t",
    "def hl_zeros : List Nat → List Nat\n  | [] => []\n  | _ :: t => 0 :: hl_zeros t",
    "def hl_eqNats : List Nat → List Nat → Bool\n  | [], [] => true\n"
    "  | x :: xs, y :: ys => Nat.beq x y && hl_eqNats xs ys\n  | _, _ => false",
    "def hl_pair (x y : Nat) : Nat := (x + y) * (x + y + 1) / 2 + y",
    "def hl_enc : List Nat → Nat\n  | [] => 0\n  | h :: t => 1 + hl_pair h (hl_enc t)",
    "def hl_okHead : List Obs → Bool\n  | Obs.ok :: _ => true\n  | _ => false",
    "def hl_allOk : List Obs → Bool\n  | [] => true\n  | Obs.ok :: t => hl_allOk t\n  | Obs.rev _ :: _ => false",
)


def _elem(t: str) -> str | None:
    m = _LIST.fullmatch(t)
    return m.group(1) if m else None


def _balanced_outer(x: str, o: str = "(", c: str = ")") -> bool:
    """Does the first bracket of x close at its last character?"""
    if not (x.startswith(o) and x.endswith(c)):
        return False
    depth = 0
    for i, ch in enumerate(x):
        depth += ch in "([{"
        depth -= ch in ")]}"
        if depth == 0 and i < len(x) - 1:
            return False
    return True


def paren(x: str) -> str:
    """x as an argument: an identifier, a projection chain, a numeral or a bracketed term stays; anything else is
    parenthesized."""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*|\d+", x):
        return x
    if _balanced_outer(x) or _balanced_outer(x, "[", "]"):
        return x
    return f"({x})"


def fn_type(t: str) -> tuple[str, str]:
    """An oracle parameter's Fn<A,B> as (A, B), each Nat, Bool or List<Nat>."""
    m = _FN.fullmatch(t.replace(" ", ""))
    if not m or m.group(1) not in ("Nat", "Bool", "List<Nat>") or m.group(2) not in ("Nat", "Bool", "List<Nat>"):
        raise Unsupported(f"oracle parameter type {t}")
    return m.group(1), m.group(2)


def lean_base(t: str) -> str:
    """Nat, Bool or List<Nat> as a Lean type."""
    return {"Nat": "Nat", "Bool": "Bool", "List<Nat>": "List Nat"}[t]


class Ctx:
    """One facts document compiled for Lean: kind (machine | machine_oracle), the oracle parameters {name: Fn type}
    in sidecar order, the library twin and the Bend model's stem."""

    def __init__(self, facts: dict, kind: str, params: dict[str, str], lib: dict, stem: str):
        if kind not in ("machine", "machine_oracle"):
            raise Unsupported(f"model kind {kind} is not a machine kind")
        if facts.get("facts_version") != "holon-facts/0.2":
            raise Unsupported(f"facts version {facts.get('facts_version')}")
        self.facts, self.kind, self.lib, self.stem = facts, kind, lib, stem
        self.params = dict(params or {}) if kind == "machine_oracle" else {}
        if kind == "machine_oracle" and not self.params:
            raise Unsupported("a machine_oracle model without a modelled oracle parameter")
        self.ptypes = {p: fn_type(t) for p, t in self.params.items()}
        for p in self.params:
            ident("p_", p)
        self.consts = dict(facts.get("params") or {})
        self.records = {t: [(f, ft) for f, ft in d["fields"]] for t, d in (facts.get("types") or {}).items()}
        self.state = [(s[0], s[1]) for s in facts["state"]]
        self.stypes = dict(self.state)
        if self.stypes.get("log") != "List<Obs>":
            raise Unsupported("a machine needs a log field of type List<Obs>")
        self.actions = {a["name"]: a for a in facts["actions"]}
        self.defs = dict(facts.get("defs") or {})
        self.observers = dict(facts.get("observers") or {})
        self.migrations = dict(facts.get("migrations") or {})
        self.consumers = dict(facts.get("consumers") or {})
        self.shadow = dict(facts.get("shadow") or {})
        self.builtins = dict(lib.get("builtins") or {})
        for n in list(self.records) + list(self.stypes) + list(self.actions) + list(self.defs) + \
                list(self.observers) + list(self.migrations) + list(self.consumers):
            ident("", n)
        for p in self.params:
            if p in self.defs:
                raise Unsupported(f"oracle parameter {p} is also a facts definition")
        self._def_reach: dict[str, bool] = {}
        self._acts: dict[str, dict] = {}

    # ------------------------------------------------------------------ names and types
    def ty(self, facts_type: str) -> str:
        """A facts type as a Lean type, unqualified (inside namespace Model): Nat, Bool, List .., T_<record>, St."""
        t = facts_type
        if t in ("Nat", "Bool"):
            return t
        if t == "Obs":
            return "Obs"
        if t == "State":
            return "St"
        if t == "Act":
            return "Act"
        e = _elem(t)
        if e is not None:
            inner = self.ty(e)
            return f"List {inner}" if e in ("Nat", "Bool", "Obs") or e in self.records else f"List ({inner})"
        if t in self.records:
            return ident("T_", t)
        raise Unsupported(f"facts type {t}")

    def def_name(self, d: str) -> str:
        """The Lean name of facts definition d."""
        if d not in self.defs:
            raise Unsupported(f"no facts definition {d}")
        return ident("d_", d)

    def def_params(self, d: str) -> list[tuple[str, str]]:
        """Facts definition d's parameters: [(name, facts type)]."""
        if d not in self.defs:
            raise Unsupported(f"no facts definition {d}")
        return [(p, t) for p, t in self.defs[d]["params"]]

    def ctor(self, a: str) -> str:
        """The Act constructor of action a: Act.a_<a>."""
        if a not in self.actions:
            raise Unsupported(f"no action {a}")
        return "Act." + ident("a_", a)

    def inp(self, n: str) -> str:
        """The binder of action input n: i_<n>."""
        return ident("i_", n)

    def field(self, s_term: str, f: str) -> str:
        """State field f of the state term s_term: <s_term>.f_<f>."""
        if f not in self.stypes:
            raise Unsupported(f"no state field {f}")
        return f"{paren(s_term)}.{ident('f_', f)}"

    def pbinders(self) -> str:
        """The oracle-parameter binders "(p_<name> : A → B) ..", or "" without parameters."""
        return " ".join(f"(p_{p} : {lean_base(a)} → {lean_base(b)})" for p, (a, b) in self.ptypes.items())

    def pargs(self) -> str:
        """The oracle-parameter arguments " p_<name> ..", or "" without parameters."""
        return "".join(f" p_{p}" for p in self.params)

    def pre(self, reach: bool) -> str:
        """The parameter binders of a function that reaches the oracle (with a trailing space), else ""."""
        return self.pbinders() + " " if reach and self.params else ""

    def parg(self, reach: bool) -> str:
        """The parameter arguments of a call of a function that reaches the oracle, else ""."""
        return self.pargs() if reach else ""

    # ------------------------------------------------------------------ oracle reach
    def reaches(self, e) -> bool:
        """Does facts expression e apply an oracle parameter, directly or through the definitions it calls?"""
        if not self.params:
            return False
        if isinstance(e, list) and e:
            if e[0] == "call" and len(e) > 1:
                if e[1] in self.params or (e[1] in self.defs and self.def_reaches(e[1])):
                    return True
                return any(self.reaches(x) for x in e[2:])
            if e[0] == "mk":
                return any(self.reaches(x) for x in e[2].values())
            if e[0] == "with":
                return self.reaches(e[2]) or any(self.reaches(x) for x in e[3].values())
            return any(self.reaches(x) for x in e[1:])
        return False

    def def_reaches(self, d: str) -> bool:
        """Does facts definition d apply an oracle parameter?"""
        if d not in self._def_reach:
            self._def_reach[d] = False      # facts definitions do not recurse
            self._def_reach[d] = self.reaches(self.defs[d]["body"])
        return self._def_reach[d]

    # ------------------------------------------------------------------ the expression compiler
    def expr(self, e, env: dict[str, tuple[str, str]]) -> tuple[str, str]:
        """A facts expression as (Lean term, facts type); env maps a facts variable to (Lean term, facts type).
        Conditions compile to Bool terms, never to Prop."""
        if isinstance(e, bool):
            return ("true" if e else "false"), "Bool"
        if isinstance(e, int):
            if e < 0:
                raise Unsupported(f"negative literal {e}")
            return str(e), "Nat"
        if isinstance(e, str):
            if e in env:
                return env[e]
            if e in self.consts:
                v = self.consts[e]
                if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                    raise Unsupported(f"facts parameter {e} = {v!r}")
                return str(v), "Nat"
            raise Unsupported(f"unbound variable {e}")
        if not isinstance(e, list) or not e or not isinstance(e[0], str):
            raise Unsupported(f"expression {json.dumps(e)[:80]}")
        op, a = e[0], e[1:]
        cmp = {"<": ("Nat.blt", False), "<=": ("Nat.ble", False), ">": ("Nat.blt", True), ">=": ("Nat.ble", True),
               "==": ("Nat.beq", False)}
        if op in ("+", "-") or op in cmp or op == "!=":
            if len(a) != 2:
                raise Unsupported(f"{op} of {len(a)} operands")
            (x, tx), (y, ty) = self.expr(a[0], env), self.expr(a[1], env)
            if tx != "Nat" or ty != "Nat":
                raise Unsupported(f"{op} of {tx} and {ty}")
            if op in ("+", "-"):
                return f"({x} {op} {y})", "Nat"
            if op == "!=":
                return f"(!(Nat.beq {paren(x)} {paren(y)}))", "Bool"
            fn, swap = cmp[op]
            if swap:
                x, y = y, x
            return f"({fn} {paren(x)} {paren(y)})", "Bool"
        if op in ("&&", "||"):
            if not a:
                raise Unsupported(f"{op} without operands")
            parts = [self.expr(x, env) for x in a]
            if any(t != "Bool" for _, t in parts):
                raise Unsupported(f"{op} of non-Bool operands")
            out = parts[-1][0]
            for p, _ in reversed(parts[:-1]):
                out = f"({p} {op} {out})"
            return out, "Bool"
        if op == "!":
            x, tx = self.expr(a[0], env)
            if tx != "Bool" or len(a) != 1:
                raise Unsupported("! of a non-Bool")
            return f"(!{paren(x)})", "Bool"
        if op == "?":
            if len(a) != 3:
                raise Unsupported("? of other than three operands")
            (c, tc), (x, tx), (y, ty) = (self.expr(z, env) for z in a)
            if tc != "Bool" or tx != ty:
                raise Unsupported("an ill-typed conditional")
            return f"(bif {c} then {x} else {y})", tx
        if op == "call":
            return self._call(a[0], a[1:], env)
        if op == "get":
            x, tx = self.expr(a[0], env)
            fields = dict(self.records.get(tx, []))
            if a[1] not in fields:
                raise Unsupported(f"{tx} has no field {a[1]}")
            return f"{paren(x)}.{ident('f_', a[1])}", fields[a[1]]
        if op == "mk":
            rt, vals = a[0], a[1]
            if rt not in self.records or set(vals) - {f for f, _ in self.records[rt]}:
                raise Unsupported(f"mk of {rt} with fields {sorted(vals)}")
            parts = []
            for f, ft in self.records[rt]:
                if f in vals:
                    x, tx = self.expr(vals[f], env)
                    if tx != ft:
                        raise Unsupported(f"{rt}.{f} is {ft}, got {tx}")
                else:
                    x = self.zero(ft)
                parts.append(f"{ident('f_', f)} := {x}")
            return f"({{ {', '.join(parts)} }} : {self.ty(rt)})", rt
        if op == "with":
            rt, base, vals = a[0], a[1], a[2]
            bx, bt = self.expr(base, env)
            if bt != rt or rt not in self.records:
                raise Unsupported(f"with: {bt} is not {rt}")
            fields = dict(self.records[rt])
            parts = []
            for k in sorted(vals):
                if k not in fields:
                    raise Unsupported(f"with {rt}.{k}")
                x, tx = self.expr(vals[k], env)
                if tx != fields[k]:
                    raise Unsupported(f"with {rt}.{k}: {tx}")
                parts.append(f"{ident('f_', k)} := {x}")
            return f"({{ {paren(bx)} with {', '.join(parts)} }} : {self.ty(rt)})", rt
        if op == "list":
            et, items = a[0], a[1:]
            xs = []
            for x in items:
                v, tv = self.expr(x, env)
                if tv != et:
                    raise Unsupported(f"a {tv} in a list of {et}")
                xs.append(v)
            lt = f"List<{et}>"
            return ("[" + ", ".join(xs) + "]" if xs else f"([] : {self.ty(lt)})"), lt
        raise Unsupported(f"operator {op}")

    def zero(self, t: str) -> str:
        """The zero of a facts type: 0, false, the empty list, a record's hz_<record>."""
        if t == "Nat":
            return "0"
        if t == "Bool":
            return "false"
        if _elem(t) is not None:
            return f"([] : {self.ty(t)})"
        if t in self.records:
            return ident("hz_", t)
        raise Unsupported(f"no zero of {t}")

    def _call(self, name: str, args: list, env: dict) -> tuple[str, str]:
        cargs = [self.expr(x, env) for x in args]
        txt = [paren(x) for x, _ in cargs]
        tys = [t for _, t in cargs]
        if name in self.defs:
            ps = self.def_params(name)
            if len(ps) != len(cargs) or any(pt != at for (_, pt), at in zip(ps, tys)):
                raise Unsupported(f"call of {name} with arguments {tys}")
            head = self.def_name(name) + self.parg(self.def_reaches(name))
            return f"({' '.join([head] + txt)})", self.defs[name]["type"]
        if name in self.params:
            a, b = self.ptypes[name]
            if tys != [a]:
                raise Unsupported(f"the oracle parameter {name} applied to {tys}")
            return f"(p_{name} {txt[0]})", b

        def need(n: int):
            if len(cargs) != n:
                raise Unsupported(f"{name} takes {n} arguments")

        def lst(i: int) -> str:
            e = _elem(tys[i])
            if e is None:
                raise Unsupported(f"{name}: argument {i} is not a list")
            return e
        if name == "len":
            need(1)
            lst(0)
            return f"(List.length {txt[0]})", "Nat"
        if name in ("take", "drop"):
            need(2)
            lst(0)
            if tys[1] != "Nat":
                raise Unsupported(f"{name} by a {tys[1]}")
            return f"(List.{name} {txt[1]} {txt[0]})", tys[0]
        if name == "tail":
            need(1)
            lst(0)
            return f"(List.tail {txt[0]})", tys[0]
        if name == "concat":
            need(2)
            lst(0)
            if tys[1] != tys[0]:
                raise Unsupported("concat of different lists")
            return f"({txt[0]} ++ {txt[1]})", tys[0]
        if name == "snoc":
            need(2)
            if lst(0) != tys[1]:
                raise Unsupported("snoc of a different element")
            return f"({txt[0]} ++ [{cargs[1][0]}])", tys[0]
        if name in self.builtins:
            return self._builtin(name, txt)
        fixed = {"eq_nats": (["List<Nat>", "List<Nat>"], "Bool", "hl_eqNats"),
                 "nth": (["List<Nat>", "Nat"], "Nat", None), "set_nat": (["List<Nat>", "Nat", "Nat"], "List<Nat>", None),
                 "mem": (["Nat", "List<Nat>"], "Bool", "hl_mem"), "remove": (["Nat", "List<Nat>"], "List<Nat>", "hl_remove"),
                 "zeros_like": (["List<Nat>"], "List<Nat>", "hl_zeros")}
        for sf, fld in self.shadow.items():
            fixed[f"es_{fld}"] = ([f"List<{self.shadow_record()}>"], self.stypes[sf], ident("hs_", fld))
        if name in fixed:
            want, res, fn = fixed[name]
            if tys != want:
                raise Unsupported(f"{name} of {tys}")
            if name == "nth":
                return f"(hl_nthD {txt[0]} {txt[1]} 0)", res
            if name == "set_nat":
                return f"(hl_setD {txt[0]} {txt[1]} {txt[2]} 0)", res
            return f"({' '.join([fn] + txt)})", res
        raise Unsupported(f"unknown function {name}")

    def _builtin(self, name: str, txt: list[str]) -> tuple[str, str]:
        b = self.builtins[name]
        if b.get("arity") is not None and b["arity"] != len(txt):
            raise Unsupported(f"{name} takes {b['arity']} arguments")

        def sub(m: re.Match) -> str:
            if m.group(1):
                if m.group(1) != "param":
                    raise Unsupported(f"template field {m.group(1)}")
                v = self.consts.get(m.group(2), m.group(3))
                if isinstance(v, bool) or not re.fullmatch(r"\d+", str(v)):
                    raise Unsupported(f"facts parameter {m.group(2)} = {v!r}")
                return str(v)
            if m.group(4) == "args":
                return " ".join(txt)
            i = int(m.group(4))
            if i >= len(txt):
                raise Unsupported(f"{name}: template argument ${i}")
            return txt[i]
        return _TOKEN.sub(sub, b["lean"]), b["type"]

    def builtin_kind(self, name: str) -> tuple[str | None, str | None]:
        """A twin builtin's kind (nth_default, set_default, default) and default builtin, as the Bend library's."""
        b = self.builtins.get(name) or {}
        return b.get("kind"), b.get("default")

    def shadow_record(self) -> str:
        """The record type the shadow projections read (the twin's)."""
        r = (self.lib.get("shadow") or {}).get("record")
        if not r or r not in self.records:
            raise Unsupported("shadow projections without a twin record")
        return r

    # ------------------------------------------------------------------ actions
    def free(self, e, out: set) -> set:
        """The variables an expression mentions (facts parameters excluded)."""
        if isinstance(e, str):
            if e not in self.consts:
                out.add(e)
        elif isinstance(e, list) and e:
            op = e[0]
            if op == "call":
                for x in e[2:]:
                    self.free(x, out)
            elif op == "get":
                self.free(e[1], out)
            elif op == "mk":
                for x in e[2].values():
                    self.free(x, out)
            elif op == "with":
                self.free(e[2], out)
                for x in e[3].values():
                    self.free(x, out)
            elif op == "list":
                for x in e[2:]:
                    self.free(x, out)
            else:
                for x in e[1:]:
                    self.free(x, out)
        return out

    def action(self, a: str) -> dict:
        """Action a compiled: {"reads": the state fields its guards read (state order), "inputs", "g_inputs" and
        "e_inputs": the inputs its guards and its effects use (input order), "lets": {let: facts type}, "carried":
        the lets its effects use (guard order), "g_reach", "e_reach": whether its guards, its effects apply an oracle
        parameter}. dec_<a> takes the read fields and g_inputs, exe_<a> the decision, the state and e_inputs."""
        if a in self._acts:
            return self._acts[a]
        if a not in self.actions:
            raise Unsupported(f"no action {a}")
        act = self.actions[a]
        inputs = [(n, t) for n, t in act["inputs"]]
        for n, _ in inputs:
            ident("i_", n)
        bound = {n for n, _ in inputs}
        reads: set = set()
        lets: dict[str, str] = {}
        order: list[str] = []
        env = {n: (ident("r_", n), t) for n, t in self.state}
        env.update({n: (ident("i_", n), t) for n, t in inputs})
        for g in act["guards"]:
            e = g["expr"] if "let" in g else g.get("require")
            if e is None:
                raise Unsupported(f"{a}: a guard that is neither a let nor a require")
            reads |= self.free(e, set()) - bound
            _, t = self.expr(e, env)
            if "let" in g:
                if g["let"] in lets:
                    raise Unsupported(f"{a}: let {g['let']} bound twice")
                lets[g["let"]] = t
                order.append(g["let"])
                bound.add(g["let"])
                env[g["let"]] = (ident("l_", g["let"]), t)
            elif t != "Bool":
                raise Unsupported(f"{a}: a require of type {t}")
        if reads - set(self.stypes):
            raise Unsupported(f"{a}: guards read unbound {sorted(reads - set(self.stypes))}")
        for f in act["effects"]:
            if f not in self.stypes or f == "log":
                raise Unsupported(f"{a}: an effect on {f}")
        eff_free: set = set()
        for x in act["effects"].values():
            self.free(x, eff_free)
        carried = [x for x in order if x in eff_free]
        g_free: set = set()
        for g in act["guards"]:
            self.free(g["expr"] if "let" in g else g["require"], g_free)
        out = {"reads": [n for n, _ in self.state if n in reads], "inputs": inputs, "lets": lets, "carried": carried,
               "g_inputs": [(n, t) for n, t in inputs if n in g_free],
               "e_inputs": [(n, t) for n, t in inputs if n in eff_free and n not in carried],
               "g_reach": any(self.reaches(g.get("expr", g.get("require"))) for g in act["guards"]),
               "e_reach": any(self.reaches(x) for x in act["effects"].values())}
        self._acts[a] = out
        return out

    def guard_walk(self, a: str, upto: int, s_term: str) -> list[tuple[str, str, str]]:
        """Action a's guards before index upto, in source order, over the state term s_term: ("let", name, term) or
        ("require", Bool term, revert code). A let's name is its Lean binder l_<let>, which later terms use; an input
        is i_<input>; an oracle parameter p_<name>."""
        info = self.action(a)
        act = self.actions[a]
        env = {n: (self.field(s_term, n), t) for n, t in self.state}
        env.update({n: (ident("i_", n), t) for n, t in info["inputs"]})
        out = []
        for g in act["guards"][:upto]:
            if "let" in g:
                x, t = self.expr(g["expr"], env)
                out.append(("let", ident("l_", g["let"]), x))
                env[g["let"]] = (ident("l_", g["let"]), t)
            else:
                x, _ = self.expr(g["require"], env)
                out.append(("require", x, str(int(g["reason"]))))
        return out

    def stp_reach(self, a: str) -> bool:
        """Does action a's step take the oracle parameters (its guards or its effects apply one)?"""
        info = self.action(a)
        return info["g_reach"] or info["e_reach"]

    def perm_actions(self) -> list[str]:
        """The permissionless actions, in facts order: by principal label (anyone, environment) in a machine model;
        by permission guard in a machine_oracle one (the action has no caller input, or no require tests the caller
        once lets are substituted)."""
        out = []
        for name, act in self.actions.items():
            if self.kind == "machine":
                if str(act.get("principal", "")).startswith(("anyone", "environment")):
                    out.append(name)
                continue
            if CALLER not in {n for n, _ in act["inputs"]}:
                out.append(name)
                continue
            deps: dict[str, set] = {}
            tested = False
            for g in act["guards"]:
                e = g["expr"] if "let" in g else g["require"]
                fv = self.free(e, set())
                names = fv.union(*(deps.get(v, set()) for v in fv))
                if "let" in g:
                    deps[g["let"]] = names
                elif CALLER in names:
                    tested = True
            if not tested:
                out.append(name)
        return out


# ---------------------------------------------------------------------- the library twin
def lib_twin(anchor_facts: Path, root: Path) -> dict:
    """The Lean twin of the target libraries that apply to a facts document: <anchor's dir>/../lib/*.lean.json and
    spec/lib/*.lean.json, merged in that order. anchor_facts: the document the libraries are found from (a law's
    facts; for an extracted view, the law's own facts document, not the view)."""
    root = Path(root)
    anchor = Path(anchor_facts)
    if not anchor.is_absolute():
        anchor = root / anchor
    mine = anchor.parent.parent / "lib"
    files = sorted(mine.glob("*.lean.json"))
    glob = root / "spec" / "lib"
    if mine.resolve() != glob.resolve():
        files += sorted(glob.glob("*.lean.json"))
    out: dict = {"decls": [], "builtins": {}, "shadow": {}}
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("lean_lib_version") != LEAN_LIB_VERSION:
            raise Unsupported(f"{f.name}: lean_lib_version {d.get('lean_lib_version')!r}")
        for k, b in (d.get("builtins") or {}).items():
            if k in out["builtins"]:
                raise Unsupported(f"builtin {k} defined by two twins")
            out["builtins"][k] = b
        out["decls"] += list(d.get("decls") or [])
        if d.get("shadow"):
            if out["shadow"]:
                raise Unsupported("two twins declare shadow projections")
            out["shadow"] = d["shadow"]
    return out


# ---------------------------------------------------------------------- the frozen declarations
def frozen_types(ctx: Ctx) -> list[str]:
    """Obs, T_<record> (facts order), St, Act: the interface's frozen texts (rule L2)."""
    out = ["inductive Obs where\n  | ok\n  | rev (code : Nat)\nderiving DecidableEq"]
    for t, fields in ctx.records.items():
        fl = "\n".join(f"  {ident('f_', f)} : {ctx.ty(ft)}" for f, ft in fields)
        out.append(f"structure {ident('T_', t)} where\n{fl}\nderiving DecidableEq")
    fl = "\n".join(f"  {ident('f_', n)} : {ctx.ty(t)}" for n, t in ctx.state)
    out.append(f"structure St where\n{fl}\nderiving DecidableEq")
    alts = []
    for a in ctx.actions.values():
        ins = "".join(f" ({ident('i_', n)} : {ctx.ty(t)})" for n, t in a["inputs"])
        alts.append(f"  | {ident('a_', a['name'])}{ins}")
    out.append("inductive Act where\n" + "\n".join(alts) + "\nderiving DecidableEq")
    return out


def view_decls(ctx: Ctx, v: str) -> list[str]:
    """V_<v> and view_<v> for the view erasing the fields of v (joined by "__"), the interface's frozen texts."""
    erased = v.split("__")
    for x in erased:
        if x not in ctx.stypes or x == "log":
            raise Unsupported(f"a view erasing {x}")
    kept = [(n, t) for n, t in ctx.state if n not in erased]
    fl = "\n".join(f"  {ident('f_', n)} : {ctx.ty(t)}" for n, t in kept)
    body = ", ".join(f"{ident('f_', n)} := s.{ident('f_', n)}" for n, _ in kept)
    vn = "__".join(ident("", x) for x in erased)
    return [f"structure V_{vn} where\n{fl}", f"def view_{vn} (s : St) : V_{vn} :=\n  {{ {body} }}"]


def reach_decl(ctx: Ctx) -> str:
    """Reach, indexed by the oracle parameters (machine_oracle): the interface's frozen text."""
    if not ctx.params:
        raise Unsupported("Reach over a model without oracle parameters")
    pa = " ".join(f"p_{p}" for p in ctx.params)
    return (f"inductive Reach {ctx.pbinders()} : St → Prop where\n  | r0 : Reach {pa} s0\n"
            f"  | rstep (a : Act) (s : St) : Reach {pa} s → Reach {pa} (step {pa} a s)")


# ---------------------------------------------------------------------- the model
def def_order(ctx: Ctx) -> list[str]:
    """The facts definitions, each after the definitions its body calls, otherwise in facts order."""
    def calls(e, out: set) -> set:
        if isinstance(e, list):
            if len(e) > 1 and e[0] == "call" and isinstance(e[1], str):
                out.add(e[1])
            for x in e[1:]:
                calls(x, out)
        elif isinstance(e, dict):
            for x in e.values():
                calls(x, out)
        return out
    names = list(ctx.defs)
    deps = {n: {c for c in calls(ctx.defs[n]["body"], set()) if c in ctx.defs and c != n} for n in names}
    out: list[str] = []
    while len(out) < len(names):
        nxt = next((n for n in names if n not in out and deps[n] <= set(out)), None)
        if nxt is None:
            raise Unsupported(f"facts definitions call each other in a cycle: {sorted(set(names) - set(out))}")
        out.append(nxt)
    return out


def literal(ctx: Ctx, t: str, v) -> str:
    """A Lean literal of facts type t (s0's values; Obs as "ok", a code, or {"$": "O_Ok"} / {"code": k})."""
    if t == "Nat":
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise Unsupported(f"Nat literal {v!r}")
        return str(v)
    if t == "Bool":
        return "true" if v else "false"
    if t == "Obs":
        if v == "ok" or (isinstance(v, dict) and v.get("$") == "O_Ok"):
            return "Obs.ok"
        code = v.get("code", v.get("rev")) if isinstance(v, dict) else v
        return f"(Obs.rev {int(code)})"
    e = _elem(t)
    if e is not None:
        xs = [literal(ctx, e, x) for x in v]
        return "[" + ", ".join(xs) + "]" if xs else f"([] : {ctx.ty(t)})"
    if t in ctx.records:
        parts = [f"{ident('f_', f)} := {literal(ctx, ft, v.get(f, False if ft == 'Bool' else 0))}"
                 for f, ft in ctx.records[t]]
        return f"({{ {', '.join(parts)} }} : {ctx.ty(t)})"
    raise Unsupported(f"no literal of {t}")


def _helpers(ctx: Ctx) -> list[str]:
    out = list(PRELUDE)
    for t, fields in ctx.records.items():
        parts = ", ".join(f"{ident('f_', f)} := {ctx.zero(ft)}" for f, ft in fields)
        out.append(f"def {ident('hz_', t)} : {ctx.ty(t)} := {{ {parts} }}")
    for d in ctx.lib.get("decls") or []:
        if all(t in ctx.records for t in d.get("when_types", [])):
            out.append(d["lean"])
    sh = ctx.lib.get("shadow") or {}
    if ctx.shadow and sh and all(t in ctx.records for t in sh.get("when_types", [sh.get("record")])):
        rec = ctx.shadow_record()
        vals = sh.get("values") or {}
        for sf, fld in ctx.shadow.items():
            if _elem(ctx.stypes[sf]) is None:
                raise Unsupported(f"shadow field {sf} is not a list")
            if fld in vals:
                v = vals[fld].replace("$0", "e")
            elif fld in dict(ctx.records[rec]):
                v = f"e.{ident('f_', fld)}"
            else:
                raise Unsupported(f"shadow field {fld} of {rec}")
            name = ident("hs_", fld)
            out.append(f"def {name} : List {ctx.ty(rec)} → {ctx.ty(ctx.stypes[sf])}\n  | [] => []\n"
                       f"  | e :: t => {v} :: {name} t")
    return out


def _defs(ctx: Ctx) -> list[str]:
    out = []
    for name in def_order(ctx):
        d = ctx.defs[name]
        env = {p: (ident("x_", p), t) for p, t in d["params"]}
        body, t = ctx.expr(d["body"], env)
        if t != d["type"]:
            raise Unsupported(f"definition {name}: body is {t}, declared {d['type']}")
        ps = [f"({ident('x_', p)} : {ctx.ty(pt)})" for p, pt in d["params"]]
        head = " ".join(x for x in [ctx.pre(ctx.def_reaches(name)).strip()] + ps if x)
        out.append(f"def {ctx.def_name(name)}{' ' + head if head else ''} : {ctx.ty(d['type'])} :=\n  {body}")
    return out


def decision_lines(ctx: Ctx, a: str) -> list[str]:
    """The body of dec_<a>: the guards in order (a let some later guard or an effect reads, or `bif !c then
    Dc_<a>.rev k else`), then the ok."""
    info = ctx.action(a)
    dc = f"Dc_{ident('', a)}"
    env = {n: (ident("r_", n), ctx.stypes[n]) for n in info["reads"]}
    env.update({n: (ident("i_", n), t) for n, t in info["inputs"]})
    guards = ctx.actions[a]["guards"]
    live, need = [], set(info["carried"])       # a let no later guard and no effect reads is dropped (pure)
    for g in reversed(guards):
        if "let" in g:
            live.append(g["let"] in need)
            if g["let"] in need:
                need.discard(g["let"])
                ctx.free(g["expr"], need)
        else:
            live.append(True)
            ctx.free(g["require"], need)
    live.reverse()
    lines = []
    for g, keep in zip(guards, live):
        if "let" in g and not keep:
            continue
        if "let" in g:
            x, t = ctx.expr(g["expr"], env)
            lines.append(f"  let {ident('l_', g['let'])} := {x}")
            env[g["let"]] = (ident("l_", g["let"]), t)
        else:
            c, _ = ctx.expr(g["require"], env)
            lines.append(f"  bif !{paren(c)} then {dc}.rev {int(g['reason'])} else")
    lines.append("  " + " ".join([f"{dc}.ok"] + [ident("l_", c) for c in info["carried"]]))
    return lines


def _action_decls(ctx: Ctx, a: str) -> list[str]:
    info = ctx.action(a)
    act = ctx.actions[a]
    an = ident("", a)
    dc = f"Dc_{an}"
    car = info["carried"]
    ok_fields = "".join(f" ({ident('l_', c)} : {ctx.ty(info['lets'][c])})" for c in car)
    out = [f"inductive {dc} where\n  | rev (code : Nat)\n  | ok{ok_fields}"]
    ps = [f"({ident('r_', n)} : {ctx.ty(ctx.stypes[n])})" for n in info["reads"]] + \
        [f"({ident('i_', n)} : {ctx.ty(t)})" for n, t in info["g_inputs"]]
    head = " ".join(x for x in [ctx.pre(info["g_reach"]).strip()] + ps if x)
    out.append(f"def dec_{an}{' ' + head if head else ''} : {dc} :=\n" + "\n".join(decision_lines(ctx, a)))
    eenv = {n: (f"s.{ident('f_', n)}", t) for n, t in ctx.state}
    eenv.update({n: (ident("i_", n), t) for n, t in info["inputs"]})
    eenv.update({c: (ident("l_", c), info["lets"][c]) for c in car})
    upd = []
    for n, t in ctx.state:
        if n in act["effects"]:
            x, tx = ctx.expr(act["effects"][n], eenv)
            if tx != t:
                raise Unsupported(f"{a}: the effect on {n} is {tx}, the field is {t}")
            upd.append(f"{ident('f_', n)} := {x}")
    upd.append("f_log := Obs.ok :: s.f_log")
    eps = [f"({ident('i_', n)} : {ctx.ty(t)})" for n, t in info["e_inputs"]]
    ehead = " ".join(x for x in [ctx.pre(info["e_reach"]).strip(), f"(d : {dc})", "(s : St)"] + eps if x)
    okpat = " ".join([f"{dc}.ok"] + [ident("l_", c) for c in car])
    out.append(f"def exe_{an} {ehead} : St :=\n  match d with\n"
               f"  | {dc}.rev c => {{ s with f_log := Obs.rev c :: s.f_log }}\n"
               f"  | {okpat} => {{ s with {', '.join(upd)} }}")
    ups = [f"({ident('i_', n)} : {ctx.ty(t)})" for n, t in info["inputs"] if n in used_inputs(info)]
    shead = " ".join(x for x in [ctx.pre(ctx.stp_reach(a)).strip(), "(s : St)"] + ups if x)
    dargs = [f"s.{ident('f_', n)}" for n in info["reads"]] + [ident("i_", n) for n, _ in info["g_inputs"]]
    dcall = " ".join([f"dec_{an}{ctx.parg(info['g_reach'])}"] + dargs)
    iargs = "".join(f" {ident('i_', n)}" for n, _ in info["e_inputs"])
    out.append(f"def stp_{an} {shead} : St :=\n  exe_{an}{ctx.parg(info['e_reach'])} ({dcall}) s{iargs}")
    return out


def used_inputs(info: dict) -> set:
    """The inputs an action's decision or execution uses (stp_<a> takes them, in input order)."""
    return {n for n, _ in info["g_inputs"]} | {n for n, _ in info["e_inputs"]}


def act_pat(ctx: Ctx, a: str, keep: set | None = None) -> str:
    """The pattern of action a's constructor, its inputs bound as i_<n> where in keep (all when keep is None)."""
    xs = [ident("i_", n) if keep is None or n in keep else "_" for n, _ in ctx.actions[a]["inputs"]]
    return " ".join([ctx.ctor(a)] + xs)


def _dispatch(ctx: Ctx) -> list[str]:
    P, PA = ctx.pre(True), ctx.parg(True)
    out = []
    alts = []
    for a in ctx.actions:
        info = ctx.action(a)
        used = used_inputs(info)
        iargs = "".join(f" {ident('i_', n)}" for n, _ in info["inputs"] if n in used)
        alts.append(f"  | {act_pat(ctx, a, used)} => stp_{ident('', a)}{ctx.parg(ctx.stp_reach(a))} s{iargs}")
    out.append(f"def step {P}(a : Act) (s : St) : St :=\n  match a with\n" + "\n".join(alts))
    out.append(f"def run {P}: List Act → St → St\n  | [], s => s\n  | a :: r, s => run{PA} r (step{PA} a s)")
    init = ctx.facts["initial"]
    vals = ", ".join(f"{ident('f_', n)} := {literal(ctx, t, init[n])}" for n, t in ctx.state)
    out.append(f"def s0 : St := {{ {vals} }}")
    out.append(f"def obs {P}(tr : List Act) (s : St) : List Obs :=\n  (run{PA} tr {{ s with f_log := [] }}).f_log")
    out.append(f"def fn_runs_ok {P}(tr : List Act) (s : St) : Bool := hl_allOk (obs{PA} tr s)")
    out.append("def fn_last_ok (s : St) : Bool := hl_okHead s.f_log")
    out.append("def fn_no_code : List Obs → Nat → Bool\n  | [], _ => true\n  | Obs.ok :: t, k => fn_no_code t k\n"
               "  | Obs.rev c :: t, k => !(Nat.beq c k) && fn_no_code t k")
    perm = set(ctx.perm_actions())
    out.append("def fn_perm : Act → Bool\n" + "\n".join(
        f"  | {act_pat(ctx, a, set())} => {'true' if a in perm else 'false'}" for a in ctx.actions))
    disch = ctx.facts.get("disch") or {}
    if disch.get("cost") is not None:
        cost = disch["cost"]
        alts = [f"  | {act_pat(ctx, a, set())} :: r => {int(cost.get(a, 0))} + fn_cost r" for a in ctx.actions]
        out.append("def fn_cost : List Act → Nat\n  | [] => 0\n" + "\n".join(alts))
    if disch.get("delay") is not None:
        dl = disch["delay"]
        alts = []
        for a in ctx.actions:
            if a == dl.get("action"):
                if dict(ctx.actions[a]["inputs"]).get(dl.get("input")) != "Nat":
                    raise Unsupported(f"delay input {dl.get('input')}")
                alts.append(f"  | {act_pat(ctx, a, {dl['input']})} :: r => {ident('i_', dl['input'])} + fn_elapsed r")
            else:
                alts.append(f"  | {act_pat(ctx, a, set())} :: r => 0 + fn_elapsed r")
        out.append("def fn_elapsed : List Act → Nat\n  | [] => 0\n" + "\n".join(alts))
    for a in ctx.actions:
        alts = [f"  | {act_pat(ctx, a, set())} => true"]
        if len(ctx.actions) > 1:
            alts.append("  | _ => false")
        out.append(f"def fn_is_{ident('', a)} : Act → Bool\n" + "\n".join(alts))
    for c, cd in ctx.consumers.items():
        alts = []
        for a, act in ctx.actions.items():
            ins = dict(act["inputs"])
            if cd["input"] in ins:
                if ins[cd["input"]] != "List<Nat>":
                    raise Unsupported(f"consumer {c} reads a {ins[cd['input']]}")
                alts.append(f"  | {act_pat(ctx, a, {cd['input']})} => {ident('i_', cd['input'])}")
            else:
                alts.append(f"  | {act_pat(ctx, a, set())} => []")
        out.append(f"def {ident('fn_', c)} : Act → List Nat\n" + "\n".join(alts))
    return out


def _observers(ctx: Ctx) -> list[str]:
    out = []
    senv = {n: (f"s.{ident('f_', n)}", t) for n, t in ctx.state}
    for o, od in ctx.observers.items():
        if [p[1] for p in od.get("params", [])] != ["State"]:
            raise Unsupported(f"observer {o} with parameters {od.get('params')}")
        body, t = ctx.expr(od["body"], senv)
        if t != od["type"]:
            raise Unsupported(f"observer {o}: {t}, declared {od['type']}")
        out.append(f"def {ident('ob_', o)} {ctx.pre(ctx.reaches(od['body']))}(s : St) : {ctx.ty(t)} :=\n  {body}")
    for m, md in ctx.migrations.items():
        ins = [(n, t) for n, t in md.get("inputs", [])]
        if set(md["effects"]) - set(ctx.stypes) or "log" in md["effects"]:
            raise Unsupported(f"migration {m} writes an unknown field or the log")
        env = dict(senv)
        env.update({n: (ident("i_", n), t) for n, t in ins})
        upd = []
        for n, t in ctx.state:
            if n in md["effects"]:
                x, tx = ctx.expr(md["effects"][n], env)
                if tx != t:
                    raise Unsupported(f"migration {m}.{n}: {tx}")
                upd.append(f"{ident('f_', n)} := {x}")
        reach = any(ctx.reaches(x) for x in md["effects"].values())
        ips = "".join(f" ({ident('i_', n)} : {ctx.ty(t)})" for n, t in ins)
        body = f"{{ s with {', '.join(upd)} }}" if upd else "s"
        out.append(f"def {ident('mig_', m)} {ctx.pre(reach)}(s : St){ips} : St :=\n  {body}")
    return out


def model(ctx: Ctx, views: list[str], site_decls: list[str]) -> Model:
    """The Lean model of ctx's document: views (V-keys: erased field names, sorted, joined by "__"), and the site
    declarations of holon.gen.lean_sites (machine_oracle only), placed before the views and Reach."""
    decls = frozen_types(ctx) + _helpers(ctx) + _defs(ctx)
    for a in ctx.actions:
        decls += _action_decls(ctx, a)
    decls += _dispatch(ctx) + _observers(ctx)
    if site_decls and ctx.kind != "machine_oracle":
        raise Unsupported("site declarations over a model without oracle parameters")
    decls += list(site_decls)
    for v in sorted(set(views)):
        decls += view_decls(ctx, v)
    if ctx.kind == "machine_oracle":
        decls.append(reach_decl(ctx))
    names = []
    for d in decls:
        m = _DECL.match(d)
        if not m:
            raise Unsupported(f"a model declaration that is not a def, structure or inductive: {d[:60]!r}")
        names.append(m.group(1))
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        raise Unsupported(f"the model declares {dup} twice")
    return Model(stem=ctx.stem, decls=tuple(decls))


# ---------------------------------------------------------------------- for the proof classes
def decl_names(decls: list[str] | tuple[str, ...]) -> list[str]:
    """The names of a model's top-level declarations, in order."""
    out = []
    for d in decls:
        m = _DECL.match(d)
        if m:
            out.append(m.group(1))
    return out


def qualify(text: str, names: set[str]) -> str:
    """A term written inside namespace Model, written for use after `end Model`: every identifier that names a
    top-level model declaration (not after a dot) gets the prefix Model."""
    return re.sub(r"(?<![A-Za-z0-9_.'])([A-Za-z_][A-Za-z0-9_']*)",
                  lambda m: "Model." + m.group(1) if m.group(1) in names else m.group(1), text)


def cone(decls: list[str] | tuple[str, ...], roots: list[str]) -> list[str]:
    """The definitions (def, not types) reachable from roots through the declarations' texts, in model order."""
    names = decl_names(decls)
    text = dict(zip(names, decls))
    seen, todo = set(), [r for r in roots if r in text]
    while todo:
        n = todo.pop()
        if n in seen:
            continue
        seen.add(n)
        body = text[n].split(":=", 1)[1] if ":=" in text[n] else text[n]
        todo += [w for w in re.findall(r"[A-Za-z_][A-Za-z0-9_']*", body) if w in text and w not in seen]
    return [n for n in names if n in seen and re.match(r"(?:noncomputable\s+)?def\s", text[n])]

