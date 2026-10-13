"""The holon-facts/0.3 adapter of the sorts pass (BUILD_PLAN I30; whitepaper §7.1-§7.4, §7.7; the contract is the
docstring of tests_m3/test_sort_types.py, rules E1-E5).

A transitions document (holon.frontends.solidity.transitions, I19/A19) is walked record by record (every guard reach,
check, panic, call, write, event and loop record of every action, in walk (seq) order; holon.machine.FORMAT names the
sections) into the events holon.sorts.constraints turns into constraints, in I13's shapes (holon.sorts.flow.Program),
so that I13's solver, cores, unions and writer labels are reused unchanged.

Variables (E2):
  "<family>"                    a scalar family's value, a mapping's values, an array's elements
  "<family>.<member>"           a member of a struct family (a struct value of a mapping, or a struct scalar)
  "<action>.<param>"            a parameter (and "<action>.<param>.<member>" a member of a struct parameter)
  "<action>.<param>@<k>"        the word or byte of a bytes parameter at constant offset k
  "env:<name>"                  an environment member (block.*, msg.*, tx.*; ["caller"] is env:caller, ["this"]
                                env:this), shared by every action
  "call:<fn>"                   the result of external function fn, shared by its call sites (A-env)
  "loop:<span>[#r]:<name>"      a loop's symbols: iter, count, and each carried name (its label: the local's name, or
                                storage.<family>); r the loop's reach index when r > 0 (holon.machine.Loop.sym)
  "$<n>"                        auxiliaries (a subterm's value, a literal operand)

Flow. A storage write flows its value into the family (a struct literal's members into "<family>.<member>"); ["?", c,
x, y] flows x and y into its result; a loop's entry, next, at_break and exit values flow into its carried names; + and
- are affine constraints (§7.2); comparisons (== != < <= > >=) are compare constraints; a constraint's src is the src
of the record that holds its term. Opaque (a fresh variable; nothing flows in or out): keccak256 and sha256 results,
memory regions and their stores, * / % ** and the bit operations, shifts, masks, byte and word extraction other than
"@k", ABI encodings and the arguments of external calls, lengths, code, balance, immutables, sload and unknown terms,
except where a seed applies. A literal carries no sort (a fresh auxiliary only as an affine operand).

Seeds (E3; holon-sort-seeds/0.2, the sidecar's seeds file, no other vocabulary): "term" seeds (a term whose head is
`head`, and first argument `arg` when given, has the sort: a unit constraint on the variable of every matching term);
"digest" seeds (a hash term of one of `heads` over a memory region ["slice", ["mem", ..], ..] every one of whose
stores, mstore and the stores of an mloop or when, writes a term a term seed gives sort `words`, has `sort`); "lexical"
seeds ({match: "family", pattern, sort}: every storage family whose name the regex matches). Writer labels are I13's
rules (holon.sorts.unions.labels, the seeds file's writer_labels).

Sites (E4): every ["-", a, b] term, grouped by (model, span, canonical node); span: the src of the action's panic
record whose op is "-" and whose args are [a, b] (checked arithmetic, the site's realization check), else the src of
the first record, in walk order, that holds the term; "checked" whether such a realization check exists.

Coherence (E5): `obstructions` (I15's R11 over 0.3) and `external_guards` (the guards of that form whose kappa reads an
external call's result, which the document cannot check).

Nothing here names a target: every name comes from the document, the seeds file and the sidecar.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from . import grammar as G
from .flow import Program

SEEDS_VERSION = "holon-sort-seeds/0.2"
KAPPA = "kappa"          # an obstruction's antecedent (I15's R11 format)
TAG_HEAD = "tag"         # a companion read in a tag term (rule G2): ["tag", family, key]
CMP = ("<", "<=", ">", ">=", "==", "!=")
OPAQUE_BIN = ("*", "/", "%", "**", "&", "|", "^", "<<", ">>")
SECTIONS = ("checks", "panics", "calls", "guards", "loops", "writes", "mstores", "events")
# the term fields of each record (holon.machine.ExtractedModel.terms)
RECORD_TERMS = {"guards": ("expr", "args"), "panics": ("expr", "args"),
                "calls": ("receiver", "args", "value", "cond", "expr"), "checks": ("expr",),
                "writes": ("path", "value", "cond"), "mstores": ("offset", "value", "cond"),
                "events": ("args", "topics", "cond"), "loops": ("cond", "head", "break", "count", "bound")}


class ExtractedError(ValueError):
    """A 0.3 construct the adapter cannot map (no silent drops)."""


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def ckey(t) -> str:
    return canonical(t).decode("utf-8")


@dataclass
class Ctx:
    actor_kind: str          # "action"
    actor: str               # the action's name
    where: str               # "<section>[<i>]" of the record that holds the term
    src: str | None          # the record's src (the constraint src)
    entry_span: str | None   # the same
    mode: str                # guard | check | panic | call | write | event | loop | mstore
    seq: int = -1


@dataclass
class Record:
    """One program record of an action (a guard reach is a record of its guard: where guards[i])."""
    action: str
    section: str
    index: int
    seq: int
    src: str | None
    rec: dict
    parent: dict


@dataclass
class Walk:
    """What the walk of one document gives: I13's Program, the seed grounds, the subtraction occurrences."""
    prog: Program
    grounds: dict = field(default_factory=dict)        # var -> [(ground, sort)]
    subs: list = field(default_factory=list)            # (node, lhs, rhs, out, Ctx)
    holders: dict = field(default_factory=dict)         # (action, ckey(node)) -> [(seq, where, src)]
    families: dict = field(default_factory=dict)        # family -> {"kind", "value", "fields"}
    params: dict = field(default_factory=dict)          # action -> {param: param record}


# ------------------------------------------------------------------------------------------------ helpers
def family_table(doc: dict) -> dict:
    """family name -> its record (storage and inherited storage; a name two contracts declare is
    "<declared_in>.<name>", as holon.machine names it)."""
    rows = list(doc.get("storage") or []) + list(doc.get("inherited_storage") or [])
    names = [r["name"] for r in rows]
    out = {}
    for r in rows:
        n = r["name"]
        if names.count(n) > 1 and r.get("declared_in"):
            n = f"{r['declared_in']}.{n}"
        out[n] = r
    return out


def is_bool_type(t) -> bool:
    return isinstance(t, str) and t == "bool"


def loop_label(name) -> str:
    if isinstance(name, list) and len(name) == 2 and name[0] == "storage":
        return f"storage.{name[1]}"
    return name if isinstance(name, str) else ckey(name)


def action_records(a: dict) -> list[Record]:
    """Every record of an action, in walk (seq) order; a guard's reaches are records of guards[i]."""
    out = []
    for sec in SECTIONS:
        for i, r in enumerate(a.get(sec) or []):
            if not isinstance(r, dict):
                continue
            if sec == "guards":
                for x in r.get("reaches") or []:
                    out.append(Record(a["name"], sec, i, int(x.get("seq", -1)), r.get("src"), x, r))
            else:
                out.append(Record(a["name"], sec, i, int(r.get("seq", -1)), r.get("src"), r, r))
    return sorted(out, key=lambda x: (x.seq, x.section, x.index))


def record_terms(r: Record):
    """(field, term) of every term a record holds (holon.machine.ExtractedModel.terms' keys)."""
    rec = r.rec
    for k in RECORD_TERMS[r.section]:
        if k in rec:
            yield k, rec[k]
    if r.section == "loops":
        for k, v in (("carried", "entry"), ("carried", "value"), ("next", "value"), ("at_break", "value"),
                     ("exit", "value")):
            for x in rec.get(k) or []:
                if isinstance(x, dict):
                    yield f"{k}.{loop_label(x.get('name'))}.{v}", x.get(v)
        for j, x in enumerate(rec.get("returns") or []):
            yield f"returns[{j}].cond", x.get("cond")
            yield f"returns[{j}].value", x.get("value")


def contains(t, node) -> bool:
    if t == node:
        return True
    if isinstance(t, list):
        return any(contains(x, node) for x in t)
    if isinstance(t, dict):
        return any(contains(x, node) for x in t.values())
    return False


def loop_spans(a: dict) -> dict:
    """seq of a loop record -> its symbol suffix (span, plus #r for its reach index r > 0)."""
    out, n = {}, {}
    for r in sorted(a.get("loops") or [], key=lambda x: x.get("seq", 0)):
        k = n.get(r.get("src"), 0)
        n[r.get("src")] = k + 1
        out[r["seq"]] = (r.get("src"), k)
    return out


# ------------------------------------------------------------------------------------------------ the walk
class Walker:
    def __init__(self, model: str, doc: dict, seeds: dict):
        self.model = model
        self.doc = doc
        self.seeds = seeds
        self.p = Program(model)
        self.w = Walk(self.p)
        self.n = 0
        self.fams = family_table(doc)
        self.w.families = self.fams
        self.term_seeds = list(seeds.get("term") or [])
        self.digest_seeds = list(seeds.get("digest") or [])
        lex = list(seeds.get("lexical") or [])
        for s in self.term_seeds + self.digest_seeds + lex:
            G.canonical(s["sort"])
        for s in lex:
            if s.get("match") != "family":
                raise ExtractedError(f"lexical seed {s.get('id')}: match {s.get('match')!r} is not family")
        self.lexical = lex

    # ---------------------------------------------------------- keys and events
    def key(self, name: str, ty: str, binder: str) -> None:
        cur = self.p.keys.get(name)
        if cur is None:
            self.p.keys[name] = {"type": ty, "binder": binder, "ghost": False}

    def fresh(self) -> str:
        self.n += 1
        return f"${self.n}"

    def ev(self, *e) -> None:
        self.p.events.append(e)

    def flow(self, a, b, ctx: Ctx) -> None:
        if a is not None and b is not None and a != b:
            self.ev("flow", a, b, ctx)

    def ground(self, var: str, gid: str, sort: str) -> None:
        g = self.w.grounds.setdefault(var, [])
        if (gid, sort) not in g:
            g.append((gid, sort))

    # ---------------------------------------------------------- seeds
    def term_seed(self, t) -> list:
        """The term seeds a term matches: [(id, sort)]."""
        out = []
        if isinstance(t, list) and t and isinstance(t[0], str):
            for s in self.term_seeds:
                if t[0] != s.get("head"):
                    continue
                if "arg" in s and (len(t) < 2 or t[1] != s["arg"]):
                    continue
                out.append((s["id"], G.canonical(s["sort"])))
        return out

    def region_stores(self, mem) -> list | None:
        """The stored value terms of a memory region (mstore and mstore8 values, through mloop and when); None when
        the region holds another kind of write."""
        out = []

        def walk(w) -> bool:
            if not isinstance(w, list) or not w:
                return False
            k = w[0]
            if k in ("mstore", "mstore8"):
                out.append(w[2])
                return True
            if k == "mloop":
                body = w[4] if isinstance(w[4], list) and w[4] and isinstance(w[4][0], list) else [w[4]]
                return all(walk(x) for x in body)
            if k == "when":
                return walk(w[2])
            return False
        if not (isinstance(mem, list) and mem and mem[0] == "mem"):
            return None
        for w in mem[1:]:
            if not walk(w):
                return None
        return out

    def digest_seed(self, t) -> list:
        out = []
        if not (isinstance(t, list) and len(t) >= 2 and isinstance(t[0], str)):
            return out
        arg = t[1]
        if not (isinstance(arg, list) and arg and arg[0] == "slice" and len(arg) >= 2):
            return out
        stores = self.region_stores(arg[1])
        if not stores:
            return out
        for s in self.digest_seeds:
            if t[0] not in (s.get("heads") or []):
                continue
            want = G.canonical(s["words"])
            if all(any(srt == want for _gid, srt in self.term_seed(x)) for x in stores):
                out.append((s["id"], G.canonical(s["sort"])))
        return out

    # ---------------------------------------------------------- variables of storage and parameter terms
    def family_var(self, t) -> str | None:
        """The variable a storage read term names (E2), or None when it is not a storage path."""
        if not isinstance(t, list) or not t:
            return None
        h = t[0]
        if h == "storage" and isinstance(t[1], str):
            return t[1]
        if h in ("map", "index") and len(t) >= 2:
            return self.family_var(t[1])
        if h == "member" and len(t) >= 3:
            base = self.family_var(t[1])
            return f"{base}.{t[2]}" if base is not None else None
        return None

    def param_var(self, t, action: str) -> str | None:
        if not isinstance(t, list) or not t:
            return None
        h = t[0]
        if h == "param" and isinstance(t[1], str):
            return f"{action}.{t[1]}"
        if h == "member" and len(t) >= 3:
            base = self.param_var(t[1], action)
            return f"{base}.{t[2]}" if base is not None else None
        if h == "index" and len(t) >= 2:
            return self.param_var(t[1], action)
        return None

    def family_key(self, var: str) -> None:
        base, _, mem = var.partition(".")
        fam = self.fams.get(base)
        ty = "Word"
        if fam is not None:
            if mem:
                f = next((x for x in fam.get("fields") or [] if x.get("name") == mem), None)
                if f is not None and is_bool_type(f.get("type")):
                    ty = "Bool"
            elif is_bool_type(fam.get("value")):
                ty = "Bool"
        self.key(var, ty, "family")
        self.p.registers.add(var)

    # ---------------------------------------------------------- terms
    def ex(self, t, ctx: Ctx):
        """(variable or None, registers read) of a term; records the events of every node."""
        v, r = self._ex(t, ctx)
        for gid, srt in self.term_seed(t) + self.digest_seed(t):
            if v is None:
                v = self.fresh()
            self.ground(v, gid, srt)
        return v, r

    def walk_all(self, ts, ctx: Ctx) -> frozenset:
        reads = frozenset()
        for x in ts:
            _, r = self.ex(x, ctx)
            reads |= r
        return reads

    def _ex(self, t, ctx: Ctx):
        if isinstance(t, bool) or isinstance(t, int) or t is None:
            return None, frozenset()
        if isinstance(t, str):
            return None, frozenset()
        if isinstance(t, list) and not t:
            return None, frozenset()
        if not isinstance(t, list):
            raise ExtractedError(f"{ctx.actor} ({ctx.where}): bad term {t!r}")
        h = t[0]
        if all(isinstance(x, str) for x in t) and len(t) > 1 and (":" in h or "/" in h):
            return None, frozenset()   # a memory region's id (its spans), not a term
        if not isinstance(h, str):     # a list of terms (an mloop body, a path)
            return None, self.walk_all(t, ctx)
        a = t[1:]
        if h in ("+", "-") and len(a) == 2:
            (va, ra), (vb, rb) = self.ex(a[0], ctx), self.ex(a[1], ctx)
            lhs = va if va is not None else self.fresh()
            rhs = vb if vb is not None else self.fresh()
            out = self.fresh()
            self.ev("affine", h, lhs, rhs, out, t, ctx)
            if h == "-":
                self.ev("sub", t, lhs, rhs, out, ctx)
                self.w.subs.append((t, lhs, rhs, out, ctx))
            return out, ra | rb
        if h in CMP and len(a) == 2:
            (va, ra), (vb, rb) = self.ex(a[0], ctx), self.ex(a[1], ctx)
            if va is not None and vb is not None:
                self.ev("compare", h, va, vb, t, ctx, None)
            return None, ra | rb
        if h in ("&&", "||", "!"):
            return None, self.walk_all(a, ctx)
        if h == "?":
            if len(a) != 3:
                raise ExtractedError(f"{ctx.actor} ({ctx.where}): ? takes three operands")
            _, rc = self.ex(a[0], ctx)
            (vx, rx), (vy, ry) = self.ex(a[1], ctx), self.ex(a[2], ctx)
            vs = [x for x in (vx, vy) if x is not None]
            if not vs:
                return None, rc | rx | ry
            out = self.fresh()
            for x in vs:
                self.flow(x, out, ctx)
            return out, rc | rx | ry
        if h in ("fits", "sfits", "callok", "returned"):
            return None, self.walk_all(a[1:] if h in ("fits", "sfits") else a, ctx)
        if h == "storage":
            var = t[1]
            if var not in self.fams:
                self.fams[var] = {"name": var, "kind": "scalar", "value": None}
            fam = self.fams[var]
            if fam.get("kind") == "scalar" and not fam.get("fields"):
                self.family_key(var)
                return var, frozenset({var})
            return None, frozenset()     # a container: its values are named through map / index / member
        if h in ("map", "index", "member"):
            fv = self.family_var(t)
            if fv is not None:
                reads = self.walk_all([x for x in self._keys(t)], ctx)
                fam = self.fams.get(fv.partition(".")[0])
                if fam is not None and (fam.get("fields") and "." not in fv):
                    return None, reads   # a struct value as a whole
                self.family_key(fv)
                return fv, reads | {fv}
            pv = self.param_var(t, ctx.actor)
            if pv is not None:
                reads = self.walk_all([x for x in self._keys(t)], ctx)
                self.key(pv, self.param_type(ctx.actor, pv), "param")
                return pv, reads
            # a member or map of another value (a call result, a carried storage view)
            reads = self.walk_all(a, ctx)
            if h == "member" and isinstance(a[0], list) and a[0] and a[0][0] in ("carried", "exit"):
                return None, reads
            return self.fresh(), reads
        if h == "param":
            pv = f"{ctx.actor}.{t[1]}"
            self.key(pv, self.param_type(ctx.actor, pv), "param")
            return pv, frozenset()
        if h in ("word", "byte"):
            pv = self.param_var(a[0], ctx.actor)
            reads = self.walk_all(a, ctx)
            if pv is not None and isinstance(a[1], int) and not isinstance(a[1], bool):
                var = f"{pv}@{a[1]}"
                self.key(var, "Word", "param_word")
                return var, reads
            return self.fresh(), reads
        if h == "env":
            var = f"env:{t[1]}"
            self.key(var, "Word", "env")
            return var, frozenset()
        if h in ("caller", "this"):
            var = f"env:{h}"
            self.key(var, "Word", "env")
            return var, frozenset()
        if h == "call":
            self.walk_all(a[1:], ctx)          # the arguments flow nowhere (A-env)
            var = f"call:{t[1]}"
            self.key(var, "Word", "call")
            return var, frozenset()
        if h == "iter":
            var = self.loop_var(t, "iter", ctx)
            return var, frozenset()
        if h == "count":
            return self.loop_var(t, "count", ctx), frozenset()
        if h in ("carried", "exit"):
            name = t[2]
            if isinstance(name, list) and len(name) == 2 and name[0] == "storage":
                return None, frozenset()     # a storage view carried through a loop
            if isinstance(name, list):       # ["return", j] and the like
                return self.fresh(), frozenset()
            return self.loop_var(t, loop_label(name), ctx), frozenset()
        if h == "store":
            return None, self.walk_all(a, ctx)
        if h == "struct":
            reads = frozenset()
            for _m, v in t[2]:
                _, r = self.ex(v, ctx)
                reads |= r
            return None, reads
        if h == "blobhash":
            reads = self.walk_all(a, ctx)
            return self.fresh(), reads
        if h in ("keccak256", "sha256", "abi.encode", "abi.encodePacked", "len", "~", "not", "neg", "trunc",
                 "mem", "slice", "mload", "ptr", "at", "immutable", "code", "balance", "blockhash", "sload",
                 "unknown", "str", "phi", "addmod", "mulmod", "input", "value", "tuple", "cdoff", "calldata") \
                or h in OPAQUE_BIN or h in ("mstore", "mstore8", "mloop", "when", "calldatacopy", "loop"):
            reads = self.walk_all([x for x in a if not isinstance(x, str)], ctx)
            if h in ("str", "mem", "mstore", "mstore8", "mloop", "when", "calldatacopy", "loop", "value", "tuple",
                     "input"):
                return None, reads
            return self.fresh(), reads
        raise ExtractedError(f"{ctx.actor} ({ctx.where}): term {h!r} has no sorts rule")

    @staticmethod
    def _keys(t) -> list:
        """The key and index subterms of a storage or parameter access path."""
        out = []
        while isinstance(t, list) and t and t[0] in ("map", "index", "member"):
            if t[0] in ("map", "index"):
                out.append(t[2])
            t = t[1]
        return out

    def loop_var(self, t, name: str, ctx: Ctx) -> str:
        span = t[1]
        rest = t[3:] if t[0] in ("carried", "exit") else t[2:]
        r = rest[0] if rest and isinstance(rest[0], int) and not isinstance(rest[0], bool) else 0
        var = f"loop:{span}{'#' + str(r) if r else ''}:{name}"
        self.key(var, "Word", "loop")
        return var

    def param_type(self, action: str, var: str) -> str:
        ps = self.w.params.get(action) or {}
        parts = var[len(action) + 1:].split(".")
        p = ps.get(parts[0])
        for m in parts[1:]:
            if p is None:
                break
            p = next((f for f in p.get("fields") or [] if f.get("name") == m), None)
        if p is None:
            return "Word"
        ty = p.get("type") or ""
        if is_bool_type(ty):
            return "Bool"
        if ty in ("bytes", "string"):
            return "Bytes"
        return "Word"

    # ---------------------------------------------------------- records
    def path_var(self, family: str, path: list) -> str | None:
        fam = self.fams.get(family)
        var = family
        for acc in path or []:
            if acc[0] == "member":
                var = f"{family}.{acc[1]}"
        if fam is not None and fam.get("fields") and "." not in var:
            return None
        return var

    def write(self, a: dict, r: Record, ctx: Ctx) -> None:
        rec = r.rec
        fam = rec.get("family")
        if not isinstance(fam, str):
            raise ExtractedError(f"{a['name']} ({ctx.where}): a write without a family")
        path = rec.get("path") or []
        reads = self.walk_all([x[1] for x in path if isinstance(x, list) and len(x) > 1 and x[0] != "member"], ctx)
        _, rc = self.ex(rec.get("cond", 1), ctx)
        val = rec.get("value")
        var = self.path_var(fam, path)
        if isinstance(val, list) and val and val[0] == "struct":
            for m, x in val[2]:
                v, rv = self.ex(x, ctx)
                reg = f"{fam}.{m}"
                self.family_key(reg)
                self.p.writers.setdefault(reg, set()).add(a["name"])
                self.p.reads.append((a["name"], reg, rv | reads))
                self.flow(v, reg, ctx)
                self.ev("write", a["name"], reg, v, ctx)
            return
        v, rv = self.ex(val, ctx)
        if var is None:      # a whole struct written with a non-literal (a delete: 0)
            fdef = self.fams.get(fam) or {}
            for f in fdef.get("fields") or []:
                reg = f"{fam}.{f['name']}"
                self.family_key(reg)
                self.p.writers.setdefault(reg, set()).add(a["name"])
            return
        self.family_key(var)
        self.p.writers.setdefault(var, set()).add(a["name"])
        self.p.reads.append((a["name"], var, rv | reads | rc))
        self.flow(v, var, ctx)
        self.ev("write", a["name"], var, v, ctx)

    def loop(self, a: dict, r: Record, ctx: Ctx) -> None:
        rec = r.rec
        for k in RECORD_TERMS["loops"]:
            if k in rec:
                self.ex(rec[k], ctx)
        span, reach = self.loop_ids[r.seq]
        sym = [span] + ([reach] if reach else [])
        for sec, fld in (("carried", "entry"), ("carried", "value"), ("next", "value"), ("at_break", "value"),
                         ("exit", "value")):
            for x in rec.get(sec) or []:
                if not isinstance(x, dict):
                    continue
                name = x.get("name")
                v, _ = self.ex(x.get(fld), ctx)
                if isinstance(name, list):
                    continue          # a storage view (its writes are the loop's write records)
                var = self.loop_var(["carried", *sym[:1], name, *sym[1:]], loop_label(name), ctx)
                self.flow(v, var, ctx)
        for x in rec.get("returns") or []:
            self.ex(x.get("cond"), ctx)
            self.ex(x.get("value"), ctx)
        for x in rec.get("regions") or []:
            if x.get("writes") is not None:
                self.ex(x["writes"], ctx)

    def run(self) -> Walk:
        doc = self.doc
        for name, fam in sorted(self.fams.items()):
            if fam.get("kind") in ("scalar", "mapping", "array") and not fam.get("fields"):
                if fam.get("kind") == "array" and str(name).endswith("__gap"):
                    continue
                self.family_key(name)
            for f in fam.get("fields") or []:
                self.family_key(f"{name}.{f['name']}")
        for a in sorted(doc.get("actions") or [], key=lambda x: x["name"]):
            self.w.params[a["name"]] = {p["name"]: p for p in a.get("params") or []}
            for p in a.get("params") or []:
                base = f"{a['name']}.{p['name']}"
                if p.get("fields"):
                    for f in p["fields"]:
                        self.key(f"{base}.{f['name']}", self.param_type(a["name"], f"{base}.{f['name']}"), "param")
                else:
                    self.key(base, self.param_type(a["name"], base), "param")
        for a in sorted(doc.get("actions") or [], key=lambda x: x["name"]):
            self.loop_ids = loop_spans(a)
            for r in action_records(a):
                where = f"{r.section}[{r.index}]"
                mode = {"guards": "guard", "checks": "check", "panics": "panic", "calls": "call", "writes": "write",
                        "events": "event", "loops": "loop", "mstores": "mstore"}[r.section]
                ctx = Ctx("action", a["name"], where, r.src, r.src, mode, r.seq)
                if r.section == "writes":
                    self.write(a, r, ctx)
                elif r.section == "loops":
                    self.loop(a, r, ctx)
                elif r.section == "mstores":
                    for k in ("offset", "value", "cond"):
                        if k in r.rec:
                            self.ex(r.rec[k], ctx)
                else:
                    for _k, t in record_terms(r):
                        self.ex(t, ctx)
                for _k, t in record_terms(r):
                    self._holders(a["name"], t, r)
        # lexical seeds: storage families by name
        for s in self.lexical:
            for var in sorted(self.p.keys):
                if self.p.keys[var]["binder"] != "family":
                    continue
                if re.search(s["pattern"], var.partition(".")[0]):
                    self.ground(var, f"lexical:{s['id']}", G.canonical(s["sort"]))
        return self.w

    def _holders(self, action: str, t, r: Record) -> None:
        """Index every subtraction node by the records that hold it (site spans and occurrences)."""
        if isinstance(t, list):
            if t and t[0] == "-" and len(t) == 3:
                k = (action, ckey(t))
                lst = self.w.holders.setdefault(k, [])
                item = (r.seq, f"{r.section}[{r.index}]", r.src)
                if item not in lst:
                    lst.append(item)
            for x in t:
                self._holders(action, x, r)


# ------------------------------------------------------------------------------------------------ constraints
def build(model: str, walk: Walk) -> list[dict]:
    prog = walk.prog
    cs: list[dict] = []

    def add(kind: str, vars_: list, src, txt: str, **extra) -> None:
        c = {"model": model, "kind": kind, "vars": list(vars_), "src": src, "text": txt}
        c.update(extra)
        cs.append(c)

    for key in sorted(prog.keys):
        if prog.keys[key]["type"] == "Bool":
            add("type", [key], None, f"{key} : Bool (ABI type)", sort="Bool")
    for var in sorted(walk.grounds, key=lambda v: (v.startswith("$"), int(v[1:]) if v.startswith("$") else 0, v)):
        gs = sorted(set(walk.grounds[var]))
        sort = G.render(G.union([G.parse(s) for _, s in gs]))
        add("seed", [var], None, f"{var} : {sort} ({', '.join(g for g, _ in gs)})",
            sort=sort, grounds=sorted({g for g, _ in gs}))
    for e in prog.events:
        kind = e[0]
        if kind == "flow":
            _, a, b, ctx = e
            add("flow", [a, b], ctx.src, f"{ctx.actor}: {a} flows into {b}")
        elif kind == "affine":
            _, op, lhs, rhs, out, node, ctx = e
            add("affine", [lhs, rhs, out], ctx.src, f"{ctx.actor}: {text(node)} ({lhs} {op} {rhs} = {out})", op=op)
        elif kind == "compare":
            _, op, x, y, node, ctx, _via = e
            add("compare", [x, y], ctx.src, f"{ctx.actor}: {text(node)} ({x} {op} {y})", op=op)
    for reg in sorted(prog.registers):
        ws = sorted(prog.writers.get(reg, ()))
        if ws:
            add("writer", [reg], None, f"{reg} is written by {', '.join(ws)}", writers=ws)
    return cs


_INFIX = {"+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||", "<<", ">>", "&", "|", "^"}


def text(t) -> str:
    """Readable text of a 0.3 term (constraint texts only)."""
    if isinstance(t, bool):
        return "true" if t else "false"
    if isinstance(t, int):
        return str(t) if t < (1 << 32) else hex(t)
    if not isinstance(t, list) or not t or not isinstance(t[0], str):
        return json.dumps(t)
    h, a = t[0], t[1:]
    if h == "param":
        return str(a[0])
    if h == "storage":
        return str(a[0])
    if h == "env":
        return str(a[0])
    if h in ("caller", "this"):
        return h
    if h == "member":
        return f"{text(a[0])}.{a[1]}"
    if h == "map":
        return f"{text(a[0])}[{text(a[1])}]"
    if h in _INFIX and len(a) == 2:
        return f"({text(a[0])} {h} {text(a[1])})"
    if h == "!":
        return "!" + text(a[0])
    if h == "?":
        return f"({text(a[0])} ? {text(a[1])} : {text(a[2])})"
    return h + "(" + ", ".join(text(x) if not isinstance(x, str) else x for x in a) + ")"


# ------------------------------------------------------------------------------------------------ sites (E4)
def realization_checks(doc: dict) -> dict:
    """(action, ckey(node)) -> the panic record of an action whose op is "-" and whose args are [a, b] (the site's
    realization check)."""
    out = {}
    for a in doc.get("actions") or []:
        for p in sorted(a.get("panics") or [], key=lambda x: x.get("seq", 0)):
            if p.get("op") == "-" and isinstance(p.get("args"), list) and len(p["args"]) == 2:
                node = ["-", p["args"][0], p["args"][1]]
                out.setdefault((a["name"], ckey(node)), p)
    return out


def build_sites(model: str, doc: dict, walk: Walk, system, active_ids: set, affine_ids: dict) -> list[dict]:
    real = realization_checks(doc)
    groups: dict = {}
    for node, lhs, rhs, out, ctx in walk.subs:
        k = ckey(node)
        p = real.get((ctx.actor, k))
        if p is not None:
            sp, checked = p.get("src"), True
        else:
            holders = sorted(walk.holders.get((ctx.actor, k)) or [(ctx.seq, ctx.where, ctx.src)])
            sp, checked = holders[0][2], False
        g = groups.setdefault((sp, k), {"node": node, "occ": set(), "sorts": [], "checked": False})
        g["checked"] = g["checked"] or checked
        for _seq, where, _src in walk.holders.get((ctx.actor, k)) or [(ctx.seq, ctx.where, ctx.src)]:
            g["occ"].add((ctx.actor, where))
        cid = affine_ids.get(out)
        if cid is None or cid not in active_ids:
            g["sorts"].append(None)
        else:
            g["sorts"].append(system.difference_sorts(model, lhs, rhs))
    sites = []
    for (sp, k), g in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        ss = g["sorts"]
        if all(s is not None and len(s) == 1 for s in ss) and len({next(iter(s)) for s in ss}) == 1:
            sort = next(iter(ss[0]))
        else:
            sort = G.UNREFINED
        occ = sorted(g["occ"])
        sites.append({
            "id": f"{model}:{sp}:{hashlib.sha256(k.encode('utf-8')).hexdigest()[:8]}",
            "model": model, "span": sp, "op": "-", "expr": g["node"], "sort": G.render(sort),
            "realized_in": "Mach(256)", "obligation": "sign" if G.is_signed(sort) else None,
            "checked": g["checked"], "entry_points": sorted({a for a, _ in occ}),
            "occurrences": [{"action": a, "where": w} for a, w in occ]})
    ids = [s["id"] for s in sites]
    if len(ids) != len(set(ids)):
        raise ExtractedError(f"{model}: two sites share an id")
    return sites


# ------------------------------------------------------------------------------------------------ coherence (E5)
def disjuncts(t) -> list:
    if isinstance(t, list) and t and t[0] == "||":
        out = []
        for x in t[1:]:
            out += disjuncts(x)
        return out
    return [t]


def reads_param(t) -> list:
    out = []

    def walk(x):
        if isinstance(x, list):
            if len(x) == 2 and x[0] == "param" and isinstance(x[1], str):
                out.append(x[1])
            for y in x:
                walk(y)
    walk(t)
    return sorted(set(out))


def calls_in(t) -> list:
    out = []

    def walk(x):
        if isinstance(x, list):
            if x and x[0] == "call" and len(x) >= 2 and isinstance(x[1], str):
                out.append(x[1])
            for y in x:
                walk(y)
    walk(t)
    return sorted(set(out))


def storage_reads(t) -> list:
    """The family variables a term reads (E2 names), with how: "key" when the read is a mapping key or array index
    of another access, "compare" otherwise."""
    out = {}

    def fam_var(x):
        if not isinstance(x, list) or not x:
            return None
        if x[0] == "storage" and isinstance(x[1], str):
            return x[1]
        if x[0] in ("map", "index"):
            return fam_var(x[1])
        if x[0] == "member" and len(x) >= 3:
            b = fam_var(x[1])
            return f"{b}.{x[2]}" if b else None
        return None

    def walk(x, as_key):
        if not isinstance(x, list) or not x or not isinstance(x[0], str):
            if isinstance(x, list):
                for y in x:
                    walk(y, as_key)
            return
        if x[0] in ("map", "index") and len(x) == 3:
            walk(x[1], False)
            walk(x[2], True)
            v = fam_var(x)
            if v is not None:
                out.setdefault(v, set()).add("compare" if not as_key else "key")
            return
        if x[0] == "member" and len(x) >= 3:
            v = fam_var(x)
            if v is not None:
                out.setdefault(v, set()).add("key" if as_key else "compare")
                walk(x[1], False)
                return
        if x[0] == "storage" and isinstance(x[1], str):
            out.setdefault(x[1], set()).add("key" if as_key else "compare")
            return
        for y in x[1:]:
            walk(y, as_key)
    walk(t, False)
    return sorted((k, sorted(v)) for k, v in out.items())


def coherence_guards(doc: dict) -> list[dict]:
    """Every guard of the form ["||", .., ["!", kappa], ..] whose rho (the other disjuncts) reads a parameter of its
    action: {"action", "guard": "guards[i]", "src", "kappa", "rho", "params", "calls"} (one per (action, guard); its
    first reach that has the form)."""
    out = []
    for a in sorted(doc.get("actions") or [], key=lambda x: x["name"]):
        own = {p["name"] for p in a.get("params") or []}
        for i, g in enumerate(a.get("guards") or []):
            for x in g.get("reaches") or []:
                ds = disjuncts(x.get("expr"))
                if len(ds) < 2:
                    continue
                found = None
                for j, d in enumerate(ds):
                    if isinstance(d, list) and len(d) == 2 and d[0] == "!":
                        rho = ds[:j] + ds[j + 1:]
                        ps = [p for p in reads_param(rho) if p in own]
                        if ps:
                            found = (d[1], rho[0] if len(rho) == 1 else ["||", *rho], ps)
                            break
                if found is not None:
                    kappa, rho, ps = found
                    out.append({"action": a["name"], "guard": f"guards[{i}]", "src": g.get("src"), "kappa": kappa,
                                "rho": rho, "params": ps, "calls": calls_in(kappa)})
                    break
    return out


def external_guards(doc: dict) -> list[dict]:
    """The guards of the coherence form whose kappa reads an external call's result (E5; types.json)."""
    out = []
    for g in coherence_guards(doc):
        if g["calls"]:
            out.append({"action": g["action"], "guard": g["guard"], "src": g["src"], "calls": g["calls"]})
    return sorted(out, key=lambda x: (x["action"], int(x["guard"][len("guards["):-1])))


def obstructions(model: str, doc: dict, assignment: dict) -> list[dict]:
    """I15's R11 over 0.3 (E5): one obstruction per (action, guard) of the coherence form whose kappa reads a storage
    family whose provenance (a writer label) does not list the action among its writers; a guard whose kappa reads an
    external call is an external guard instead (it cannot be checked in the document)."""
    m = (assignment.get("models") or {}).get(model) or {}
    prov = m.get("provenance") or {}
    sorts = m.get("assignment") or {}
    out = []
    for g in coherence_guards(doc):
        if g["calls"]:
            continue
        regs = []
        for var, _how in storage_reads(g["kappa"]):
            p = prov.get(var)
            if p is None or g["action"] in (p.get("writers") or []):
                continue
            regs.append({"var": var, "sort": sorts.get(var), "label": p.get("label"), "writers": p.get("writers")})
        if not regs:
            continue
        gi = g["guard"]
        out.append({"id": f"coherence:{model}:{g['action']}:{gi}:{gi}", "kind": "coherence", "model": model,
                    "action": g["action"], "guard": gi, "guard_span": g["src"], "kappa": g["kappa"], "rho": g["rho"],
                    "registers": sorted(regs, key=lambda r: r["var"]), "constrains": g["params"]})
    return sorted(out, key=lambda o: o["id"])


def walk(model: str, doc: dict, seeds: dict) -> Walk:
    return Walker(model, doc, seeds).run()
