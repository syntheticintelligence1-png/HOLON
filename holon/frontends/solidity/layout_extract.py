"""From walks to edges: naming, projection, merging, debt and the holon-facts/0.3 document of the Solidity frontend
(rules W3, W11, N1-N4, J1-J5, D1-D3 of the I17 contract: the docstring of tests_m2/test_extract_solidity_layout.py).

Per sidecar edge: the entry is found (W3), every path of its walk is explored (holon.frontends.solidity.ast.Walker),
the fields written into the selected sink's region are named after the formals that carry them (N1) and listed as the
encoder's input record (N2), condition atoms are named (N3, N4), paths are projected to their input conjuncts (J1),
merged (J2), kept in walk order (J3) and checked (J4); the debt of the store sequences and of the whole walk is kept
(D1-D3). Nothing here reads a fact document, a law or a result: the inputs are the sidecar and the compiler's output.
"""
from __future__ import annotations

import json

from .. import ExtractionError, FACTS_VERSION
from .ast import DSL_OPS, NON_DSL_OPS, Index, Walker, bits_of

FRONTEND_VERSION = "holon-frontend-solidity/0.1"
LANG = "solidity-evm-memory"
MAX_PATHS_PER_WALK = 4096
MAX_CALL_DEPTH = 16

ASSUMPTION_TEXT = {
    "A-dirty": ("Memory at the free pointer is not zeroed: every region a walk allocates (mload(0x40)) starts with "
                "unknown cells (memory_init dirty), so a byte that no op writes is unknown, never zero."),
    "A-env": ("Environment terms (storage, block, msg and tx members, blobhash, results of external calls, memory "
              "reads, and values computed from them) are free: a revert whose failing condition mentions one belongs "
              "to the transition, not to the edge (rule J1), and conditions on them are projected away."),
    "A-implicit": ("Implicit reverts (checked arithmetic, array bounds, ABI decoding) are not part of an edge's "
                   "partiality: only explicit require, revert and branch conditions on inputs are."),
}


def _key(x) -> str:
    return json.dumps(x, sort_keys=True)


def _dedup(entries: list[dict]) -> list[dict]:
    seen, out = set(), []
    for d in entries:
        k = _key(d)
        if k not in seen:
            seen.add(k)
            out.append(d)
    return out


def sorted_debt(entries: list[dict]) -> list[dict]:
    """D1: deduplicated, sorted by (stack, kind)."""
    return sorted(_dedup(entries), key=lambda d: (d["stack"], d["kind"], _key(d)))


def find_entry(index: Index, edge: str, spec: dict) -> dict:
    """W3: the FunctionDefinition named by the edge's entry, declared in that contract, exactly one, with a body."""
    entry = spec["entry"]
    contracts = index.contracts_named(entry["contract"])
    if len(contracts) != 1:
        raise ExtractionError(f"edge {edge}: contract {entry['contract']} found {len(contracts)} times (W3)")
    fns = [n for n in contracts[0].get("nodes", [])
           if n.get("nodeType") == "FunctionDefinition" and n.get("name") == entry["function"] and n.get("body")]
    if len(fns) != 1:
        raise ExtractionError(f"edge {edge}: entry {entry['contract']}.{entry['function']} with a body found "
                              f"{len(fns)} times (W3)")
    return fns[0]


# ------------------------------------------------------------------------------------------------ naming (N1-N4)
class Namer:
    """Condition and length atoms of one edge (N3, N4): a term is a field name, an input atom, or environment."""

    def __init__(self, kind: str, fields_by_term: dict, input_param: str | None):
        self.kind = kind
        self.fields_by_term = fields_by_term
        self.input_term = ("param", input_param) if input_param else None
        self.input_name = input_param.lstrip("_") if input_param else None

    def leaf(self, t):
        if self.kind == "encoder":
            return self.fields_by_term.get(t)
        if isinstance(t, tuple) and len(t) >= 2 and t[1] == self.input_term:
            if t[0] == "len" and len(t) == 2:
                return ["len", self.input_name]
            if t[0] == "byte" and len(t) == 3 and isinstance(t[2], int):
                return ["byte", self.input_name, t[2]]
        return None

    def analyze(self, t):
        """(DSL expression or None, has an environment atom, expressible) of a term (J5)."""
        if isinstance(t, int) and not isinstance(t, bool):
            return t, False, True
        leaf = self.leaf(t)
        if leaf is not None:
            return leaf, False, True
        if isinstance(t, tuple) and t and t[0] in DSL_OPS and len(t) >= 2:
            parts = [self.analyze(a) for a in t[1:]]
            expr = [t[0]] + [p[0] for p in parts]
            ok = all(p[2] for p in parts)
            return (expr if ok else None), any(p[1] for p in parts), ok
        if isinstance(t, tuple) and t and t[0] in NON_DSL_OPS:
            parts = [self.analyze(a) for a in (t[2:] if t[0] == "trunc" else t[1:])]
            return None, any(p[1] for p in parts), False
        return None, True, False


def written_fields(edge: str, oks: list) -> tuple[list[dict], dict]:
    """N1, N2: the encoder's input record and the map underlying term -> field name (first in record order)."""
    order, widths, vtypes = [], {}, {}
    by_term: dict = {}
    for p in oks:
        terms = {}
        for op in p.ops:
            for name, width, term, vtype in op["fields"]:
                if widths.setdefault(name, width) != width:
                    raise ExtractionError(f"edge {edge}: field {name} is written with widths {widths[name]} and "
                                          f"{width} (N1)")
                if terms.setdefault(name, term) != term:
                    raise ExtractionError(f"edge {edge}: field {name} stands for two different terms on one path (N1)")
                if name not in vtypes:
                    vtypes[name] = vtype
                    order.append(name)
                by_term.setdefault(term, set()).add(name)
    rank = {n: i for i, n in enumerate(order)}
    fields_by_term = {t: min(ns, key=rank.__getitem__) for t, ns in by_term.items()}
    record = []
    for name in order:
        vb = bits_of(vtypes[name]) if vtypes[name] else None
        record.append({"name": name, "width": widths[name], "value_type": vtypes[name], "value_bits": vb,
                       "truncates": vb is not None and vb > 8 * widths[name]})
    return record, fields_by_term


def _item(it: tuple) -> dict:
    if it[0] == "field":
        return {"field": it[1], "from": it[2], "len": it[3]}
    if it[0] == "zeros":
        return {"zeros": it[1]}
    return {"const": it[1]}


def _op(edge: str, op: dict, namer: Namer) -> dict:
    if op["op"] == "calldatacopy":
        if namer.kind != "loader" or op["input"] != namer.input_term:
            raise ExtractionError(f"edge {edge}: a calldatacopy of {op['input']!r:.120} is not expressible (J4, N4)")
        n, env, ok = namer.analyze(op["n"])
        if env or not ok:
            raise ExtractionError(f"edge {edge}: a calldatacopy length is not expressible (J4)")
        return {"op": "calldatacopy", "offset": op["offset"], "width": n,
                "src": [{"input": namer.input_name, "from": op["from"], "len": n}], "origin": op["origin"]}
    return {"op": op["op"], "offset": op["offset"], "width": 32 if op["op"] == "mstore" else 1,
            "src": [_item(it) for it in op["items"]], "origin": op["origin"]}


# ------------------------------------------------------------------------------------------------ J1-J4
def project(edge: str, paths: list, namer: Namer) -> list[dict]:
    """J1: ok paths keep their input conjuncts; a revert path belongs to the edge iff its failing conjunct is one."""
    out = []
    for p in paths:
        if p.outcome == "other":
            continue
        conv = []
        for c in p.cond:
            expr, env, ok = namer.analyze(c)
            if env:
                conv.append(None)
                continue
            if not ok:
                raise ExtractionError(f"edge {edge}: a field-condition is not expressible in the DSL (J4): {c!r:.200}")
            conv.append(expr)
        cond = [x for x in conv if x is not None]
        if p.outcome == "revert":
            if p.failing is None or conv[p.failing] is None:
                continue
            out.append({"cond": cond, "outcome": "revert", "reason": p.reason, "src": p.src})
            continue
        length, env, ok = namer.analyze(p.length)
        if env or not ok:
            raise ExtractionError(f"edge {edge}: an ok path's length is not an integer or an input-only DSL "
                                  f"expression (J4): {p.length!r:.200}")
        out.append({"cond": cond, "outcome": "ok", "length": length, "ops": [_op(edge, op, namer) for op in p.ops]})
    return out


def merge(paths: list[dict]) -> list[dict]:
    """J2: equal paths are one (first position kept); two ok paths with equal ops and length whose conds differ only
    at one position, c against ["!", c], are one without that conjunct (first position kept); until nothing merges."""
    out = _unique(paths)
    changed = True
    while changed:
        changed = False
        for i in range(len(out)):
            a = out[i]
            if a["outcome"] != "ok":
                continue
            for j in range(i + 1, len(out)):
                b = out[j]
                if b["outcome"] != "ok" or _key(a["ops"]) != _key(b["ops"]) or _key(a["length"]) != _key(b["length"]) \
                        or len(a["cond"]) != len(b["cond"]):
                    continue
                diff = [k for k, (x, y) in enumerate(zip(a["cond"], b["cond"])) if _key(x) != _key(y)]
                if len(diff) != 1:
                    continue
                x, y = a["cond"][diff[0]], b["cond"][diff[0]]
                if _key(y) == _key(["!", x]) or _key(x) == _key(["!", y]):
                    merged = dict(a, cond=a["cond"][:diff[0]] + a["cond"][diff[0] + 1:])
                    out = _unique(out[:i] + [merged] + out[i + 1:j] + out[j + 1:])
                    changed = True
                    break
            if changed:
                break
    return out


def _unique(paths: list[dict]) -> list[dict]:
    seen, out = set(), []
    for p in paths:
        k = _key(p)
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def check_well_formed(edge: str, paths: list[dict]) -> None:
    """J4: two ok paths with equal conditions and different bytes depend on the environment."""
    by_cond: dict = {}
    for p in paths:
        if p["outcome"] != "ok":
            continue
        k = _key(p["cond"])
        body = _key([p["ops"], p["length"]])
        if by_cond.setdefault(k, body) != body:
            raise ExtractionError(f"edge {edge}: two ok paths with the condition {p['cond']} write different bytes: "
                                  "the layout depends on the environment (J4)")


# ------------------------------------------------------------------------------------------------ one edge
def edge_document(index: Index, edge: str, spec: dict) -> tuple[dict, list[dict] | None]:
    """The document entry of one edge and, for an encoder, its input record."""
    entry = find_entry(index, edge, spec)
    walker = Walker(index, edge, spec, entry, MAX_PATHS_PER_WALK, MAX_CALL_DEPTH)
    paths = walker.walk()
    oks = [p for p in paths if p.outcome == "ok"]
    if not oks:
        raise ExtractionError(f"edge {edge}: the selected sink {spec['sink']} is never reached (W10)")
    record, by_term = written_fields(edge, oks)
    namer = Namer(spec["kind"], by_term if spec["kind"] == "encoder" else {},
                  spec.get("input") if spec["kind"] == "loader" else None)
    projected = merge(project(edge, paths, namer))
    check_well_formed(edge, projected)
    debt = sorted_debt([d for p in oks for d in p.seq_debt])
    stacks = sorted({tuple(s) for p in paths for s in p.sinks})
    doc = {
        "kind": spec["kind"],
        "from": spec["from"],
        "to": "Maybe<Bytes>" if any(p["outcome"] == "revert" for p in projected) else "Bytes",
        "lang": LANG,
        "entry": {"fn": index.fn_name(entry), "src": index.span(entry["src"])},
        "sink": {"op": "keccak256", "stack": list(spec["sink"])},
        "memory_init": "dirty",
        "paths": projected,
        "debt": debt,
        "exact": debt == [],
        "walk": {
            "functions": sorted({f for p in paths for f in p.functions}),
            "paths": {k: sum(p.outcome == k for p in paths) for k in ("ok", "revert", "other")},
            "sinks": [{"op": "keccak256", "stack": list(s), "selected": list(s) == list(spec["sink"])} for s in stacks],
            "debt": sorted_debt([d for p in paths for d in p.debt]),
        },
    }
    return doc, (record if spec["kind"] == "encoder" else None)


def build(compiled, side: dict, sidecar_rel: str, sidecar_sha256: str) -> dict:
    """The holon-facts/0.3 document of a Solidity sidecar."""
    index = Index(compiled)
    types: dict = {"Bytes": {"kind": "bytes"}}
    functions: dict = {}
    widths: list[dict] = []
    for edge in sorted(side["edges"]):
        spec = side["edges"][edge]
        doc, record = edge_document(index, edge, spec)
        functions[edge] = doc
        if record is not None:
            rec = {"kind": "record", "fields": record}
            if spec["from"] in types and types[spec["from"]] != rec:
                raise ExtractionError(f"edge {edge}: record {spec['from']} differs from another encoder's (N2)")
            types[spec["from"]] = rec
    for name in sorted(types):
        t = types[name]
        trunc = [f["name"] for f in t.get("fields", []) if f["truncates"]]
        if trunc:
            widths.append({"id": f"A-width:{name}", "record": name, "fields": trunc,
                           "text": (f"Fields of {name} whose value type is wider than their stored width: the bytes "
                                    "keep only the low part of the value, so they determine it only when it fits the "
                                    "width.")})
    assumptions = [{"id": k, "text": v} for k, v in ASSUMPTION_TEXT.items()
                   if k != "A-dirty" or any(f["memory_init"] == "dirty" for f in functions.values())]
    assumptions = sorted(assumptions + widths, key=lambda a: a["id"])
    return {
        "facts_version": FACTS_VERSION,
        "target": dict(side["target"]),
        "extraction": {
            "method": "extracted",
            "frontend": "solidity",
            "frontend_version": FRONTEND_VERSION,
            "sidecar": {"path": sidecar_rel, "sha256": sidecar_sha256},
            "toolchain": {"solc": {"version": compiled.version, "sha256": compiled.solc_sha256}},
            "settings": compiled.settings,
            "inputs": [{"unit": u, "sha256": _sha256(compiled.units[u])} for u in sorted(compiled.units)],
        },
        "types": types,
        "functions": functions,
        "assumptions": assumptions,
    }


def _sha256(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()
