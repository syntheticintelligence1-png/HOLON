"""Rules L1-L8: the linked machine, over holon.extracted_eval's programs of the members' documents.

State (L1): every member's raw storage and every member's ETH balance. A call to a member (L3) dispatches by selector:
an action, empty calldata the receive action, a selector of a public storage family's getter its ABI encoding, any
other selector a revert with empty data (decided before L5). A member's external call term whose receiver is a member
(L4) runs that member as a nested frame, with the calling member as caller and the call's value, on the bundle state
as the step's earlier frames left it; its result answers the term (holon.extracted_eval's call hook). Re-entry into a
member already on the frame stack runs only an action whose document writes no storage (L5); deeper than the
sidecar's link.depth is unsupported (L6). A call to a non-member is answered from the harness's record of it (L7). The
result (L8): status, revert data, return data, every member's writes, the logs, the balances, the outgoing calls and
the frames ([parent, caller, member, selector, value, ok], ok when the frame returned and every enclosing frame did).
"""
from __future__ import annotations

from . import Ctx

UNSUPPORTED = "unsupported"


class Unsup(Exception):
    pass


class _Table(dict):
    """An env table answering every address: the given ones, else the default."""

    def __init__(self, data: dict, default):
        super().__init__(data)
        self.default = default

    def __contains__(self, k) -> bool:
        return True

    def __getitem__(self, k):
        return dict.get(self, k, self.default)


def _addr(v) -> str:
    return "0x%040x" % (int(v, 16) if isinstance(v, str) else int(v))


class Bundle:
    def __init__(self, ctx: Ctx, dep: dict):
        from . import members as M
        from .corpus import abis
        from ..extracted_eval import keccak
        self.ctx = ctx
        self.dep = dep
        self.names = [m["name"] for m in ctx.members()]
        self.addr = {n: dep["members"][n]["address"] for n in self.names}
        self.by_addr = {a: n for n, a in self.addr.items()}
        self.models = {n: M.model(ctx, n) for n in self.names}
        self.abi = abis(ctx)
        self.depth = int(ctx.side["link"]["depth"])
        self.code = {a: bytes(n) for a, n in dep["code"].items()}
        self.keccak = keccak
        self.by_sel, self.getters, self.writes = {}, {}, {}
        for n in self.names:
            doc = self.models[n].doc
            self.by_sel[n] = {(a.get("selector") or a["name"]): a["name"] for a in doc["actions"]}
            self.writes[n] = {a["name"]: bool(a.get("writes") or a.get("effects")) for a in doc["actions"]}
            fams = {s["name"] for s in doc["storage"]} | {s["name"] for s in doc.get("inherited_storage") or []}
            self.getters[n] = {k: e for k, e in self.abi[n].items()
                               if k.startswith("0x") and k not in self.by_sel[n] and e.get("name") in fams}

    # ------------------------------------------------------------------------------------------- one step
    def run(self, pre: dict, balances: dict, step) -> dict:
        """The step's result from the members' storage (name -> {slot: word}) and balances (address -> wei)."""
        self.st = {n: dict(pre[n]) for n in self.names}
        self.bal = dict(balances)
        self.frames, self.outgoing = [], []
        self.answers: dict = {}             # frame index -> the answers its call terms received (M4's env calls)
        self.step = step
        self.used = set()
        to = self.by_addr.get(step.to)
        try:
            if to is None:
                raise Unsup(f"the step's callee {step.to} is not a member")
            ok, data, logs = self.frame(to, step.caller, step.value, bytes.fromhex(step.data[2:]), -1, [])
        except Unsup as e:
            return {"status": UNSUPPORTED, "reason": str(e)[:500], "frames": self.frames}
        kept = self._kept()
        out = {"status": "ok" if ok else "revert", "revert": None if ok else "0x" + data.hex(),
               "return": "0x" + data.hex() if ok else None, "frames": [f[:5] + [kept[i]] for i, f in
                                                                    enumerate(self.frames)]}
        if ok:
            out["storage"] = self.st
            out["logs"] = logs
            out["balances"] = {n: self.bal.get(self.addr[n], 0) for n in self.names}
            out["outgoing"] = [o[:4] for o in self.outgoing if o[4] and kept[o[5]]]
        else:
            out["storage"] = {n: dict(pre[n]) for n in self.names}
            out["logs"] = []
            out["balances"] = {n: balances.get(self.addr[n], 0) for n in self.names}
            out["outgoing"] = []
        return out

    def _kept(self) -> list:
        kept = []
        for f in self.frames:
            k = bool(f[5])
            if f[0] >= 0:
                k = k and kept[f[0]]
            kept.append(k)
        return kept

    # ------------------------------------------------------------------------------------------- frames
    def frame(self, name: str, caller: str, value: int, data: bytes, parent: int, stack: list):
        """(ok, return or revert data, logs [(member, topics, data)]) of a frame on member `name`."""
        from ..extracted_eval import step as eval_step
        idx = len(self.frames)
        sel = "0x" + data[:4].hex() if len(data) >= 4 else ("0x" if not data else "0x" + data.hex())
        self.frames.append([parent, caller, name, sel, value, None])
        if len(stack) >= self.depth:
            raise Unsup("depth")
        saved = ({n: dict(s) for n, s in self.st.items()}, dict(self.bal))
        me = self.addr[name]
        if value:
            if self.bal.get(caller, 0) < value:
                raise Unsup(f"a call of {value} wei from {caller}, whose balance is lower")
            self.bal[caller] = self.bal.get(caller, 0) - value
            self.bal[me] = self.bal.get(me, 0) + value

        def revert(d: bytes):
            self.st, self.bal = saved
            self.frames[idx][5] = False
            return False, d, []
        if not data:
            action = "receive" if "receive" in self.models[name].actions else (
                "fallback" if "fallback" in self.models[name].actions else None)
        elif len(data) >= 4 and sel in self.by_sel[name]:
            action = self.by_sel[name][sel]
        elif len(data) >= 4 and sel in self.getters[name]:
            if name in stack:
                pass                          # a getter writes nothing: re-entry is allowed (L5)
            try:
                ret = self.getter(name, self.getters[name][sel], data[4:])
            except Unsup:
                raise
            self.frames[idx][5] = True
            return True, ret, []
        else:
            action = None
        if action is None:
            return revert(b"")
        if name in stack and self.writes[name].get(action):
            raise Unsup(f"reentry: {name}.{action}")
        model = self.models[name]
        try:
            args = self.decode(model, action, data)
        except Unsup:
            return revert(b"")
        env = self.env(name, caller, value, data, idx, stack + [name])
        r = eval_step(model, self.st[name], action, args, env)
        if r["status"] == "unsupported":
            raise Unsup(f"{name}.{action}: {r.get('reason')}")
        if r["status"] == "revert":
            if r.get("revert_prefix"):
                raise Unsup(f"{name}.{action}: only the revert data's selector is determined")
            return revert(bytes.fromhex(r["revert"][2:]))
        for k, v in r["writes"].items():
            self.st[name][int(k, 16)] = int(v, 16)
        self.frames[idx][5] = True
        logs = [(e.get("emitter", name), [t.lower() for t in e["topics"]], e["data"].lower()) for e in r["events"]]
        return True, bytes.fromhex((r.get("return") or "0x")[2:]), logs

    def decode(self, model, action: str, data: bytes) -> dict:
        from ..extracted_eval import abi_decode
        ps = model.params(action) or []
        if not ps:
            return {}
        try:
            vals = abi_decode(data[4:], ps)
        except Exception as e:  # noqa: BLE001  (the compiler's decoder reverts on malformed calldata)
            raise Unsup(f"calldata: {e}") from e
        return {p["name"]: v for p, v in zip(ps, vals)}

    def getter(self, name: str, entry: dict, argdata: bytes) -> bytes:
        """A public storage family's getter: the word(s) at the compiler's slots, ABI-encoded (L3)."""
        from ..extracted_eval import Eval, abi_decode, abi_encode, norm
        ins, outs = entry.get("inputs") or [], entry.get("outputs") or []
        if len(outs) != 1:
            raise Unsup(f"{name}.{entry['name']}: a getter of {len(outs)} values")
        try:
            keys = abi_decode(argdata, ins) if ins else []
        except Exception as x:  # noqa: BLE001
            raise Unsup(f"{name}.{entry['name']}: calldata: {x}") from x
        t = ["storage", entry["name"]]
        for k in keys:
            t = ["map", t, int.from_bytes(k, "big") if isinstance(k, (bytes, bytearray)) else int(k)]
        model = self.models[name]
        e = Eval(model, self.st[name], next(iter(model.actions)), {}, {})
        try:
            v = e.value(e.ev(t))
        except Exception as x:  # noqa: BLE001  (the evaluator's Unsupported)
            raise Unsup(f"{name}.{entry['name']}: {x}") from x
        return abi_encode([norm(v, outs[0])], outs)

    def env(self, name: str, caller: str, value: int, data: bytes, idx: int, stack: list) -> dict:
        s = self.step
        bal = {a: self.bal.get(a, s.before.get(a, 0)) for a in set(self.bal) | set(s.before)}
        imm = dict(self.dep["members"][name].get("immutables") or {})
        return {"caller": int(caller, 16), "this": int(self.addr[name], 16), "msg.value": value,
                "msg.data.length": len(data), "msg.data": data, "msg.sig": int.from_bytes(data[:4].ljust(4, b"\0"), "big"),
                "block.timestamp": s.timestamp, "block.number": s.number, "block.chainid": s.env.get("chainid"),
                "block.basefee": s.env.get("basefee"), "block.prevrandao": s.env.get("prevrandao"),
                "block.coinbase": s.env.get("coinbase"), "block.gaslimit": s.env.get("gaslimit"),
                "tx.origin": s.env.get("origin"), "tx.gasprice": s.env.get("gasprice"),
                "blobhash": list(getattr(s, "blobs", []) or []),
                "immutable": imm, "code": _Table(self.code, b""), "balance": _Table(bal, 0), "unknown": {},
                "return_data": True, "call_hook": self.hook(name, idx, stack)}

    def hook(self, name: str, idx: int, stack: list):
        memo: dict = {}
        me = self.addr[name]

        def call(ev, fn, receiver, args, sig, value):
            from ..extracted_eval import abi_decode, abi_encode, norm
            if fn.startswith("address."):
                to = _addr(receiver)
                data = bytes(args)
                v = value or 0
                # a call term the program evaluates more than once (its status and its data read separately) is
                # one call: answered once per frame
                lkey = ("low", to, v, data)
                if lkey not in memo:
                    memo[lkey] = self.dispatch(ev, name, me, idx, stack, to, v, data)
                    self.answers.setdefault(idx, []).append(
                        {"fn": fn, "to": to, "data": "0x" + data.hex(), "args": None, "ok": memo[lkey][0],
                         "ret": "0x" + memo[lkey][1].hex()})
                return memo[lkey]
            key = (fn, repr([ev.value(a) for a in args]))
            if receiver is None:
                if key in memo:
                    return memo[key]
                raise Unsup(f"{name}: the call {fn} has no receiver before its answer is needed")
            if sig is None or not sig.get("selector"):
                raise Unsup(f"{name}: the call {fn} has no known signature")
            ins = sig.get("inputs") or []
            data = bytes.fromhex(sig["selector"][2:]) + abi_encode([norm(ev.value(a), p) for a, p in zip(args, ins)],
                                                                   ins)
            ok, ret = self.dispatch(ev, name, me, idx, stack, _addr(receiver), 0, data)
            outs = sig.get("outputs") or []
            if ok and outs:                  # callok includes the decoder's checks (L4)
                try:
                    abi_decode(ret, outs)
                    if len(ret) < 32 * len(outs):
                        raise ValueError("short")
                except Exception:  # noqa: BLE001
                    ok, ret = False, b""
            memo[key] = (ok, ret)
            self.answers.setdefault(idx, []).append({"fn": fn, "to": _addr(receiver), "data": "0x" + data.hex(),
                                                     "args": None, "ok": ok, "ret": "0x" + ret.hex()})
            return ok, ret
        return call

    def dispatch(self, ev, name: str, me: str, idx: int, stack: list, to: str, value: int, data: bytes):
        callee = self.by_addr.get(to)
        if callee is not None:
            ok, ret, logs = self.frame(callee, me, value, data, idx, stack)
            if ok:
                for m, topics, d in logs:
                    ev.events.append({"topics": topics, "data": d, "emitter": m})
            return ok, ret
        # L7: a non-member, answered from the harness's record of the step's outgoing calls (in order)
        for k, o in enumerate(self.step.outgoing):
            if k in self.used:
                continue
            if self.names[o[0]] == name and o[1] == to and o[2] == value and o[3] == "0x" + data.hex():
                self.used.add(k)
                ok, ret = o[5], bytes.fromhex(o[6][2:])
                self.outgoing.append((name, to, value, "0x" + data.hex(), ok, idx))
                if ok and value:
                    self.bal[me] = self.bal.get(me, 0) - value
                    self.bal[to] = self.bal.get(to, 0) + value
                return ok, ret
        if not self.code.get(to):
            # an account without code: the call succeeds with empty return data (L7)
            self.outgoing.append((name, to, value, "0x" + data.hex(), True, idx))
            if value:
                self.bal[me] = self.bal.get(me, 0) - value
                self.bal[to] = self.bal.get(to, 0) + value
            return True, b""
        raise Unsup(f"{name}: a call to the non-member {to} with no recorded answer")
