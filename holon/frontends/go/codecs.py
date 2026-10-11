"""Reduce dumped SSA to codec facts (go_codecs.json content).

Recognizes, in the loaded morph packages:
  * byte-buffer encoders   -> {"kind": "encoder", length, memory_init, ops}
  * accept predicates      -> {"kind": "predicate", rules}
  * offset getters         -> decoder getters {offset, width, accessor, when}
  * composite getters/encoders (dispatch or buffer reuse) -> marked composite
  * partiality annotations -> every slice/index site with its bound form

Everything unrecognized lands in coverage.debt, never approximated.
"""
from __future__ import annotations

from . import model as M

ENDIAN_PREFIX = "binary.BigEndian."
PUTS = {
    "PutUint16": ("put_uint16_be", 2),
    "PutUint32": ("put_uint32_be", 4),
    "PutUint64": ("put_uint64_be", 8),
}
GETS = {"Uint16": 2, "Uint32": 4, "Uint64": 8}
HASH_ACCESSORS = ("BytesToHash", "BytesToAddress")


# ---------- receiver / field helpers ----------

def recv_slots(fn: M.Fn):
    """Value ids that hold the receiver: param0 plus entry-copy allocs."""
    slots = set()
    for ins in fn.d["instrs"]:
        if ins["op"] == "param" and ins.get("index", 0) == 0:
            slots.add(ins["id"])
    for ins in fn.d["instrs"]:
        if ins["op"] == "store":
            a = ins.get("args") or []
            if len(a) == 2 and a[1] in slots:
                slots.add(a[0])
    return slots


def _unwrap_addr(e):
    while e and e[0] in ("load", "cast"):
        e = e[1] if e[0] == "load" else e[2]
    return e


def field_of(e, slots):
    """`fieldaddr(<recv-slot>, F)` chains -> innermost field name or None.
    Promoted fields (embedded structs) walk the chain to the receiver."""
    e = _unwrap_addr(e)
    path = []
    while e and e[0] in ("fieldaddr", "field"):
        path.append(e[2])
        e = _unwrap_addr(e[1])
    if path and e and (e[0] == "alloc" and e[1] in slots
                       or e[0] == "param" and e[2] == 0):
        return path[0]
    return None


def buffer_key(e):
    """Stable identity of the backing a slice/pointer expr refers to."""
    e = _unwrap_addr(e)
    if e is None:
        return ("expr", "?")
    if e[0] == "slice":
        return buffer_key(e[1])
    if e[0] == "indexaddr":
        return buffer_key(e[1])
    if e[0] == "alloc":
        return ("alloc", e[1])
    if e[0] == "param":
        return ("param", e[1])
    if e[0] in ("fieldaddr", "field"):
        b = _unwrap_addr(e[1])
        if b and b[0] == "param":
            return ("field", e[2])
        return ("field_of", buffer_key(b), e[2])
    if e[0] == "call":
        return ("call", e[1])
    if e[0] == "makeslice":
        return ("makeslice",)
    if e[0] == "phi":
        return ("phi", tuple(buffer_key(a) for a in e[1]))
    if e[0] == "global":
        return ("global", e[1])
    if e[0] == "extract":
        return ("extract", buffer_key(e[1]), e[2])
    return ("expr", M.expr_text(e))


def slice_window(fn, e):
    """`slice(base, lo, hi, mx)` or `indexaddr(base, k)` -> (key, off, hi)."""
    e = _unwrap_addr(e)
    if e and e[0] == "slice":
        lo = M.const_val(e[2]) or 0
        hi = M.const_val(e[3])
        return buffer_key(e[1]), lo, hi
    if e and e[0] == "indexaddr":
        return buffer_key(e[1]), M.const_val(e[2]), M.const_val(e[2])
    return None


def norm_src(fn, slots, e):
    """Classify a value expression as a fact-level source."""
    e = _unwrap_addr(e)
    if e is None or e[0] == "nil":
        return {"expr": "nil"}
    f = field_of(e, slots)
    if f:
        return {"field": f}
    if e[0] == "slice":
        f2 = field_of(e[1], slots)
        if f2:
            return {"field": f2}
        inner = _unwrap_addr(e[1])
        if inner and inner[0] == "param":
            return {"param": inner[1]}
        return {"expr": M.expr_text(e)}
    if e[0] == "param":
        return {"param": e[1]}
    if e[0] == "const":
        return {"const": e[1] if e[1] is not None else 0}
    if e[0] == "global":
        return {"global": e[1]}
    if e[0] == "call":
        return {"call": e[1]}
    if e[0] in ("index", "indexaddr"):
        f2 = field_of(e[1], slots)
        if f2:
            return {"field_elem": f2, "index": M.expr_text(e[2])}
        inner = _unwrap_addr(e[1])
        if inner and inner[0] == "param":
            return {"param_elem": inner[1]}
    if e[0] == "extract":
        return {"expr": M.expr_text(e)}
    return {"expr": M.expr_text(e)}


def short_fn(fid):
    s = fid.rsplit("/", 1)[-1]
    if s.startswith("("):
        s = s.rsplit(")", 1)[-1]
        return s.lstrip(".")
    return s.rsplit(".", 1)[-1]


# ---------- normalized op stream ----------

def codec_ops(fn: M.Fn, seq):
    """Extract the codec op stream: writes, appends, reads, field stores."""
    slots = recv_slots(fn)
    ops, aux = [], []
    buffers = {}  # key -> {"len": n}
    # first pass: find fresh-buffer makes (alloc [N]byte + slice / makeslice)
    for ins, _ in M.seq_instrs(fn, seq):
        if ins["op"] == "alloc" and ins.get("type", "").startswith("*["):
            t = ins["type"]
            try:
                n = int(t[2:t.index("]")])
            except Exception:
                continue
            buffers[("alloc", ins["id"])] = {"len": n}
        elif ins["op"] == "makeslice":
            key = ("alloc", ins["id"])
            ln = M.expr(fn, (ins.get("args") or [-1])[0])
            buffers[key] = {"len": M.const_val(ln), "len_expr": M.expr_text(ln)}
    for ins, in_loop in M.seq_instrs(fn, seq):
        op = ins["op"]
        args = ins.get("args") or []
        site = {"file": fn.file, "line": ins.get("line")}
        if op == "store" and len(args) == 2:
            ae = M.expr(fn, args[0])
            ve = M.expr(fn, args[1])
            f = field_of(ae, slots)
            dst = slice_window(fn, ae)
            if f:
                ops.append({"op": "field_store", "field": f,
                            "src": norm_src(fn, slots, ve), "site": site})
            elif dst and isinstance(dst[1], int):
                t = (fn.instr(args[0]) or {}).get("type", "")
                ops.append({"op": "set_byte", "offset": dst[1],
                            "src": [norm_src(fn, slots, ve)],
                            "byte": "byte" in t,
                            "dst": dst[0], "site": site})
            elif dst:
                ops.append({"op": "store_idx", "offset_expr": M.expr_text(
                    (_unwrap_addr(ae) or ("nil",))[2]), "dst": dst[0],
                    "src": norm_src(fn, slots, ve), "site": site})
            else:
                aux.append({"op": "store", "site": site,
                            "dst": M.expr_text(ae)})
        elif op == "call":
            fid = ins.get("fn", "")
            eargs = [M.expr(fn, a) for a in args]
            if fid == "builtin.copy" and len(eargs) == 2:
                dst = slice_window(fn, eargs[0])
                t = (fn.instr(args[0]) or {}).get("type", "")
                ops.append({"op": "copy",
                            "offset": dst[1] if dst else None,
                            "dst": dst[0] if dst else buffer_key(eargs[0]),
                            "byte": "byte" in t,
                            "src": [norm_src(fn, slots, eargs[1])],
                            "site": site})
            elif fid == "builtin.append" and len(eargs) >= 2:
                ops.append({"op": "append",
                            "dst": buffer_key(eargs[0]),
                            "src": [norm_src(fn, slots, x) for x in eargs[1:]],
                            "result": ins["id"],
                            "in_loop": in_loop, "site": site})
            elif fid.startswith(ENDIAN_PREFIX):
                m = fid[len(ENDIAN_PREFIX):]
                if m in PUTS and len(eargs) == 3:
                    name, _w = PUTS[m]
                    dst = slice_window(fn, eargs[1])
                    t = (fn.instr(args[1]) or {}).get("type", "")
                    ops.append({"op": name,
                                "offset": dst[1] if dst else None,
                                "dst": dst[0] if dst else buffer_key(eargs[1]),
                                "byte": "byte" in t,
                                "src": [norm_src(fn, slots, eargs[2])],
                                "site": site})
                elif m in GETS and len(eargs) == 2:
                    dst = slice_window(fn, eargs[1])
                    ops.append({"op": "read_" + m.lower(),
                                "offset": dst[1] if dst else None,
                                "hi": dst[2] if dst else None,
                                "src": buffer_key(eargs[1]) if dst else None,
                                "site": site})
                else:
                    aux.append({"op": "call", "fn": fid, "site": site})
            elif fid == "builtin.len":
                continue
            elif fid.startswith("invoke."):
                aux.append({"op": "invoke", "fn": fid, "site": site})
            else:
                aux.append({"op": "call", "fn": fid, "site": site})
        elif op == "mapupdate":
            aux.append({"op": "mapupdate", "site": site})
    # bind append results to the field they are stored into
    ap_by_result = {o["result"]: o for o in ops if o["op"] == "append"}
    kept = []
    for o in ops:
        if o["op"] == "field_store":
            continue
        kept.append(o)
    for ins, _loop in M.seq_instrs(fn, seq):
        if ins["op"] == "store":
            a = ins.get("args") or []
            if len(a) != 2:
                continue
            ae, ve = M.expr(fn, a[0]), M.expr(fn, a[1])
            f = field_of(ae, slots)
            ve2 = _unwrap_addr(ve)
            if f and ve2 and ve2[0] == "builtin" and ve2[1] == "append":
                ap = ap_by_result.get(a[1])
                if ap is not None:
                    ap["to_field"] = f
                    continue
            if f and a[0] != a[1]:
                kept.append({"op": "field_store", "field": f,
                             "src": norm_src(fn, slots, ve),
                             "site": {"file": fn.file,
                                      "line": ins.get("line")}})
    return kept, aux, buffers


def write_ops(ops):
    """Buffer-write ops in stream order (set_byte/copy/put_*/store_idx)."""
    return [o for o in ops
            if o["op"] in ("set_byte", "copy", "store_idx")
            or o["op"].startswith("put_")]


# ---------- conditions ----------

def _swap(op):
    return {"<": ">", ">": "<", "<=": ">=", ">=": "<="}.get(op, op)


def selector_of(e):
    """What a cond expr reads: 'version', 'len', a call's err, or None."""
    e = _unwrap_addr(e)
    if e is None:
        return None
    if e[0] == "builtin" and e[1] == "len":
        return ("len", e[2][0] if e[2] else None)
    if e[0] == "extract":
        base = _unwrap_addr(e[1])
        if base and base[0] == "call":
            name = base[1]
            if e[2] == 0 and (name.endswith(".Version")
                              or name.rsplit(".", 1)[-1] == "Version"):
                return ("version", base[1], e[2])
            return ("call_out", base[1], e[2])
        return ("extract",)
    if e[0] == "call":
        return ("call_out", e[1], 0)
    return None


def norm_cond(fn, e, dump=None, depth=0):
    """Normalize a path condition to a fact constraint (dict/atom/expr)."""
    if e is not None and e[0] == "not":
        return complement(norm_cond(fn, e[1], dump, depth))
    e = _unwrap_addr(e)
    if e is None or e[0] != "binop":
        if e is not None and e[0] == "extract":
            sel = selector_of(e)
            if sel and sel[0] == "call_out":
                return {"expr": M.expr_text(e)}
        return {"expr": M.expr_text(e)}
    op, a, b = e[1], e[2], e[3]
    sa, sb = selector_of(a), selector_of(b)
    if sb is not None and sa is None:
        a, b, sa, sb = b, a, sb, sa
        op = _swap(op)
    if sa is None:
        return {"expr": M.expr_text(e)}
    cv = M.const_val(b)
    if M.is_nil_const(b) or (b[0] == "const" and b[1] is None):
        cv = None
    if sa[0] == "len":
        if op == "==" and cv == 0:
            return "empty"
        if op == "!=" and cv == 0:
            return "not_empty"
        m = {"==": "len_eq", "!=": "len_ne", "<": "len_lt", "<=": "len_le",
             ">": "len_gt", ">=": "len_ge"}
        return {m.get(op, "len_" + op): cv}
    if sa[0] == "version":
        m = {"==": "version_eq", "!=": "version_ne", "<": "version_lt",
             "<=": "version_le", ">": "version_gt", ">=": "version_ge"}
        if op in m and isinstance(cv, int):
            return {m[op]: cv}
        return {"expr": M.expr_text(e)}
    if sa[0] == "call_out" and sa[2] == 1 and op == "!=":
        # `_, err := F(...); err != nil` — substitute F's reject conditions
        if dump is not None and depth < 3:
            rc = reject_conds_of_call(dump, sa[1], depth + 1)
            if rc:
                if len(rc) == 1:
                    return rc[0]
                return {"any": rc}
        return {"expr": M.expr_text(e)}
    if sa[0] == "call_out" and op == "!=":
        if dump is not None and depth < 3:
            rc = reject_conds_of_call(dump, sa[1], depth + 1)
            if rc:
                if len(rc) == 1:
                    return rc[0]
                return {"any": rc}
        return {"expr": M.expr_text(e)}
    return {"expr": M.expr_text(e)}


def complement(c):
    if not isinstance(c, dict):
        return {"not": c} if c not in ("empty", "not_empty") else (
            "not_empty" if c == "empty" else "empty")
    if "not" in c:
        return c["not"]
    flip = {"len_eq": "len_ne", "len_ne": "len_eq", "len_ge": "len_lt",
            "len_lt": "len_ge", "len_gt": "len_le", "len_le": "len_gt",
            "version_eq": "version_ne", "version_ne": "version_eq",
            "version_ge": "version_lt", "version_lt": "version_ge",
            "version_gt": "version_le", "version_le": "version_gt"}
    out = {}
    for k, v in c.items():
        if k in flip:
            out[flip[k]] = v
        else:
            return {"not": c}
    return out


def ret_class(fn, term):
    """Classify a return terminator: 'err' | 'ok' | 'value' | 'void'."""
    if term is None:
        return "void"
    if term["op"] == "panic":
        return "panic"
    if term["op"] != "return":
        return "void"
    args = term.get("args") or []
    if not args:
        return "ok"
    saw_err = False
    for a in args:
        e = M.expr(fn, a)
        e = _unwrap_addr(e)
        if e is None:
            continue
        if e[0] == "const" and (e[1] is None or e[3] == "nil"):
            continue
        if e[0] == "global":
            if "err" in e[1].lower():
                saw_err = True
            continue
        if e[0] == "call":
            nm = e[1]
            if "errors.New" in nm or "Errorf" in nm or "errors." in nm:
                saw_err = True
                continue
            return "value"
        if e[0] == "extract":
            # returned err extract -> err return
            if e[2] == 1:
                saw_err = True
                continue
            return "value"
        if e[0] == "index" or e[0] == "slice":
            return "value"
        if e[0] in ("binop", "field", "param", "load"):
            return "value"
    return "err" if saw_err else "ok"


def reject_conds(fn, dump, depth=0):
    """Normalized condition-sets under which fn returns an error value."""
    seq, ok = M.walk_seq(fn)
    out = []
    for conds, term in M.seq_leaves(seq):
        if ret_class(fn, term) == "err":
            nc = [norm_cond(fn, c, dump, depth) for c in conds]
            out.append(nc)
    return out


def reject_conds_of_call(dump: M.Dump, fid, depth):
    f = dump.funcs.get(fid)
    if f is None:
        for k, v in dump.funcs.items():
            if k.endswith(fid) or short_fn(k) == short_fn(fid):
                f = v
                break
    if f is None:
        return []
    flat = []
    for cs in reject_conds(f, dump, depth):
        flat.extend(cs)
    return flat


def predicate_rules(fn, dump):
    """Build the accept-rule list for a validator-style function."""
    seq, complete = M.walk_seq(fn)
    arms = []  # (selector, [accept residuals], has_err, has_ok, order)
    order = []
    for conds, term in M.seq_leaves(seq):
        nc = [norm_cond(fn, c, dump) for c in conds]
        cls = ret_class(fn, term)
        if cls not in ("err", "ok", "value"):
            continue
        ok = cls == "ok"
        # selector: positive version_eq / empty atoms in conds
        vers = [c["version_eq"] for c in nc
                if isinstance(c, dict) and "version_eq" in c]
        sel = None
        if "empty" in nc:
            sel = "empty"
        elif vers:
            sel = ("version_in", tuple(sorted(set(vers))))
        else:
            sel = "otherwise"
        residuals = []
        if ok:
            for c in nc:
                if c in ("empty", "not_empty"):
                    continue
                if isinstance(c, dict) and any(
                        k.startswith("version_") for k in c):
                    continue
                residuals.append(c)
        key = sel
        arms.append((key, residuals if ok else None, cls, len(order)))
        order.append(key)
    rules = []
    seen = {}
    for key, res, cls, _i in arms:
        if key not in seen:
            seen[key] = {"res": [], "has_err": False, "has_ok": False}
        s = seen[key]
        if cls in ("err",):
            s["has_err"] = True
        elif res is not None:
            s["has_ok"] = True
            s["res"].extend(res)
        else:
            s["has_ok"] = True
    for key in order:
        s = seen.pop(key, None)
        if s is None:
            continue
        if key == "empty":
            cond = "empty"
        elif key == "otherwise":
            cond = "otherwise"
        else:
            cond = {"version_in": list(key[1])}
        if not s["has_ok"]:
            then = False
        else:
            rs = s["res"]
            if not rs:
                then = True
            elif len(rs) == 1:
                then = rs[0]
            else:
                then = {"all": rs}
        rules.append({"if": cond, "then": then})
    return rules, complete


# ---------- getters ----------

def _accessor_of(fn, e, dump=None, depth=0):
    """expr -> (accessor, offset, width) for a getter's returned value."""
    e = _unwrap_addr(e)
    if e is None:
        return None
    if e[0] == "call":
        name = e[1]
        if name.startswith(ENDIAN_PREFIX):
            m = name[len(ENDIAN_PREFIX):]
            if m in GETS and len(e[2]) == 2:
                w = slice_window(fn, e[2][1])
                if w and isinstance(w[1], int) and isinstance(w[2], int):
                    return ("big_endian_" + m.lower(), w[1], w[2] - w[1])
        if name.endswith("BytesToHash") or name.endswith("BytesToAddress"):
            w = slice_window(fn, e[2][0])
            if w and isinstance(w[1], int):
                return ("bytes", w[1],
                        (w[2] - w[1]) if isinstance(w[2], int) else None)
        if name.endswith(".Bytes") or name.endswith(".String"):
            w = slice_window(fn, e[2][0])
            if w:
                return ("raw", w[1],
                        (w[2] - w[1]) if isinstance(w[2], int) else None)
        # delegate: return g.SomeGetter() where SomeGetter is another
        # bytes-recv getter in the dump
        if dump is not None and depth < 3:
            tgt = dump.funcs.get(name)
            if tgt is not None and tgt is not fn:
                hits, _g, _c = getter_info(tgt, dump, depth + 1)
                if hits:
                    return ("delegate", hits)
    if e[0] == "index" or e[0] == "indexaddr":
        k = M.const_val(e[2])
        if isinstance(k, int):
            return ("byte_at", k, 1)
    if e[0] == "slice":
        lo, hi = M.const_val(e[2]), M.const_val(e[3])
        return ("bytes", lo or 0,
                (hi - (lo or 0)) if isinstance(hi, int) else None)
    if e[0] == "extract":
        base = _unwrap_addr(e[1])
        if base and base[0] == "call" and e[2] == 0:
            return _accessor_of(fn, base, dump, depth)
    if e[0] == "param":
        return ("identity", 0, None)
    return None


def getter_info(fn, dump, depth=0):
    """Analyze a candidate getter -> {offset,width,accessor,when,guards}."""
    seq, complete = M.walk_seq(fn)
    hits = []
    guards = []
    for ins, _loop in M.seq_instrs(fn, seq):
        if ins["op"] == "call" and ins.get("fn", "").endswith(".validate"):
            guards.append("validate")
    for conds, term in M.seq_leaves(seq):
        if ret_class(fn, term) not in ("value", "ok"):
            continue
        args = term.get("args") or []
        if not args:
            continue
        acc = _accessor_of(fn, M.expr(fn, args[0]), dump, depth)
        if acc is None:
            continue
        when = None
        nc = [norm_cond(fn, c, dump) for c in conds]
        vers = [c for c in nc if isinstance(c, dict) and
                any(k.startswith("version_") for k in c)]
        if vers:
            when = vers[0] if len(vers) == 1 else {"all": vers}
        if acc[0] == "delegate":
            for h in acc[1]:
                w = h["when"]
                both = [x for x in (when, w) if x]
                hits.append({"accessor": h["accessor"],
                             "offset": h["offset"], "width": h["width"],
                             "when": both[0] if len(both) == 1 else
                             ({"all": both} if both else None),
                             "conds": nc})
        else:
            hits.append({"accessor": acc[0], "offset": acc[1],
                         "width": acc[2], "when": when, "conds": nc})
    return hits, guards, complete


# ---------- partiality ----------

def partiality_sites(fn, seq):
    """Every slice/index/indexaddr site with its bound form."""
    slots = recv_slots(fn)
    sites = []
    for ins, in_loop in M.seq_instrs(fn, seq):
        if ins["op"] not in ("slice", "index", "indexaddr", "lookup"):
            continue
        e = M.expr(fn, ins["id"])
        base, lo, hi = None, None, None
        if e[0] == "slice":
            base = M.expr_text(e[1])
            lo = M.const_val(e[2])
            hi = M.const_val(e[3])
            form = "slice"
        elif e[0] in ("index", "indexaddr"):
            base = M.expr_text(e[1])
            lo = M.const_val(e[2])
            form = "index" if e[0] == "index" else "index_addr"
        else:
            continue
        bound = "unverified"
        if in_loop:
            bound = "loop_index"
        elif isinstance(lo, int) and (hi is None or isinstance(hi, int)):
            bound = "const"
        sites.append({
            "site": {"file": fn.file, "line": ins.get("line")},
            "form": form, "base": base,
            "lo": lo if lo is not None else M.expr_text(e[2] if e[0] == "slice" else e[2]),
            "hi": hi if hi is not None else (
                M.expr_text(e[3]) if e[0] == "slice" else None),
            "bound": bound,
        })
    sites.sort(key=lambda s: (s["site"]["file"], s["site"]["line"] or 0,
                              s["form"]))
    return sites


# ---------- extraction driver ----------

def is_bytes_recv(fn):
    r = fn.recv
    return bool(r and "Bytes" in r["type"])


def is_bytes_param(fn):
    for ins in fn.d["instrs"]:
        if ins["op"] == "param" and "[]byte" in ins.get("type", ""):
            return True
    return False


def classify(fn, ops, aux):
    for o in ops:
        if o["op"] in ("copy", "set_byte") or o["op"].startswith("put_"):
            if o.get("byte", True):
                return "encoder"
    if any(o["op"] == "append" for o in ops):
        return "appender"
    return "other"


def extract_codecs(dump: M.Dump, scope_prefix="common/batch"):
    encoders, predicates, decoders, coverage = {}, {}, {"getters": []}, {
        "modelled": [], "candidates": [], "debt": []}
    partiality = []
    for fid in sorted(dump.funcs):
        fn = dump.funcs[fid]
        if fn.d.get("anonymous"):
            coverage["debt"].append({
                "element": f"{fn.file}:{fn.line} func literal {fn.name}",
                "kind": "anonymous", "reason": "closure bodies not reduced"})
            continue
        seq, complete = M.walk_seq(fn)
        if not complete:
            coverage["debt"].append({
                "element": f"{fn.file}:{fn.line} func {fn.name}",
                "kind": "cfg", "reason": "walk budget exceeded"})
            continue
        ops, aux, buffers = codec_ops(fn, seq)
        kind = classify(fn, ops, aux)
        short = short_fn(fid)
        recv_t = (fn.recv or {}).get("type", "").rsplit("/", 1)[-1].lstrip("*")
        label = f"{recv_t}.{fn.name}" if fn.recv else fn.name
        label = f"{fn.d['pkg'].rsplit('/',1)[-1]}/{label}" if "/" not in (fn.recv or {}).get("type", "") else label
        entry = {"function": label, "id": fid, "file": fn.file,
                 "line": fn.line, "pkg": fn.d["pkg"]}
        partiality.extend(partiality_sites(fn, seq))

        if kind == "encoder":
            wops = write_ops(ops)
            dsts = {o.get("dst") for o in wops if o.get("dst")}
            composite = any(d and d[0] == "call" for d in dsts)
            # length = the alloc receiving the most writes (if any)
            from collections import Counter
            cnt = Counter(o.get("dst") for o in wops)
            length = None
            for k, _n in cnt.most_common():
                if k and k[0] == "alloc" and k in buffers \
                        and buffers[k].get("len"):
                    length = buffers[k]["len"]
                    break
            encoders[label] = {
                "kind": "encoder", "lang": "go-bytes",
                "function": label, "id": fid, "file": fn.file,
                "line": fn.line, "pkg": fn.d["pkg"],
                "memory_init": "zeros",
                "length": length,
                "composite": composite,
                "ops": [{kk: vv for kk, vv in o.items()
                         if kk in ("op", "offset", "src", "dst") or kk == "site"}
                        for o in wops],
                "field_stores": [o for o in ops if o["op"] == "field_store"],
            }
            coverage["modelled"].append(f"{label} (encoder)")
        elif fn.name == "validate" or (
                ret_is_err(fn) and any(
                    "version" in M.expr_text(M.expr(fn, i.get("cond")))
                    for i in fn.d["instrs"] if i["op"] == "if")):
            rules, _c = predicate_rules(fn, dump)
            predicates[label] = {
                "kind": "predicate", "lang": "go", "function": label,
                "id": fid, "file": fn.file, "line": fn.line,
                "pkg": fn.d["pkg"], "rules": rules,
            }
            coverage["modelled"].append(f"{label} (predicate)")
        else:
            hits, guards, _c = getter_info(fn, dump)
            if hits and any(h["accessor"] != "identity" for h in hits):
                decoders["getters"].append({
                    "function": label, "id": fid, "file": fn.file,
                    "line": fn.line, "pkg": fn.d["pkg"],
                    "accessors": [
                        {"accessor": h["accessor"], "offset": h["offset"],
                         "width": h["width"], "when": h["when"]}
                        for h in hits],
                    "guards": sorted(set(guards)),
                })
                coverage["modelled"].append(f"{label} (getter)")
            elif hits or aux or ops:
                coverage["candidates"].append(entry)
    decoders["getters"].sort(key=lambda g: (g["pkg"], g["file"], g["line"]))
    partiality.sort(key=lambda s: (s["site"]["file"], s["site"]["line"] or 0,
                                   s["form"]))
    coverage["modelled"].sort()
    coverage["candidates"].sort(key=lambda e: (e["file"], e["line"]))
    coverage["debt"].sort(key=lambda e: e["element"])
    return {
        "format": "holon-extracted/go-codecs/0.1",
        "extractor": "holon.frontends.go (gossa-dump/0.1)",
        "scope": scope_prefix,
        "encoders": encoders,
        "predicates": predicates,
        "decoders": decoders,
        "partiality": partiality,
        "coverage": coverage,
    }


def ret_is_err(fn):
    sig = fn.d.get("signature", "")
    return sig.rstrip().endswith("error") or ", error)" in sig or sig.endswith("error)")
