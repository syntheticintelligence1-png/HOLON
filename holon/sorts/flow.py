"""Value flow, register reads and writer sets of a holon-facts/0.2 document (whitepaper §7.3; BUILD_PLAN I13).

One walk over the facts' definitions, actions, migrations and observers (in that order, each in facts
order) produces the events holon.sorts.constraints turns into constraints:

  flow(src, dst)           a value moves: a let binds it, an effect or a record constructor writes it, a call
                           passes it to a definition's parameter or returns it, a conditional selects it
  affine(op, l, r, out)    one + or - node; operands are named directly (a variable, a let, a record field, a
                           definition's result, or an auxiliary variable for a nested node, a conditional or a
                           literal), out is an auxiliary variable
  compare(op, l, r)        one comparison of two Nat terms (==, !=, <, <=, >, >=); membership and list
                           equality builtins (mem, remove, eq_nats) compare an element with a list's elements
  call(name, var)          the result of a library builtin or a facts definition (lexical "builtin" seeds)
  write(actor, reg, var)   an effect (or a record constructor) writes register reg with the value var
  sub(...)                 one occurrence of a subtraction (assignment.json sites)

Variables. Keys name facts binders: state fields "<f>", parameters "<P>", record fields "<T>.<g>", action
inputs and lets "<a>.<x>", migration inputs "<m>.<x>", definition parameters "<d>.<p>" (each of type Nat, Bool,
List<Nat> or List<Bool>; for a list the key is its elements). Auxiliary variables start with "$": "$<n>" for a
subterm, "$<d>()" for the result of definition d. Literals carry no sort of their own (a fresh auxiliary
variable when they are an affine operand, nothing otherwise).

Definitions are monomorphic: one set of parameter variables per definition, fed by every call. Records are
abstracted by type: every instance of record T shares the field variables "<T>.<g>", so a field read
get(x, g) is the variable "<T>.<g>" and a constructor mk/with writes it. A library builtin with a declared
kind (holon.gen.targetlib: nth_default, set_default, default) moves list elements; a builtin without a kind is
opaque: its arguments flow nowhere, and its result is a fresh variable (an opaque builtin that returns records
is not a writer of their fields). The generic builtins are holon.gen.machine's: nth, set_nat, len, take, drop,
tail, snoc, concat, mem, remove, zeros_like, eq_nats and the shadow projections es_<field>.

Ghosts are not read (honesty): a ghost state field (ghost_state), a record's ghost field (types.<T>.ghost)
and a ghost definition ("ghost": true) are opaque. A reference to one yields no variable, nothing flows into
or out of it, and a ghost definition's body is not walked. Their keys exist (Bool keys keep their type) but no
constraint other than a type reaches them. Hand annotations (guard "site" and "note", docs) are never read
here; the lexical seeds of holon.sorts.constraints read only the docs the frozen sidecar names.

Register reads (rule R3). Every write of a register b (a state field, or a record field written by a
constructor) records the registers its written expression reads, directly or through lets (a definition call
reads its arguments and the fields its body reads); holon.sorts.unions merges labels over the strongly
connected components of that graph.

Writer sets (rule R2, "provenance"): the actions and migrations whose effects write the variable: a state
field f is written by every effect on f; a record field <T>.<g> by every effect that contains, through lets
and definition bodies, ["mk", T, {.. g ..}] or ["with", T, _, {.. g ..}].
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

ARITH = ("+", "-")
CMP = ("<", "<=", ">", ">=", "==", "!=")
GENERIC = ("nth", "set_nat", "len", "take", "drop", "tail", "snoc", "concat", "mem", "remove", "zeros_like",
           "eq_nats")
SCALAR = ("Nat", "Bool", "List<Nat>", "List<Bool>")
ACTION_KEYS = {"name", "src", "principal", "inputs", "guards", "effects", "effects_src"}
GUARD_KEYS = {"let", "expr", "require", "reason", "src", "note", "site"}
MIGRATION_KEYS = {"doc", "src", "inputs", "effects"}
DEF_KEYS = {"params", "type", "body", "doc", "src", "ghost"}
OBSERVER_KEYS = {"params", "type", "body", "doc"}
TYPE_KEYS = {"fields", "doc", "ghost", "doc_fields"}
# facts 0.2 sections: those the pass reads, and those that carry no sort information (provenance, concrete
# values, revert codes, principal ids, coverage, explorer configuration). Any other section is an error.
SECTIONS_READ = {"facts_version", "params", "constants_doc", "types", "state", "ghost_state", "shadow", "defs",
                 "actions", "migrations", "observers", "disch"}
SECTIONS_INERT = {"target", "extraction", "abstractions", "initial", "principals", "reasons", "consumers",
                  "coverage", "policy", "search"}
_SPAN = re.compile(r"^(\S+?):(\d+)(?:-(\d+))?")


class FlowError(ValueError):
    """A facts construct the sorts pass cannot map (no silent drops)."""


def span(src) -> str | None:
    """The leading "<path>:<line>[-<line>]" of a facts src string; None when it has none."""
    if not isinstance(src, str):
        return None
    m = _SPAN.match(src)
    if not m:
        return None
    return f"{m.group(1)}:{m.group(2)}" + (f"-{m.group(3)}" if m.group(3) else "")


def span_lines(sp: str) -> tuple[str, int, int] | None:
    m = re.fullmatch(r"(\S+?):(\d+)(?:-(\d+))?", sp or "")
    if not m:
        return None
    lo = int(m.group(2))
    return m.group(1), lo, int(m.group(3) or lo)


# ------------------------------------------------------------------ values
# ("nat", var | None) | ("bool",) | ("list", inner) | ("rec", T) | ("opaque", type) | ("ghost",)
GHOST = ("ghost",)
BOOLV = ("bool",)


@dataclass
class Ctx:
    actor_kind: str          # action | migration | def | observer
    actor: str
    where: str
    src: str | None          # the constraint src (a span) of the facts entry being walked
    entry_span: str | None   # the same, used as the site span (i)
    mode: str                # guard | let | effect | body


@dataclass
class Program:
    model: str
    keys: dict = field(default_factory=dict)        # key -> {"type", "binder", "ghost"}
    events: list = field(default_factory=list)
    writers: dict = field(default_factory=dict)     # register key -> set of actors
    reads: list = field(default_factory=list)       # (actor, register, frozenset of registers read)
    registers: set = field(default_factory=set)     # non-ghost scalar state fields and record fields
    def_results: dict = field(default_factory=dict)  # def -> result var


class Walker:
    def __init__(self, model: str, facts: dict, lib_builtins: dict):
        self.f = facts
        self.p = Program(model)
        self.types = {}
        self.ghost_fields = set()
        for tname, t in facts.get("types", {}).items():
            self.types[tname] = {g: ty for g, ty in t["fields"]}
            for g in t.get("ghost", []):
                self.ghost_fields.add((tname, g))
        self.state = {row[0]: row[1] for row in facts["state"]}
        self.ghost_state = set(facts.get("ghost_state", []))
        self.params = {}
        for name, v in facts.get("params", {}).items():
            if isinstance(v, bool):
                self.params[name] = "Bool"
            elif isinstance(v, int):
                self.params[name] = "Nat"
            else:
                raise FlowError(f"params.{name}: unmapped value {v!r}")
        self.defs = facts.get("defs", {})
        self.lib = lib_builtins
        self.shadow = facts.get("shadow", {})
        self.shadow_field_types = {fld: self.state[sf] for sf, fld in self.shadow.items() if sf in self.state}
        self.n = 0
        self.def_vals: dict = {}
        self.def_reads: dict = {}
        self.def_writes: dict = {}

    # ---------------------------------------------------------- keys
    def key(self, name: str, ty: str, binder: str, ghost: bool = False) -> None:
        if name in self.p.keys and self.p.keys[name]["type"] != ty:
            raise FlowError(f"two binders map to key {name!r} ({self.p.keys[name]['binder']}, {binder})")
        if name in self.p.keys and self.p.keys[name]["binder"] != binder:
            raise FlowError(f"two binders map to key {name!r} ({self.p.keys[name]['binder']}, {binder})")
        self.p.keys[name] = {"type": ty, "binder": binder, "ghost": ghost}

    def fresh(self) -> str:
        self.n += 1
        return f"${self.n}"

    def val_of(self, ty: str, var: str | None, ghost: bool = False):
        """The value shape of a binder of facts type ty whose key (or element key) is var."""
        if ghost:
            return BOOLV if ty in ("Bool",) else GHOST
        if ty == "Nat":
            return ("nat", var)
        if ty == "Bool":
            return BOOLV
        m = re.fullmatch(r"List<(.+)>", ty)
        if m:
            inner = m.group(1)
            if inner == "Nat":
                return ("list", ("nat", var))
            if inner == "Bool":
                return ("list", BOOLV)
            if inner in self.types:
                return ("list", ("rec", inner))
            return ("opaque", ty)
        if ty in self.types:
            return ("rec", ty)
        return ("opaque", ty)

    def ev(self, *e) -> None:
        self.p.events.append(e)

    def flow(self, src: str | None, dst: str | None, ctx: Ctx) -> None:
        if src is not None and dst is not None:
            self.ev("flow", src, dst, ctx)

    # ---------------------------------------------------------- program
    def run(self) -> Program:
        f = self.f
        unknown = sorted(set(f) - SECTIONS_READ - SECTIONS_INERT)
        if unknown:
            raise FlowError(f"unmapped facts sections {unknown}")
        for tname, t in f.get("types", {}).items():
            self._keys_ok(f"types.{tname}", t, TYPE_KEYS)
        if not isinstance(f.get("disch", {}), dict):
            raise FlowError("disch is not an object")
        self._keys_ok("disch", f.get("disch", {}), {"doc", "cost", "cost_doc", "delay"})
        for name, ty in self.state.items():
            g = name in self.ghost_state
            if ty in SCALAR:
                self.key(name, ty, "state", g)
                if not g:
                    self.p.registers.add(name)
        for name, ty in self.params.items():
            if name in self.state:
                raise FlowError(f"parameter {name} shadows a state field")
            self.key(name, ty, "param")
        for tname, flds in self.types.items():
            for g, ty in flds.items():
                if ty in SCALAR:
                    gh = (tname, g) in self.ghost_fields
                    self.key(f"{tname}.{g}", ty, "field", gh)
                    if not gh:
                        self.p.registers.add(f"{tname}.{g}")
        for name, d in self.defs.items():
            self._keys_ok(f"defs.{name}", d, DEF_KEYS)
            self.walk_def(name)
        for a in f["actions"]:
            self.walk_action(a)
        for name, mg in f.get("migrations", {}).items():
            self.walk_migration(name, mg)
        for name, o in f.get("observers", {}).items():
            self.walk_observer(name, o)
        return self.p

    @staticmethod
    def _keys_ok(what: str, obj: dict, allowed: set) -> None:
        extra = sorted(set(obj) - allowed)
        if extra:
            raise FlowError(f"{what}: unmapped keys {extra}")

    def walk_def(self, name: str):
        if name in self.def_vals:
            return self.def_vals[name]
        d = self.defs[name]
        if d.get("ghost"):
            self.def_vals[name] = BOOLV if d["type"] == "Bool" else GHOST
            self.def_reads[name] = frozenset()
            return self.def_vals[name]
        self.def_vals[name] = None  # recursion guard
        env = {}
        for p, ty in d["params"]:
            if ty in SCALAR:
                self.key(f"{name}.{p}", ty, "def_param")
            env[p] = (self.val_of(ty, f"{name}.{p}"), frozenset())
        sp = span(d.get("src"))
        ctx = Ctx("def", name, f"defs.{name}.body", sp, sp, "body")
        v, r = self.ex(d["body"], env, ctx, params_visible=True)
        res = f"${name}()"
        ty = d["type"]
        out = self.val_of(ty, res)
        if out[0] == "nat":
            self.flow(v[1] if v[0] == "nat" else None, res, ctx)
            self.ev("call", name, res, ctx)
        elif out[0] == "list" and out[1][0] == "nat":
            self.flow(v[1][1] if v[0] == "list" and v[1][0] == "nat" else None, res, ctx)
            self.ev("call", name, res, ctx)
        self.p.def_results[name] = res
        self.def_vals[name] = out
        self.def_reads[name] = r
        return out

    def base_env(self, inputs, owner: str, binder: str) -> dict:
        env = {}
        for name, ty in self.params.items():
            env[name] = (self.val_of(ty, name), frozenset())
        for name, ty in self.state.items():
            g = name in self.ghost_state
            reads = frozenset() if g or ty not in SCALAR else frozenset({name})
            env[name] = (self.val_of(ty, name, g), reads)
        for x, ty in inputs:
            if ty in SCALAR:
                self.key(f"{owner}.{x}", ty, binder)
            env[x] = (self.val_of(ty, f"{owner}.{x}"), frozenset())
        return env

    def walk_action(self, a: dict) -> None:
        self._keys_ok(f"actions.{a.get('name')}", a, ACTION_KEYS)
        name = a["name"]
        env = self.base_env(a.get("inputs", []), name, "input")
        asrc = span(a.get("src"))
        lets = {}
        for i, g in enumerate(a.get("guards", [])):
            self._keys_ok(f"actions.{name}.guards[{i}]", g, GUARD_KEYS)
            gsrc = span(g.get("src")) or asrc
            if "let" in g:
                ctx = Ctx("action", name, f"guards[{i}].expr", gsrc, gsrc, "let")
                v, r = self.ex(g["expr"], env, ctx)
                env[g["let"]] = (self.bind(f"{name}.{g['let']}", v, ctx, "let"), r)
                lets[g["let"]] = g["expr"]
            elif "require" in g:
                ctx = Ctx("action", name, f"guards[{i}].require", gsrc, gsrc, "guard")
                self.ex(g["require"], env, ctx)
            else:
                raise FlowError(f"actions.{name}.guards[{i}]: neither let nor require")
        esrc = span(a.get("effects_src")) or asrc
        self.effects(name, a.get("effects", {}), env, esrc, lets, "action")

    def walk_migration(self, name: str, mg: dict) -> None:
        self._keys_ok(f"migrations.{name}", mg, MIGRATION_KEYS)
        env = self.base_env(mg.get("inputs", []), name, "mig_input")
        self.effects(name, mg.get("effects", {}), env, span(mg.get("src")), {}, "migration")

    def walk_observer(self, name: str, o: dict) -> None:
        self._keys_ok(f"observers.{name}", o, OBSERVER_KEYS)
        if [list(p) for p in o.get("params", [])] != [["s", "State"]]:
            raise FlowError(f"observers.{name}: unmapped parameters {o.get('params')}")
        env = self.base_env([], name, "observer")
        ctx = Ctx("observer", name, f"observers.{name}.body", None, None, "body")
        self.ex(o["body"], env, ctx)

    def bind(self, key: str, v, ctx: Ctx, binder: str):
        """A let: its key receives the value (Nat or List<Nat> element); records and ghosts bind as they are."""
        if v[0] == "nat":
            self.key(key, "Nat", binder)
            self.flow(v[1], key, ctx)
            return ("nat", key)
        if v[0] == "bool":
            self.key(key, "Bool", binder)
            return BOOLV
        if v[0] == "list" and v[1][0] == "nat":
            self.key(key, "List<Nat>", binder)
            self.flow(v[1][1], key, ctx)
            return ("list", ("nat", key))
        if v[0] == "list" and v[1][0] == "bool":
            self.key(key, "List<Bool>", binder)
            return v
        return v

    def effects(self, actor: str, effects: dict, env: dict, esrc: str | None, lets: dict, kind: str) -> None:
        for fld, e in effects.items():
            if fld not in self.state or fld == "log":
                raise FlowError(f"{actor}: effect on {fld}, which is not a writable state field")
            ctx = Ctx(kind, actor, f"effects.{fld}", esrc, esrc, "effect")
            v, r = self.ex(e, env, ctx)
            self.p.writers.setdefault(fld, set()).add(actor)
            ty = self.state[fld]
            if fld in self.ghost_state or ty not in SCALAR:
                continue
            self.p.reads.append((actor, fld, r))
            if ty == "Nat":
                var = v[1] if v[0] == "nat" else None
            elif ty == "List<Nat>":
                var = v[1][1] if v[0] == "list" and v[1][0] == "nat" else None
            else:
                continue
            self.flow(var, fld, ctx)
            self.ev("write", actor, fld, var, ctx)
        for (tname, g) in sorted(self.effect_fields(effects, lets)):
            self.p.writers.setdefault(f"{tname}.{g}", set()).add(actor)

    # ---------------------------------------------------------- writer sets (syntactic)
    def effect_fields(self, effects: dict, lets: dict) -> set:
        out: set = set()
        for e in effects.values():
            out |= self._mk_fields(e, lets, set())
        return out

    def _mk_fields(self, e, lets: dict, seen: set) -> set:
        if isinstance(e, str):
            if e in lets and e not in seen:
                return self._mk_fields(lets[e], lets, seen | {e})
            return set()
        if not isinstance(e, list) or not e:
            return set()
        op = e[0]
        out: set = set()
        if op == "mk":
            out |= {(e[1], g) for g in e[2]}
            for v in e[2].values():
                out |= self._mk_fields(v, lets, seen)
        elif op == "with":
            out |= {(e[1], g) for g in e[3]}
            out |= self._mk_fields(e[2], lets, seen)
            for v in e[3].values():
                out |= self._mk_fields(v, lets, seen)
        elif op == "call":
            if e[1] in self.defs:
                if e[1] not in self.def_writes:
                    self.def_writes[e[1]] = set()
                    self.def_writes[e[1]] = self._mk_fields(self.defs[e[1]]["body"], {}, set())
                out |= self.def_writes[e[1]]
            for x in e[2:]:
                out |= self._mk_fields(x, lets, seen)
        elif op == "get":
            out |= self._mk_fields(e[1], lets, seen)
        elif op == "list":
            for x in e[2:]:
                out |= self._mk_fields(x, lets, seen)
        else:
            for x in e[1:]:
                out |= self._mk_fields(x, lets, seen)
        return out

    # ---------------------------------------------------------- expressions
    def operand(self, v, ctx: Ctx) -> str:
        """An affine operand: its variable, or a fresh one for a literal (literals carry no sort)."""
        if v[0] == "nat" and v[1] is not None:
            return v[1]
        if v[0] in ("nat", "ghost"):
            return self.fresh()
        raise FlowError(f"{ctx.actor} ({ctx.where}): an arithmetic operand of shape {v[0]}")

    def nat_var(self, v, what: str, ctx: Ctx) -> str | None:
        if v[0] == "nat":
            return v[1]
        if v[0] == "ghost":
            return None
        raise FlowError(f"{ctx.actor} ({ctx.where}): {what} needs a Nat, got {v[0]}")

    def elem(self, v, ctx: Ctx):
        """The element shape of a list value."""
        if v[0] == "list":
            return v[1]
        if v[0] in ("ghost", "opaque"):
            return GHOST if v[0] == "ghost" else ("opaque", "elem")
        raise FlowError(f"{ctx.actor} ({ctx.where}): a list operation on {v[0]}")

    def ex(self, e, env: dict, ctx: Ctx, params_visible: bool = False):
        """(value, registers read) of a DSL expression; records the events of every node."""
        if isinstance(e, bool):
            return BOOLV, frozenset()
        if isinstance(e, int):
            return ("nat", None), frozenset()
        if isinstance(e, str):
            if e in env:
                return env[e]
            if params_visible and e in self.params:
                return self.val_of(self.params[e], e), frozenset()
            raise FlowError(f"{ctx.actor} ({ctx.where}): unbound variable {e}")
        if not isinstance(e, list) or not e:
            raise FlowError(f"{ctx.actor} ({ctx.where}): bad expression {e!r}")
        op, *a = e
        if op in ARITH:
            if len(a) != 2:
                raise FlowError(f"{ctx.actor}: {op} takes two operands")
            (va, ra), (vb, rb) = self.ex(a[0], env, ctx, params_visible), self.ex(a[1], env, ctx, params_visible)
            lhs, rhs = self.operand(va, ctx), self.operand(vb, ctx)
            out = self.fresh()
            self.ev("affine", op, lhs, rhs, out, e, ctx)
            if op == "-":
                self.ev("sub", e, lhs, rhs, out, ctx)
            return ("nat", out), ra | rb
        if op in CMP:
            if len(a) != 2:
                raise FlowError(f"{ctx.actor}: {op} takes two operands")
            (va, ra), (vb, rb) = self.ex(a[0], env, ctx, params_visible), self.ex(a[1], env, ctx, params_visible)
            x, y = self.nat_var(va, op, ctx), self.nat_var(vb, op, ctx)
            if x is not None and y is not None:
                self.ev("compare", op, x, y, e, ctx, None)
            return BOOLV, ra | rb
        if op in ("&&", "||", "!"):
            reads = frozenset()
            for x in a:
                _, r = self.ex(x, env, ctx, params_visible)
                reads |= r
            return BOOLV, reads
        if op == "?":
            if len(a) != 3:
                raise FlowError(f"{ctx.actor}: ? takes three operands")
            _, rc = self.ex(a[0], env, ctx, params_visible)
            (vx, rx), (vy, ry) = self.ex(a[1], env, ctx, params_visible), self.ex(a[2], env, ctx, params_visible)
            return self.join(vx, vy, ctx), rc | rx | ry
        if op == "call":
            return self.call(a[0], a[1:], env, ctx, params_visible)
        if op == "get":
            vx, rx = self.ex(a[0], env, ctx, params_visible)
            if vx[0] == "ghost":
                return GHOST, rx
            if vx[0] != "rec":
                raise FlowError(f"{ctx.actor} ({ctx.where}): get .{a[1]} of a {vx[0]}")
            tname, g = vx[1], a[1]
            if g not in self.types[tname]:
                raise FlowError(f"{ctx.actor} ({ctx.where}): {tname} has no field {g}")
            ghost = (tname, g) in self.ghost_fields
            ty = self.types[tname][g]
            reads = rx | (frozenset({f"{tname}.{g}"}) if ty in SCALAR and not ghost else frozenset())
            return self.val_of(ty, f"{tname}.{g}", ghost), reads
        if op == "mk":
            tname, vals = a
            return ("rec", tname), self.fields_write(tname, vals, env, ctx, params_visible)
        if op == "with":
            tname, base, vals = a
            vb, rb = self.ex(base, env, ctx, params_visible)
            if vb[0] not in ("rec", "ghost"):
                raise FlowError(f"{ctx.actor} ({ctx.where}): with on a {vb[0]}")
            return ("rec", tname), rb | self.fields_write(tname, vals, env, ctx, params_visible)
        if op == "list":
            ty, *items = a
            reads = frozenset()
            vars_ = []
            for x in items:
                v, r = self.ex(x, env, ctx, params_visible)
                reads |= r
                if v[0] == "nat" and v[1] is not None:
                    vars_.append(v[1])
            if ty == "Nat":
                if not vars_:
                    return ("list", ("nat", None)), reads
                out = self.fresh()
                for v in vars_:
                    self.flow(v, out, ctx)
                return ("list", ("nat", out)), reads
            return self.val_of(f"List<{ty}>", None), reads
        raise FlowError(f"{ctx.actor} ({ctx.where}): unknown operator {op!r}")

    def join(self, vx, vy, ctx: Ctx):
        """The value of a conditional: both branches flow into one fresh variable (Nat, List<Nat> elements)."""
        if vx[0] == "ghost":
            return vy if vy[0] != "nat" else ("nat", vy[1])
        if vy[0] == "ghost":
            return vx
        if vx[0] != vy[0]:
            raise FlowError(f"{ctx.actor} ({ctx.where}): conditional branches of shapes {vx[0]} and {vy[0]}")
        if vx[0] == "nat":
            vs = [v for v in (vx[1], vy[1]) if v is not None]
            if not vs:
                return ("nat", None)
            out = self.fresh()
            for v in vs:
                self.flow(v, out, ctx)
            return ("nat", out)
        if vx[0] == "list" and vx[1][0] == "nat" and vy[1][0] == "nat":
            vs = [v for v in (vx[1][1], vy[1][1]) if v is not None]
            if not vs:
                return ("list", ("nat", None))
            out = self.fresh()
            for v in vs:
                self.flow(v, out, ctx)
            return ("list", ("nat", out))
        return vx

    def fields_write(self, tname: str, vals: dict, env: dict, ctx: Ctx, pv: bool) -> frozenset:
        if tname not in self.types:
            raise FlowError(f"{ctx.actor} ({ctx.where}): record {tname} is not declared")
        reads = frozenset()
        for g, x in vals.items():
            if g not in self.types[tname]:
                raise FlowError(f"{ctx.actor} ({ctx.where}): {tname} has no field {g}")
            v, r = self.ex(x, env, ctx, pv)
            reads |= r
            ty = self.types[tname][g]
            reg = f"{tname}.{g}"
            if (tname, g) in self.ghost_fields or ty not in SCALAR:
                continue
            if ctx.actor_kind in ("action", "migration"):
                self.p.reads.append((ctx.actor, reg, r))
            if ty == "Nat":
                var = v[1] if v[0] == "nat" else None
            elif ty == "List<Nat>":
                var = v[1][1] if v[0] == "list" and v[1][0] == "nat" else None
            else:
                continue
            self.flow(var, reg, ctx)
            if ctx.actor_kind in ("action", "migration"):
                self.ev("write", ctx.actor, reg, var, ctx)
        return reads

    def call(self, name: str, args: list, env: dict, ctx: Ctx, pv: bool):
        walked = [self.ex(x, env, ctx, pv) for x in args]
        vals = [v for v, _ in walked]
        reads = frozenset().union(*[r for _, r in walked]) if walked else frozenset()
        if name in self.defs:
            d = self.defs[name]
            if len(d["params"]) != len(args):
                raise FlowError(f"{ctx.actor} ({ctx.where}): {name} takes {len(d['params'])} arguments")
            out = self.walk_def(name)
            if out is None:
                raise FlowError(f"definition {name} is recursive")
            if d.get("ghost"):
                return out, reads
            for (p, ty), v in zip(d["params"], vals):
                key = f"{name}.{p}"
                if ty == "Nat":
                    self.flow(self.nat_var(v, f"argument {p} of {name}", ctx), key, ctx)
                elif ty == "List<Nat>":
                    el = self.elem(v, ctx)
                    self.flow(el[1] if el[0] == "nat" else None, key, ctx)
            return out, reads | self.def_reads[name]
        if name in GENERIC:
            return self.generic(name, vals, ctx), reads
        if name.startswith("es_") and name[3:] in self.shadow_field_types:
            return self.projection(name[3:], vals, ctx, reads)
        if name in self.lib:
            return self.library(name, vals, ctx), reads
        raise FlowError(f"{ctx.actor} ({ctx.where}): unknown function {name}")

    def generic(self, name: str, vals: list, ctx: Ctx):
        def need(n):
            if len(vals) != n:
                raise FlowError(f"{ctx.actor} ({ctx.where}): {name} takes {n} arguments")
        if name == "nth":
            need(2)
            el = self.elem(vals[0], ctx)
            return el if el[0] in ("nat", "ghost") else GHOST
        if name == "len":
            need(1)
            return ("nat", self.fresh())
        if name in ("take", "drop"):
            need(2)
            return vals[0]
        if name == "tail":
            need(1)
            return vals[0]
        if name in ("snoc", "set_nat"):
            need(2 if name == "snoc" else 3)
            lst, x = vals[0], vals[-1]
            if lst[0] == "list" and lst[1][0] == "nat":
                vs = [v for v in (lst[1][1], x[1] if x[0] == "nat" else None) if v is not None]
                if not vs:
                    return ("list", ("nat", None))
                out = self.fresh()
                for v in vs:
                    self.flow(v, out, ctx)
                return ("list", ("nat", out))
            return lst
        if name == "concat":
            need(2)
            x, y = vals
            if x[0] == "list" and x[1][0] == "nat" or y[0] == "list" and y[1][0] == "nat":
                vs = [v[1][1] for v in (x, y) if v[0] == "list" and v[1][0] == "nat" and v[1][1] is not None]
                if not vs:
                    return ("list", ("nat", None))
                out = self.fresh()
                for v in vs:
                    self.flow(v, out, ctx)
                return ("list", ("nat", out))
            return x if x[0] != "ghost" else y
        if name in ("mem", "remove"):
            need(2)
            x, lst = vals
            el = self.elem(lst, ctx)
            xv = self.nat_var(x, name, ctx)
            if xv is not None and el[0] == "nat" and el[1] is not None:
                self.ev("compare", "==", xv, el[1], ["call", name], ctx, name)
            return BOOLV if name == "mem" else lst
        if name == "zeros_like":
            need(1)
            return ("list", ("nat", None))
        if name == "eq_nats":
            need(2)
            ex, ey = self.elem(vals[0], ctx), self.elem(vals[1], ctx)
            if ex[0] == "nat" and ey[0] == "nat" and ex[1] is not None and ey[1] is not None:
                self.ev("compare", "==", ex[1], ey[1], ["call", name], ctx, name)
            return BOOLV
        raise FlowError(f"generic builtin {name} has no rule")

    def projection(self, fld: str, vals: list, ctx: Ctx, reads: frozenset):
        """es_<field>(xs): the shadow projection of field fld of every record in xs."""
        if len(vals) != 1:
            raise FlowError(f"{ctx.actor} ({ctx.where}): es_{fld} takes 1 argument")
        el = self.elem(vals[0], ctx)
        ty = self.shadow_field_types[fld]
        if el[0] == "rec" and fld in self.types[el[1]]:
            tname = el[1]
            if (tname, fld) in self.ghost_fields:
                return GHOST, reads
            fty = self.types[tname][fld]
            if fty == "Nat":
                return ("list", ("nat", f"{tname}.{fld}")), reads | {f"{tname}.{fld}"}
        return self.val_of(ty, None), reads

    def library(self, name: str, vals: list, ctx: Ctx):
        b = self.lib[name]
        kind, ty = b.get("kind"), b.get("type")
        if kind == "nth_default":
            el = self.elem(vals[0], ctx) if vals else GHOST
            if el[0] == "nat":
                return el
            return self.val_of(ty, None)
        if kind == "set_default":
            return vals[0] if vals and vals[0][0] == "list" else self.val_of(ty, None)
        if kind == "default":
            return ("nat", None) if ty == "Nat" else self.val_of(ty, None)
        if kind is not None:
            raise FlowError(f"library builtin {name}: unknown kind {kind!r}")
        # opaque: the arguments flow nowhere; a Nat result (or element) is a fresh variable
        if ty == "Nat":
            out = self.fresh()
            self.ev("call", name, out, ctx)
            return ("nat", out)
        if ty == "List<Nat>":
            out = self.fresh()
            self.ev("call", name, out, ctx)
            return ("list", ("nat", out))
        return self.val_of(ty, None)


def walk(model: str, facts: dict, lib_builtins: dict) -> Program:
    return Walker(model, facts, lib_builtins).run()
