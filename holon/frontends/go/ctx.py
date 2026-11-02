"""The analysis context shared by the path enumerator and the flow-insensitive builder: the program, its types, the
analyzed functions, the config primitives, generic standard-library semantics and the term helpers both use."""
from __future__ import annotations

import re

from .ssaload import Func, Instr, Program, span_of
from .terms import NIL, Lengths, const

# Standard-library semantics (generic, target independent).
BINARY_ORDERS = {"bigEndian": "be", "littleEndian": "le"}
_BINARY = re.compile(r"^\(encoding/binary\.(bigEndian|littleEndian)\)\.(Put)?Uint(16|32|64)$")
ERROR_CONSTRUCTORS = ("errors.New", "fmt.Errorf")


def binary_op(callee: str):
    """(order "be" | "le", put: bool, bytes) for an encoding/binary {Big,Little}Endian.{Put,}UintN method, else None."""
    m = _BINARY.match(callee or "")
    if not m:
        return None
    return BINARY_ORDERS[m.group(1)], bool(m.group(2)), int(m.group(3)) // 8


class Ctx:
    def __init__(self, prog: Program, config: dict):
        self.prog = prog
        self.types = prog.types
        self.prims: dict = dict(config.get("primitives") or {})
        self.config_version = config.get("config_version")   # I67: the loop_bodies section is emitted only for 0.2
        lim = config.get("limits") or {}
        self.max_paths = int(lim.get("max_paths", 512))
        self.inline_depth = int(lim.get("inline_depth", 4))
        self.flow_depth = int(lim.get("flow_depth", 3))
        self.analyzed = {fid for fid, f in prog.funcs.items() if f.has_body}
        self.nonnil_globals = self._nonnil_globals()
        self.recursive = self._recursive()
        self._loop_free: dict[str, bool] = {}
        self.debt: list[dict] = []

    # ------------------------------------------------------------------ program facts
    def loop_free(self, fid: str) -> bool:
        if fid not in self._loop_free:
            f = self.prog.funcs.get(fid)
            self._loop_free[fid] = bool(f and f.is_loop_free())
        return self._loop_free[fid]

    def _nonnil_globals(self) -> set:
        """Package error variables that a package initializer assigns from errors.New or fmt.Errorf."""
        out = set()
        for f in self.prog.funcs.values():
            if f.synthetic != "package initializer":
                continue
            for ins in f.instrs:
                if ins.op != "Store":
                    continue
                addr, val = ins.operands[0], ins.operands[1]
                if not addr or "global" not in addr or not val or "v" not in val:
                    continue
                d = f.defs.get(val["v"])
                if d is not None and d.op == "Call" and d.call and d.call.get("mode") == "static" \
                        and d.call.get("callee") in ERROR_CONSTRUCTORS \
                        and self.types.is_error(self.global_type(addr["global"])):
                    out.add(addr["global"])
        return out

    def global_type(self, gid: str) -> str:
        g = self.prog.globals.get(gid)
        return self.types.pointer_elem(g["type"]) if g else ""

    def _recursive(self) -> set:
        """Analyzed functions on a cycle of static calls (Tarjan's SCCs)."""
        graph = {}
        for fid, f in self.prog.funcs.items():
            outs = set()
            for ins in f.instrs:
                c = ins.call
                if c and c.get("mode") == "static" and c.get("callee") in self.prog.funcs:
                    outs.add(c["callee"])
            graph[fid] = sorted(outs)
        index, low, onstack, stack, out = {}, {}, set(), [], set()
        counter = [0]
        import sys
        sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))

        def strong(v):
            index[v] = low[v] = counter[0]
            counter[0] += 1
            stack.append(v)
            onstack.add(v)
            for w in graph.get(v, ()):
                if w not in index:
                    strong(w)
                    low[v] = min(low[v], low[w])
                elif w in onstack:
                    low[v] = min(low[v], index[w])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    onstack.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1 or v in graph.get(v, ()):
                    out.update(comp)
        for v in sorted(graph):
            if v not in index:
                strong(v)
        return out

    # ------------------------------------------------------------------ terms
    def nonnil(self, t) -> bool:
        """The error rule's non-nil terms: a call of errors.New / fmt.Errorf, an interface made from a concrete value,
        a package error variable assigned from one of them."""
        if not isinstance(t, tuple) or not t:
            return False
        if t[0] == "call" and t[1] in ERROR_CONSTRUCTORS:
            return True
        if t[0] == "iface":
            return True
        if t[0] == "global" and t[1] in self.nonnil_globals:
            return True
        return False

    def zero(self, typ: str):
        ty = self.types
        if ty.is_integer(typ):
            return const(0)
        if ty.is_bool(typ):
            return ("bool", False)
        if ty.is_string(typ):
            return ("str", "")
        k = ty.kind(typ)
        if k in ("pointer", "slice", "map", "chan", "signature", "interface"):
            return NIL
        if k == "basic":
            return ("unknown", "float")
        return ("zero", typ)

    def const_term(self, c: dict):
        k = c.get("kind")
        if k == "int":
            return const(int(c["value"]))
        if k == "bool":
            return ("bool", c.get("value") == "true")
        if k == "string":
            return ("str", c.get("value") or "")
        if k == "nil":
            return NIL
        if k == "zero":
            return self.zero(c.get("type") or "")
        return ("unknown", k or "const")

    def operand_type(self, fn: Func, o: dict | None) -> str:
        if not o:
            return ""
        if "v" in o:
            d = fn.defs.get(o["v"])
            return d.type if d else ""
        if "param" in o:
            return fn.params[o["param"]][1]
        if "free" in o:
            return fn.freevars[o["free"]][1]
        if "const" in o:
            return o["const"].get("type") or ""
        if "global" in o:
            g = self.prog.globals.get(o["global"])
            return g["type"] if g else ""
        return ""

    def int_info(self, typ: str):
        return self.types.int_info(typ)

    def note_len(self, lengths: Lengths, t, typ: str) -> None:
        """Remember (in a function's own registry: terms over parameters are scoped to their function) the array
        length of a term built from a value of array (or pointer-to-array) type."""
        if typ:
            n = self.types.array_len(typ)
            if n is not None:
                lengths.note(t, n)

    def dyn_name(self, fn: Func, c: dict) -> str:
        """The callee name of a dynamic call: "dynamic:<method>" (interface) or "dynamic:<value>" (function value: a
        parameter or free variable by name, a function-typed field by its selection "(T).f" as go/ssa names
        selections, a package variable by its qualified name, any other value by its SSA name)."""
        if c.get("mode") == "invoke":
            return "dynamic:" + (c.get("method") or "?")
        v = c.get("value") or {}
        if "param" in v:
            return "dynamic:" + fn.params[v["param"]][0]
        if "free" in v:
            return "dynamic:" + fn.freevars[v["free"]][0]
        if "v" in v:
            d = fn.defs.get(v["v"])
            if d is not None and d.op == "UnOp" and d.get("unop") == "*":
                a = d.operands[0] or {}
                dd = fn.defs.get(a.get("v", "")) if "v" in a else None
                if dd is not None and dd.op == "FieldAddr" and dd.get("fieldname"):
                    return f"dynamic:({self.operand_type(fn, dd.operands[0])}).{dd.get('fieldname')}"
                if "global" in a:
                    return "dynamic:" + a["global"]
            if d is not None and d.op == "Field" and d.get("fieldname"):
                return f"dynamic:({self.operand_type(fn, d.operands[0])}).{d.get('fieldname')}"
            return "dynamic:" + v["v"]
        return "dynamic:?"

    def callee_name(self, fn: Func, c: dict) -> str:
        m = c.get("mode")
        if m == "static":
            return c["callee"]
        if m == "builtin":
            return "builtin:" + c["callee"]
        return self.dyn_name(fn, c)

    def callee_kind(self, fn: Func, c: dict) -> str:
        m = c.get("mode")
        if m == "static":
            fid = c["callee"]
            if fid in self.prims:
                return "primitive"
            if fid in self.prog.funcs:
                return "analyzed"
            return "external"
        return "dynamic"

    def debt_entry(self, fid: str, kind: str, where: str, what: str) -> None:
        self.debt.append({"function": fid, "kind": kind, "where": where, "what": what})


def site_pos(ins: Instr) -> str:
    """The instruction's position, else the nearest positioned instruction before it in its block, else the
    function's position."""
    if ins.pos:
        return ins.pos
    for j in range(ins.idx - 1, -1, -1):
        p = ins.block.instrs[j].pos
        if p and ins.block.instrs[j].op != "Phi":
            return p
    for j in range(ins.idx + 1, len(ins.block.instrs)):
        p = ins.block.instrs[j].pos
        if p and ins.block.instrs[j].op != "Phi":
            return p
    return ins.fn.pos


def fn_span(fn: Func) -> str:
    return span_of(fn.pos)
