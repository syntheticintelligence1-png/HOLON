"""Sort inference over holon-facts (whitepaper §7.7) with writer provenance (§7.3).

Input: a facts file (holon-facts/0.2 state machine or holon-facts/0.1 header facts) and its lexical seeds
(spec/M3/sorts/seeds.json: register / field / input / param sorts and realization widths). Output: an
Assignment: a sort for every register, field, input, parameter, let and def; the writer set of every
register; and the SORT obligations found at every site:

  realize      a signed difference (Time-Time, Idx-Idx, Cnt-Cnt) realized in an unsigned word; discharged
               when the nearest preceding guard syntactically implies non-negativity (then the law is
               "that guard never fails", i.e. no_code(reason) when the guard is a checked-arithmetic panic)
  sentinel     a register of a point sort (Time, Prin, Dig) tested against a literal while no writer is Null
  union_read   a union-sorted register read at one member's sort (ghost tag, Prop 6.19)
  tag_writer   a union register with a Null member is discriminated by `!= 0`, so every non-Null writer
               must be provably non-zero: Prin writers are discharged by a membership guard, Time writers
               never are (Time has no distinguished 0: SYM-tau)
  width        a sum whose worst-case width exceeds the realization width of the written register
  mismatch     two different base sorts compared

The assignment is frozen (written to the sorted facts) before any Bend typing (Theorem 6.18).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import grammar as G
from . import rules as R
from .grammar import BOOL, MACH, NULL, Sort


class SortError(Exception):
    pass


@dataclass
class Site:
    where: str                 # "action:commitBatch/guard[14]" | "def:w" | "observer:kappa" | "effect:Entry.bds"
    expr: list | str | int
    src: str = ""


@dataclass
class Obligation:
    kind: str
    site: Site
    detail: dict
    discharged: str | None = None        # how (guard text) when the obligation is discharged syntactically

    def to_json(self) -> dict:
        return {"kind": self.kind, "where": self.site.where, "src": self.site.src, "expr": self.site.expr,
                **self.detail, "discharged": self.discharged}


@dataclass
class Assignment:
    registers: dict = field(default_factory=dict)   # state field -> Sort
    fields: dict = field(default_factory=dict)      # "Type.f" -> Sort
    params: dict = field(default_factory=dict)
    inputs: dict = field(default_factory=dict)      # "action.input" -> Sort
    lets: dict = field(default_factory=dict)        # "action.let" -> Sort
    defs: dict = field(default_factory=dict)        # def name -> Sort of body
    widths: dict = field(default_factory=dict)      # register / field / input -> realization width
    writers: dict = field(default_factory=dict)     # register -> [{"site", "sort"}]
    obligations: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)   # ill-sorted combinations (minimal explanation: the site + both sorts)

    def to_json(self) -> dict:
        return {
            "registers": {k: str(v) for k, v in sorted(self.registers.items())},
            "fields": {k: str(v) for k, v in sorted(self.fields.items())},
            "params": {k: str(v) for k, v in sorted(self.params.items())},
            "inputs": {k: str(v) for k, v in sorted(self.inputs.items())},
            "lets": {k: str(v) for k, v in sorted(self.lets.items())},
            "defs": {k: str(v) for k, v in sorted(self.defs.items())},
            "widths": dict(sorted(self.widths.items())),
            "writers": {k: v for k, v in sorted(self.writers.items())},
            "obligations": [o.to_json() for o in self.obligations],
            "conflicts": self.conflicts,
        }


# builtins of the machine generator (holon.gen.machine) and their sort behaviour
_LIST_OF_ELEM = {"snoc": 0, "tail": 0, "drop": 0, "take": 0, "concat": 0, "remove": 1, "set_nat": 0, "zeros_like": 0,
                 "set_ch": 0, "bump_f": 0, "clear_chs": 0, "zero_csr": 0, "set_last_csr": 0}


class Inference:
    def __init__(self, facts: dict, seeds: dict):
        self.f = facts
        self.seeds = seeds
        self.a = Assignment()
        self.types = facts.get("types", {})
        self.state = {n: t for n, t, *_ in facts.get("state", [])}
        self.defs = facts.get("defs", {})
        self.families = seeds.get("list_families", {})
        self._seed()

    # ------------------------------------------------------------------ seeds (§7.7 step 1)
    def _seed(self) -> None:
        sd = self.seeds
        for ty, spec in self.types.items():
            for fname, ft in spec["fields"]:
                key = f"{ty}.{fname}"
                txt = sd.get("fields", {}).get(key)
                if txt is None:
                    if ft == "Bool":
                        self.a.fields[key] = BOOL
                        continue
                    raise SortError(f"no seed for field {key}")
                s, w = G.parse_seed(txt)
                self.a.fields[key] = s
                if w is not None:
                    self.a.widths[key] = w
        for n, t in self.state.items():
            txt = sd.get("registers", {}).get(n)
            if txt is None:
                if t == "Bool":
                    s = BOOL
                elif t == "List<Obs>":
                    s = G.lst(MACH)
                elif t.startswith("List<") and t[5:-1] in self.types:
                    s = G.lst(self._record_sort(t[5:-1]))
                elif t in self.types:
                    s = self._record_sort(t)
                else:
                    raise SortError(f"no seed for register {n}: {t}")
                self.a.registers[n] = s
                continue
            s, w = G.parse_seed(txt)
            if t.startswith("List<") and s.kind != "List":
                s = G.lst(s)
            self.a.registers[n] = s
            if w is not None:
                self.a.widths[n] = w
        for p in self.f.get("params", {}):
            txt = sd.get("params", {}).get(p)
            if txt is None:
                raise SortError(f"no seed for param {p}")
            self.a.params[p] = G.parse(txt)
        for act in self.f.get("actions", []):
            for n, t in act["inputs"]:
                key = f"{act['name']}.{n}"
                txt = sd.get("inputs", {}).get(key) or sd.get("inputs", {}).get("*." + n)
                if txt is None:
                    if t == "Bool":
                        self.a.inputs[key] = BOOL
                        continue
                    raise SortError(f"no seed for input {key}")
                s, w = G.parse_seed(txt)
                if t.startswith("List<") and s.kind != "List":
                    s = G.lst(s)
                self.a.inputs[key] = s
                if w is not None:
                    self.a.widths[key] = w
        for m, spec in self.f.get("migrations", {}).items():
            for n, t in spec.get("inputs", []):
                key = f"{m}.{n}"
                txt = sd.get("inputs", {}).get(key)
                if txt is None:
                    raise SortError(f"no seed for migration input {key}")
                self.a.inputs[key] = G.parse(txt)

    def _record_sort(self, ty: str) -> Sort:
        return G.record({f: self.a.fields.get(f"{ty}.{f}", BOOL if t == "Bool" else MACH) for f, t in self.types[ty]["fields"]})

    # ------------------------------------------------------------------ helpers
    def _ob(self, kind: str, site: Site, detail: dict, discharged: str | None = None) -> None:
        self.a.obligations.append(Obligation(kind, site, detail, discharged))

    def _conflict(self, site: Site, msg: str) -> None:
        self.a.conflicts.append({"where": site.where, "src": site.src, "expr": site.expr, "why": msg})

    def _family(self, e, env: dict) -> str | None:
        if isinstance(e, str) and e in self.families:
            return self.families[e]
        if isinstance(e, list) and e[0] == "call" and e[1] in _LIST_OF_ELEM:
            return self._family(e[2 + _LIST_OF_ELEM[e[1]]], env)
        return None

    def _elem(self, s: Sort) -> Sort:
        if s.kind == "List":
            return s.members[0]
        raise SortError(f"not a list sort: {s}")

    def _empty_record(self, ty: str) -> Sort:
        """The storage default of a record: Null for point sorts (Prin, Time, Dig), the field's own sort otherwise (0 is a count)."""
        out = {}
        for f, t in self.types[ty]["fields"]:
            fs = self.a.fields[f"{ty}.{f}"]
            out[f] = BOOL if t == "Bool" else (NULL if fs.kind in ("Prin", "Time", "Dig") or (fs.kind == "Union" and NULL in fs.members) else fs)
        return G.record(out)

    def _write_record(self, ty: str, rec: Sort, site: Site) -> None:
        for m in G.members(rec):
            if m.kind != "Record":
                continue
            for f, fs in m.members:
                if fs != BOOL:
                    self._write(f"{ty}.{f}", fs, None, Site(site.where, f"{ty}.{f}", site.src))

    def _field_width(self, f: str) -> int | None:
        ws = {self.a.widths[k] for k in self.a.widths if k.endswith("." + f)}
        return max(ws) if ws else None

    def _field(self, s: Sort, f: str) -> Sort:
        if s.kind == "Record":
            d = dict(s.members)
            if f in d:
                return d[f]
        if s.kind == "Union":
            return G.union(*(self._field(m, f) for m in s.members))
        raise SortError(f"get {f} of {s}")

    # ------------------------------------------------------------------ expression sorts (§7.2, §7.4)
    def sort(self, e, env: dict, site: Site, guards: list | None = None) -> Sort:  # noqa: C901
        s, _ = self.sort_w(e, env, site, guards)
        return s

    def sort_w(self, e, env: dict, site: Site, guards: list | None = None) -> tuple[Sort, int | None]:  # noqa: C901
        """Sort and worst-case width (None = unknown) of an expression."""
        if isinstance(e, bool):
            return BOOL, 1
        if isinstance(e, int):
            return (NULL if e == 0 else MACH), max(1, e.bit_length())
        if isinstance(e, str):
            if e in env:
                return env[e]
            if e in self.a.params:
                return self.a.params[e], None
            raise SortError(f"{site.where}: unbound {e!r}")
        if isinstance(e, dict):
            raise SortError(f"{site.where}: bare record literal")
        op = e[0]
        if op in ("+", "-", "*"):
            (sa, wa), (sb, wb) = self.sort_w(e[1], env, site, guards), self.sort_w(e[2], env, site, guards)
            la, lb = sa == NULL, sb == NULL
            sa2, sb2 = (MACH if la else sa), (MACH if lb else sb)
            for s_, other in ((sa2, sb2), (sb2, sa2)):
                if s_.kind == "Union" and NULL in s_.members:
                    exp = G.union(*(m for m in s_.members if m != NULL))
                    self._ob("union_read", site, {"sort": str(s_), "expected": str(exp), "others": ["Null"], "op": op})
            try:
                out = R.combine(op, sa2, sb2)
            except R.IllSorted as x:
                self._conflict(site, str(x))
                return MACH, None
            if op == "-" and R.realize_obligation(out):
                self._ob("realize", site, {**R.realize_obligation(out), "minuend": str(sa2), "subtrahend": str(sb2)},
                         discharged=self._discharge_sub(e[1], e[2], guards))
            w = R.width_of_sum([wa, wb]) if op == "+" else (wa if op == "-" else None)
            return out, w
        if op in ("<", "<=", ">", ">=", "==", "!="):
            (sa, _), (sb, _) = self.sort_w(e[1], env, site, guards), self.sort_w(e[2], env, site, guards)
            self._compare(op, sa, sb, e, site)
            return BOOL, 1
        if op in ("&&", "||"):
            for x in e[1:]:
                self.sort_w(x, env, site, guards)
            return BOOL, 1
        if op == "!":
            self.sort_w(e[1], env, site, guards)
            return BOOL, 1
        if op == "?":
            self.sort_w(e[1], env, site, guards)
            gthen = list(guards or []) + [{"require": e[1]}]
            (sa, wa), (sb, wb) = self.sort_w(e[2], env, site, gthen), self.sort_w(e[3], env, site, guards)
            if sa == MACH and sb.kind not in ("Mach",):
                sa = sb
            if sb == MACH and sa.kind not in ("Mach",):
                sb = sa
            if sa == NULL:
                sa = NULL if sb.kind in ("Prin", "Time", "Dig", "Union") else sb
            if sb == NULL:
                sb = NULL if sa.kind in ("Prin", "Time", "Dig", "Union") else sa
            return G.union(sa, sb), (None if wa is None or wb is None else max(wa, wb))
        if op == "get":
            s = self.sort(e[1], env, site, guards)
            return self._field(s, e[2]), self._field_width(e[2])
        if op in ("mk", "with"):
            ty = e[1]
            base = self.sort(e[2], env, site, guards) if op == "with" else None
            fields = dict(base.members) if base is not None and base.kind == "Record" else {}
            vals = e[3] if op == "with" else e[2]
            for fname, fe in vals.items():
                s, w = self.sort_w(fe, env, site, guards)
                key = f"{ty}.{fname}"
                self._write(key, s, w, Site(site.where, fe, site.src))
                fields[fname] = self.a.fields[key]
            for fname, _t in self.types[ty]["fields"]:
                fields.setdefault(fname, self.a.fields[f"{ty}.{fname}"])
            return G.record(fields), None
        if op == "call":
            return self._call(e[1], e[2:], env, site, guards)
        raise SortError(f"{site.where}: unknown op {op}")

    def _compare(self, op: str, sa: Sort, sb: Sort, e, site: Site) -> None:
        la, lb = sa in (NULL, MACH), sb in (NULL, MACH)
        if la and lb:
            return
        if la:
            sa, sb, e = sb, sa, [op, e[2], e[1]]
            lb = True
        if lb:
            if sa.kind == "Union" and NULL in sa.members:
                # discriminating the union by its Null member: a tag test, well-sorted; the writers carry the obligation
                self._ob("tag_test", site, {"sort": str(sa), "op": op})
                return
            r = R.compare(op, sa, MACH)
            if r:
                self._ob("sentinel", site, {**r, "literal": e[2]})
            return
        r = R.compare(op, sa, sb)
        if r:
            self._ob("mismatch", site, r)

    def _write(self, reg: str, s: Sort, w: int | None, site: Site) -> None:
        """Writer provenance (§7.3): a register's sort is the union of its seed and all writer sorts."""
        table = self.a.fields if "." in reg else self.a.registers
        cur = table.get(reg)
        ws = NULL if s == NULL else s
        if ws == MACH and cur is not None:
            ws = cur                      # a non-zero literal adopts the register's sort (unit / constant)
        self.a.writers.setdefault(reg, [])
        ent = {"site": site.where, "sort": str(ws), "expr": site.expr}
        if ent not in self.a.writers[reg]:
            self.a.writers[reg].append(ent)
        if cur is None:
            table[reg] = ws
        elif cur.kind == "List" and ws.kind == "List":
            table[reg] = G.lst(G.union(cur.members[0], ws.members[0]))
        elif cur.kind == "List" or ws.kind == "List" or cur.kind == "Record" or ws.kind == "Record":
            table[reg] = cur
        elif cur == BOOL or ws == BOOL:
            pass
        elif {cur.kind, ws.kind} == {"Idx", "Cnt"} and cur.arg == ws.arg:
            self._ob("coercion", site, {"register": reg, "from": str(ws), "to": str(cur)}, discharged="zero-based index: Cnt[k] -> Idx[k]")
        else:
            table[reg] = G.union(cur, ws)
        rw = self.a.widths.get(reg)
        ob = R.width_obligation(w, rw)
        if ob:
            self._ob("width", site, {**ob, "register": reg},
                     discharged="EVM word: a counter cannot reach 2^256" if rw is not None and rw >= 256 else None)

    def _discharge_sub(self, a, b, guards: list | None) -> str | None:
        """Does a preceding `require` syntactically imply a >= b (so the realization cannot underflow)?"""
        def expand(c):
            if not isinstance(c, list):
                return []
            if c[0] == "&&":
                return [x for y in c[1:] for x in expand(y)]
            if c[0] == "||" and len(c) == 3 and isinstance(c[1], list) and c[1][0] == "!":
                return [c] + expand(c[2])
            if c[0] == "call" and c[1] in self.defs:
                d = self.defs[c[1]]
                sub = {p: v for (p, _t), v in zip(d["params"], c[2:])}

                def subst(x):
                    if isinstance(x, str) and x in sub:
                        return sub[x]
                    if isinstance(x, list):
                        return [subst(y) for y in x]
                    return x
                return expand(subst(d["body"]))
            return [c]
        for g in guards or []:
            c = g.get("require")
            if c is None:
                continue
            forms = expand(c)
            for cc in forms:
                if not isinstance(cc, list) or len(cc) != 3:
                    continue
                o, l, r = cc
                if (o in (">", ">=") and l == a and r == b) or (o in ("<", "<=") and l == b and r == a):
                    return json.dumps(c) + (f" (reason {g['reason']})" if "reason" in g else "")
        return None

    def _call(self, fn: str, args: list, env: dict, site: Site, guards) -> tuple[Sort, int | None]:  # noqa: C901
        sw = [self.sort_w(x, env, site, guards) for x in args]
        ss = [s for s, _ in sw]
        if fn in self.defs:
            d = self.defs[fn]
            denv = {p: (s if s != NULL else MACH, w) for (p, _t), (s, w) in zip(d["params"], sw)}
            for (p, _t), s in zip(d["params"], ss):
                pass
            out = self.sort_w(d["body"], denv, Site(f"def:{fn}", d["body"], d.get("src", "")), None)
            self.a.defs[fn] = out[0]
            return out
        fam = self._family(args[0], env) if args else None
        if fn == "len":
            return G.cnt(fam or "?"), None
        if fn in ("nth", "nth_ch", "win_at"):
            elem = self._elem(ss[0])
            if fam and ss[1].kind not in ("Idx", "Cnt", "Mach", "Null") and ss[1] != NULL:
                self._ob("mismatch", site, {"left": str(ss[1]), "right": f"Idx[{fam}]", "op": fn})
            return elem, None
        if fn == "mem":
            if ss[1].kind == "List" and R.read_at(ss[0], self._elem(ss[1])):
                self._ob("union_read", site, {**R.read_at(ss[0], self._elem(ss[1])), "op": fn})
            return BOOL, 1
        if fn == "remove":
            elem = self._elem(ss[1])
            ob = R.read_at(ss[0], elem)
            if ob:
                self._ob("union_read", site, {**ob, "op": fn})
            return ss[1], None
        if fn == "set_ch":
            self._write_record("Ch", ss[2], site)
            return ss[0], None
        if fn in ("snoc", "set_nat", "set_last_csr"):
            elem = self._elem(ss[0])
            v = ss[-1]
            if v.kind == "Record" and fn == "snoc":
                self._write_record("Entry", v, site)
            if v == MACH or v == NULL:
                return ss[0], None
            return G.lst(G.union(elem, v)) if v.kind != "Record" else ss[0], None
        if fn in ("tail", "drop", "take", "concat", "zeros_like", "bump_f", "clear_chs", "zero_csr"):
            return ss[0], None
        if fn in ("es_csr", "es_bd", "es_bvh", "es_tag"):
            fld = fn[3:]
            if fld == "bd":
                return G.lst(self._record_sort("BD")), None
            return G.lst(self.a.fields[f"Entry.{fld}"]), None
        if fn == "win_last":
            return self._elem(ss[0]), None
        if fn in ("empty_entry", "empty_ch"):
            return self._empty_record("Entry" if fn == "empty_entry" else "Ch"), None
        if fn in ("agg", "blob_hash"):
            return G.dig("agg"), None
        if fn == "blob_count":
            return G.cnt("blob"), None
        if fn in ("any_open", "open_ch", "in_win", "tags_exact", "eq_nats", "lci"):
            return (G.idx("batch") if fn == "lci" else BOOL), None
        if fn == "hdr_of":
            return G.lst(MACH), None
        if fn.startswith("go_") or fn in ("first_ge", "pair", "enc", "zeros", "put", "overlay"):
            return (ss[0] if ss and ss[0].kind == "List" else MACH), None
        if fn.startswith("pred_"):
            return BOOL, 1
        if fn.startswith("map_"):
            return ss[0], None
        raise SortError(f"{site.where}: unknown builtin {fn}")

    # ------------------------------------------------------------------ driver
    def run(self) -> Assignment:
        """Walk every action (guards in order, then effects), observers and migrations; iterate to a fixpoint."""
        for _round in range(4):
            before = json.dumps(self.a.to_json(), sort_keys=True)
            self.a.obligations, self.a.conflicts = [], []
            for name, d in self.defs.items():
                env = {}
                for p, t in d["params"]:
                    env[p] = (self._param_sort(p, t), None)
                self.a.defs[name] = self.sort(d["body"], env, Site(f"def:{name}", d["body"], d.get("src", "")))
            for act in self.f.get("actions", []):
                self._action(act)
            for name, o in self.f.get("observers", {}).items():
                env = {n: (s, self.a.widths.get(n)) for n, s in self.a.registers.items()}
                self.sort(o["body"], env, Site(f"observer:{name}", o["body"], o.get("src", "")))
            for name, m in self.f.get("migrations", {}).items():
                env = {n: (s, self.a.widths.get(n)) for n, s in self.a.registers.items()}
                for n, _t in m.get("inputs", []):
                    env[n] = (self.a.inputs[f"{name}.{n}"], None)
                for reg, e in m.get("effects", {}).items():
                    s, w = self.sort_w(e, env, Site(f"migration:{name}/effect:{reg}", e, m.get("src", "")))
                    self._write(reg, s, w, Site(f"migration:{name}", e, m.get("src", "")))
            self._initial_writes()
            self._tag_writers()
            if json.dumps(self.a.to_json(), sort_keys=True) == before:
                break
        seen: dict = {}
        for o in self.a.obligations:
            key = (o.kind, o.site.where, json.dumps(o.site.expr, sort_keys=True), json.dumps(o.detail, sort_keys=True))
            seen.setdefault(key, o)
        self.a.obligations = sorted(seen.values(), key=lambda o: (o.kind, o.site.where, json.dumps(o.site.expr, sort_keys=True)))
        return self.a

    def _param_sort(self, p: str, t: str) -> Sort:
        if p in self.a.registers:
            return self.a.registers[p]
        if t == "Bool":
            return BOOL
        if t.startswith("List<"):
            inner = t[5:-1]
            return G.lst(self._record_sort(inner)) if inner in self.types else G.lst(MACH)
        if t in self.types:
            return self._record_sort(t)
        return self.seeds.get("def_params", {}).get(p) and G.parse(self.seeds["def_params"][p]) or MACH

    def _action(self, act: dict) -> None:
        name = act["name"]
        env = {n: (s, self.a.widths.get(n)) for n, s in self.a.registers.items()}
        for n, _t in act["inputs"]:
            key = f"{name}.{n}"
            env[n] = (self.a.inputs[key], self.a.widths.get(key))
        seen: list = []
        for i, g in enumerate(act.get("guards", [])):
            site = Site(f"action:{name}/guard[{i}]", g.get("require", g.get("expr")), g.get("src", ""))
            if "let" in g:
                s, w = self.sort_w(g["expr"], env, site, seen)
                env[g["let"]] = (s, w)
                self.a.lets[f"{name}.{g['let']}"] = s
            else:
                self.sort_w(g["require"], env, site, seen)
            seen.append(g)
        for reg, e in act.get("effects", {}).items():
            site = Site(f"action:{name}/effect:{reg}", e, act.get("src", ""))
            s, w = self.sort_w(e, env, site, seen)
            self._write(reg, s, w, site)

    def _initial_writes(self) -> None:
        init = self.f.get("initial", {})
        for reg, v in init.items():
            if reg in ("doc",) or reg not in self.state:
                continue
            site = Site("initial", v if not isinstance(v, (list, dict)) else "...", init.get("doc", ""))
            if isinstance(v, list) and v and isinstance(v[0], dict):
                ty = self.state[reg][5:-1]
                for ent in v:
                    for fname, fv in ent.items():
                        key = f"{ty}.{fname}"
                        base = G.union(*(m for m in G.members(self.a.fields[key]) if m != NULL))
                        if not isinstance(fv, bool) and fv == 0 and base.kind in ("Prin", "Time", "Dig"):
                            self._write(key, NULL, None, Site("initial", fv, init.get("doc", "")))

    def _tag_writers(self) -> None:
        """§7.3/§7.4: for each union register with a Null member that is tag-tested, each non-Null writer must be non-zero."""
        tested = {o.detail["sort"] for o in self.a.obligations if o.kind == "tag_test"}
        tested_regs = {reg for reg, s in {**self.a.registers, **self.a.fields}.items()
                       if s.kind == "Union" and NULL in s.members and str(s) in tested}
        for reg in sorted(tested_regs):
            for w in self.a.writers.get(reg, []):
                if w["sort"] in ("Null",) or "Null" in w["sort"] or w["expr"] == reg:
                    continue
                ws = G.parse(w["sort"]) if "<" not in w["sort"] else None
                if ws is None:
                    continue
                act = w["site"].split("/")[0].replace("action:", "")
                disch = None
                if ws.kind == "Prin":
                    for a in self.f.get("actions", []):
                        if a["name"] == act:
                            for g in a.get("guards", []):
                                c = g.get("require")
                                if isinstance(c, list) and c[0] == "call" and c[1] == "mem" and c[2] == w["expr"]:
                                    disch = f"membership guard {json.dumps(c)}"
                                if isinstance(c, list) and c[0] == "==" and c[1] == w["expr"]:
                                    disch = f"equality guard {json.dumps(c)}"
                self._ob("tag_writer", Site(w["site"], w["expr"]), {"register": reg, "writer_sort": w["sort"],
                         "union": str((self.a.fields if "." in reg else self.a.registers)[reg])}, discharged=disch)


def infer(facts: dict, seeds: dict) -> Assignment:
    return Inference(facts, seeds).run()


# ---------------------------------------------------------------------- holon-facts/0.1 header facts (M0)
def infer_header(facts: dict, seeds: dict) -> dict:
    """Header facts (facts/morph_header.json): each field has a byte width and a seed sort; the width rule checks
    that every field realized in w bytes has a sort whose natural width fits (Ver in 1 byte, Idx/Cnt in 8, Dig in 32)."""
    out = {"fields": {}, "obligations": []}
    natural = {"Ver": 1, "Idx": 8, "Cnt": 8, "Time": 8, "Dig": 32, "Amt": 32, "Mach": None, "Prin": 20}
    for fld in facts.get("types", {}).get("Header", {}).get("fields", []):
        name = fld["name"]
        width = fld.get("width")
        txt = seeds.get("header_fields", {}).get(name)
        if txt is None:
            out["obligations"].append({"kind": "unsorted", "field": name})
            continue
        s = G.parse(txt)
        out["fields"][name] = str(s)
        nat = natural.get(s.kind)
        if nat is not None and width is not None and width < nat:
            out["obligations"].append({"kind": "width", "field": name, "sort": str(s), "realized_bytes": width, "needed_bytes": nat})
    return out
