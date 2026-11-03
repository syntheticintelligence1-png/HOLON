"""Index-sensitive read and write sets of facts-0.2 expressions (whitepaper Def 4.2).

An access is a pair [carrier, key]. The key is an index term rendered as infix text without
spaces ("idx-lfi", "bc", "lci+1"), "*" (every slot of a sequence, or the whole of a scalar or
record register) or "#" (the length only). Sets are computed by walking the facts expressions:

  * lets are substituted, so terms are expressed over action inputs, state fields and parameters;
  * calls to facts `defs` are inlined with their parameters bound to the call's arguments, so an
    access inside a definition is attributed to the action that calls it, in the action's terms;
  * a call to a definition whose arguments are exactly its parameter names renders as the bare
    definition name ("lci" for lci(lfi,win)).

Builtin roles come from the generic DSL vocabulary of holon.gen.machine (nth, set_nat, len, take,
drop, tail, snoc, concat, mem, remove, zeros_like) and from the `kind` a target library declares for
its builtins (nth_default reads at an index, set_default writes at one, default is a constant). A
library builtin with no declared kind is opaque: every state field passed to it is accessed whole
("*"), and the diagram lists it as ACCESS debt. No target name appears in this module.

Key spaces. A sequence is keyed by list position, as the facts index it (win_at(win,idx-lfi) gives
[win, idx-lfi]). The exception is a residue (shadow) list, which the facts define only through the
absolute slots of the window field it shadows: its keys are slots, slot = position + base. The base
is derived from a definition that maps an absolute index parameter i to a position of the list
(position = i - base, e.g. bvh_at reads nth(s_bvh, idx-lci-1), so base = lci+1). Shadow lists the
definitions never read take the base of their siblings only when every action moves all shadow lists
in lockstep (`shadow_bases`). Slot terms assume the facts' shadow invariant: shadow position k is
slot base+k in every reachable state, which is what the deriving definition presumes.

Terms are rendered over the integers. Nat subtraction in the model truncates, but the accesses the
facts make happen on paths where positions are non-negative, so the integer reading is the slot the
model touches there.

Every step of a facts-0.2 machine logs its outcome (O_Ok, or O_Rev with the failed guard's reason),
so every TRANS edge writes the log; `step_writes` adds that write.

Instrumentation (I14, the evidence calculus: which "*" terms are imprecise). A Walker whose
`drop_kindless` is set records nothing at the kindless-builtin fallback: a state field passed directly
to a target-library builtin that declares no access kind, whether read (`read`) or updated by an effect
(`write`, role "opaque"). Everything else, control flow included, is unchanged, so the terms such a walk
lacks are exactly those produced only at that fallback. The diagram build never sets the flag.
"""
from __future__ import annotations

import re

WHOLE = "*"
LENGTH = "#"

ARITH = ("+", "-")
CMP = ("<", "<=", ">", ">=", "==", "!=")
BOOL_N = ("&&", "||")

# generic builtins (holon.gen.machine.Machine.builtin) -> role
GENERIC_ROLES = {
    "nth": "read_at",
    "set_nat": "set_at",
    "len": "length",
    "take": "take",
    "drop": "drop",
    "tail": "tail",
    "snoc": "snoc",
    "concat": "concat",
    "mem": "member",
    "remove": "remove",
    "zeros_like": "map",
    "eq_nats": "opaque",
}
# target-library builtin kinds (holon.gen.targetlib) -> role
LIB_KIND_ROLES = {"nth_default": "read_at", "set_default": "set_at", "default": "const"}
_ES = re.compile(r"es_[A-Za-z0-9_]+")


class AccessError(Exception):
    """An expression construct the access walker does not know."""


# ------------------------------------------------------------------ rendering
_PREC = {"?": 0, "||": 1, "&&": 2, **{c: 3 for c in CMP}, "+": 4, "-": 4, "!": 5}


def render(e, defs: dict | None = None, ctx: int = 0) -> str:
    """Infix text of a DSL expression, with no spaces and only the parentheses precedence needs."""
    defs = defs or {}
    if isinstance(e, bool):
        return "true" if e else "false"
    if isinstance(e, int):
        return str(e)
    if isinstance(e, str):
        return e
    if not isinstance(e, list) or not e:
        raise AccessError(f"bad expression {e!r}")
    op, *a = e
    if op in ARITH:
        p = _PREC[op]
        txt = render(a[0], defs, p) + op + render(a[1], defs, p + 1)
    elif op in CMP:
        p = _PREC[op]
        txt = render(a[0], defs, p + 1) + op + render(a[1], defs, p + 1)
    elif op in BOOL_N:
        p = _PREC[op]
        txt = op.join(render(x, defs, p + 1) for x in a)
    elif op == "!":
        p = _PREC[op]
        txt = "!" + render(a[0], defs, p + 1)
    elif op == "?":
        p = 0
        txt = render(a[0], defs, 1) + "?" + render(a[1], defs, 1) + ":" + render(a[2], defs, 0)
    elif op == "call":
        name, *args = a
        d = defs.get(name)
        if d is not None and list(args) == [pn for pn, _ in d["params"]]:
            return name
        return name + "(" + ",".join(render(x, defs, 0) for x in args) + ")"
    elif op == "get":
        return render(a[0], defs, 6) + "." + a[1]
    elif op == "mk":
        return a[0] + "{" + ",".join(f"{k}:{render(v, defs, 0)}" for k, v in a[1].items()) + "}"
    elif op == "with":
        return render(a[1], defs, 6) + "{" + ",".join(f"{k}:={render(v, defs, 0)}" for k, v in a[2].items()) + "}"
    elif op == "list":
        return "[" + ",".join(render(x, defs, 0) for x in a[1:]) + "]"
    else:
        raise AccessError(f"unknown operator {op!r} in {e!r}")
    return f"({txt})" if p < ctx else txt


def subst(e, sub: dict):
    """Replace variables bound in `sub` (names in call, field, type and key positions are not variables)."""
    if isinstance(e, bool) or isinstance(e, int):
        return e
    if isinstance(e, str):
        return sub.get(e, e)
    op, *a = e
    if op == "call":
        return ["call", a[0], *(subst(x, sub) for x in a[1:])]
    if op == "get":
        return ["get", subst(a[0], sub), a[1]]
    if op == "mk":
        return ["mk", a[0], {k: subst(v, sub) for k, v in a[1].items()}]
    if op == "with":
        return ["with", a[0], subst(a[1], sub), {k: subst(v, sub) for k, v in a[2].items()}]
    if op == "list":
        return ["list", a[0], *(subst(x, sub) for x in a[1:])]
    return [op, *(subst(x, sub) for x in a)]


def free_vars(e) -> set[str]:
    if isinstance(e, bool) or isinstance(e, int):
        return set()
    if isinstance(e, str):
        return {e}
    op, *a = e
    if op == "call":
        return set().union(set(), *(free_vars(x) for x in a[1:]))
    if op == "get":
        return free_vars(a[0])
    if op == "mk":
        return set().union(set(), *(free_vars(v) for v in a[1].values()))
    if op == "with":
        return free_vars(a[1]).union(*(free_vars(v) for v in a[2].values()))
    if op == "list":
        return set().union(set(), *(free_vars(x) for x in a[1:]))
    return set().union(set(), *(free_vars(x) for x in a))


# ------------------------------------------------------------------ linear terms
class Lin:
    """A linear integer term: atoms (rendered text -> (coefficient, expression)) plus a constant."""

    def __init__(self, atoms=None, const: int = 0):
        self.atoms: dict[str, list] = dict(atoms or {})
        self.const = const

    def add(self, other: "Lin", sign: int = 1) -> "Lin":
        out = Lin({k: list(v) for k, v in self.atoms.items()}, self.const + sign * other.const)
        for k, (c, ex) in other.atoms.items():
            if k in out.atoms:
                out.atoms[k][0] += sign * c
            else:
                out.atoms[k] = [sign * c, ex]
        return out

    def text(self) -> str:
        parts = []
        for k, (c, _) in self.atoms.items():
            if c == 0:
                continue
            mag = "" if abs(c) == 1 else f"{abs(c)}*"
            parts.append(("+" if c > 0 else "-") + mag + k)
        if self.const:
            parts.append(("+" if self.const > 0 else "-") + str(abs(self.const)))
        if not parts:
            return "0"
        s = "".join(parts)
        return s[1:] if s.startswith("+") else s

    def expr(self):
        """Back to a DSL expression (atoms in order, then the constant)."""
        out = None
        for _, (c, ex) in self.atoms.items():
            for _ in range(abs(c)):
                if out is None:
                    out = ex if c > 0 else ["-", 0, ex]
                else:
                    out = ["+" if c > 0 else "-", out, ex]
        if self.const or out is None:
            k = abs(self.const)
            if out is None:
                out = self.const if self.const >= 0 else ["-", 0, k]
            else:
                out = ["+" if self.const > 0 else "-", out, k]
        return out


def linear(e, defs: dict) -> Lin:
    if isinstance(e, bool):
        raise AccessError(f"not a Nat term: {e!r}")
    if isinstance(e, int):
        return Lin(const=e)
    if isinstance(e, list) and e and e[0] in ARITH:
        return linear(e[1], defs).add(linear(e[2], defs), 1 if e[0] == "+" else -1)
    return Lin({render(e, defs): [1, e]})


# ------------------------------------------------------------------ roles
class Roles:
    """Builtin roles for one facts document (generic DSL builtins plus its libraries' kinds)."""

    def __init__(self, lib_kinds: dict[str, str | None], shadow_fields: dict[str, str]):
        self.lib_kinds = lib_kinds
        self.es = {f"es_{v}" for v in shadow_fields.values()}
        self.opaque_used: set[str] = set()

    def note_opaque(self, name: str) -> None:
        """A kindless library builtin received a state field (accessed whole): ACCESS debt."""
        if name in self.lib_kinds and self.lib_kinds[name] is None:
            self.opaque_used.add(name)

    def kindless(self, name: str) -> bool:
        """A target-library builtin that declares no access kind (its role is "opaque" because the library
        gives no kind; never a generic builtin or a shadow projection)."""
        return (name not in GENERIC_ROLES and name not in self.es and name in self.lib_kinds
                and self.lib_kinds[name] is None)

    def role(self, name: str) -> str:
        if name in GENERIC_ROLES:
            return GENERIC_ROLES[name]
        if name in self.es:
            return "opaque"
        if name in self.lib_kinds:
            kind = self.lib_kinds[name]
            if kind is None:
                return "opaque"
            if kind not in LIB_KIND_ROLES:
                raise AccessError(f"library builtin {name}: unknown kind {kind!r}")
            return LIB_KIND_ROLES[kind]
        raise AccessError(f"unknown function {name}")


# ------------------------------------------------------------------ the walker
class Scope:
    """Names visible to an expression: state fields (reads), inputs and parameters (no state access),
    and local bindings (lets, definition parameters) mapped to their expressions in outer terms."""

    def __init__(self, state: set[str], inputs: set[str], params: set[str], local: dict | None = None,
                 free_state: bool = True):
        """free_state: whether bare state-field names are visible (not in a definition body, which
        sees the state only through its parameters)."""
        self.state, self.inputs, self.params = state, inputs, params
        self.local = dict(local or {})
        self.free_state = free_state

    def resolve(self, e):
        return subst(e, self.local)

    def bound(self, name: str) -> bool:
        return (name in self.local or name in self.inputs or name in self.params
                or (self.free_state and name in self.state))

    def field_of(self, e) -> str | None:
        """The state field an argument denotes when it is passed by reference (a bare name)."""
        if not isinstance(e, str):
            return None
        if e in self.local:
            r = self.local[e]
            return r if isinstance(r, str) and r in self.state else None
        if e in self.inputs or e in self.params:
            return None
        return e if self.free_state and e in self.state else None


class Walker:
    def __init__(self, defs: dict, roles: Roles, bases: dict[str, Lin], state: set[str]):
        self.defs, self.roles, self.bases, self.state = defs, roles, bases, state
        self.reads: set[tuple[str, str]] = set()
        self.writes: set[tuple[str, str]] = set()
        self.defs_used: set[str] = set()
        self.drop_kindless = False  # I14 instrumentation (module docstring); the diagram never sets it

    def _fallback(self, role: str, name: str) -> bool:
        """An access made at the kindless-builtin fallback that this walk does not record."""
        return self.drop_kindless and role == "opaque" and self.roles.kindless(name)

    # ---------------------------------------------------------- keys
    def key(self, f: str, k) -> str:
        """Index term of slot/position expression `k` (in action terms) of field f."""
        if f in self.bases:
            return linear(k, self.defs).add(self.bases[f]).text()
        return render(k, self.defs)

    def key_from(self, f: str, k) -> str:
        """Range term for the slots from position k on."""
        return self.key(f, k) + ".."

    def key_upto(self, f: str, n) -> str:
        """Range term for positions 0..n-1."""
        hi = linear(["-", n, 1], self.defs)
        if f in self.bases:
            return f"{self.key(f, 0)}..{hi.add(self.bases[f]).text()}"
        return f"0..{hi.text()}"

    def base_key(self, f: str) -> str | None:
        return self.bases[f].text() if f in self.bases else None

    # ---------------------------------------------------------- reads
    def read(self, e, sc: Scope) -> None:
        if isinstance(e, bool) or isinstance(e, int):
            return
        if isinstance(e, str):
            f = sc.field_of(e)
            if f is not None:
                self.reads.add((f, WHOLE))
            elif not sc.bound(e):
                raise AccessError(f"unbound variable {e}")
            return
        if not isinstance(e, list) or not e:
            raise AccessError(f"bad expression {e!r}")
        op, *a = e
        if op in ARITH or op in CMP or op in BOOL_N or op in ("!", "?"):
            for x in a:
                self.read(x, sc)
            return
        if op == "get":
            self.read(a[0], sc)
            return
        if op == "mk":
            for v in a[1].values():
                self.read(v, sc)
            return
        if op == "with":
            self.read(a[1], sc)
            for v in a[2].values():
                self.read(v, sc)
            return
        if op == "list":
            for x in a[1:]:
                self.read(x, sc)
            return
        if op != "call":
            raise AccessError(f"unknown operator {op!r}")
        name, *args = a
        if name in self.defs:
            self.inline(name, args, sc)
            return
        role = self.roles.role(name)
        fields = [sc.field_of(x) for x in args]
        if role == "read_at" and fields[0] is not None:
            self.reads.add((fields[0], self.key(fields[0], sc.resolve(args[1]))))
            self.read(args[1], sc)
            return
        if role == "length" and fields[0] is not None:
            self.reads.add((fields[0], LENGTH))
            return
        if role == "drop" and fields[0] is not None:
            self.reads.add((fields[0], self.key_from(fields[0], sc.resolve(args[1]))))
            self.read(args[1], sc)
            return
        if role == "take" and fields[0] is not None:
            self.reads.add((fields[0], self.key_upto(fields[0], sc.resolve(args[1]))))
            self.read(args[1], sc)
            return
        if role == "tail" and fields[0] is not None:
            self.reads.add((fields[0], self.key_from(fields[0], 1)))
            return
        for x, f in zip(args, fields):
            if f is not None:
                if not self._fallback(role, name):
                    self.reads.add((f, WHOLE))
                if role == "opaque":
                    self.roles.note_opaque(name)
            else:
                self.read(x, sc)

    def inline(self, name: str, args: list, sc: Scope) -> None:
        d = self.defs[name]
        if len(d["params"]) != len(args):
            raise AccessError(f"{name}: arity")
        self.defs_used.add(name)
        local = {}
        for (pn, _), x in zip(d["params"], args):
            if sc.field_of(x) is None:
                self.read(x, sc)
            local[pn] = sc.resolve(x)
        inner = Scope(self.state, set(), sc.params, local, free_state=False)
        self.read(d["body"], inner)

    # ---------------------------------------------------------- writes
    def write(self, f: str, e, sc: Scope) -> None:
        """Writes of the effect `f := e` (and the reads it makes)."""
        if isinstance(e, str) and sc.field_of(e) == f:
            return
        if isinstance(e, list) and e and e[0] == "?":
            self.read(e[1], sc)
            self.write(f, e[2], sc)
            self.write(f, e[3], sc)
            return
        if isinstance(e, list) and e and e[0] == "call" and e[1] not in self.defs:
            name, *args = e[1:]
            role = self.roles.role(name)
            fields = [sc.field_of(x) for x in args]
            own = [i for i, g in enumerate(fields) if g == f]
            if own:
                i = own[0]
                key = self.update_key(role, f, i, args, sc)
                if role == "opaque":
                    self.roles.note_opaque(name)
                if key is not None:
                    if not self._fallback(role, name):
                        self.writes.add((f, key))
                    for j, x in enumerate(args):
                        if j != i:
                            self.read(x, sc)
                    return
        self.writes.add((f, WHOLE))
        self.read(e, sc)

    def update_key(self, role: str, f: str, i: int, args: list, sc: Scope) -> str | None:
        """Key written when builtin `role` updates field f passed as argument i; None if f is merely
        an input of the expression (then the effect writes f whole and reads what it reads)."""
        if role == "set_at" and i == 0:
            return self.key(f, sc.resolve(args[1]))
        if role == "snoc" and i == 0:
            return self.key(f, ["call", "len", f])
        if role == "tail" and i == 0:
            # removes position 0. On a slot-keyed (shadow) list this consumes the slot at the base;
            # on a position-keyed list every later element moves down: all positions change.
            return self.base_key(f) or WHOLE
        if role == "take" and i == 0:
            return self.key_from(f, sc.resolve(args[1]))
        if role == "concat" and i == 0:
            return self.key_from(f, ["call", "len", f])
        if role in ("drop", "concat", "remove", "map", "opaque") and (role != "remove" or i == 1):
            return WHOLE
        return None


def step_writes() -> set[tuple[str, str]]:
    """The write every step makes besides its effects: it logs its outcome."""
    return {("log", WHOLE)}


# ------------------------------------------------------------------ shadow bases
def _nth_reads(e, roles: Roles, defs: dict):
    """(list argument, position) of every read-at call in e (not inside nested definitions)."""
    if isinstance(e, list) and e:
        if e[0] == "call" and e[1] not in defs and roles.role(e[1]) == "read_at":
            yield e[2], e[3]
        for x in (e[2:] if e[0] == "call" else e[1:]):
            if isinstance(x, dict):
                for v in x.values():
                    yield from _nth_reads(v, roles, defs)
            else:
                yield from _nth_reads(x, roles, defs)


def _calls(e, name: str):
    if isinstance(e, list) and e:
        if e[0] == "call" and e[1] == name:
            yield e[2:]
        for x in e[1:]:
            if isinstance(x, dict):
                for v in x.values():
                    yield from _calls(v, name)
            else:
                yield from _calls(x, name)


def shadow_bases(facts: dict, roles: Roles) -> tuple[dict[str, Lin], dict[str, dict], list[str]]:
    """Slot base of every shadow list: ({field: base}, {field: provenance}, problems).

    1. From definitions: a definition d with a list parameter L and a Nat parameter i that reads
       nth(L, p) where p = i - b (i with coefficient 1, b free of i) maps slot i to position p, so
       the list's base is b. At every call site of d whose argument for L is a shadow field S, and
       whose arguments for the free names of b are those same names (so b means the same there),
       base(S) = b.
    2. Lockstep: a shadow field no definition reads takes the common base of the derived ones when
       every action that writes any shadow field writes all of them with the same expression up to
       the field (and its es_ projection), and every other writer (a migration) only rewrites
       values (zeros_like), keeping positions.
    Fields with no base stay position-keyed and are reported as problems."""
    defs = facts.get("defs", {})
    shadow = facts.get("shadow", {})
    found: dict[str, dict[str, Lin]] = {}
    prov: dict[str, dict] = {}
    exprs = [g.get("expr", g.get("require")) for a in facts.get("actions", []) for g in a["guards"]]
    exprs += [v for a in facts.get("actions", []) for v in a["effects"].values()]
    exprs += [d["body"] for d in defs.values()] + [o["body"] for o in facts.get("observers", {}).values()]
    exprs += [v for m in facts.get("migrations", {}).values() for v in m["effects"].values()]
    for dname, d in defs.items():
        ptypes = dict((p, t) for p, t in d["params"])
        pnames = [p for p, _ in d["params"]]
        for lst, pos in _nth_reads(d["body"], roles, defs):
            if not isinstance(lst, str) or lst not in ptypes or not ptypes[lst].startswith("List<"):
                continue
            lin = linear(pos, defs)
            idx = [p for p in pnames if ptypes[p] == "Nat" and p in lin.atoms and lin.atoms[p][0] == 1]
            for i in idx:
                b = Lin(const=0).add(lin, -1).add(Lin({i: [1, i]}))
                if any(c != 0 and i in free_vars(ex) for k, (c, ex) in b.atoms.items()):
                    continue
                bfree = free_vars(b.expr())
                for args in (x for e in exprs for x in _calls(e, dname)):
                    if len(args) != len(pnames):
                        continue
                    bind = dict(zip(pnames, args))
                    s = bind[lst]
                    if isinstance(s, str) and s in shadow and all(bind.get(v, v) == v for v in bfree):
                        found.setdefault(s, {})[b.text()] = b
                        prov.setdefault(s, {"def": [], "index_param": i})
                        if dname not in prov[s]["def"]:
                            prov[s]["def"].append(dname)
    problems: list[str] = []
    bases: dict[str, Lin] = {}
    for s, cand in found.items():
        if len(cand) != 1:
            problems.append(f"shadow list {s}: definitions disagree on its base {sorted(cand)}")
            continue
        bases[s] = next(iter(cand.values()))
    missing = [s for s in shadow if s not in bases]
    if missing and bases:
        common = {b.text() for b in bases.values()}
        ok = len(common) == 1 and _lockstep(facts, shadow, roles)
        if ok:
            b = next(iter(bases.values()))
            sib = sorted(bases)
            for s in missing:
                bases[s] = b
                prov[s] = {"lockstep_with": sib}
        else:
            problems.append(f"shadow lists {missing}: no definition fixes their base and the lockstep rule does "
                            "not apply; they stay position-keyed")
    elif missing:
        problems.append(f"shadow lists {missing}: no definition fixes their base; they stay position-keyed")
    for s in prov:
        if "def" in prov[s]:
            prov[s]["def"] = sorted(prov[s]["def"])
    return bases, prov, problems


def _norm_shadow(e, s: str, field: str):
    if isinstance(e, str):
        return "$S" if e == s else e
    if isinstance(e, list):
        out = []
        for i, x in enumerate(e):
            if i == 1 and e[0] == "call" and x == f"es_{field}":
                out.append("es_$")
            elif isinstance(x, dict):
                out.append({k: _norm_shadow(v, s, field) for k, v in x.items()})
            else:
                out.append(_norm_shadow(x, s, field))
        return out
    return e


def _lockstep(facts: dict, shadow: dict, roles: Roles) -> bool:
    for a in facts.get("actions", []):
        eff = a["effects"]
        touched = [s for s in shadow if s in eff]
        if not touched:
            continue
        if len(touched) != len(shadow):
            return False
        shapes = {repr(_norm_shadow(eff[s], s, shadow[s])) for s in shadow}
        if len(shapes) != 1:
            return False
    for m in facts.get("migrations", {}).values():
        for s in shadow:
            e = m["effects"].get(s)
            if e is None:
                continue
            if not (isinstance(e, list) and e[:2] == ["call", "zeros_like"] and e[2:] == [s]):
                return False
    return True
