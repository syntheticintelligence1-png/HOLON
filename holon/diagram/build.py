"""Adapters: one fact document -> one diagram 𝔇 (whitepaper §4 Defs 4.1-4.4, 4.7; §8.3; BUILD_PLAN I11).

Each facts version has a table with one adapter per top-level section. A section without an
adapter, or a construct inside a section that no adapter maps (an unknown function kind, guard key,
action key, operator, ...), is a DiagramError: the diagram has zero unmapped constructs or it is not
written. A construct that fits no edge kind is a question for the human, never a forced mapping.

Facts 0.1 (header codecs):
  types        base types; carriers for the types the functions connect (records are products)
  functions    encoders and decoders -> CODEC edges. An edge is partial iff its declared codomain is
               an option type (Maybe<T>; §8.3: "partial edges return an option type"); an encoder's
               domain guard is kept on the edge as `domain`. Predicates -> domains of their input
               carrier, which becomes an interface carrier (R^ext). Projections -> product metadata of
               their record carrier, not edges (Def 4.1).
  assumptions  assumption records with ledger links (spec/ledger entries citing them)

Facts 0.2 (guarded-command machines):
  params -> parameter carriers (env); constants_doc -> lexical sources on them (E6); types -> base
  types; state -> one state carrier per field under the product carrier State, plus a STORE/LOAD
  pair per field; ghost_state -> ghost carriers; shadow -> residue carriers (slot-keyed); initial ->
  S0; principals -> concrete principal ids; reasons -> revert variants of Obs; defs -> content-hashed
  definitions attached to the edges that use them; actions -> TRANS edges with index-sensitive
  read/write sets (holon.diagram.access) and principal classes (holon.diagram.principals);
  migrations -> MIG (a migration with no code source is a modelling device: pseudo); observers ->
  observation LOAD edges into Obs; disch -> cost and delay terms; consumers -> CONS; coverage ->
  coverage debt; abstractions -> abstraction records with ledger links; target, extraction ->
  provenance; policy, search -> explorer configuration (metadata).

Both: hash functions the facts replace by stand-ins or premises (ledger entries of kind "hash")
are HASH coverage debt, since no facts construct yields a HASH edge.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .. import facts as F
from ..gen.targetlib import Library, lib_files
from ..ir import canonical_json
from ..records import LEDGER, all_bundles
from . import access as A
from .model import Carrier, Diagram, DiagramError, Edge
from .principals import CALLER, ENVIRONMENT, PrincipalError, principal_classes

ROOT = Path(__file__).resolve().parents[2]
# Def 4.7: the definition of the executable model each edge compiles to, by the generators' naming
# (holon.gen.model: one function per fact function; holon.gen.machine: step_<action>, mig_<migration>,
# one function per observer and per consumer). STORE and LOAD edges are field updates and projections
# of the state record inside those functions, so they have none.
MODEL_FN = {"CODEC": "{}", "TRANS": "step_{}", "MIG": "mig_{}", "observer": "{}", "CONS": "{}"}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _keys(what: str, obj: dict, allowed: set[str]) -> None:
    extra = sorted(set(obj) - allowed)
    if extra:
        raise DiagramError(f"{what}: unmapped keys {extra}")


def _plural(n: int, word: str) -> str:
    if n == 1:
        return f"{n} {word}"
    if word.endswith("s"):
        return f"{n} {word}es"
    if word.endswith("y"):
        return f"{n} {word[:-1]}ies"
    return f"{n} {word}s"


class Ctx:
    """One build: the facts, the diagram being built, ledger links and the inputs read."""

    def __init__(self, facts: dict, path: Path, root: Path):
        self.f = facts
        self.root = root
        self.path = path
        self.rel = path.resolve().relative_to(root.resolve()).as_posix()
        self.sha = _sha(path)
        self.d = Diagram(model=path.stem, facts=self.rel, facts_sha256=self.sha, facts_version=facts["facts_version"])
        self.inputs: dict[str, str] = {}
        self.prov: dict = {}
        self.bundle = self._bundle()
        self.links: dict[str, list[str]] = {}
        for e in (self.bundle or {}).get("entries", []):
            src, _, ptr = e.get("source", "").partition("#")
            if src == self.rel and ptr:
                self.links.setdefault(ptr, []).append(e["id"])
        self.links = {k: sorted(v) for k, v in self.links.items()}

    def _bundle(self) -> dict | None:
        for p in (self.root / LEDGER, self.path.parent / "ledger.json"):
            if p.exists():
                self.inputs[p.resolve().relative_to(self.root.resolve()).as_posix()] = _sha(p)
        try:
            bundles = all_bundles(self.root, self.rel)
        except FileNotFoundError:
            bundles = []
        return next((b for b in bundles if b["facts_sha256"] == self.sha), None)


# ====================================================================== shared
def a_target(ctx: Ctx, v: dict) -> str:
    ctx.prov["target"] = v
    return "provenance.target: the code the facts describe"


def a_extraction(ctx: Ctx, v: dict) -> str:
    ctx.prov["extraction"] = v
    return "provenance.extraction: how the facts were obtained"


def _hash_debt(ctx: Ctx) -> None:
    if ctx.bundle is None:
        ctx.d.debt("LEDGER", f"no ledger bundle has facts_sha256 {ctx.sha}: no model assumption is linked")
        return
    for e in ctx.bundle.get("entries", []):
        if e.get("kind") == "hash":
            ctx.d.debt("HASH", f"{e['id']}: {e['text']}", ledger=e["id"])


def _finish(ctx: Ctx) -> None:
    _hash_debt(ctx)
    ctx.d.extra["provenance"] = ctx.prov
    ctx.d.extra["inputs"] = [{"path": p, "sha256": s} for p, s in sorted(ctx.inputs.items())]


# ====================================================================== facts 0.1
def _vtext(vs: list[int]) -> str | None:
    vs = sorted(set(vs))
    if not vs:
        return None
    if len(vs) > 1 and vs == list(range(vs[0], vs[-1] + 1)):
        return f"{vs[0]}..{vs[-1]}"
    return ",".join(str(v) for v in vs)


def _rng(lo: int, n: int) -> str:
    return str(lo) if n == 1 else f"{lo}..{lo + n - 1}"


def _codomain(to: str) -> tuple[str, bool]:
    m = re.fullmatch(r"Maybe<(.+)>", to)
    return (m.group(1), True) if m else (to, False)


def _ensure01(ctx: Ctx, ty: str) -> Carrier:
    for c in ctx.d.carriers:
        if c.id == ty:
            return c
    bt = ctx.d.extra.get("base_types", {})
    if ty not in bt:
        raise DiagramError(f"type {ty} is not declared in types")
    kind = bt[ty]["kind"]
    extra: dict = {}
    if kind == "record":
        extra["product"] = [f["name"] for f in bt[ty]["fields"]]
    if kind == "bytes":
        extra["key_space"] = "byte"
    if kind == "list_of_bytes":
        extra["key_space"] = "position"
    return ctx.d.add_carrier(Carrier(ty, "rep", ty, extra=extra))


def _version_slot(ctx: Ctx) -> int | None:
    """Byte offset of the record field `version` (facts 0.1 conditions are over it: version_le,
    version_ge, version_in), in the declared field order."""
    off = 0
    for t in ctx.f["types"].values():
        if t.get("kind") != "record":
            continue
        for fld in t["fields"]:
            if fld["name"] == "version":
                return off
            off += fld["width"]
        off = 0
    return None


def _versions(ctx: Ctx, name: str, f: dict) -> list[int]:
    if f["kind"] == "encoder":
        if "domain" in f:
            dom = {k: v for k, v in f["domain"].items() if k != "code"}
            if set(dom) != {"version_le"}:
                raise DiagramError(f"functions.{name}: unmapped domain {sorted(dom)}")
            return list(range(dom["version_le"] + 1))
        slot = _version_slot(ctx)
        for op in f["ops"]:
            if op["offset"] == slot and len(op["src"]) == 1 and "const" in op["src"][0]:
                return [op["src"][0]["const"]]
        return []
    if f["kind"] == "decoder" and f.get("guard"):
        vs = []
        for r in ctx.f["functions"][f["guard"]]["rules"]:
            if isinstance(r["if"], dict) and set(r["if"]) == {"version_in"} and r["then"] is not False:
                vs += r["if"]["version_in"]
        return vs
    return []


def a01_types(ctx: Ctx, types: dict) -> str:
    bt = {}
    for name, t in types.items():
        _keys(f"types.{name}", t, {"kind", "doc", "fields"})
        entry: dict = {"kind": t["kind"]}
        if "doc" in t:
            entry["doc"] = t["doc"]
        if t["kind"] == "record":
            fields = []
            for fld in t["fields"]:
                _keys(f"types.{name}.{fld.get('name')}", fld, {"name", "width", "sol", "go"})
                lex = {k: fld[k] for k in ("go", "sol") if k in fld}
                fields.append({"name": fld["name"], "width": fld["width"], **({"lexical": lex} if lex else {})})
            entry["fields"] = fields
        elif "fields" in t:
            raise DiagramError(f"types.{name}: fields on a {t['kind']} type")
        bt[name] = entry
    ctx.d.extra["base_types"] = bt
    return f"{_plural(len(bt), 'base type')} ({', '.join(sorted(bt))}); records become product carriers"


ENC_KEYS = {"kind", "from", "to", "lang", "source", "memory_init", "domain", "length", "length_by_version", "length_code",
            "preconditions", "notes", "ops"}
DEC_KEYS = {"kind", "from", "to", "lang", "source", "meaning", "guard", "getters"}
PRED_KEYS = {"kind", "from", "to", "lang", "source", "meaning", "rules"}
PROJ_KEYS = {"kind", "from", "to", "meaning", "order", "when"}


def a01_functions(ctx: Ctx, fns: dict) -> str:
    w = F.widths(ctx.f)
    codecs, preds, projs = [], [], []
    for name, f in fns.items():
        kind = f.get("kind")
        if kind == "encoder":
            _keys(f"functions.{name}", f, ENC_KEYS)
            src = _ensure01(ctx, f["from"])
            tgt_ty, partial = _codomain(f["to"])
            tgt = _ensure01(ctx, tgt_ty)
            reads, writes, cond = [], [], []
            for op in f["ops"]:
                _keys(f"functions.{name}.ops[{op.get('offset')}]", op, {"op", "offset", "src", "code", "when"})
                n = len(F.src_cells(op["src"], w))
                F.check_op_width(name, op, n)
                key = _rng(op["offset"], n)
                writes.append((tgt.id, key))
                reads += [(src.id, item["field"]) for item in op["src"] if "field" in item]
                if "when" in op:
                    cond.append({"write": key, "when": op["when"]})
            extra = {"fn_kind": "encoder", "model_fn": MODEL_FN["CODEC"].format(name), "lang": f["lang"], "source": f["source"],
                     "memory_init": f.get("memory_init"), "conditional_writes": cond}
            for k in ("domain", "length", "length_by_version", "length_code", "preconditions", "notes"):
                if k in f:
                    extra[k] = f[k]
            codecs.append(ctx.d.add_edge(Edge(f"CODEC.{name}", "CODEC", src.id, tgt.id, name,
                                              version=_vtext(_versions(ctx, name, f)), partial=partial,
                                              reads=reads, writes=writes, extra=extra)))
        elif kind == "decoder":
            _keys(f"functions.{name}", f, DEC_KEYS)
            src = _ensure01(ctx, f["from"])
            tgt_ty, partial = _codomain(f["to"])
            tgt = _ensure01(ctx, tgt_ty)
            src.interface, src.reach = True, "external"
            if tgt.reach is None:
                tgt.reach = "image"
            reads, writes, cond = [], [], []
            for i, g in enumerate(f["getters"]):
                _keys(f"functions.{name}.getters[{i}]", g, {"name", "offset", "width", "code", "when"})
                reads.append((src.id, _rng(g["offset"], g["width"])))
                writes.append((tgt.id, str(i)))
                if "when" in g:
                    cond.append({"write": str(i), "when": g["when"]})
            extra = {"fn_kind": "decoder", "model_fn": MODEL_FN["CODEC"].format(name), "lang": f["lang"], "source": f["source"],
                     "meaning": f.get("meaning"),
                     "domain": f.get("guard"), "getters": [g["name"] for g in f["getters"]], "conditional_writes": cond}
            codecs.append(ctx.d.add_edge(Edge(f"CODEC.{name}", "CODEC", src.id, tgt.id, name,
                                              version=_vtext(_versions(ctx, name, f)), partial=partial,
                                              reads=reads, writes=writes, extra=extra)))
        elif kind == "predicate":
            _keys(f"functions.{name}", f, PRED_KEYS)
            if f["to"] != "Bool":
                raise DiagramError(f"functions.{name}: a predicate into {f['to']}")
            c = _ensure01(ctx, f["from"])
            c.interface, c.reach = True, "external"
            c.extra.setdefault("domains", []).append(name)
            c.extra["domains"].sort()
            ctx.d.extra.setdefault("predicates", {})[name] = {
                "carrier": c.id, "model_fn": MODEL_FN["CODEC"].format(name), "lang": f["lang"], "meaning": f.get("meaning"),
                "source": f["source"],
                "rules": f["rules"]}
            preds.append(name)
        elif kind == "projection":
            _keys(f"functions.{name}", f, PROJ_KEYS)
            c = _ensure01(ctx, f["from"])
            if "product" not in c.extra:
                raise DiagramError(f"functions.{name}: a projection out of {c.id}, which is not a record")
            tgt = _ensure01(ctx, f["to"])
            if tgt.reach is None:
                tgt.reach = "image"
            c.extra.setdefault("projections", []).append(
                {"id": name, "model_fn": MODEL_FN["CODEC"].format(name), "to": tgt.id, "order": f["order"],
                 "when": f.get("when", {}), "meaning": f.get("meaning")})
            projs.append((name, c.id))
        else:
            raise DiagramError(f"functions.{name}: kind {kind!r} fits no edge kind (a question for the human)")
    if not codecs:
        raise DiagramError("functions: no codec")
    iface = sorted({ctx.d.extra["predicates"][p]["carrier"] for p in preds})
    parts = [f"{_plural(len(codecs), 'CODEC edge')} ("
             + ", ".join(e.component + (" partial" if e.partial else "") for e in sorted(codecs, key=lambda e: e.id)) + ")"]
    if preds:
        parts.append(f"{_plural(len(preds), 'predicate')} as domains of interface carrier {', '.join(iface)} "
                     f"({', '.join(sorted(preds))})")
    if projs:
        parts.append(f"{_plural(len(projs), 'projection')} as product metadata of "
                     f"{', '.join(sorted({c for _, c in projs}))} ({', '.join(sorted(n for n, _ in projs))}), not edges")
    return "; ".join(parts)


def a01_assumptions(ctx: Ctx, items: list) -> str:
    recs = []
    for i, a in enumerate(items):
        _keys(f"assumptions[{i}]", a, {"id", "text"})
        links = ctx.links.get(f"/assumptions/{i}", [])
        if not links:
            ctx.d.debt("LEDGER", f"assumption {a['id']} is cited by no ledger entry", source=f"#/assumptions/{i}")
        recs.append({"id": a["id"], "text": a["text"], "ledger": links})
    ctx.d.extra["assumptions"] = recs
    linked = sum(1 for r in recs if r["ledger"])
    return f"{_plural(len(recs), 'assumption record')} with ledger links ({linked} linked)"


def post01(ctx: Ctx) -> None:
    _finish(ctx)


ADAPTERS_01 = [("target", a_target), ("extraction", a_extraction), ("types", a01_types),
               ("functions", a01_functions), ("assumptions", a01_assumptions)]


# ====================================================================== facts 0.2
class Machine:
    """What the 0.2 adapters share: state, definitions, builtin roles and shadow bases."""

    def __init__(self, ctx: Ctx):
        f = ctx.f
        self.state = [row[0] for row in f["state"]]
        self.stypes = {row[0]: row[1] for row in f["state"]}
        self.sset = set(self.state)
        self.params = set(f.get("params", {}))
        self.defs = f.get("defs", {})
        lib = Library.for_facts(ctx.path, f.get("params", {}), root=ctx.root)
        for p in lib_files(ctx.path, ctx.root):
            ctx.inputs[p.resolve().relative_to(ctx.root.resolve()).as_posix()] = _sha(p)
        self.roles = A.Roles({k: b.get("kind") for k, b in lib.builtins.items()}, f.get("shadow", {}))
        self.bases, self.base_prov, self.base_problems = A.shadow_bases(f, self.roles)

    def walker(self) -> A.Walker:
        return A.Walker(self.defs, self.roles, self.bases, self.sset)

    def scope(self, inputs=()) -> A.Scope:
        return A.Scope(self.sset, set(inputs), self.params)


def pre02(ctx: Ctx) -> None:
    for need in ("state", "actions"):
        if need not in ctx.f:
            raise DiagramError(f"facts 0.2 without {need}")
    ctx.m = Machine(ctx)


def a02_abstractions(ctx: Ctx, items: list) -> str:
    recs = []
    for i, text in enumerate(items):
        if not isinstance(text, str):
            raise DiagramError(f"abstractions[{i}] is not text")
        links = ctx.links.get(f"/abstractions/{i}", [])
        if not links:
            ctx.d.debt("LEDGER", f"abstraction {i} is cited by no ledger entry: {text}", source=f"#/abstractions/{i}")
        recs.append({"index": i, "text": text, "ledger": links})
    ctx.d.extra["abstractions"] = recs
    unlinked = sum(1 for r in recs if not r["ledger"])
    return (f"{_plural(len(recs), 'abstraction record')} with ledger links"
            + (f" ({unlinked} cited by no ledger entry: LEDGER debt)" if unlinked else ""))


def a02_params(ctx: Ctx, params: dict) -> str:
    for name, v in params.items():
        if isinstance(v, bool):
            ty = "Bool"
        elif isinstance(v, int):
            ty = "Nat"
        else:
            raise DiagramError(f"params.{name}: unmapped value {v!r}")
        ctx.d.add_carrier(Carrier(f"param.{name}", "env", ty, extra={
            "param": name, "value": v, "ledger": ctx.links.get(f"/params/{name}", [])}))
    if not params:
        return "no parameters"
    return f"{_plural(len(params), 'parameter carrier')} (env: {', '.join(sorted(params))})"


def a02_constants_doc(ctx: Ctx, docs: dict) -> str:
    for name, text in docs.items():
        if f"param.{name}" not in {c.id for c in ctx.d.carriers}:
            raise DiagramError(f"constants_doc.{name}: no such parameter")
        ctx.d.carrier(f"param.{name}").extra["lexical"] = text
    return f"lexical sources (E6) on {_plural(len(docs), 'parameter carrier')} ({', '.join(sorted(docs))})"


def a02_types(ctx: Ctx, types: dict) -> str:
    bt = {}
    for name, t in types.items():
        _keys(f"types.{name}", t, {"fields", "doc", "ghost", "doc_fields"})
        fields = [list(x) for x in t["fields"]]
        names = [x[0] for x in fields]
        for g in t.get("ghost", []):
            if g not in names:
                raise DiagramError(f"types.{name}: ghost field {g} is not a field")
        entry = {"kind": "record", "fields": fields, "ghost": list(t.get("ghost", []))}
        for k in ("doc", "doc_fields"):
            if k in t:
                entry[k] = t[k]
        bt[name] = entry
    ctx.d.extra["base_types"] = bt
    return f"{_plural(len(bt), 'record base type')} ({', '.join(sorted(bt))})" if bt else "no record types"


def a02_state(ctx: Ctx, state: list) -> str:
    m = ctx.m
    if "log" not in m.sset:
        raise DiagramError("state: a machine needs a log field")
    for row in state:
        if len(row) not in (2, 3):
            raise DiagramError(f"state: unmapped row {row}")
        name, ty = row[0], row[1]
        extra = {"component_of": "State", "doc": row[2] if len(row) == 3 else None, "ghost": False,
                 "key_space": "position" if ty.startswith("List<") else None}
        ctx.d.add_carrier(Carrier(name, "state", ty, reach="inductive", extra=extra))
        ctx.d.add_edge(Edge(f"STORE.{name}", "STORE", "State", name, name))
        ctx.d.add_edge(Edge(f"LOAD.{name}", "LOAD", name, "State", name))
    ctx.d.add_carrier(Carrier("State", "state", "State", reach="inductive", extra={"product": list(m.state)}))
    ctx.d.add_carrier(Carrier("Obs", "rep", "Obs", reach="image", extra={
        "doc": "observations: the outcome every step logs (O_Ok, or O_Rev with the failed guard's reason) and the "
               "observers' values", "revert_variants": []}))
    return (f"{_plural(len(state), 'state carrier')} under the product carrier State, with a STORE/LOAD pair per field "
            "(STORE.<field>, LOAD.<field>)")


def a02_ghost_state(ctx: Ctx, ghosts: list) -> str:
    for g in ghosts:
        if g not in ctx.m.sset:
            raise DiagramError(f"ghost_state: {g} is not a state field")
        ctx.d.carrier(g).extra["ghost"] = True
    return f"{_plural(len(ghosts), 'ghost carrier')} ({', '.join(ghosts)})" if ghosts else "no ghost state"


def a02_shadow(ctx: Ctx, shadow: dict) -> str:
    m = ctx.m
    for s, fld in shadow.items():
        if s not in m.sset:
            raise DiagramError(f"shadow: {s} is not a state field")
        c = ctx.d.carrier(s)
        c.extra["residue_of"] = fld
        if s in m.bases:
            c.extra["key_space"] = "slot"
            c.extra["slot_base"] = m.bases[s].text()
            c.extra["slot_base_from"] = m.base_prov[s]
    for p in m.base_problems:
        ctx.d.debt("SHADOW", p)
    bases = sorted({m.bases[s].text() for s in shadow if s in m.bases})
    return (f"{_plural(len(shadow), 'residue carrier')} ({', '.join(shadow)}), keyed by absolute slot from base "
            f"{', '.join(bases) or 'none'}")


def a02_initial(ctx: Ctx, init: dict) -> str:
    sets = sorted(k for k in init if k != "doc")
    missing, extra = sorted(ctx.m.sset - set(sets)), sorted(set(sets) - ctx.m.sset)
    if missing or extra:
        raise DiagramError(f"initial: missing {missing}, unknown {extra}")
    ctx.d.carrier("State").extra["initial"] = {"doc": init.get("doc"), "sets": sets, "pointer": "#/initial"}
    return "S0: the initial state, generating Reach on carrier State"


def a02_principals(ctx: Ctx, ps: dict) -> str:
    ctx.d.extra["principals"] = [{"id": int(k), "name": v} for k, v in sorted(ps.items(), key=lambda kv: int(kv[0]))]
    return (f"{_plural(len(ps), 'concrete principal')} (Π instances); the classes come from the actions' guards"
            if ps else "no concrete principals; the classes come from the actions")


def a02_reasons(ctx: Ctx, rs: dict) -> str:
    ctx.d.carrier("Obs").extra["revert_variants"] = [{"code": int(k), "reason": v}
                                                     for k, v in sorted(rs.items(), key=lambda kv: int(kv[0]))]
    return f"{_plural(len(rs), 'revert variant')} of carrier Obs (O_Rev codes)" if rs else "no revert variants"


def a02_defs(ctx: Ctx, defs: dict) -> str:
    out = {}
    for name, d in defs.items():
        _keys(f"defs.{name}", d, {"params", "type", "body", "doc", "src", "ghost"})
        out[name] = {"sha256": hashlib.sha256(canonical_json(d)).hexdigest(), "params": [list(p) for p in d["params"]],
                     "type": d["type"], "ghost": bool(d.get("ghost", False)), "body": A.render(d["body"], defs)}
    ctx.d.extra["defs"] = out
    return f"{_plural(len(out), 'content-hashed definition')}, attached to the edges whose expressions reach them" \
        if out else "no definitions"


ACTION_KEYS = {"name", "src", "principal", "inputs", "guards", "effects", "effects_src"}
GUARD_KEYS = {"let", "expr", "require", "reason", "src", "note", "site"}


def a02_actions(ctx: Ctx, actions: list) -> str:
    m = ctx.m
    try:
        classes, of, problems = principal_classes(ctx.f, m.walker)
    except (PrincipalError, A.AccessError) as e:
        raise DiagramError(f"actions (principal classes): {e}") from e
    for p in problems:
        ctx.d.debt("PRINCIPAL", p)
    ctx.d.principal_classes = classes
    cls = {c["id"]: c for c in classes}
    variants = {}
    for a in actions:
        _keys(f"actions.{a.get('name')}", a, ACTION_KEYS)
        name = a["name"]
        inputs = [list(x) for x in a["inputs"]]
        variants[name] = inputs
        w = m.walker()
        sc = m.scope(n for n, _ in inputs)
        guards, reverts = [], []
        try:
            for i, g in enumerate(a["guards"]):
                _keys(f"actions.{name}.guards[{i}]", g, GUARD_KEYS)
                if "let" in g:
                    w.read(g["expr"], sc)
                    sc.local[g["let"]] = sc.resolve(g["expr"])
                    item = {"let": g["let"], "expr": A.render(g["expr"], m.defs)}
                elif "require" in g:
                    w.read(g["require"], sc)
                    item = {"require": A.render(g["require"], m.defs), "reason": g["reason"]}
                    reverts.append(g["reason"])
                else:
                    raise DiagramError(f"actions.{name}.guards[{i}]: neither let nor require")
                for k in ("src", "note", "site"):
                    if k in g:
                        item[k] = g[k]
                guards.append(item)
            for fld, e in a["effects"].items():
                if fld not in m.sset or fld == "log":
                    raise DiagramError(f"actions.{name}: effect on {fld}, which is not a writable state field")
                w.write(fld, e, sc)
        except A.AccessError as e:
            raise DiagramError(f"actions.{name}: {e}") from e
        c = cls[of[name]]
        extra = {"source": a.get("src"), "label": a["principal"], "inputs": inputs,
                 "caller": CALLER if any(n == CALLER for n, _ in inputs) else None,
                 "guards": guards, "reverts": sorted(set(reverts)),
                 "effects": {k: A.render(v, m.defs) for k, v in a["effects"].items()},
                 "defs": sorted(w.defs_used), "permissionless": c["permissionless"], "cost": 0, "delay": None,
                 "model_fn": MODEL_FN["TRANS"].format(name)}
        if "effects_src" in a:
            extra["effects_src"] = a["effects_src"]
        ctx.d.add_edge(Edge(f"TRANS.{name}", "TRANS", "State", "State", name, principal_class=c["id"],
                            env=c["id"] == ENVIRONMENT, reads=sorted(w.reads),
                            writes=sorted(w.writes | A.step_writes()), extra=extra))
    ctx.d.add_carrier(Carrier("Act", "rep", "Act", interface=True, reach="external", extra={
        "doc": "the actions' inputs: everything any principal can submit (R^ext is the full input type)",
        "variants": variants}))
    envs = sorted(a["name"] for a in actions if of[a["name"]] == ENVIRONMENT)
    return (f"{_plural(len(actions), 'TRANS edge')} with index-sensitive read/write sets"
            + (f" ({_plural(len(envs), 'environment edge')}: {', '.join(envs)})" if envs else "")
            + f"; {_plural(len(classes), 'principal class')} ({', '.join(c['id'] for c in classes)})")


def a02_migrations(ctx: Ctx, migs: dict) -> str:
    m = ctx.m
    pseudo = []
    for name, g in migs.items():
        _keys(f"migrations.{name}", g, {"doc", "src", "inputs", "effects"})
        inputs = [list(x) for x in g.get("inputs", [])]
        w, sc = m.walker(), m.scope(n for n, _ in inputs)
        try:
            for fld, e in g["effects"].items():
                if fld not in m.sset or fld == "log":
                    raise DiagramError(f"migrations.{name}: effect on {fld}, which is not a writable state field")
                w.write(fld, e, sc)
        except A.AccessError as e:
            raise DiagramError(f"migrations.{name}: {e}") from e
        is_pseudo = "src" not in g  # no code realises it: a modelling device (e.g. state as an older version wrote it)
        if is_pseudo:
            pseudo.append(name)
        ctx.d.add_edge(Edge(f"MIG.{name}", "MIG", "State", "State", name, pseudo=is_pseudo, reads=sorted(w.reads),
                            writes=sorted(w.writes), extra={
                                "doc": g.get("doc"), "source": g.get("src"), "inputs": inputs,
                                "effects": {k: A.render(v, m.defs) for k, v in g["effects"].items()},
                                "defs": sorted(w.defs_used), "ledger": ctx.links.get(f"/migrations/{name}", []),
                                "model_fn": MODEL_FN["MIG"].format(name)}))
    return (f"{_plural(len(migs), 'MIG edge')}"
            + (f" ({_plural(len(pseudo), 'pseudo-migration')}, no code source: {', '.join(sorted(pseudo))})" if pseudo else ""))


def a02_observers(ctx: Ctx, obs: dict) -> str:
    m = ctx.m
    for name, o in obs.items():
        _keys(f"observers.{name}", o, {"params", "type", "body", "doc"})
        if [list(p) for p in o["params"]] != [["s", "State"]]:
            raise DiagramError(f"observers.{name}: unmapped parameters {o['params']}")
        w = m.walker()
        try:
            w.read(o["body"], m.scope())
        except A.AccessError as e:
            raise DiagramError(f"observers.{name}: {e}") from e
        ctx.d.add_edge(Edge(f"LOAD.obs.{name}", "LOAD", "State", "Obs", name, reads=sorted(w.reads), extra={
            "observer": True, "model_fn": MODEL_FN["observer"].format(name), "type": o["type"],
            "body": A.render(o["body"], m.defs), "doc": o.get("doc"),
            "defs": sorted(w.defs_used)}))
    return f"{_plural(len(obs), 'observation LOAD edge')} into Obs (LOAD.obs.<name>)"


def a02_disch(ctx: Ctx, disch: dict) -> str:
    _keys("disch", disch, {"doc", "cost", "cost_doc", "delay"})
    trans = {e.component: e for e in ctx.d.edges if e.kind == "TRANS"}
    for a, c in disch.get("cost", {}).items():
        if a not in trans:
            raise DiagramError(f"disch.cost: {a} is not an action")
        trans[a].extra["cost"] = c
    delay = disch.get("delay")
    if delay:
        _keys("disch.delay", delay, {"action", "input"})
        e = trans.get(delay["action"])
        if e is None or delay["input"] not in [n for n, _ in e.extra["inputs"]]:
            raise DiagramError(f"disch.delay: {delay} names no action input")
        e.extra["delay"] = delay["input"]
    ctx.d.extra["disch"] = {k: disch[k] for k in sorted(disch)}
    priced = sorted(a for a in disch.get("cost", {}))
    return (f"DISCH metadata: cost terms on {_plural(len(priced), 'TRANS edge')} ({', '.join(priced)})"
            + (f", delay input {delay['input']} of {delay['action']}" if delay else "")
            + "; permissionless class and guard annotations on every TRANS edge")


def a02_consumers(ctx: Ctx, cons: dict) -> str:
    for name, c in cons.items():
        _keys(f"consumers.{name}", c, {"doc", "input"})
        acts = sorted(e.component for e in ctx.d.edges if e.kind == "TRANS"
                      and any(n == c["input"] for n, _ in e.extra["inputs"]))
        types = sorted({t for e in ctx.d.edges if e.kind == "TRANS" for n, t in e.extra["inputs"] if n == c["input"]})
        if not acts or len(types) != 1:
            raise DiagramError(f"consumers.{name}: input {c['input']} has types {types} in actions {acts}")
        ctx.d.add_carrier(Carrier(f"out.{name}", "rep", types[0], reach="image", extra={"consumer": name}))
        ctx.d.add_edge(Edge(f"CONS.{name}", "CONS", "Act", f"out.{name}", name, reads=[("Act", c["input"])], extra={
            "input": c["input"], "from_actions": acts, "doc": c.get("doc"), "model_fn": MODEL_FN["CONS"].format(name)}))
    return f"{_plural(len(cons), 'CONS edge')} ({', '.join(sorted(cons))})" if cons else "no consumers"


def a02_coverage(ctx: Ctx, cov: dict) -> str:
    _keys("coverage", cov, {"modelled", "debt"})
    for i, item in enumerate(cov.get("debt", [])):
        ctx.d.debt("UNMODELLED", item, source=f"#/coverage/debt/{i}")
    ctx.d.extra["coverage"] = {"modelled": list(cov.get("modelled", []))}
    return (f"{_plural(len(cov.get('debt', [])), 'coverage-debt entry')} (UNMODELLED); "
            f"{len(cov.get('modelled', []))} modelled components listed")


def a02_policy(ctx: Ctx, policy) -> str:
    ctx.d.extra.setdefault("explorer", {})["policy"] = policy
    return "explorer.policy: the search-hint policy the refuter uses (configuration, not part of 𝔇)"


def a02_search(ctx: Ctx, search: dict) -> str:
    ctx.d.extra.setdefault("explorer", {})["search"] = search
    return "explorer.search: bounds of the refuter's prefix search (configuration, not part of 𝔇)"


def post02(ctx: Ctx) -> None:
    m = ctx.m
    d = ctx.d
    movers = [e for e in d.edges if e.kind in ("TRANS", "MIG")]
    readers = movers + [e for e in d.edges if e.kind == "LOAD" and e.extra.get("observer")]
    for f in m.state:
        st, ld = next(e for e in d.edges if e.id == f"STORE.{f}"), next(e for e in d.edges if e.id == f"LOAD.{f}")
        ws = [e for e in movers if any(c == f for c, _ in e.writes)]
        rs = [e for e in readers if any(c == f for c, _ in e.reads)]
        st.writes = sorted({(c, k) for e in ws for c, k in e.writes if c == f})
        st.extra = {"writers": sorted(e.id for e in ws), "initial": True, "model_fn": None}
        ld.reads = sorted({(c, k) for e in rs for c, k in e.reads if c == f})
        ld.extra = {"readers": sorted(e.id for e in rs), "model_fn": None}
        tw = [e for e in ws if e.kind == "TRANS"]
        if tw and all(e.env for e in tw) and not [e for e in ws if e.kind != "TRANS"]:
            d.carrier(f).cls = "env"  # only the environment moves it (time)
    for name in sorted(m.roles.opaque_used):
        d.debt("ACCESS", f"library builtin {name} declares no access kind: every state field passed to it is "
                         "accessed whole (*)")
    _finish(ctx)


ADAPTERS_02 = [("target", a_target), ("extraction", a_extraction), ("abstractions", a02_abstractions),
               ("params", a02_params), ("constants_doc", a02_constants_doc), ("types", a02_types),
               ("state", a02_state), ("ghost_state", a02_ghost_state), ("shadow", a02_shadow),
               ("initial", a02_initial), ("reasons", a02_reasons), ("defs", a02_defs),
               ("actions", a02_actions), ("principals", a02_principals), ("migrations", a02_migrations),
               ("observers", a02_observers), ("consumers", a02_consumers), ("disch", a02_disch),
               ("coverage", a02_coverage), ("policy", a02_policy), ("search", a02_search)]

VERSIONS = {"holon-facts/0.1": (None, ADAPTERS_01, post01), "holon-facts/0.2": (pre02, ADAPTERS_02, post02)}


# ====================================================================== entry points
def build(path: Path | str, root: Path | str = ROOT) -> Diagram:
    root, path = Path(root), Path(path)
    facts = json.loads(path.read_text(encoding="utf-8"))
    version = facts.get("facts_version")
    if version not in VERSIONS:
        raise DiagramError(f"{path}: facts_version {version!r} has no adapters")
    pre, table, post = VERSIONS[version]
    unmapped = sorted(set(facts) - {"facts_version"} - {s for s, _ in table})
    if unmapped:
        raise DiagramError(f"{path}: unmapped facts sections {unmapped}")
    ctx = Ctx(facts, path, root)
    try:
        if pre:
            pre(ctx)
        for section, fn in table:
            if section in facts:
                ctx.d.mapped_sections[section] = fn(ctx, facts[section])
        post(ctx)
    except (KeyError, TypeError) as e:
        raise DiagramError(f"{path}: malformed facts ({type(e).__name__}: {e})") from e
    return ctx.d
