"""The evaluator of record (holon.extracted_eval), extended additively for the constructs a bundle member adds (rule M1
of the contract): storage dynamic arrays written by push and pop, struct values updated member by member (the walk's
["update", base, ["member", base, name], v]), and an action's return data. It lives here, outside every generator
closure, so that no committed record moves; extracted_eval itself is unchanged and a document without these constructs
evaluates exactly as before.

  push   a write whose value is ["push", array, v]: the array's length word at its slot is n (as the step left it), the
         element n is written at keccak256(slot) + n * the element's slots (sub-word elements packed per slot, as the
         compiler packs them), and the length becomes n + 1
  pop    a write whose value is ["pop", array]: element n - 1 is zeroed and the length becomes n - 1 (the document
         places the Panic 0x31 check of an empty array before it; an empty array here is unsupported)
  update ["update", base, target, v]: the struct value base with the member target names set to v
  return the action's "returns" term, evaluated after the program ran, ABI-encoded by the compiler's output types
"""
from __future__ import annotations

from .. import extracted_eval as EV
from ..extracted_eval import MASK, SRef, Unsupported, keccak


class BEval(EV.Eval):
    def t_update(self, t):
        base = self.value(self.ev(t[1]))
        tgt = t[2]
        if not (isinstance(tgt, list) and len(tgt) == 3 and tgt[0] == "member" and isinstance(tgt[2], str)):
            raise Unsupported(f"an update of a {str(tgt)[:60]}")
        if isinstance(base, int) and base == 0:
            base = {}
        if not isinstance(base, dict):
            raise Unsupported(f"an update of a {type(base).__name__}")
        out = dict(base)
        out[tgt[2]] = self.value(self.ev(t[3]))
        return out

    def t_push(self, t):
        raise Unsupported("a push outside a storage write")

    def t_pop(self, t):
        raise Unsupported("a pop outside a storage write")

    def _elem(self, slot: int, i: int, tid: str) -> tuple[int, int]:
        size = int(self.m.type_of(tid)["numberOfBytes"])
        base = keccak(slot.to_bytes(32, "big"))
        if size <= 16:
            per = 32 // size
            return (base + i // per) & MASK, (i % per) * size
        return (base + i * ((size + 31) // 32)) & MASK, 0

    def write(self, w) -> None:
        v = w.value
        if not (isinstance(v, list) and v and v[0] in ("push", "pop")):
            return super().write(w)
        path = tuple(self.path(w.path))
        slot, _off, tid = self.locate(SRef(w.family, path))
        t = self.m.type_of(tid)
        if t.get("encoding") != "dynamic_array" or "base" not in t:
            raise Unsupported(f"a {v[0]} on a {t.get('label')}")
        arr = self.ev(v[1])
        if not isinstance(arr, SRef) or arr.overlays or self.locate(arr)[0] != slot:
            raise Unsupported(f"a {v[0]} whose array term is not the written family's location")
        n = self.overlay.get(slot, self.state.get(slot, 0))
        if v[0] == "push":
            val = self.value(self.ev(v[2]))
            es, eo = self._elem(slot, n, t["base"])
            self._write_at(es, eo, t["base"], val)
            self._set_word(slot, n + 1)
        else:
            if n == 0:
                raise Unsupported("a pop of an empty array (its Panic 0x31 check is the document's)")
            es, eo = self._elem(slot, n - 1, t["base"])
            self._write_at(es, eo, t["base"], 0)
            self._set_word(slot, n - 1)

    def _set_word(self, slot: int, v: int) -> None:
        self.overlay[slot] = v & MASK
        if slot not in self.touched:
            self.touched.append(slot)

    def return_data(self, action: str) -> bytes:
        """The action's return data: its returns term, ABI-encoded by the compiler's output types (empty when it
        returns nothing)."""
        a = self.m.actions[action]
        outs = self.outputs(action)
        r = a.get("returns")
        if r is None:
            if outs:
                raise Unsupported(f"{action}: the document records no return value for {len(outs)} outputs")
            return b""
        if outs is None:
            raise Unsupported(f"{action}: no compiled output types")
        val = self.value(self.ev(r))
        vals = list(val) if len(outs) > 1 and isinstance(val, (list, tuple)) else [val]
        if len(vals) != len(outs):
            raise Unsupported(f"{action}: {len(vals)} return values for {len(outs)} outputs")
        return EV.abi_encode([self.value(x) for x in vals], outs)

    def outputs(self, action: str):
        a = self.m.actions[action]
        fns = self.m.info.get("functions") or {}
        e = fns.get(a.get("selector")) if a.get("selector") else fns.get(a["name"])
        return None if e is None else list(e.get("outputs") or [])


def step(model, state, action: str, args: dict, env: dict, cls=BEval) -> dict:
    """holon.extracted_eval.step with the extension, and "return" (the return data, 0x-hex) on ok."""
    if action not in model.actions:
        return EV._result("unsupported", reason=f"no action {action} in the document")
    e = cls(model, state, action, args or {}, env or {})
    try:
        e.run(model.program(action).steps)
        ret = e.return_data(action)
    except EV.Reverted as x:
        out = EV._result("revert", EV.hexb(x.data), guard=x.check.id)
        if x.prefix:
            out["revert_prefix"] = True
        return out
    except EV.CallReverted as x:
        return EV._result("revert", EV.hexb(x.data), guard=None, reason=f"external call {x.fn} reverted (bubbled)")
    except Unsupported as x:
        return EV._result("unsupported", reason=f"{action}: {x}")
    except (ArithmeticError, RecursionError) as x:
        return EV._result("unsupported", reason=f"{action}: {type(x).__name__}: {x}")
    wd = {EV.h32(k): EV.h32(e.overlay[k]) for k in sorted(e.touched)}
    return EV._result("ok", None, wd, e.events, None, **{"return": EV.hexb(ret)})
