"""Path enumeration of loop-free functions: depth first from entry, true successor first; branches the reasoner
implies (refutes) follow one edge, others split; static calls of loop-free, non-recursive analyzed functions are
inlined to inline_depth; memory the function (or an inlined callee) allocates is modelled per path (arrays as cells,
structs as fields, a by-value parameter's copy reading as field terms of the parameter until stored); at each bounds
site every bound atom the reasoner does not imply splits off a panic path.

Each finished path records its condition, end, returned terms, panic site and error class, and, for every result that
is (a changetype or full-length slice of) a fixed-length byte allocation of the function's own body, the layout of
that allocation at the return.
"""
from __future__ import annotations

from .ctx import Ctx, binary_op, site_pos
from .flow import Flow
from .ssaload import Func, Instr
from .terms import (C0, NIL, UNKNOWN_CELL, Lengths, Reasoner, const, fold_atom, is_const, negate, op, plus, unop, wrap)


class PathLimit(Exception):
    pass


class OtherLoop(Exception):
    """Loop-body mode (I67): a path of one iteration met the header of another loop of the function (nested in the body
    or after its exit). That loop is not enumerated, so the iteration has no loop-free paths."""


class Ptr:
    __slots__ = ("oid", "path", "typ")

    def __init__(self, oid, path, typ):
        self.oid, self.path, self.typ = oid, path, typ


class SliceVal:
    __slots__ = ("oid", "path", "lo", "hi", "mx", "typ")

    def __init__(self, oid, path, lo, hi, mx, typ):
        self.oid, self.path, self.lo, self.hi, self.mx, self.typ = oid, path, lo, hi, mx, typ


class LVal:
    __slots__ = ("oid", "path", "typ")

    def __init__(self, oid, path, typ):
        self.oid, self.path, self.typ = oid, path, typ


class Cmp:
    __slots__ = ("atom",)

    def __init__(self, atom):
        self.atom = atom


class Tup:
    __slots__ = ("items",)

    def __init__(self, items):
        self.items = list(items)


class Clo:
    __slots__ = ("fid", "binds")

    def __init__(self, fid, binds):
        self.fid, self.binds = fid, list(binds)


class Cell:
    """A stored byte: its layout cell and, for a stored byte value, the value itself."""
    __slots__ = ("cell", "value")

    def __init__(self, cell, value=None):
        self.cell, self.value = cell, value


class Obj:
    __slots__ = ("oid", "root", "typ", "n", "own", "pos")

    def __init__(self, oid, root, typ, n, own, pos):
        self.oid, self.root, self.typ, self.n, self.own, self.pos = oid, root, typ, n, own, pos


class OState:
    __slots__ = ("whole", "stores", "havoc")

    def __init__(self, whole=None, stores=None, havoc=frozenset()):
        self.whole = whole
        self.stores = stores if stores is not None else {}
        self.havoc = havoc   # path prefixes whose contents are unknown


class Frame:
    __slots__ = ("fn", "flow", "env", "bidx", "pc", "depth", "ret", "args", "free")

    def copy(self):
        f = Frame()
        f.fn, f.flow, f.env, f.bidx, f.pc, f.depth, f.ret, f.args, f.free = (
            self.fn, self.flow, dict(self.env), self.bidx, self.pc, self.depth, self.ret, self.args, self.free)
        return f


class PState:
    __slots__ = ("frames", "cond", "mem", "_r", "looped")

    def __init__(self, frames, cond, mem):
        self.frames, self.cond, self.mem, self._r = frames, cond, mem, None
        self.looped = False      # loop-body mode (I67): this path has entered the loop header once

    def fork(self) -> "PState":
        p = PState([f.copy() for f in self.frames], list(self.cond), dict(self.mem))
        p.looped = self.looped
        return p


class Result:
    def __init__(self):
        self.paths: list[dict] = []
        self.layouts: list[list] = []     # per path: [(result index, length, cells, alloc pos)]
        self.ends: set = set()            # site ids some path ends at
        self.extra_sites: dict = {}       # site id -> (kind, bound) met only on paths
        self.unsupported: list = []


class Enumerator:
    def __init__(self, ctx: Ctx, flows, fn: Func):
        self.ctx = ctx
        self.flows = flows       # fid -> Flow
        self.fn = fn
        self.ty = ctx.types
        self.objs: dict[int, Obj] = {}
        self.lengths = Lengths()
        self.res = Result()
        self.reasoner_nonnil = self.nonnil
        self.array_bytes_calls: set = set()
        # loop-body mode (I67, holon-go-frontend/0.2): set by run_loop, which enumerates one iteration of a counted
        # loop as loop-free paths over the symbolic induction variable; a path's second entry of the header (a jump
        # back) ends it "continue", and the exit successor flows on to the function's return.
        self._loop = None

    # ------------------------------------------------------------------ public
    def run(self) -> Result:
        fn = self.fn
        top = Frame()
        top.fn, top.flow, top.env, top.bidx, top.pc, top.depth, top.ret = fn, self.flow(fn), {}, 0, 0, 0, None
        top.args = []
        for name, typ in fn.params:
            t = ("param", name)
            self.ctx.note_len(self.lengths, t, typ)
            top.args.append(t)
        top.free = [("param", n) for n, _ in fn.freevars]
        work = [PState([top], [], {})]
        while work:
            st = work.pop()
            out = self.step(st)
            nxt = []
            for kind, x in out:
                if kind == "done":
                    self.finish(*x)
                else:
                    nxt.append(x)
            work.extend(reversed(nxt))
            if len(self.res.paths) + len(work) > self.ctx.max_paths:
                raise PathLimit()
        return self.res

    def run_loop(self, L) -> Result:
        """I67 (holon-go-frontend/0.2): one iteration of a counted loop as loop-free paths over its symbolic induction
        variable. The blocks before the loop run as in run() (the function's own allocations are in scope, with their
        lengths); the header's first entry on a path binds the induction phi to ("iv", <name>), assumes init <= iv, and
        binds every other phi of the header to an opaque term of its own (a loop-carried value is unknown in a later
        iteration); the header's own test then forks the body from the exit. A path's second entry of the header ends
        it "continue"; the exit flows on to the function's return. A bound site the reasoner cannot prove safe forks a
        "panic" path, as in run(). Memory the loop writes is read as at the loop's entry: per-iteration writes are not
        tracked, so a consumer of these paths reads conditions over the induction variable and the parameters only."""
        fn = self.fn
        self._loop = {"header": L.header, "phi": L.phi.name if L.phi else None, "iv": ("iv", L.iv or "i"),
                      "init": L.init, "others": {x.header for x in self.flow(fn).loops() if x.header != L.header}}
        top = Frame()
        top.fn, top.flow, top.env, top.bidx, top.pc, top.depth, top.ret = fn, self.flow(fn), {}, 0, 0, 0, None
        top.args = []
        for name, typ in fn.params:
            t = ("param", name)
            self.ctx.note_len(self.lengths, t, typ)
            top.args.append(t)
        top.free = [("param", n) for n, _ in fn.freevars]
        work = [PState([top], [], {})]
        while work:
            st = work.pop()
            out = self.step(st)
            nxt = []
            for kind, x in out:
                if kind == "done":
                    self.finish(*x)
                else:
                    nxt.append(x)
            work.extend(reversed(nxt))
            if len(self.res.paths) + len(work) > self.ctx.max_paths:
                raise PathLimit()
        return self.res

    def flow(self, fn: Func) -> Flow:
        f = self.flows.get(fn.id)
        if f is None:
            f = Flow(self.ctx, fn)
            self.flows[fn.id] = f
        return f

    def nonnil(self, t) -> bool:
        return self.ctx.nonnil(t)

    # ------------------------------------------------------------------ path bookkeeping
    def reasoner(self, st: PState) -> Reasoner:
        if st._r is None:
            st._r = Reasoner(st.cond, self.nonnil)
        return st._r

    def assume(self, st: PState, atom) -> None:
        st.cond.append(atom)
        st._r = None

    def finish(self, st: PState, end: str, vals, site) -> None:
        fn = self.fn
        if end == "panic":
            self.res.paths.append({"cond": list(st.cond), "end": "panic", "returns": None, "site": site,
                                   "error": None})
            self.res.layouts.append([])
            self.res.ends.add(site)
            return
        if end == "continue":                 # I67 loop-body mode: the iteration completed, control goes to the header
            self.res.paths.append({"cond": list(st.cond), "end": "continue", "returns": None, "site": None,
                                   "error": None})
            self.res.layouts.append([])
            return
        rets = [self.render(st, v) for v in vals]
        err = None
        if fn.results and self.ty.is_error(fn.results[-1]):
            t = rets[-1]
            if t == NIL:
                err = "nil"
            elif self.ctx.nonnil(t) or ("!=", t, NIL) in st.cond or ("!=", NIL, t) in st.cond:
                err = "nonnil"
            else:
                err = "unknown"
        lay = []
        for i, v in enumerate(vals):
            if isinstance(v, SliceVal):
                ob = self.objs[v.oid]
                if ob.own and ob.n is not None and v.path == () and self.ty.byte_array_len(ob.typ) is not None \
                        and v.lo == C0 and v.hi == const(ob.n):
                    cells = [self.cell_at(st, v.oid, (), k) for k in range(ob.n)]
                    lay.append((i, ob.n, cells, ob.pos))
        self.res.paths.append({"cond": list(st.cond), "end": "return", "returns": rets, "site": None, "error": err})
        self.res.layouts.append(lay)

    # ------------------------------------------------------------------ values
    def val(self, fr: Frame, o, st: PState):
        if o is None:
            return None
        if "v" in o:
            return fr.env.get(o["v"], ("unknown", "undefined"))
        if "param" in o:
            return fr.args[o["param"]]
        if "free" in o:
            return fr.free[o["free"]]
        if "const" in o:
            return self.ctx.const_term(o["const"])
        if "global" in o:
            t = ("global", o["global"])
            self.ctx.note_len(self.lengths, t, self.ctx.global_type(o["global"]))
            return t
        if "func" in o:
            return Clo(o["func"], [])
        return ("unknown", "operand")

    def loc_term(self, st: PState, oid: int, path: tuple):
        ob = self.objs[oid]
        os_ = st.mem.get(oid)
        base = os_.whole if os_ is not None and os_.whole is not None else ob.root
        for step in path:
            base = self.extend(base, step)
        return base

    @staticmethod
    def extend(t, step):
        if step[0] == "field":
            if isinstance(t, tuple) and t[:1] == ("zero",):
                return ("unknown", "zero")
            return ("field", t, step[1])
        k = step[1]
        return ("index", t, const(k) if isinstance(k, int) else k)

    def render(self, st: PState, v):
        if isinstance(v, tuple):
            return v
        if isinstance(v, (Ptr, LVal)):
            return self.loc_term(st, v.oid, v.path)
        if isinstance(v, SliceVal):
            base = self.loc_term(st, v.oid, v.path)
            n = self.arr_len(v.oid, v.path)
            nn = const(n) if n is not None else None
            return ("slice", base, None if v.lo == C0 else v.lo, None if v.hi == nn else v.hi,
                    None if v.mx == nn else v.mx)
        if isinstance(v, Cmp):
            return ("unknown", "compare")
        if isinstance(v, Tup):
            return ("unknown", "tuple")
        if isinstance(v, Clo):
            return ("unknown", "closure")
        return ("unknown", "void")

    def arr_len(self, oid, path):
        if path == ():
            return self.objs[oid].n
        return None

    def av_len(self, v):
        if isinstance(v, SliceVal):
            return op("-", v.hi, v.lo)
        if isinstance(v, tuple):
            return self.lengths.len_(v)
        if isinstance(v, (Ptr, LVal)):
            n = self.ty.array_len(v.typ)
            if n is not None:
                return const(n)
        return ("len", ("unknown", "value"))

    def av_cap(self, v):
        if isinstance(v, SliceVal):
            return op("-", v.mx, v.lo)
        if isinstance(v, tuple):
            return self.lengths.cap_(v)
        if isinstance(v, (Ptr, LVal)):
            n = self.ty.array_len(v.typ)
            if n is not None:
                return const(n)
        return ("cap", ("unknown", "value"))

    # ------------------------------------------------------------------ memory
    def new_obj(self, st: PState, fr: Frame, ins: Instr, typ: str, n, root) -> int:
        oid = len(self.objs)
        self.objs[oid] = Obj(oid, root, typ, n, fr.depth == 0, site_pos(ins))
        st.mem[oid] = OState()
        return oid

    def havocked(self, os_: OState, path: tuple) -> bool:
        return any(path[:len(h)] == h for h in os_.havoc)

    def load(self, st: PState, ptr, typ: str):
        os_ = st.mem.get(ptr.oid)
        if os_ is None:
            return ("unknown", "memory")
        path = ptr.path
        if self.havocked(os_, path):
            return ("unknown", "opaque")
        if path in os_.stores:
            v = os_.stores[path]
            return self.cell_value(v) if isinstance(v, Cell) else v
        best = None
        for q in os_.stores:
            if len(q) < len(path) and path[:len(q)] == q and (best is None or len(q) > len(best)):
                best = q
        if best is not None:
            v = os_.stores[best]
            if isinstance(v, Cell):
                return ("unknown", "memory")
            if isinstance(v, tuple) and v[:1] == ("zero",):
                return self.ctx.zero(typ)
            if isinstance(v, tuple):
                for step in path[len(best):]:
                    v = self.extend(v, step)
                return v
            if isinstance(v, LVal):
                return self.load(st, LVal(v.oid, v.path + path[len(best):], typ), typ)
            return ("unknown", "memory")
        if any(len(q) > len(path) and q[:len(path)] == path for q in os_.stores):
            return LVal(ptr.oid, path, typ)
        if os_.whole is not None:
            v = os_.whole
            for step in path:
                v = self.extend(v, step)
            return v
        return self.ctx.zero(typ)

    @staticmethod
    def cell_value(c: Cell):
        if c.value is not None:
            return c.value
        if c.cell[0] == "const":
            return const(c.cell[1])
        return ("unknown", "cell")

    def store(self, st: PState, ptr: Ptr, v) -> None:
        old = st.mem.get(ptr.oid)
        if old is None:
            return
        path = ptr.path
        if any(s[0] == "index" and not isinstance(s[1], int) for s in path):
            j = next(i for i, s in enumerate(path) if s[0] == "index" and not isinstance(s[1], int))
            st.mem[ptr.oid] = OState(old.whole, dict(old.stores), old.havoc | {path[:j]})
            return
        if path == ():
            whole = self.render(st, v) if not isinstance(v, tuple) else v
            if whole[:1] == ("zero",):
                whole = None  # a composite zero value: the memory reads as fresh zero memory
            st.mem[ptr.oid] = OState(whole, {}, frozenset())
            return
        stores = {q: x for q, x in old.stores.items() if not (len(q) > len(path) and q[:len(path)] == path)}
        if path[-1][0] == "index" and self.ty.is_byte(ptr.typ):
            t = self.render(st, v) if not isinstance(v, tuple) else v
            if is_const(t):
                stores[path] = Cell(("const", t[1] & 0xFF), const(t[1] & 0xFF))
            else:
                stores[path] = Cell(("byte", t, 0), t)
        else:
            stores[path] = v
        havoc = frozenset(h for h in old.havoc if not (len(h) >= len(path) and h[:len(path)] == path))
        st.mem[ptr.oid] = OState(old.whole, stores, havoc)

    def write_cell(self, st: PState, oid: int, path: tuple, idx: int, cell) -> None:
        old = st.mem.get(oid)
        if old is None:
            return
        n = self.arr_len(oid, path)
        if n is not None and not (0 <= idx < n):
            return
        stores = dict(old.stores)
        stores[path + (("index", idx),)] = Cell(cell, const(cell[1]) if cell[0] == "const" else None)
        st.mem[oid] = OState(old.whole, stores, old.havoc)

    def havoc(self, st: PState, oid: int, path: tuple = ()) -> None:
        old = st.mem.get(oid)
        if old is None:
            return
        st.mem[oid] = OState(old.whole, dict(old.stores), old.havoc | {path})

    def havoc_value(self, st: PState, v) -> None:
        if isinstance(v, (Ptr, SliceVal, LVal)):
            self.havoc(st, v.oid, v.path)
        elif isinstance(v, Tup):
            for x in v.items:
                self.havoc_value(st, x)

    def cell_at(self, st: PState, oid: int, path: tuple, idx):
        """The layout cell of byte idx of the array at oid/path."""
        os_ = st.mem.get(oid)
        if os_ is None or not isinstance(idx, int):
            return UNKNOWN_CELL
        p = path + (("index", idx),)
        if self.havocked(os_, p):
            return UNKNOWN_CELL
        if p in os_.stores:
            v = os_.stores[p]
            if isinstance(v, Cell):
                return v.cell
            t = v if isinstance(v, tuple) else self.render(st, v)
            return ("const", t[1] & 0xFF) if is_const(t) else ("byte", t, 0)
        best = None
        for q in os_.stores:
            if len(q) < len(p) and p[:len(q)] == q and (best is None or len(q) > len(best)):
                best = q
        if best is not None:
            v = os_.stores[best]
            if isinstance(v, tuple) and v[:1] == ("zero",):
                return ("const", 0)
            if isinstance(v, tuple):
                for step in path[len(best):]:
                    v = self.extend(v, step)
                return ("byte", v, idx)
            if isinstance(v, LVal):
                return self.cell_at(st, v.oid, v.path + path[len(best):], idx)
            if isinstance(v, (Ptr, SliceVal)):
                return UNKNOWN_CELL
            return UNKNOWN_CELL
        if os_.whole is not None:
            v = os_.whole
            for step in path:
                v = self.extend(v, step)
            return ("byte", v, idx)
        return ("const", 0)

    def src_cell(self, st: PState, src, k: int):
        if isinstance(src, SliceVal):
            lo = src.lo
            if not is_const(lo):
                return UNKNOWN_CELL
            return self.cell_at(st, src.oid, src.path, lo[1] + k)
        if isinstance(src, tuple):
            tag = src[0]
            if tag == "str":
                b = src[1].encode("utf-8")
                return ("const", b[k]) if k < len(b) else UNKNOWN_CELL
            if tag == "slice":
                lo = src[2] if src[2] is not None else C0
                if not is_const(lo):
                    return UNKNOWN_CELL
                base = src[1]
                if base[:1] == ("str",):
                    b = base[1].encode("utf-8")
                    j = lo[1] + k
                    return ("const", b[j]) if j < len(b) else UNKNOWN_CELL
                return ("byte", base, lo[1] + k)
            if tag == "call" and src in self.array_bytes_calls and src[2]:
                return ("byte", src[2][0], k)
            if tag in ("unknown",):
                return UNKNOWN_CELL
            return ("byte", src, k)
        return UNKNOWN_CELL

    # ------------------------------------------------------------------ stepping
    def enter(self, fr: Frame, st: PState, b: int, pred: int):
        # I67 loop-body mode (run_loop): the header's first entry on a path binds the induction phi symbolically and
        # every other phi to an opaque term; its second entry is the jump back that ends the iteration "continue"
        if self._loop is not None and fr.depth == 0 and b in self._loop["others"]:
            raise OtherLoop(b)                       # unrolled or forked it might never end: no loop body here
        if self._loop is not None and b == self._loop["header"] and fr.depth == 0:
            if st.looped:
                return "continue"
            st.looped = True
            blk = fr.fn.blocks[b]
            fr.bidx, fr.pc = b, 0
            while fr.pc < len(blk.instrs) and blk.instrs[fr.pc].op == "Phi":
                ins = blk.instrs[fr.pc]
                fr.env[ins.name] = self._loop["iv"] if ins.name == self._loop["phi"] else ("unknown", f"loop:{ins.name}")
                fr.pc += 1
            if self._loop["init"] is not None:                 # the induction variable is at least its initial value
                self.assume(st, ("<=", self._loop["init"], self._loop["iv"]))
            return None
        blk = fr.fn.blocks[b]
        fr.bidx, fr.pc = b, 0
        phis = []
        while fr.pc < len(blk.instrs) and blk.instrs[fr.pc].op == "Phi":
            ins = blk.instrs[fr.pc]
            e = blk.preds.index(pred) if pred in blk.preds else -1
            phis.append((ins.name, self.val(fr, ins.operands[e], st) if e >= 0 else ("unknown", "phi")))
            fr.pc += 1
        for name, v in phis:
            fr.env[name] = v
        return None

    def site_of(self, fr: Frame, ins: Instr, kind: str, bound):
        s = fr.flow.site_ids().get(ins.uid)
        if s is not None:
            return s.id
        sid = f"{site_pos(ins)}:{kind}"
        if fr.depth == 0:
            self.res.extra_sites.setdefault(sid, (kind, bound))
        return sid

    def step(self, st: PState) -> list:
        out = []
        while True:
            fr = st.frames[-1]
            blk = fr.fn.blocks[fr.bidx]
            if fr.pc >= len(blk.instrs):
                out.append(("done", (st, "panic", None, f"{fr.fn.pos}:panic")))
                return out
            ins = blk.instrs[fr.pc]
            # bounds sites
            sb = fr.flow.site_bound(ins, V=lambda o: self.val(fr, o, st), LEN=self.av_len, CAP=self.av_cap,
                                    TERM=lambda v: self.render(st, v))
            if sb is not None and sb[1] is not None:
                kind, bound = sb
                sid = self.site_of(fr, ins, kind, bound)
                dead = False
                for a in bound:
                    s = self.reasoner(st).status(a)
                    if s is True:
                        continue
                    if s is False:
                        out.append(("done", (st, "panic", None, sid)))
                        dead = True
                        break
                    p = st.fork()
                    self.assume(p, negate(a))
                    out.append(("done", (p, "panic", None, sid)))
                    self.assume(st, a)
                if dead:
                    return out
            r = self.exec(fr, ins, st)
            if r is None:
                fr.pc += 1
                continue
            kind = r[0]
            if kind == "jump":
                if self.enter(fr, st, r[1], fr.bidx) == "continue":
                    out.append(("done", (st, "continue", None, None)))
                    return out
                continue
            if kind == "branch":
                atom, tb, fb = r[1], r[2], r[3]
                s = self.reasoner(st).status(atom)
                if s is True:
                    if self.enter(fr, st, tb, fr.bidx) == "continue":
                        out.append(("done", (st, "continue", None, None)))
                        return out
                    continue
                if s is False:
                    if self.enter(fr, st, fb, fr.bidx) == "continue":
                        out.append(("done", (st, "continue", None, None)))
                        return out
                    continue
                p = st.fork()
                cur = fr.bidx
                self.assume(st, atom)
                if self.enter(st.frames[-1], st, tb, cur) == "continue":
                    out.append(("done", (st, "continue", None, None)))
                else:
                    out.append(("work", st))
                self.assume(p, negate(atom))
                if self.enter(p.frames[-1], p, fb, cur) == "continue":
                    out.append(("done", (p, "continue", None, None)))
                else:
                    out.append(("work", p))
                return out
            if kind == "return":
                vals = r[1]
                if len(st.frames) == 1:
                    out.append(("done", (st, "return", vals, None)))
                    return out
                st.frames.pop()
                caller = st.frames[-1]
                ret = fr.ret
                if ret.name:
                    if len(vals) == 1:
                        caller.env[ret.name] = vals[0]
                    else:
                        caller.env[ret.name] = Tup(vals)
                caller.pc += 1
                continue
            if kind == "panic":
                out.append(("done", (st, "panic", None, r[1])))
                return out
            if kind == "call":
                callee, args, free = r[1], r[2], r[3]
                nf = Frame()
                nf.fn, nf.flow, nf.env, nf.depth, nf.ret = callee, self.flow(callee), {}, fr.depth + 1, ins
                nf.args, nf.free = args, free
                st.frames.append(nf)
                self.enter(nf, st, 0, -1)
                continue
            raise AssertionError(kind)

    # ------------------------------------------------------------------ instructions
    def unsupported(self, fr: Frame, ins: Instr, what: str) -> None:
        if fr.depth == 0:
            self.res.unsupported.append((site_pos(ins), what))

    def exec(self, fr: Frame, ins: Instr, st: PState):
        o = ins.op
        ops = ins.operands
        V = lambda x: self.val(fr, x, st)  # noqa: E731
        R = lambda v: self.render(st, v)  # noqa: E731
        env = fr.env
        ty = self.ty
        if o == "Alloc":
            typ = ty.pointer_elem(ins.type)
            n = ty.array_len(ins.type)
            root = ("alloc", site_pos(ins), const(n) if n is not None else None)
            oid = self.new_obj(st, fr, ins, typ, n, root)
            env[ins.name] = Ptr(oid, (), typ)
            return None
        if o == "Store":
            a, v = V(ops[0]), V(ops[1])
            if isinstance(a, Ptr):
                self.store(st, a, v)
            elif isinstance(v, (Ptr, SliceVal, LVal)):
                pass  # a local address escapes into other memory; its contents stay modelled
            return None
        if o == "UnOp":
            u = ins.get("unop")
            x = V(ops[0])
            if u == "*":
                if isinstance(x, Ptr):
                    env[ins.name] = self.load(st, x, ins.type)
                elif isinstance(x, tuple):
                    self.ctx.note_len(self.lengths, x, ins.type)
                    env[ins.name] = x
                else:
                    env[ins.name] = ("unknown", "load")
            elif u == "!":
                if isinstance(x, Cmp):
                    env[ins.name] = Cmp(negate(x.atom))
                else:
                    env[ins.name] = unop("!", R(x))
            elif u == "<-":
                env[ins.name] = ("unknown", "recv")
            else:
                env[ins.name] = unop(u, R(x), self.ctx.int_info(ins.type))
            return None
        if o == "BinOp":
            b = ins.get("binop")
            xa, xb = V(ops[0]), V(ops[1])
            if b in ("==", "!=", "<", "<=", ">", ">="):
                for p, q in ((xa, xb), (xb, xa)):
                    if isinstance(p, (Ptr, SliceVal)) and q == NIL and b in ("==", "!="):
                        env[ins.name] = ("bool", b == "!=")
                        return None
                if isinstance(xa, Cmp) or isinstance(xb, Cmp):
                    env[ins.name] = ("unknown", "compare")
                    return None
                atom = (b, R(xa), R(xb))
                f = fold_atom(atom, self.nonnil)
                env[ins.name] = ("bool", f) if f is not None else Cmp(atom)
            else:
                env[ins.name] = op(b, R(xa), R(xb), self.ctx.int_info(ins.type))
            return None
        if o == "If":
            c = V(ops[0])
            blk = fr.fn.blocks[fr.bidx]
            tb, fb = blk.succs[0], blk.succs[1]
            if isinstance(c, tuple) and c[:1] == ("bool",):
                return ("jump", tb if c[1] else fb)
            atom = c.atom if isinstance(c, Cmp) else ("true", R(c))
            return ("branch", atom, tb, fb)
        if o == "Jump":
            return ("jump", fr.fn.blocks[fr.bidx].succs[0])
        if o == "Return":
            return ("return", [V(x) for x in ops])
        if o == "Panic":
            s = fr.flow.site_ids().get(ins.uid)
            return ("panic", s.id if s else f"{site_pos(ins)}:panic")
        if o == "Phi":
            return None
        if o == "Extract":
            t = V(ops[0])
            i = ins.get("index")
            if isinstance(t, Tup):
                env[ins.name] = t.items[i] if i < len(t.items) else ("unknown", "extract")
            else:
                env[ins.name] = ("result", R(t), i)
            return None
        if o == "FieldAddr":
            x = V(ops[0])
            f = ins.get("fieldname")
            if isinstance(x, (Ptr, LVal)):
                env[ins.name] = Ptr(x.oid, x.path + (("field", f),), ty.pointer_elem(ins.type))
            else:
                t = ("field", R(x), f)
                self.ctx.note_len(self.lengths, t, ins.type)
                env[ins.name] = t
            return None
        if o == "Field":
            x = V(ops[0])
            f = ins.get("fieldname")
            if isinstance(x, LVal):
                env[ins.name] = self.load(st, Ptr(x.oid, x.path + (("field", f),), ins.type), ins.type)
            else:
                t = R(x)
                if t[:1] == ("zero",):
                    env[ins.name] = self.ctx.zero(ins.type)
                else:
                    t = ("field", t, f)
                    self.ctx.note_len(self.lengths, t, ins.type)
                    env[ins.name] = t
            return None
        if o == "IndexAddr":
            x = V(ops[0])
            it = R(V(ops[1]))
            if isinstance(x, SliceVal):
                k = plus(x.lo, it)
                env[ins.name] = Ptr(x.oid, x.path + (("index", k[1] if is_const(k) else k),),
                                    ty.pointer_elem(ins.type))
            elif isinstance(x, (Ptr, LVal)):
                env[ins.name] = Ptr(x.oid, x.path + (("index", it[1] if is_const(it) else it),),
                                    ty.pointer_elem(ins.type))
            else:
                t = ("index", R(x), it)
                self.ctx.note_len(self.lengths, t, ins.type)
                env[ins.name] = t
            return None
        if o == "Index":
            x = V(ops[0])
            it = R(V(ops[1]))
            if isinstance(x, LVal):
                env[ins.name] = self.load(st, Ptr(x.oid, x.path + (("index", it[1] if is_const(it) else it),),
                                                  ins.type), ins.type)
            else:
                env[ins.name] = ("index", R(x), it)
            return None
        if o == "Lookup":
            if ins.get("commaok"):
                env[ins.name] = ("unknown", "lookup")
            else:
                env[ins.name] = ("index", R(V(ops[0])), R(V(ops[1])))
            return None
        if o == "Slice":
            x = V(ops[0])
            lo = R(V(ops[1])) if ops[1] else None
            hi = R(V(ops[2])) if ops[2] else None
            mx = R(V(ops[3])) if ops[3] else None
            if isinstance(x, Ptr) and ty.array_len(x.typ) is not None:
                n = const(ty.array_len(x.typ))
                env[ins.name] = SliceVal(x.oid, x.path, lo or C0, hi or n, mx or n, ins.type)
            elif isinstance(x, SliceVal):
                env[ins.name] = SliceVal(x.oid, x.path, plus(x.lo, lo) if lo else x.lo,
                                   plus(x.lo, hi) if hi else x.hi, plus(x.lo, mx) if mx else x.mx, ins.type)
            else:
                xt = R(x)
                self.ctx.note_len(self.lengths, xt, self.ctx.operand_type(fr.fn, ops[0]))
                env[ins.name] = ("slice", xt, lo, hi, mx)
            return None
        if o in ("ChangeType", "ChangeInterface"):
            env[ins.name] = V(ops[0])
            return None
        if o == "Convert":
            src = self.ctx.operand_type(fr.fn, ops[0])
            x = R(V(ops[0]))
            if ty.numeric(src) and ty.numeric(ins.type):
                info = self.ctx.int_info(ins.type)
                if is_const(x) and info:
                    env[ins.name] = const(wrap(x[1], info))
                    return None
            env[ins.name] = ("convert", ins.type, x)
            return None
        if o in ("MultiConvert", "SliceToArrayPointer"):
            env[ins.name] = ("convert", ins.type, R(V(ops[0])))
            return None
        if o == "MakeInterface":
            env[ins.name] = ("iface", self.ctx.operand_type(fr.fn, ops[0]), R(V(ops[0])))
            return None
        if o == "TypeAssert":
            x = R(V(ops[0]))
            if ins.get("commaok"):
                env[ins.name] = ("unknown", "assert")
            elif x[:1] == ("iface",) and x[1] == ins.get("asserted"):
                env[ins.name] = x[2]
            else:
                env[ins.name] = ("unknown", "assert")
            return None
        if o == "MakeSlice":
            ln, cp = R(V(ops[0])), R(V(ops[1]))
            n = cp[1] if is_const(cp) else None
            root = ("alloc", site_pos(ins), ln)
            oid = self.new_obj(st, fr, ins, ins.type, n, root)
            env[ins.name] = SliceVal(oid, (), C0, ln, cp, ins.type)
            return None
        if o in ("MakeMap", "MakeChan"):
            env[ins.name] = ("alloc", site_pos(ins), None)
            return None
        if o == "MakeClosure":
            env[ins.name] = Clo(ins.get("fn"), [V(x) for x in ops[1:]])
            return None
        if o in ("Go", "Defer"):
            if o == "Defer" and self.may_recover(fr.fn, ins.call or {}):
                self.unsupported(fr, ins, "deferred call that may recover from a panic (panic paths would return)")
            for a in (ins.call or {}).get("args") or []:
                self.havoc_value(st, V(a))
            return None
        if o in ("RunDefers", "DebugRef", "MapUpdate", "Send"):
            return None
        if o == "Call":
            return self.call(fr, ins, st)
        if o in ("Select", "Next", "Range"):
            self.unsupported(fr, ins, f"go/ssa {o} is not modelled by path enumeration")
            env[ins.name] = ("unknown", o.lower())
            return None
        self.unsupported(fr, ins, f"go/ssa {o} is not modelled by path enumeration")
        if ins.name:
            env[ins.name] = ("unknown", o.lower())
        return None

    def may_recover(self, fn: Func, c: dict) -> bool:
        """A deferred call can turn a panic into a return when the deferred function calls the recover builtin:
        an analyzed callee whose body does, or a dynamic callee (unknown body)."""
        if c.get("mode") == "static":
            callee = self.ctx.prog.funcs.get(c.get("callee"))
            if callee is None:
                return False
            return any(i.op == "Call" and (i.call or {}).get("mode") == "builtin" and i.call.get("callee") == "recover"
                       for i in callee.instrs)
        return c.get("mode") in ("invoke", "dynamic")

    def inlinable(self, fr: Frame, fid: str) -> bool:
        ctx = self.ctx
        return (fid in ctx.analyzed and fid not in ctx.recursive and ctx.loop_free(fid)
                and fr.depth < ctx.inline_depth)

    def call(self, fr: Frame, ins: Instr, st: PState):
        c = ins.call
        mode = c.get("mode")
        V = lambda x: self.val(fr, x, st)  # noqa: E731
        R = lambda v: self.render(st, v)  # noqa: E731
        args = [V(a) for a in c.get("args") or []]
        env = fr.env
        name = ins.name
        if mode == "builtin":
            b = c["callee"]
            if b == "len":
                env[name] = self.av_len(args[0])
            elif b == "cap":
                env[name] = self.av_cap(args[0])
            elif b == "append":
                x = args[0]
                if isinstance(x, SliceVal) and x.mx != x.hi:
                    self.havoc(st, x.oid, x.path)
                env[name] = ("append", R(x), R(args[1]))
            elif b == "copy":
                env[name] = self.copy(st, args[0], args[1])
            elif b == "ssa:wrapnilchk":
                env[name] = args[0]
            elif b in ("min", "max") and all(isinstance(a, tuple) and is_const(a) for a in args):
                vs = [a[1] for a in args]
                env[name] = const(min(vs) if b == "min" else max(vs))
            else:
                env[name] = ("call", "builtin:" + b, tuple(R(a) for a in args))
            return None
        if mode == "static":
            fid = c["callee"]
            bo = binary_op(fid)
            if bo is not None:
                order, put, nb = bo
                if put:
                    if len(args) >= 3:
                        self.put(st, args[1], R(args[2]), order, nb)
                    if name:
                        env[name] = ("unknown", "void")
                else:
                    env[name] = ("call", fid, tuple(R(a) for a in args))
                return None
            prim = self.ctx.prims.get(fid)
            if prim is not None:
                t = ("call", fid, tuple(R(a) for a in args))
                if prim.get("kind") in ("to_array", "array_bytes", "hex_to_array") and prim.get("width"):
                    self.lengths.note(t, prim["width"])
                if prim.get("kind") == "array_bytes":
                    self.array_bytes_calls.add(t)
                if name:
                    env[name] = t
                return None
            if self.inlinable(fr, fid):
                callee = self.ctx.prog.funcs[fid]
                free = []
                v = c.get("value") or {}
                if "v" in v:
                    cl = fr.env.get(v["v"])
                    if isinstance(cl, Clo):
                        free = cl.binds
                if len(free) != len(callee.freevars):
                    free = [("param", n) for n, _ in callee.freevars]
                return ("call", callee, args, free)
            for a in args:
                self.havoc_value(st, a)
            t = ("call", fid, tuple(R(a) for a in args))
            self.ctx.note_len(self.lengths, t, ins.type)
            if name:
                env[name] = t
            return None
        recv = V(c.get("value"))
        self.havoc_value(st, recv)
        for a in args:
            self.havoc_value(st, a)
        callee = self.ctx.dyn_name(fr.fn, c)
        if mode == "invoke":
            t = ("call", callee, (R(recv),) + tuple(R(a) for a in args))
        else:
            t = ("call", callee, tuple(R(a) for a in args))
        if name:
            env[name] = t
        return None

    def put(self, st: PState, dst, v, order: str, nb: int) -> None:
        if not isinstance(dst, SliceVal):
            return
        if not is_const(dst.lo):
            self.havoc(st, dst.oid, dst.path)
            return
        base = dst.lo[1]
        for k in range(nb):
            if is_const(v):
                sh = 8 * (nb - 1 - k) if order == "be" else 8 * k
                cell = ("const", (v[1] >> sh) & 0xFF)
            else:
                cell = ("byte" if order == "be" else "byte_le", v, k)
            self.write_cell(st, dst.oid, dst.path, base + k, cell)

    def copy(self, st: PState, dst, src):
        nd, ns = self.av_len(dst), self.av_len(src)
        n = min(nd[1], ns[1]) if is_const(nd) and is_const(ns) else None
        if isinstance(dst, SliceVal):
            if not is_const(dst.lo):
                self.havoc(st, dst.oid, dst.path)
            elif n is not None:
                cells = [self.src_cell(st, src, k) for k in range(n)]
                for k, cell in enumerate(cells):
                    self.write_cell(st, dst.oid, dst.path, dst.lo[1] + k, cell)
            else:
                end = dst.hi[1] if is_const(dst.hi) else self.arr_len(dst.oid, dst.path)
                if end is None:
                    self.havoc(st, dst.oid, dst.path)
                else:
                    for k in range(dst.lo[1], end):
                        self.write_cell(st, dst.oid, dst.path, k, UNKNOWN_CELL)
        return const(n) if n is not None else ("call", "builtin:copy", (self.render(st, dst), self.render(st, src)))
