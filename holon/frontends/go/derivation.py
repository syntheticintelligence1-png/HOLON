"""SSA-derived Morph batch derivation facts for the M3 E3 extraction.

The reducer consumes only the gossa dump.  Raw SSA values are rendered under
semantic names introduced by the extraction itself (for example ``batchBytes``
for the successful result of ``zstd.DecompressBatchBytes``); expressions and
constants still come from instructions in the dump.
"""
from __future__ import annotations

import re
from collections import OrderedDict

from . import codecs as C
from . import model as M
from . import own


def _all_expr(e):
    if not isinstance(e, tuple) or not e:
        return
    yield e
    for x in e[1:]:
        if isinstance(x, tuple):
            yield from _all_expr(x)
        elif isinstance(x, (list, tuple)):
            for y in x:
                yield from _all_expr(y)


def _params(fn):
    return sorted((i for i in fn.d["instrs"] if i["op"] == "param"),
                  key=lambda i: i.get("index", 0))


def _alloc_aliases(fn):
    """Map compiler heap slots that copy an input struct back to its parameter."""
    param_types = {}
    for p in _params(fn):
        ty = p.get("type", "").lstrip("*")
        if ty:
            param_types.setdefault(ty, p.get("name") or f"arg{p.get('index', 0)}")
    aliases = {}
    for i in fn.d["instrs"]:
        if i["op"] != "alloc":
            continue
        ty = i.get("type", "").lstrip("*")
        if ty in param_types:
            aliases[i["id"]] = param_types[ty]
    return aliases


def _call_label(callee):
    """Render a canonical callee id without per-callee aliases."""
    if callee.startswith("builtin."):
        return callee.split(".", 1)[1]
    tail = callee.rsplit("/", 1)[-1]
    if ")." in tail:
        recv, meth = tail.rsplit(").", 1)
        recv = recv.split(".")[-1].lstrip("*(")
        return f"{recv}.{meth}"
    parts = tail.split(".")
    return ".".join(parts[-2:]) if len(parts) > 1 else tail


def _local_names(fn):
    """Name SSA values from the dump's DebugRef records."""
    alloc_names = dict(_alloc_aliases(fn))
    named_exprs = {}
    cycle_names = {}
    dyn_names = {}

    for ref in fn.d.get("debug_refs", []):
        name = ref.get("name")
        vid = ref.get("value")
        ins = fn.instr(vid)
        if not name or ins is None or not ref.get("is_var"):
            continue
        if ref.get("is_addr"):
            if ins["op"] == "alloc":
                alloc_names[vid] = name
            continue
        if ins["op"] == "const":
            continue
        named_exprs[M.expr(fn, vid)] = name
        if ins["op"] == "phi":
            cycle_names[vid] = name

    # Anonymous variadic vectors have no source identifier; name their role,
    # not a per-function SSA id, so unrelated instruction shifts do not leak
    # into extracted expressions.
    for ins in fn.d["instrs"]:
        if ins["op"] != "call" or not ins.get("fn", "").endswith("fmt.Errorf"):
            continue
        e = M.expr(fn, ins["id"])
        if len(e[2]) > 1 and e[2][1][0] == "slice" and e[2][1][1][0] == "alloc":
            alloc_names[e[2][1][1][1]] = "fmtArgs"

    # Dynamic calls are encoded as dyn.*tNNN.  Resolve each to the nearest
    # earlier function-valued load in the same block (e.g. bc.isBatchUpgraded).
    for ins in fn.d["instrs"]:
        if ins["op"] != "call" or not ins.get("fn", "").startswith("dyn."):
            continue
        candidates = [j for j in fn.d["instrs"]
                      if j["block"] == ins["block"] and j["id"] < ins["id"] and
                      j["op"] == "unop" and "func" in j.get("type", "")]
        if candidates:
            prev = candidates[-1]
            e = M.expr(fn, prev["id"])
            if e[0] == "load":
                dyn_names[ins["fn"]] = _expr_text(e[1], alloc_names, named_exprs,
                                                   cycle_names, {})
            else:
                dyn_names[ins["fn"]] = _expr_text(e, alloc_names, named_exprs,
                                                 cycle_names, {})

    return alloc_names, named_exprs, cycle_names, dyn_names


def _expr_text(e, alloc_names=None, named_exprs=None, cycle_names=None,
               dyn_names=None, depth=0):
    if e is None or depth > 40:
        return "?"
    alloc_names = alloc_names or {}
    named_exprs = named_exprs or {}
    cycle_names = cycle_names or {}
    dyn_names = dyn_names or {}
    if e in named_exprs:
        return named_exprs[e]
    tag = e[0]
    rec = lambda x: _expr_text(x, alloc_names, named_exprs, cycle_names,
                               dyn_names, depth + 1)
    if tag == "const":
        return repr(e[1]) if e[1] is not None else (e[3] or "nil")
    if tag == "param":
        return e[1] or f"arg{e[2]}"
    if tag == "global":
        return e[1]
    if tag == "alloc":
        return alloc_names.get(e[1], f"v{e[1]}")
    if tag in ("call", "builtin"):
        name = dyn_names.get(e[1], _call_label(e[1]))
        return f"{name}(" + ", ".join(rec(a) for a in e[2]) + ")"
    if tag in ("field", "fieldaddr"):
        return f"{rec(e[1])}.{e[2]}"
    if tag in ("index", "indexaddr"):
        return f"{rec(e[1])}[{rec(e[2])}]"
    if tag == "slice":
        lo = "" if e[2][0] == "nil" else rec(e[2])
        hi = "" if e[3][0] == "nil" else rec(e[3])
        return f"{rec(e[1])}[{lo}:{hi}]"
    if tag == "binop":
        return f"{rec(e[2])} {e[1]} {rec(e[3])}"
    if tag == "load":
        return rec(e[1])
    if tag == "cast":
        return rec(e[2])
    if tag == "extract":
        return f"{rec(e[1])}.{e[2]}"
    if tag == "phi":
        return "phi(" + "|".join(rec(a) for a in e[1]) + ")"
    if tag == "makeslice":
        return f"makeslice({rec(e[1])})"
    if tag == "nil":
        return "nil"
    if tag == "cycle":
        return cycle_names.get(e[1], f"cycle#{e[1]}")
    if tag == "fnref":
        return _call_label(e[1])
    if tag.startswith("unop:"):
        return f"{tag[5:]}({rec(e[1])})"
    return f"{tag}#{e[1] if len(e) > 1 else ''}"


def _names(fn):
    if not hasattr(fn, "_holon_names"):
        fn._holon_names = _local_names(fn)
    return fn._holon_names


def _text(fn, e):
    return _expr_text(e, *_names(fn))


def _text_unnamed(fn, e):
    names = _names(fn)
    named = {k: v for k, v in names[1].items() if k != e}
    return _expr_text(e, names[0], named, names[2], names[3])


def _cond_text(fn, c):
    if isinstance(c, tuple) and c and c[0] == "not":
        return f"not ({_text(fn, c[1])})"
    return _text(fn, c)


def _walk_seq(seq, conds=()):
    for n in seq:
        if n[0] == "instr":
            yield conds, n[1]
        elif n[0] == "branch":
            yield from _walk_seq(n[2], conds + (n[1],))
            yield from _walk_seq(n[3], conds + (("not", n[1]),))
        elif n[0] == "backedge":
            continue


def _path(fn, cs):
    return [_cond_text(fn, c) for c in cs]


def _line(fn, ins):
    line = ins.get("line")
    return int(line) if isinstance(line, int) else None


def _expr_line(fn, vid):
    return _line(fn, fn.instr(vid) or {})


def _call_records(fn):
    out = []
    for ins in fn.d["instrs"]:
        if ins["op"] == "call":
            out.append({"callee": ins.get("fn", ""), "line": _line(fn, ins),
                        "arguments": [_text(fn, M.expr(fn, a)) for a in ins.get("args", [])]})
    return out


def _find_fn(dump, name, path_fragment=None):
    hits = [f for f in dump.funcs.values() if f.name == name and
            (path_fragment is None or path_fragment in f.file)]
    if len(hits) != 1:
        raise ValueError(f"expected one {name} in {path_fragment}, got {len(hits)}")
    return hits[0]


def _fmt_args(fn, fmt_e, line):
    """Recover values stored into the variadic argument vector of fmt.Errorf."""
    if len(fmt_e[2]) < 2 or fmt_e[2][1][0] != "slice" or fmt_e[2][1][1][0] != "alloc":
        return []
    aid = fmt_e[2][1][1][1]
    out = []
    for ins in fn.d["instrs"]:
        if ins["op"] != "store" or _line(fn, ins) != line:
            continue
        args = ins.get("args") or []
        if len(args) != 2:
            continue
        dst = M.expr(fn, args[0])
        if dst[0] == "indexaddr" and dst[1] == ("alloc", aid):
            out.append(_text(fn, M.expr(fn, args[1])))
    return out


def _return_error(fn, term):
    args = [M.expr(fn, a) for a in (term.get("args") or [])]
    calls = [e for a in args for e in _all_expr(a) if e[0] == "call"]
    fmt = next((e for e in calls if e[1].endswith("fmt.Errorf")), None)
    if fmt:
        msg = M.const_val(fmt[2][0]) if fmt[2] else None
        return {"kind": "fmt.Errorf", "message": msg,
                "arguments": _fmt_args(fn, fmt, _line(fn, term)),
                "returned": [_text(fn, e) for e in args]}
    return {"kind": "propagated_error", "message": None, "arguments": [],
            "returned": [_text(fn, e) for e in args]}


def _conditions_for_ins(seq, iid):
    for conds, ins in _walk_seq(seq):
        if ins.get("id") == iid:
            return conds
    return ()


def _block_conditions(seq, bid):
    for conds, ins in _walk_seq(seq):
        if ins.get("block") == bid:
            return conds
    return ()


def _edge_conditions(fn, seq, pred_bid, target_bid):
    conds = tuple(_block_conditions(seq, pred_bid))
    block = fn.blocks.get(pred_bid) or {}
    ids = block.get("instrs") or []
    term = fn.instr(ids[-1]) if ids else None
    if term and term["op"] == "if":
        tag = next((s.get("tag") for s in block.get("succs") or []
                    if s.get("to") == target_bid), None)
        cond = M.expr(fn, term.get("cond"))
        if tag == "then":
            conds += (cond,)
        elif tag == "else":
            conds += (("not", cond),)
    return conds


def _phi_branches(fn, seq, phi_id):
    ins = fn.instr(phi_id)
    target = ins["block"]
    out = []
    for pred, vid in ins.get("edges") or []:
        e = M.expr(fn, vid)
        out.append({"predecessor_block": pred,
                    "path_condition": _path(fn, _edge_conditions(fn, seq, pred, target)),
                    "value": _text_unnamed(fn, e),
                    "source_name": _text(fn, e),
                    "line": _expr_line(fn, vid)})
    return out


def _named_instrs(fn, name, op=None):
    ids = []
    for ref in fn.d.get("debug_refs", []):
        if ref.get("name") != name or ref.get("value") in ids:
            continue
        ins = fn.instr(ref["value"])
        if ins is not None and (op is None or ins["op"] == op):
            ids.append(ref["value"])
    return sorted(ids)


def _subst_expr(e, old, new):
    if e == old:
        return new
    if not isinstance(e, tuple):
        return e
    return tuple(_subst_expr(x, old, new) if isinstance(x, tuple) else x
                 for x in e)


def _field_slice_base(e):
    e = M.strip_loads(e)
    if e and e[0] in ("field", "fieldaddr"):
        return e
    return None


def _first_call(fn, needle):
    return next((i for i in fn.d["instrs"] if i["op"] == "call" and needle in i.get("fn", "")), None)


def _parse_batch(fn):
    seq, complete = M.walk_seq(fn)
    decode_call = _first_call(fn, "DecodeTxsFromBytes")
    boundary = _line(fn, decode_call) if decode_call else fn.d.get("end_line")
    exits = OrderedDict()
    for conds, term in M.seq_leaves(seq):
        if term is None or term.get("op") != "return":
            continue
        line = _line(fn, term)
        if line is None or line >= boundary:
            continue
        info = _return_error(fn, term)
        key = (line, info["kind"], info["message"], tuple(info["returned"]))
        if key not in exits:
            exits[key] = {"line": line, "path_condition": _path(fn, conds), **info}
    exits_list = sorted(exits.values(), key=lambda e: e["line"])

    calls = _call_records(fn)
    oracles = []
    for c in calls:
        if ("BatchHeaderBytes" in c["callee"] or "DecompressBatchBytes" in c["callee"] or
                "BlockContext).Decode" in c["callee"]):
            oracles.append({"oracle": _call_label(c["callee"]), "callee": c["callee"],
                            "line": c["line"], "arguments": c["arguments"]})

    batch_index = []
    slots = C.recv_slots(fn)
    for ins in fn.d["instrs"]:
        if ins["op"] != "store" or len(ins.get("args") or []) != 2:
            continue
        dst, src = M.expr(fn, ins["args"][0]), M.expr(fn, ins["args"][1])
        if C.field_of(dst, slots) == "batchIndex":
            batch_index.append({"line": _line(fn, ins),
                                "expression": _text_unnamed(fn, src),
                                "source_name": _text(fn, src)})

    block_count_phis = _named_instrs(fn, "blockCount", "phi")
    raw_context_phis = _named_instrs(fn, "rawBlockContexts", "phi")
    txs_data_phis = _named_instrs(fn, "txsData", "phi")
    bc_len_ids = _named_instrs(fn, "bcLen")
    bc_len_ins = fn.instr(bc_len_ids[0]) if bc_len_ids else None
    block_count = {
        "initial_or_version_derived": _phi_branches(fn, seq, block_count_phis[0]) if block_count_phis else [],
        "calldata_or_version_derived": _phi_branches(fn, seq, block_count_phis[1]) if len(block_count_phis) > 1 else [],
    }
    raw_contexts = _phi_branches(fn, seq, raw_context_phis[0]) if raw_context_phis else []
    txs_data = _phi_branches(fn, seq, txs_data_phis[0]) if txs_data_phis else []
    zero_if = None
    if len(block_count_phis) > 1:
        count_e = M.expr(fn, block_count_phis[1])
        zero_if = next((i for i in fn.d["instrs"] if i["op"] == "if" and
                        M.expr(fn, i.get("cond"))[0] == "binop" and
                        M.expr(fn, i.get("cond"))[1] == "==" and
                        M.expr(fn, i.get("cond"))[2] == count_e and
                        M.const_val(M.expr(fn, i.get("cond"))[3]) == 0), None)
    tail_instrs = [i for i in fn.d["instrs"] if _line(fn, i) and _line(fn, i) >= boundary]
    debt = [{"element": f"{fn.file}:{boundary}-{max((_line(fn, i) or boundary for i in tail_instrs), default=boundary)}",
             "kind": "untranslated_remainder",
             "reason": "after the zero-block check, tx decoding, per-block context decoding, block-number and tx-count checks, queue dequeue, and BatchInfo field updates are not reduced in E3"}]

    def first_expr(pred):
        return next((_text(fn, M.expr(fn, i["id"])) for i in fn.d["instrs"]
                     if pred(i)), None)
    fields = OrderedDict((
        ("blobCount", first_expr(lambda i: i["op"] == "call" and i.get("fn") == "builtin.len")),
        ("parentIndex", first_expr(lambda i: i["op"] == "extract" and "BatchIndex" in _text(fn, M.expr(fn, i["args"][0])))),
        ("parentTotalL1Popped", first_expr(lambda i: i["op"] == "extract" and "TotalL1MessagePopped" in _text(fn, M.expr(fn, i["args"][0])))),
        ("parentVersion", first_expr(lambda i: i["op"] == "extract" and ".Version" in M.expr(fn, i["args"][0])[1])),
        ("parentLastBlock", first_expr(lambda i: i["op"] == "extract" and "LastBlockNumber" in _text(fn, M.expr(fn, i["args"][0])))),
        ("batch.Version", first_expr(lambda i: i["op"] == "fieldaddr" and i.get("name") == "Version")),
        ("batch.LastBlockNumber", first_expr(lambda i: i["op"] == "fieldaddr" and i.get("name") == "LastBlockNumber")),
        ("batch.BlockContexts", first_expr(lambda i: i["op"] == "fieldaddr" and i.get("name") == "BlockContexts")),
        ("len(batch.BlockContexts)", first_expr(lambda i: i["op"] == "call" and i.get("fn") == "builtin.len" and "BlockContexts" in _text(fn, M.expr(fn, i["args"][0])))),
        ("batchBytes", first_expr(lambda i: i["op"] == "extract" and "DecompressBatchBytes" in _text(fn, M.expr(fn, i["args"][0])) and i.get("index", 0) == 0)),
        ("len(batchBytes)", first_expr(lambda i: i["op"] == "call" and i.get("fn") == "builtin.len" and "batchBytes" in _text(fn, M.expr(fn, i["args"][0])))),
        ("startBlock.Number", first_expr(lambda i: i["op"] == "unop" and "startBlock.Number" in _text(fn, M.expr(fn, i["id"])))),
    ))

    predicates = []
    for ins in fn.d["instrs"]:
        if ins["op"] == "if":
            ln = _expr_line(fn, ins.get("cond"))
            if ln is not None and ln < boundary:
                predicates.append({"line": ln, "expression": _text(fn, M.expr(fn, ins["cond"]))})

    return {
        "source": f"{fn.file}:{fn.line}-{fn.d.get('end_line')}",
        "abstract_inputs": fields,
        "decision_predicates": predicates,
        "oracles": oracles,
        "error_exits": exits_list,
        "success": {
            "batchIndex": batch_index,
            "blockCount": block_count,
            "bcLen": {"line": _line(fn, bc_len_ins),
                      "expression": _text_unnamed(fn, M.expr(fn, bc_len_ins["id"])) if bc_len_ins else None,
                      "source_name": _text(fn, M.expr(fn, bc_len_ins["id"])) if bc_len_ins else None},
            "rawBlockContexts": raw_contexts,
            "txsData": txs_data,
        },
        "zero_block_check": {"line": _expr_line(fn, zero_if.get("cond")) if zero_if else None,
                             "condition": _text(fn, M.expr(fn, zero_if["cond"])) if zero_if else None},
        "scope_complete_through_zero_block_check": complete,
        "coverage_debt": debt,
    }


def _codec_entry(fn, ops):
    return {"kind": "encoder", "lang": "go-bytes", "function": M.short_name(fn.d),
            "id": fn.d["id"], "file": fn.file, "line": fn.line, "pkg": fn.d.get("pkg"),
            "memory_init": "zeros", "length": 1, "composite": False,
            "ops": ops, "field_stores": []}


def _slice_partiality(fn):
    """Derive the loop slice's panic predicate from its SSA operands."""
    slice_ins = next((i for i in fn.d["instrs"] if i["op"] == "slice" and
                      fn.blocks.get(i["block"], {}).get("loop")), None)
    if slice_ins is None:
        return None
    base, lo, hi = M.expr(fn, slice_ins["args"][0]), M.expr(fn, slice_ins["args"][1]), M.expr(fn, slice_ins["args"][2])
    if lo[0] != "binop" or lo[1] != "*" or hi[0] != "binop":
        return None
    index_e, factor_e = lo[2], lo[3]
    loop_if = next((i for i in fn.d["instrs"] if i["op"] == "if" and
                    (e := M.expr(fn, i.get("cond")))[0] == "binop" and e[1] == "<" and
                    e[2] == index_e), None)
    if loop_if is None or M.const_val(factor_e) is None:
        return None
    bound_e = M.expr(fn, loop_if["cond"])[3]
    one = ("const", 1, bound_e[2] if bound_e[0] == "const" else "int", "")
    max_i = ("binop", "-", bound_e, one)
    max_hi = _subst_expr(hi, index_e, max_i)
    len_base = ("builtin", "len", (base,))
    panic = ("binop", ">", max_hi, len_base)
    incomplete = ("binop", "<", len_base, ("binop", "*", factor_e, bound_e))
    panic_text = (_text(fn, max_hi) if max_hi == hi else
                  f"({_text(fn, bound_e)} - 1) * {_text(fn, factor_e)} + "
                  f"{_text(fn, hi[3])} > {_text(fn, len_base)}")
    return {"slice": _text(fn, M.expr(fn, slice_ins["id"])),
            "loop_bound": _text(fn, bound_e),
            "incomplete_full_context_predicate": _text(fn, incomplete),
            "maximal_index": _text(fn, max_i),
            "go_panic_condition": panic_text}


def _data_hash(fn):
    seq, _ = M.walk_seq(fn)
    ops, _aux, buffers = C.codec_ops(fn, seq)
    calls = _call_records(fn)
    conditions = [{"line": _expr_line(fn, i["cond"]), "expression": _text(fn, M.expr(fn, i["cond"]))}
                  for i in fn.d["instrs"] if i["op"] == "if"]
    slices = [{"line": _line(fn, i), "expression": _text(fn, M.expr(fn, i["id"]))}
              for i in fn.d["instrs"] if i["op"] == "slice"]
    out = {
        "source": f"{fn.file}:{fn.line}-{fn.d.get('end_line')}",
        "cached_hash_short_circuit": next((c["expression"] for c in conditions if "hash" in c["expression"]), None),
        "loop_condition": next((c["expression"] for c in conditions if "blockNum" in c["expression"]), None),
        "concat_appends": [{"line": c["line"], "arguments": c["arguments"]}
                            for c in calls if c["callee"] == "builtin.append"],
        "block_context_slices": slices,
        "codec_format": _codec_entry(fn, ops),
        "ops": ops,
        "buffers": [{"slot": list(k), "len": v.get("len"), "len_expr": v.get("len_expr")}
                    for k, v in buffers.items()],
    }
    partiality = _slice_partiality(fn)
    if partiality is None:
        out["coverage_debt"] = [{"element": f"{fn.file}:{fn.line}-{fn.d.get('end_line')}",
                                 "kind": "underived_partiality",
                                 "reason": "could not derive loop slice high bound against base length"}]
    else:
        out["slice_partiality"] = partiality
    return out


def _data_hash_v2(fn):
    calls = _call_records(fn)
    conditions = [{"line": _expr_line(fn, i["cond"]), "expression": _text(fn, M.expr(fn, i["cond"]))}
                  for i in fn.d["instrs"] if i["op"] == "if"]
    slices = [{"line": _line(fn, i), "expression": _text(fn, M.expr(fn, i["id"]))}
              for i in fn.d["instrs"] if i["op"] == "slice"]
    return {"source": f"{fn.file}:{fn.line}-{fn.d.get('end_line')}",
            "guards": conditions,
            "last_block_context_slice": slices,
            "height_oracle": [c for c in calls if "HeightFromBlockContextBytes" in c["callee"]],
            "hash_call": [c for c in calls if "calculateHash" in c["callee"]]}


def _calculate_hash(fn):
    seq, _ = M.walk_seq(fn)
    ops, _aux, buffers = C.codec_ops(fn, seq)
    calls = _call_records(fn)
    slices = [{"line": _line(fn, i), "expression": _text(fn, M.expr(fn, i["id"]))}
              for i in fn.d["instrs"] if i["op"] == "slice"]
    copies = [c for c in calls if c["callee"] == "builtin.copy"]
    layout_parts = [c["arguments"][1] for c in copies if len(c["arguments"]) > 1]
    return {"source": f"{fn.file}:{fn.line}-{fn.d.get('end_line')}",
            "codec_format": _codec_entry(fn, ops),
            "layout_parts": layout_parts,
            "layout_formula": " ++ ".join(layout_parts) if layout_parts else None,
            "ops": ops,
            "buffers": [{"slot": list(k), "len": v.get("len"), "len_expr": v.get("len_expr")}
                        for k, v in buffers.items()],
            "destination_slices": slices,
            "hash_oracle": [c for c in calls if "Keccak256Hash" in c["callee"]]}


def _combine_payloads(fn):
    copies = []
    for ins in fn.d["instrs"]:
        if ins["op"] != "call" or ins.get("fn") != "builtin.copy":
            continue
        args = ins.get("args") or []
        copies.append({"line": _line(fn, ins),
                       "destination": _text(fn, M.expr(fn, args[0])) if args else None,
                       "source": _text(fn, M.expr(fn, args[1])) if len(args) > 1 else None})
    allocation = next((i for i in fn.d["instrs"] if i["op"] == "makeslice"), None)
    return {"source": f"{fn.file}:{fn.line}-{fn.d.get('end_line')}",
            "payload_concat": [c["source"] for c in copies],
            "allocation_length": _text_unnamed(fn, M.expr(fn, allocation["args"][0])) if allocation else None,
            "copy_order": copies,
            "returns": [_text(fn, M.expr(fn, a)) for i in fn.d["instrs"] if i["op"] == "return"
                        for a in (i.get("args") or [])]}


def _estimator(fn, combine=None, dump=None):
    calls = _call_records(fn)
    conditions = [{"line": _expr_line(fn, i["cond"]), "expression": _text(fn, M.expr(fn, i["cond"]))}
                  for i in fn.d["instrs"] if i["op"] == "if"]
    appends = [c for c in calls if c["callee"] == "builtin.append"]
    compressor = [c for c in calls if "CompressBatchBytes" in c["callee"]]
    limit_e = next((M.expr(fn, i["cond"])[3] for i in fn.d["instrs"]
                    if i["op"] == "if" and M.expr(fn, i.get("cond"))[0] == "binop" and
                    M.expr(fn, i["cond"])[1] == "<="), None)
    limit = None
    if limit_e is not None:
        consts = [c for c in (dump.consts if dump is not None else [])
                  if c["name"] == "MaxBlobBytesSize"]
        limit = {"ssa_expression": _text_unnamed(fn, limit_e)}
        for c in consts:
            target = ("const", int(c["value"]), "int", "")
            renamed = _subst_expr(limit_e, target, ("global", f"blob.{c['name']}"))
            if renamed != limit_e:
                limit["expression"] = _text_unnamed(fn, renamed)
                limit["constant"] = c
                break
        else:
            limit["expression"] = limit["ssa_expression"]
    if combine is not None:
        payload = combine["payload_concat"]
    elif appends:
        payload = appends[0]["arguments"]
    else:
        payload = next((c["arguments"][1:] for c in calls if "combinePayloads" in c["callee"]), None)
    result_expressions = [{"line": _line(fn, i), "values": [_text(fn, M.expr(fn, a)) for a in i.get("args", [])]}
                          for i in fn.d["instrs"] if i["op"] == "return"]
    compressed_result = next((r["values"][0] for r in result_expressions
                              if r["values"] and "compressed" in r["values"][0] and " > " in r["values"][0]), None)
    return {"source": f"{fn.file}:{fn.line}-{fn.d.get('end_line')}",
            "limit": limit,
            "payload_concat": payload,
            "uncompressed_short_circuit": next((c for c in conditions if " <= " in c["expression"]), None),
            "compressed_result": compressed_result,
            "compressor_oracle": compressor,
            "result_expressions": result_expressions,
            "combine_payloads": combine}


def _ownership(dump, estimator_fn):
    machine = own.extract_machine(dump, type_names=("BatchData",))
    actions = machine["machines"][0]["actions"]
    action = next((a for a in actions if a.get("name") == "estimateCompressedSizeWithNewPayload"), None)
    append = next((i for i in estimator_fn.d["instrs"] if i["op"] == "call" and i.get("fn") == "builtin.append"), None)
    args = append.get("args", []) if append else []
    dst_e = M.expr(estimator_fn, args[0]) if args else None
    src_e = M.expr(estimator_fn, args[1]) if len(args) > 1 else None
    backing = C.buffer_key(dst_e) if dst_e else None
    field_base = _field_slice_base(dst_e)
    allocates = dst_e is not None and any(e[0] in ("alloc", "makeslice") for e in _all_expr(dst_e))
    may_share = bool(field_base is not None and not allocates)
    updates_header = False
    if field_base is not None:
        for ins in estimator_fn.d["instrs"]:
            if ins["op"] == "store" and len(ins.get("args") or []) == 2 and \
               M.expr(estimator_fn, ins["args"][0]) == field_base:
                updates_header = True
                break
    dst_text = _text(estimator_fn, dst_e)
    src_text = _text(estimator_fn, src_e)
    return {"source": f"{estimator_fn.file}:{estimator_fn.line}-{estimator_fn.d.get('end_line')}",
            "ssa_append": _text_unnamed(estimator_fn, M.expr(estimator_fn, append["id"])) if append else None,
            "destination_backing_key_from_codecs": list(backing) if isinstance(backing, tuple) else backing,
            "own_py_action": action,
            "append_result_may_share_backing": may_share,
            "aliasing_kind": {"destination": "loaded_field_slice" if field_base is not None else "unknown",
                              "fresh_alloc": allocates, "may_share_backing": may_share},
            "updates_header": updates_header,
            "capacity_condition": f"len({dst_text}) + len({src_text}) <= cap({dst_text})" if dst_e and src_e else None}


def _decode_txs(fn):
    calls = _call_records(fn)
    seq, _complete = M.walk_seq(fn)
    read = next((i for i in fn.d["instrs"] if i["op"] == "call" and i.get("fn") == "encoding/binary.Read"), None)
    byte_addr = _text(fn, M.expr(fn, read["args"][2])) if read and len(read.get("args", [])) > 2 else None
    conditions = []
    for ins in fn.d["instrs"]:
        if ins["op"] != "if":
            continue
        text = _text(fn, M.expr(fn, ins["cond"]))
        if "typeByte" in text or "EOF" in text:
            conditions.append({"condition": text, "line": _expr_line(fn, ins.get("cond")),
                               "block": ins.get("block")})
    type_conditions = []
    for item in conditions:
        m = re.search(r"typeByte (==|<=|<|>=|>) (\d+)", item["condition"])
        if m:
            type_conditions.append({"condition": item["condition"], "operator": m.group(1),
                                    "value": int(m.group(2)), "line": item["line"], "block": item["block"]})
    zero = next((x for x in type_conditions if x["operator"] == "==" and x["value"] == 0), None)
    eof = next((x for x in conditions if "EOF" in x["condition"]), None)
    routes = OrderedDict()
    for conds, ins in _walk_seq(seq):
        if ins["op"] == "call" and any(x in ins.get("fn", "") for x in
                                        ("decodeTypedTx", "decodeMorphTx", "extractInnerTxFullBytes", "rlp.DecodeBytes")):
            routes.setdefault(_call_label(ins.get("fn")).rsplit(".", 1)[-1],
                              []).append(_path(fn, conds))
    route_bytes = {}
    for name, route_list in routes.items():
        values = []
        for route in route_list:
            for cond in route:
                m = re.fullmatch(r"typeByte == (\d+)", cond)
                if m:
                    values.append(int(m.group(1)))
        route_bytes[name] = sorted(set(values))
    max_return_line = max((_line(fn, i) or 0 for i in fn.d["instrs"] if i["op"] == "return"), default=0)
    success_paths = [_path(fn, conds) for conds, term in M.seq_leaves(seq)
                     if term and term["op"] == "return" and _line(fn, term) == max_return_line]
    error_paths = []
    for conds, term in M.seq_leaves(seq):
        if term and term["op"] == "return":
            error = _return_error(fn, term)
            if _line(fn, term) != max_return_line:
                error_paths.append({"line": _line(fn, term), "message": error["message"],
                                    "kind": error["kind"], "path_condition": _path(fn, conds)})
    table = []
    if eof:
        table.append({"condition": eof["condition"], "action": "terminate",
                      "result": "success", "line": eof["line"]})
    if zero:
        table.append({"condition": zero["condition"], "action": "terminate",
                      "result": "success", "line": zero["line"]})
    for name in ("decodeTypedTx", "decodeMorphTx", "extractInnerTxFullBytes"):
        if name in routes:
            vals = route_bytes.get(name, [])
            cond = ("typeByte > 247" if name == "extractInnerTxFullBytes" else
                    "typeByte in {" + ",".join(str(v) for v in vals) + "}")
            action = "accept"
            if name == "extractInnerTxFullBytes":
                action += ": legacy RLP decode"
            table.append({"condition": cond, "action": action, "decoder": name,
                          "path_conditions": routes[name]})
    unsupported = next((x for x in type_conditions if x["operator"] == "<="), None)
    if unsupported:
        table.append({"condition": unsupported["condition"] + " after earlier equality cases",
                      "action": "error", "line": unsupported["line"],
                      "message": "not supported tx type: %d"})
    body_debt = [{"element": f"{f.file}:{f.line}-{f.d.get('end_line')}", "function": f.name,
                  "reason": "per-type decode body is not reduced in E3"}
                 for f in (next((x for x in []), None),) if f]
    return {"source": f"{fn.file}:{fn.line}-{fn.d.get('end_line')}",
            "stream_byte_address_from_binary_Read": byte_addr,
            "dispatch_table": table,
            "dispatch_conditions": type_conditions,
            "accepted_byte_values_by_decoder_from_branch_paths": route_bytes,
            "byte_zero_termination": {"condition": zero, "success_paths": [p for p in success_paths if any("== 0" in c for c in p)]} if zero else None,
            "eof_termination": {"condition": eof, "success_paths": [p for p in success_paths if any("EOF" in c for c in p)]} if eof else None,
            "error_routes": error_paths,
            "decoder_calls": [{"callee": c["callee"], "line": c["line"]} for c in calls
                              if any(x in c["callee"] for x in
                                     ("decodeTypedTx", "decodeMorphTx", "extractInnerTxFullBytes", "rlp.DecodeBytes"))],
            "per_type_decode_body": body_debt,
            "unsupported_branch": unsupported}


def _affine_index(e):
    """Return (loop phi, coefficient, offset) for an affine index expression."""
    if e[0] == "phi":
        return e, 1, 0
    if e[0] == "const":
        return None, 0, int(e[1])
    if e[0] != "binop":
        return None, 0, None
    if e[1] in ("+", "-"):
        lphi, la, lo = _affine_index(e[2])
        rphi, ra, ro = _affine_index(e[3])
        if lphi is not None and (rphi is None or rphi == lphi):
            sign = 1 if e[1] == "+" else -1
            return lphi, la + sign * ra, lo + sign * ro
        if rphi is not None and lphi is None and e[1] == "+":
            return rphi, ra, lo + ro
    if e[1] == "*":
        lphi, la, lo = _affine_index(e[2])
        rphi, ra, ro = _affine_index(e[3])
        if lphi is not None and rphi is None:
            return lphi, la * ro, lo * ro
        if rphi is not None and lphi is None:
            return rphi, ra * lo, ro * lo
    return None, 0, None


def _constant_base_len(fn, base):
    """Length of a locally allocated constant-size slice/array base."""
    base = M.strip_loads(M.strip_casts(base))
    if base[0] == "slice" and base[3][0] == "const" and base[3][1] is not None:
        return int(base[3][1])
    if base[0] == "makeslice" and base[1][0] == "const":
        return int(base[1][1])
    if base[0] == "alloc":
        ty = (fn.instr(base[1]) or {}).get("type", "")
        m = re.match(r"\*\[(\d+)\]", ty)
        if m:
            return int(m.group(1))
    return None


def _phi_start(phi):
    for edge in phi[1]:
        if edge[0] == "const" and edge[1] is not None:
            return int(edge[1])
    return None


def _index_partiality(fn, dump):
    seq, _ = M.walk_seq(fn)
    checked, debt = [], []
    const_by_value = {}
    for c in dump.consts:
        if c["name"] == "MaxBlobBytesSize":
            try:
                const_by_value.setdefault(int(c["value"]), c)
            except (TypeError, ValueError):
                pass
    for ins in fn.d["instrs"]:
        if ins["op"] not in ("index", "indexaddr") or len(ins.get("args") or []) < 2:
            continue
        e = M.expr(fn, ins["id"])
        phi, coef, off = _affine_index(e[2])
        if phi is None:
            continue
        loop = next((i for i in fn.d["instrs"] if i["op"] == "if" and
                     (c := M.expr(fn, i.get("cond")))[0] == "binop" and
                     c[1] == "<" and c[2] == phi and c[3][0] == "const"), None)
        if loop is None:
            debt.append({"line": _line(fn, ins), "expr": _text(fn, e),
                         "reason": "affine loop index has no constant upper bound"})
            continue
        bound = int(M.expr(fn, loop["cond"])[3][1])
        base_len = _constant_base_len(fn, e[1])
        if base_len is None:
            debt.append({"line": _line(fn, ins), "expr": _text(fn, e),
                         "reason": "index base has no constant local allocation length"})
            continue
        start = _phi_start(phi)
        if start is None:
            debt.append({"line": _line(fn, ins), "expr": _text(fn, e),
                         "reason": "affine loop index has no constant lower bound"})
            continue
        if coef <= 0:
            debt.append({"line": _line(fn, ins), "expr": _text(fn, e),
                         "reason": "affine loop index has a non-positive coefficient"})
            continue
        end = bound - 1
        min_val, max_val = coef * start + off, coef * end + off
        first = (base_len - off + coef - 1) // coef
        item = {"line": _line(fn, ins), "expr": _text(fn, e),
                "base_len": {"value": base_len,
                             "constant": const_by_value.get(base_len)},
                "index_range": {"loop_var": _text(fn, phi),
                                "start": start, "end": end,
                                "value_min": min_val, "value_max": max_val},
                "path_condition": _path(fn, _conditions_for_ins(seq, ins["id"]))}
        if first is not None and start <= first <= end:
            item["first_panicking_index"] = first
            item["panic_condition"] = (f"{_text(fn, e[2])} >= {base_len} "
                                       f"({_text(fn, phi)} >= {first})")
            item["panics"] = True
        else:
            item["panic_condition"] = None
            item["panics"] = False
        checked.append(item)
    return {"checked": checked,
            "panic_set": [x for x in checked if x["panics"]],
            "debt": debt}


def _fmt_arg_exprs(fn, fmt_e, line):
    if len(fmt_e[2]) < 2 or fmt_e[2][1][0] != "slice" or fmt_e[2][1][1][0] != "alloc":
        return []
    aid = fmt_e[2][1][1][1]
    out = []
    for ins in fn.d["instrs"]:
        if ins["op"] != "store" or _line(fn, ins) != line:
            continue
        args = ins.get("args") or []
        if len(args) != 2:
            continue
        dst = M.expr(fn, args[0])
        if dst[0] == "indexaddr" and dst[1] == ("alloc", aid):
            out.append(M.expr(fn, args[1]))
    return out


def _twin_summary(fn, dump):
    calls = _call_records(fn)
    seq, _ = M.walk_seq(fn)
    guards = [_text(fn, M.expr(fn, i["cond"])) for i in fn.d["instrs"] if i["op"] == "if"]
    copies = [c for c in calls if c["callee"] == "builtin.copy"]
    fmt = next((i for i in fn.d["instrs"] if i["op"] == "call" and i.get("fn", "").endswith("fmt.Errorf")), None)
    message = None
    error_args = []
    unchecked = None
    if fmt:
        fmt_e = M.expr(fn, fmt["id"])
        args = fmt.get("args") or []
        if args:
            message = M.const_val(M.expr(fn, args[0]))
        arg_exprs = _fmt_arg_exprs(fn, fmt_e, _line(fn, fmt))
        error_args = [_text(fn, e) for e in arg_exprs]
        conds = _conditions_for_ins(seq, fmt["id"])
        guard = next((c for c in reversed(conds) if c[0] == "binop" and c[1] in ("!=", "==")), None)
        if guard is not None and arg_exprs:
            operand = M.strip_loads(M.strip_casts(guard[2]))
            reported = M.strip_loads(M.strip_casts(arg_exprs[0]))
            unchecked = {"guard_operand": _text(fn, guard[2]),
                         "reported_operand": _text(fn, arg_exprs[0]),
                         "error_reports_unchecked_value": reported != operand}
    return {"source": f"{fn.file}:{fn.line}-{fn.d.get('end_line')}",
            "loop_conditions": guards,
            "error_format": message,
            "error_arguments": error_args,
            "unchecked_error_operand": unchecked,
            "index_partiality": _index_partiality(fn, dump),
            "copy_calls": [{"arguments": c["arguments"]} for c in copies]}


def _twin_diff(a, b):
    differences = []
    for key in ("loop_conditions", "error_format", "error_arguments", "unchecked_error_operand",
                "index_partiality", "copy_calls"):
        if a[key] != b[key]:
            differences.append({"field": key, "common_batch": a[key], "common_blob": b[key]})
    structural_keys = ("loop_conditions", "error_format", "copy_calls")
    return {"structurally_identical_except_error_arguments": all(a[k] == b[k] for k in structural_keys),
            "differences_derived_by_recursive_field_comparison": differences,
            "error_reports_unchecked_value": {
                "common_batch": (a.get("unchecked_error_operand") or {}).get("error_reports_unchecked_value"),
                "common_blob": (b.get("unchecked_error_operand") or {}).get("error_reports_unchecked_value")},
            "index_panic_set": {
                "common_batch": a["index_partiality"]["panic_set"],
                "common_blob": b["index_partiality"]["panic_set"]}}


def _producer_sites(dump):
    sites = []
    targets = ("WillExceedCompressedSizeLimit", "EstimateCompressedSizeWithNewPayload")
    for fn in dump.funcs.values():
        seq, _ = M.walk_seq(fn)
        for ins in fn.d["instrs"]:
            name = ins.get("fn", "") if ins["op"] == "call" else ""
            if any(name.endswith("." + target) for target in targets):
                sites.append({"caller": fn.name, "file": fn.file, "line": _line(fn, ins),
                              "callee": name,
                              "path_condition": _path(fn, _conditions_for_ins(seq, ins["id"]))})
    return sorted(sites, key=lambda s: (s["file"], s["line"] or 0, s["callee"]))


def extract_derivation(dump: M.Dump, target_commit: str) -> dict:
    parse = _find_fn(dump, "ParseBatch", "node/derivation/batch_info.go")
    batch_twin = _find_fn(dump, "RetrieveBlobBytes", "common/batch/blob.go")
    blob_twin = _find_fn(dump, "RetrieveBlobBytes", "common/blob/payload.go")
    data_hash_fn = _find_fn(dump, "DataHash", "common/batch/batch_data.go")
    data_hash_v2 = _find_fn(dump, "DataHashV2", "common/batch/batch_data.go")
    calculate_hash = _find_fn(dump, "calculateHash", "common/batch/batch_data.go")
    estimate = _find_fn(dump, "EstimateCompressedSizeWithNewPayload", "common/batch/batch_data.go")
    will_exceed = _find_fn(dump, "WillExceedCompressedSizeLimit", "common/batch/batch_data.go")
    combine = _find_fn(dump, "combinePayloads", "common/batch/batch_data.go")
    decode = _find_fn(dump, "DecodeTxsFromBytes", "common/batch/blob.go")

    batch_summary = _twin_summary(batch_twin, dump)
    blob_summary = _twin_summary(blob_twin, dump)
    comp = _combine_payloads(combine)
    data_hash = _data_hash(data_hash_fn)
    est_fact = _estimator(estimate, dump=dump)
    est_fact["ownership"] = _ownership(dump, estimate)
    parse_fact = _parse_batch(parse)
    decode_fact = _decode_txs(decode)
    decode_bodies = []
    for name in ("decodeTypedTx", "decodeMorphTx", "extractInnerTxFullBytes"):
        f = _find_fn(dump, name, "common/batch/blob.go")
        decode_bodies.append({"element": f"{f.file}:{f.line}-{f.d.get('end_line')}",
                              "function": name, "kind": "untranslated_decode_body",
                              "reason": "per-type decode body is not reduced in E3"})
    decode_fact["per_type_decode_body"] = decode_bodies

    h_oracle = next(c for c in _call_records(data_hash_v2) if "HeightFromBlockContextBytes" in c["callee"])
    zstd_oracle = next(c for c in _call_records(parse) if "DecompressBatchBytes" in c["callee"])
    coverage = parse_fact["coverage_debt"] + data_hash.get("coverage_debt", []) + decode_bodies + [
        {"element": f"{data_hash_v2.file}:{h_oracle['line']}", "kind": "oracle_body",
         "reason": "HeightFromBlockContextBytes parser body is an oracle"},
        {"element": f"{parse.file}:{zstd_oracle['line']}", "kind": "oracle_body",
         "reason": "zstd.DecompressBatchBytes body is an oracle"},
    ]
    return {
        "format": "holon-extracted/go-derivation/0.1",
        "extractor": "holon.frontends.go.derivation (gossa-dump/0.2)",
        "target": {"repo": "morph-l2/morph", "commit": target_commit,
                   "packages": ["morph-l2/common/batch", "morph-l2/node/types",
                                "morph-l2/common/blob", "morph-l2/node/derivation"]},
        "parse_batch": parse_fact,
        "retrieve_blob_bytes": {
            "common_batch": batch_summary,
            "common_blob": blob_summary,
            "differ": _twin_diff(batch_summary, blob_summary),
        },
        "hash_encoders": {
            "DataHash": data_hash,
            "DataHashV2": _data_hash_v2(data_hash_v2),
            "calculateHash": _calculate_hash(calculate_hash),
            "m2_coverage_reconciliation": {
                "old_machine_debt": {"element": f"{calculate_hash.file}:{calculate_hash.line} method BatchData.calculateHash",
                                     "kind": "unmodelled_method",
                                     "reason": "resolved in E3 as a byte-layout encoder; it has no BatchData slice/backing state transition"},
                "resolution": "The M2 go_batchdata slice/backing machine correctly classifies this read-only helper as outside its state-transition cone; M2 go_codecs also correctly recognizes its emitted byte-buffer encoder. E3 extracts its layout here, so it is not carried as unresolved E3 debt."
            },
        },
        "size_estimators": {
            "EstimateCompressedSizeWithNewPayload": est_fact,
            "WillExceedCompressedSizeLimit": _estimator(will_exceed, comp, dump),
            "combinePayloads": comp,
            "batch_producer_calls": _producer_sites(dump),
        },
        "decode_txs_from_bytes": decode_fact,
        "coverage": {"modelled": [f"{fn.file}:{fn.line} {fn.name}" for fn in
                                   (parse, batch_twin, blob_twin, data_hash_fn, data_hash_v2,
                                    calculate_hash, estimate, will_exceed, combine, decode)],
                     "debt": coverage},
    }
