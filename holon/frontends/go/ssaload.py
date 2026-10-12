"""The holon-ssadump/0.1 document as Python objects: packages, functions, blocks, instructions and types.

Nothing here interprets a program: it indexes what the Go helper printed (value definitions, referrers, dominator
tree, CFG reachability) so that the analyses in this package can read it.
"""
from __future__ import annotations

from functools import lru_cache

SSADUMP_VERSION = "holon-ssadump/0.1"


class DumpError(Exception):
    pass


class Instr:
    __slots__ = ("op", "name", "type", "pos", "operands", "x", "block", "idx", "fn", "uid")

    def __init__(self, raw: dict, block: "Block", idx: int, fn: "Func"):
        self.op = raw["op"]
        self.name = raw.get("name") or ""
        self.type = raw.get("type") or ""
        self.pos = raw.get("pos") or ""
        self.operands = raw.get("operands") or []
        self.x = raw
        self.block = block
        self.idx = idx
        self.fn = fn
        self.uid = (block.index, idx)

    def get(self, k, default=None):
        return self.x.get(k, default)

    @property
    def call(self) -> dict | None:
        return self.x.get("call")

    def __repr__(self):
        return f"<{self.fn.id} b{self.block.index}#{self.idx} {self.x.get('text', self.op)}>"


class Block:
    __slots__ = ("index", "comment", "preds", "succs", "idom", "instrs", "children")

    def __init__(self, raw: dict):
        self.index = raw["index"]
        self.comment = raw.get("comment") or ""
        self.preds = list(raw.get("preds") or [])
        self.succs = list(raw.get("succs") or [])
        self.idom = raw.get("idom", -1)
        self.instrs: list[Instr] = []
        self.children: list[int] = []

    @property
    def last(self) -> Instr | None:
        return self.instrs[-1] if self.instrs else None


class Func:
    def __init__(self, raw: dict):
        self.id = raw["id"]
        self.name = raw.get("name") or ""
        self.package = raw.get("package") or ""
        self.synthetic = raw.get("synthetic") or ""
        self.parent = raw.get("parent") or ""
        self.method = bool(raw.get("method"))
        self.pos = raw.get("pos") or ""
        self.signature = raw.get("signature") or ""
        self.params = [(p["name"], p["type"]) for p in raw.get("params") or []]
        self.freevars = [(p["name"], p["type"]) for p in raw.get("freevars") or []]
        self.results = list(raw.get("results") or [])
        self.recover = raw.get("recover", -1)
        self.loops_syntax = list(raw.get("loops") or [])
        self.blocks = [Block(b) for b in raw.get("blocks") or []]
        self.defs: dict[str, Instr] = {}
        self.instrs: list[Instr] = []
        for b, rb in zip(self.blocks, raw.get("blocks") or []):
            for i, ri in enumerate(rb.get("instrs") or []):
                ins = Instr(ri, b, i, self)
                b.instrs.append(ins)
                self.instrs.append(ins)
                if ins.name:
                    self.defs[ins.name] = ins
        for b in self.blocks:
            if b.idom >= 0:
                self.blocks[b.idom].children.append(b.index)
        self._referrers: dict[str, list[Instr]] | None = None
        self._param_refs: dict[int, list[Instr]] | None = None
        self._reach: dict[int, frozenset] | None = None
        self._depth: dict[int, int] | None = None

    # ------------------------------------------------------------------ structure
    @property
    def has_body(self) -> bool:
        return bool(self.blocks)

    def span(self) -> str:
        return span_of(self.pos)

    def referrers(self, name: str) -> list[Instr]:
        if self._referrers is None:
            refs: dict[str, list[Instr]] = {}
            prefs: dict[int, list[Instr]] = {}
            frefs: dict[int, list[Instr]] = {}
            for ins in self.instrs:
                seen = set()
                for o in ins.operands:
                    if not o:
                        continue
                    if "v" in o and o["v"] not in seen:
                        seen.add(o["v"])
                        refs.setdefault(o["v"], []).append(ins)
                    elif "param" in o and ("p", o["param"]) not in seen:
                        seen.add(("p", o["param"]))
                        prefs.setdefault(o["param"], []).append(ins)
                    elif "free" in o and ("f", o["free"]) not in seen:
                        seen.add(("f", o["free"]))
                        frefs.setdefault(o["free"], []).append(ins)
            self._referrers = refs
            self._param_refs = prefs
            self._free_refs = frefs
        return self._referrers.get(name, [])

    def operand_referrers(self, o: dict) -> list[Instr]:
        self.referrers("")
        if "v" in o:
            return self._referrers.get(o["v"], [])
        if "param" in o:
            return self._param_refs.get(o["param"], [])
        if "free" in o:
            return self._free_refs.get(o["free"], [])
        return []

    def dom_depth(self, b: int) -> int:
        if self._depth is None:
            d = {}
            for blk in self.blocks:
                n, x = 0, blk.index
                while self.blocks[x].idom >= 0:
                    x = self.blocks[x].idom
                    n += 1
                d[blk.index] = n
            self._depth = d
        return self._depth[b]

    def dominates(self, a: int, b: int) -> bool:
        """Block a dominates block b (reflexive)."""
        x = b
        while x >= 0:
            if x == a:
                return True
            x = self.blocks[x].idom
        return False

    def reach(self, b: int) -> frozenset:
        """Blocks reachable from b by one or more edges."""
        if self._reach is None:
            self._reach = {}
        if b not in self._reach:
            seen = set()
            stack = list(self.blocks[b].succs)
            while stack:
                x = stack.pop()
                if x in seen:
                    continue
                seen.add(x)
                stack.extend(self.blocks[x].succs)
            self._reach[b] = frozenset(seen)
        return self._reach[b]

    def instr_reaches(self, a: Instr, b: Instr) -> bool:
        """Instruction b can execute after instruction a (strictly later on some path)."""
        if a.block is b.block and a.idx < b.idx:
            return True
        return b.block.index in self.reach(a.block.index)

    def back_edges(self) -> list[tuple[int, int]]:
        out = []
        for blk in self.blocks:
            for s in blk.succs:
                if self.dominates(s, blk.index):
                    out.append((blk.index, s))
        return out

    def is_loop_free(self) -> bool:
        if not self.blocks:
            return True
        # any cycle at all (go/ssa CFGs are reducible, so a cycle is a back edge)
        color = {}

        def dfs(u):
            color[u] = 1
            for v in self.blocks[u].succs:
                c = color.get(v, 0)
                if c == 1:
                    return False
                if c == 0 and not dfs(v):
                    return False
            color[u] = 2
            return True
        import sys
        lim = sys.getrecursionlimit()
        sys.setrecursionlimit(max(lim, 10000))
        try:
            return dfs(0)
        finally:
            sys.setrecursionlimit(lim)


def span_of(pos: str) -> str:
    """"<path>:<line>:<col>" -> "<path>:<line>"."""
    if not pos:
        return ""
    parts = pos.rsplit(":", 2)
    if len(parts) == 3:
        return parts[0] + ":" + parts[1]
    return pos


def pos_key(pos: str) -> tuple:
    """(path, line, col) of a position string, for range comparisons."""
    parts = pos.rsplit(":", 2)
    if len(parts) != 3:
        return (pos, 0, 0)
    return (parts[0], int(parts[1]), int(parts[2]))


class Types:
    """The types table: every type keyed by its go/types string with full package paths."""

    def __init__(self, table: dict):
        self.t = table

    def entry(self, k: str) -> dict:
        return self.t.get(k) or {"kind": "other"}

    @lru_cache(maxsize=None)
    def under(self, k: str) -> str:
        seen = set()
        while k and k not in seen:
            seen.add(k)
            e = self.entry(k)
            if e.get("kind") in ("named", "alias", "typeparam") and e.get("underlying"):
                k = e["underlying"]
            else:
                break
        return k

    def kind(self, k: str) -> str:
        return self.entry(self.under(k)).get("kind", "other")

    def elem(self, k: str) -> str:
        return self.entry(self.under(k)).get("elem", "")

    def is_byte(self, k: str) -> bool:
        e = self.entry(self.under(k))
        return e.get("kind") == "basic" and e.get("integer") and e.get("unsigned") and e.get("size") == 1

    def is_byte_slice(self, k: str) -> bool:
        return self.kind(k) == "slice" and self.is_byte(self.elem(k))

    def byte_array_len(self, k: str):
        if self.kind(k) == "array" and self.is_byte(self.elem(k)):
            return self.entry(self.under(k)).get("len")
        return None

    def is_bytes_shape(self, k: str) -> bool:
        return self.is_byte_slice(k) or self.byte_array_len(k) is not None

    def array_len(self, k: str):
        """Length of an array type, or of the array a pointer type points to."""
        u = self.entry(self.under(k))
        if u.get("kind") == "pointer":
            u = self.entry(self.under(u.get("elem", "")))
        if u.get("kind") == "array":
            return u.get("len")
        return None

    def is_slice(self, k: str) -> bool:
        return self.kind(k) == "slice"

    def is_array(self, k: str) -> bool:
        return self.kind(k) == "array"

    def is_pointer(self, k: str) -> bool:
        return self.kind(k) == "pointer"

    def is_string(self, k: str) -> bool:
        e = self.entry(self.under(k))
        return e.get("kind") == "basic" and bool(e.get("string"))

    def is_integer(self, k: str) -> bool:
        e = self.entry(self.under(k))
        return e.get("kind") == "basic" and bool(e.get("integer"))

    def int_info(self, k: str):
        """(bits, unsigned) of a sized integer type, else None."""
        e = self.entry(self.under(k))
        if e.get("kind") == "basic" and e.get("integer") and e.get("size"):
            return e["size"] * 8, bool(e.get("unsigned"))
        return None

    def is_bool(self, k: str) -> bool:
        e = self.entry(self.under(k))
        return e.get("kind") == "basic" and bool(e.get("boolean"))

    def is_interface(self, k: str) -> bool:
        return self.kind(k) == "interface"

    def is_struct(self, k: str) -> bool:
        return self.kind(k) == "struct"

    def is_tuple(self, k: str) -> bool:
        return self.entry(k).get("kind") == "tuple"

    def tuple_elems(self, k: str) -> list:
        return list(self.entry(k).get("elems") or [])

    def pointer_elem(self, k: str) -> str:
        e = self.entry(self.under(k))
        return e.get("elem", "") if e.get("kind") == "pointer" else ""

    def is_error(self, k: str) -> bool:
        return k == "error"

    def numeric(self, k: str) -> bool:
        e = self.entry(self.under(k))
        return e.get("kind") == "basic" and (e.get("integer") or e.get("float"))


class Program:
    def __init__(self, doc: dict):
        if doc.get("ssadump_version") != SSADUMP_VERSION:
            raise DumpError(f"ssadump document version {doc.get('ssadump_version')!r}, want {SSADUMP_VERSION!r}")
        self.packages = {p["path"]: p for p in doc.get("packages") or []}
        self.globals = {g["id"]: g for g in doc.get("globals") or []}
        self.types = Types(doc.get("types") or {})
        self.funcs: dict[str, Func] = {}
        for raw in doc.get("functions") or []:
            f = Func(raw)
            if f.id in self.funcs:
                raise DumpError(f"two functions print as {f.id}")
            self.funcs[f.id] = f
