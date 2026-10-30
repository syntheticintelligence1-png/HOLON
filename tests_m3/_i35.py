"""I35's instrument, fixed at the prereg (do not edit: a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl). Rules W1-W5 of tests_m3/test_own.py (rule OWN over the extracted Go document's backing
identities: carriers, views, writers, lost writes, the laws), written out a second time, independently of holon/, plus
Go 1.24's slice growth (runtime/slice.go nextslicecap, runtime/msize.go roundupsize over runtime/sizeclasses.go's
class_to_size, for byte slices) and the BatchData traces the predictions name. Standard library only; deterministic.

W1 Methods. A function of the document whose id is "(T).M" or "(*T).M" is a method M of the named type T (the package
   path, a dot, the type name); its receiver is its first parameter.
W2 Views. A case of a method's slice result whose backing is ["of", ["field", ["param", R], F]], R the receiver's
   name: the view (M, F) of T, region [offset, offset + len) of F's backing in the receiver's state, under the case's
   cond.
W3 Writers. An entry of go.slices.writes whose function is a method of T and whose backing is ["of", ["field",
   ["param", R], G]], R the receiver's name: an in-place write of the method into G's backing, region [from, to), under
   its cond. The writer methods of T are the methods with at least one such entry.
W4 Alias laws. One per (view method V, writer method W) of the same type T, V == W included, such that W writes in
   place the field some view of V returns (an E2 relation: written via W, read via V): L_own_alias_<pkg>_<T>_<V>_<W>
   (<pkg> the last element of T's package path, <T> its type name). A writer of another field is no law of V: the
   model's invariant that distinct fields never share a backing covers it.
W5 Lost-write laws. One per entry (m, receiver b, field F) of go.slices.lost_writes whose method m has a value
   receiver of type T and some method of T reads F through its receiver (an occurrence of ["field", ["param", R], F],
   R that method's receiver, in a case cond, backing, len, cap or offset of one of its slice results):
   L_own_lost_<pkg>_<T>_<m>_<F>. A lost write with no such read is a gap (no law).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GO_DOC = "spec/M3/facts/morph_blob.go.extracted.json"
GO_METHOD = re.compile(r"\((\*?)([^()]*)\)\.([A-Za-z_][A-Za-z0-9_]*)")

# Go 1.24 runtime/sizeclasses.go class_to_size (the pinned go1.24.7 toolchain)
CLASS_TO_SIZE = (0, 8, 16, 24, 32, 48, 64, 80, 96, 112, 128, 144, 160, 176, 192, 208, 224, 240, 256, 288, 320, 352,
                 384, 416, 448, 480, 512, 576, 640, 704, 768, 896, 1024, 1152, 1280, 1408, 1536, 1792, 2048, 2304, 2688,
                 3072, 3200, 3456, 4096, 4864, 5376, 6144, 6528, 6784, 6912, 8192, 9472, 9728, 10240, 10880, 12288,
                 13568, 14336, 16384, 18432, 19072, 20480, 21760, 24576, 27264, 28672, 32768)
PAGE = 8192


def load(p) -> dict:
    return json.loads((ROOT / p).read_text(encoding="utf-8")) if not Path(p).is_absolute() else \
        json.loads(Path(p).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ Go 1.24 growth
def nextslicecap(new_len: int, old_cap: int) -> int:
    newcap = old_cap
    doublecap = newcap + newcap
    if new_len > doublecap:
        return new_len
    if old_cap < 256:
        return doublecap
    while True:
        newcap += (newcap + 3 * 256) >> 2
        if newcap >= new_len:
            return newcap


def roundupsize(size: int) -> int:
    """A noscan allocation's size (byte slices carry no pointers: no malloc header)."""
    if size <= CLASS_TO_SIZE[-1]:
        for c in CLASS_TO_SIZE:
            if c >= size:
                return c
    return (size + PAGE - 1) // PAGE * PAGE


def append_cap(old_len: int, old_cap: int, k: int) -> tuple[int, bool]:
    """(the capacity after appending k bytes to a slice of length old_len and capacity old_cap, whether it was in
    place): in place when old_len + k <= old_cap, else growslice's new capacity."""
    if old_len + k <= old_cap:
        return old_cap, True
    return roundupsize(nextslicecap(old_len + k, old_cap)), False


# ------------------------------------------------------------------------------------------------ W1-W5
def method(fid: str):
    """(type, method name, pointer receiver) of a method id, else None."""
    m = GO_METHOD.fullmatch(fid)
    return (m.group(2), m.group(3), m.group(1) == "*") if m else None


def receiver(go: dict, fid: str) -> str | None:
    ps = (go["functions"].get(fid) or {}).get("params") or []
    return ps[0]["name"] if ps else None


def _field_of(backing, recv: str):
    if isinstance(backing, list) and len(backing) == 2 and backing[0] == "of":
        t = backing[1]
        if isinstance(t, list) and len(t) == 3 and t[0] == "field" and t[1] == ["param", recv]:
            return t[2]
    return None


def views(go: dict) -> list[dict]:
    out = []
    for r in go["slices"]["results"]:
        fid = r["function"]
        mt = method(fid)
        if mt is None:
            continue
        recv = receiver(go, fid)
        for i, c in enumerate(r["cases"]):
            f = _field_of(c["backing"], recv)
            if f is not None:
                out.append({"type": mt[0], "method": mt[1], "function": fid, "field": f, "case": i,
                            "result": r["result"]})
    return sorted(out, key=lambda v: (v["type"], v["method"], v["result"], v["case"]))


def writes(go: dict) -> list[dict]:
    out = []
    for w in go["slices"]["writes"]:
        fid = w["function"]
        mt = method(fid)
        if mt is None:
            continue
        f = _field_of(w["backing"], receiver(go, fid))
        if f is not None:
            out.append({"type": mt[0], "method": mt[1], "function": fid, "field": f, "site": w["site"]})
    return sorted(out, key=lambda w: (w["type"], w["method"], w["site"]))


def _occurs(t, target) -> bool:
    if t == target:
        return True
    if isinstance(t, list):
        return any(_occurs(x, target) for x in t)
    if isinstance(t, dict):
        return any(_occurs(x, target) for x in t.values())
    return False


def readers(go: dict, typ: str, field: str) -> list[str]:
    """The methods of typ that read field through their receiver in a slice result's case (W5)."""
    out = set()
    for r in go["slices"]["results"]:
        fid = r["function"]
        mt = method(fid)
        if mt is None or mt[0] != typ:
            continue
        target = ["field", ["param", receiver(go, fid)], field]
        if any(_occurs([c.get(k) for k in ("cond", "backing", "len", "cap", "offset")], target) for c in r["cases"]):
            out.add(mt[1])
    return sorted(out)


def lost_writes(go: dict) -> list[dict]:
    out = []
    for e in go["slices"]["lost_writes"]:
        mt = method(e["function"])
        if mt is None or mt[2]:
            continue
        field = e["field"][0] if isinstance(e["field"], list) and len(e["field"]) == 1 else None
        if field is None:
            continue
        out.append({"type": mt[0], "method": mt[1], "function": e["function"], "field": field, "site": e["site"],
                    "readers": readers(go, mt[0], field)})
    return sorted(out, key=lambda x: (x["type"], x["method"], x["field"]))


def short(typ: str) -> tuple[str, str]:
    pkg, name = typ.rsplit(".", 1)
    return pkg.rsplit("/", 1)[-1], name


def laws(go: dict) -> dict:
    """law id -> {"subform", "type", ...} (W4, W5)."""
    out = {}
    vs, ws = views(go), writes(go)
    for typ in sorted({v["type"] for v in vs}):
        pkg, name = short(typ)
        vms = sorted({v["method"] for v in vs if v["type"] == typ})
        wms = sorted({w["method"] for w in ws if w["type"] == typ})
        for V in vms:
            vf = {v["field"] for v in vs if v["type"] == typ and v["method"] == V}
            for W in wms:
                if not vf & {w["field"] for w in ws if w["type"] == typ and w["method"] == W}:
                    continue
                out[f"L_own_alias_{pkg}_{name}_{V}_{W}"] = {
                    "subform": "alias", "type": typ, "view": V, "writer": W,
                    "view_fields": sorted({v["field"] for v in vs if v["type"] == typ and v["method"] == V}),
                    "writer_fields": sorted({w["field"] for w in ws if w["type"] == typ and w["method"] == W})}
    for lw in lost_writes(go):
        if not lw["readers"]:
            continue
        pkg, name = short(lw["type"])
        out[f"L_own_lost_{pkg}_{name}_{lw['method']}_{lw['field']}"] = {
            "subform": "lost_write", "type": lw["type"], "method": lw["method"], "field": lw["field"],
            "readers": lw["readers"], "site": lw["site"]}
    return dict(sorted(out.items()))


# ------------------------------------------------------------------------------------------------ the traces
def batchdata_alias_trace(contexts: int = 3, ctx_len: int = 60, payload: int = 1) -> dict:
    """The (TxsPayloadV2, Append) trace the predictions name, by Go 1.24's growth: `contexts` Appends of ctx_len-byte
    block contexts (and `payload`-byte payloads) from NewBatchData's empty slices, then TxsPayloadV2, then one more
    Append of a ctx_len-byte context. Returns the blockContexts (len, cap, in_place) after each Append, the view's
    region and whether TxsPayloadV2 appended in place, and the last Append's written region and whether it was in
    place."""
    ln, cap = 0, 0
    tl, tcap = 0, 0
    steps = []
    for _ in range(contexts):
        cap, inplace = append_cap(ln, cap, ctx_len)
        ln += ctx_len
        tcap, _tin = append_cap(tl, tcap, payload)
        tl += payload
        steps.append({"len": ln, "cap": cap, "in_place": inplace})
    v_in_place = ln + tl <= cap
    view = [0, ln + tl]
    cap2, last_in_place = append_cap(ln, cap, ctx_len)
    return {"appends": steps, "view": view, "view_in_place": v_in_place, "txs_len": tl,
            "last_write": [ln, ln + ctx_len], "last_in_place": last_in_place, "cap_after": cap2,
            "overlap": last_in_place and v_in_place and ln < view[1]}
