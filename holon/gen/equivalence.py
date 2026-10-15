"""Equivalence obligations for a binding change (F31; I10's binding_change, whitepaper §9.4, L22).

A law is bound to the kernel form (BendTT) of every definition its emitted statement reaches (holon.bindings). When
a model generator is rewritten, those kernel forms change although the statement does not. This module decides, with
kernel-checked proofs and never by inspection, whether such a change leaves the statement's meaning unchanged.

THE CRITERION. The roots of a statement are the model definitions its emitted text names (`M.<name>`, constructors
mapped to their datatype: holon.bindings.kernel_cone's roots). The meaning is unchanged when every root is
extensionally the same old and new:

  * a function root f:   for all inputs x of its parameter types, {Old.f(x) == New.f(x)} (propositional equality,
                         proved in the kernel; the parameter and result types are the same datatypes in both);
  * a datatype root T:   its kernel form and the kernel form of every definition it reaches are unchanged (the same
                         type), or, for an inductive family whose constructors' fields mention changed functions,
                         Old.T<i> and New.T<i> are inter-derivable for every index i (two transport laws, by
                         induction over the family);
  * a root whose cone is unchanged needs nothing (its kernel forms are byte-identical).

Why it is sound: the emitted statement is a term built from its roots and from Base (and law-local definitions the
binding pins by its statement_sha256). Replacing each root by one that agrees on every input (or, for a type used
as a premise or binder, by an inter-derivable one) changes neither the proposition nor any of its instances: every
proof, witness or counter-law of the old statement transports to the new one and back. Internal helpers (the
definitions the roots reach) may then differ freely: only the roots' input-output behaviour reaches the statement.
A weaker criterion (equality only on "realistic" inputs, on reachable states, on byte-valued limbs, by testing, or by
a supplied proof) is not used: the statement quantifies over every value of its binder types, so a root that differs
on any value of its type changes some instance of the statement.

HOW BOTH MODELS ARE CHECKED TOGETHER. Bend types are nominal per module (a probe: Old.KW and New.KW are different
types even when declared identically), so a law cannot compare Old.f(x) with New.f(x) across two imports. The
generator therefore writes ONE pair module: the new model verbatim, then every old definition and datatype whose
kernel form differs from the new one, or that reaches one that does (the "dirty" set), renamed with the prefix o__
(constructors of a renamed datatype too); the old definitions that are clean are shared with the new side, because
their kernel forms are byte-identical. The pair module is then tied to the two models by the kernel itself
(linkage): its BendTT translation, with the o__ prefix removed, must give exactly the old model's kernel entry for
every definition of the old cone, and exactly the new model's entry for every definition of the new cone. The
caller compares those entries with the bindings (spec/bindings/<m>.json at the bound commit, and holon.bindings.derive
now), so a proof about the pair module is a proof about the two bound models and nothing else.

Files (in a temporary directory, never committed): pair.bend, LAWS.bend (one law per changed root, nothing else),
PROOF.bend (imports LAWS.bend as Laws; lemmas as typed defs; no law). An obligation counts only when bend accepts
PROOF.bend, BendTT (--verdict) accepts it too, LAWS.bend states exactly the expected laws, and no file has an escape
hatch (holon.bend.escape_hatches).

PROOF CLASSES (untrusted, one per class of transformation; the kernel decides):
  unchanged     the root's cone is byte-identical in kernel form: nothing to prove.
  normalize     finite case analysis: every parameter of a finite type (Bool, enumerations, records of finite
                fields, recursively) is opened, then {==} (fixed-limb operations over bits).
  congruence    the new definition's match tree, mirrored; in each leaf every call of a changed definition already
                proven equal is rewritten (%lemma : motive) until both sides are the same term up to computation,
                then {==}. The driver tree may also be the old definition's (the old leaf rewritten towards the new
                names through Equal.sym).
  induction     congruence where the rewritten call is the definition's own recursive call (the induction
                hypothesis): list and Nat recursions that differ only in binder quantity or argument order.
  family        an inductive family root whose constructors mention changed functions: transport each way by
                induction over the family, rewriting each constructor's equality fields with the function lemmas.
  counter       a refutation: a concrete input (found by evaluating both sides of the compiled pair module on
                generated values of the parameter types, fixed seed) where the two sides differ, stated as a
                counter-law {o__f(W) != f(W)} and accepted by bend and BendTT. A refuted root is a real semantic
                difference; the entry is rejected with the witness.

Every changed definition the roots reach is attempted bottom-up: a definition is attempted only when every changed
definition it calls is proven; one that no class proves blocks the definitions that call it, and the report names
the first blocking definitions and the kernel's message for each class tried.

API:
  prove(old_text, new_text, statement_text, cfg=None, workdir=None) -> dict
      {status: PROVED | REFUTED | UNKNOWN | UNSUPPORTED, roots: [{root, kind, class, status, reason, ...}],
       lemmas: {def: {class, status, reason}}, laws, proof, pair_sha256, kernels, linkage, seconds, reason}
  pair_module(old_text, new_text, roots) -> PairModule (text, renamed set, old/new entries)
Target-agnostic: no law ids, no target or definition names; everything is read from the two model texts.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

PREFIX = "o__"
ALIAS = "P"
BASE_CTORS = {"Con": ("List", ["head", "tail"]), "Nil": ("List", []), "True": ("Bool", []), "False": ("Bool", []),
              "Some": ("Maybe", ["value"]), "None": ("Maybe", []), "Unit": ("Unit", []),
              "WCon": ("Word", ["head", "tail"]), "WNil": ("Word", []), "LT": ("Cmp", []), "EQ": ("Cmp", []),
              "GT": ("Cmp", [])}
_IDENT = re.compile(r"(?<![\w.$])([A-Za-z_][A-Za-z0-9_]*)(?![\w])")
_LOCAL = re.compile(r"^x[0-9]+$")
MAX_ROUNDS = 400
ARROW = "\x00\x01"   # "->" while brackets are counted (same length)


class Unsupported(Exception):
    pass


# ---------------------------------------------------------------- source items
@dataclass
class Item:
    kind: str                     # "def" | "type"
    name: str
    text: str                     # the item's source lines (comments above it excluded), ending with "\n"
    params: list = field(default_factory=list)   # [(q, name, type)]  q in "", "+", "-"
    ret: str = ""                 # a def's result type; a type's kind ("Data", "Type")
    ctors: list = field(default_factory=list)    # a type's [(ctor, [(field, type)])]
    body: list = field(default_factory=list)     # a def's body lines


def split_top(s: str, sep: str = ",") -> list[str]:
    """s split on sep at bracket depth 0 (<>, (), {}, [])."""
    out, depth, cur = [], 0, ""
    s = s.replace("->", ARROW)
    for ch in s:
        if ch in "<({[":
            depth += 1
        elif ch in ">)}]":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip() or out:
        out.append(cur)
    return [x.replace(ARROW, "->").strip() for x in out if x.strip()]


def _param(p: str) -> tuple[str, str, str]:
    q = p[0] if p[:1] in "+-" else ""
    name, _, ty = p[len(q):].partition(":")
    return q, name.strip(), ty.strip()


def _close(s: str, i: int) -> int:
    """Index after the bracket that closes the one opening at s[i]."""
    depth = 0
    s = s.replace("->", ARROW)
    for j in range(i, len(s)):
        if s[j] in "<({[":
            depth += 1
        elif s[j] in ">)}]":
            depth -= 1
            if depth == 0:
                return j + 1
    raise Unsupported(f"unbalanced brackets in {s[:80]!r}")


def parse_items(text: str) -> tuple[list[str], list[Item]]:
    """(header lines before the first item, items) of a model source. Comment lines are dropped."""
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    header, items, cur = [], [], None
    for ln in lines:
        top = ln[:1] not in (" ", "\t", "") and ln.strip()
        if top and (ln.startswith("def ") or ln.startswith("type ")):
            cur = [ln]
            items.append(cur)
        elif top:
            if items:
                raise Unsupported(f"unexpected top-level line {ln[:80]!r}")
            header.append(ln)
        elif cur is not None:
            cur.append(ln)
        elif ln.strip():
            header.append(ln)
    return header, [_item(blk) for blk in items]


def _item(blk: list[str]) -> Item:
    while blk and not blk[-1].strip():
        blk.pop()
    text = "\n".join(blk) + "\n"
    head = blk[0]
    if head.startswith("type "):
        m = re.match(r"type ([A-Za-z_][\w.]*)(<.*>)? is (\w+):$", head)
        if not m:
            raise Unsupported(f"unrecognised type header {head[:80]!r}")
        params = [_param(p) for p in split_top(m.group(2)[1:-1])] if m.group(2) else []
        ctors = []
        for ln in blk[1:]:
            s = ln.strip()
            if not s:
                continue
            cm = re.match(r"([A-Za-z_][\w]*)\{(.*)\}$", s)
            if not cm:
                raise Unsupported(f"unrecognised constructor line {s[:80]!r}")
            ctors.append((cm.group(1), [tuple(x.strip() for x in f.split(":", 1)) for f in split_top(cm.group(2))]))
        return Item("type", m.group(1), text, params, m.group(3), ctors)
    # def: the header may span lines until it ends with ':' at depth 0
    i, hdr = 0, head
    while not _header_done(hdr):
        i += 1
        hdr += " " + blk[i].strip()
    m = re.match(r"def ([A-Za-z_][\w.]*)\((.*)\)\s*->\s*(.*):$", hdr)
    if not m:
        raise Unsupported(f"unrecognised def header {hdr[:80]!r}")
    params = [_param(p) for p in split_top(m.group(2))]
    return Item("def", m.group(1), text, params, m.group(3).strip(), [], blk[i + 1:])


def _header_done(h: str) -> bool:
    depth = 0
    for ch in h.replace("->", ARROW):
        depth += ch in "<({["
        depth -= ch in ">)}]"
    return depth == 0 and h.rstrip().endswith(":")


def rename(text: str, mapping: dict) -> str:
    return _IDENT.sub(lambda m: mapping.get(m.group(1), m.group(1)), text)


# ---------------------------------------------------------------- kernel forms
def kernel_entries_of(text: str, cfg: dict | None = None, shown: str = "model") -> dict[str, str]:
    from .. import bindings as B
    tmp = Path(tempfile.mkdtemp(prefix="holon-eqv-tt-"))
    try:
        f = tmp / "m.bend"
        f.write_text(text)
        return B.parse_entries(B.bendtt_text(f, cfg, shown), shown)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def closure(graph: dict, roots) -> set:
    seen, todo = set(), sorted(roots)
    while todo:
        d = todo.pop()
        if d not in seen and d in graph:
            seen.add(d)
            todo.extend(x for x in graph[d] if x not in seen)
    return seen


def roots_of(statement_text: str, entries: dict) -> list[str]:
    from .. import bindings as B
    own = B.tag_owner(entries)
    out = set()
    for tok in B._QUAL.findall(re.sub(r"#[^\n]*", "", statement_text)):
        r = B._resolve_root(tok, entries, own)
        if r is None:
            raise Unsupported(f"M.{tok} in the statement resolves to no kernel entry")
        out.add(r)
    if not out:
        raise Unsupported("the statement names no model definition")
    return sorted(out)


def _source_name(entry: str, items: dict) -> str | None:
    """The source item a kernel entry comes from (a datatype's generated entries, like T.arms, belong to T)."""
    if entry in items:
        return entry
    head = entry.split(".")[0]
    return head if head in items and items[head].kind == "type" else None


@dataclass
class PairModule:
    text: str
    renamed: list            # old source items copied with the o__ prefix (sorted)
    roots: list
    eo: dict                 # old model kernel entries
    en: dict                 # new model kernel entries
    cone_old: set
    cone_new: set
    old_items: dict
    new_items: dict
    dirty_entries: set       # old-cone kernel entries whose behaviour may differ (renamed side)


def dirty_set(eo: dict, en: dict, cone_old: set, old_items: dict) -> set:
    """Old-cone kernel entries of the old source whose kernel form differs from the new model's, is missing there, or
    that reach such an entry (Base entries are shared: the same checker's Base on both sides)."""
    from .. import bindings as B
    g = B.kernel_graph(eo)
    bad = {d for d in cone_old if _source_name(d, old_items) and (d not in en or eo[d] != en[d])}
    rev: dict = {}
    for a in cone_old:
        for b in g.get(a, []):
            rev.setdefault(b, set()).add(a)
    out, todo = set(), sorted(bad)
    while todo:
        x = todo.pop()
        if x not in out:
            out.add(x)
            todo.extend(sorted(rev.get(x, ())))
    return {d for d in out if _source_name(d, old_items)}


def pair_module(old_text: str, new_text: str, statement_text: str, cfg: dict | None = None,
                eo: dict | None = None, en: dict | None = None) -> PairModule:
    from .. import bindings as B
    eo = eo if eo is not None else kernel_entries_of(old_text, cfg, "old model")
    en = en if en is not None else kernel_entries_of(new_text, cfg, "new model")
    for side, es in (("old", eo), ("new", en)):
        clash = sorted(n for n in es if n.startswith(PREFIX) or _LOCAL.match(n))
        if clash:
            raise Unsupported(f"the {side} model names definitions {clash[:5]} like the pair module's renamed side or a "
                              "kernel local")
    roots = roots_of(statement_text, en)
    missing = [r for r in roots if r not in eo]
    if missing:
        raise Unsupported(f"the statement's roots {missing} do not exist in the old model")
    cone_old = closure(B.kernel_graph(eo), roots)
    cone_new = closure(B.kernel_graph(en), roots)
    oh, oi = parse_items(old_text)
    nh, ni = parse_items(new_text)
    old_items, new_items = {i.name: i for i in oi}, {i.name: i for i in ni}
    if len(old_items) != len(oi) or len(new_items) != len(ni):
        raise Unsupported("a model declares a name twice")
    dirty = dirty_set(eo, en, cone_old, old_items)
    names = sorted({_source_name(d, old_items) for d in dirty})
    mapping = {n: PREFIX + n for n in names}
    for n in names:
        for c, _ in old_items[n].ctors:
            mapping[c] = PREFIX + c
    order = [i.name for i in oi if i.name in mapping]
    parts = [new_text.rstrip("\n"), "", "# ---- the old side (holon.gen.equivalence): every old definition whose kernel form "
             "differs from the new one or reaches one that does, renamed " + PREFIX + "<name>"]
    for n in order:
        parts.append("")
        parts.append(rename(old_items[n].text, mapping).rstrip("\n"))
    text = "\n".join(parts) + "\n"
    return PairModule(text, order, roots, eo, en, cone_old, cone_new, old_items, new_items, dirty)


def strip_prefix(entry_text: str) -> str:
    return re.sub(r"(?<![\w])" + PREFIX, "", entry_text)


def linkage(pm: PairModule, ep: dict) -> list[str]:
    """The pair module's kernel entries, against the two models': the old cone through the o__ names (prefix removed)
    and the new cone as is. [] when every entry is byte-identical."""
    probs = []
    for d in sorted(pm.cone_old):
        name = PREFIX + d if d in pm.dirty_entries else d
        got = ep.get(name)
        if got is None:
            probs.append(f"old {d}: no entry {name} in the pair module")
        elif strip_prefix(got) != pm.eo[d]:
            probs.append(f"old {d}: the pair module's {name} has another kernel form than the old model's")
    for d in sorted(pm.cone_new):
        if ep.get(d) != pm.en.get(d):
            probs.append(f"new {d}: the pair module's entry differs from the new model's")
    return probs


# ---------------------------------------------------------------- expressions
def qualify(text: str, model_names: set, bound: set) -> str:
    """Model names (defs, types, constructors) qualified with the pair module's alias; bound locals left alone."""
    return _IDENT.sub(lambda m: (f"{ALIAS}.{m.group(1)}" if m.group(1) in model_names and m.group(1) not in bound
                                 else m.group(1)), text)


def calls(text: str, names: set) -> list[tuple[int, int, str, int]]:
    """[(start, end, name, args start)] of every call `P.name(..)` with name in names, in text order."""
    out = []
    for m in re.finditer(r"(?<![\w.])" + ALIAS + r"\.([A-Za-z_][A-Za-z0-9_]*)\(", text):
        if m.group(1) in names:
            end = _close(text, m.end() - 1)
            out.append((m.start(), end, m.group(1), m.end()))
    return out


def subst(text: str, sub: dict) -> str:
    """Replace bound variables by their terms (simultaneous, to a fixpoint over nested patterns)."""
    for _ in range(64):
        new = _IDENT.sub(lambda m: sub.get(m.group(1), m.group(1)), text)
        if new == text:
            return new
        text = new
    raise Unsupported("substitution does not terminate")


@dataclass
class Node:
    kind: str                     # "match" | "let" | "expr"
    scrut: list = field(default_factory=list)
    cases: list = field(default_factory=list)  # [([pattern], Node)]
    var: str = ""
    expr: str = ""
    body: "Node | None" = None


def _indent(ln: str) -> int:
    return len(ln) - len(ln.lstrip(" "))


def parse_body(lines: list[str]) -> Node:
    lines = [ln for ln in lines if ln.strip()]
    if not lines:
        raise Unsupported("empty body")
    return _block(lines, 0, len(lines), _indent(lines[0]))


def _block(lines, i, j, ind) -> Node:
    ln = lines[i].strip()
    if ln.startswith("match ") and ln.endswith(":"):
        scrut = ln[len("match "):-1].split()
        cases, k = [], i + 1
        while k < j:
            c = lines[k]
            if _indent(c) != ind + 2 or not c.strip().startswith("case ") or not c.rstrip().endswith(":"):
                raise Unsupported(f"unrecognised case line {c.strip()[:80]!r}")
            pats = split_top(c.strip()[len("case "):-1], " ")
            e = k + 1
            while e < j and _indent(lines[e]) > ind + 2:
                e += 1
            if e == k + 1:
                raise Unsupported("a case without a body")
            cases.append((pats, _block(lines, k + 1, e, _indent(lines[k + 1]))))
            k = e
        if len(cases[0][0]) != len(scrut) if cases else True:
            raise Unsupported(f"match arity: {ln[:80]!r}")
        return Node("match", scrut=scrut, cases=cases)
    m = re.match(r"([+-]?)([a-z_][A-Za-z0-9_]*) = (.*)$", ln)
    if m and i + 1 < j:
        return Node("let", var=m.group(2), expr=m.group(3), body=_block(lines, i + 1, j, ind))
    if i + 1 != j:
        raise Unsupported(f"unrecognised statement {ln[:80]!r}")
    return Node("expr", expr=ln)


# ---------------------------------------------------------------- types and finite values
class Types:
    def __init__(self, items: dict):
        self.items = items
        self.ctor_of = {}
        for it in items.values():
            for c, fs in it.ctors:
                self.ctor_of[c] = (it.name, fs)

    def head(self, ty: str) -> tuple[str, list[str]]:
        ty = ty.strip()
        if ty.startswith("+"):
            ty = ty[1:]
        m = re.match(r"([A-Za-z_][\w.]*)(?:<(.*)>)?$", ty)
        if not m:
            raise Unsupported(f"unrecognised type {ty!r}")
        return m.group(1), split_top(m.group(2)) if m.group(2) else []

    def finite(self, ty: str, seen=()) -> bool:
        name, args = self.head(ty)
        if name == "Bool":
            return True
        it = self.items.get(name)
        if it is None or it.kind != "type" or it.ret != "Data" or it.params or name in seen:
            return False
        return all(self.finite(t, seen + (name,)) for _, fs in it.ctors for _, t in fs)

    def ctors(self, ty: str) -> list[tuple[str, list]]:
        name, args = self.head(ty)
        if name == "Bool":
            return [("True", []), ("False", [])]
        if name == "List":
            el = args[-1] if args else "U32"
            return [("Nil", []), ("Con", [("head", el), ("tail", ty)])]
        it = self.items.get(name)
        if it is None or it.kind != "type" or it.params:
            raise Unsupported(f"no constructors for {ty!r}")
        return [(c, list(fs)) for c, fs in it.ctors]


# ---------------------------------------------------------------- lemma generation
class Gen:
    """Proof text for one pair module. Lemma `q_<f>` proves {P.o__f(x) == P.f(x)} for a changed function f."""

    def __init__(self, pm: PairModule):
        self.pm = pm
        self.T = Types(pm.new_items)
        self.model_names = set(pm.new_items) | {c for it in pm.new_items.values() for c, _ in it.ctors} | \
            {PREFIX + n for n in pm.renamed} | {PREFIX + c for n in pm.renamed for c, _ in pm.old_items[n].ctors}
        self.fresh = 0

    def q(self, text: str, bound: set) -> str:
        return qualify(text, self.model_names, bound)

    def var(self, base: str = "v") -> str:
        self.fresh += 1
        return f"{base}__{self.fresh}"

    def sig(self, f: str) -> tuple[list, str]:
        it_n, it_o = self.pm.new_items[f], self.pm.old_items[f]
        if [(n, t) for _, n, t in it_n.params] != [(n, t) for _, n, t in it_o.params] and \
                [t for _, _, t in it_n.params] != [t for _, _, t in it_o.params]:
            raise Unsupported(f"{f}: the old and new parameter types differ")
        if it_n.ret != it_o.ret:
            raise Unsupported(f"{f}: the old and new result types differ")
        if any(q == "-" for q, _, _ in it_n.params):
            raise Unsupported(f"{f}: erased (type) parameters")
        return it_n.params, it_n.ret

    def header(self, f: str, lemma: str) -> tuple[str, list[str], str]:
        params, ret = self.sig(f)
        names = [n for _, n, _ in params]
        ps = ", ".join(f"+{n}: {self.q(t, set())}" for _, n, t in params)
        goal = f"{{{ALIAS}.{PREFIX}{f}({', '.join(names)}) == {ALIAS}.{f}({', '.join(names)}) : {self.q(ret, set())}}}"
        return f"def {lemma}({ps}) -> {goal}:", names, self.q(ret, set())

    # -- normalize: finite case analysis on every finite parameter
    def normalize(self, f: str, lemma: str, budget: int = 4096) -> str | None:
        hdr, names, ret = self.header(f, lemma)
        params, _ = self.sig(f)
        lines = [hdr]

        def leaves(tys: list) -> int:
            fin = [t for t in tys if self.T.finite(t)]
            if not fin:
                return 1
            n = sum(leaves([ft for _, ft in fs] + fin[1:]) for _, fs in self.T.ctors(fin[0]))
            if n > budget:
                raise Unsupported(f"{f}: more than {budget} cases")
            return n

        def split(vars_types: list, ind: int) -> list[str]:
            fin = [(v, t) for v, t in vars_types if self.T.finite(t)]
            if not fin:
                return [" " * ind + "{==}"]
            (v, t), rest = fin[0], [x for x in vars_types if x[0] != fin[0][0]]
            cs = self.T.ctors(t)
            out = [" " * ind + f"match {v}:"]
            for c, fs in cs:
                fv = [(self.var(fld), ft) for fld, ft in fs]
                pat = f"{self.q(c, set())}{{{', '.join('+' + x for x, _ in fv)}}}"
                out.append(" " * (ind + 2) + f"case {pat}:")
                out += split(fv + rest, ind + 4)
            return out
        if not any(self.T.finite(t) for _, _, t in params):
            return None
        leaves([t for _, _, t in params])
        lines += split([(n, t) for _, n, t in params], 2)
        return "\n".join(lines) + "\n"

    # -- congruence / induction over a driver's match tree
    def congruence(self, f: str, lemma: str, lemmas: dict, driver: str = "new", expand: bool = False,
                   core: bool = False) -> tuple[str, bool] | None:
        """(proof text, uses its own induction hypothesis) or None. lemmas: {g: lemma def name} for every changed
        function proven equal (f itself included, for the induction hypothesis). expand: a wildcard of a multi-value
        match is split into its type's constructors too (the other side may match on it), or None when the driver
        tree has no such wildcard."""
        hdr, names, ret = self.header(f, lemma)
        params, _ = self.sig(f)
        it = self.pm.new_items[f] if driver == "new" else self.pm.old_items[f]
        body = parse_body(it.body)
        self._side = (lambda e: e) if driver == "new" else (lambda e: rename(e, {n: PREFIX + n for n in self.pm.renamed}))
        lines = [hdr]
        used_ih = [False]
        targets = set(lemmas)

        def leaf(expr: str, sub: dict, bound: set, ind: int) -> list[str]:
            args = ", ".join(subst(n, sub) for n in names)
            cur = subst(self.q(self._side(expr), bound), sub)
            fixed = f"{ALIAS}.{PREFIX}{f}({args})" if driver == "new" else f"{ALIAS}.{f}({args})"
            out = []
            for _ in range(10000):
                cs = calls(cur, targets if driver == "new" else {PREFIX + g for g in targets})
                # innermost first: a call whose arguments hold no other target call
                inner = [c for c in cs if not any(o is not c and c[0] < o[0] and o[1] <= c[1] for o in cs)]
                if not inner:
                    break
                s, e, name, a0 = inner[0]
                g = name if driver == "new" else name[len(PREFIX):]
                gargs = cur[a0:e - 1]
                if g == f:
                    used_ih[0] = True
                # every occurrence of this same call is rewritten at once (F32: one step per distinct instance)
                call_txt = cur[s:e]
                motive_side = _replace_calls(cur, call_txt, "_")
                if driver == "new":
                    motive = f"{{{fixed} == {motive_side} : {ret}}}"
                    out.append(" " * ind + f"%{lemmas[g]}({gargs}) : {motive}")
                    cur = _replace_calls(cur, call_txt, f"{ALIAS}.{PREFIX}{g}({gargs})")
                else:
                    gret = self.q(self.pm.new_items[g].ret, set())
                    motive = f"{{{motive_side} == {fixed} : {ret}}}"
                    out.append(" " * ind + f"%Equal.sym({gret}, {ALIAS}.{PREFIX}{g}({gargs}), {ALIAS}.{g}({gargs}), "
                                           f"{lemmas[g]}({gargs})) : {motive}")
                    cur = _replace_calls(cur, call_txt, f"{ALIAS}.{g}({gargs})")
            else:
                raise Unsupported("too many rewrites")
            if core and driver == "new":   # Base identities, new form -> old form (each a lemma of CORE)
                for _ in range(10000):
                    hit = None
                    for name, lem, old_form in CORE_RULES:
                        for m in re.finditer(r"(?<![\w.])" + re.escape(name) + r"\(", cur):
                            e = _close(cur, m.end() - 1)
                            inner_args = cur[m.end():e - 1]
                            if not any(re.search(r"(?<![\w.])" + re.escape(n) + r"\(", inner_args) for n, _, _ in CORE_RULES):
                                hit = (m.start(), e, lem, old_form, inner_args)
                                break
                        if hit:
                            break
                    if hit is None:
                        break
                    s, e, lem, old_form, a = hit
                    out.append(" " * ind + f"%{lem}({a}) : {{{fixed} == {cur[:s]}_{cur[e:]} : {ret}}}")
                    cur = cur[:s] + old_form.format(a) + cur[e:]
            out.append(" " * ind + "{==}")
            return out

        expanded = [False]

        def walk(n: Node, sub: dict, bound: set, ind: int, tys: dict) -> list[str]:
            if n.kind == "expr":
                return leaf(n.expr, sub, bound, ind)
            if n.kind == "let":
                e = subst(self.q(self._side(n.expr), bound), sub)
                return walk(n.body, {**sub, n.var: f"({e})"}, bound | {n.var}, ind, tys)
            out = [" " * ind + f"match {' '.join(n.scrut)}:"]
            cases = n.cases
            if expand:
                cases = []
                for pats, child in n.cases:
                    alts = [[p] if p != "_" or len(n.scrut) == 1 else self._ctor_patterns(tys.get(v)) or [p]
                            for v, p in zip(n.scrut, pats)]
                    expanded[0] |= any(len(a) > 1 for a in alts)
                    for combo in _product(alts):
                        cases.append((combo, child))
            for pats, child in cases:
                nsub, nbound, ps, ntys = dict(sub), set(bound), [], dict(tys)
                for v, p in zip(n.scrut, pats):
                    if p == "_":
                        ps.append("_")
                        continue
                    pt, fvs = self._pattern(p)
                    nbound |= set(fvs)
                    ntys.update(self._field_tys(tys.get(v), p, fvs))
                    qp = self.q(pt, nbound)
                    ps.append(qp)
                    nsub[v] = _unplus(qp)
                out.append(" " * (ind + 2) + f"case {' '.join(ps)}:")
                out += walk(child, nsub, nbound, ind + 4, ntys)
            return out
        lines += walk(body, {}, set(names), 2, {n: t for _, n, t in params})
        if expand and not expanded[0]:
            return None
        return "\n".join(lines) + "\n", used_ih[0]

    def _ctor_patterns(self, ty: str | None) -> list[str]:
        """Source patterns of every constructor of a type (fresh field names), [] when unknown."""
        if not ty:
            return []
        name, _ = self.T.head(ty)
        if name == "Nat":
            return ["0n", f"1n+{self.var('p')}"]
        try:
            cs = self.T.ctors(ty)
        except Unsupported:
            return []
        return [f"{c}{{{', '.join(self.var(fn) for fn, _ in fs)}}}" for c, fs in cs]

    def _field_tys(self, ty: str | None, pat: str, fvs: list) -> dict:
        """The types of a top-level pattern's variables (for a later wildcard split), as far as they are known."""
        if not ty:
            return {}
        name, _ = self.T.head(ty)
        m = re.match(r"(\d+n)\+", pat)
        if name == "Nat" and m:
            return {fvs[0]: "Nat"} if fvs else {}
        cm = re.match(r"([A-Za-z_][\w]*)\{(.*)\}$", pat)
        if not cm:
            return {}
        try:
            fs = dict(self.T.ctors(ty)).get(cm.group(1))
        except Unsupported:
            return {}
        if fs is None:
            return {}
        out = {}
        for (fn, ft), fp in zip(fs, split_top(cm.group(2))):
            v = fp.lstrip("+")
            if re.match(r"[a-z_][A-Za-z0-9_]*$", v):
                out[v] = ft
        return out

    def _pattern(self, p: str) -> tuple[str, list[str]]:
        """A source pattern with every field bound (wildcards named) and reusable: (pattern text, its variables)."""
        fvs = []

        def fix(s: str) -> str:
            m = re.match(r"([A-Za-z_][\w.]*)\{(.*)\}$", s)
            if not m:
                if s == "_":
                    v = self.var("w")
                    fvs.append(v)
                    return "+" + v
                nm = re.match(r"(\d+n)\+([+]?)([a-z_]\w*)$", s)
                if nm:
                    fvs.append(nm.group(3))
                    return f"{nm.group(1)}+{nm.group(3)}"
                if re.match(r"\d+n$", s):
                    return s
                v = s.lstrip("+")
                fvs.append(v)
                return "+" + v
            return f"{m.group(1)}{{{', '.join(fix(x) for x in split_top(m.group(2)))}}}"
        return fix(p), fvs

    # -- the root law's proof
    def law_def(self, f: str, law: str, lemma: str) -> str:
        params, _ = self.sig(f)
        names = [n for _, n, _ in params]
        return f"def Laws.{law}({', '.join(names)}):\n  {lemma}({', '.join(names)})\n"

    def law_text(self, f: str, law: str) -> str:
        params, ret = self.sig(f)
        names = [n for _, n, _ in params]
        bs = "".join(f"  for +{n}: {self.q(t, set())}\n" for _, n, t in params)
        return (f"law {law}:\n{bs}  {{{ALIAS}.{PREFIX}{f}({', '.join(names)}) == {ALIAS}.{f}({', '.join(names)}) : "
                f"{self.q(ret, set())}}}\n")

    # -- family roots: transport both ways
    def family(self, t: str, lemmas: dict) -> tuple[str, str] | None:
        """(laws text, proofs text) of to_<t> (old family to new) and from_<t> (new to old), or None when the class
        does not apply: the old and new declarations must have the same constructors, fields and erased indices; a
        field is plain data (passed on), a recursive occurrence of the family (transported by the induction
        hypothesis), or an equality whose sides mention changed functions only through proven lemmas (rewritten)."""
        it_n, it_o = self.pm.new_items[t], self.pm.old_items.get(t)
        if it_o is None or it_n.kind != "type" or it_n.ret != "Type":
            return None
        ren = {n: PREFIX + n for n in self.pm.renamed}
        shape = lambda it, r: [(c, [(n, rename(ty, r)) for n, ty in fs]) for c, fs in it.ctors]
        if shape(it_n, ren) != shape(it_o, ren) or it_n.params != it_o.params:
            return None
        if any(q != "-" for q, _, _ in it_n.params):
            return None
        idx = [n for _, n, _ in it_n.params]
        changed = {n for n in self.pm.renamed if self.pm.new_items.get(n) and self.pm.new_items[n].kind == "def"}
        laws, proofs = [], []
        for direction in ("to", "from"):
            src, dst = (PREFIX + t, t) if direction == "to" else (t, PREFIX + t)
            law = f"{direction}_{t}"
            ib = "".join(f"  for -{n}: {self.q(ty, set())}\n" for _, n, ty in it_n.params)
            laws.append(f"law {law}:\n{ib}  for r: {ALIAS}.{src}<{', '.join(idx)}>\n  {ALIAS}.{dst}<{', '.join(idx)}>\n")
            body = [f"def Laws.{law}({', '.join(idx + ['r'])}):", "  match r:"]
            for c, fs in it_n.ctors:
                csrc, cdst = (PREFIX + c, c) if direction == "to" else (c, PREFIX + c)
                fvs = [f"f_{n}" for n, _ in fs]
                fren = {n: v for (n, _), v in zip(fs, fvs)}
                bound = set(fvs) | set(idx)
                pats, out_args = [], []
                for (fname, fty), fv in zip(fs, fvs):
                    hd = fty.strip()
                    rec = re.match(re.escape(t) + r"<(.*)>$", hd)
                    if hd.startswith("{"):
                        pats.append(fv)
                        sides, ty = _eq_parts(hd)
                        if sides is None:
                            return None
                        # the destination field's type: the new declaration (to) or the old one (from)
                        lhs, rhs = (rename(x, fren) for x in sides)
                        if direction == "from":
                            lhs, rhs = rename(lhs, ren), rename(rhs, ren)
                        if calls(self.q(lhs, bound), changed | {PREFIX + g for g in changed}):
                            return None   # only the right-hand side of an equality field is rewritten
                        lq, cur, tq = self.q(lhs, bound), self.q(rhs, bound), self.q(ty, bound)
                        want = changed if direction == "to" else {PREFIX + g for g in changed}
                        steps = []
                        for _ in range(10000):
                            cs = calls(cur, want)
                            inner = [x for x in cs if not any(o is not x and x[0] < o[0] and o[1] <= x[1] for o in cs)]
                            if not inner:
                                break
                            s_, e_, name, a0 = inner[0]
                            g = name if direction == "to" else name[len(PREFIX):]
                            if g not in lemmas:
                                return None
                            gargs = cur[a0:e_ - 1]
                            motive = f"{{{lq} == {cur[:s_]}_{cur[e_:]} : {tq}}}"
                            if direction == "to":
                                steps.append(f"%{lemmas[g]}({gargs}) : {motive}")
                                cur = cur[:s_] + f"{ALIAS}.{PREFIX}{g}({gargs})" + cur[e_:]
                            else:
                                gret = self.q(self.pm.new_items[g].ret, set())
                                steps.append(f"%Equal.sym({gret}, {ALIAS}.{PREFIX}{g}({gargs}), {ALIAS}.{g}({gargs}), "
                                             f"{lemmas[g]}({gargs})) : {motive}")
                                cur = cur[:s_] + f"{ALIAS}.{g}({gargs})" + cur[e_:]
                        out_args.append(("(" + "\n        ".join(steps + [fv]) + ")") if steps else fv)
                    elif rec:
                        pats.append(fv)
                        rargs = [rename(x, fren) for x in split_top(rec.group(1))]
                        out_args.append(f"Laws.{law}({', '.join(rargs + [fv])})")
                    else:
                        if calls(self.q(rename(hd, fren), bound), changed | {PREFIX + g for g in changed}):
                            return None
                        pats.append("+" + fv)
                        out_args.append(fv)
                body.append(f"    case {ALIAS}.{csrc}{{{', '.join(pats)}}}:")
                body.append(f"      {ALIAS}.{cdst}{{{', '.join(out_args)}}}")
            proofs.append("\n".join(body) + "\n")
        return "\n".join(laws), "\n".join(proofs)


def _replace_calls(text: str, call: str, new: str) -> str:
    """text with every occurrence of the call text `call` (a whole call: not preceded by a name character) replaced."""
    return re.sub(r"(?<![\w.$])" + re.escape(call), lambda m: new, text)


def _product(alts: list) -> list:
    out = [[]]
    for a in alts:
        out = [x + [y] for x in out for y in a]
    return out


def _unplus(p: str) -> str:
    return re.sub(r"(?<![\w])\+(?=[A-Za-z_])", "", p)


def _rename_fields(text: str, fs: list, fvs: list) -> str:
    return rename(text, {n: v for (n, _), v in zip(fs, fvs)})


def _eq_parts(t: str):
    """'{a == b : T}' -> ((a, b), T)."""
    t = t.strip()
    if not (t.startswith("{") and t.endswith("}")):
        return None, None
    inner = t[1:-1]
    parts = split_top(inner, ":")
    if len(parts) < 2:
        return None, None
    eq, ty = ":".join(parts[:-1]), parts[-1]
    sides = eq.split(" == ")
    if len(sides) != 2:
        return None, None
    return (sides[0].strip(), sides[1].strip()), ty.strip()


# ---------------------------------------------------------------- checking
LEMMA = "q_"

# Base identities the congruence class may use (proved here by induction over Word(n); no axioms), and the rules
# (Base call, lemma, the old form) that rewrite a new form into the old one: target-agnostic facts about Base only.
CORE = """\
# ---- core: Base identities, proved here by induction over Word(n)
def core_wz_add(n: Nat, w: Word(n)) -> {Word.adc(n, w, Word.zero(n), False{}, False{}) == w : Word(n)}:
  match n:
    case 0n:
      match w:
        case WNil{}:
          {==}
    case 1n+p:
      match w:
        case WCon{False{}, t}:
          %core_wz_add(p, t) : {WCon{False{}, Word.adc(p, t, Word.zero(p), False{}, False{})} == WCon{False{}, _} : Word(1n+p)}
          {==}
        case WCon{True{}, t}:
          %core_wz_add(p, t) : {WCon{True{}, Word.adc(p, t, Word.zero(p), False{}, False{})} == WCon{True{}, _} : Word(1n+p)}
          {==}

def core_wz_inc(n: Nat, w: Word(n)) -> {Word.adc(n, w, Word.zero(n), False{}, True{}) == Word.inc(n, w) : Word(n)}:
  match n:
    case 0n:
      match w:
        case WNil{}:
          {==}
    case 1n+p:
      match w:
        case WCon{False{}, t}:
          %core_wz_add(p, t) : {WCon{True{}, Word.adc(p, t, Word.zero(p), False{}, False{})} == WCon{True{}, _} : Word(1n+p)}
          {==}
        case WCon{True{}, t}:
          %core_wz_inc(p, t) : {WCon{False{}, Word.adc(p, t, Word.zero(p), False{}, True{})} == WCon{False{}, _} : Word(1n+p)}
          {==}

def core_u32_inc(x: U32) -> {U32.add(x, 1) == U32.inc(x) : U32}:
  match x:
    case U32{w}:
      match w:
        case WCon{False{}, t}:
          %core_wz_add(31n, t) : {U32{WCon{True{}, Word.adc(31n, t, Word.zero(31n), False{}, False{})}} == U32{WCon{True{}, _}} : U32}
          {==}
        case WCon{True{}, t}:
          %core_wz_inc(31n, t) : {U32{WCon{False{}, Word.adc(31n, t, Word.zero(31n), False{}, True{})}} == U32{WCon{False{}, _}} : U32}
          {==}
"""
CORE_RULES = [("U32.inc", "core_u32_inc", "U32.add({}, 1)")]


@dataclass
class Check:
    ok: bool
    out: str
    seconds: float
    location: str | None


def _run(d: Path, name: str, cfg: dict | None, verdict: bool = False) -> Check:
    from .. import bend
    r = bend.check_verdict(d / name, cfg) if verdict else bend.check(d / name, cfg)
    m = re.search(r"^Location: (\S+)", r.out, re.M)
    text = "\n".join(ln for ln in r.out.splitlines() if "is available: run bend update" not in ln).strip()
    return Check(bool(r.ok), text, r.seconds, m.group(1) if m else None)


def kernel_message(out: str, lines: int = 14) -> str:
    keep = [ln for ln in out.splitlines() if ln.strip()]
    return "\n".join(keep[:lines])


# ---------------------------------------------------------------- the counter class
class Values:
    """Values of a parameter type, generated with a fixed seed. A value of a type already generated within the same
    candidate is reused with probability one half, so keys repeat (equal keys, duplicate entries): the inputs where
    first-match and every-match definitions part."""
    POOL = [0, 1, 2, 3, 255, 256, 57005, 4294967295]

    def __init__(self, types: Types, seed: str):
        self.T = types
        self.rng = random.Random(int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16))
        self.seen: dict = {}

    def reset(self):
        self.seen = {}

    def gen(self, ty: str, depth: int = 0):
        name, args = self.T.head(ty)
        key = ty.replace(" ", "")
        if self.seen.get(key) and self.rng.random() < 0.5:
            return self.rng.choice(self.seen[key])
        v = self._fresh(name, args, ty, depth)
        self.seen.setdefault(key, []).append(v)
        return v

    def _fresh(self, name, args, ty, depth):
        if name == "U32":
            return self.rng.choice(self.POOL)
        if name == "Bool":
            return {"$bool": self.rng.random() < 0.5}
        if name == "Nat":
            return {"$nat": str(self.rng.choice([0, 1, 2, 3, 8, 32]))}
        if name == "List":
            el = args[-1] if args else "U32"
            n = 0 if depth > 4 else self.rng.choice([0, 1, 2, 2, 3, 4])
            items = [self.gen(el, depth + 1) for _ in range(n)]
            out = {"$": "Nil"}
            for x in reversed(items):
                out = {"$": "Con", "head": x, "tail": out}
            return out
        it = self.T.items.get(name)
        if it is None or it.kind != "type" or it.ret != "Data" or it.params:
            raise Unsupported(f"cannot generate values of {ty}")
        cs = it.ctors
        if depth > 6:   # prefer a constructor without recursive fields
            flat = [c for c in cs if all(self.T.head(t)[0] != name for _, t in c[1])]
            cs = flat or cs
        c, fs = self.rng.choice(cs)
        v = {"$": c}
        for fname, fty in fs:
            v[fname] = self.gen(fty, depth + 1)
        return v


def render(v, ty: str, T: Types) -> str:
    """A generated value as a Bend literal (constructors qualified with the pair module's alias)."""
    if isinstance(v, int):
        return str(v)
    if "$nat" in v:
        return f"{v['$nat']}n"
    if "$bool" in v:
        return "True{}" if v["$bool"] else "False{}"
    name, args = T.head(ty)
    if name == "List":
        el = args[-1] if args else "U32"
        xs = []
        while v.get("$") == "Con":
            xs.append(render(v["head"], el, T))
            v = v["tail"]
        return "[" + ", ".join(xs) + "]" if xs else "Nil{}"
    c = v["$"]
    fs = next(f for cc, f in T.items[name].ctors if cc == c)
    return f"{ALIAS}.{c}{{{', '.join(render(v[fn], ft, T) for fn, ft in fs)}}}"


def _field_types(T: Types, ty: str, ctor: str) -> list:
    name, args = T.head(ty)
    if name == "List":
        el = args[-1] if args else "U32"
        return [("head", el), ("tail", ty)] if ctor == "Con" else []
    return list(next(fs for c, fs in T.items[name].ctors if c == ctor))


def discriminator(T: Types, ty: str, val, path: list, prefix: str) -> tuple[list[str], str]:
    """(defs, name of the first): d(x) is Unit when x agrees with val along path (constructor by constructor, then the
    leaf's value) and Empty elsewhere, so d(old result) is Unit and d(new result) is Empty."""
    defs, k = [], [0]
    names = set(T.items) | set(T.ctor_of)

    def go(ty, v, path):
        me = f"{prefix}{k[0]}"
        k[0] += 1
        head = f"def {me}(x: {qualify(ty, names, set())}) -> Type:"
        if isinstance(v, int):
            defs.append(f"{head}\n  {prefix}t(U32.is_eq(x, {v}))\n")
            return me
        if "$bool" in v:
            a, b = ("Unit", "Empty") if v["$bool"] else ("Empty", "Unit")
            defs.append(f"{head}\n  match x:\n    case True{{}}:\n      {a}\n    case False{{}}:\n      {b}\n")
            return me
        if "$nat" in v:
            defs.append(f"{head}\n  {prefix}t(Nat.is_eq(x, {v['$nat']}n))\n")
            return me
        ctor = v["$"]
        sub = go(dict(_field_types(T, ty, ctor))[path[0]], v[path[0]], path[1:]) if path else None
        lines = [head, "  match x:"]
        for c, _ in T.ctors(ty):
            fs = _field_types(T, ty, c)
            cq = c if c in BASE_CTORS else f"{ALIAS}.{c}"
            pats = ", ".join(f"y_{fn}" if (c == ctor and path and fn == path[0]) else "_" for fn, _ in fs)
            lines.append(f"    case {cq}{{{pats}}}:")
            lines.append("      " + ("Empty" if c != ctor else "Unit" if sub is None else f"{sub}(y_{path[0]})"))
        defs.append("\n".join(lines) + "\n")
        return me
    first = go(ty, val, list(path))
    defs.insert(0, f"def {prefix}t(b: Bool) -> Type:\n  match b:\n    case True{{}}:\n      Unit\n    case False{{}}:\n"
                "      Empty\n")
    return defs, first


class Evaluator:
    """The compiled pair module in one node process (holon/js/equiv.mjs)."""
    DRIVER = Path(__file__).resolve().parents[1] / "js" / "equiv.mjs"

    def __init__(self, d: Path, cfg: dict | None):
        from .. import bend
        r = bend.run(["pair.bend", "-o", "pair.mjs"], cwd=d, cfg=cfg)
        if r.code != 0 or not (d / "pair.mjs").exists():
            raise Unsupported(f"the pair module does not compile to JavaScript: {r.out[:400]}")
        node = (cfg or bend.config()).get("node", "node")
        self.p = subprocess.Popen([node, str(self.DRIVER), str(d / "pair.mjs")], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)

    def ask(self, old: str, new: str, args: list) -> dict:
        self.p.stdin.write(json.dumps({"old": old, "new": new, "args": args}) + "\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        return json.loads(line) if line else {"error": "the evaluator stopped"}

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=10)
            self.p.stdout.close()
        except Exception:  # noqa: BLE001
            self.p.kill()


def search_counter(ev: Evaluator, gen: "Gen", f: str, tries: int) -> dict | None:
    """The first generated input where o__f and f differ: {"args", "a", "b", "path"}; None when none is found."""
    params, ret = gen.sig(f)
    vals = Values(gen.T, f"holon-equivalence:{f}")
    for _ in range(tries):
        vals.reset()
        try:
            args = [vals.gen(t) for _, _, t in params]
        except Unsupported:
            return None
        r = ev.ask(PREFIX + f, f, args)
        if r.get("error"):
            continue
        if not r["same"]:
            return {"args": args, "a": r["a"], "b": r["b"], "path": r["path"]}
    return None


def counter_texts(gen: "Gen", f: str, wit: dict) -> tuple[str, str, str]:
    """(law name, LAWS text, PROOF text) of the counter-law {o__f(W) != f(W)} at a found witness."""
    params, ret = gen.sig(f)
    law = f"cl_{f}"
    T = gen.T
    lits = [render(v, t, T) for v, (_, _, t) in zip(wit["args"], params)]
    names = [n for _, n, _ in params]
    bs = "".join(f"  exs {n}: {gen.q(t, set())}\n" for _, n, t in params)
    laws = (f"law {law}:\n{bs}  {{{ALIAS}.{PREFIX}{f}({', '.join(names)}) != {ALIAS}.{f}({', '.join(names)}) : "
            f"{gen.q(ret, set())}}}\n")
    defs, first = discriminator(T, ret, wit["a"], wit["path"], f"d_{f}_")   # each def before its users
    wdefs = [f"def w_{f}_{i}() -> {gen.q(t, set())}:\n  {lit}\n" for i, (lit, (_, _, t)) in enumerate(zip(lits, params))]
    body = "e => (%e : " + first + "(_)\n  Unit{})"
    for i in reversed(range(len(params))):
        body = f"(w_{f}_{i}(), {body})"
    proof = "\n".join(defs + wdefs) + f"\ndef Laws.{law}():\n  {body}\n"
    return law, laws, proof


# ---------------------------------------------------------------- the obligation
def _deps(pm: PairModule, changed: set) -> dict:
    """f -> the changed definitions f's old or new body reaches through definitions that are not themselves
    changed (an unchanged or one-sided helper unfolds; a changed one needs its lemma first)."""
    from .. import bindings as B
    gn, go = B.kernel_graph(pm.en), B.kernel_graph(pm.eo)
    out = {}
    for f in sorted(changed):
        need = set()
        for g in (gn, go):
            seen, todo = {f}, list(g.get(f, []))
            while todo:
                x = todo.pop()
                if x in seen:
                    continue
                seen.add(x)
                if x in changed:
                    need.add(x)
                    continue
                todo.extend(g.get(x, []))
        out[f] = sorted(need - {f})
    return out


def _write(d: Path, files: dict):
    for name, text in files.items():
        (d / name).write_text(text)


def _progress(msg: str) -> None:
    """A progress line on stderr when HOLON_EQV_PROGRESS is set (long runs; nothing else reads it)."""
    import os
    import sys
    if os.environ.get("HOLON_EQV_PROGRESS"):
        print(f"[equivalence] {msg}", file=sys.stderr, flush=True)


def _owner(loc: str, trying: dict):
    """The lemma a failing definition belongs to: q_<f> itself or one of its helpers and lemmas q_<f>__<x>."""
    best = None
    for f in trying:
        if loc == LEMMA + f or loc.startswith(LEMMA + f + "__"):
            if best is None or len(f) > len(best):
                best = f
    return best


def default_cache_path(old_text: str, new_text: str, cfg: dict | None = None) -> Path:
    """F33: where the lemma cache of a model pair lives, outside the repository:
    ~/.holon/cache/eqv/<sha256 of the two model texts>/<sha256 of the bend fingerprint, the BendTT kernel's sha256 and
    the generator's own source>.jsonl. Pair modules built from the same two models (the laws of one model pair) share it."""
    import os
    from .. import bend
    from . import eqsearch
    pair = hashlib.sha256(old_text.encode() + b"\0" + new_text.encode()).hexdigest()[:24]
    try:
        cfg = cfg or bend.config()
        fp = bend.fingerprint(cfg)
        kp = bend.verdict_kernel_path(Path(fp["checkout"]))
        kern = bend.file_sha256(kp) if kp.is_file() else "no-kernel"
        ident = fp["fingerprint"] + "\0" + kern
    except Exception as e:  # noqa: BLE001  (no checker: the key says so, and nothing is checked anyway)
        ident = f"no-checker: {type(e).__name__}"
    who = hashlib.sha256((ident + "\0" + eqsearch.generator_sha256()).encode()).hexdigest()[:24]
    return Path(os.path.expanduser("~")) / ".holon" / "cache" / "eqv" / pair / f"{who}.jsonl"


def default_cache(old_text: str, new_text: str, cfg: dict | None = None):
    """The persistent lemma cache of a model pair (holon.gen.eqsearch.LemmaCache), shared within the process;
    HOLON_EQV_CACHE=0 gives a cache in memory only."""
    import os
    from . import eqsearch
    if os.environ.get("HOLON_EQV_CACHE", "1") == "0":
        return eqsearch.LemmaCache(None)
    return eqsearch.cache_at(default_cache_path(old_text, new_text, cfg))


def library_modules() -> tuple:
    """Lemma libraries about fixed model text (holon.sorts.prelude3_lemmas): each is used only for a new model that
    holds the definitions it is about with exactly its text (the module's applies). The Base library holon.gen.eqlib
    is always emitted. Imported statically, so the generator closure (holon.records.generator_files) holds them."""
    from ..sorts import prelude3_lemmas
    return (prelude3_lemmas,)


def libraries_for(pm: "PairModule") -> list:
    return [m for m in library_modules() if m.applies(pm.new_items)]


def library_text(libs) -> str:
    from . import eqlib
    return eqlib.text() + "".join("\n" + m.text() for m in libs)


_LEMMA_REF = re.compile(r"(?<![\w.])" + LEMMA + r"([A-Za-z0-9_]+)\(")


def _needed(proven: dict, texts) -> set:
    """The proven lemmas the given texts use, directly or through other proven lemmas."""
    need, todo = set(), [t for t in texts]
    while todo:
        for m in _LEMMA_REF.finditer(todo.pop()):
            t = m.group(1)   # q_<f>, or a helper or lemma of it, q_<f>__<x>
            for g in [t] + [t[:i] for i in range(len(t)) if t.startswith("__", i)]:
                if g in proven and g not in need:
                    need.add(g)
                    todo.append(proven[g]["text"])
    return need


def _lemma_file(proven: dict, trying: dict, libs=()) -> str:
    """The lemmas being tried, after the proven lemmas they use (only those: a round checks what it adds; the final
    check holds every lemma)."""
    parts = [f"import Base\nimport ./pair.bend as {ALIAS}\n", CORE, library_text(libs)]
    need = _needed(proven, [t[1] for t in trying.values()])
    for f in proven:   # proof order: every lemma after the lemmas it uses
        if f in need:
            parts.append(proven[f]["text"])
    for f in sorted(trying):
        parts.append(trying[f][1])
    return "\n".join(parts)


def root_laws_text(pm: "PairModule") -> tuple[str, list[str]]:
    """(LAWS.bend text, law names) of a PROVED equivalence on pair module pm, regenerated from pm alone (F33: G2
    compares it byte for byte with a committed LAWS.bend): eq_<r> for a changed definition root, to_<r> and from_<r>
    for a changed datatype root, nothing for an unchanged root, in pm.roots order, as prove writes them. Raises
    Unsupported for a root no PROVED equivalence states a law for."""
    gen = Gen(pm)
    src = lambda d: _source_name(d, pm.old_items)
    changed = sorted({src(d) for d in pm.dirty_entries
                      if pm.old_items[src(d)].kind == "def" and src(d) in pm.new_items
                      and pm.new_items[src(d)].kind == "def"})
    lemmas = {g: LEMMA + g for g in changed}
    laws, names = [], []
    for r in pm.roots:
        if r not in pm.dirty_entries:
            continue
        if r in pm.new_items and pm.new_items[r].kind == "def" and r in changed:
            laws.append(gen.law_text(r, f"eq_{r}"))
            names.append(f"eq_{r}")
        elif r in pm.new_items and pm.new_items[r].kind == "type":
            fam = gen.family(r, lemmas)
            if fam is None:
                raise Unsupported(f"the family root {r} has no transport law")
            laws.append(fam[0])
            names += [f"to_{r}", f"from_{r}"]
        else:
            raise Unsupported(f"the changed root {r} is not a definition or a datatype of both models")
    return f"import Base\nimport ./pair.bend as {ALIAS}\n\n" + "\n".join(laws), names


def prove(old_text: str, new_text: str, statement_text: str, cfg: dict | None = None, workdir: Path | None = None,
          verdict: bool | None = None, counter_tries: int = 300, eo: dict | None = None, en: dict | None = None,
          cache=None, workers: int | None = None, batch: int | None = None, deadline: float | None = None) -> dict:
    """Decide the equivalence obligation of a binding change (see the module docstring). Deterministic: the same two
    model texts and statement give byte-identical laws and proofs."""
    from .. import bend
    t0 = time.monotonic()
    cfg = cfg or bend.config()
    verdict = bend.verdict_enabled(cfg) if verdict is None else verdict
    out = {"status": "UNSUPPORTED", "roots": [], "lemmas": {}, "laws": None, "proof": None, "pair_sha256": None,
           "kernels": [], "linkage": [], "counters": {}, "seconds": 0.0, "reason": "", "generator": "holon.gen.equivalence"}
    try:
        pm = pair_module(old_text, new_text, statement_text, cfg, eo, en)
    except (Unsupported, ValueError) as e:
        out["reason"] = f"unsupported: {e}"
        return out
    out["pair_sha256"] = hashlib.sha256(pm.text.encode()).hexdigest()
    out["pair_text"] = pm.text
    try:
        ep = kernel_entries_of(pm.text, cfg, "pair module")
    except Exception as e:  # noqa: BLE001  (a pair module the checker refuses proves nothing)
        out["reason"] = f"the pair module does not translate to BendTT: {e}"
        return out
    out["linkage"] = linkage(pm, ep)
    if out["linkage"]:
        out["reason"] = f"the pair module is not the two models: {'; '.join(out['linkage'][:5])}"
        return out
    gen = Gen(pm)
    libs = libraries_for(pm)
    out["libraries"] = [m.__name__ for m in libs]
    src = lambda d: _source_name(d, pm.old_items)
    changed = sorted({src(d) for d in pm.dirty_entries
                      if pm.old_items[src(d)].kind == "def" and src(d) in pm.new_items
                      and pm.new_items[src(d)].kind == "def"})
    deps = _deps(pm, set(changed))
    tmp = Path(tempfile.mkdtemp(prefix="holon-eqv-", dir=str(workdir) if workdir else None))
    proven: dict = {}
    failed: dict = {}
    try:
        _write(tmp, {"pair.bend": pm.text})
        # ---- lemmas (holon.gen.eqsearch): found bottom-up in small, batched bend2 checks, cached by obligation; the
        # final whole-file check below, in both kernels, is the only verdict
        engine_state: dict = {}

        def engine(f, cone):
            """(class, text) of the F32 proof classes (holon.gen.eqprove) for f, or raises Unsupported. Only the
            changed definitions f reaches are given (all proven by then): the text depends on f's obligation alone."""
            from . import eqprove as EP
            if "defs" not in engine_state:
                from . import eqlib, eqterms as ET
                bd, bt = eqlib.base_defs()
                pd, pt = ET.read_source(pm.text, qualify=ALIAS)
                engine_state["defs"], engine_state["types"] = {**bd, **pd}, {**bt, **pt}
            callee = {f"{ALIAS}.{g}": LEMMA + g for g in cone}
            opaque = set(callee) | {f"{ALIAS}.{PREFIX}{g}" for g in cone}
            pv = EP.Prover(engine_state["defs"], engine_state["types"], f"{ALIAS}.{PREFIX}", opaque, callee,
                           tag=LEMMA + f, libraries=libs)
            params, ret = gen.sig(f)
            ps = [(n, gen.q(t, set())) for _, n, t in params]
            args = tuple(("var", n) for n, _ in ps)
            try:
                text = pv.prove_lemma(LEMMA + f, ps, ("app", f"{ALIAS}.{PREFIX}{f}", args), ("app", f"{ALIAS}.{f}", args),
                                      gen.q(ret, set()))
            except (EP.Fail, EP.E.TermError, RecursionError) as e:
                raise Unsupported(f"no proof found: {str(e)[:300]}")
            return pv.label(), "\n".join(pv.out + [text])

        from . import eqsearch as ES
        head = f"import Base\nimport ./pair.bend as {ALIAS}\n\n" + CORE + "\n" + library_text(libs) + "\n"
        if cache is None:
            cache = ES.LemmaCache(None)
        search = ES.Search(pm, gen, libs, changed, deps, cfg, tmp, head, LEMMA, PREFIX, ALIAS, cache=cache,
                           workers=ES.default_workers() if workers is None else workers,
                           batch=ES.default_batch() if batch is None else batch, engine=engine, progress=_progress)
        out["search"] = search.stats
        final_tries = 0
        while True:
            stop = search.run(deadline)
            proven = {f: search.proven[f] for f in search.ordered()}
            failed = dict(search.failed)
            out["lemmas"] = {}
            for f in changed:
                if f in proven:
                    out["lemmas"][f] = {"status": "PROVED", "class": proven[f]["class"], "attempts": search.attempts[f]}
                elif f in failed:
                    out["lemmas"][f] = {"status": "UNKNOWN", "class": None, "attempts": search.attempts[f]}
                else:
                    out["lemmas"][f] = {"status": "BLOCKED", "class": None, "attempts": search.attempts[f],
                                        "blocked_by": [g for g in deps[f] if g not in proven]}
            if stop:   # the time box, or a stop of the search (repeated bend timeouts, a failure outside the lemmas):
                # no verdict on what it did not reach; the roots are still decided below (UNKNOWN unless proven by the
                # final check) and the counter search still runs (AGENTS rule 6: UNKNOWN, with what was tried)
                out["search_stop"] = stop
            out["roots"] = []
            # ---- root obligations
            lemmas = {g: LEMMA + g for g in proven}
            laws, proofs, expected = [], [], []
            for r in pm.roots:
                info = {"root": r}
                if r not in pm.dirty_entries:
                    info.update(kind="unchanged", **{"class": "unchanged"}, status="PROVED",
                                reason="the kernel form of the root and of everything it reaches is unchanged")
                elif r in pm.new_items and pm.new_items[r].kind == "def" and r in changed:
                    info.update(kind="function", law=f"eq_{r}")
                    if r in proven:
                        laws.append(gen.law_text(r, f"eq_{r}"))
                        proofs.append(gen.law_def(r, f"eq_{r}", LEMMA + r))
                        expected.append(f"eq_{r}")
                        info.update(**{"class": proven[r]["class"]}, status="PENDING")
                    else:
                        info.update(**{"class": None}, status="UNKNOWN",
                                    reason=_why(r, out["lemmas"], deps, proven))
                elif r in pm.new_items and pm.new_items[r].kind == "type":
                    info.update(kind="family")
                    try:
                        fam = gen.family(r, lemmas)
                    except Unsupported as e:
                        fam = None
                        info["reason"] = str(e)
                    if fam is None:
                        need = sorted({g for d in [r] for g in _family_calls(pm, r)} - set(proven))
                        info.update(**{"class": None}, status="UNKNOWN",
                                    reason=info.get("reason") or ("the family class needs lemmas for " + ", ".join(need) + ": "
                                           + "; ".join(f"{g}: {_why(g, out['lemmas'], deps, proven)}" for g in need[:3])))
                    else:
                        laws.append(fam[0])
                        proofs.append(fam[1])
                        expected += [f"to_{r}", f"from_{r}"]
                        info.update(**{"class": "family"}, status="PENDING", law=f"to_{r}, from_{r}")
                else:
                    info.update(kind="other", **{"class": None}, status="UNSUPPORTED",
                                reason="a changed root that is not a definition or a datatype of both models")
                out["roots"].append(info)
            # ---- the final check: the root laws, every lemma, both kernels
            if expected:
                laws_text = f"import Base\nimport ./pair.bend as {ALIAS}\n\n" + "\n".join(laws)
                proof_text = (f"import Base\nimport ./pair.bend as {ALIAS}\nimport ./LAWS.bend as Laws\n\n" + CORE + "\n"
                              + library_text(libs) + "\n"
                              + "\n".join(proven[f]["text"] for f in proven) + "\n" + "\n".join(proofs))
                out["final"] = {"proof_bytes": len(proof_text), "lemmas": len(proven)}
                _write(tmp, {"LAWS.bend": laws_text, "PROOF.bend": proof_text})
                from ..pipeline import law_names
                hatches = bend.escape_hatches(proof_text + laws_text + pm.text)
                r = _run(tmp, "PROOF.bend", cfg)
                ok = r.ok and sorted(law_names(laws_text)) == sorted(expected) and not hatches
                bad = search.owner_of(r.location or "") if (not r.ok and not hatches) else None
                if bad is not None and final_tries < 3:   # a cached lemma the whole file refuses: search it again
                    final_tries += 1
                    search.reject(bad, r.out)
                    continue
                kern = ["bend"] if ok else []
                v = None
                if ok and verdict:
                    v = _run(tmp, "PROOF.bend", cfg, verdict=True)
                    ok = v.ok
                    if ok:
                        kern.append("BendTT")
                for info in out["roots"]:
                    if info["status"] == "PENDING":
                        info["status"] = "PROVED" if ok else "UNKNOWN"
                        info["bend_seconds"] = r.seconds
                        info["bendtt"] = None if v is None else ("accepted" if v.ok else "rejected")
                        info["bendtt_seconds"] = None if v is None else v.seconds
                        if not ok:
                            info["reason"] = ("escape hatch: " + ", ".join(hatches) if hatches else
                                              kernel_message((v.out if (v is not None and r.ok) else r.out)))
                out.update(laws=laws_text, proof=proof_text, kernels=kern)
            break
        # ---- counters: a refutation for every root that is not proven, and for every lemma that failed
        todo = [i["root"] for i in out["roots"] if i["status"] != "PROVED" and i.get("kind") == "function"]
        todo += [f for f in sorted(failed) if f not in todo]
        # every other changed definition that is not proven: a cheaper search (the report names which really differ)
        rest = [f for f in changed if f not in proven and f not in todo]
        if todo and counter_tries:
            try:
                ev = Evaluator(tmp, cfg)
            except Unsupported as e:
                ev = None
                out["counter_note"] = str(e)
            if ev is not None:
                try:
                    for f in todo:
                        try:
                            wit = search_counter(ev, gen, f, counter_tries)
                        except Unsupported:
                            wit = None
                        if wit is None:
                            continue
                        _counter(out, tmp, gen, f, wit, cfg, verdict)
                    for f in rest:
                        try:
                            wit = search_counter(ev, gen, f, max(1, counter_tries // 5))
                        except Unsupported:
                            wit = None
                        if wit is None:
                            continue
                        _counter(out, tmp, gen, f, wit, cfg, verdict)
                finally:
                    ev.close()
        for info in out["roots"]:
            c = out["counters"].get(info["root"])
            if c and c["status"] == "REFUTED":
                info["status"] = "REFUTED"
                info["class"] = "counter"
                info["reason"] = (f"old and new differ at a concrete input (counter-law {c['law']} accepted by "
                                  f"{' and '.join(c['kernels'])})")
            elif info["status"] == "UNKNOWN":
                refuted = sorted(g for g, cc in out["counters"].items() if cc["status"] == "REFUTED")
                if refuted:
                    info["refuted_helpers"] = refuted
                    info["reason"] = (info.get("reason") or "") + (
                        f"; helpers whose old and new definitions differ at a concrete input (kernel-checked "
                        f"counter-laws): {', '.join(refuted[:8])}")
        for f, c in out["counters"].items():
            if f in out["lemmas"] and c["status"] == "REFUTED":
                out["lemmas"][f]["status"] = "REFUTED"
        st = [i["status"] for i in out["roots"]]
        out["status"] = ("REFUTED" if "REFUTED" in st else "PROVED" if all(s == "PROVED" for s in st) else
                         "UNSUPPORTED" if "UNSUPPORTED" in st else "UNKNOWN")
        out["reason"] = _summary(out) + (f"; the lemma search stopped: {out['search_stop']}" if out.get("search_stop")
                                         else "")
        return out
    finally:
        out["seconds"] = round(time.monotonic() - t0, 3)
        shutil.rmtree(tmp, ignore_errors=True)


def _counter(out: dict, tmp: Path, gen: "Gen", f: str, wit: dict, cfg, verdict: bool) -> None:
    """Check the counter-law at a found witness in both kernels; record it in out["counters"][f]."""
    from .. import bend
    law, ltext, ptext = counter_texts(gen, f, wit)
    cd = tmp / f"cl_{f}"
    cd.mkdir()
    (cd / "pair.bend").symlink_to(tmp / "pair.bend")
    lt = f"import Base\nimport ./pair.bend as {ALIAS}\n\n" + ltext
    pt = f"import Base\nimport ./pair.bend as {ALIAS}\nimport ./LAWS.bend as Laws\n\n" + ptext
    _write(cd, {"LAWS.bend": lt, "PROOF.bend": pt})
    rc = _run(cd, "PROOF.bend", cfg)
    vc = _run(cd, "PROOF.bend", cfg, verdict=True) if (rc.ok and verdict) else None
    acc = rc.ok and (vc is None or vc.ok) and not bend.escape_hatches(lt + pt)
    out["counters"][f] = {"status": "REFUTED" if acc else "UNKNOWN", "law": law, "laws": lt, "proof": pt,
                          "witness": wit["args"], "path": wit["path"], "bend_seconds": rc.seconds,
                          "kernels": (["bend"] + (["BendTT"] if vc is not None else [])) if acc else [],
                          "message": kernel_message((vc or rc).out)}


def _family_calls(pm: PairModule, t: str) -> list[str]:
    from .. import bindings as B
    g = B.kernel_graph(pm.en)
    out = set()
    for e in [t] + [n for n in pm.en if n.startswith(t + ".")]:
        for x in g.get(e, []):
            if pm.new_items.get(x) and pm.new_items[x].kind == "def" and x in {
                    _source_name(d, pm.old_items) for d in pm.dirty_entries}:
                out.add(x)
    return sorted(out)


def _why(f: str, lemmas: dict, deps: dict, proven: dict, depth: int = 0) -> str:
    info = lemmas.get(f) or {}
    if info.get("status") == "BLOCKED" or (f in deps and any(g not in proven for g in deps[f])):
        bl = [g for g in deps.get(f, []) if g not in proven]
        leaves = []
        seen = set()

        def walk(g):
            if g in seen:
                return
            seen.add(g)
            inf = lemmas.get(g) or {}
            nb = [h for h in deps.get(g, []) if h not in proven]
            if inf.get("status") == "UNKNOWN" or not nb:
                leaves.append(g)
            for h in nb:
                walk(h)
        for g in bl:
            walk(g)
        return f"blocked: needs {len(bl)} unproven changed definitions; the first unproven ones: {', '.join(sorted(leaves)[:8])}"
    att = info.get("attempts") or []
    return "no class proves it" + (f" ({att[-1].splitlines()[0]})" if att else "")


def _summary(out: dict) -> str:
    parts = []
    for i in out["roots"]:
        parts.append(f"{i['root']}: {i['status']}" + (f" ({i['class']})" if i.get("class") else ""))
    return "; ".join(parts)
