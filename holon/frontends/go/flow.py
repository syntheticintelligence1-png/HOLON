"""Flow-insensitive values of one function: terms built from definitions (phis stay ["var", ...]), loads from the
function's own memory by the one dominating store, dominator-edge atoms, natural loops with their bounds as fuel, and
the bounds-checked sites with their bound atoms.

This is the view of functions with loops (and of every function in the slices, calls and loops passes); loop-free
functions additionally get exact path sets from paths.py.
"""
from __future__ import annotations

from .ctx import Ctx, binary_op, site_pos
from .ssaload import Func, Instr, pos_key, span_of
from .terms import C0, CMP_OPS, Lengths, const, fold_atom, minus, negate, op, plus, unop


def _is_prefix(a: tuple, b: tuple, loose: bool = False) -> bool:
    if len(a) > len(b):
        return False
    for x, y in zip(a, b):
        if x == y:
            continue
        if loose and x[0] == y[0] == "index" and (x[1] is None or y[1] is None):
            continue
        return False
    return True


class Site:
    __slots__ = ("instr", "kind", "id", "bound")

    def __init__(self, instr, kind, sid, bound):
        self.instr = instr
        self.kind = kind
        self.id = sid
        self.bound = bound


class Loop:
    __slots__ = ("header", "body", "back", "span", "depth", "kind", "iv", "init", "step", "cmp", "limit", "fuel",
                 "exits", "x", "in_succ", "exit_succ", "phi", "k")


class Flow:
    def __init__(self, ctx: Ctx, fn: Func):
        self.ctx = ctx
        self.fn = fn
        self.ty = ctx.types
        self.memo: dict[str, tuple] = {}
        self.lengths = Lengths()
        self._stores = None
        self._sites = None
        self._loops = None
        self._param_copy: dict[str, int] | None = None

    # ------------------------------------------------------------------ operands and terms
    def term(self, o):
        if o is None:
            return None
        if "v" in o:
            return self.value(o["v"])
        if "param" in o:
            name, typ = self.fn.params[o["param"]]
            t = ("param", name)
            self.ctx.note_len(self.lengths, t, typ)
            return t
        if "free" in o:
            name, typ = self.fn.freevars[o["free"]]
            t = ("param", name)
            self.ctx.note_len(self.lengths, t, self.ty.pointer_elem(typ) or typ)
            return t
        if "const" in o:
            return self.ctx.const_term(o["const"])
        if "global" in o:
            t = ("global", o["global"])
            self.ctx.note_len(self.lengths, t, self.ctx.global_type(o["global"]))
            return t
        if "func" in o:
            return ("unknown", "func")
        return ("unknown", "operand")

    def value(self, name: str):
        if name in self.memo:
            return self.memo[name]
        ins = self.fn.defs.get(name)
        if ins is None:
            return ("unknown", "undefined")
        self.memo[name] = ("unknown", "cycle")
        t = self._build(ins)
        self.ctx.note_len(self.lengths, t, ins.type)
        self.memo[name] = t
        return t

    def _build(self, ins: Instr):
        o = ins.op
        ops = ins.operands
        T = self.term
        if o == "Phi":
            return ("var", ins.name, ins.get("comment") or None)
        if o == "BinOp":
            b = ins.get("binop")
            if b in CMP_OPS:
                return ("unknown", "compare")
            return op(b, T(ops[0]), T(ops[1]), self.ctx.int_info(ins.type))
        if o == "UnOp":
            u = ins.get("unop")
            if u == "*":
                return self.load(ins)
            if u == "<-":
                return ("unknown", "recv")
            if u == "!" and self.cond_atom(ops[0]) is not None and self._is_compare(ops[0]):
                return ("unknown", "compare")
            return unop(u, T(ops[0]), self.ctx.int_info(ins.type))
        if o == "Call":
            return self.call_term(ins.call)
        if o == "Extract":
            return ("result", T(ops[0]), ins.get("index"))
        if o in ("Field", "FieldAddr"):
            x = T(ops[0])
            if o == "Field" and isinstance(x, tuple) and x[:1] == ("zero",):
                return self.ctx.zero(ins.type)
            return ("field", x, ins.get("fieldname") or str(ins.get("field")))
        if o in ("Index", "IndexAddr", "Lookup"):
            return ("index", T(ops[0]), T(ops[1]))
        if o == "Slice":
            x = T(ops[0])
            self.ctx.note_len(self.lengths, x, self.ctx.operand_type(self.fn, ops[0]))
            return ("slice", x, T(ops[1]), T(ops[2]), T(ops[3]))
        if o == "Convert":
            src = self.ctx.operand_type(self.fn, ops[0])
            x = T(ops[0])
            if self.ty.numeric(src) and self.ty.numeric(ins.type):
                info = self.ctx.int_info(ins.type)
                if x[:1] == ("const",) and info:
                    from .terms import wrap
                    return const(wrap(x[1], info))
            return ("convert", ins.type, x)
        if o in ("ChangeType", "ChangeInterface"):
            return T(ops[0])
        if o in ("MultiConvert", "SliceToArrayPointer"):
            return ("convert", ins.type, T(ops[0]))
        if o == "MakeInterface":
            return ("iface", self.ctx.operand_type(self.fn, ops[0]), T(ops[0]))
        if o == "Alloc":
            return self.alloc_root(ins)
        if o == "MakeSlice":
            return ("alloc", site_pos(ins), T(ops[0]))
        if o in ("MakeMap", "MakeChan"):
            return ("alloc", site_pos(ins), None)
        if o == "MakeClosure":
            return ("unknown", "closure")
        if o == "TypeAssert":
            if ins.get("commaok"):
                return ("unknown", "assert")
            x = T(ops[0])
            if x[:1] == ("iface",) and x[1] == ins.get("asserted"):
                return x[2]
            return ("unknown", "assert")
        return ("unknown", o.lower())

    def alloc_root(self, ins: Instr):
        p = self.param_copy_of(ins.name)
        if p is not None:
            return ("param", self.fn.params[p][0])
        n = self.ty.array_len(ins.type)
        return ("alloc", site_pos(ins), const(n) if n is not None else None)

    def param_copy_of(self, alloc_name: str):
        """The parameter index when the Alloc is the function's copy of a by-value parameter (the entry block stores
        the parameter into it), else None."""
        if self._param_copy is None:
            pc = {}
            if self.fn.blocks:
                for ins in self.fn.blocks[0].instrs:
                    if ins.op == "Store":
                        a, v = ins.operands[0], ins.operands[1]
                        if a and "v" in a and v and "param" in v:
                            d = self.fn.defs.get(a["v"])
                            if d is not None and d.op == "Alloc" and a["v"] not in pc:
                                pc[a["v"]] = v["param"]
            self._param_copy = pc
        return self._param_copy.get(alloc_name)

    def call_term(self, c: dict):
        T = self.term
        args = tuple(T(a) for a in c.get("args") or [])
        m = c.get("mode")
        if m == "builtin":
            name = c["callee"]
            if name == "len" and args:
                return self.lengths.len_(args[0])
            if name == "cap" and args:
                return self.lengths.cap_(args[0])
            if name == "append" and len(args) == 2:
                return ("append", args[0], args[1])
            if name == "ssa:wrapnilchk" and args:
                return args[0]
            return ("call", "builtin:" + name, args)
        if m == "static":
            return ("call", c["callee"], args)
        callee = self.ctx.dyn_name(self.fn, c)
        if m == "invoke":
            return ("call", callee, (T(c.get("value")),) + args)
        return ("call", callee, args)

    # ------------------------------------------------------------------ memory
    def addr(self, o):
        """("local", alloc name, steps) for an address into the function's own memory, else ("term", T)."""
        if o and "v" in o:
            d = self.fn.defs.get(o["v"])
            if d is not None:
                if d.op == "Alloc":
                    return ("local", d.name, ())
                if d.op == "FieldAddr":
                    a = self.addr(d.operands[0])
                    if a[0] == "local":
                        return ("local", a[1], a[2] + (("field", d.get("fieldname")),))
                elif d.op == "IndexAddr":
                    base = d.operands[0]
                    bt = self.ctx.operand_type(self.fn, base)
                    idx = self.term(d.operands[1])
                    if self.ty.is_pointer(bt):
                        a = self.addr(base)
                        if a[0] == "local":
                            return ("local", a[1], a[2] + (("index", idx[1] if idx[:1] == ("const",) else None),))
                    else:
                        s = self.slice_of_local(base)
                        if s is not None:
                            root, steps, lo = s
                            k = plus(lo, idx)
                            return ("local", root, steps + (("index", k[1] if k[:1] == ("const",) else None),))
        return ("term", self.term(o))

    def slice_of_local(self, o):
        """(alloc, steps, lo) when the slice value o is a slice of an array in the function's own memory."""
        if not o or "v" not in o:
            return None
        d = self.fn.defs.get(o["v"])
        if d is None:
            return None
        if d.op == "ChangeType":
            return self.slice_of_local(d.operands[0])
        if d.op == "Slice":
            base = d.operands[0]
            bt = self.ctx.operand_type(self.fn, base)
            lo = self.term(d.operands[1]) if d.operands[1] else C0
            if self.ty.is_pointer(bt):
                a = self.addr(base)
                if a[0] == "local":
                    return a[1], a[2], lo
            else:
                s = self.slice_of_local(base)
                if s is not None:
                    return s[0], s[1], plus(s[2], lo)
        return None

    def stores(self):
        if self._stores is None:
            out = []
            for ins in self.fn.instrs:
                if ins.op == "Store":
                    a = self.addr(ins.operands[0])
                    if a[0] == "local":
                        out.append((ins, a[1], a[2]))
            self._stores = out
        return self._stores

    def dominates_instr(self, a: Instr, b: Instr) -> bool:
        if a.block is b.block:
            return a.idx < b.idx
        return self.fn.dominates(a.block.index, b.block.index)

    def load_local(self, root: str, steps: tuple, at: Instr):
        cands = []
        relevant = []
        for s, r, st in self.stores():
            if r != root:
                continue
            if _is_prefix(st, steps, loose=True) or _is_prefix(steps, st, loose=True):
                relevant.append(s)
                if _is_prefix(st, steps) and all(x[1] is not None for x in st if x[0] == "index") \
                        and self.dominates_instr(s, at):
                    cands.append((s, st))
        if not cands:
            return ("unknown", "memory")
        s, st = max(cands, key=lambda c: (self.fn.dom_depth(c[0].block.index), c[0].idx))
        for s2 in relevant:
            if s2 is s:
                continue
            if self.fn.instr_reaches(s, s2) and self.fn.instr_reaches(s2, at):
                return ("unknown", "memory")
        v = self.term(s.operands[1])
        if v[:1] == ("zero",) and len(steps) > len(st):
            return self.ctx.zero(at.type)  # a field or element of a composite zero value
        for step in steps[len(st):]:
            v = self.extend(v, step)
        return v

    def extend(self, v, step):
        if step[0] == "field":
            return ("field", v, step[1])
        return ("index", v, const(step[1]) if step[1] is not None else ("unknown", "index"))

    def load(self, ins: Instr):
        a = self.addr(ins.operands[0])
        if a[0] == "term":
            return a[1]
        return self.load_local(a[1], a[2], ins)

    # ------------------------------------------------------------------ conditions
    def _is_compare(self, o) -> bool:
        if not o or "v" not in o:
            return False
        d = self.fn.defs.get(o["v"])
        if d is None:
            return False
        if d.op == "BinOp" and d.get("binop") in CMP_OPS:
            return True
        if d.op == "UnOp" and d.get("unop") == "!":
            return self._is_compare(d.operands[0])
        return False

    def cond_atom(self, o):
        """The atom of a boolean value (comparison, negation, other boolean); None for a constant."""
        if o and "const" in o:
            return None
        if o and "v" in o:
            d = self.fn.defs.get(o["v"])
            if d is not None and d.op == "BinOp" and d.get("binop") in CMP_OPS:
                return (d.get("binop"), self.term(d.operands[0]), self.term(d.operands[1]))
            if d is not None and d.op == "UnOp" and d.get("unop") == "!":
                a = self.cond_atom(d.operands[0])
                return negate(a) if a is not None else None
        return ("true", self.term(o))

    def edge_atom(self, d: int, x: int):
        """The atom of the branch edge d -> x (None when d ends in no If or the condition is constant)."""
        last = self.fn.blocks[d].last
        if last is None or last.op != "If":
            return None
        succs = self.fn.blocks[d].succs
        if len(succs) != 2 or succs[0] == succs[1]:
            return None
        a = self.cond_atom(last.operands[0])
        if a is None or fold_atom(a, self.ctx.nonnil) is not None:
            return None
        return a if x == succs[0] else negate(a)

    def dom_atoms(self, b: int) -> list:
        """Atoms on the dominator-tree edges into block b (an edge counts when its target has the branch block as only
        predecessor), root first."""
        out = []
        x = b
        blocks = self.fn.blocks
        while blocks[x].idom >= 0:
            d = blocks[x].idom
            if blocks[x].preds == [d]:
                a = self.edge_atom(d, x)
                if a is not None:
                    out.append(a)
            x = d
        out.reverse()
        return out

    # ------------------------------------------------------------------ loops
    def loops(self) -> list:
        if self._loops is not None:
            return self._loops
        fn = self.fn
        heads: dict[int, set] = {}
        backs: dict[int, list] = {}
        for u, h in fn.back_edges():
            backs.setdefault(h, []).append(u)
        for h, us in backs.items():
            body = {h}
            stack = list(us)
            while stack:
                x = stack.pop()
                if x in body:
                    continue
                body.add(x)
                stack.extend(fn.blocks[x].preds)
            heads[h] = body
        loops = []
        for h in sorted(heads):
            L = Loop()
            L.header, L.body, L.back = h, frozenset(heads[h]), sorted(backs[h])
            loops.append(L)
        for L in loops:
            L.depth = 1 + sum(1 for M in loops if M is not L and L.body < M.body)
            self._analyze(L)
        self._loops = loops
        return loops

    def _span(self, L) -> tuple[str, str, bool]:
        poss = []
        for b in sorted(L.body):
            for ins in self.fn.blocks[b].instrs:
                if ins.pos and ins.op != "Phi":
                    poss.append(pos_key(ins.pos))
        best = None
        for s in self.fn.loops_syntax:
            p, e = pos_key(s["pos"]), pos_key(s["end"])
            if all(q[0] == p[0] and p[1:] <= q[1:] <= e[1:] for q in poss):
                if best is None or pos_key(best["pos"])[1:] < p[1:]:
                    best = s
        if best is None:
            return span_of(self.fn.pos), "", False
        return span_of(best["pos"]), best["kind"], bool(best.get("cond"))

    def _invariant(self, o, L, seen=None) -> bool:
        if not o or "v" not in o:
            return True
        d = self.fn.defs.get(o["v"])
        if d is None:
            return False
        if d.block.index not in L.body:
            return True
        if d.block.index != L.header or d.op == "Phi":
            return False
        seen = seen or set()
        if d.name in seen:
            return False
        seen.add(d.name)
        return all(self._invariant(x, L, seen) for x in d.operands if x)

    def _iv_of(self, o, L):
        """(phi instr, c) when o is a header phi or phi + constant."""
        if not o or "v" not in o:
            return None
        d = self.fn.defs.get(o["v"])
        if d is None:
            return None
        if d.op == "Phi" and d.block.index == L.header:
            return d, 0
        if d.op == "BinOp" and d.get("binop") in ("+", "-"):
            a, b = d.operands
            if b and "const" in b and b["const"].get("kind") == "int":
                inner = self.fn.defs.get(a.get("v", "")) if a and "v" in a else None
                if inner is not None and inner.op == "Phi" and inner.block.index == L.header:
                    c = int(b["const"]["value"])
                    return inner, (c if d.get("binop") == "+" else -c)
            if d.get("binop") == "+" and a and "const" in a and a["const"].get("kind") == "int":
                inner = self.fn.defs.get(b.get("v", "")) if b and "v" in b else None
                if inner is not None and inner.op == "Phi" and inner.block.index == L.header:
                    return inner, int(a["const"]["value"])
        return None

    def _analyze(self, L) -> None:
        fn = self.fn
        L.span, stmt, has_cond = self._span(L)
        L.kind, L.iv, L.init, L.step, L.cmp, L.limit, L.fuel = "unbounded", None, None, None, None, None, None
        L.x, L.in_succ, L.exit_succ, L.phi, L.k = None, None, None, None, 0
        hb = fn.blocks[L.header]
        last = hb.last
        if has_cond and last is not None and last.op == "If" and len(hb.succs) == 2:
            ins_ = [s for s in hb.succs if s in L.body]
            outs = [s for s in hb.succs if s not in L.body]
            if len(ins_) == 1 and len(outs) == 1:
                L.exit_succ = outs[0]
                L.in_succ = ins_[0]
                self._counted(L, last, stmt)
        L.exits = self._exits(L)

    def _counted(self, L, last: Instr, stmt: str) -> None:
        fn = self.fn
        c = last.operands[0]
        d = fn.defs.get(c.get("v", "")) if c and "v" in c else None
        if d is None or d.op != "BinOp" or d.get("binop") not in CMP_OPS:
            return
        cmp = d.get("binop")
        if L.in_succ != fn.blocks[L.header].succs[0]:
            cmp = {"==": "!=", "!=": "==", "<": ">=", ">=": "<", ">": "<=", "<=": ">"}[cmp]
        a, b = d.operands
        iva, ivb = self._iv_of(a, L), self._iv_of(b, L)
        if iva and not ivb and self._invariant(b, L):
            (phi, k), lim, xo = iva, b, a
        elif ivb and not iva and self._invariant(a, L):
            (phi, k), lim, xo = ivb, a, b
            cmp = {"==": "==", "!=": "!=", "<": ">", ">": "<", "<=": ">=", ">=": "<="}[cmp]
        else:
            return
        preds = phi.block.preds
        init_o, steps = [], []
        for e, val in zip(preds, phi.operands):
            if e in L.body:
                st = self._iv_of(val, L)
                if st is None or st[0] is not phi or st[1] == 0 or val is None or "v" not in val:
                    return
                if fn.defs[val["v"]].op == "Phi":
                    return
                steps.append(st[1])
            else:
                init_o.append(val)
        if not init_o or not steps or len(set(steps)) != 1:
            return
        inits = {self.term(v) for v in init_o}
        if len(inits) != 1:
            return
        init = plus(inits.pop(), const(k)) if k else self.term(init_o[0])
        step = steps[0]
        limit = self.term(lim)
        L.kind = "range" if stmt == "range" else "counted"
        L.iv = (phi.get("comment") or None) if L.kind == "counted" else None
        L.init, L.step, L.cmp, L.limit = init, step, cmp, limit
        L.x = self.term(xo)
        if step == 1 and cmp == "<":
            L.fuel = limit if init == C0 else op("-", limit, init)
        elif step == 1 and cmp == "<=":
            L.fuel = op("+", op("-", limit, init), const(1))
        else:
            L.fuel = None
        L.phi = phi
        L.k = k   # the header compares x = phi + k; init, limit and cmp are about x (I67: loop-body mode binds x)

    def _exits(self, L) -> list:
        fn = self.fn
        kinds = set()
        for b in sorted(L.body):
            for s in fn.blocks[b].succs:
                if s in L.body:
                    continue
                if b == L.header and s == L.exit_succ:
                    continue
                if L.exit_succ is not None and s == L.exit_succ:
                    kinds.add("break")
                    continue
                kinds.add(self._reach_kind(s, L))
        return sorted(kinds)

    def _reach_kind(self, s: int, L) -> str:
        fn = self.fn
        seen, stack, ends = set(), [s], set()
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            if x in L.body:
                ends.add("other")
                continue
            seen.add(x)
            blk = fn.blocks[x]
            last = blk.last
            if not blk.succs:
                if last is not None and last.op == "Return":
                    ends.add("return")
                elif last is not None and last.op == "Panic":
                    ends.add("panic")
                else:
                    ends.add("other")
            stack.extend(blk.succs)
        if ends == {"return"}:
            return "return"
        if ends == {"panic"}:
            return "panic"
        return "other"

    def loop_facts(self, b: int) -> list:
        """Facts of the counted / range loops (step 1, constant effective init) whose in-loop header successor
        dominates block b."""
        out = []
        for L in self.loops():
            if L.kind not in ("counted", "range") or L.step != 1 or L.init is None or L.init[:1] != ("const",):
                continue
            if L.in_succ is None or not self.fn.dominates(L.in_succ, b):
                continue
            x = L.x
            out.append(("<=", L.init, x))
            if L.limit is not None and L.limit[:1] == ("const",):
                if L.cmp == "<":
                    out.append(("<=", x, const(L.limit[1] - 1)))
                elif L.cmp == "<=":
                    out.append(("<=", x, L.limit))
        return out

    def loops_containing(self, b: int) -> list:
        """Loops whose body holds block b, outermost first."""
        return sorted((L for L in self.loops() if b in L.body), key=lambda L: (L.depth, L.span))

    # ------------------------------------------------------------------ sites
    def sites(self) -> list[Site]:
        """Bounds-checked sites of the function with their bound atoms (atoms that fold to true dropped; a site
        whose whole bound folds to true is not a site)."""
        if self._sites is not None:
            return self._sites
        out = []
        counts: dict[str, int] = {}
        for ins in self.fn.instrs:
            r = self.site_bound(ins)
            if r is None:
                continue
            kind, bound = r
            base = f"{site_pos(ins)}:{kind}"
            n = counts.get(base, 0) + 1
            counts[base] = n
            sid = base if n == 1 else f"{base}#{n}"
            out.append(Site(ins, kind, sid, bound))
        self._sites = out
        return out

    def site_bound(self, ins: Instr, V=None, LEN=None, CAP=None, TERM=None):
        """(kind, bound atoms | None) when the instruction is a bounds-checked site, else None. V maps an operand to
        a value, LEN / CAP / TERM map a value to its length, capacity and term (defaults: flow terms)."""
        V = V or self.term
        TERM = TERM or (lambda v: v)
        LEN = LEN or self.lengths.len_
        CAP = CAP or self.lengths.cap_
        ty = self.ty
        o = ins.op
        if o in ("IndexAddr", "Index", "Lookup"):
            xt = self.ctx.operand_type(self.fn, ins.operands[0])
            if o == "Lookup" and not ty.is_string(xt):
                return None
            n = ty.array_len(xt)
            length = const(n) if n is not None else LEN(V(ins.operands[0]))
            i = TERM(V(ins.operands[1]))
            return self._bound("index", [("<=", C0, i), ("<", i, length)])
        if o == "Slice":
            xt = self.ctx.operand_type(self.fn, ins.operands[0])
            x = V(ins.operands[0])
            n = ty.array_len(xt)
            if n is not None:
                length = capacity = const(n)
            elif ty.is_string(xt):
                length = capacity = LEN(x)
            else:
                length, capacity = LEN(x), CAP(x)
            lo = TERM(V(ins.operands[1])) if ins.operands[1] else C0
            hi = TERM(V(ins.operands[2])) if ins.operands[2] else length
            if ty.is_string(xt):
                return self._bound("slice", [("<=", C0, lo), ("<=", lo, hi), ("<=", hi, length)])
            mx = TERM(V(ins.operands[3])) if ins.operands[3] else capacity
            return self._bound("slice", [("<=", C0, lo), ("<=", lo, hi), ("<=", hi, mx), ("<=", mx, capacity)])
        if o == "Call":
            c = ins.call
            if c.get("mode") == "static":
                b = binary_op(c.get("callee"))
                if b and len(c.get("args") or []) >= 2:
                    return self._bound("prim", [(">=", LEN(V(c["args"][1])), const(b[2]))])
            return None
        if o == "SliceToArrayPointer":
            n = ty.array_len(ins.type)
            if n is None:
                return None
            return self._bound("convert", [(">=", LEN(V(ins.operands[0])), const(n))])
        if o == "Panic":
            return "panic", None
        if o == "TypeAssert" and not ins.get("commaok"):
            return "assert", None
        return None

    def _bound(self, kind, atoms):
        keep = []
        for a in atoms:
            f = fold_atom(a, self.ctx.nonnil)
            if f is True:
                continue
            keep.append(a)
        if not keep:
            return None
        return kind, keep

    def site_ids(self) -> dict:
        return {s.instr.uid: s for s in self.sites()}
