"""The linked machine (rules L1-L8 of the contract): the members' extracted programs run as one machine in which a call
from one member to another runs the callee's transitions as a nested frame instead of a free answer.

  Member(name, model, address, abi, code, immutables, call_names)   one member: its document's program (holon.machine
        ExtractedModel), its address in the deployment, its compiled ABI (functions by selector, getters included), its
        runtime code and immutable words, and the external-call names of its document by selector
  Bundle(members, created, depth)   the members, the accounts the deployment created and the depth limit
  Bundle.step(pre, caller, to, value, data, env, records) -> result (L8)
        pre: {member address: {slot: word}}; env: the step's block and transaction members, blob hashes and balances;
        records: the harness's calls (from, to, data, value, ok, ret), answered to non-members (L7)

L3 dispatch: the selector names an action of the callee's document, else a getter of a public storage family (its
value at the compiler's slots, ABI-encoded), else the call reverts with empty data; empty calldata runs the receive
action. L4: an external call term whose receiver is a member runs that member as a nested frame on the bundle state the
step's frames left (finished frames' writes and the in-progress writes of the frames on the stack); callok holds when
the frame succeeded and its return data decodes by the called function's outputs. L5: a frame on a member already on
the stack runs only when its action's effects are empty (else "reentry"). L6: depth. L7: a high-level call to an
account that is no member, no account the deployment created and no precompile reverts with empty data; any other
non-member call is answered from the records of that caller (holon.extracted_eval's env.calls); a low-level call into a
member is unsupported. Nothing here names a target.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import evm_abi as abi
from .. import extracted_eval as EV
from ..extracted_eval import MASK, SRef, Unsupported
from .evalx import BEval

PRECOMPILES = set(range(1, 11))


def _addr(v) -> str:
    return "0x%040x" % (EV.to_int(v) & ((1 << 160) - 1))


def _canon_args(args) -> str:
    def norm(x):
        if isinstance(x, (bytes, bytearray)):
            return "b:" + bytes(x).hex()
        if isinstance(x, SRef):
            return ["sref", x.fam, [list(p) for p in x.path]]
        if isinstance(x, dict):
            return {k: norm(v) for k, v in sorted(x.items())}
        if isinstance(x, (list, tuple)):
            return [norm(v) for v in x]
        return x
    return EV.canonical(norm(args))


@dataclass
class Member:
    name: str
    model: object
    address: str
    fns: dict                      # selector -> ABI entry (actions and getters)
    code: str = "0x"
    immutables: dict = field(default_factory=dict)
    call_names: dict = field(default_factory=dict)   # selector -> ("<I>.<f>", ABI entry)

    def action_of(self, sel: str | None) -> str | None:
        if sel is None:
            return "receive" if "receive" in self.model.actions else None
        for n, a in self.model.actions.items():
            if (a.get("selector") or "").lower() == sel:
                return n
        return None

    def effects_empty(self, action: str) -> bool:
        return not (self.model.actions[action].get("effects") or [])


class Frame:
    def __init__(self, member: Member, sel: str | None, parent: int):
        self.member, self.sel, self.parent = member, sel, parent
        self.ok = False


class StepCtx:
    def __init__(self, bundle: "Bundle", pre: dict, env: dict, records: list):
        self.b = bundle
        self.layers = [{m: {} for m in bundle.by_addr}]    # write overlays, innermost frame last
        self.pre = pre
        self.env = env
        self.records = records
        self.frames: list[Frame] = []
        self.stack: list[tuple] = []                   # (member address, action, evaluator) of the running frames

    def view(self, addr: str) -> dict:
        """A member's storage as a new frame sees it: the pre-state, the finished frames' writes, and the writes so far
        of the frames on the stack (re-entry)."""
        st = dict(self.pre.get(addr) or {})
        for layer in self.layers:
            st.update(layer.get(addr) or {})
        for a, _act, ev in self.stack:
            if a == addr and ev is not None:
                st.update(ev.overlay)
        return st


class LEval(BEval):
    """A frame's evaluator: external calls to members run nested frames; others are answered from the records."""

    def __init__(self, sc: StepCtx, member: Member, state, action, args, env):
        super().__init__(member.model, state, action, args, env)
        self.sc, self.mem = sc, member
        self.cache: dict = {}

    def event(self, ev) -> dict:
        d = super().event(ev)
        d["emitter"] = self.mem.address
        return d

    def answer(self, fn: str, receiver, args: list):
        raw = list(args)
        value = 0
        if raw and isinstance(raw[-1], tuple) and raw[-1][:1] == ("value",):
            value = raw[-1][1]
            raw = raw[:-1]
        key = (fn, _canon_args([self.value(a) for a in raw]))
        if key in self.cache:
            return self.cache[key]
        if receiver is None:
            return super().answer(fn, receiver, args)
        to = _addr(receiver)
        sig = self.m.call_signature(fn)
        callee = self.sc.b.by_addr.get(to)
        if callee is not None:
            if sig is None or not sig.get("selector"):
                raise Unsupported(f"external call {fn}: no single ABI signature to encode it")
            vals = [self.value(a) for a in raw]
            data = bytes.fromhex(sig["selector"][2:]) + EV.abi_encode(vals, sig.get("inputs") or [])
            ok, ret, out_vals = self.sc.b.frame(self.sc, self.mem, callee, value, data, self._my_frame)
            if ok and sig.get("outputs"):
                try:
                    EV.abi_decode(ret, sig["outputs"])
                    if len(ret) < 32 * len(sig["outputs"]):
                        raise ValueError("short return data")
                except Exception:   # noqa: BLE001: undecodable return data fails the call (empty revert data)
                    ok, ret = False, b""
            res = (ok, ret, sig)
            if ok and out_vals is not None:
                self.events.extend(out_vals)
            self.cache[key] = res
            return res
        if int(to, 16) not in PRECOMPILES and to not in self.sc.b.created:
            res = (False, b"", sig)
            self.cache[key] = res
            return res
        res = super().answer(fn, receiver, args)
        self.cache[key] = res
        return res

    def low_level(self, fn: str, args: list, value, status_only: bool = False):
        if args and _addr(self.as_int(args[0])) in self.sc.b.by_addr:
            raise Unsupported(f"{fn} into a member (a low-level call between members)")
        return super().low_level(fn, args, value, status_only)


class Bundle:
    def __init__(self, members: list[Member], created: set, depth: int):
        self.members = members
        self.by_addr = {m.address: m for m in members}
        self.created = set(created)
        self.depth = depth

    def env_for(self, sc: StepCtx, member: Member, caller: str, value: int, data: bytes) -> dict:
        env = dict(sc.env)
        env.update({"caller": caller, "this": member.address, "msg.value": value, "msg.data.length": len(data),
                    "code": {m.address: m.code for m in self.members}})
        calls = []
        for frm, to, cdata, _val, ok, ret in sc.records:
            if frm != member.address:
                continue
            name, fe = member.call_names.get(cdata[:10], (None, None))
            cargs = None
            if fe is not None:
                try:
                    cargs = abi.decode_args(fe["inputs"], bytes.fromhex(cdata[10:]))
                except abi.AbiError:
                    cargs = None
            calls.append({"to": to, "data": cdata, "fn": name, "args": cargs, "ok": ok, "ret": ret})
        env["calls"] = calls
        if member.immutables:
            env["immutable"] = dict(member.immutables)
        return env

    def frame(self, sc: StepCtx, caller_m: Member | None, callee: Member, value: int, data: bytes, parent: int):
        """Run one frame; (ok, return or revert data, the frame's logs to append on success)."""
        if len(sc.stack) >= self.depth:
            raise Unsupported("depth")
        sel = "0x" + data[:4].hex() if len(data) >= 4 else None
        fr = Frame(callee, sel, parent)
        sc.frames.append(fr)
        idx = len(sc.frames) - 1
        caller = caller_m.address if caller_m is not None else sc.env["__top_caller"]
        action = callee.action_of(sel) if (sel is not None or not data) else None
        if action is None:
            g = callee.fns.get(sel) if sel else None
            if g is not None and g.get("stateMutability") in ("view", "pure"):
                ret = self.getter(sc, callee, g, data)
                fr.ok = ret is not None
                return (fr.ok, ret if ret is not None else b"", [])
            return (False, b"", [])
        if any(a == callee.address for a, _x, _e in sc.stack) and not callee.effects_empty(action):
            raise Unsupported(f"reentry: {callee.name}.{action}")
        fn = callee.fns.get(sel) if sel else None
        args = {}
        if fn is not None:
            try:
                args = abi.decode_args(fn["inputs"], data[4:])
            except abi.AbiError:
                try:
                    args = abi.decode_args(fn["inputs"], data[4:], strict=False)
                except abi.AbiError:
                    args = {}
        state = sc.view(callee.address)
        sc.layers.append({m: {} for m in self.by_addr})
        e = LEval(sc, callee, state, action, args, self.env_for(sc, callee, caller, value, data))
        e._my_frame = idx
        sc.stack.append((callee.address, action, e))
        try:
            try:
                e.run(callee.model.program(action).steps)
                ret = e.return_data(action)
            except EV.Reverted as x:
                sc.layers.pop()
                return (False, bytes(x.data), [])
            except EV.CallReverted as x:
                sc.layers.pop()
                return (False, bytes(x.data), [])
            layer = sc.layers.pop()
            for k in e.touched:
                layer[callee.address][k] = e.overlay[k]
            parent_layer = sc.layers[-1]
            for a, d in layer.items():
                parent_layer.setdefault(a, {}).update(d)
            fr.ok = True
            return (True, bytes(ret), list(e.events))
        finally:
            sc.stack.pop()

    def getter(self, sc: StepCtx, member: Member, g: dict, data: bytes) -> bytes | None:
        """A public storage family's getter (L3): the ABI encoding of the value at the compiler's slots; None when it
        reverts."""
        name = g["name"]
        m = member.model
        if name not in m.families:
            return None
        try:
            args = abi.decode_args(g["inputs"], data[4:])
        except abi.AbiError:
            return None
        e = BEval(m, sc.view(member.address), next(iter(m.actions)), {}, {})
        ref = SRef(name)
        for p in g["inputs"]:
            t = m.type_of(e.locate(ref)[2])
            v = args[p["name"]]
            if t.get("encoding") == "mapping":
                ref = ref.extend("map", EV.to_int(v) if not isinstance(v, (bytes, bytearray)) else bytes(v))
            elif t.get("encoding") == "dynamic_array" or "base" in t:
                ref = ref.extend("index", EV.to_int(v))
            else:
                raise Unsupported(f"getter {name}: an argument into a {t.get('label')}")
        val = e.load(ref)
        outs = g.get("outputs") or []
        if isinstance(val, dict):
            vals = [val[o["name"]] for o in outs]
        else:
            vals = [val]
        return EV.abi_encode([x & MASK if isinstance(x, int) else x for x in vals], outs)

    def step(self, pre: dict, caller: str, to: str, value: int, data: bytes, env: dict, records: list) -> dict:
        """One top-level call (L8): {"status", "revert", "return", "writes": {member address: {slot: word}},
        "logs": [{"emitter", "topics", "data"}], "frames": [[parent, member name, selector, persisted]]} or
        {"status": "unsupported", "reason"}."""
        sc = StepCtx(self, pre, dict(env, __top_caller=caller), records)
        callee = self.by_addr.get(to)
        if callee is None:
            return {"status": "unsupported", "reason": f"the step's callee {to} is no member"}
        try:
            ok, ret, logs = self.frame(sc, None, callee, value, data, -1)
        except Unsupported as x:
            return {"status": "unsupported", "reason": str(x)}
        except (ArithmeticError, RecursionError) as x:
            return {"status": "unsupported", "reason": f"{type(x).__name__}: {x}"}
        frames = []
        for i, f in enumerate(sc.frames):
            persisted = f.ok and ok
            j = f.parent
            while persisted and j >= 0:
                persisted = sc.frames[j].ok
                j = sc.frames[j].parent
            frames.append([f.parent, f.member.name, f.sel, persisted])
        if not ok:
            return {"status": "revert", "revert": "0x" + ret.hex(), "return": None, "writes": {}, "logs": [],
                    "frames": frames}
        writes = {a: {k: v for k, v in d.items()} for a, d in sc.layers[0].items() if d}
        return {"status": "ok", "revert": None, "return": "0x" + ret.hex(), "writes": writes,
                "logs": [{"emitter": lg["emitter"], "topics": lg["topics"], "data": lg["data"]} for lg in logs],
                "frames": frames}
