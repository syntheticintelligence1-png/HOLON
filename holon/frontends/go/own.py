"""Reduce dumped SSA to slice/backing-identity machine facts.

For each struct type with slice fields we extract:
  * the tracked field cone: slice fields that are both grown by append and
    read by a view-producing method (the OWN-alias surface);
  * actions: one per method — append sites become (heap, header) lets;
    slice returns snapshot the view into ghost state;
  * the constructor's initial slice headers;
  * the generic view_intact observer.

Output format: holon-extracted/go-machine/0.1.
"""
from __future__ import annotations

from . import model as M
from . import codecs as C

SLICE_CLASSES = [0, 8, 16, 24, 32, 48, 64, 80, 96, 112, 128, 144, 160, 176,
                 192, 208, 224, 240, 256, 288, 320, 352, 384, 416, 448, 480,
                 512]


def _field_reads(fn, slots):
    """Fields loaded anywhere in fn."""
    reads = set()
    for ins in fn.d["instrs"]:
        if ins["op"] in ("fieldaddr", "field"):
            f = C.field_of(M.expr(fn, ins["id"]), slots)
            if f:
                reads.add(f)
    return reads


def _returns_slice(fn):
    sig = fn.d.get("signature", "")
    tail = sig[sig.rfind(")") + 1:] if ")" in sig else ""
    return "]byte" in tail


def action_of_fn(fn, cone, dump):
    """Extract one machine action from a method."""
    slots = C.recv_slots(fn)
    seq, complete = M.walk_seq(fn)
    ops, aux, _buf = C.codec_ops(fn, seq)
    params = [i.get("name", f"arg{i.get('index')}")
              for i in fn.d["instrs"] if i["op"] == "param"
              and i.get("index", 0) > 0]

    returned = set()
    ret_field = None
    for _c, term in M.seq_leaves(seq):
        if term and term["op"] == "return":
            for a in term.get("args") or []:
                e = M.expr(fn, a)
                if e and e[0] == "builtin" and e[1] == "append":
                    returned.add(a)
                else:
                    f = C.field_of(e, slots)
                    if f:
                        ret_field = f

    appends = [o for o in ops if o["op"] == "append"]
    lets, effects, dropped = [], {}, []
    heap_prev = "heap"
    hcount = 0

    def src_name(s):
        if "field" in s:
            f = s["field"]
            lname = f"r_{f}"
            if not any(l["let"] == lname for l in lets):
                lets.append({"let": lname,
                             "expr": ["call", "go_read", heap_prev, f],
                             "src": "field load"})
            return lname
        if "param" in s:
            return s["param"]
        if "call" in s:
            lname = f"c{len(lets)}"
            lets.append({"let": lname, "expr": ["call_result", s["call"]]})
            return lname
        if "const" in s:
            return ["const", s["const"]]
        if "param_elem" in s:
            lname = f"e_{s['param_elem']}_{len(lets)}"
            lets.append({"let": lname,
                         "expr": ["elem", s["param_elem"]]})
            return lname
        return ["expr", s.get("expr", "?")]

    def dst_field_of(ap):
        d = ap["dst"]
        if d and d[0] == "field":
            return d[1]
        if d and d[0] == "field_of":
            return d[-1]
        return ap.get("to_field")

    for ap in appends:
        f_dst = dst_field_of(ap)
        srcs = ap["src"]
        if f_dst not in cone:
            dropped.append({
                "site": ap["site"], "field": f_dst or repr(ap["dst"]),
                "reason": "append outside tracked cone",
                "in_loop": ap.get("in_loop", False)})
            continue
        hcount += 1
        hn = f"h{hcount}"
        src_e = src_name(srcs[0]) if srcs else ["expr", "empty"]
        site = f"{ap['site']['file']}:{ap['site']['line']} append"
        lets.append({"let": hn,
                     "expr": ["call", "go_append_heap", heap_prev,
                              f_dst, src_e, "classes"],
                     "src": site})
        if ap.get("to_field"):
            lets.append({"let": f"{f_dst}'",
                         "expr": ["call", "go_append_slice", heap_prev,
                                  f_dst, src_e, "classes"],
                         "src": site})
            effects[f_dst] = f"{f_dst}'"
        if ap["result"] in returned:
            lets.append({"let": "v",
                         "expr": ["call", "go_append_slice", heap_prev,
                                  f_dst, src_e, "classes"],
                         "src": site})
            effects["view"] = "v"
        effects["heap"] = hn
        heap_prev = hn

    returns_view = _returns_slice(fn)
    if returns_view and "view" not in effects and ret_field in cone:
        effects["view"] = ret_field
    if "view" in effects:
        effects["heap"] = heap_prev
        effects["snap"] = ["call", "go_read", heap_prev, effects["view"]]
        effects["live"] = True

    other = [o for o in ops if o["op"] != "append"]
    # inputs: only params that feed an in-cone append (alias-relevant bytes)
    used = set()
    for l in lets:
        for x in l["expr"]:
            if isinstance(x, str) and x in params:
                used.add(x)
    return {
        "name": fn.name[0].lower() + fn.name[1:],
        "function": f"{(fn.recv or {}).get('type', '').lstrip('*').rsplit('.', 1)[-1]}.{fn.name}",
        "src": f"{fn.file}:{fn.line}-{fn.d.get('end_line')}",
        "inputs": [[p, "List<Nat>"] for p in params if p in used],
        "guards": lets,
        "effects": effects,
        "dropped": dropped,
        "complete": complete,
        "other_ops": [
            {k: v for k, v in o.items() if k in ("op", "field", "src", "site")}
            for o in other],
    }


def _initial_of(ctor, cone):
    """Read the constructor's field inits for cone fields (makeslice)."""
    init = {}
    for ins in ctor.d["instrs"]:
        if ins["op"] == "store":
            a = ins.get("args") or []
            if len(a) != 2:
                continue
            ae = C._unwrap_addr(M.expr(ctor, a[0]))
            if ae and ae[0] in ("fieldaddr", "field"):
                f = ae[2]
                if f in cone:
                    init[f] = {"b": 0, "off": 0, "len": 0, "cap": 0}
            elif ae and ae[0] == "alloc":
                # fieldaddr results were folded into the alloc expr
                pass
    return init


def extract_machine(dump: M.Dump, type_names=("BatchData",),
                    ctor_prefix="New"):
    machines = []
    coverage = {"modelled": [], "debt": [], "candidates": []}
    for tname in type_names:
        methods = [f for f in dump.funcs.values()
                   if f.recv and f.recv["type"].lstrip("*")
                   .rsplit(".", 1)[-1] == tname]
        view_fns = [f for f in methods if _returns_slice(f)]
        read_in_views = set()
        for f in view_fns:
            read_in_views |= _field_reads(f, C.recv_slots(f))
        appended = set()
        for f in methods:
            seq, _ok = M.walk_seq(f)
            ops, _aux, _b = C.codec_ops(f, seq)
            for o in ops:
                if o["op"] == "append":
                    d = o["dst"]
                    tf = o.get("to_field") or (
                        d[1] if d and d[0] == "field" else
                        (d[-1] if d and d[0] == "field_of" else None))
                    if tf:
                        appended.add(tf)
        cone = sorted(appended & read_in_views)

        ctor = next((f for f in dump.funcs.values()
                     if not f.recv and f.name == ctor_prefix + tname), None)
        init_fields = _initial_of(ctor, cone) if ctor else {}

        state = [["heap", "List<Arr>", "Go heap (backing arrays)"]]
        for f in cone:
            state.append([f, "Sl", f"{tname}.{f}"])
        state += [["view", "Sl",
                   "the slice the last view-producing call returned"],
                  ["snap", "List<Nat>",
                   "GHOST: contents of the view when it was returned"],
                  ["live", "Bool", "GHOST: a caller holds the view"],
                  ["classes", "List<Nat>", "oracle: Go runtime size classes"],
                  ["log", "List<Obs>", "observations"]]
        initial = {"heap": [{"cells": []}], "snap": [], "live": False,
                   "classes": SLICE_CLASSES, "log": [],
                   "view": {"b": 0, "off": 0, "len": 0, "cap": 0}}
        for f in cone:
            initial[f] = init_fields.get(
                f, {"b": 0, "off": 0, "len": 0, "cap": 0})

        actions = []
        debt = []
        for f in sorted(methods, key=lambda g: (g.file, g.line)):
            seq, _ok = M.walk_seq(f)
            ops, _aux, _b = C.codec_ops(f, seq)
            has_append = any(o["op"] == "append" for o in ops)
            if has_append or _returns_slice(f):
                act = action_of_fn(f, cone, dump)
                if act["guards"] or act["effects"].get("view"):
                    actions.append(act)
                    coverage["modelled"].append(f"{tname}.{f.name}")
                    debt.extend(act["dropped"])
                else:
                    coverage["candidates"].append(
                        f"{tname}.{f.name} ({f.file}:{f.line})")
            else:
                debt.append({"site": {"file": f.file, "line": f.line},
                             "field": None,
                             "reason": f"method {f.name} not modelled "
                                       "(no append, no slice return)",
                             "in_loop": False})
        machines.append({
            "type": tname,
            "types": {
                "Sl": {"doc": "Go slice header",
                       "fields": [["b", "Nat"], ["off", "Nat"],
                                  ["len", "Nat"], ["cap", "Nat"]]},
                "Arr": {"doc": "a backing array",
                        "fields": [["cells", "List<Nat>"]]},
            },
            "state": state,
            "ghost_state": ["snap", "live"],
            "initial": initial,
            "actions": actions,
            "observers": {
                "view_intact": {
                    "params": [["s", "State"]],
                    "type": "Bool",
                    "body": ["||", ["!", "live"],
                             ["call", "eq_nats",
                              ["call", "go_read", "heap", "view"], "snap"]],
                    "doc": "OWN-alias: while a caller holds the view, its "
                           "contents are unchanged by writes not made "
                           "through it",
                }
            },
            "coverage_debt": debt,
        })
        coverage["debt"].extend(
            {"element": f"{d['site']['file']}:{d['site']['line']} "
                        f"method {tname}.{d['reason'].split()[1]}",
             "kind": "unmodelled_method",
             "reason": d["reason"]}
            for d in debt if d.get("field") is None
            and d.get("site"))
        coverage["debt"].extend(
            {"element": f"{d['site']['file']}:{d['site']['line']} "
                        f"append {tname}.{d['field']}",
             "kind": "dropped_append",
             "reason": f"{d['reason']}"
                       + (" (in loop)" if d.get("in_loop") else "")}
            for d in debt if d.get("field"))
    coverage["modelled"].sort()
    coverage["debt"].sort(key=lambda d: d["element"])
    coverage["candidates"].sort()
    return {
        "format": "holon-extracted/go-machine/0.1",
        "extractor": "holon.frontends.go (gossa-dump/0.1)",
        "machines": machines,
        "coverage": coverage,
    }
