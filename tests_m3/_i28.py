"""I28 instrument (versioned machines, PAR-init, O9, D4, F12.5 and G11V's in-flight sets), fixed at the I28 prereg
(BUILD_PLAN §0.1, "instruments are inputs").

The contract is the docstring of tests_m3/test_versions.py, rules V1-V9, PI1-PI6 and G1-G3. This module writes those
rules out a second time, independently of holon/, so that the tests can decide what holon must write. It reads I63's
committed history and timeline (gen/M3/history/morph_rollup.json, results/M3/history/timeline.json) and the
implementation codes I63 committed (results/M3/history/code/), I63's instrument (tests_m3/_i63.py: the H5 layout diff
and the H6 in-flight sets, fixed at the I63 prereg), I26's instrument (tests_m3/_i26.py: commitments F1/F2 and their
authenticating guard reaches, fixed at the I26 prereg) and transitions documents, all as JSON; nothing here imports
holon/.

  path(root)                 V1: the deployed path (versions in upgrade order, repeats collapsed), the versions in no
                             match and the unmatched upgrades
  deployments(root)          V1: every matched upgrade keyed by (version, the words at the matched build's immutable
                             ranges of the committed code)
  edges(root)                V2: the entry edge from the placeholder and the MIG edges along the path (I63's edges)
  inflight_types(root)       V3: the in-flight entries of the path's edges whose kind is retyped or reinterpreted
  reverse(root)              V4: every path edge reversed (a downgrade) with its H5 diff and H6 in-flight set, and the
                             downgrade gaps (the reverse edges whose diff is incompatible)
  gap_meta(kind)             V4, PI5: the obligation, question and status every gap of a kind carries (the sidecar's)
  inflight_words(..)         V8: the legacy words of an edge at a key: entry, reads, real slot and layout coordinate
  commit_key(calldata)       V8: the batch index a commit writes, from its calldata (the parent header's index + 1)
  abi_leaves(params, cd)     V8: a call's arguments decoded from its calldata by a document's parameter types, as the
                             leaves x_i's literal must begin with
  limbs(n)                   a word as the model's eight little-endian 32-bit limbs (w_of_limbs's argument)
  versions_basis_doc(root)   the content of spec/M3/lib/versions_basis.json (its doc field aside)
  chains(path)               PI1-PI3 over one transitions document: per commitment family its root sites, successor
                             sites and chained pairs
  par_init(docs, contract)   PI4: the PAR-init basis over the versioned documents and its law ids
  link_gaps(path, chains)    PI5: the external calls of a document that carry a chained cell, by interface
  cell(header, o, s)         a header cell's value: the word at byte offset o shifted right by s
  root_witness_problems(..)  PI6: what a PAR-init witness's root step must show, checked on its input bytes

  python -m tests_m3._i28 --write   recompute spec/M3/lib/versions_basis.json (only at the prereg)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDECAR = ROOT / "spec" / "M3" / "lib" / "versions.json"
BASIS = ROOT / "spec" / "M3" / "lib" / "versions_basis.json"
HISTORY = "gen/M3/history/morph_rollup.json"
TIMELINE = "results/M3/history/timeline.json"
CODE_DIR = "results/M3/history/code"
HEAD_DOC = "spec/M2/facts/morph_rollup.extracted.json"
HASHES = ("keccak256", "sha256")
PLACEHOLDER = "placeholder"
BASIS_VERSION = "holon-versions-basis/0.1"


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def is_op(t, op=None) -> bool:
    return isinstance(t, list) and bool(t) and isinstance(t[0], str) and (op is None or t[0] == op)


def conjuncts(e) -> list:
    if is_op(e, "&&"):
        out = []
        for x in e[1:]:
            out += conjuncts(x)
        return out
    return [e]


def contains(t, sub) -> bool:
    if t == sub:
        return True
    if isinstance(t, list):
        return any(contains(x, sub) for x in t)
    return False


def norm(t):
    """Additions of the literal 0 folded away, bottom up (["+", 0, x] and ["+", x, 0] are x): the only normalisation
    PI3 applies before comparing terms syntactically."""
    if not isinstance(t, list):
        return t
    if t and isinstance(t[0], str):
        t = [t[0]] + [norm(x) for x in t[1:]]
        if t[0] == "+" and len(t) == 3:
            if t[1] == 0:
                return t[2]
            if t[2] == 0:
                return t[1]
        return t
    return [norm(x) for x in t]


# ---------------------------------------------------------------------------------------------------- V1-V4
def _i63():
    import tests_m3._i63 as I63
    return I63


def history(root: Path = ROOT) -> dict:
    return load(Path(root) / HISTORY)


def timeline(root: Path = ROOT) -> dict:
    return load(Path(root) / TIMELINE)


def path(root: Path = ROOT) -> dict:
    """V1: {"path": the versions of the timeline's matched upgrades in upgrade order with consecutive repeats collapsed,
    "never_deployed": the history's versions in no match, "unmatched": [{"block", "implementation", "reason"}] (the
    timeline's coverage debt)}. Refused (ValueError) when an upgrade matches more than one version, or when two
    consecutive path versions are not the two ends of one history edge, or the path goes back (a downgrade)."""
    h, t = history(root), timeline(root)
    order = [v["id"] for v in h["versions"]]
    seq = []
    for u in t["upgrades"]:
        vs = sorted({m["version"] for m in u.get("matches") or []})
        if len(vs) > 1:
            raise ValueError(f"upgrade at block {u['block']} matches several versions {vs}")
        if vs and (not seq or seq[-1] != vs[0]):
            seq.append(vs[0])
    edges = {(e["from"], e["to"]) for e in h["edges"]}
    for a, b in zip(seq, seq[1:]):
        if (a, b) not in edges:
            raise ValueError(f"path step {a} -> {b} is not a history edge")
        if order.index(b) < order.index(a):
            raise ValueError(f"path step {a} -> {b} goes back")
    matched = set(seq)
    return {"path": seq, "never_deployed": [v for v in order if v not in matched],
            "unmatched": [{"block": c["block"], "implementation": c["implementation"], "reason": c["reason"]}
                          for c in t["coverage_debt"]]}


def deployments(root: Path = ROOT) -> list:
    """V1: [{"block", "implementation", "version", "config", "immutables": [the code's words at each immutable range of the
    matched build, in range order]}] for every matched upgrade, in upgrade order. The code is the committed file
    results/M3/history/code/<implementation>.hex; the ranges are the matched version's build under the matched
    configuration (gen/M3/history/morph_rollup.json versions[].code[config].ranges)."""
    root = Path(root)
    h, t = history(root), timeline(root)
    vers = {v["id"]: v for v in h["versions"]}
    out = []
    for u in t["upgrades"]:
        ms = u.get("matches") or []
        if not ms:
            continue
        m = ms[0]
        code = bytes.fromhex((root / CODE_DIR / f"{u['implementation']}.hex").read_text().strip().removeprefix("0x"))
        rngs = vers[m["version"]]["code"][m["config"]]["ranges"]
        out.append({"block": u["block"], "implementation": u["implementation"], "version": m["version"],
                    "config": m["config"], "immutables": [int.from_bytes(code[o:o + n], "big") for o, n in rngs]})
    return out


def _reinit(r: dict) -> dict:
    return {"name": r["name"], "version": r["version"]}


def edges(root: Path = ROOT) -> dict:
    """V2: {"entry": {"from": "placeholder", "to": the first path version, "introduced": that version's reinitializers},
    "edges": [{"from", "to", "introduced", "compatible", "in_flight", "in_flight_count"}] one per consecutive pair of the
    path, copied from the history's edge between them (introduced reduced to name and version)}."""
    h = history(root)
    p = path(root)["path"]
    vers = {v["id"]: v for v in h["versions"]}
    by = {(e["from"], e["to"]): e for e in h["edges"]}
    out = []
    for a, b in zip(p, p[1:]):
        e = by[(a, b)]
        out.append({"from": a, "to": b, "introduced": [_reinit(r) for r in e["introduced"]],
                    "compatible": e["compatible"], "in_flight": e["in_flight"], "in_flight_count": len(e["in_flight"])})
    first = vers[p[0]] if p else None
    entry = {"from": PLACEHOLDER, "to": p[0], "introduced": [_reinit(r) for r in first["reinitializers"]]} if p else None
    return {"entry": entry, "edges": out}


def inflight_types(root: Path = ROOT) -> list:
    """V3: [{"edge": "<from>-><to>", "entry", "kind", "reads"}] for every in-flight entry of a path edge whose kind is
    retyped or reinterpreted, in edge then entry order."""
    out = []
    for e in edges(root)["edges"]:
        for x in e["in_flight"]:
            if x["kind"] != "unchanged":
                out.append({"edge": f"{e['from']}->{e['to']}", "entry": x["entry"], "kind": x["kind"],
                            "reads": x["reads"]})
    return out


def gap_meta(kind: str, root: Path = ROOT) -> dict:
    """V4, PI5: {"obligation", "question", "status": "open"} for a gap of this kind, the obligation and question from the
    sidecar's gaps.<kind> (data: the code that writes gaps names no case-study item)."""
    g = load(Path(root) / "spec" / "M3" / "lib" / "versions.json")["gaps"][kind]
    return {"obligation": g["obligation"], "question": g["question"], "status": "open"}


def reverse(root: Path = ROOT) -> dict:
    """V4: {"reverse": [{"from": b, "to": a, "compatible", "diff", "in_flight_changed"}] for every path edge a -> b
    (the downgrade b -> a: I63's H5 diff of layout b to layout a, and the H6 in-flight entries of a's layout that are not
    unchanged), "gaps": [{"id": "gap:M3:downgrade:<b>-><a>", "kind": "downgrade", "from": b, "to": a, "retyped",
    "overlap", "removed", "added", "obligation", "question", "status"}] for the reverse edges whose diff is
    incompatible}, in path order."""
    I63 = _i63()
    h = history(root)
    vers = {v["id"]: v for v in h["versions"]}
    rev, gaps = [], []
    for e in edges(root)["edges"]:
        a, b = e["from"], e["to"]
        d = I63.layout_diff(vers[b]["layout"], vers[a]["layout"])
        inf = I63.in_flight(vers[b]["layout"], vers[a]["layout"], d)
        rev.append({"from": b, "to": a, "compatible": d["compatible"], "diff": d,
                    "in_flight_changed": [x for x in inf if x["kind"] != "unchanged"]})
        if not d["compatible"]:
            gaps.append({"id": f"gap:M3:downgrade:{b}->{a}", "kind": "downgrade", "from": b, "to": a,
                         "retyped": [f"{r['contract']}.{r['label']}" for r in d["retyped"]],
                         "overlap": [f"{o['contract']}.{o['label']} meets {o['meets']['contract']}."
                                     f"{o['meets']['label']}" for o in d["overlap"]],
                         "removed": [f"{r['contract']}.{r['label']}" for r in d["removed"]],
                         "added": [f"{r['contract']}.{r['label']}" for r in d["added"]], **gap_meta("downgrade", root)})
    return {"reverse": rev, "gaps": gaps}


def _layout(root: Path, version: str) -> dict:
    return {f"{e['contract']}.{e['label']}": e for e in next(v for v in history(root)["versions"]
                                                            if v["id"] == version)["layout"]}


def _word(n: int) -> bytes:
    return (n % (1 << 256)).to_bytes(32, "big")


def inflight_words(root: Path, a: str, b: str, key: int | None) -> list:
    """V8: the storage words a legacy state at version a must hold nonzero for edge a -> b to be inhabited: for every
    in-flight entry of the edge whose kind is retyped or reinterpreted, [{"entry", "reads", "slot", "base", "offset",
    "path"}] for each word of each entry it reads that the change touches: a scalar's slot; for a mapping whose value
    is a struct, the slots (keccak256(key . slot) + member slot) of the members of the read entry whose (label, slot,
    offset, type) the new entry's struct does not have at the same member slot, at the given key (the key of the
    trace's last commit); for any other mapping, its value slot at the key. "slot" is the real slot; (base, offset,
    path) is its layout coordinate: the family's base slot, the offset in the top-level variable (0 here) and the
    mapping steps [[key, member slot]] ([] for a scalar). Sorted by (entry, slot)."""
    from tests_m2._keccak import keccak256
    la, lb = _layout(root, a), _layout(root, b)
    e = next(x for x in edges(root)["edges"] if (x["from"], x["to"]) == (a, b))
    out = []
    for x in e["in_flight"]:
        if x["kind"] == "unchanged":
            continue
        new = lb[x["entry"]]
        for r in x["reads"]:
            old = la[r]
            t = old["type"]
            if t.get("encoding") != "mapping":
                out.append({"entry": x["entry"], "reads": r, "slot": old["slot"], "base": old["slot"], "offset": 0,
                            "path": []})
                continue
            if key is None:
                raise ValueError(f"{x['entry']}: a mapping entry needs the key of the trace's last commit")
            base = int.from_bytes(keccak256(_word(key) + _word(old["slot"])), "big")
            ov, nv = t["value"], (new["type"].get("value") or {})
            if "members" in ov:
                newm = {(m["slot"], m["offset"]): m for m in nv.get("members") or []}
                for m in ov["members"]:
                    n = newm.get((m["slot"], m["offset"]))
                    if n is None or (n["label"], n["type"]) != (m["label"], m["type"]):
                        out.append({"entry": x["entry"], "reads": f"{r}.{m['label']}",
                                    "slot": (base + m["slot"]) % (1 << 256), "base": old["slot"], "offset": 0,
                                    "path": [[key, m["slot"]]]})
            else:
                out.append({"entry": x["entry"], "reads": r, "slot": base, "base": old["slot"], "offset": 0,
                            "path": [[key, 0]]})
    return sorted(out, key=lambda w: (w["entry"], w["slot"], w["reads"]))


def commit_key(calldata: str) -> int:
    """V8: the batch index a successor-site call commits: its first argument is BatchDataInput (at every path version a
    tuple whose first two fields are uint8 version and bytes parentBatchHeader), and the index is the parent header's
    (bytes 1..8, big-endian) plus one."""
    cd = bytes.fromhex(calldata[2:] if calldata.startswith("0x") else calldata)[4:]
    t = int.from_bytes(cd[0:32], "big")
    tup = cd[t:]
    off = int.from_bytes(tup[32:64], "big")
    n = int.from_bytes(tup[off:off + 32], "big")
    header = tup[off + 32:off + 32 + n]
    return int.from_bytes(header[1:9], "big") + 1


_ARRAY = re.compile(r"^(.*)\[(\d*)\]$")


def _abi_dynamic(p: dict) -> bool:
    m = _ARRAY.match(p["type"])
    if m:
        return m.group(2) == "" or _abi_dynamic(dict(p, type=m.group(1)))
    if p.get("fields"):
        return any(_abi_dynamic(f) for f in p["fields"])
    return p["type"] in ("bytes", "string")


def _abi_size(p: dict) -> int:
    """The bytes a static parameter takes in place."""
    m = _ARRAY.match(p["type"])
    if m:
        return int(m.group(2)) * _abi_size(dict(p, type=m.group(1)))
    if p.get("fields"):
        return sum(_abi_size(f) for f in p["fields"])
    return 32


def _abi_read(data: bytes, at: int, n: int) -> bytes:
    if at < 0 or at + n > len(data):
        raise ValueError(f"calldata ends at {len(data)}: no {n} bytes at {at}")
    return data[at:at + n]


def _abi_tuple(ps: list, data: bytes, base: int) -> list:
    out, head = [], base
    for p in ps:
        if _abi_dynamic(p):
            out += _abi_value(p, data, base + int.from_bytes(_abi_read(data, head, 32), "big"))
            head += 32
        else:
            out += _abi_value(p, data, head)
            head += _abi_size(p)
    return out


def _abi_value(p: dict, data: bytes, at: int) -> list:
    m = _ARRAY.match(p["type"])
    if m:
        el = dict(p, type=m.group(1))
        if m.group(2) == "":
            n = int.from_bytes(_abi_read(data, at, 32), "big")
            if n > (len(data) - at - 32) // 32:       # every element takes at least one word in place
                raise ValueError(f"an array of {n} elements at {at} does not fit the calldata")
            xs = _abi_tuple([el] * n, data, at + 32)
        else:
            xs = _abi_tuple([el] * int(m.group(2)), data, at)
        return xs or [["nil"]]
    if p.get("fields"):
        return _abi_tuple(p["fields"], data, at)
    if p["type"] in ("bytes", "string"):
        n = int.from_bytes(_abi_read(data, at, 32), "big")
        b = _abi_read(data, at + 32, n)
        return [["b", b.hex()]] if b else [["nil"]]
    return [["w", int.from_bytes(_abi_read(data, at, 32), "big")]]


def abi_leaves(params: list, calldata: str) -> list:
    """V8: the leaves of a call's arguments, decoded from its calldata (the 4-byte selector aside) by the ABI types of a
    transitions document's params ({"name", "type", "fields" for a struct}), in parameter order and a struct's fields in
    declaration order: ["w", n] for a value type (n the 32-byte word of its encoding), ["b", hex] for non-empty bytes or
    string, ["nil"] for empty bytes, string or array; an array's leaves are its elements' leaves in order. A calldata
    too short for its types raises ValueError."""
    data = bytes.fromhex(calldata[2:] if calldata.startswith("0x") else calldata)
    if len(data) < 4:
        raise ValueError("calldata has no selector")
    return _abi_tuple(params, data[4:], 0)


def limbs(n: int) -> list:
    """A word as the model's eight little-endian 32-bit limbs (the argument of w_of_limbs)."""
    n %= 1 << 256
    return [(n >> (32 * i)) & 0xFFFFFFFF for i in range(8)]


# ---------------------------------------------------------------------------------------------------- PI1-PI5
def _i26():
    import tests_m3._i26 as I26
    return I26


def _authenticated_inputs(a: dict, F: str) -> list:
    """The input bytes X of every authenticating guard reach of F in action a (I26 F1: a top-level conjunct
    ["==", ["map", ["storage", F], k], H] or its mirror, H a hash term) whose hash term hashes X itself (not a memory
    region): [(the reach's "guards[i].reaches[j]", k, X)], in reach order."""
    I26 = _i26()
    out = []
    for gi, ri, _seq, key in I26.authenticating(a, F):
        expr = a["guards"][gi]["reaches"][ri]["expr"]
        for c in conjuncts(expr):
            if not (is_op(c, "==") and len(c) == 3):
                continue
            for R, H in ((c[1], c[2]), (c[2], c[1])):
                if (is_op(R, "map") and len(R) == 3 and R[1] == ["storage", F] and is_op(H) and H[0] in HASHES
                        and len(H) == 2 and not is_op(H[1], "slice")):
                    out.append((f"guards[{gi}].reaches[{ri}]", key, H[1]))
    return out


def _region_cells(value) -> dict | None:
    """{offset: value term} of the mstores at literal offsets of the memory region a commitment write hashes
    (["keccak256" | "sha256", ["slice", ["mem", write..], off, len]]), the last write to an offset winning; None when the
    value hashes no memory region."""
    if not (is_op(value) and value[0] in HASHES and len(value) == 2 and is_op(value[1], "slice")
            and is_op(value[1][1], "mem")):
        return None
    cells = {}
    for w in value[1][1][1:]:
        if is_op(w, "mstore") and len(w) == 3 and isinstance(w[1], int) and not isinstance(w[1], bool):
            cells[w[1]] = w[2]
    return cells


def _shifted(v):
    """(V, s) when a cell value is ["<<", V, s] with s a literal, else None."""
    if is_op(v, "<<") and len(v) == 3 and isinstance(v[2], int) and not isinstance(v[2], bool):
        return norm(v[1]), v[2]
    return None


def chains(doc_path: Path, rel: str | None = None) -> dict:
    """PI1-PI3 over one transitions document: {"contract", "families": [{"family", "root_sites": [{"action", "at"}],
    "successor_sites": [{"action", "at", "auth", "parent"}], "pairs": [{"cell", "incr", "shift"}]}]} sorted by family,
    sites by (action, at), pairs by (cell, incr). A family appears only when it is a commitment (I26 F1/F2) with at least
    one root site and one successor site.
      root site:      a commitment site (I26 F2) in an action with no authenticating guard reach of F, whose committed
                      value hashes input bytes ["keccak256" | "sha256", X], X not a memory region;
      successor site: a commitment site in an action with an authenticating guard reach of F at key k over input bytes P
                      (["==", ["map", ["storage", F], k], [hash, P]]), whose committed value hashes a memory region;
      chained pair:   (o, o', s) such that, in every successor site's region, the cell at offset o is ["<<", V, s] with
                      norm(V) = ["+", R, Y] or ["+", Y, R], R = [">>", ["word", P, o], s] (that site's parent read of
                      the same cell) and the cell at offset o' != o is ["<<", Y', s] with norm(Y') = Y. A cell chained
                      with a literal increment (Y an integer) gives no pair."""
    I26 = _i26()
    doc = I26.Doc(Path(doc_path), rel)
    fams = []
    for c in I26.commitments(doc):
        F = c["family"]
        roots, succs, per_site = [], [], []
        for s in c["sites"]:
            a = doc.by[s["action"]]
            w = a["writes"][int(s["at"][len("writes["):-1])]
            auth = _authenticated_inputs(a, F)
            v = w["value"]
            if not auth:
                if is_op(v) and v[0] in HASHES and len(v) == 2 and not is_op(v[1], "slice"):
                    roots.append({"action": s["action"], "at": s["at"]})
                continue
            cells = _region_cells(v)
            if cells is None:
                continue
            at, _key, P = auth[0]
            succs.append({"action": s["action"], "at": s["at"], "auth": at, "parent": P})
            pairs = set()
            for o, val in cells.items():
                sv = _shifted(val)
                if sv is None:
                    continue
                V, sh = sv
                if not is_op(V, "+") or len(V) != 3:
                    continue
                R = [">>", ["word", P, o], sh]
                for x, y in ((V[1], V[2]), (V[2], V[1])):
                    if x != R or isinstance(y, int):
                        continue
                    for o2, val2 in cells.items():
                        sv2 = _shifted(val2)
                        if o2 != o and sv2 is not None and sv2[1] == sh and sv2[0] == y:
                            pairs.add((o, o2, sh))
            per_site.append(pairs)
        if not roots or not succs:
            continue
        common = set.intersection(*per_site) if per_site else set()
        fams.append({"family": F, "root_sites": sorted(roots, key=lambda r: (r["action"], r["at"])),
                     "successor_sites": sorted(succs, key=lambda r: (r["action"], r["at"])),
                     "pairs": [{"cell": o, "incr": o2, "shift": sh} for o, o2, sh in sorted(common)]})
    return {"contract": doc.contract, "families": sorted(fams, key=lambda f: f["family"])}


def law_id(contract: str, root_action: str, family: str, pair: dict) -> str:
    """PI4: L_pinit_<contract>_<root action>_<family>_<cell>_<incr>."""
    return f"L_pinit_{contract}_{root_action}_{family}_{pair['cell']}_{pair['incr']}"


def init_id(model: str, family: str, pair: dict) -> str:
    """PI4: the init term's id <model>:chain:<family>:<cell>:<incr>."""
    return f"{model}:chain:{family}:{pair['cell']}:{pair['incr']}"


def par_init(docs: dict, model: str = "morph_rollup.versions") -> dict:
    """PI4 over the versioned documents {version: (path, rel)}: {"versions": {version: chains(..)}, "basis": [{"family",
    "root_action", "cell", "incr", "shift", "versions": the versions whose chains hold the pair with that root action,
    "law_id", "init_id"}]} sorted by law id. One basis element per (family, root action, pair) found in any version."""
    per = {v: chains(p, rel) for v, (p, rel) in sorted(docs.items())}
    found = {}
    for v, ch in per.items():
        for f in ch["families"]:
            for r in f["root_sites"]:
                for pr in f["pairs"]:
                    k = (ch["contract"], f["family"], r["action"], pr["cell"], pr["incr"], pr["shift"])
                    found.setdefault(k, []).append(v)
    basis = []
    for (contract, F, ra, o, o2, sh), vs in found.items():
        pr = {"cell": o, "incr": o2, "shift": sh}
        basis.append({"family": F, "root_action": ra, "cell": o, "incr": o2, "shift": sh,
                      "versions": sorted(vs, key=_vkey), "law_id": law_id(contract, ra, F, pr),
                      "init_id": init_id(model, F, pr)})
    return {"versions": per, "basis": sorted(basis, key=lambda b: b["law_id"])}


def _vkey(v: str):
    return (int(v[1:]) if v[1:].isdigit() else 10 ** 9, v)


def _call_terms(t, out: list) -> None:
    if is_op(t) and t[0] in ("call", "callok") and len(t) > 1 and isinstance(t[1], str):
        out.append(t)
    if isinstance(t, list):
        for x in t:
            _call_terms(x, out)


def link_gaps(doc_path: Path, ch: dict | None = None) -> list:
    """PI5 over one transitions document: [{"id": "gap:M3:link:<family>:<cell>:<interface>", "kind": "link", "family",
    "cell", "incr", "interface", "sites": [{"action", "at", "fn"}], "obligation", "question", "status"}] (gap_meta) for
    every chained pair (chains(..)) and every
    interface I such that some calls[i] record of an action that authenticates input bytes X against the family carries,
    among the arguments of a ["call" | "callok", "<I>.<f>", ..] term of its expr, X's read of the chained cell
    ([">>", ["word", X, o], s]); sorted by (family, cell, interface), sites by (action, at)."""
    I26 = _i26()
    doc = I26.Doc(Path(doc_path))
    ch = ch if ch is not None else chains(doc_path)
    out = []
    for f in ch["families"]:
        F = f["family"]
        for pr in f["pairs"]:
            by_if = {}
            for a in doc.actions:
                reads = [[">>", ["word", X, pr["cell"]], pr["shift"]] for _, _, X in _authenticated_inputs(a, F)]
                if not reads:
                    continue
                for i, c in enumerate(a.get("calls") or []):
                    terms = []
                    _call_terms(c.get("expr"), terms)
                    for t in terms:
                        if any(contains(t[2:], r) for r in reads):
                            iface = t[1].split(".", 1)[0]
                            by_if.setdefault(iface, set()).add((a["name"], f"calls[{i}]", t[1]))
            for iface in sorted(by_if):
                out.append({"id": f"gap:M3:link:{F}:{pr['cell']}:{iface}", "kind": "link", "family": F,
                            "cell": pr["cell"], "incr": pr["incr"], "interface": iface,
                            "sites": [{"action": n, "at": at, "fn": fn} for n, at, fn in sorted(by_if[iface])],
                            **gap_meta("link")})
    return out


def analysis_doc(docs: dict, gaps: list) -> dict:
    """The PAR-init analysis holon versions analyze must write (gen/M3/versions/par_init.json), over the versioned
    documents {version: (path, rel)} and the downgrade gaps (reverse(..)["gaps"]): {"analysis_version":
    "holon-par-init/0.1", "versions": {version: chains}, "basis": PI4's, "link_gaps": PI5's merged over the versions
    [{"id", "kind", "family", "cell", "incr", "interface", "obligation", "question", "status", "sites": {version:
    [{"action", "at", "fn"}]}}] sorted by id,
    "downgrade_gaps": gaps}."""
    pi = par_init(docs)
    merged = {}
    for v, (p, _rel) in sorted(docs.items(), key=lambda kv: _vkey(kv[0])):
        for g in link_gaps(p, pi["versions"][v]):
            m = merged.setdefault(g["id"], {k: g[k] for k in ("id", "kind", "family", "cell", "incr", "interface",
                                                              "obligation", "question", "status")})
            m.setdefault("sites", {})[v] = g["sites"]
    return {"analysis_version": "holon-par-init/0.1", "versions": pi["versions"], "basis": pi["basis"],
            "link_gaps": [merged[k] for k in sorted(merged)], "downgrade_gaps": gaps}


# ---------------------------------------------------------------------------------------------------- PI6
def cell(header: bytes, o: int, s: int) -> int:
    """A header cell: the 32-byte word at offset o (zero-padded past the end) shifted right by s bits."""
    w = bytes(header[o:o + 32])
    w += bytes(32 - len(w))
    return int.from_bytes(w, "big") >> s


def root_witness_problems(header: bytes, b: dict) -> list:
    """PI6 on the input bytes a PAR-init witness's root step hashes: the chained cell differs from its increment cell
    (the law's claim fails on them). [] when it does."""
    c, i = cell(header, b["cell"], b["shift"]), cell(header, b["incr"], b["shift"])
    return [] if c != i else [f"cell {b['cell']} ({c}) equals cell {b['incr']} ({i}): the claim holds on this header"]


# ---------------------------------------------------------------------------------------------------- S1-S3
RENAME = {"Rollup": "Ledger", "importGenesisBatch": "seedChain", "committedBatches": "sealedHeaders"}


def _rename(x, m: dict):
    if isinstance(x, str):
        return m.get(x, x)
    if isinstance(x, list):
        return [_rename(y, m) for y in x]
    if isinstance(x, dict):
        return {k: _rename(v, m) for k, v in x.items()}
    return x


def planted(kind: str, root: Path = ROOT) -> dict:
    """The planted documents of S1-S3, made from the adopted head document:
      "renamed"   every JSON string equal to a key of RENAME (the contract, the root action, the commitment family)
                  replaced by its value;
      "no_chain"  in every successor site's committed value (PI1, over the head document), each chained cell's sum
                  ["+", R, Y] (or ["+", Y, R]) at its offset replaced by ["+", R, 1]: a literal step;
      "no_root"   the root sites' actions removed from "actions"."""
    root = Path(root)
    d = load(root / HEAD_DOC)
    if kind == "renamed":
        return _rename(d, RENAME)
    ch = chains(root / HEAD_DOC, HEAD_DOC)
    if kind == "no_root":
        gone = {r["action"] for f in ch["families"] for r in f["root_sites"]}
        d["actions"] = [a for a in d["actions"] if a["name"] not in gone]
        return d
    if kind != "no_chain":
        raise ValueError(f"unknown planted document {kind!r}")
    by = {a["name"]: a for a in d["actions"]}
    for f in ch["families"]:
        for s in f["successor_sites"]:
            w = by[s["action"]]["writes"][int(s["at"][len("writes["):-1])]
            P = s["parent"]
            mem = w["value"][1][1]
            for i, x in enumerate(mem):
                if not (is_op(x, "mstore") and len(x) == 3 and isinstance(x[1], int)):
                    continue
                for pr in f["pairs"]:
                    if x[1] != pr["cell"]:
                        continue
                    R = [">>", ["word", P, pr["cell"]], pr["shift"]]
                    mem[i] = ["mstore", x[1], ["<<", ["+", R, 1], pr["shift"]]]
    return d


# ---------------------------------------------------------------------------------------------------- the basis
def basis_inputs(root: Path = ROOT) -> list:
    """The files versions_basis_doc reads, with their sha256 (the code files of the matched upgrades included)."""
    root = Path(root)
    rels = [HISTORY, TIMELINE, HEAD_DOC, "spec/M3/lib/versions.json", "tests_m3/_i26.py", "tests_m3/_i63.py"]
    rels += sorted(f"{CODE_DIR}/{d['implementation']}.hex" for d in deployments(root))
    return [{"path": r, "sha256": sha256_file(root / r)} for r in sorted(set(rels))]


def versions_basis_doc(root: Path = ROOT) -> dict:
    """V1-V4 over I63's committed outputs, and PI1-PI5 over the adopted head document (the code of the path's last
    version, whose per-version document the build writes): the content of spec/M3/lib/versions_basis.json without its
    doc field."""
    root = Path(root)
    p = path(root)
    e = edges(root)
    rv = reverse(root)
    ch = chains(root / HEAD_DOC, HEAD_DOC)
    head = {"document": HEAD_DOC, "chains": ch, "link_gaps": link_gaps(root / HEAD_DOC, ch)}
    return {"basis_version": BASIS_VERSION, "inputs": basis_inputs(root), "path": p["path"],
            "never_deployed": p["never_deployed"], "unmatched": p["unmatched"], "deployments": deployments(root),
            "entry": e["entry"], "edges": e["edges"], "in_flight_types": inflight_types(root),
            "reverse": rv["reverse"], "downgrade_gaps": rv["gaps"], "head": head}


def write_basis(root: Path = ROOT) -> None:
    doc = versions_basis_doc(root)
    old = load(BASIS) if BASIS.exists() else {}
    doc["doc"] = old.get("doc", "")
    BASIS.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="python -m tests_m3._i28")
    ap.add_argument("--write", action="store_true", help="recompute spec/M3/lib/versions_basis.json (prereg only)")
    a = ap.parse_args(argv)
    if a.write:
        write_basis(ROOT)
        print(f"wrote {BASIS.relative_to(ROOT)}")
        return 0
    print(json.dumps(versions_basis_doc(ROOT), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
