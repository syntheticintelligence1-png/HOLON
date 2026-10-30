"""Rules C1-C2 and C4: the forge harness of the bundle (replay/<M>/bundle/), its deployment record and its runs.

The scratch project is the target's Foundry tree at the pinned checkout (holon.replay_fragments.harness_project), with
the harness files under test/: the generic multi-target step base (HolonBundleBase.sol), the concrete harness
(HolonBundle.t.sol) and the M1 trace harness it reuses (copied unchanged). A first run with no step gives the
deployment record (every member's address and implementation, code lengths, the named non-member addresses, the
deployment's storage writes and the members' balances); corpus steps are then encoded with those addresses and run in
chunks, each trace from a fresh deployment, and the harness's lines are parsed into per-step records.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import BundleError, Ctx

HARNESS_CONTRACT = "HolonBundleTest"
MAX_STEPS = 400


@dataclass
class StepRec:
    tid: int
    id: str
    kind: str = ""                 # call | env
    ok: bool = True
    to: str = ""
    caller: str = ""
    value: int = 0
    timestamp: int = 0
    number: int = 0
    data: str = "0x"
    ret: str = "0x"
    env: dict = field(default_factory=dict)
    before: dict = field(default_factory=dict)          # address -> balance before the call
    pokes: list = field(default_factory=list)           # (account, slot, word)
    writes: list = field(default_factory=list)          # (member, slot, value, reverted)
    logs: list = field(default_factory=list)            # (member, topics, data)
    frames: list = field(default_factory=list)          # [parent, caller, member, selector, value, reverted]
    outgoing: list = field(default_factory=list)        # (member, to, value, data, reverted, ok, ret)
    balances: dict = field(default_factory=dict)        # member index -> balance after the step


@dataclass
class TraceRec:
    tid: int
    members: dict = field(default_factory=dict)         # index -> (address, implementation)
    code: dict = field(default_factory=dict)            # address -> code length
    named: dict = field(default_factory=dict)           # name -> address
    runtime: dict = field(default_factory=dict)         # member index -> the runtime code it runs (hex)
    deploy: StepRec | None = None
    steps: list = field(default_factory=list)


def toolchain(ctx: Ctx) -> dict:
    from ..replay import toolchain as tc
    try:
        return tc(argparse.Namespace(forge=None, solc=None, write_pins=False), ctx.root)
    except SystemExit as e:
        raise BundleError(f"toolchain: {e}") from e


def harness_files(ctx: Ctx) -> list:
    h = ctx.out("harness")
    return [f"{h}/HolonBundleBase.sol", f"{h}/HolonBundle.t.sol", "replay/M1/solidity/HolonTraceReplay.t.sol"]


def project(ctx: Ctx, work: Path, tc: dict) -> Path:
    from ..replay_fragments import forge_build, harness_project
    binding = {"project": {"kind": "checkout", "foundry_dir": "contracts", "drop": ["mock", "test"]},
               "harness": {"files": harness_files(ctx)}}
    checkout = Path(ctx.source_repo())
    proj = harness_project(binding, work, ctx.root, checkout, tc)
    forge_build(proj, tc)
    return proj


def _int(s: str) -> int:
    return int(s, 16) if s.startswith("0x") else int(s)


def parse(text: str) -> list:
    """The harness's lines, as TraceRec records in trace order."""
    traces: dict = {}
    cur: dict = {}

    def tr(tid: int) -> TraceRec:
        if tid not in traces:
            traces[tid] = TraceRec(tid)
        return traces[tid]

    def rec(tid: int, sid: str) -> StepRec:
        key = (tid, sid)
        if key not in cur:
            r = StepRec(tid, sid)
            cur[key] = r
            t = tr(tid)
            if sid == "d":
                t.deploy = r
            else:
                t.steps.append(r)
        return cur[key]
    for ln in text.splitlines():
        p = ln.split(" ")
        tag = p[0]
        if tag == "T":
            tr(int(p[1])).members[int(p[2])] = (p[3].lower(), p[4].lower())
        elif tag == "K":
            tr(int(p[1])).code[p[2].lower()] = int(p[3])
        elif tag == "Q":
            tr(int(p[1])).runtime[int(p[2])] = p[3].lower()
        elif tag == "N":
            tr(int(p[1])).named[p[2]] = p[3].lower()
        elif tag == "S":
            r = rec(int(p[1]), p[2])
            r.kind, r.ok = p[3], p[4] == "1"
            r.to, r.caller = p[5].lower(), p[6].lower()
            r.value, r.timestamp, r.number = int(p[7]), int(p[8]), int(p[9])
            r.data, r.ret = p[10].lower(), p[11].lower()
        elif tag == "V":
            r = rec(int(p[1]), p[2])
            r.env = {"chainid": int(p[3]), "basefee": int(p[4]), "prevrandao": int(p[5]), "coinbase": p[6].lower(),
                     "gaslimit": int(p[7]), "origin": p[8].lower(), "gasprice": int(p[9])}
        elif tag == "A":
            rec(int(p[1]), p[2]).before[p[3].lower()] = int(p[4])
        elif tag == "P":
            rec(int(p[1]), p[2]).pokes.append((p[3].lower(), _int(p[4]), _int(p[5])))
        elif tag == "W":
            rec(int(p[1]), p[2]).writes.append((int(p[3]), _int(p[4]), _int(p[5]), p[6] == "1"))
        elif tag == "L":
            topics = [] if p[4] == "-" else [t.lower() for t in p[4].split(",")]
            rec(int(p[1]), p[2]).logs.append((int(p[3]), topics, p[5].lower()))
        elif tag == "F":
            rec(int(p[1]), p[2]).frames.append([int(p[3]), p[4].lower(), int(p[5]), p[6].lower(), int(p[7]),
                                                p[8] == "1"])
        elif tag == "O":
            rec(int(p[1]), p[2]).outgoing.append((int(p[3]), p[4].lower(), int(p[5]), p[6].lower(), p[7] == "1",
                                                  p[8] == "1", p[9].lower()))
        elif tag == "B":
            rec(int(p[1]), p[2]).balances[int(p[3])] = int(p[4])
    return [traces[k] for k in sorted(traces)]


def run_chunks(proj: Path, tc: dict, inputs: list, jobs: int, tag: str, log=print) -> list:
    """Run every (lo, hi, input document) chunk with forge, jobs at a time; return the parsed traces (renumbered)."""
    out: list = []
    pending = []
    for k, (lo, hi, doc) in enumerate(inputs):
        fin, fout = proj / f"holon_{tag}_{k}.json", proj / f"holon_{tag}_{k}.out"
        fin.write_text(json.dumps(doc))
        fout.unlink(missing_ok=True)
        cmd = ["nice", "-n", "10", tc["forge"], "test", "--match-contract", f"^{HARNESS_CONTRACT}$", "--match-test",
               "^test_steps\\(\\)$", "--offline", "--use", tc["solc"]]
        env = {**os.environ, "HOLON_STEPS_IN": fin.name, "HOLON_STEPS_OUT": fout.name, "HOLON_LO": "0",
               "HOLON_HI": str(hi - lo)}
        pending.append((k, lo, hi, fin, fout, cmd, env))
    results: dict = {}
    active: list = []

    def finish(item, proc):
        k, lo, hi, fin, fout, cmd, env = item
        o, _ = proc.communicate()
        text = fout.read_text() if fout.exists() else ""
        if proc.returncode != 0 or not text.rstrip().endswith(f"DONE 0 {hi - lo}"):
            raise BundleError(f"harness chunk {k} (traces {lo}..{hi}) failed (exit {proc.returncode}): "
                              f"{(o or '')[-3000:]}")
        trs = parse(text)
        for t in trs:
            t.tid += lo
            for s in ([t.deploy] if t.deploy else []) + t.steps:
                s.tid = t.tid
        results[k] = trs
        fin.unlink(missing_ok=True)
        fout.unlink(missing_ok=True)
        log(f"harness chunk {k + 1}/{len(inputs)} done")
    for item in pending:
        while len(active) >= max(1, jobs):
            it, pr = active.pop(0)
            finish(it, pr)
        proc = subprocess.Popen(item[5], cwd=proj, env=item[6], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True)
        active.append((item, proc))
    for it, pr in active:
        finish(it, pr)
    for k in sorted(results):
        out.extend(results[k])
    return out


# ------------------------------------------------------------------------------------------------------ encoding
def _enc(values: list, types: list) -> bytes:
    from ..extracted_eval import abi_encode, parse_types
    return abi_encode(values, parse_types(",".join(types)))


class Encoder:
    """Corpus steps as harness steps: names resolved to the deployment's addresses."""

    def __init__(self, ctx: Ctx, dep: TraceRec):
        self.ctx = ctx
        self.dep = dep
        names = [m["name"] for m in ctx.members()]
        self.addr = {f"@{n}": dep.members[i][0] for i, n in enumerate(names)}
        for k, v in ctx.side["deployment"]["actors"].items():
            self.addr[f"@{k}"] = dep.named["harness"] if v == "harness" else v.lower()
        self.member_addr = {n: dep.members[i][0] for i, n in enumerate(names)}
        self.facts = ctx.load(ctx.side["corpus"]["m1"]["facts"])

    def resolve(self, v):
        if isinstance(v, str) and v.startswith("@"):
            return self.addr[v]
        if isinstance(v, list):
            return [self.resolve(x) for x in v]
        return v

    def calldata(self, fn: str, args: list) -> bytes:
        from ..extracted_eval import abi_encode, parse_types, keccak
        if fn in ("", "receive", "fallback"):
            return b""
        name, rest = fn.split("(", 1)
        types = parse_types(rest[:-1]) if rest[:-1] else []
        sel = keccak(fn.encode()).to_bytes(32, "big")[:4]
        return sel + abi_encode(self.resolve(args), types)

    def call(self, c: dict, warp: int = 0) -> bytes:
        data = self.calldata(c["fn"], c["args"])
        payload = _enc([self.resolve(c["caller"]), c["value"], warp, self.member_addr[c["to"]], data],
                       ["address", "uint256", "uint256", "address", "bytes"])
        return _enc([2, payload], ["uint8", "bytes"])

    def relay_parts(self) -> dict:
        """C4's inputs, from the declaration and the documents: the member owning the relay family, the static link
        row (a getter of that family) whose action proves and relays, that action's ABI signature, and the signature
        its leaf encodes (the action's abi.encodeWithSignature literal)."""
        if hasattr(self, "_relay"):
            return self._relay
        rel = self.ctx.side["corpus"]["relay"]
        decl = self.ctx.load(self.ctx.out("declaration"))
        rows = [r for r in decl["links"] if r[5] == "getter" and r[6] == rel["family"]]
        if len(rows) != 1:
            raise BundleError(f"the relay family {rel['family']} is read by {len(rows)} link rows")
        member, action, _src, _fn, owner = rows[0][:5]
        doc = self.ctx.load(self.ctx.document_rel(self.ctx.member(member)))
        act = next(a for a in doc["actions"] if a["name"] == action)
        found = []

        def walk(t):
            if isinstance(t, list):
                if t and t[0] == "abi.encodeWithSignature" and isinstance(t[1], list) and t[1][0] == "str":
                    found.append(bytes.fromhex(t[1][1]).decode())
                for x in t:
                    walk(x)
            elif isinstance(t, dict):
                for x in t.values():
                    walk(x)
        walk(act)
        if len(set(found)) != 1:
            raise BundleError(f"{member}.{action}: {len(set(found))} encodeWithSignature literals")
        from .corpus import abis
        sig = abis(self.ctx)[member][act["selector"]]["signature"]
        self._relay = {"member": member, "owner": owner, "signature": sig, "leaf": found[0], "slot": rel["slot"]}
        return self._relay

    def relay(self, r: dict) -> bytes:
        from ..extracted_eval import abi_encode, keccak, parse_types
        p = self.relay_parts()
        frm, to = int(self.resolve(r["from"]), 16), int(self.resolve(r["to"]), 16)
        msg = bytes.fromhex(r["message"][2:])
        leaf = relay_leaf(p["leaf"], frm, to, r["value"], r["nonce"], msg)
        root = relay_root(leaf, r["nonce"])
        slots, words = [], []
        if r["root"] == "valid":
            slots, words = [keccak(root + p["slot"].to_bytes(32, "big"))], [1]
        elif r["root"] == "mismatch":
            other = relay_root(relay_leaf(p["leaf"], frm, to, r["value"], r["nonce"], msg + b"\x00"), r["nonce"])
            slots, words = [keccak(other + p["slot"].to_bytes(32, "big"))], [1]
        sig = p["signature"]
        data = keccak(sig.encode()).to_bytes(32, "big")[:4] + abi_encode(
            [frm, to, r["value"], r["nonce"], msg, [0] * 32, root], parse_types(sig.split("(", 1)[1][:-1]))
        call = _enc([self.resolve(r["caller"]), 0, 0, self.member_addr[p["member"]], data],
                    ["address", "uint256", "uint256", "address", "bytes"])
        payload = _enc([self.member_addr[p["owner"]], [x.to_bytes(32, "big") for x in slots],
                        [w.to_bytes(32, "big") for w in words], call], ["address", "bytes32[]", "bytes32[]", "bytes"])
        return _enc([3, payload], ["uint8", "bytes"])

    def row(self, a: dict) -> bytes:
        from ..mreplay import encode_step
        return _enc([1, _enc([encode_step(a, self.facts)], ["uint256[]"])], ["uint8", "bytes"])

    def step(self, st: dict) -> bytes:
        if "row" in st:
            return self.row(st["row"])
        if "relay" in st:
            return self.relay(st["relay"])
        return self.call(st["call"], st.get("warp", 0))


def relay_leaf(sig: str, frm: int, to: int, value: int, nonce: int, message: bytes) -> bytes:
    """C4: keccak256 of abi.encodeWithSignature(sig, from, to, value, nonce, message)."""
    from ..extracted_eval import abi_encode, parse_types, keccak
    body = abi_encode([frm, to, value, nonce, message], parse_types(sig.split("(", 1)[1][:-1]))
    return keccak(keccak(sig.encode()).to_bytes(32, "big")[:4] + body).to_bytes(32, "big")


def relay_root(leaf: bytes, nonce: int) -> bytes:
    """C4: the fold of 32 zero siblings over the leaf at index nonce."""
    from ..extracted_eval import keccak
    node = leaf
    for h in range(32):
        node = (keccak(bytes(32) + node) if (nonce >> h) & 1 else keccak(node + bytes(32))).to_bytes(32, "big")
    return node


def init_values(ctx: Ctx) -> list:
    return list(ctx.side["deployment"]["init"]["values"])


def watch_list(ctx: Ctx) -> list:
    return sorted(v.lower() for v in ctx.side["deployment"]["actors"].values() if v != "harness")


def deployment(proj: Path, tc: dict, ctx: Ctx, log=print) -> TraceRec:
    doc = {"lens": [0], "steps": [], "init": init_values(ctx), "watch": watch_list(ctx)}
    trs = run_chunks(proj, tc, [(0, 1, doc)], 1, "deploy", log)
    if len(trs) != 1 or trs[0].deploy is None:
        raise BundleError("the deployment run recorded no deployment")
    return trs[0]


def run_corpus(proj: Path, tc: dict, ctx: Ctx, corpus: dict, dep: TraceRec, jobs: int, log=print) -> list:
    enc = Encoder(ctx, dep)
    encoded = [["0x" + enc.step(st).hex() for st in tr["steps"]] for tr in corpus["traces"]]
    watch = sorted(set(watch_list(ctx)) | {dep.named["verifier"], dep.named["harness"]})
    inputs, lo, n = [], 0, 0
    for i, tr in enumerate(encoded):
        n += len(tr) + 1
        if n >= MAX_STEPS or i == len(encoded) - 1:
            steps = [s for t in encoded[lo:i + 1] for s in t]
            inputs.append((lo, i + 1, {"lens": [len(t) for t in encoded[lo:i + 1]], "steps": steps,
                                       "init": init_values(ctx), "watch": watch}))
            lo, n = i + 1, 0
    trs = run_chunks(proj, tc, inputs, jobs, "corpus", log)
    if len(trs) != len(corpus["traces"]):
        raise BundleError(f"the harness recorded {len(trs)} traces for {len(corpus['traces'])}")
    for t, tr in zip(trs, corpus["traces"]):
        if len(t.steps) != len(tr["steps"]):
            raise BundleError(f"trace {tr['id']}: {len(t.steps)} records for {len(tr['steps'])} steps")
    return trs
