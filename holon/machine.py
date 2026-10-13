"""The extracted model: holon-facts/0.3 transitions documents compiled to a raw-storage model (I20; whitepaper §8.7,
§10.1 translators, Def 4.7; BUILD_PLAN I20). The contract is the docstring of tests_m2/test_extracted_refinement.py,
clauses 1, 7 and 10.

  load_extracted(doc_path, root=None, source=None, info=None) -> ExtractedModel
  python -m holon model --facts <transitions document> --out DIR      (holon.mpipeline.main_model dispatches here)

The document (holon.frontends.solidity.transitions, I19, extended additively by the I19 follow-up A19; its module
docstring and spec/schemas/facts_0_3.schema.json are the format). This module is the one place that reads a document's
sections; every other I20 module (holon.extracted_eval, holon.machine_bend, holon.window, holon.differential,
holon.sorts.width, holon.fragments_doc) goes through it. FORMAT names every key read:
  document  "storage" (fields with "slot", "offset"), "inherited_storage" [{name, slot, offset, kind, .., declared_in}]
            (a name declared by two contracts, e.g. "__gap", is the family "<declared_in>.<name>");
  action    "params" [{name, type, width, location, fields}], "payable", "mutability", "returns", "declared_in";
            "guards" [{src, kind, reason, error?: {name, signature, selector}, args?, reaches: [{seq, stack, expr,
                      loop?, code?, args?}]}] (every reach; its own revert data args, an assert's code 1);
            "checks" [{seq, src, stack, kind: callvalue|calldatasize|abi|slice|uncaught, expr, param?, loop?}];
            "panics" [{seq, src, stack, code, op, args, expr, loop?}] (checked operations: Panic codes);
            "calls" [{seq, src, stack, fn, receiver, args, value, mutability, cond, commit, try, expr, loop?}] (a call
                     whose expr is not 1 is a check: a failing call bubbles its revert data);
            "writes" [{seq, src, stack, family, path: [[map|index|member, key]..], value, cond, loop?}];
            "mstores" [{seq, src, stack, region, op, offset, value, cond, loop?}];
            "events" [{seq, src, stack, event, signature, topic0, args, indexed, topics, anonymous, cond, loop?}];
            "loops" [{seq, src, stack, kind, cond, carried: [{name, entry, value}], regions, head, next: [{name,
                     value}], break, at_break: [{name, value}], returns: [{cond, value}], count, bound, exit: [{name,
                     value}], steps: [seq..], loop?}];
            "order" (the checks in walk order) and "post" (the families after the action) are not needed here: every
            record carries "seq", the walk-order counter shared by the records of an action.
  A record made in a loop's generic iteration carries "loop", the seq of the innermost loop record; that loop's
  "steps" lists exactly those records. The program of an action is its records without "loop" in seq order, a loop
  record holding its own records (its body) in seq order. A loop's terms name it by its span, plus its reach index
  r (the number of earlier loop records of the same span in the action) as a last element when r > 0.

Checks. Every guard reach, implicit check (checks, panics) and external-call check is one Check. Its id is
"<action>#<span>#<k>": span is the record's src, k counts the checks of that span in the action in walk (seq) order,
loop bodies included. The transaction reverts at the first check whose condition is 0 (holon.extracted_eval).

What the model reads from the compiler (the document leaves it to solc): the storage layout of the contract (types,
inherited storage), the ABI of every action and of every interface function a call term names, and the selectors of
custom errors and events. It is compiled through the extraction's own provenance (the sidecar extraction.sidecar.path,
which must still hash to extraction.sidecar.sha256, with the pinned solc; every unit solc reads must hash to the
document's extraction.inputs), cached under holon.bend.build_dir()/extracted/ by (document sha256, sidecar sha256).
A family the document declares must sit at the compiler's slot and offset; a family a term reads that the document does
not declare is resolved in the compiler's layout (inherited storage, e.g. _owner, _paused), never by counting slots;
"inherited_storage", when the document has it, must agree with the layout too.

`python -m holon model --facts DOC --out DIR` writes DIR/model.bend (holon.machine_bend: the raw families, per action
the decision over its checks and the post-state of its writes; Bend checks it, no escape hatch), DIR/layout.json (the
resolved families) and, when a window declaration names the document (holon.window), DIR/window_check.json. Outputs
are canonical and byte-identical across runs (clause 10).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTS_VERSION = "holon-facts/0.3"
KIND = "transitions"
INFO_VERSION = "holon-extracted-info/0.2"
MACHINE_VERSION = "holon-machine-extracted/0.1"
WORD = 1 << 256
MASK = WORD - 1

# Every key of the A19 document this module reads (holon.frontends.solidity.transitions; the schema
# spec/schemas/facts_0_3.schema.json): one table, so that a rename of the format is one edit here.
FORMAT = {
    "inherited_storage": "inherited_storage", "params": "params", "payable": "payable", "mutability": "mutability",
    "returns": "returns", "declared_in": "declared_in", "reaches": "reaches", "panics": "panics", "calls": "calls",
    "checks": "checks", "writes": "writes", "mstores": "mstores", "events": "events", "loops": "loops",
    "post": "post", "seq": "seq", "steps": "steps", "loop": "loop", "order": "order",
}
# the sections of an action that hold program records (every record carries a seq unique in the action)
SECTIONS = ("checks", "panics", "calls", "guards", "loops", "writes", "mstores", "events")
A19_KEYS = ("panics", "calls", "checks", "writes", "mstores", "events", "loops")
CHECK_KINDS = ("callvalue", "calldatasize", "abi", "slice", "uncaught")


class ModelError(ValueError):
    """A document the extracted model cannot be built from (named)."""


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def canonical(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def is_transitions(doc) -> bool:
    return (isinstance(doc, dict) and doc.get("facts_version") == FACTS_VERSION
            and (doc.get("extraction") or {}).get("kind") == KIND)


# ------------------------------------------------------------------------------------------------ the compiler's view
def _node_index(asts: dict) -> dict:
    out = {}
    stack = list(asts.values())
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            if isinstance(x.get("id"), int) and "nodeType" in x:
                out[x["id"]] = x
            stack.extend(x.values())
        elif isinstance(x, list):
            stack.extend(x)
    return out


def _strip_location(ts: str) -> str:
    return re.sub(r"\s+(calldata|memory|storage( pointer| ref)?)$", "", ts.strip())


def abi_type(tn: dict, ix: dict) -> dict:
    """The ABI shape of a type name node: {"type", "components"?} (structs are tuples, enums uint8, contracts
    address)."""
    nt = tn.get("nodeType")
    if nt == "ArrayTypeName":
        base = abi_type(tn["baseType"], ix)
        ln = tn.get("length")
        n = ""
        if isinstance(ln, dict):
            n = str(ln.get("value") or (ln.get("typeDescriptions") or {}).get("typeString", "").split(" ")[-1])
        out = dict(base)
        out["type"] = base["type"] + f"[{n}]"
        return out
    if nt == "UserDefinedTypeName":
        ref = ix.get(tn.get("referencedDeclaration"))
        rt = (ref or {}).get("nodeType")
        if rt == "StructDefinition":
            return {"type": "tuple", "struct": ref.get("canonicalName") or ref.get("name"),
                    "components": [dict(abi_type(m["typeName"], ix), name=m["name"]) for m in ref.get("members") or []]}
        if rt == "EnumDefinition":
            return {"type": "uint8", "enum": len(ref.get("members") or [])}
        if rt == "ContractDefinition":
            return {"type": "address"}
        if rt == "UserDefinedValueTypeDefinition":
            return abi_type(ref["underlyingType"], ix)
        raise ModelError(f"type {tn.get('typeDescriptions')}: unresolved user-defined type")
    if nt == "FunctionTypeName":
        return {"type": "function"}
    ts = _strip_location((tn.get("typeDescriptions") or {}).get("typeString") or tn.get("name") or "")
    ts = ts.replace("address payable", "address")
    if ts == "byte":
        ts = "bytes1"
    if ts in ("uint", "int"):
        ts += "256"
    return {"type": ts}


def _params(plist: dict, ix: dict) -> list[dict]:
    out = []
    for p in (plist or {}).get("parameters") or []:
        d = abi_type(p["typeName"], ix) if p.get("typeName") else {"type": _strip_location(
            (p.get("typeDescriptions") or {}).get("typeString", ""))}
        d = dict(d, name=p.get("name") or "")
        if "indexed" in p:
            d["indexed"] = bool(p["indexed"])
        out.append(d)
    return out


def compiler_info(asts: dict, layouts: dict, contract: str) -> dict:
    """What the model reads from the compiler for `contract`: its full storage layout, the ABI of its external and
    public functions (by selector), of every interface or contract function (by "<Contract>.<function>"), and the
    custom errors and events declared anywhere in the compiled units (by name, every overload)."""
    ix = _node_index(asts)
    hits = [(u, n) for (u, n) in sorted(layouts) if n == contract]
    if len(hits) != 1:
        raise ModelError(f"contract {contract}: {len(hits)} storage layouts in the compiler's output (want 1)")
    lay = layouts[hits[0]]
    functions: dict = {}
    members: dict = {}
    errors: dict = {}
    events: dict = {}
    for unit in sorted(asts):
        for c in asts[unit].get("nodes") or []:
            if c.get("nodeType") == "ErrorDefinition":
                errors.setdefault(c["name"], []).append({"selector": "0x" + c.get("errorSelector", ""),
                                                         "params": _params(c.get("parameters"), ix)})
            if c.get("nodeType") != "ContractDefinition":
                continue
            for n in c.get("nodes") or []:
                nt = n.get("nodeType")
                if nt == "FunctionDefinition" and n.get("kind") in ("function", "receive", "fallback"):
                    entry = {"name": n.get("name") or n.get("kind"), "kind": n.get("kind"),
                             "visibility": n.get("visibility"), "mutability": n.get("stateMutability"),
                             "selector": ("0x" + n["functionSelector"]) if n.get("functionSelector") else None,
                             "inputs": _params(n.get("parameters"), ix),
                             "outputs": _params(n.get("returnParameters"), ix)}
                    members.setdefault(f"{c['name']}.{entry['name']}", []).append(entry)
                    if n.get("visibility") in ("external", "public"):
                        key = entry["selector"] or entry["kind"]
                        functions.setdefault(c["name"], {})[key] = entry
                elif nt == "ErrorDefinition":
                    errors.setdefault(n["name"], []).append({"selector": "0x" + n.get("errorSelector", ""),
                                                             "params": _params(n.get("parameters"), ix)})
                elif nt == "EventDefinition":
                    events.setdefault(n["name"], []).append({"selector": "0x" + n.get("eventSelector", ""),
                                                             "anonymous": bool(n.get("anonymous")),
                                                             "params": _params(n.get("parameters"), ix)})
    for d in (errors, events):
        for k in d:
            uniq = []
            for x in d[k]:
                if x not in uniq:
                    uniq.append(x)
            d[k] = sorted(uniq, key=lambda x: x["selector"])
    # the contract's own external/public functions over its linearization, most derived first (an override wins)
    cdefs = [n for n in ix.values() if n.get("nodeType") == "ContractDefinition" and n.get("name") == contract]
    lin = [ix[i]["name"] for i in (cdefs[0].get("linearizedBaseContracts") or []) if i in ix] if len(cdefs) == 1 else [contract]
    own: dict = {}
    for cname in lin:
        for key, entry in sorted((functions.get(cname) or {}).items()):
            own.setdefault(key, dict(entry, declared_in=cname))
    # the immutables and constants of the contract over its linearization (most derived first): their declared ABI
    # types (an ["immutable", name] term's width, e.g. inside abi.encodePacked)
    immutables: dict = {}
    for cname in lin:
        for c in cdefs if cname == contract else [n for n in ix.values() if n.get("nodeType") == "ContractDefinition"
                                                  and n.get("name") == cname]:
            for n in c.get("nodes") or []:
                if n.get("nodeType") == "VariableDeclaration" and n.get("mutability") in ("immutable", "constant") \
                        and n.get("typeName"):
                    immutables.setdefault(n["name"], abi_type(n["typeName"], ix))
    return {"info_version": INFO_VERSION, "contract": contract, "unit": hits[0][0], "linearization": lin,
            "layout": {"storage": [{k: s[k] for k in ("label", "slot", "offset", "type", "contract")}
                                   for s in lay.get("storage") or []],
                       "types": lay.get("types") or {}},
            "functions": own, "members": members, "errors": errors, "events": events,
            "immutables": dict(sorted(immutables.items()))}


def _cache_dir(root: Path) -> Path:
    from .bend import build_dir
    return build_dir(root) / "extracted"


def toolchain_info(doc: dict, doc_sha: str, root: Path, source=None) -> dict:
    """compiler_info for the document's contract, compiled through the extraction's provenance (module docstring).
    Cached by (document sha256, sidecar sha256)."""
    from .frontends import Refused, ExtractionError, load_sidecar
    from .frontends.solidity import compile as comp
    ext = doc.get("extraction") or {}
    side_ref = ext.get("sidecar") or {}
    rel = side_ref.get("path")
    if not isinstance(rel, str) or rel.startswith("<outside>"):
        raise ModelError(f"the document's extraction names no sidecar inside the repository ({rel!r}); pass info=")
    sp = Path(root) / rel
    if not sp.is_file():
        raise ModelError(f"the extraction's sidecar {rel} does not exist")
    got = sha256_bytes(sp.read_bytes())
    if got != side_ref.get("sha256"):
        raise ModelError(f"the extraction's sidecar {rel} hashes to {got}, the document records {side_ref.get('sha256')}")
    cache = _cache_dir(root) / f"{doc_sha[:16]}-{got[:8]}.json"
    if cache.is_file():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("info_version") == INFO_VERSION:
                return data
        except ValueError:
            pass
    side = load_sidecar(sp)
    cfg = comp.load_config(root)
    if source is None:
        source = ((cfg.get("extract") or {}).get("sources") or {}).get((side.get("target") or {}).get("repo"))
        if not source:
            raise ModelError(f"no source tree for {(side.get('target') or {}).get('repo')!r}: pass source=")
    try:
        compiled = comp.compile_sources(cfg, side, Path(os.path.abspath(source)), storage_layout=True)
    except (Refused, ExtractionError) as e:
        raise ModelError(f"the extraction's compile failed: {e}") from e
    want = {i["unit"]: i["sha256"] for i in ext.get("inputs") or []}
    have = {u: sha256_bytes(b) for u, b in compiled.units.items()}
    bad = sorted(u for u in set(want) | set(have) if want.get(u) != have.get(u))
    if bad:
        raise ModelError("the compiled units are not the document's extraction inputs: " + ", ".join(bad[:8]))
    info = compiler_info(compiled.asts, compiled.layouts, doc.get("contract"))
    info["provenance"] = {"sidecar": rel, "sidecar_sha256": got, "solc": compiled.version,
                          "solc_sha256": compiled.solc_sha256}
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_name(cache.name + f".{os.getpid()}.tmp")
    tmp.write_text(dumps(info), encoding="utf-8")
    os.replace(tmp, cache)
    return info


# ------------------------------------------------------------------------------------------------ program records
@dataclass
class Family:
    """A state variable: a family the document declares, or inherited storage a term or write names."""
    name: str
    slot: int
    offset: int
    type: str                 # solc storage-layout type id
    declared: bool            # in the document's own storage list (False: inherited)
    contract: str = ""


@dataclass
class Check:
    """A guard reach, an implicit check (checks, panics) or an external-call check (module docstring)."""
    id: str
    action: str
    span: str                 # the record's src
    src: object
    kind: str                 # require | modifier | revert | panic | call | callvalue | calldatasize | abi | slice | uncaught
    reason: object
    expr: object
    code: object = None       # a Panic code (a panic record, or an assert's reach: 1)
    seq: object = None
    stack: object = None
    section: str = "guards"
    entry: dict = field(default_factory=dict)     # the guard entry (guards) or the record itself
    loop: object = None       # the span of the innermost loop record holding it
    error: object = None      # a guard's revert data: {name, signature, selector} (the document's), else None
    args: object = None       # that reach's revert data arguments (terms), else None
    reach: dict = field(default_factory=dict)     # the guard reach record itself (guards), else the record


@dataclass
class Write:
    seq: object
    src: object
    stack: object
    family: str
    path: list
    value: object
    cond: object
    entry: dict = field(default_factory=dict)


@dataclass
class MStore:
    seq: object
    src: object
    stack: object
    region: object
    op: str
    offset: object
    value: object
    cond: object
    entry: dict = field(default_factory=dict)


@dataclass
class Event:
    seq: object
    src: object
    stack: object
    event: str
    signature: object
    topic0: object
    args: list
    indexed: list
    anonymous: bool
    cond: object
    topics: list = field(default_factory=list)    # the indexed arguments' topic terms (after topic0)
    entry: dict = field(default_factory=dict)


@dataclass
class Loop:
    seq: object
    src: str
    stack: object
    kind: str
    cond: object
    carried: list            # [(name, entry term, value term)]
    head: object
    next: list               # [(name, value term)]
    brk: object
    at_break: list           # [(name, value term)]
    count: object
    body: list               # program records of one generic iteration, in seq order
    entry: dict = field(default_factory=dict)
    reach: int = 0           # the loop's reach index r in the action (its terms carry r as a last element when r > 0)
    exits: list = field(default_factory=list)     # [(name, value term)]: the names' values after the loop
    returns: list = field(default_factory=list)   # [(cond term, value term)]: the iteration's return paths

    def sym(self, tag: str, *rest) -> list:
        """The term [tag, span, *rest] (+ [r] when r > 0) that names this loop's symbols (iter, carried, exit, count,
        returned)."""
        return [tag, self.src, *rest] + ([self.reach] if self.reach else [])


@dataclass
class Program:
    """An action's records in program order (module docstring)."""
    action: str
    steps: list

    def checks(self) -> list[Check]:
        out = []

        def walk(xs):
            for x in xs:
                if isinstance(x, Check):
                    out.append(x)
                elif isinstance(x, Loop):
                    walk(x.body)
        walk(self.steps)
        return out

    def records(self, kind) -> list:
        out = []

        def walk(xs):
            for x in xs:
                if isinstance(x, kind):
                    out.append(x)
                if isinstance(x, Loop):
                    walk(x.body)
        walk(self.steps)
        return out


def _records(a: dict) -> list[tuple[str, dict]]:
    """(section, record) of every record of an action's sections (a guard entry once; its reaches are its records)."""
    out = []
    for sec in SECTIONS:
        for r in a.get(FORMAT.get(sec, sec)) or []:
            if isinstance(r, dict):
                out.append((sec, r))
    return out


def _pairs(xs, key: str = "value") -> list:
    out = []
    for x in xs or []:
        if isinstance(x, dict):
            out.append((x.get("name"), x.get(key)))
        elif isinstance(x, list) and len(x) == 2:
            out.append((x[0], x[1]))
    return out


_SPAN_RX = re.compile(r"^(?P<u>\S+?\.\w+):(?P<lo>\d+)(?:-(?P<hi>\d+))?")


def source_span(src) -> tuple[str, int, int] | None:
    """(unit, lo, hi) of a source span "<unit>:<lo>[-<hi>]" (anything may follow it); None otherwise."""
    if not isinstance(src, str):
        return None
    m = _SPAN_RX.match(src.strip())
    if not m:
        return None
    lo = int(m["lo"])
    return m["u"], lo, int(m["hi"] or lo)


def spans_overlap(a, b) -> bool:
    """Two source spans of one unit whose line ranges intersect."""
    return bool(a and b and a[0] == b[0] and a[1] <= b[2] and b[1] <= a[2])


def _label(name) -> str:
    """A carried name as text: a local's name, or "storage.<family>" for ["storage", family]."""
    if isinstance(name, list) and len(name) == 2 and name[0] == "storage":
        return f"storage.{name[1]}"
    return name if isinstance(name, str) else canonical(name)


def call_is_check(rec: dict) -> bool:
    """A call record whose failure reverts (its expr is not 1): a check (A19 "order" lists exactly these)."""
    return "expr" in rec and rec.get("expr") != 1


# ------------------------------------------------------------------------------------------------ programs
def is_a19(a: dict) -> bool:
    """An action of the I19 follow-up's shape: every section present and every guard with its reaches."""
    return all(FORMAT[k] in a for k in A19_KEYS) and all(
        isinstance(g, dict) and isinstance(g.get(FORMAT["reaches"]), list) and g[FORMAT["reaches"]]
        for g in a.get("guards") or [])


def build_program(a: dict) -> Program:
    """The action's records in program order, with check ids (module docstring). Needs no compiler information."""
    action = a["name"]
    if not is_a19(a):
        raise ModelError(f"{action}: not an action of the I19 follow-up's document (holon-frontend-solidity/0.3: "
                         f"sections {', '.join(A19_KEYS)} and every guard's reaches); re-extract the document")
    SEQ, LOOP = FORMAT["seq"], FORMAT["loop"]
    raw = []    # (section, record, parent)
    for sec, r in _records(a):
        if sec == "guards":
            for x in r[FORMAT["reaches"]]:
                raw.append((sec, x, r))
        elif sec == "calls" and not call_is_check(r):
            raw.append(("calls_free", r, r))   # a call whose failure is a value: no check
        else:
            raw.append((sec, r, r))
    for sec, r, _ in raw:
        if not isinstance(r.get(SEQ), int) or isinstance(r.get(SEQ), bool):
            raise ModelError(f"{action}: a {sec} record without an integer seq ({canonical(r)[:160]})")
    seqs = [r[SEQ] for _, r, _ in raw]
    if len(set(seqs)) != len(seqs):
        raise ModelError(f"{action}: two records share seq {sorted({s for s in seqs if seqs.count(s) > 1})[:4]}")
    raw.sort(key=lambda x: x[1][SEQ])
    loops = {r[SEQ]: r for sec, r, _ in raw if sec == "loops"}
    children: dict = {}
    for sec, r, _ in raw:
        lp = r.get(LOOP)
        if lp is not None and lp not in loops:
            raise ModelError(f"{action}: record seq {r[SEQ]} names loop seq {lp}, which is not a loop record")
        children.setdefault(lp, []).append(r[SEQ])
    for s, lr in loops.items():
        steps = lr.get(FORMAT["steps"])
        if isinstance(steps, list) and sorted(steps) != sorted(children.get(s, [])):
            raise ModelError(f"{action}: loop seq {s} lists steps {sorted(steps)[:8]}, its records are "
                             f"{sorted(children.get(s, []))[:8]}")
    # check ids and loop reach indexes, in walk (seq) order
    counts: dict = {}
    ids: dict = {}
    reach_of: dict = {}
    nloop: dict = {}
    for sec, r, parent in raw:
        if sec in ("guards", "panics", "calls", "checks"):
            span = (parent if sec == "guards" else r).get("src") or sec
            k = counts.get(span, 0)
            counts[span] = k + 1
            ids[r[SEQ]] = f"{action}#{span}#{k}"
        elif sec == "loops":
            k = nloop.get(r.get("src"), 0)
            nloop[r.get("src")] = k + 1
            reach_of[r[SEQ]] = k
    by_seq = {r[SEQ]: (sec, r, parent) for sec, r, parent in raw}

    def make(seq: int, loop_span):
        sec, r, parent = by_seq[seq]
        if sec == "guards":
            span = parent.get("src") or sec
            return Check(ids[seq], action, span, parent.get("src"), parent.get("kind") or "require",
                         parent.get("reason"), r.get("expr", parent.get("expr")), code=r.get("code"), seq=seq,
                         stack=r.get("stack"), section=sec, entry=parent, loop=loop_span, error=parent.get("error"),
                         args=r.get("args", parent.get("args")), reach=r)
        if sec == "panics":
            return Check(ids[seq], action, r.get("src") or sec, r.get("src"), "panic", None, r.get("expr"),
                         code=r.get("code"), seq=seq, stack=r.get("stack"), section=sec, entry=r, loop=loop_span,
                         reach=r)
        if sec == "calls":
            return Check(ids[seq], action, r.get("src") or sec, r.get("src"), "call", r.get("fn"), r.get("expr"),
                         seq=seq, stack=r.get("stack"), section=sec, entry=r, loop=loop_span, reach=r)
        if sec == "checks":
            kind = r.get("kind")
            if kind not in CHECK_KINDS:
                raise ModelError(f"{action}: a check of unknown kind {kind!r} (seq {seq})")
            return Check(ids[seq], action, r.get("src") or sec, r.get("src"), kind, None, r.get("expr"), seq=seq,
                         stack=r.get("stack"), section=sec, entry=r, loop=loop_span, reach=r)
        if sec == "writes":
            return Write(seq, r.get("src"), r.get("stack"), r.get("family"), list(r.get("path") or []), r.get("value"),
                         r.get("cond", 1), r)
        if sec == "mstores":
            return MStore(seq, r.get("src"), r.get("stack"), r.get("region"), r.get("op", "mstore"), r.get("offset"),
                          r.get("value"), r.get("cond", 1), r)
        if sec == "events":
            return Event(seq, r.get("src"), r.get("stack"), r.get("event"), r.get("signature"), r.get("topic0"),
                         list(r.get("args") or []), list(r.get("indexed") or []), bool(r.get("anonymous")),
                         r.get("cond", 1), list(r.get("topics") or []), r)
        if sec == "loops":
            span = r.get("src")
            body = [x for x in (make(s, span) for s in children.get(seq, [])) if x is not None]
            return Loop(seq, span, r.get("stack"), r.get("kind", "for"), r.get("cond", 1),
                        [(c.get("name"), c.get("entry"), c.get("value")) for c in r.get("carried") or []],
                        r.get("head", 1), _pairs(r.get("next")), r.get("break", 0), _pairs(r.get("at_break")),
                        r.get("count"), body, r, reach_of[seq], _pairs(r.get("exit")),
                        [(x.get("cond"), x.get("value")) for x in r.get("returns") or []])
        return None     # calls_free: a call whose failure is a value (its result is a term where it is used)

    steps = [x for x in (make(s, None) for s in children.get(None, [])) if x is not None]
    return Program(action, steps)


def document_programs(doc: dict) -> dict:
    """action name -> Program of every action of a transitions document (no compiler information)."""
    return {a["name"]: build_program(a) for a in sorted(doc.get("actions") or [], key=lambda a: a["name"])}


# ------------------------------------------------------------------------------------------------ the model
class ExtractedModel:
    """A loaded transitions document with its compiler information (holon.extracted_eval evaluates it)."""

    def __init__(self, doc: dict, info: dict, path: Path | None = None, sha256: str | None = None):
        if not is_transitions(doc):
            raise ModelError("not a holon-facts/0.3 transitions document")
        self.doc = doc
        self.info = info
        self.path = path
        self.sha256 = sha256 or sha256_bytes(dumps(doc).encode("utf-8"))
        self.contract = doc.get("contract")
        self.types: dict = dict((info.get("layout") or {}).get("types") or {})
        self.layout_list = list((info.get("layout") or {}).get("storage") or [])
        labels: dict = {}
        for s in self.layout_list:
            labels.setdefault(s["label"], []).append(s)
        # a label declared once in the layout: the family a term names by it (a twice-declared label, e.g. __gap, is
        # private to its contracts and named by no term)
        self.layout_entries = {k: v[0] for k, v in labels.items() if len(v) == 1}
        self.actions = {a["name"]: a for a in doc.get("actions") or []}
        self.families: dict[str, Family] = {}
        names = [s["name"] for s in (doc.get("storage") or []) + list(doc.get(FORMAT["inherited_storage"]) or [])]
        for s in doc.get("storage") or []:
            self._declare(s, True, names.count(s["name"]) > 1)
        for s in doc.get(FORMAT["inherited_storage"]) or []:
            self._declare(s, False, names.count(s["name"]) > 1)
        for name in sorted(self.storage_names()):
            if name not in self.families:
                le = self.layout_entries.get(name)
                if le is None:
                    raise ModelError(f"the document reads or writes storage {name!r}, which is neither one of its "
                                     "families nor a variable declared once in the contract's storage layout")
                self.families[name] = Family(name, int(le["slot"]), int(le["offset"]), le["type"], False,
                                             le.get("contract", ""))
        self._programs = {a: build_program(self.actions[a]) for a in sorted(self.actions)}

    def _declare(self, s: dict, own: bool, shared_name: bool = False) -> None:
        """A family of the document's storage or inherited storage, checked against the compiler's layout entry of the
        same label, slot and offset. A name two contracts declare is the family "<declared_in>.<name>"."""
        le = next((x for x in self.layout_list if x["label"] == s["name"] and int(x["slot"]) == int(s["slot"])
                   and int(x["offset"]) == int(s.get("offset", 0))), None)
        if le is None:
            at = [(x["slot"], x["offset"]) for x in self.layout_list if x["label"] == s["name"]]
            raise ModelError(f"family {s['name']}: the document says slot {s['slot']} offset {s.get('offset')}, "
                             f"the compiler's layout has it at {at or 'no slot'}")
        for f in s.get("fields") or []:
            if "slot" in f:
                mt = self._member(le["type"], f["name"])
                if mt is None or int(mt["slot"]) != int(f["slot"]) or int(mt["offset"]) != int(f.get("offset", 0)):
                    raise ModelError(f"family {s['name']}: field {f['name']} at slot {f['slot']} offset "
                                     f"{f.get('offset')} is not the compiler's member layout")
        name = f"{s['declared_in']}.{s['name']}" if shared_name and s.get("declared_in") else s["name"]
        if name in self.families:
            raise ModelError(f"family {name}: declared twice")
        self.families[name] = Family(name, int(s["slot"]), int(s.get("offset", 0)), le["type"], own,
                                     le.get("contract", ""))

    def _member(self, tid: str, name: str) -> dict | None:
        t = self.types.get(tid) or {}
        if t.get("encoding") == "mapping":
            t = self.types.get(t.get("value")) or {}
        return next((m for m in t.get("members") or [] if m.get("label") == name), None)

    # ---------------------------------------------------------------- what the terms read
    def terms(self):
        """(action name, where, term) of every term the document holds."""
        keys = {"guards": ("expr", "args"), "panics": ("expr", "args"),
                "calls": ("receiver", "args", "value", "cond", "expr"), "checks": ("expr",),
                "writes": ("path", "value", "cond"), "mstores": ("offset", "value", "cond"),
                "events": ("args", "topics", "cond"), "loops": ("cond", "head", "break", "count", "bound")}
        for a in self.doc.get("actions") or []:
            n = a["name"]
            for sec, r in _records(a):
                where = f"{sec}@{r.get('seq', r.get('src'))}"
                for k in keys[sec]:
                    if k in r:
                        yield n, f"{where}.{k}", r[k]
                if sec == "guards":
                    for j, x in enumerate(r.get(FORMAT["reaches"]) or []):
                        for k in ("expr", "args"):
                            if isinstance(x, dict) and k in x:
                                yield n, f"{where}.reaches[{j}].{k}", x[k]
                if sec == "loops":
                    for k, v in (("carried", "entry"), ("carried", "value"), ("next", "value"), ("at_break", "value"),
                                 ("exit", "value")):
                        for nm, t in _pairs(r.get(k), v):
                            yield n, f"{where}.{k}.{_label(nm)}.{v}", t
                    for j, x in enumerate(r.get("returns") or []):
                        yield n, f"{where}.returns[{j}].cond", x.get("cond")
                        yield n, f"{where}.returns[{j}].value", x.get("value")
                    for j, x in enumerate(r.get("regions") or []):
                        if x.get("writes") is not None:
                            yield n, f"{where}.regions[{j}].writes", x["writes"]
            if a.get("principal"):
                yield n, "principal", a["principal"].get("predicate")
            for i, t in enumerate((a.get("cost") or {}).get("terms") or []):
                yield n, f"cost[{i}]", t.get("iters")
            if isinstance(a.get(FORMAT["post"]), dict):
                for fam, t in sorted(a[FORMAT["post"]].items()):
                    yield n, f"post.{fam}", t
            if a.get(FORMAT["returns"]) is not None:
                yield n, "returns", a[FORMAT["returns"]]

    def storage_names(self) -> set:
        out = set()

        def walk(t):
            if isinstance(t, list):
                if len(t) == 2 and t[0] == "storage" and isinstance(t[1], str):
                    out.add(t[1])
                for x in t[1:] if t and isinstance(t[0], str) else t:
                    walk(x)
        for _a, _w, t in self.terms():
            walk(t)
        for a in self.doc.get("actions") or []:
            for e in a.get("effects") or []:
                if isinstance(e.get("family"), str):
                    out.add(e["family"])
            for w in self.program_records(a):
                if w[0] == "writes" and isinstance(w[1].get("family"), str):
                    out.add(w[1]["family"])
        return out

    @staticmethod
    def program_records(a: dict):
        """(section, record) of every record of an action (a loop's records are top-level records with "loop")."""
        yield from _records(a)

    def program(self, action: str) -> Program:
        return self._programs[action]

    def reaches(self, action: str) -> list[Check]:
        """Every check of the action in program order (guard reaches and implicit checks; module docstring)."""
        return self._programs[action].checks()

    def all_reaches(self) -> list[Check]:
        return [r for a in sorted(self.actions) for r in self.reaches(a)]

    # ---------------------------------------------------------------- the ABI
    def params(self, action: str) -> list[dict] | None:
        """The action's parameters ({name, type, components?}): the compiler's ABI, else the document's "params"
        (A19-12), else None."""
        a = self.actions[action]
        fns = self.info.get("functions") or {}
        sel = a.get("selector")
        e = fns.get(sel) if sel else fns.get(a["name"])
        if e is not None:
            return e["inputs"]
        ps = a.get(FORMAT["params"])
        if isinstance(ps, list):
            return [_doc_param(p) for p in ps]
        return None

    def call_signature(self, fn: str) -> dict | None:
        """The interface function a call term names ("<Contract>.<function>"), when it has exactly one overload."""
        hits = (self.info.get("members") or {}).get(fn) or []
        return hits[0] if len(hits) == 1 else None

    def error(self, name: str) -> dict | None:
        """The custom error of that name ({selector, params}) when every declaration of it has one selector."""
        hits = (self.info.get("errors") or {}).get(name) or []
        sels = sorted({h["selector"] for h in hits})
        return hits[0] if len(sels) == 1 else None

    def event(self, name: str) -> dict | None:
        hits = (self.info.get("events") or {}).get(name.rsplit(".", 1)[-1]) or []
        return hits[0] if len(hits) == 1 else None

    def immutable_type(self, name: str) -> dict | None:
        """The declared ABI type of an immutable or constant of the contract ({type, ..}), from the compiler."""
        return (self.info.get("immutables") or {}).get(name)

    # ---------------------------------------------------------------- storage addressing
    def type_of(self, tid: str) -> dict:
        t = self.types.get(tid)
        if t is None:
            raise ModelError(f"storage type {tid} is not in the compiler's layout")
        return t

    def family(self, name: str) -> Family:
        f = self.families.get(name)
        if f is None:
            raise ModelError(f"storage {name!r} is not a family of the model")
        return f

    def layout_document(self) -> dict:
        """The resolved families, as `holon model` writes them (DIR/layout.json)."""
        fams = []
        for name, f in sorted(self.families.items(), key=lambda kv: (kv[1].slot, kv[1].offset, kv[0])):
            t = self.type_of(f.type)
            fams.append({"name": name, "slot": f.slot, "offset": f.offset, "type": f.type, "label": t.get("label"),
                         "declared": f.declared, "contract": f.contract})
        used = set()
        todo = [f.type for f in self.families.values()]
        while todo:
            tid = todo.pop()
            if tid in used or tid not in self.types:
                continue
            used.add(tid)
            t = self.types[tid]
            todo += [x for x in (t.get("key"), t.get("value"), t.get("base")) if x]
            todo += [m["type"] for m in t.get("members") or []]
        progs = {a: {"checks": [c.id for c in p.checks()]} for a, p in sorted(self._programs.items())}
        return {"document": "extracted_layout", "machine_version": MACHINE_VERSION,
                "facts": self.path.as_posix() if self.path else None, "facts_sha256": self.sha256,
                "contract": self.contract, "families": fams, "types": {k: self.types[k] for k in sorted(used)},
                "programs": progs}


def _doc_param(p: dict) -> dict:
    t = p.get("type") or ""
    out = {"name": p.get("name") or "", "type": t}
    if p.get("fields"):
        out = {"name": p.get("name") or "", "type": "tuple" + (t[t.index("["):] if "[" in t else ""),
               "components": [_doc_param(f) for f in p["fields"]]}
    return out


def load_extracted(doc_path, root=None, source=None, info: dict | None = None) -> ExtractedModel:
    """The extracted model of a transitions document (module docstring). doc_path: a path (repo-relative or
    absolute) or the document itself (a dict, then info is required)."""
    root = Path(root or ROOT)
    if isinstance(doc_path, dict):
        if info is None:
            raise ModelError("a document passed as a dict needs info=")
        return ExtractedModel(doc_path, info)
    p = Path(doc_path)
    if not p.is_absolute():
        p = (root / p) if (root / p).exists() else Path.cwd() / p
    data = p.read_bytes()
    doc = json.loads(data.decode("utf-8"))
    if not is_transitions(doc):
        raise ModelError(f"{doc_path}: not a holon-facts/0.3 transitions document")
    sha = sha256_bytes(data)
    if info is None:
        info = toolchain_info(doc, sha, root, source)
    try:
        rel = Path(p.resolve().relative_to(root.resolve()).as_posix())
    except ValueError:
        rel = Path(p.name)
    return ExtractedModel(doc, info, rel, sha)


# ------------------------------------------------------------------------------------------------ holon model
def write_model(doc_path, out_dir, root=None, source=None, info: dict | None = None, check: bool = True,
                log=print) -> int:
    """`holon model --facts DOC --out DIR` for a transitions document (module docstring). Exit 0 when Bend checks
    the model; 1 otherwise."""
    from . import bend
    from .machine_bend import bend_model
    root = Path(root or ROOT)
    m = load_extracted(doc_path, root, source, info)
    text, debt = bend_model(m)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "model.bend").write_text(text, encoding="utf-8")
    (out / "layout.json").write_text(dumps(dict(m.layout_document(), environment_terms=debt)), encoding="utf-8")
    from . import window
    decl = window.declaration_for(m, root)
    wc = out / "window_check.json"
    if decl is not None:
        wc.write_text(dumps(window.check(m, decl, root)), encoding="utf-8")
        log(f"wrote {wc}")
    elif wc.exists():
        wc.unlink()
    log(f"wrote {out / 'model.bend'} ({len(m.actions)} actions, {len(m.families)} families, "
        f"{len(m.all_reaches())} checks; {len(debt)} terms left to the environment)")
    if not check:
        return 0
    cfg = bend.config(root)
    r = bend.check(out / "model.bend", cfg)
    log(r.first_line)
    return 0 if r.ok else 1


def main_model(args) -> int:
    """holon.mpipeline.main_model hands a transitions document here."""
    try:
        return write_model(args.facts, args.out or (ROOT / "build" / "extracted_model"), ROOT,
                           source=getattr(args, "source", None))
    except ModelError as e:
        print(f"holon model: {e}", file=sys.stderr)
        return 1
