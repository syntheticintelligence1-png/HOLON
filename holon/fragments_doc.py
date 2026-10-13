"""What the refinement harness reads from a holon-facts/0.3 transitions document (I20-B; holon.replay_fragments,
holon.fragments_corpus): the document of the I19 follow-up (A19; holon.frontends.solidity.transitions and
spec/schemas/facts_0_3.schema.json are the format). One dispatch point per document section:

  actions[].selector, name, src            the action; selector null for receive/fallback
  actions[].params, payable                the action's interface (A19-12)
  reaches                                  every guard reach, implicit check (checks, panics) and external-call check:
                                           holon.machine.build_program, the one rule for check ids and evaluation
                                           order (the model's evaluator, holon.extracted_eval, uses the same program)
  actions[].events                         every emit (A19-09; a loop's emits are top-level records with "loop")
  storage[i], inherited_storage[i]         {name, slot, offset, kind, key, value, width, fields: [{name, type, width,
                                           slot, offset}], declared_in}: the layout the harness reads with vm.load,
                                           checked against the compiled storage layout by (name, slot, offset)

Reach ids are "<action>#<span>#<k>": span is the record's src, k counts the checks of that span in the action in walk
(seq) order, loop bodies included (holon.machine module docstring).
"""
from __future__ import annotations

from dataclasses import dataclass, field

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
    kind: str                # require | revert | modifier | panic | call | callvalue | calldatasize | abi | slice | uncaught
    src: str
    reason: object = None    # the guard's reason (string literal or custom error name), else None
    code: int | None = None  # the Panic code of a panic reach (an assert's: 1)
    expr: object = None      # the condition that must hold for the step to pass the reach
    stack: list | None = None
    seq: int | None = None
    section: str = "guards"
    loop: str | None = None  # the span of the innermost loop record holding it
    position: int = 0        # evaluation order within the action

    def as_dict(self) -> dict:
        out = {"id": self.id, "action": self.action, "kind": self.kind, "src": self.src, "section": self.section,
               "expr": self.expr}
        for k in ("reason", "code", "stack", "seq", "loop"):
            v = getattr(self, k)
            if v is not None:
                out[k] = v
        return out


def collect_reaches(action: dict) -> list[Reach]:
    """Every reach of an action, in evaluation order (module docstring)."""
    from .machine import ModelError, build_program
    try:
        checks = build_program(action).checks()
    except ModelError as e:
        raise DocError(str(e)) from e
    out = []
    for i, c in enumerate(checks):
        reason = c.reason if c.kind != "panic" else PANIC_NAMES.get(c.code)
        out.append(Reach(c.id, c.action, c.kind, c.src if isinstance(c.src, str) else c.span, reason,
                         c.code if isinstance(c.code, int) else None, c.expr, c.stack, c.seq, c.section, c.loop, i))
    return out


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
    adapted: list = field(default_factory=list)          # kept for the record: nothing is adapted

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
        if not isinstance(planned, list):
            raise DocError("the document has no inherited_storage (A19-10): re-extract it")
        for source, entries in (("storage", self.doc.get("storage") or []), ("inherited_storage", planned)):
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
        """The action's emit records (a loop's emits included: they are top-level records with "loop")."""
        return [e for e in self.actions[action].get("events") or [] if isinstance(e, dict)]

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
