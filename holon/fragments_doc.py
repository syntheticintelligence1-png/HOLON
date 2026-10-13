"""What the refinement harness reads from a holon-facts/0.3 transitions document (I20-B; holon.replay_fragments,
holon.fragments_corpus). One dispatch point per document section, written against the PLANNED format of the I19
follow-up (A19), with an adapter for the current document (holon-frontend-solidity/0.2) so the harness runs end to
end today. Field names of the planned format are not final: every place that depends on one is named in SECTIONS,
CHECK_SECTIONS and the functions below, and listed in the I20 report's integration notes.

Sections read (planned format first, then what the adapter does for a document without them):
  actions[].selector, name, src            the action; selector null for receive/fallback
  actions[].params      (A19-12)           [{name, type, width, location, fields}]; adapter: the compiled ABI
  actions[].payable     (A19-12)           bool; adapter: the compiled ABI's stateMutability
  actions[].guards[i]   (I19, A19-03)      one reach per guard entry, or one per element of its "reaches":
                                           [{seq, stack, expr}] (the first reach's expr is the entry's expr)
  actions[].panics[i]   (A19-02)           {seq, src, stack, code, op, args, expr}: an implicit check (Panic code)
  actions[].checks[i]   (A19-02 c/d)       {kind: callvalue | abi | call, expr, src?, seq?}: implicit checks that are
                                           not Panics (msg.value of a non-payable action, ABI range of a narrow
                                           parameter, a failing external call)
  actions[].calls[i]    (A19-02 c)         {seq, src, stack, fn, receiver, args, value, mutability, cond, commit,
                                           check?}: an external call; its "check" ({kind: "call", expr}) is a reach
  actions[].implicit[i]                    the name the A side's first draft read for implicit checks (same entry
                                           shape as panics); kept so either name works
  actions[].loops[i]    (A19-04)           {seq, src, stack, kind, cond, carried, head, next, break, count,
                                           steps: [nested records]}: every check nested in steps is a reach (loop
                                           set), checked at every iteration
  actions[].events[i]   (A19-09)           {seq, src, stack, event, signature, topic0, args, indexed, anonymous,
                                           cond}; nested events of loops too
  actions[].order       (A19-03 minimum)   [["guard", span, k] | ["panic", i] | ["call", i], ...]
  storage[i]            (I19, A19-15)      {name, slot, offset, kind, key, value, width, fields: [{name, type,
                                           width, slot, offset}], keys, length}
  inherited_storage[i]  (A19-10)           the same entry shape plus declared_in; adapter: every compiled layout
                                           variable the document does not declare (marked "adapter")

Reach ids are "<action>#<span>#<k>": k counts the reaches of that span in the action in collection order (guards
with their reaches, then panics, then checks, then call checks, then loop-nested checks, depth first). The evaluation
order is by seq when every reach has one, else by the action's "order" list when it names every reach, else the
collection order. This is the rule of holon.machine.ExtractedModel.reaches (the A side); holon.replay_fragments
checks that both give the same ids when the evaluator's model exposes them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

CHECK_SECTIONS = ("panics", "implicit", "checks")   # sections whose entries are each one reach (after the guards)
LOOP_KEYS = ("steps", "body")                        # where a loop record holds its nested records
PANIC_NAMES = {0x01: "assert", 0x11: "arithmetic", 0x12: "division or modulo by zero", 0x21: "enum conversion",
               0x22: "storage byte array encoding", 0x31: "pop on empty array", 0x32: "array index out of bounds",
               0x41: "memory allocation", 0x51: "zero internal function"}


class DocError(ValueError):
    pass


@dataclass
class Reach:
    """One guard reach or implicit check of an action."""
    id: str
    action: str
    kind: str                # require | revert | modifier | assert | panic | callvalue | abi | call | <entry kind>
    src: str
    reason: object = None    # the guard's reason (string literal or custom error name), else None
    code: int | None = None  # the Panic code of a panic reach
    expr: object = None      # the condition that must hold for the step to pass the reach
    stack: list | None = None
    seq: int | None = None
    section: str = "guards"
    loop: str | None = None  # the span of the innermost loop record holding it
    position: int = 0        # collection order within the action

    def as_dict(self) -> dict:
        out = {"id": self.id, "action": self.action, "kind": self.kind, "src": self.src, "section": self.section,
               "expr": self.expr}
        for k in ("reason", "code", "stack", "seq", "loop"):
            v = getattr(self, k)
            if v is not None:
                out[k] = v
        return out


def _span_of(entry: dict, fallback: str) -> str:
    s = entry.get("src")
    return s if isinstance(s, str) and s else fallback


def _int_or_none(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        try:
            return int(v, 0)
        except ValueError:
            return None
    return None


class _Collector:
    def __init__(self, action: dict):
        self.a = action
        self.name = action["name"]
        self.seen: dict = {}
        self.out: list[Reach] = []

    def add(self, src: str, kind: str, section: str, expr, *, reason=None, code=None, stack=None, seq=None,
            loop=None) -> None:
        k = self.seen.get(src, 0)
        self.seen[src] = k + 1
        self.out.append(Reach(f"{self.name}#{src}#{k}", self.name, kind, src, reason, code, expr, stack,
                              _int_or_none(seq), section, loop, len(self.out)))

    # ---------------------------------------------------------------- one function per kind of entry
    def guard(self, g: dict, loop: str | None = None) -> None:
        src = _span_of(g, self.a.get("src") or self.name)
        subs = g.get("reaches")
        if isinstance(subs, list) and subs:
            for r in subs:
                r = r if isinstance(r, dict) else {}
                self.add(_span_of(r, src), g.get("kind") or "require", "guards", r.get("expr", g.get("expr")),
                         reason=g.get("reason"), stack=r.get("stack", g.get("stack")), seq=r.get("seq", g.get("seq")),
                         loop=loop)
        else:
            self.add(src, g.get("kind") or "require", "guards", g.get("expr"), reason=g.get("reason"),
                     stack=g.get("stack"), seq=g.get("seq"), loop=loop)

    def panic(self, p: dict, section: str = "panics", loop: str | None = None) -> None:
        code = _int_or_none(p.get("code", p.get("panic")))
        kind = p.get("kind") or ("panic" if code is not None else "implicit")
        self.add(_span_of(p, self.a.get("src") or self.name), kind, section, p.get("expr"),
                 reason=p.get("reason") or (PANIC_NAMES.get(code) if code is not None else None), code=code,
                 stack=p.get("stack"), seq=p.get("seq"), loop=loop)

    def check(self, c: dict, loop: str | None = None) -> None:
        if _int_or_none(c.get("code", c.get("panic"))) is not None:
            self.panic(c, "checks", loop)
            return
        self.add(_span_of(c, self.a.get("src") or self.name), c.get("kind") or "implicit", "checks", c.get("expr"),
                 reason=c.get("reason"), stack=c.get("stack"), seq=c.get("seq"), loop=loop)

    def call(self, c: dict, loop: str | None = None) -> None:
        ch = c.get("check")
        if not isinstance(ch, dict):
            return
        self.add(_span_of(ch, _span_of(c, self.a.get("src") or self.name)), ch.get("kind") or "call", "calls",
                 ch.get("expr"), reason=ch.get("reason") or c.get("fn"), stack=ch.get("stack", c.get("stack")),
                 seq=ch.get("seq", c.get("seq")), loop=loop)

    def loop(self, lp: dict) -> None:
        span = _span_of(lp, self.a.get("src") or self.name)
        for key in LOOP_KEYS:
            for x in lp.get(key) or []:
                if isinstance(x, dict):
                    self.nested(x, span)

    def nested(self, x: dict, loop: str) -> None:
        """A record nested in a loop: dispatched on its shape (the planned format gives nested records the shapes of
        the top-level sections; an explicit "record"/"type" tag wins when present)."""
        tag = x.get("record") or x.get("type")
        if tag in ("guard", "guards") or (tag is None and ("reaches" in x or x.get("kind") in
                                                            ("require", "revert", "modifier", "assert"))):
            self.guard(x, loop)
        elif tag in ("panic", "panics") or (tag is None and x.get("code") is not None and "expr" in x):
            self.panic(x, "panics", loop)
        elif tag in ("check", "checks") or (tag is None and x.get("kind") in ("callvalue", "abi", "call") and "expr" in x):
            self.check(x, loop)
        elif tag in ("call", "calls") or (tag is None and "receiver" in x):
            self.call(x, loop)
        elif tag in ("loop", "loops") or (tag is None and "carried" in x):
            self.loop(x)
        # writes, mstores, events: no reach


def collect_reaches(action: dict) -> list[Reach]:
    """Every reach of an action, in evaluation order (module docstring)."""
    c = _Collector(action)
    for g in action.get("guards") or []:
        if isinstance(g, dict):
            c.guard(g)
    for sec in CHECK_SECTIONS:
        for x in action.get(sec) or []:
            if isinstance(x, dict):
                (c.panic(x, sec) if sec != "checks" else c.check(x))
    for x in action.get("calls") or []:
        if isinstance(x, dict):
            c.call(x)
    for x in action.get("loops") or []:
        if isinstance(x, dict):
            c.loop(x)
    out = c.out
    if out and all(r.seq is not None for r in out):
        return sorted(out, key=lambda r: (r.seq, r.position))
    order = action.get("order")
    if isinstance(order, list) and order:
        rank = _order_rank(order, out)
        if rank is not None:
            return sorted(out, key=lambda r: rank[r.id])
    return out


def _order_rank(order: list, reaches: list[Reach]) -> dict | None:
    """{reach id: rank} from an "order" list that names every reach, else None."""
    by_sec: dict = {}
    for r in reaches:
        by_sec.setdefault(r.section, []).append(r)
    rank: dict = {}
    for i, o in enumerate(order):
        if not isinstance(o, list) or not o:
            return None
        if o[0] == "guard" and len(o) == 3:
            rid = f"{reaches[0].action}#{o[1]}#{o[2]}"
            if not any(r.id == rid for r in reaches):
                return None
            rank[rid] = i
        elif o[0] in ("panic", "call", "check") and len(o) == 2 and isinstance(o[1], int):
            sec = {"panic": "panics", "call": "calls", "check": "checks"}[o[0]]
            lst = by_sec.get(sec) or []
            if not 0 <= o[1] < len(lst):
                return None
            rank[lst[o[1]].id] = i
        else:
            return None
    return rank if len(rank) == len(reaches) else None


# ------------------------------------------------------------------------------------------------ the document view
@dataclass
class LayoutEntry:
    name: str
    slot: int
    offset: int
    source: str              # storage | inherited_storage | adapter (a compiled variable the document does not hold)
    width: int | None = None
    declared_in: str | None = None
    type: str | None = None  # the compiler's type id, when joined with the compiled layout
    nbytes: int | None = None
    encoding: str | None = None


@dataclass
class DocView:
    doc: dict
    actions: dict = field(default_factory=dict)          # name -> action
    by_selector: dict = field(default_factory=dict)      # "0x<8 hex>" -> action name
    reaches: dict = field(default_factory=dict)          # action name -> [Reach]
    layout: list = field(default_factory=list)           # [LayoutEntry]
    adapted: list = field(default_factory=list)          # what the adapter supplied (for the record)

    @classmethod
    def build(cls, doc: dict, compiled_layout: dict | None = None) -> "DocView":
        if not isinstance(doc, dict) or not isinstance(doc.get("actions"), list):
            raise DocError("not a transitions document (no actions list)")
        v = cls(doc)
        for a in doc["actions"]:
            v.actions[a["name"]] = a
            sel = a.get("selector")
            if isinstance(sel, str) and sel:
                v.by_selector[sel.lower()] = a["name"]
            v.reaches[a["name"]] = collect_reaches(a)
        v.layout = v._layout(compiled_layout)
        return v

    # ---------------------------------------------------------------- storage layout (clause 7: the document's slots)
    def _layout(self, compiled: dict | None) -> list[LayoutEntry]:
        types = (compiled or {}).get("types") or {}
        comp = {(s["label"], int(s["slot"]), int(s["offset"])): s for s in (compiled or {}).get("storage") or []}
        out: list[LayoutEntry] = []
        seen = set()
        planned = self.doc.get("inherited_storage")
        for source, entries in (("storage", self.doc.get("storage") or []),
                                ("inherited_storage", planned if isinstance(planned, list) else [])):
            for s in entries:
                key = (s["name"], int(s["slot"]), int(s.get("offset", 0)))
                c = comp.get(key)
                if compiled is not None and c is None:
                    raise DocError(f"{source} entry {s['name']} (slot {key[1]}, offset {key[2]}) is not a variable of the "
                                   "compiled storage layout")
                t = types.get(c["type"]) if c else None
                out.append(LayoutEntry(s["name"], key[1], key[2], source, s.get("width"), s.get("declared_in"),
                                       c["type"] if c else None, int(t["numberOfBytes"]) if t else None,
                                       t.get("encoding") if t else None))
                seen.add(key)
        if compiled is not None and not isinstance(planned, list):
            for key, c in sorted(comp.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
                if key in seen:
                    continue
                t = types.get(c["type"]) or {}
                out.append(LayoutEntry(key[0], key[1], key[2], "adapter", None, c.get("contract"), c["type"],
                                       int(t.get("numberOfBytes", "32")), t.get("encoding")))
                self.adapted.append(f"inherited_storage: {key[0]} (slot {key[1]}, offset {key[2]}) from the compiled "
                                    "storage layout")
        return sorted(out, key=lambda e: (e.slot, e.offset, e.name))

    def dump_slots(self) -> list[int]:
        """The slots read with vm.load after every step: every slot an in-place (statically sized) variable of the
        layout occupies, and the length word of every dynamic array, bytes and string."""
        out = set()
        for e in self.layout:
            if e.encoding in ("mapping",):
                continue
            if e.encoding in ("bytes", "dynamic_array"):
                out.add(e.slot)
                continue
            n = e.nbytes if e.nbytes is not None else max(1, ((e.width or 256) + 7) // 8)
            out.update(range(e.slot, e.slot + max(1, (n + e.offset + 31) // 32)))
        return sorted(out)

    # ---------------------------------------------------------------- actions
    def action_of(self, selector: str) -> str | None:
        return self.by_selector.get((selector or "").lower())

    def params(self, action: str) -> list | None:
        p = self.actions[action].get("params")
        return p if isinstance(p, list) else None

    def payable(self, action: str, abi_entry: dict | None = None) -> bool | None:
        a = self.actions[action]
        if isinstance(a.get("payable"), bool):
            return a["payable"]
        if abi_entry is not None:
            return abi_entry.get("stateMutability") == "payable"
        return None

    def all_reaches(self) -> list[Reach]:
        return [r for a in sorted(self.reaches) for r in self.reaches[a]]

    def reach(self, rid: str) -> Reach | None:
        a = rid.split("#", 1)[0]
        return next((r for r in self.reaches.get(a, []) if r.id == rid), None)

    # ---------------------------------------------------------------- events (A19-09)
    def events(self, action: str) -> list[dict]:
        out = []

        def walk(x):
            if isinstance(x, dict):
                if "topic0" in x or "signature" in x:
                    out.append(x)
                for key in LOOP_KEYS:
                    for y in x.get(key) or []:
                        walk(y)
        for e in self.actions[action].get("events") or []:
            walk(e)
        for lp in self.actions[action].get("loops") or []:
            walk(lp)
        return out

    def topics0(self) -> set[str]:
        return {str(e["topic0"]).lower() for a in self.actions for e in self.events(a) if e.get("topic0")}

    def has_events(self) -> bool:
        return any("events" in a for a in self.actions.values())

    # ---------------------------------------------------------------- widths (the boundary corpus)
    def widths(self) -> set[int]:
        """Every width the document's sorts give: storage values and struct fields (inherited storage included),
        and parameters (A19-12)."""
        out = set()

        def take(x):
            if isinstance(x, dict):
                if isinstance(x.get("width"), int) and not isinstance(x.get("width"), bool):
                    out.add(x["width"])
                for f in x.get("fields") or []:
                    take(f)
        for s in (self.doc.get("storage") or []) + list(self.doc.get("inherited_storage") or []):
            take(s)
        for a in self.actions.values():
            for p in a.get("params") or []:
                take(p)
        return {w for w in out if 0 < w <= 256}
