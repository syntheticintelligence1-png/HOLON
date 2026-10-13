"""The extracted model: holon-facts/0.3 transitions documents compiled to a raw-storage model (I20; whitepaper §8.7,
§10.1 translators, Def 4.7; BUILD_PLAN I20). The contract is the docstring of tests_m2/test_extracted_refinement.py,
clauses 1, 7 and 10.

  load_extracted(doc_path, root=None, source=None, info=None) -> ExtractedModel
  python -m holon model --facts <transitions document> --out DIR      (holon.mpipeline.main_model dispatches here)

The document (holon.frontends.solidity.transitions, I19, extended additively by the I19 follow-up A19). This module is
the one place that reads a document's sections; every other I20 module (holon.extracted_eval, holon.machine_bend,
holon.window, holon.differential, holon.sorts.width) goes through ExtractedModel. Two shapes are read:

  * the planned A19 shape (a19_i20_designs.json; the key names are not final, FORMAT lists every one read here):
      document  "storage" (fields gain "slot", "offset"), "inherited_storage" [{name, slot, offset, kind, ..,
                declared_in}];
      action    "params" [{name, type, width, location, fields}], "payable", "mutability", "returns", "declared_in";
                "guards"[i]["reaches"] [{seq, stack, expr}] (every reach; the first equals the guard's expr);
                "panics" [{seq, src, stack, code, op, args, expr}] (implicit checks: Panic codes);
                "calls" [{seq, src, stack, fn, receiver, args, value, mutability, cond, commit[, check]}] (a failing
                external call bubbles its revert data; its check is ["callok", fn, receiver, args..] under cond);
                "checks" [{seq, kind: callvalue|abi, src, expr}] (the dispatcher's checks);
                "writes" [{seq, src, stack, family, path: [[map|index|member, key]..], value, cond}];
                "mstores" [{seq, src, stack, region, op, offset, value, cond}];
                "events" [{seq, src, stack, event, signature, topic0, args, indexed, anonymous, cond}];
                "loops" [{seq, src, stack, kind, cond, carried: [{name, entry}], head, next: [{name, value}], break,
                          at_break: [{name, value}], count, steps}] whose steps hold the same sections for one
                          generic iteration (a dict of sections, or a list of records tagged by "type" or classified by
                          their keys: Program.classify);
      seq is the walk-order counter shared by every record of an action: the program is every record sorted by seq.
  * the current I19 shape (adapter): "guards" (first reach of each span) in document order are the program's checks;
    effects carry no values and there are no events, so a program of this shape is incomplete (Program.missing) and
    an ok step cannot give its writes or events.

Checks. Every guard reach, implicit check (panic), external-call check and dispatcher check is one Check, in program
order. Its id is "<action>#<span>#<k>": span is the record's src (for a dispatcher check without src, its kind), k
counts the checks of that span in the action in program order (nested loop records included, in walk order). The
transaction reverts at the first check whose condition is 0 (holon.extracted_eval).

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
INFO_VERSION = "holon-extracted-info/0.1"
MACHINE_VERSION = "holon-machine-extracted/0.1"
WORD = 1 << 256
MASK = WORD - 1

# Every key of the planned A19 shape this module reads (integration hook: the follow-up's names are not final; a
# rename is one edit here).
FORMAT = {
    "inherited_storage": "inherited_storage", "params": "params", "payable": "payable", "mutability": "mutability",
    "returns": "returns", "declared_in": "declared_in", "reaches": "reaches", "panics": "panics", "calls": "calls",
    "checks": "checks", "writes": "writes", "mstores": "mstores", "events": "events", "loops": "loops",
    "post": "post", "seq": "seq", "steps": "steps", "order": "order",
}
# the sections of an action (and of a loop body) that hold program records, in tie-break order for equal seq: an
# implicit check before a guard reach at the same point (an assert is both: Panic 0x01 is its revert data)
SECTIONS = ("checks", "panics", "calls", "guards", "loops", "writes", "mstores", "events")
A19_KEYS = ("panics", "calls", "checks", "writes", "mstores", "events", "loops")


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
    return {"info_version": INFO_VERSION, "contract": contract, "unit": hits[0][0], "linearization": lin,
            "layout": {"storage": [{k: s[k] for k in ("label", "slot", "offset", "type", "contract")}
                                   for s in lay.get("storage") or []],
                       "types": lay.get("types") or {}},
            "functions": own, "members": members, "errors": errors, "events": events}


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
    """A guard reach, an implicit check (panic), an external-call check or a dispatcher check (module docstring)."""
    id: str
    action: str
    span: str                 # the id's span: the record's src, or the kind of a dispatcher check without one
    src: object
    kind: str                 # require | modifier | revert | panic | call | callvalue | abi
    reason: object
    expr: object
    code: object = None       # a Panic code
    seq: object = None
    stack: object = None
    section: str = "guards"
    entry: dict = field(default_factory=dict)
    loop: object = None       # the span of the innermost loop record holding it


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
    entry: dict = field(default_factory=dict)


@dataclass
class Loop:
    seq: object
    src: str
    stack: object
    kind: str
    cond: object
    carried: list            # [(name, entry term)]
    head: object
    next: list               # [(name, value term)]
    brk: object
    at_break: list           # [(name, value term)]
    count: object
    body: list               # program records of one generic iteration, in seq order
    entry: dict = field(default_factory=dict)


@dataclass
class Program:
    """An action's records in program order (module docstring)."""
    action: str
    steps: list
    shape: str                # "a19" | "i19"
    missing: list             # what the document does not give for this action ("writes", "events")

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


def classify(rec: dict) -> str | None:
    """The section of a record of a loop body given as a list (integration hook: by its "type"/"record" tag, else by
    its keys)."""
    t = rec.get("type") or rec.get("record")
    if isinstance(t, str):
        t = t.lower().rstrip("s")
        return {"guard": "guards", "reach": "guards", "panic": "panics", "call": "calls", "check": "checks",
                "write": "writes", "mstore": "mstores", "event": "events", "loop": "loops"}.get(t)
    if "carried" in rec or "head" in rec:
        return "loops"
    if "code" in rec and "expr" in rec:
        return "panics"
    if "family" in rec and "value" in rec:
        return "writes"
    if "event" in rec or "topic0" in rec:
        return "events"
    if "fn" in rec and "receiver" in rec:
        return "calls"
    if "op" in rec and "offset" in rec:
        return "mstores"
    if rec.get("kind") in ("callvalue", "abi"):
        return "checks"
    if "expr" in rec:
        return "guards"
    return None


def _records(container) -> list[tuple[str, dict]]:
    """(section, record) of a container: an action (its sections) or a loop body (a dict of sections, or a list)."""
    out = []
    if isinstance(container, dict):
        for sec in SECTIONS:
            for r in container.get(FORMAT.get(sec, sec)) or []:
                if isinstance(r, dict):
                    out.append((sec, r))
    elif isinstance(container, list):
        for r in container:
            if isinstance(r, dict):
                sec = classify(r)
                if sec is None:
                    raise ModelError(f"a loop body record of unknown kind: {canonical(r)[:200]}")
                out.append((sec, r))
    return out


def _pairs(xs, key: str = "value") -> list:
    out = []
    for x in xs or []:
        if isinstance(x, dict):
            out.append((x.get("name"), x.get(key, x.get("entry"))))
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


def callok_expr(rec: dict):
    """The check of an external call record: its own "check"."expr" when the record has one, else
    ["||", ["!", cond], ["callok", fn, receiver, args..]] (["callok", ..] when unconditional)."""
    chk = rec.get("check")
    if isinstance(chk, dict) and "expr" in chk:
        return chk["expr"]
    ok = ["callok", rec.get("fn"), rec.get("receiver")] + list(rec.get("args") or [])
    cond = rec.get("cond", 1)
    return ok if cond == 1 else ["||", ["!", cond], ok]


# ------------------------------------------------------------------------------------------------ programs
def with_order(a: dict) -> dict:
    """The action with every top-level record given a seq from the action's "order" list, when its records carry
    none (the follow-up's minimum, A19-03: [["guard", span, reach index] | ["panic", i] | ["call", i] | ["check", i],
    ..] over the checks). Writes, memory stores and events, whose terms are over the pre-state, follow every check in
    document order (their relative order to the checks does not change a step's result). A loop record without seq
    cannot be placed: ModelError."""
    order = a.get(FORMAT["order"])
    recs = list(_records(a))
    if not isinstance(order, list) or all(isinstance(r.get(FORMAT["seq"]), int) or
                                          any(isinstance(x, dict) and isinstance(x.get(FORMAT["seq"]), int)
                                              for x in r.get(FORMAT["reaches"]) or [])
                                          for _, r in recs):
        return a
    out = {k: (json.loads(json.dumps(v)) if k in SECTIONS else v) for k, v in a.items()}
    for i, item in enumerate(order):
        kind, *rest = item
        if kind == "guard":
            span, k = rest[0], rest[1] if len(rest) > 1 else 0
            g = next((x for x in out.get("guards") or [] if x.get("src") == span), None)
            if g is None:
                raise ModelError(f"{a['name']}: order names guard {span}, which the action does not have")
            subs = g.get(FORMAT["reaches"])
            if isinstance(subs, list) and subs:
                subs[k][FORMAT["seq"]] = i
            else:
                g[FORMAT["seq"]] = i
        elif kind in ("panic", "call", "check"):
            sec = kind + "s"
            out[sec][rest[0]][FORMAT["seq"]] = i
        else:
            raise ModelError(f"{a['name']}: an order entry of unknown kind {kind!r}")
    nxt = len(order)
    for sec in ("writes", "mstores", "events", "loops"):
        for r in out.get(sec) or []:
            if not isinstance(r.get(FORMAT["seq"]), int):
                if sec == "loops":
                    raise ModelError(f"{a['name']}: a loop record without seq cannot be placed by the order list")
                r[FORMAT["seq"]] = nxt
                nxt += 1
    return out


def shape(a: dict) -> str:
    """"a19" for an action with any section of the planned follow-up shape, else "i19"."""
    if any(k in a for k in (FORMAT[x] for x in A19_KEYS)):
        return "a19"
    if any(isinstance(g, dict) and FORMAT["reaches"] in g for g in a.get("guards") or []):
        return "a19"
    return "i19"

def build_program(a: dict) -> Program:
    """The action's records in program order, with check ids (module docstring). Needs no compiler information."""
    action = a["name"]
    shape_ = shape(a)
    counts: dict = {}

    def cid(span: str) -> str:
        k = counts.get(span, 0)
        counts[span] = k + 1
        return f"{action}#{span}#{k}"

    if shape_ == "i19":
        steps = []
        for g in a.get("guards") or []:
            span = g.get("src") or g.get("kind") or "guard"
            steps.append(Check(cid(span), action, span, g.get("src"), g.get("kind") or "require",
                               g.get("reason"), g.get("expr"), section="guards", entry=g))
        missing = []
        if a.get("effects"):
            missing.append("writes")
        missing.append("events")
        return Program(action, steps, shape_, missing)

    def items(container, loop_span) -> list:
        raw = []
        for sec, r in _records(container):
            if sec == "guards":
                subs = r.get(FORMAT["reaches"])
                if isinstance(subs, list) and subs:
                    for x in subs:
                        raw.append((sec, dict(x), r))
                else:
                    raw.append((sec, r, r))
            else:
                raw.append((sec, r, r))
        for sec, r, _ in raw:
            if not isinstance(r.get(FORMAT["seq"]), int):
                raise ModelError(f"{action}: a {sec} record without an integer seq in a document of the A19 shape "
                                 f"({canonical(r)[:160]})")
        raw.sort(key=lambda x: (x[1][FORMAT["seq"]], SECTIONS.index(x[0])))
        seqs = [x[1][FORMAT["seq"]] for x in raw]
        if len(set(seqs)) != len(seqs):
            dup = sorted({s for s in seqs if seqs.count(s) > 1})
            # an assert is a guard reach and a Panic 0x01 at one point: the panic decides (SECTIONS order)
            kinds = {s: sorted({x[0] for x in raw if x[1][FORMAT["seq"]] == s}) for s in dup}
            if any(v != ["guards", "panics"] for v in kinds.values()):
                raise ModelError(f"{action}: two records share seq {dup[:4]} ({kinds})")
        out = []
        for sec, r, parent in raw:
            seq = r[FORMAT["seq"]]
            if sec == "guards":
                span = parent.get("src") or "guard"
                out.append(Check(cid(span), action, span, parent.get("src"), parent.get("kind") or "require",
                                 parent.get("reason"), r.get("expr", parent.get("expr")), seq=seq,
                                 stack=r.get("stack"), section=sec, entry=parent, loop=loop_span))
            elif sec == "panics":
                span = r.get("src") or "panic"
                out.append(Check(cid(span), action, span, r.get("src"), "panic", None, r.get("expr"),
                                 code=r.get("code"), seq=seq, stack=r.get("stack"), section=sec, entry=r,
                                 loop=loop_span))
            elif sec == "calls":
                span = r.get("src") or "call"
                out.append(Check(cid(span), action, span, r.get("src"), "call", None, callok_expr(r), seq=seq,
                                 stack=r.get("stack"), section=sec, entry=r, loop=loop_span))
            elif sec == "checks":
                span = r.get("src") or r.get("kind") or "check"
                out.append(Check(cid(span), action, span, r.get("src"), r.get("kind") or "check", None,
                                 r.get("expr"), seq=seq, stack=r.get("stack"), section=sec, entry=r,
                                 loop=loop_span))
            elif sec == "writes":
                out.append(Write(seq, r.get("src"), r.get("stack"), r.get("family"), list(r.get("path") or []),
                                 r.get("value"), r.get("cond", 1), r))
            elif sec == "mstores":
                out.append(MStore(seq, r.get("src"), r.get("stack"), r.get("region"), r.get("op", "mstore"),
                                  r.get("offset"), r.get("value"), r.get("cond", 1), r))
            elif sec == "events":
                out.append(Event(seq, r.get("src"), r.get("stack"), r.get("event"), r.get("signature"),
                                 r.get("topic0"), list(r.get("args") or []), list(r.get("indexed") or []),
                                 bool(r.get("anonymous")), r.get("cond", 1), r))
            elif sec == "loops":
                span = r.get("src")
                body = items(r.get(FORMAT["steps"]), span)
                out.append(Loop(seq, span, r.get("stack"), r.get("kind", "for"), r.get("cond", 1),
                                _pairs(r.get("carried"), "entry"), r.get("head", 1), _pairs(r.get("next")),
                                r.get("break", 0), _pairs(r.get("at_break")), r.get("count"), body, r))
        return out

    steps = items(with_order(a), None)
    missing = []
    if FORMAT["writes"] not in a and a.get("effects"):
        missing.append("writes")
    if FORMAT["events"] not in a:
        missing.append("events")
    return Program(action, steps, shape_, missing)


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
        self.layout_entries = {s["label"]: s for s in (info.get("layout") or {}).get("storage") or []}
        self.actions = {a["name"]: a for a in doc.get("actions") or []}
        self.families: dict[str, Family] = {}
        for s in doc.get("storage") or []:
            self._declare(s, True)
        for s in doc.get(FORMAT["inherited_storage"]) or []:
            self._declare(s, False)
        for name in sorted(self.storage_names()):
            if name not in self.families:
                le = self.layout_entries.get(name)
                if le is None:
                    raise ModelError(f"the document reads or writes storage {name!r}, which is neither one of its "
                                     "families nor in the contract's storage layout")
                self.families[name] = Family(name, int(le["slot"]), int(le["offset"]), le["type"], False,
                                             le.get("contract", ""))
        self._programs = {a: build_program(self.actions[a]) for a in sorted(self.actions)}

    def _declare(self, s: dict, own: bool) -> None:
        le = self.layout_entries.get(s["name"])
        if le is None:
            raise ModelError(f"family {s['name']}: not in the compiler's storage layout")
        if int(le["slot"]) != int(s["slot"]) or int(le["offset"]) != int(s.get("offset", 0)):
            raise ModelError(f"family {s['name']}: the document says slot {s['slot']} offset {s.get('offset')}, "
                             f"the compiler {le['slot']} {le['offset']}")
        for f in s.get("fields") or []:
            if "slot" in f:
                mt = self._member(le["type"], f["name"])
                if mt is None or int(mt["slot"]) != int(f["slot"]) or int(mt["offset"]) != int(f.get("offset", 0)):
                    raise ModelError(f"family {s['name']}: field {f['name']} at slot {f['slot']} offset "
                                     f"{f.get('offset')} is not the compiler's member layout")
        self.families[s["name"]] = Family(s["name"], int(s["slot"]), int(s.get("offset", 0)), le["type"], own,
                                          le.get("contract", ""))

    def _member(self, tid: str, name: str) -> dict | None:
        t = self.types.get(tid) or {}
        if t.get("encoding") == "mapping":
            t = self.types.get(t.get("value")) or {}
        return next((m for m in t.get("members") or [] if m.get("label") == name), None)

    # ---------------------------------------------------------------- what the terms read
    def terms(self):
        """(action name, where, term) of every term the document holds."""
        def walk_rec(n, where, sec, r):
            keys = {"guards": ("expr",), "panics": ("expr", "args"), "calls": ("receiver", "args", "value", "cond"),
                    "checks": ("expr",), "writes": ("path", "value", "cond"), "mstores": ("offset", "value", "cond"),
                    "events": ("args", "cond"), "loops": ("cond", "head", "break", "count")}[sec]
            for k in keys:
                if k in r:
                    yield n, f"{where}.{k}", r[k]
            if sec == "guards":
                for j, x in enumerate(r.get(FORMAT["reaches"]) or []):
                    if isinstance(x, dict) and "expr" in x:
                        yield n, f"{where}.reaches[{j}]", x["expr"]
            if sec == "loops":
                for k in ("carried", "next", "at_break"):
                    for nm, t in _pairs(r.get(k), "entry" if k == "carried" else "value"):
                        yield n, f"{where}.{k}.{nm}", t
                for j, (s2, r2) in enumerate(_records(r.get(FORMAT["steps"]))):
                    yield from walk_rec(n, f"{where}.steps[{j}]", s2, r2)
        for a in self.doc.get("actions") or []:
            n = a["name"]
            for sec, r in _records(a):
                yield from walk_rec(n, sec, sec, r)
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
        for sec, r in _records(a):
            yield sec, r
            if sec == "loops":
                stack = list(_records(r.get(FORMAT["steps"])))
                while stack:
                    s2, r2 = stack.pop(0)
                    yield s2, r2
                    if s2 == "loops":
                        stack.extend(_records(r2.get(FORMAT["steps"])))

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
        progs = {a: {"shape": p.shape, "missing": p.missing, "checks": [c.id for c in p.checks()]}
                 for a, p in sorted(self._programs.items())}
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
