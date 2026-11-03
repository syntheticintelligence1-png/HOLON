"""The bases of the Go part of rule PAR (I93 = I38d; the contract is the docstring of tests_m3/test_go_laws.py, rules
G4-G6): go_round_trip, go_branch and go_recompute over the Go document the milestone's gox sidecar
(spec/<M>/lib/go_laws.json) names, its compression sidecar and the Solidity documents its recompute roles name.

Every name here comes from the sidecars and the documents: the hash primitive is the config's primitive of kind "hash",
the compressor is the compression sidecar's enc, and the recompute roles name their Go functions and Solidity store.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SIDECAR = "spec/{}/lib/go_laws.json"
NEG = {"<=": ">", ">": "<=", "<": ">=", ">=": "<", "==": "!=", "!=": "=="}
CONSTS = ("bool", "const", "nil", "str")


class GoxError(ValueError):
    pass


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class Ctx:
    """The milestone's gox inputs, each read once (through inputs when given, so derive records them)."""

    def __init__(self, root, milestone: str, inputs=None):
        self.root, self.milestone, self.inputs = Path(root), milestone, inputs
        self.side_rel = SIDECAR.format(milestone)
        self.side = self.read_json(self.side_rel)
        self.doc_rel = self.side["document"]
        self.doc_bytes = self.read_bytes(self.doc_rel)
        self.doc = json.loads(self.doc_bytes)
        self.config = self.read_json(self.side["config"])
        self.compression = self.read_json(self.side["compression"])

    def read_bytes(self, rel: str) -> bytes:
        p = self.root / rel
        if not p.is_file():
            raise GoxError(f"{rel} is missing")
        if self.inputs is not None:
            self.inputs.read(p)
        return p.read_bytes()

    def read_json(self, rel: str):
        return json.loads(self.read_bytes(rel))

    @property
    def fns(self) -> dict:
        return self.doc["go"]["functions"]

    def hash_prims(self) -> set:
        return {n for n, p in (self.config.get("primitives") or {}).items() if p.get("kind") == "hash"}


def has_sidecar(root, milestone: str) -> bool:
    return (Path(root) / SIDECAR.format(milestone)).is_file()


def short(fn: str) -> str:
    """G7: "(*pkg.T).M" and "(pkg.T).M" -> "T_M"; "pkg.F" -> "F"."""
    if fn.startswith("("):
        recv, meth = fn[1:].split(").", 1)
        return recv.lstrip("*").rsplit(".", 1)[1] + "_" + meth
    return fn.rsplit(".", 1)[1]


# ====================================================================== go_round_trip (G4)
def _accepted(f: dict) -> int | None:
    """The one length every non-error return path of a one-parameter decoder requires of its parameter."""
    par = f["params"][0]["name"]
    out = set()
    for p in f.get("paths") or []:
        if p.get("end") != "return" or p.get("error") != "nil":
            continue
        ls = {c[2][1] for c in p["cond"] if isinstance(c, list) and len(c) == 3 and c[0] == "=="
              and c[1] == ["len", ["param", par]] and isinstance(c[2], list) and c[2][:1] == ["const"]}
        if len(ls) != 1:
            return None
        out |= ls
    return out.pop() if len(out) == 1 else None


def _single(cells: list, w: int):
    """The value v when cells are ["byte", v, 0..w-1], else None."""
    if len(cells) != w or not all(isinstance(c, list) and c[:1] == ["byte"] for c in cells):
        return None
    vs = {canon(c[1]) for c in cells}
    if len(vs) != 1 or [c[2] for c in cells] != list(range(w)):
        return None
    return cells[0][1]


def inputs_of(cells: list) -> list:
    """The entry's input values in first-cell order: [{"value", "width"}], width the number of its cells."""
    order, width = [], {}
    for c in cells:
        if isinstance(c, list) and c[:1] == ["byte"]:
            k = canon(c[1])
            if k not in width:
                order.append(c[1])
                width[k] = 0
            width[k] = max(width[k], c[2] + 1)
    return [{"value": v, "width": width[canon(v)]} for v in order]


def round_trips(cx: Ctx) -> list:
    cod, fs = cx.doc["go"]["codecs"], cx.fns
    versioned = {e for m in cod.get("matches") or [] for e in m["encoders"]}
    tagged = {fs[p["function"]]["params"][0]["type"] for p in cod.get("predicates") or [] if p["function"] in fs}
    entries: dict = {}
    for e in cod.get("encoders") or []:
        entries.setdefault(e["function"], []).append(e)
    out = []
    for dec in sorted(cod.get("decoders") or [], key=lambda d: d["function"]):
        f = fs.get(dec["function"])
        if f is None or len(f["params"]) != 1 or f["params"][0]["type"] in tagged:
            continue
        length = _accepted(f)
        if length is None:
            continue
        for enc in sorted(entries):
            if enc in versioned:
                continue
            for k, e in enumerate(entries[enc]):
                if e["length"] != length or not e.get("exact"):
                    continue
                reads = []
                for r in dec["reads"]:
                    v = _single(e["cells"][r["offset"]:r["offset"] + r["width"]], r["width"])
                    reads.append({"offset": r["offset"], "width": r["width"], "via": r["via"], "value": v})
                lid = f"L_par_gort_{short(enc)}_{short(dec['function'])}_{k}"
                basis = {"kind": "go_round_trip", "encoder": enc, "entry": k, "decoder": dec["function"],
                         "length": length, "conds": e.get("conds") or [], "cells": e["cells"], "reads": reads,
                         "inputs": inputs_of(e["cells"]), "encoder_params": fs[enc]["params"] if enc in fs else []}
                el = {"law_id": lid, "subform": "go_round_trip", "words": [short(enc), short(dec["function"]), str(k)],
                      "basis": basis}
                if any(r["value"] is None for r in reads):
                    el["reason"] = "mixed_read"
                out.append(el)
    return out


# ====================================================================== go_branch (G5)
def _calls(t, acc: set) -> set:
    if isinstance(t, list):
        if len(t) > 2 and t[0] == "result" and isinstance(t[1], list) and t[1][:1] == ["call"]:
            acc.add(canon(t[1]))
        for x in t:
            _calls(x, acc)
    return acc


def lengths_of(x) -> list:
    out = [["len", x]]
    if isinstance(x, list) and x[:1] == ["slice"] and len(x) == 5 and x[3] is not None:
        out.append(["op", "-", x[3], x[2] if x[2] is not None else ["const", 0]])
    return out


def _const(t) -> bool:
    return isinstance(t, list) and bool(t) and t[0] in CONSTS


def _size_value(t, g: str, x, bound) -> bool:
    return isinstance(t, list) and len(t) == 3 and t[0] in (">", ">=") and t[2] == bound \
        and t[1] == ["len", ["result", ["call", g, [x]], 0]]


def _pairs(fn: str, f: dict) -> list:
    out = []
    ps = f.get("paths") or []
    for i, p in enumerate(ps):
        if p.get("end") != "return" or p.get("error") != "nil" or not p.get("returns") \
                or not all(_const(r) for r in p["returns"]):
            continue
        for j, q in enumerate(ps):
            if j == i or q.get("end") != "return" or q.get("error") != "nil" or not q.get("returns"):
                continue
            diff = [c for c in p["cond"] if c not in q["cond"]]
            if len(diff) != 1:
                continue
            c = diff[0]
            if not (isinstance(c, list) and len(c) == 3 and c[0] in ("<=", "<")) or [NEG[c[0]]] + c[1:] not in q["cond"]:
                continue
            new = _calls(q["cond"], set()) | _calls(q["returns"], set())
            new -= _calls(p["cond"], set()) | _calls(p["returns"], set())
            for cj in sorted(new):
                call = json.loads(cj)
                if len(call[2]) != 1 or c[1] not in lengths_of(call[2][0]):
                    continue
                pos = [k for k, r in enumerate(q["returns"]) if _size_value(r, call[1], call[2][0], c[2])]
                if not pos:
                    continue
                shared = [x for x in p["cond"] if x != c]
                extra = [x for x in q["cond"] if x not in shared and x != [NEG[c[0]]] + c[1:]]
                out.append({"function": fn, "p": i, "q": j, "position": pos[0], "test": c, "call": call[1],
                            "arg": call[2][0], "bound": c[2], "shared": shared, "extra": extra,
                            "p_value": p["returns"][pos[0]], "q_value": q["returns"][pos[0]]})
    return out


def delegates(cx: Ctx) -> dict:
    """{callee: conds}: the compression sidecar's enc itself (no condition) and each call enc makes on its parameter and
    returns as its own result on a non-error path (on that path's conditions)."""
    enc = cx.compression["codec"]["enc"]
    out = {enc: []}
    f = cx.fns.get(enc)
    if f is None:
        return out
    par = f["params"][0]["name"] if f["params"] else None
    for p in f.get("paths") or []:
        r = (p.get("returns") or [None])[0]
        if p.get("end") == "return" and p.get("error") == "nil" and isinstance(r, list) and r[:1] == ["result"] \
                and r[2] == 0 and r[1][:1] == ["call"] and r[1][2] == [["param", par]]:
            out[r[1][1]] = p["cond"]
    return out


def branches(cx: Ctx) -> list:
    fs = cx.fns
    raw = {fn: _pairs(fn, f) for fn, f in sorted(fs.items())}
    callees: dict = {}
    for e in (cx.doc["go"].get("calls") or {}).get("edges") or []:
        if e.get("callee_kind") == "analyzed":
            callees.setdefault(e["caller"], set()).add(e["callee"])
    dele = delegates(cx)
    out = []
    for fn in sorted(raw):
        for r in raw[fn]:
            if any(r["call"] in {x["call"] for x in raw.get(g, [])} for g in callees.get(fn, ()) if g != fn):
                continue   # G5: the pair belongs to an analyzed callee that F inlines
            lid = f"L_par_gobr_{short(fn)}_p{r['p']}_p{r['q']}"
            basis = {"kind": "go_branch", **r, "params": fs[fn]["params"],
                     "hypz_len": ({"enc": cx.compression["codec"]["enc"], "via": r["call"],
                                   "cb": cx.side["hypz_len"]["cb"], "from": cx.side["hypz_len"]["from"],
                                   "delegate_conds": dele[r["call"]]} if r["call"] in dele else None)}
            out.append({"law_id": lid, "subform": "go_branch", "words": [short(fn), f"p{r['p']}", f"p{r['q']}"],
                        "basis": basis})
    return out


# ====================================================================== go_recompute (G6)
def _has(t, tag: str) -> bool:
    if isinstance(t, list):
        if t[:1] == [tag]:
            return True
        return any(_has(x, tag) for x in t)
    return False


def _hash_returns(f: dict, hp: set) -> list:
    """[(path, loop body or None)] of the non-error returns whose first value is a hash primitive's call."""
    out = []
    for p in f.get("paths") or []:
        r = (p.get("returns") or [None])[0]
        if p.get("end") == "return" and isinstance(r, list) and r[:1] == ["call"] and r[1] in hp:
            out.append((p, None))
    for lb in f.get("loop_bodies") or []:
        for p in lb.get("paths") or []:
            r = (p.get("returns") or [None])[0]
            if p.get("end") == "return" and isinstance(r, list) and r[:1] == ["call"] and r[1] in hp:
                out.append((p, lb))
    return out


def recomputes(cx: Ctx) -> list:
    out = []
    hp = cx.hash_prims()
    for role, spec in sorted((cx.side.get("recompute") or {}).items()):
        so = spec["solidity"]
        sdoc = cx.read_json(so["document"])
        act = next((a for a in sdoc.get("actions") or [] if a.get("name") == so["action"]), None)
        if act is None:
            raise GoxError(f"{so['document']}: no action {so['action']}")
        stores = [m for m in act.get("mstores") or [] if m.get("src") == so["store"]]
        if len(stores) != 1:
            raise GoxError(f"{so['document']}: {so['action']} has {len(stores)} stores at {so['store']}")
        val = stores[0]["value"]
        if not (isinstance(val, list) and val[:1] == ["keccak256"] and val[1][:1] == ["slice"]
                and val[1][1][:1] == ["mem"]):
            raise GoxError(f"{so['store']}: the stored value is not keccak256 over a memory slice")
        widths = {fl["name"]: fl.get("width") for p in act.get("params") or [] for fl in p.get("fields") or []}
        sol = {"document": so["document"], "action": so["action"], "store": so["store"], "value": val,
               "widths": dict(sorted(widths.items()))}
        for fn in spec["go"]["functions"]:
            f = cx.fns.get(fn)
            lid = f"L_par_gorc_{role}_{short(fn)}"
            el = {"law_id": lid, "subform": "go_recompute", "words": [role, short(fn)], "function": fn}
            rets = _hash_returns(f, hp) if f is not None else []
            if f is None:
                el["reason"] = "absent"
            elif len(rets) != 1:
                el["reason"] = "no_hash" if not rets else "several_hashes"
            else:
                p, lb = rets[0]
                arg = p["returns"][0][2]
                pre = arg[0][1][0] if (len(arg) == 1 and isinstance(arg[0], list) and arg[0][:1] == ["varargs"]
                                       and len(arg[0][1]) == 1) else None
                if pre is None:
                    el["reason"] = "no_preimage"
                elif _has(pre, "alloc"):
                    el["reason"] = "alloc_preimage"
                else:
                    loop = None
                    if lb is not None:
                        loop = {k: lb[k] for k in ("span", "iv", "init", "step", "cmp", "limit", "fuel", "carried")}
                        loop["continue"] = [{"cond": q["cond"], "updates": q.get("updates") or {}}
                                            for q in lb["paths"] if q["end"] == "continue"]
                        loop["panics"] = [{"cond": q["cond"], "site": q["site"]} for q in lb["paths"]
                                          if q["end"] == "panic"]
                    el["basis"] = {"kind": "go_recompute", "role": role, "function": fn, "params": f["params"],
                                   "exit_cond": p["cond"], "preimage": pre, "loop": loop, "solidity": sol}
            if "basis" not in el:
                el["basis"] = {"kind": "go_recompute", "role": role, "function": fn, "solidity": sol}
            out.append(el)
    return out


def elements(root, milestone: str, inputs=None) -> list:
    """Every basis element of the three sub-forms, sorted by law id: {law_id, subform, words, basis[, reason]}."""
    cx = Ctx(root, milestone, inputs)
    els = round_trips(cx) + branches(cx) + recomputes(cx)
    ids = [e["law_id"] for e in els]
    if len(ids) != len(set(ids)):
        raise GoxError(f"two basis elements map to one law id: {sorted({i for i in ids if ids.count(i) > 1})}")
    for e in els:
        e["facts"] = cx.doc_rel
        e["facts_sha256"] = sha256_bytes(cx.doc_bytes)
        e["gox_id"] = ":".join([e["subform"], *e["words"]])
    return sorted(els, key=lambda e: e["law_id"])
