"""The sections of a Go document, computed over the whole program (every package of every document) and split by
package: functions with paths and sites, codecs, slices, calls, loops and coverage (the contract's Analysis)."""
from __future__ import annotations

import json

from .ctx import Ctx, binary_op, fn_span, site_pos
from .flow import Flow
from .paths import Enumerator, OtherLoop, PathLimit
from .ssaload import Func, Instr, span_of
from .terms import (C0, NIL, Reasoner, atom_vars, const, is_const, key, lin, op, plus, to_json, witness_range)


def _rooted(t, allow_global=True) -> bool:
    """t is a parameter or (when allowed) a global, or a field / index / slice chain over one."""
    while isinstance(t, tuple) and t:
        if t[0] == "param":
            return True
        if t[0] == "global":
            return allow_global
        if t[0] in ("field", "index", "slice"):
            t = t[1]
            continue
        return False
    return False


def subst(t, m: dict):
    """Replace ["param", p] by m[p] throughout a term, atom, backing or case."""
    if isinstance(t, tuple):
        if len(t) == 2 and t[0] == "param" and t[1] in m:
            return m[t[1]]
        return tuple(subst(x, m) for x in t)
    return t


def _ukey(u: dict):
    return (u["kind"], u["callee"] or "", -1 if u["index"] is None else u["index"], u["site"])


class Case:
    __slots__ = ("cond", "backing", "offset", "len", "cap")

    def __init__(self, cond, backing, offset, ln, cap):
        self.cond, self.backing, self.offset, self.len, self.cap = tuple(cond), backing, offset, ln, cap

    def tup(self):
        return (self.cond, self.backing, self.offset, self.len, self.cap)

    def subst(self, m):
        return Case(subst(self.cond, m), subst(self.backing, m), subst(self.offset, m), subst(self.len, m),
                    subst(self.cap, m))


class Analysis:
    def __init__(self, ctx: Ctx):
        self.ctx = ctx
        self.prog = ctx.prog
        self.ty = ctx.types
        self.flows: dict[str, Flow] = {}
        self.enum: dict[str, object] = {}
        self._cases: dict = {}
        self._results: dict = {}
        self._writes: dict = {}
        self.listed = sorted(fid for fid, f in self.prog.funcs.items() if f.synthetic == "")

    def flow(self, fid: str) -> Flow:
        f = self.flows.get(fid)
        if f is None:
            f = Flow(self.ctx, self.prog.funcs[fid])
            self.flows[fid] = f
        return f

    # ================================================================== functions, paths, sites
    def codec_shaped(self, fn: Func) -> bool:
        return any(self.ty.is_bytes_shape(t) for _, t in fn.params) or \
            any(self.ty.is_bytes_shape(t) for t in fn.results)

    def enumerate(self, fid: str):
        """The path enumeration of a loop-free, non-recursive function (Result), or the reason there is none."""
        if fid in self.enum:
            return self.enum[fid]
        fn = self.prog.funcs[fid]
        if not fn.has_body:
            r = "not_codec"
        elif not self.ctx.loop_free(fid):
            r = "loop"
        elif fid in self.ctx.recursive:
            r = "recursion"
        else:
            try:
                r = Enumerator(self.ctx, self.flows, fn).run()
            except PathLimit:
                r = "path_limit"
                self.ctx.debt_entry(fid, "path_limit", fn_span(fn),
                                    f"more than {self.ctx.max_paths} paths: no path set; sites by dominator atoms")
        self.enum[fid] = r
        return r

    def function_entry(self, fid: str) -> dict:
        fn = self.prog.funcs[fid]
        r = self.enumerate(fid)
        paths, reason = None, None
        if isinstance(r, str):
            reason = r
        elif self.codec_shaped(fn):
            paths = [to_json(p) for p in r.paths]
        else:
            reason = "not_codec"
        if not isinstance(r, str):
            for pos, what in r.unsupported:
                self.ctx.debt_entry(fid, "unsupported", pos, what)
        entry = {"span": fn_span(fn), "package": fn.package,
                 "params": [{"name": n, "type": t} for n, t in fn.params], "results": list(fn.results),
                 "loop_free": self.ctx.loop_free(fid) if fn.has_body else True,
                 "paths": paths, "paths_reason": reason, "sites": self.sites(fid)}
        if self.ctx.config_version == "holon-go-frontend/0.2":   # I67: additive loop-body paths over the iv
            lb = self.loop_bodies(fid)
            if lb is not None:
                entry["loop_bodies"] = lb
        return entry

    def loop_bodies(self, fid: str) -> list | None:
        """holon-go-frontend/0.2's loop_bodies (I67): one iteration of each counted or range loop of step 1 with an
        induction phi and a fuel, as loop-free paths over its symbolic induction variable
        (holon.frontends.go.paths.Enumerator.run_loop), in header order; None when the function has no such loop. An
        entry is the loop's go.loops fields and its paths, each written as the paths section writes one (end panic,
        return or continue). A body over the path limit has paths null and a path_limit debt entry; an unsupported
        construct is a debt entry, as in a path enumeration; a path that meets another loop's header (that loop is not
        enumerated) gives the body paths null and an unsupported debt entry."""
        fn = self.prog.funcs[fid]
        if not fn.has_body or not self.codec_shaped(fn):
            return None
        fl = self.flow(fid)
        out = []
        for L in fl.loops():
            if L.kind not in ("counted", "range") or L.phi is None or L.fuel is None or L.step != 1:
                continue
            try:
                res = Enumerator(self.ctx, self.flows, fn).run_loop(L)
            except PathLimit:
                paths = None
                self.ctx.debt_entry(fid, "path_limit", L.span,
                                    f"more than {self.ctx.max_paths} paths in one iteration of the loop: no loop body")
            except OtherLoop:
                paths = None
                self.ctx.debt_entry(fid, "unsupported", L.span,
                                    "another loop on a path of one iteration (nested or after the exit): no loop body")
            else:
                paths = [to_json(p) for p in res.paths]
                for pos, what in res.unsupported:
                    self.ctx.debt_entry(fid, "unsupported", pos, what)
            out.append({"span": L.span, "iv": L.iv, "init": to_json(L.init), "step": L.step, "cmp": L.cmp,
                        "limit": to_json(L.limit), "fuel": to_json(L.fuel), "exits": list(L.exits), "paths": paths})
        return out or None

    def sites(self, fid: str) -> list:
        fn = self.prog.funcs[fid]
        fl = self.flow(fid)
        r = self.enumerate(fid)
        out = []
        listed = {s.id: s for s in fl.sites()}
        extra = {} if isinstance(r, str) else r.extra_sites
        for sid in sorted(set(listed) | set(extra)):
            if sid in listed:
                s = listed[sid]
                kind, bound, block = s.kind, s.bound, s.instr.block.index
            else:
                kind, bound = extra[sid]
                block = None
            witness = None
            if bound is None:
                status = "open"
            elif not isinstance(r, str):
                status = "open" if sid in r.ends else "safe"
            else:
                facts = fl.dom_atoms(block) + fl.loop_facts(block)
                rs = Reasoner(facts, self.ctx.nonnil)
                bad = [a for a in bound if not rs.implies(a)]
                status = "open" if bad else "safe"
                if bad:
                    witness = self.witness(fl, block, bad)
            out.append({"id": sid, "kind": kind, "bound": to_json(bound) if bound is not None else None,
                        "status": status, "witness": witness})
        return out

    def witness(self, fl: Flow, block: int, bad: list):
        for a in bad:
            vs = atom_vars(a)
            if len(vs) != 1:
                continue
            v = vs[0]
            for L in fl.loops():
                if L.in_succ is None or not fl.fn.dominates(L.in_succ, block):
                    continue
                if L.kind != "counted" or L.phi is None or not is_const(L.init or ("x",)) \
                        or not is_const(L.limit or ("x",)) or L.step != 1:
                    continue
                pv = ("var", L.phi.name, L.phi.get("comment") or None)
                if v != pv:
                    continue
                cx, kx = lin(L.x)
                if cx != {pv: 1}:
                    continue
                lo = L.init[1] - kx
                hi = (L.limit[1] - 1 if L.cmp == "<" else L.limit[1] if L.cmp == "<=" else None)
                if hi is None:
                    continue
                hi -= kx
                w = witness_range(a, pv, lo, hi)
                if w is not None:
                    return {"var": pv[2], "min": w[0], "max": w[1]}
        return None

    # ================================================================== codecs
    def path_functions(self):
        """Functions whose paths are listed (loop-free, codec-shaped, enumerated)."""
        for fid in self.listed:
            fn = self.prog.funcs[fid]
            r = self.enumerate(fid)
            if not isinstance(r, str) and self.codec_shaped(fn):
                yield fid, fn, r

    def encoders(self) -> list:
        if hasattr(self, "_encoders"):
            return self._encoders
        out = {}
        order = []
        for fid, fn, r in self.path_functions():
            for p, lays in zip(r.paths, r.layouts):
                for (i, n, cells, pos) in lays:
                    k = (fid, i, n, tuple(cells))
                    if k not in out:
                        out[k] = {"function": fid, "result": i, "length": n, "cells": to_json(list(cells)),
                                  "conds": [], "exact": all(c != ("unknown",) for c in cells), "_pos": pos}
                        order.append(k)
                    out[k]["conds"].append(to_json(p["cond"]))
        encs = [out[k] for k in order]
        encs.sort(key=lambda e: (e["function"], e["length"], json.dumps(e["cells"])))
        for e in encs:
            if not e["exact"]:
                self.ctx.debt_entry(e["function"], "inexact_layout", e["_pos"],
                                    f"layout of the {e['length']}-byte allocation has unknown cells")
        self._encoders = encs
        return encs

    def read_of(self, t, P):
        """(offset, width, via) when t reads the parameter P."""
        if not isinstance(t, tuple) or not t:
            return None
        if t[0] == "index" and t[1] == P and is_const(t[2]):
            return (t[2][1], 1, "index")
        if t[0] == "call":
            bo = binary_op(t[1])
            args = t[2]
            sl = None
            width = None
            via = None
            if bo is not None and not bo[1] and len(args) == 2:
                sl, width, via = args[1], bo[2], "be_uint" if bo[0] == "be" else "le_uint"
            else:
                prim = self.ctx.prims.get(t[1])
                if prim and prim.get("kind") == "to_array" and len(args) == 1:
                    sl, width, via = args[0], prim.get("width"), "to_array"
            if sl is not None and isinstance(sl, tuple) and sl[:1] == ("slice",) and sl[1] == P:
                lo = sl[2] if sl[2] is not None else C0
                hi = sl[3]
                if hi is not None and is_const(lo) and is_const(hi) and hi[1] - lo[1] == width:
                    return (lo[1], width, via)
        return None

    def byte_param(self, fn: Func):
        ps = [n for n, t in fn.params if self.ty.is_byte_slice(t)]
        return ps[0] if len(ps) == 1 else None

    def decoders(self) -> list:
        out = []
        for fid, fn, r in self.path_functions():
            pname = self.byte_param(fn)
            if pname is None or not fn.results:
                continue
            P = ("param", pname)
            reads = set()
            ok = True
            seen = False
            for p in r.paths:
                if p["end"] != "return" or p["error"] not in (None, "nil"):
                    continue
                seen = True
                rd = self.read_of(p["returns"][0], P)
                if rd is None:
                    ok = False
                    break
                reads.add(rd)
            if ok and seen:
                out.append({"function": fid, "param": pname,
                            "reads": [{"offset": o, "width": w, "via": v} for o, w, v in sorted(reads)]})
        return out

    def predicates(self) -> list:
        out = []
        for fid, fn, r in self.path_functions():
            pname = self.byte_param(fn)
            if pname is None or fn.results not in (["error"], ["bool"]):
                continue
            P = ("param", pname)
            oks = []
            for p in r.paths:
                if p["end"] != "return":
                    continue
                if fn.results == ["error"] and p["error"] == "nil":
                    oks.append(p)
                elif fn.results == ["bool"] and p["returns"] == [("bool", True)]:
                    oks.append(p)
            tag, accepts = None, None
            pins = []
            for p in oks:
                lens = {a[2][1] for a in p["cond"] if a[0] == "==" and a[1] == ("len", P) and is_const(a[2])}
                idx = {}
                for a in p["cond"]:
                    if a[0] == "==" and isinstance(a[1], tuple) and a[1][:2] == ("index", P) and is_const(a[1][2]) \
                            and is_const(a[2]):
                        idx.setdefault(a[1][2][1], set()).add(a[2][1])
                pins.append((lens, idx))
            if oks and all(len(l) == 1 for l, _ in pins):
                common = set.intersection(*[set(k for k, vs in i.items() if len(vs) == 1) for _, i in pins])
                if len(common) == 1:
                    k = common.pop()
                    tag = k
                    accepts = sorted({(next(iter(i[k])), next(iter(l))) for l, i in pins})
            out.append({"function": fid, "param": pname, "tag_index": tag,
                        "accepts": [{"value": v, "length": n} for v, n in accepts] if accepts is not None else None})
        return out

    def matches(self, preds: list) -> list:
        encs = self.encoders()
        out = []
        for p in preds:
            if p["tag_index"] is None:
                continue
            k = p["tag_index"]
            for a in p["accepts"]:
                fs = sorted({e["function"] for e in encs if e["length"] == a["length"] and k < len(e["cells"])
                             and e["cells"][k] == ["const", a["value"]]})
                out.append({"predicate": p["function"], "index": k, "value": a["value"], "length": a["length"],
                            "encoders": fs})
        out.sort(key=lambda m: (m["predicate"], m["index"], m["value"], m["length"]))
        return out

    def absences(self, matches: list) -> list:
        out = []
        for m in matches:
            pkg = self.prog.funcs[m["predicate"]].package
            if not any(self.prog.funcs[f].package == pkg for f in m["encoders"]):
                out.append({"predicate": m["predicate"], "index": m["index"], "value": m["value"],
                            "length": m["length"], "elsewhere": list(m["encoders"])})
        return out

    def patches(self) -> list:
        enc_results: dict[str, set] = {}
        for e in self.encoders():
            enc_results.setdefault(e["function"], set()).add(e["result"])
        out = []
        for fid in self.listed:
            fn = self.prog.funcs[fid]
            fl = self.flow(fid)
            for ins in fn.instrs:
                c = ins.call
                if ins.op != "Call" or not c or c.get("mode") != "static" or c.get("callee") not in enc_results:
                    continue
                callee = self.prog.funcs[c["callee"]]
                for ri in sorted(enc_results[c["callee"]]):
                    vals = self._result_values(fn, ins, ri, len(callee.results))
                    names = self._through_changetypes(fn, vals)
                    writes = []
                    for s in fn.instrs:
                        if s.op != "Store":
                            continue
                        a, v = s.operands[0], s.operands[1]
                        d = fn.defs.get(a.get("v", "")) if a and "v" in a else None
                        if d is None or d.op != "IndexAddr" or not d.operands[0] or d.operands[0].get("v") not in names:
                            continue
                        k, val = fl.term(d.operands[1]), fl.term(v)
                        if is_const(k) and is_const(val):
                            writes.append({"index": k[1], "value": val[1], "site": site_pos(s)})
                    returned = any(x.op == "Return" and any(o and o.get("v") in names for o in x.operands)
                                   for x in fn.instrs)
                    if writes and returned:
                        out.append({"function": fid, "encoder": c["callee"], "site": c.get("pos") or site_pos(ins),
                                    "writes": writes, "guards": to_json(fl.dom_atoms(ins.block.index)),
                                    "returned": True})
        out.sort(key=lambda p: (p["function"], p["site"]))
        return out

    def _result_values(self, fn: Func, call: Instr, ri: int, nres: int) -> set:
        if nres == 1:
            return {call.name}
        out = set()
        for r in fn.referrers(call.name):
            if r.op == "Extract" and r.get("index") == ri:
                out.add(r.name)
        return out

    def _through_changetypes(self, fn: Func, names: set) -> set:
        out = set(names)
        stack = list(names)
        while stack:
            n = stack.pop()
            for r in fn.referrers(n):
                if r.op in ("ChangeType",) and r.name not in out:
                    out.add(r.name)
                    stack.append(r.name)
        return out

    # ================================================================== slices
    def cases(self, fid: str, o, visiting=None) -> list:
        fn = self.prog.funcs[fid]
        fl = self.flow(fid)
        L = fl.lengths
        T = fl.term
        if o is None:
            return [Case((), ("unknown", "value"), ("unknown", "value"), ("unknown", "value"),
                         ("unknown", "value"))]
        if "const" in o:
            t = T(o)
            if t == NIL:
                return [Case((), ("none",), C0, C0, C0)]
            return [Case((), ("unknown", "const"), C0, L.len_(t), L.cap_(t))]
        if "param" in o or "free" in o:
            t = T(o)
            return [Case((), ("of", t), C0, L.len_(t), L.cap_(t))]
        if "v" not in o:
            t = T(o)
            return [Case((), ("unknown", "value"), ("unknown", "value"), L.len_(t), L.cap_(t))]
        name = o["v"]
        ck = (fid, name)
        if ck in self._cases:
            return self._cases[ck]
        visiting = visiting if visiting is not None else set()
        if ck in visiting:
            return [Case((), ("unknown", "cycle"), ("unknown", "cycle"), L.len_(T(o)), L.cap_(T(o)))]
        visiting.add(ck)
        try:
            r = self._cases_of(fid, fn, fl, fn.defs[name], visiting)
        finally:
            visiting.discard(ck)
        if not visiting:
            self._cases[ck] = r
        return r

    def _cases_of(self, fid, fn, fl, d: Instr, visiting) -> list:
        L = fl.lengths
        T = fl.term
        ty = self.ty
        t = T({"v": d.name})
        unknown = lambda why: [Case((), ("unknown", why), ("unknown", why), L.len_(t), L.cap_(t))]  # noqa: E731
        op_ = d.op
        if op_ in ("ChangeType", "ChangeInterface"):
            return self.cases(fid, d.operands[0], visiting)
        if op_ == "Convert":
            src = self.ctx.operand_type(fn, d.operands[0])
            if ty.is_slice(src):
                return self.cases(fid, d.operands[0], visiting)
            if ty.is_string(src):
                return [Case((), ("fresh", site_pos(d)), C0, L.len_(T(d.operands[0])), ("unknown", "convert"))]
            return unknown("convert")
        if op_ == "Slice":
            x = d.operands[0]
            xt = self.ctx.operand_type(fn, x)
            lo = T(d.operands[1]) if d.operands[1] else None
            hi = T(d.operands[2]) if d.operands[2] else None
            mx = T(d.operands[3]) if d.operands[3] else None
            n = ty.array_len(xt)
            if ty.is_pointer(xt) and n is not None:
                a = fl.addr(x)
                N = const(n)
                lo_ = lo or C0
                ln = op("-", hi or N, lo_)
                cp = op("-", mx or N, lo_)
                if a[0] == "local":
                    alloc = fn.defs[a[1]]
                    return [Case((), ("fresh", site_pos(alloc)), lo_, ln, cp)]
                return [Case((), ("of", T(x)), lo_, ln, cp)]
            if ty.is_string(xt):
                return unknown("string")
            out = []
            for c in self.cases(fid, x, visiting):
                lo_ = lo or C0
                off = plus(c.offset, lo_) if lo else c.offset
                ln = op("-", hi, lo_) if hi else op("-", c.len, lo_)
                cp = op("-", mx, lo_) if mx else op("-", c.cap, lo_)
                out.append(Case(c.cond, c.backing, off, ln, cp))
            return out
        if op_ == "MakeSlice":
            return [Case((), ("fresh", site_pos(d)), C0, T(d.operands[0]), T(d.operands[1]))]
        if op_ == "UnOp" and d.get("unop") == "*":
            a = fl.addr(d.operands[0])
            if a[0] == "term":
                v = a[1]
                return [Case((), ("of", v), C0, L.len_(v), L.cap_(v))]
            store = self._dominating_store(fl, a, d)
            if store is None:
                return unknown("memory")
            s, steps_rest = store
            if not steps_rest:
                return self.cases(fid, s.operands[1], visiting)
            v = t
            return [Case((), ("of", v), C0, L.len_(v), L.cap_(v))]
        if op_ in ("Field", "Index", "Lookup"):
            return [Case((), ("of", t), C0, L.len_(t), L.cap_(t))]
        if op_ == "Phi":
            out, seen = [], set()
            for e in d.operands:
                for c in self.cases(fid, e, visiting):
                    k = c.tup()
                    if k not in seen:
                        seen.add(k)
                        out.append(c)
            return out
        if op_ in ("Call", "Extract"):
            if op_ == "Extract":
                src = d.operands[0]
                cd = fn.defs.get(src.get("v", "")) if src and "v" in src else None
                if cd is None or cd.op != "Call":
                    return unknown("call")
                ri = d.get("index")
            else:
                cd, ri = d, 0
            c = cd.call
            if c.get("mode") == "builtin" and c.get("callee") == "append" and op_ == "Call":
                x, y = c["args"][0], c["args"][1]
                tx, tyy = T(x), T(y)
                S = op("+", L.len_(tx), L.len_(tyy))
                cap_x = L.cap_(tx)
                out = []
                for cx in self.cases(fid, x, visiting):
                    out.append(Case(cx.cond + (("<=", S, cap_x),), cx.backing, cx.offset, S, cx.cap))
                out.append(Case(((">", S, cap_x),), ("fresh", c.get("pos") or site_pos(cd)), C0, S,
                                ("unknown", "growth")))
                return out
            if c.get("mode") == "static":
                fid2 = c["callee"]
                prim = self.ctx.prims.get(fid2)
                if prim and prim.get("kind") == "array_bytes":
                    w = const(prim.get("width") or 0)
                    return [Case((), ("fresh", c.get("pos") or site_pos(cd)), C0, w, w)]
                callee = self.prog.funcs.get(fid2)
                if callee is not None and callee.has_body and ri < len(callee.results):
                    res = self.result_cases(fid2, ri, visiting)
                    if res is None:
                        return unknown("cycle")
                    m = {}
                    for (pn, _), a in zip(callee.params, c.get("args") or []):
                        m[pn] = T(a)
                    return [x.subst(m) for x in res]
            return unknown("call")
        return unknown(op_.lower())

    def _dominating_store(self, fl: Flow, a, at: Instr):
        """(store, remaining steps) of the one store that dominates a load from the function's own memory with no
        other store to that address on the way; None otherwise."""
        from .flow import _is_prefix
        root, steps = a[1], a[2]
        cands, relevant = [], []
        for s, r, st in fl.stores():
            if r != root:
                continue
            if _is_prefix(st, steps, loose=True) or _is_prefix(steps, st, loose=True):
                relevant.append(s)
                if _is_prefix(st, steps) and all(x[1] is not None for x in st if x[0] == "index") \
                        and fl.dominates_instr(s, at):
                    cands.append((s, st))
        if not cands:
            return None
        s, st = max(cands, key=lambda c: (fl.fn.dom_depth(c[0].block.index), c[0].idx))
        for s2 in relevant:
            if s2 is not s and fl.fn.instr_reaches(s, s2) and fl.fn.instr_reaches(s2, at):
                return None
        return s, steps[len(st):]

    def result_cases(self, fid: str, ri: int, visiting=None):
        """All cases of result ri of fid over its Returns (in block order), each with the dominator-tree atoms into the
        Return's block before its own atoms; None on a cycle."""
        k = (fid, ri)
        if k in self._results:
            return self._results[k]
        visiting = visiting if visiting is not None else set()
        mark = ("result", fid, ri)
        if mark in visiting:
            return None
        visiting.add(mark)
        try:
            fn = self.prog.funcs[fid]
            fl = self.flow(fid)
            out = []
            for b in fn.blocks:
                last = b.last
                if last is None or last.op != "Return" or ri >= len(last.operands):
                    continue
                dom = tuple(fl.dom_atoms(b.index))
                for c in self.cases(fid, last.operands[ri], visiting):
                    out.append(Case(dom + c.cond, c.backing, c.offset, c.len, c.cap))
        finally:
            visiting.discard(mark)
        if not any(isinstance(m, tuple) and m[:1] == ("result",) for m in visiting):
            self._results[k] = out
        return out

    def results(self) -> list:
        out = []
        for fid in self.listed:
            fn = self.prog.funcs[fid]
            for i, t in enumerate(fn.results):
                if not self.ty.is_slice(t):
                    continue
                cs = self.result_cases(fid, i) or []
                out.append({"function": fid, "result": i,
                            "cases": [{"cond": to_json(list(c.cond)), "backing": to_json(c.backing),
                                       "offset": to_json(c.offset), "len": to_json(c.len), "cap": to_json(c.cap)}
                                      for c in cs]})
        return out

    def writes_of(self, fid: str) -> list:
        """In-place byte writes into parameter- or global-rooted backings."""
        if fid in self._writes:
            return self._writes[fid]
        fn = self.prog.funcs[fid]
        fl = self.flow(fid)
        L = fl.lengths
        T = fl.term
        ty = self.ty
        out = []

        def rooted(c):
            return c.backing[:1] == ("of",) and _rooted(c.backing[1])

        for ins in fn.instrs:
            if ins.op == "Call":
                c = ins.call
                site = c.get("pos") or site_pos(ins)
                dom = fl.dom_atoms(ins.block.index)
                if c.get("mode") == "builtin" and c.get("callee") == "append":
                    x, y = c["args"][0], c["args"][1]
                    if not ty.is_byte_slice(self.ctx.operand_type(fn, x)):
                        continue
                    tx = T(x)
                    S = op("+", L.len_(tx), L.len_(T(y)))
                    for cx in self.cases(fid, x):
                        if rooted(cx):
                            out.append({"function": fid, "site": site, "via": "append",
                                        "backing": cx.backing, "from": plus(cx.offset, L.len_(tx)),
                                        "to": plus(cx.offset, S),
                                        "cond": tuple(dom) + cx.cond + (("<=", S, L.cap_(tx)),)})
                elif c.get("mode") == "builtin" and c.get("callee") == "copy":
                    dst = c["args"][0]
                    if not ty.is_byte_slice(self.ctx.operand_type(fn, dst)):
                        continue
                    for cx in self.cases(fid, dst):
                        if rooted(cx):
                            out.append({"function": fid, "site": site, "via": "copy", "backing": cx.backing,
                                        "from": cx.offset, "to": plus(cx.offset, cx.len),
                                        "cond": tuple(dom) + cx.cond})
                elif c.get("mode") == "static" and binary_op(c.get("callee")) and binary_op(c["callee"])[1]:
                    dst = c["args"][1]
                    nb = binary_op(c["callee"])[2]
                    for cx in self.cases(fid, dst):
                        if rooted(cx):
                            out.append({"function": fid, "site": site, "via": "prim", "backing": cx.backing,
                                        "from": cx.offset, "to": plus(cx.offset, const(nb)),
                                        "cond": tuple(dom) + cx.cond})
            elif ins.op == "Store":
                a = ins.operands[0]
                d = fn.defs.get(a.get("v", "")) if a and "v" in a else None
                if d is None or d.op != "IndexAddr":
                    continue
                x = d.operands[0]
                xt = self.ctx.operand_type(fn, x)
                i = T(d.operands[1])
                dom = fl.dom_atoms(ins.block.index)
                if ty.is_byte_slice(xt):
                    for cx in self.cases(fid, x):
                        if rooted(cx):
                            off = plus(cx.offset, i)
                            out.append({"function": fid, "site": site_pos(ins), "via": "index",
                                        "backing": cx.backing, "from": off, "to": plus(off, const(1)),
                                        "cond": tuple(dom) + cx.cond})
                elif ty.is_pointer(xt) and ty.byte_array_len(ty.pointer_elem(xt)) is not None:
                    ta = fl.addr(x)
                    if ta[0] == "term" and _rooted(ta[1]):
                        out.append({"function": fid, "site": site_pos(ins), "via": "index",
                                    "backing": ("of", ta[1]), "from": i, "to": plus(i, const(1)),
                                    "cond": tuple(dom)})
        self._writes[fid] = out
        return out

    def writes(self) -> list:
        out = []
        for fid in self.listed:
            for w in self.writes_of(fid):
                out.append({k: to_json(v) if k in ("backing", "from", "to") else v for k, v in w.items()
                            if k != "cond"} | {"cond": to_json(list(w["cond"]))})
        out.sort(key=lambda w: (w["function"], w["site"]))
        return out

    def stores(self) -> list:
        out = []
        for fid in self.listed:
            fn = self.prog.funcs[fid]
            fl = self.flow(fid)
            for ins in fn.instrs:
                if ins.op != "Store":
                    continue
                a = fl.addr(ins.operands[0])
                if a[0] != "term" or not _rooted(a[1]):
                    continue
                out.append({"function": fid, "site": site_pos(ins), "target": to_json(a[1]),
                            "value": to_json(fl.term(ins.operands[1]))})
        out.sort(key=lambda s: (s["function"], s["site"]))
        return out

    def lost_writes(self) -> list:
        out = []
        for fid in self.listed:
            fn = self.prog.funcs[fid]
            fl = self.flow(fid)
            for ins in fn.instrs:
                if ins.op != "Alloc":
                    continue
                p = fl.param_copy_of(ins.name)
                if p is None or not self._copy_does_not_escape(fn, ins.name):
                    continue
                for s, root, steps in fl.stores():
                    if root != ins.name or not steps or any(x[0] != "field" for x in steps):
                        continue
                    if self._field_read_after(fn, fl, root, steps, s):
                        continue
                    out.append({"function": fid, "site": site_pos(s), "param": fn.params[p][0],
                                "field": [x[1] for x in steps], "value": to_json(fl.term(s.operands[1]))})
        out.sort(key=lambda x: (x["function"], x["site"]))
        return out

    def _copy_does_not_escape(self, fn: Func, root: str) -> bool:
        stack = [root]
        seen = set()
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            for r in fn.referrers(n):
                if r.op == "UnOp" and r.get("unop") == "*":
                    continue
                if r.op == "Store":
                    if r.operands[0] and r.operands[0].get("v") == n and not (r.operands[1] or {}).get("v") == n:
                        continue
                    return False
                if r.op in ("FieldAddr", "IndexAddr"):
                    stack.append(r.name)
                    continue
                if r.op == "Slice":
                    for u in fn.referrers(r.name):
                        c = u.call
                        if u.op == "Call" and c and c.get("mode") == "builtin" and c.get("callee") in ("copy", "len"):
                            continue
                        return False
                    continue
                return False
        return True

    def _field_read_after(self, fn: Func, fl: Flow, root: str, steps: tuple, s: Instr) -> bool:
        from .flow import _is_prefix
        for ins in fn.instrs:
            if ins is s:
                continue
            reads = False
            if ins.op == "UnOp" and ins.get("unop") == "*":
                a = fl.addr(ins.operands[0])
                reads = a[0] == "local" and a[1] == root and (_is_prefix(a[2], steps) or _is_prefix(steps, a[2]))
            elif ins.op == "Slice":
                a = fl.addr(ins.operands[0])
                reads = a[0] == "local" and a[1] == root and (_is_prefix(a[2], steps) or _is_prefix(steps, a[2]))
            if reads and fn.instr_reaches(s, ins):
                return True
        return False

    # ================================================================== calls
    def edges(self) -> list:
        out = []
        for fid in self.listed:
            fn = self.prog.funcs[fid]
            fl = self.flow(fid)
            for ins in fn.instrs:
                if ins.op not in ("Call", "Go", "Defer"):
                    continue
                c = ins.call
                if not c or c.get("mode") == "builtin":
                    continue
                site = (c.get("pos") or site_pos(ins)) if ins.op == "Call" else site_pos(ins)
                out.append({"caller": fid, "callee": self.ctx.callee_name(fn, c),
                            "kind": {"Call": "call", "Go": "go", "Defer": "defer"}[ins.op],
                            "site": site, "callee_kind": self.ctx.callee_kind(fn, c),
                            "in_loops": [L.span for L in fl.loops_containing(ins.block.index)]})
        out.sort(key=lambda e: (e["caller"], e["site"], e["callee"]))
        return out

    def producers(self) -> dict:
        """fid -> result indices with a view case (backing ["of", T], T rooted at a parameter)."""
        if hasattr(self, "_producers"):
            return self._producers
        out = {}
        for fid, fn in sorted(self.prog.funcs.items()):
            if not fn.has_body:
                continue
            for i, t in enumerate(fn.results):
                if not self.ty.is_slice(t):
                    continue
                for c in self.result_cases(fid, i) or []:
                    if c.backing[:1] == ("of",) and _rooted(c.backing[1], allow_global=False):
                        out.setdefault(fid, set()).add(i)
                        break
        self._producers = out
        return out

    def uses(self, fn: Func, starts: list) -> tuple[list, set, set]:
        """(uses, use instructions, derived value names) of the values in starts ({"v"} / {"param"} operands)."""
        out = []
        instrs = set()
        derived = set()
        seen = set()
        stack = list(starts)
        fl = self.flow(fn.id)
        while stack:
            o = stack.pop()
            k = json.dumps(o, sort_keys=True)
            if k in seen:
                continue
            seen.add(k)
            if "v" in o:
                derived.add(o["v"])
            for r in fn.operand_referrers(o):
                pos = [j for j, x in enumerate(r.operands) if x == o]

                def use(kind, callee=None, index=None, ck=None, at=r):
                    out.append({"kind": kind, "callee": callee, "index": index, "callee_kind": ck,
                                "site": (at.call or {}).get("pos") or site_pos(at)})
                    instrs.add(at.uid)
                if r.op in ("ChangeType", "ChangeInterface", "Phi"):
                    stack.append({"v": r.name})
                    continue
                if r.op == "Slice":
                    if 0 in pos:
                        use("slice")
                        stack.append({"v": r.name})
                    else:
                        use("other")
                    continue
                if r.op in ("Call", "Go", "Defer"):
                    c = r.call
                    args = c.get("args") or []
                    if c.get("mode") == "builtin":
                        name = c["callee"]
                        for j, a in enumerate(args):
                            if a != o:
                                continue
                            if name in ("len", "cap"):
                                use(name)
                            elif name == "append":
                                use("append_dst" if j == 0 else "append_src")
                            elif name == "copy":
                                use("copy_dst" if j == 0 else "copy_src")
                            else:
                                use("other")
                        continue
                    callee = self.ctx.callee_name(fn, c)
                    ck = self.ctx.callee_kind(fn, c)
                    shift = 1 if c.get("mode") == "invoke" else 0
                    if c.get("mode") == "invoke" and c.get("value") == o:
                        use("arg", callee, 0, ck)
                    for j, a in enumerate(args):
                        if a == o:
                            use("arg", callee, j + shift, ck)
                    if c.get("mode") == "dynamic" and c.get("value") == o:
                        use("other")
                    continue
                if r.op == "IndexAddr" and 0 in pos:
                    kinds = set()
                    for u in fn.referrers(r.name):
                        if u.op == "Store" and u.operands[0] and u.operands[0].get("v") == r.name:
                            kinds.add("index_store")
                        else:
                            kinds.add("index")
                    for kd in sorted(kinds or {"index"}):
                        use(kd)
                    continue
                if r.op in ("Index", "Lookup") and 0 in pos:
                    use("index")
                    continue
                if r.op == "Store":
                    use("store" if 1 in pos else "other")
                    continue
                if r.op == "Return":
                    for j in pos:
                        use("return", None, j)
                    continue
                if r.op == "BinOp" and r.get("binop") in ("==", "!=", "<", "<=", ">", ">="):
                    use("compare")
                    continue
                use("other")
        uniq = {}
        for u in out:
            uniq[_ukey(u)] = u
        return [uniq[k] for k in sorted(uniq)], instrs, derived

    def param_into(self, fid: str, param: int, level: int) -> dict:
        fn = self.prog.funcs[fid]
        us, _, _ = self.uses(fn, [{"param": param}])
        into = self.into(fn, us, level + 1) if level < self.ctx.flow_depth else []
        return {"callee": fid, "param": param, "uses": us, "into": into}

    def into(self, fn: Func, us: list, level: int) -> list:
        seen = set()
        out = []
        for u in us:
            if u["kind"] != "arg" or u["callee_kind"] != "analyzed":
                continue
            callee = self.prog.funcs.get(u["callee"])
            if callee is None or not callee.has_body or u["index"] >= len(callee.params):
                continue
            k = (u["callee"], u["index"])
            if k in seen:
                continue
            seen.add(k)
            out.append(self.param_into(u["callee"], u["index"], level))
        out.sort(key=lambda x: (x["callee"], x["param"]))
        return out

    def flows_(self) -> list:
        prods = self.producers()
        out = []
        for fid in self.listed:
            fn = self.prog.funcs[fid]
            fl = self.flow(fid)
            for ins in fn.instrs:
                c = ins.call
                if ins.op != "Call" or not c or c.get("mode") != "static" or c.get("callee") not in prods:
                    continue
                pid = c["callee"]
                producer = self.prog.funcs[pid]
                starts = []
                for ri in sorted(prods[pid]):
                    starts += [{"v": n} for n in sorted(self._result_values(fn, ins, ri, len(producer.results)))]
                us, use_instrs, derived = self.uses(fn, starts)
                m = {pn: fl.term(a) for (pn, _), a in zip(producer.params, c.get("args") or [])}
                backs = set()
                for ri in sorted(prods[pid]):
                    for cs in self.result_cases(pid, ri) or []:
                        if cs.backing[:1] == ("of",):
                            backs.add(subst(cs.backing, m))
                held, opaque = [], []
                uses_at = [x for x in fn.instrs if x.uid in use_instrs]
                for x in fn.instrs:
                    if x.op not in ("Call", "Go", "Defer") or x is ins or x.uid in use_instrs:
                        continue
                    xc = x.call
                    if not xc or xc.get("mode") == "builtin":
                        continue
                    if not fn.instr_reaches(ins, x) or not any(fn.instr_reaches(x, u) for u in uses_at):
                        continue
                    ck = self.ctx.callee_kind(fn, xc)
                    site = xc.get("pos") or site_pos(x)
                    if ck == "analyzed":
                        callee = self.prog.funcs[xc["callee"]]
                        mm = {pn: fl.term(a) for (pn, _), a in zip(callee.params, xc.get("args") or [])}
                        for w in self.writes_of(xc["callee"]):
                            if subst(w["backing"], mm) in backs:
                                held.append({"callee": xc["callee"], "site": site})
                                break
                    elif ck in ("external", "dynamic"):
                        args = list(xc.get("args") or [])
                        if xc.get("mode") == "invoke":
                            args = [xc.get("value")] + args
                        hit = False
                        for a in args:
                            if a and a.get("v") in derived:
                                hit = True
                            else:
                                ta = fl.term(a)
                                for b in backs:
                                    if self._prefix_of(ta, b[1]):
                                        hit = True
                        if hit:
                            opaque.append({"callee": self.ctx.callee_name(fn, xc), "site": site})
                held = sorted({(h["callee"], h["site"]) for h in held})
                opaque = sorted({(h["callee"], h["site"]) for h in opaque})
                out.append({"producer": pid, "caller": fid, "site": c.get("pos") or site_pos(ins), "uses": us,
                            "held_across": [{"callee": a, "site": b} for a, b in held],
                            "opaque_between": [{"callee": a, "site": b} for a, b in opaque],
                            "into": self.into(fn, us, 1)})
        out.sort(key=lambda f: (f["producer"], f["caller"], f["site"]))
        return out

    @staticmethod
    def _prefix_of(a, t) -> bool:
        """t is a or a field chain extension of a."""
        while True:
            if a == t:
                return True
            if isinstance(t, tuple) and t[:1] == ("field",):
                t = t[1]
                continue
            return False

    # ================================================================== loops
    def loops(self) -> list:
        out = []
        for fid in self.listed:
            fl = self.flow(fid)
            for L in fl.loops():
                out.append({"function": fid, "span": L.span, "depth": L.depth, "kind": L.kind, "iv": L.iv,
                            "init": to_json(L.init), "step": L.step, "cmp": L.cmp, "limit": to_json(L.limit),
                            "fuel": to_json(L.fuel), "exits": list(L.exits)})
                if L.fuel is None:
                    self.ctx.debt_entry(fid, "loop_bound", L.span,
                                        f"{L.kind} loop without a fuel term (no counted bound)")
        out.sort(key=lambda l: (l["function"], l["span"]))
        return out

    # ================================================================== package variables (I19 follow-up A19-13)
    def globals_(self) -> list:
        """go.globals (holon.frontends.go.extract docstring): the package variables a package initializer assigns as a
        whole, with their values and, for byte arrays, their cells."""
        stores: dict = {}
        for fid in sorted(self.prog.funcs):
            fn = self.prog.funcs[fid]
            if fn.synthetic != "package initializer":
                continue
            fl = self.flow(fid)
            for ins in fn.instrs:
                if ins.op != "Store":
                    continue
                a, v = ins.operands[0], ins.operands[1]
                if not a or "global" not in a or a["global"] not in self.prog.globals or "$" in a["global"]:
                    continue                # not a whole-variable store, or a synthetic variable (init$guard)
                stores.setdefault(a["global"], []).append(fl.term(v))
        out = []
        for gid in sorted(stores):
            g = self.prog.globals[gid]
            typ = self.ctx.global_type(gid)
            vals = stores[gid]
            value = vals[0] if len(vals) == 1 else ("unknown", "stores")
            out.append({"global": gid, "package": g.get("package") or "", "span": span_of(g.get("pos") or ""),
                        "type": typ, "value": to_json(value), "cells": self._global_cells(value, typ)})
        return out

    def _global_cells(self, value, typ: str):
        n = self.ty.byte_array_len(typ)
        if n is None:
            return None
        if isinstance(value, tuple) and value[:1] == ("call",) and len(value) == 3:
            prim = self.ctx.prims.get(value[1]) or {}
            args = value[2]
            if prim.get("kind") == "hex_to_array" and prim.get("width") == n and len(args) == 1 \
                    and isinstance(args[0], tuple) and args[0][:1] == ("str",):
                raw = hex_bytes(args[0][1])
                if raw is not None:
                    raw = raw[-n:] if len(raw) > n else bytes(n - len(raw)) + raw
                    return [["const", b] for b in raw]
                return [["unknown"] for _ in range(n)]
        return [["byte", to_json(value), k] for k in range(n)]


def hex_bytes(s: str) -> bytes | None:
    """The bytes of a hexadecimal string (an optional 0x / 0X prefix removed, an odd count left-padded with "0"), or
    None when it holds a character that is not a hexadecimal digit."""
    if s[:2] in ("0x", "0X"):
        s = s[2:]
    if len(s) % 2:
        s = "0" + s
    try:
        return bytes.fromhex(s) if all(c in "0123456789abcdefABCDEF" for c in s) else None
    except ValueError:
        return None
