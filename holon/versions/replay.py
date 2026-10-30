"""Rule V9: `python -m holon versions replay [--check]`, the versioned machine's traces on the real code.

The runs: the sidecar's upgrade path (V7, name "upgrade_path"), every REFUTED PAR-init record's witness (name its law
id) and the in-flight inhabitant of every edge of the path, in its order (name "inflight:<a>-><b>", when it has one;
I83, rule IS3: I28 ran the last edge's alone). Each runs on the
model (holon.versions.machine) and, through the versioned harness, on the real code: an OpenZeppelin 4.9.3
TransparentUpgradeableProxy of the pinned dependency tree, constructed over a placeholder contract (no function, no
storage) with the binding's proxy admin, at the deployment record's target address; every path version's implementation
built from its commit by the pinned solc under the compiler configuration of its matched upgrades (I63's timeline) and
constructed with the binding's constructor arguments (the deployment record's immutables, by name); the labelled
stand-in (holon.versions.machine) at the binding's stand-ins and at every account a model run calls; each migration
step the admin's upgradeTo or upgradeToAndCall, each other step a call by its caller, at the deployment record's block.

Per step: the model's and the real status and revert data, and one entry per real slot in the union of the slots the
model's step writes and those whose word the real step changes (the harness's state diff; the proxy's EIP-1967 slots
aside), with both words after the step. An inhabitant's run also reads each legacy word on the real chain before the
migration step, and calls each retyped or reinterpreted entry's public getter after it. A run passes when every step's
statuses, revert data and words agree; a disagreement is reported, never smoothed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import PLACEHOLDER, REPLAY_VERSION, Ctx, Refused, VersionsError, render, write_or_check
from .machine import Machine, cd_bytes, h32, num, solc_standard, storage_of

FOUNDRY = """[profile.default]
src = 'src'
test = 'test'
out = 'out'
libs = ['node_modules']
evm_version = 'cancun'
optimizer = false
fs_permissions = [{ access = 'read-write', path = './' }]
"""
REMAP = ("forge-std/=node_modules/forge-std/src/\nds-test/=node_modules/ds-test/src/\n"
         "@openzeppelin/=node_modules/@openzeppelin/\n")
PLACEHOLDER_SOL = """// SPDX-License-Identifier: MIT
// HOLON I28: the placeholder implementation the proxy is created over (no function, no storage).
pragma solidity =0.8.24;

contract HolonVersionsPlaceholder {}
"""
HARNESS = """// SPDX-License-Identifier: MIT
// HOLON I28: the versioned harness (holon.versions.replay). It compares nothing: it runs the traces on the real code and
// writes what happened, one record per line, for Python to compare with the versioned model.
//
// Input ($HOLON_VERSIONS_IN): setup [proxy, admin, timestamp, number, chainid], impls (each implementation's creation
// code with its constructor arguments), standinAt and standinCode (accounts given the labelled stand-in's code), lens
// (steps per run) and steps (abi.encode(uint8 kind (0 migrate, 1 call), uint256 impl, bool withCall, address caller,
// bytes data, bytes32[] pre, bytes32[] post, bytes[] probes)). Every run starts from the same state: the stand-ins in
// place, the implementations and the placeholder constructed at addresses of their own (keccak256 of a tag and an index),
// then a fresh proxy constructed at setup[0] over the placeholder with admin setup[1].
// Output ($HOLON_VERSIONS_OUT): K <i> <runtime code>; P <run> <proxy code>; B <run> <step> <slot> <word> (pre reads);
// S <run> <step> <ok> <return data>; W <run> <step> <slot> <previous> <new> (every storage write to the proxy that
// is not reverted, in order); A <run> <step> <slot> <word> (post reads); G <run> <step> <i> <ok> <return data>
// (probe calls after the step); DONE <runs>.
pragma solidity =0.8.24;

import {Test} from "forge-std/Test.sol";
import {TransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";
import {HolonVersionsPlaceholder} from "../src/HolonVersionsPlaceholder.sol";

interface HolonVersionsVm {
    enum AccountAccessKind { Call, DelegateCall, CallCode, StaticCall, Create, SelfDestruct, Resume, Balance,
                             Extcodesize, Extcodehash, Extcodecopy }
    struct ChainInfo { uint256 forkId; uint256 chainId; }
    struct StorageAccess { address account; bytes32 slot; bool isWrite; bytes32 previousValue; bytes32 newValue;
                           bool reverted; }
    struct AccountAccess { ChainInfo chainInfo; AccountAccessKind kind; address account; address accessor;
                           bool initialized; uint256 oldBalance; uint256 newBalance; bytes deployedCode; uint256 value;
                           bytes data; bool reverted; StorageAccess[] storageAccesses; uint64 depth; }
    function snapshotState() external returns (uint256);
    function revertToState(uint256) external returns (bool);
    function startStateDiffRecording() external;
    function stopAndReturnStateDiff() external returns (AccountAccess[] memory);
    function prank(address) external;
    function warp(uint256) external;
    function roll(uint256) external;
    function chainId(uint256) external;
    function etch(address, bytes calldata) external;
    function load(address, bytes32) external view returns (bytes32);
    function pauseGasMetering() external;
    function readFile(string calldata) external view returns (string memory);
    function writeLine(string calldata, string calldata) external;
    function envString(string calldata) external view returns (string memory);
    function parseJsonUintArray(string calldata, string calldata) external pure returns (uint256[] memory);
    function parseJsonBytesArray(string calldata, string calldata) external pure returns (bytes[] memory);
    function toString(bytes calldata) external pure returns (string memory);
    function toString(uint256) external pure returns (string memory);
}

contract HolonVersionsReplayTest is Test {
    HolonVersionsVm internal constant HV = HolonVersionsVm(address(uint160(uint256(keccak256("hevm cheat code")))));
    string internal out;
    uint256[] internal setupw;
    address[] internal impls;

    function line(string memory s) internal {
        HV.writeLine(out, s);
    }

    function hb(bytes memory b) internal pure returns (string memory) {
        return HV.toString(b);
    }

    function hw(bytes32 w) internal pure returns (string memory) {
        return HV.toString(abi.encodePacked(w));
    }

    function dec(uint256 v) internal pure returns (string memory) {
        return HV.toString(v);
    }

    function pre(uint256 r, uint256 j) internal pure returns (string memory) {
        return string.concat(dec(r), " ", dec(j), " ");
    }

    // a contract constructed at a chosen address: its creation code run there, then its runtime code put there (no
    // CREATE of this test contract, whose addresses the binding's stand-ins already hold)
    function deployAt(address a, bytes memory init) internal {
        HV.etch(a, init);
        (bool ok, bytes memory rt) = a.call("");
        require(ok, "construction failed");
        HV.etch(a, rt);
    }

    function slotAddress(string memory tag, uint256 i) internal pure returns (address) {
        return address(uint160(uint256(keccak256(abi.encode("holon.versions.harness", tag, i)))));
    }

    function env() internal {
        HV.warp(setupw[2]);
        HV.roll(setupw[3]);
        HV.chainId(setupw[4]);
    }

    function proxy(address placeholder) internal returns (address p) {
        p = address(uint160(setupw[0]));
        deployAt(p, abi.encodePacked(type(TransparentUpgradeableProxy).creationCode,
                                     abi.encode(placeholder, address(uint160(setupw[1])), bytes(""))));
    }

    struct Step {
        uint8 kind;
        uint256 impl;
        bool withCall;
        address caller;
        bytes data;
        bytes32[] before;
        bytes32[] afterw;
        bytes[] probes;
    }

    function decode(bytes memory enc) internal pure returns (Step memory s) {
        (s.kind, s.impl, s.withCall, s.caller, s.data, s.before, s.afterw, s.probes) =
            abi.decode(enc, (uint8, uint256, bool, address, bytes, bytes32[], bytes32[], bytes[]));
    }

    function reads(string memory tag, uint256 r, uint256 j, address p, bytes32[] memory slots) internal {
        for (uint256 i = 0; i < slots.length; i++) {
            bytes32 w = HV.load(p, slots[i]);
            line(string.concat(tag, pre(r, j), hw(slots[i]), " ", hw(w)));
        }
    }

    function exec(address p, Step memory s) internal returns (bool ok, bytes memory ret) {
        if (s.kind == 0) {
            HV.prank(address(uint160(setupw[1])));
            if (s.withCall) {
                (ok, ret) = p.call(abi.encodeWithSignature("upgradeToAndCall(address,bytes)", impls[s.impl], s.data));
            } else {
                (ok, ret) = p.call(abi.encodeWithSignature("upgradeTo(address)", impls[s.impl]));
            }
        } else {
            HV.prank(s.caller);
            (ok, ret) = p.call(s.data);
        }
    }

    function writes(uint256 r, uint256 j, address p, HolonVersionsVm.AccountAccess[] memory acc) internal {
        for (uint256 a = 0; a < acc.length; a++) {
            HolonVersionsVm.StorageAccess[] memory st = acc[a].storageAccesses;
            for (uint256 b = 0; b < st.length; b++) {
                if (st[b].account != p || !st[b].isWrite || st[b].reverted) continue;
                line(string.concat("W ", pre(r, j), hw(st[b].slot), " ", hw(st[b].previousValue), " ",
                                   hw(st[b].newValue)));
            }
        }
    }

    function probe(uint256 r, uint256 j, address p, bytes[] memory probes) internal {
        for (uint256 i = 0; i < probes.length; i++) {
            (bool pok, bytes memory pret) = p.staticcall(probes[i]);
            line(string.concat("G ", pre(r, j), dec(i), pok ? " 1 " : " 0 ", hb(pret)));
        }
    }

    function step(uint256 r, uint256 j, address p, bytes memory enc) internal {
        Step memory s = decode(enc);
        reads("B ", r, j, p, s.before);
        HV.startStateDiffRecording();
        (bool ok, bytes memory ret) = exec(p, s);
        HolonVersionsVm.AccountAccess[] memory acc = HV.stopAndReturnStateDiff();
        line(string.concat("S ", pre(r, j), ok ? "1 " : "0 ", hb(ret)));
        writes(r, j, p, acc);
        reads("A ", r, j, p, s.afterw);
        probe(r, j, p, s.probes);
    }

    function test_replay() public {
        HV.pauseGasMetering();
        string memory inp = HV.readFile(HV.envString("HOLON_VERSIONS_IN"));
        out = HV.envString("HOLON_VERSIONS_OUT");
        setupw = HV.parseJsonUintArray(inp, ".setup");
        bytes[] memory codes = HV.parseJsonBytesArray(inp, ".impls");
        uint256[] memory sAt = HV.parseJsonUintArray(inp, ".standinAt");
        bytes[] memory sCode = HV.parseJsonBytesArray(inp, ".standinCode");
        uint256[] memory lens = HV.parseJsonUintArray(inp, ".lens");
        bytes[] memory steps = HV.parseJsonBytesArray(inp, ".steps");
        env();
        for (uint256 i = 0; i < sAt.length; i++) {
            HV.etch(address(uint160(sAt[i])), sCode[i]);
        }
        for (uint256 i = 0; i < codes.length; i++) {
            impls.push(slotAddress("implementation", i));
            deployAt(impls[i], codes[i]);
            line(string.concat("K ", dec(i), " ", hb(impls[i].code)));
        }
        address placeholder = slotAddress("placeholder", 0);
        deployAt(placeholder, type(HolonVersionsPlaceholder).creationCode);
        uint256 snap = HV.snapshotState();
        uint256 k = 0;
        for (uint256 r = 0; r < lens.length; r++) {
            HV.revertToState(snap);
            env();
            address p = proxy(placeholder);
            line(string.concat("P ", dec(r), " ", hb(p.code)));
            for (uint256 j = 0; j < lens[r]; j++) {
                step(r, j, p, steps[k]);
                k++;
            }
        }
        line(string.concat("DONE ", dec(lens.length)));
    }
}
"""


# ------------------------------------------------------------------------------------------------ implementations
def matched_configs(ctx: Ctx) -> dict:
    """{version: the compiler configuration of its matched upgrades} (sidecar replay.configurations), Refused when a
    version's upgrades match under several configurations."""
    out = {}
    for u in ctx.timeline["upgrades"]:
        for mt in u.get("matches") or []:
            if out.setdefault(mt["version"], mt["config"]) != mt["config"]:
                raise Refused(f"{mt['version']}'s upgrades match under several configurations")
    return out


def build_implementation(ctx: Ctx, vid: str, config: str) -> dict:
    """{"creation": bytes, "abi": [..], "commit"} of the version's contract built from its commit's tree under the
    configuration (I63's settings), cached under the build directory."""
    from ..bend import build_dir
    from ..replay import ensure_sol_deps
    from .extract import tree
    hside = json.loads((ctx.root / ctx.inputs["history_sidecar"]).read_text(encoding="utf-8"))
    conf = hside["compiler_configs"][config]
    unit, name = hside["contract"]["source"], hside["contract"]["name"]
    commit = ctx.version(vid)["commit"]
    key = hashlib.sha256(json.dumps([commit, conf, unit, name], sort_keys=True).encode()).hexdigest()[:16]
    cache = build_dir(ctx.root) / "versions" / "impl" / f"{vid}-{key}.json"
    if cache.is_file():
        d = json.loads(cache.read_text())
        return {"creation": bytes.fromhex(d["creation"]), "abi": d["abi"], "commit": commit}
    repo = json.loads((ctx.root / ctx.inputs["extract_sidecar"]).read_text(encoding="utf-8"))["target"]["repo"]
    t = tree(ctx, repo, commit, hside["contract"]["build_paths"])
    deps = ensure_sol_deps(Path((ctx.cfg.get("replay") or {}).get("sol_deps") or ""))
    settings = {"evmVersion": conf["evm_version"], "optimizer": {"enabled": True, "runs": int(conf["optimizer_runs"])},
                "metadata": {"bytecodeHash": conf["bytecode_hash"]},
                "outputSelection": {unit: {name: ["abi", "evm.bytecode.object", "evm.bytecode.linkReferences"]}}}
    out = solc_standard(ctx.cfg, {unit: {"content": (t / unit).read_text(encoding="utf-8")}}, settings, cwd=t,
                        include=deps)
    c = out["contracts"][unit][name]
    if c["evm"]["bytecode"].get("linkReferences"):
        raise VersionsError(f"{vid}: {name} links libraries; the harness deploys no library")
    d = {"creation": c["evm"]["bytecode"]["object"], "abi": c["abi"]}
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_name(cache.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(d))
    os.replace(tmp, cache)
    return {"creation": bytes.fromhex(d["creation"]), "abi": d["abi"], "commit": commit}


def constructor_args(m: Machine, abi: list) -> bytes:
    """The binding's constructor arguments: the deployment record's immutables by name, one per constructor input."""
    from ..evm_abi import encode_args
    cons = next((x for x in abi if x.get("type") == "constructor"), None)
    ins = (cons or {}).get("inputs") or []
    imm = m.dep.get("immutables") or {}
    if len(ins) != len(imm):
        raise Refused(f"the constructor takes {len(ins)} arguments, the deployment record holds {len(imm)} immutables")
    vals = [num(imm[k]) for k in sorted(imm)]
    return encode_args(ins, vals)


# ------------------------------------------------------------------------------------------------ runs
class Plan:
    """The runs to replay: their traces, the model's outcomes, and what the harness reads per step."""

    def __init__(self, m: Machine):
        self.m = m
        self.runs: list = []     # [{"name", "trace", "outs", "pre": [[slot]], "probes": [[(entry, getter, args, cd)]]}]

    def add(self, name: str, trace: list, legacy: list | None = None, after: list | None = None,
            extra: dict | None = None) -> None:
        outs, kh, sh = self.m.run(trace)
        n = len(trace)
        pre = [[] for _ in range(n)]
        probes = [[] for _ in range(n)]
        if legacy:
            pre[n - 1] = [num(w["slot"]) for w in legacy]
        if after:
            probes[n - 1] = list(after)
        self.runs.append({"name": name, "trace": trace, "outs": outs, "pre": pre, "probes": probes,
                          "legacy": legacy or [], "after": after or [], "extra": extra or {}})


def eip1967(ctx: Ctx) -> set:
    return {int(str(ctx.side["proxy"][k]), 16) for k in ("admin_slot", "implementation_slot")}


def harness_input(ctx: Ctx, m: Machine, plan: Plan, impls: list, called: set) -> dict:
    from ..evm_abi import encode_args
    path = m.path
    skip = eip1967(ctx)
    setup = [num(m.dep["target"]), m.admin, num(m.dep.get("timestamp") or 0), num(m.dep.get("number") or 0),
             num(m.dep.get("chainid") or 0)]
    stand = sorted(set(m.standin_addresses()) | set(called))
    steps, lens = [], []
    t = [{"type": "uint8"}, {"type": "uint256"}, {"type": "bool"}, {"type": "address"}, {"type": "bytes"},
         {"type": "bytes32[]"}, {"type": "bytes32[]"}, {"type": "bytes[]"}]
    for run in plan.runs:
        lens.append(len(run["trace"]))
        for i, (st, o) in enumerate(zip(run["trace"], run["outs"])):
            post = sorted(x for x in o["writes"] if x not in skip)
            mig = st["kind"] == "migrate"
            vals = [0 if mig else 1, path.index(st["version"]), bool(mig and st.get("call")),
                    "0x" + h32(num(st["caller"]))[-40:], st["calldata"] if (st.get("call") or not mig) else "0x",
                    ["0x%064x" % x for x in run["pre"][i]], ["0x%064x" % x for x in post],
                    [p["calldata"] for p in run["probes"][i]]]
            steps.append("0x" + encode_args(t, vals).hex())
    return {"setup": setup, "impls": ["0x" + c.hex() for c in impls], "standinAt": stand,
            "standinCode": ["0x" + m.standin().hex() for _ in stand], "lens": lens, "steps": steps}


def parse_output(text: str) -> dict:
    out = {"K": {}, "P": {}, "steps": {}, "done": None}
    for ln in text.splitlines():
        f = ln.split()
        if not f:
            continue
        if f[0] == "K":
            out["K"][int(f[1])] = f[2] if len(f) > 2 else "0x"
        elif f[0] == "P":
            out["P"][int(f[1])] = f[2] if len(f) > 2 else "0x"
        elif f[0] in ("B", "S", "W", "A", "G"):
            r, j = int(f[1]), int(f[2])
            d = out["steps"].setdefault((r, j), {"B": [], "S": None, "W": [], "A": [], "G": []})
            if f[0] == "S":
                d["S"] = (f[3] == "1", f[4] if len(f) > 4 else "0x")
            elif f[0] == "W":
                d["W"].append((int(f[3], 16), int(f[4], 16), int(f[5], 16)))
            elif f[0] == "G":
                d["G"].append((int(f[3]), f[4] == "1", f[5] if len(f) > 5 else "0x"))
            else:
                d[f[0]].append((int(f[3], 16), int(f[4], 16)))
        elif f[0] == "DONE":
            out["done"] = int(f[1])
    return out


def run_harness(ctx: Ctx, data: dict, work: Path) -> dict:
    from ..replay import _sol_deps, toolchain
    tc = toolchain(argparse.Namespace(forge=None, solc=None, write_pins=False), ctx.root)
    proj = work / "solidity"
    (proj / "src").mkdir(parents=True, exist_ok=True)
    (proj / "test").mkdir(parents=True, exist_ok=True)
    (proj / "foundry.toml").write_text(FOUNDRY)
    (proj / "remappings.txt").write_text(REMAP)
    (proj / "src" / "HolonVersionsPlaceholder.sol").write_text(PLACEHOLDER_SOL)
    (proj / "test" / "HolonVersionsReplay.t.sol").write_text(HARNESS)
    _sol_deps(proj, Path(tc["sol_deps"]))
    fin, fout = proj / "holon_versions_in.json", proj / "holon_versions_out.txt"
    fin.write_text(json.dumps(data))
    fout.unlink(missing_ok=True)
    cmd = [tc["forge"], "test", "--match-contract", "^HolonVersionsReplayTest$", "--match-test", r"^test_replay\(\)$",
           "--offline", "--use", tc["solc"]]
    env = {**os.environ, "HOLON_VERSIONS_IN": fin.name, "HOLON_VERSIONS_OUT": fout.name}
    p = subprocess.run(cmd, cwd=proj, env=env, capture_output=True, text=True, timeout=7200)
    text = fout.read_text() if fout.exists() else ""
    res = parse_output(text)
    if p.returncode != 0 or res["done"] != len(data["lens"]):
        raise VersionsError(f"the versioned harness failed (exit {p.returncode}): {(p.stdout + p.stderr)[-3000:]}")
    return {"out": res, "toolchain": {k: tc[k] for k in ("forge_sha256", "solc_sha256", "sol_deps_sha256",
                                                          "go_version")}}


def hexw(n: int) -> str:
    return "0x%064x" % (int(n) % (1 << 256))


def compare(ctx: Ctx, run: dict, r: int, real: dict) -> dict:
    """The run's report entry from the model's outcomes and the harness's records."""
    skip = eip1967(ctx)
    steps, ok_all = [], True
    for j, (st, o) in enumerate(zip(run["trace"], run["outs"])):
        d = real["steps"].get((r, j))
        if d is None or d["S"] is None:
            raise VersionsError(f"the harness recorded no step {j} of run {run['name']}")
        rok, ret = d["S"]
        first, last = {}, {}
        for slot, prev, new in d["W"]:
            first.setdefault(slot, prev)
            last[slot] = new
        changed = {s for s in last if last[s] != first[s]}
        post = dict(d["A"])
        model_post = storage_of(o["state"]["sl"])
        slots = []
        for s in sorted((set(o["writes"]) | changed) - skip):
            mw = model_post.get(s, 0)
            rw = last[s] if s in last else post.get(s)
            if rw is None:
                raise VersionsError(f"run {run['name']} step {j}: no real word read at slot {hexw(s)}")
            slots.append({"slot": hexw(s), "model": hexw(mw), "real": hexw(rw)})
        mstat, rstat = o["status"], "ok" if rok else "revert"
        mrev = o["revert"] if mstat == "revert" else "0x"
        rrev = ret if not rok else "0x"
        agree = (mstat == rstat and cd_bytes(mrev) == cd_bytes(rrev)
                 and all(num(x["model"]) == num(x["real"]) for x in slots))
        ok_all = ok_all and agree
        steps.append({"model": mstat, "real": rstat, "revert": {"model": mrev, "real": "0x" + cd_bytes(rrev).hex()},
                      "slots": slots})
    entry = {"name": run["name"], "trace": run["trace"], "steps": steps}
    if run["legacy"]:
        n = len(run["trace"])
        reads = dict(real["steps"][(r, n - 1)]["B"])
        entry["legacy"] = [{"reads": w["reads"], "slot": hexw(num(w["slot"])), "real": hexw(reads.get(num(w["slot"]), 0))}
                           for w in run["legacy"]]
        ok_all = ok_all and all(num(x["real"]) == num(w["word"]) for x, w in zip(entry["legacy"], run["legacy"]))
    if run["after"]:
        n = len(run["trace"])
        got = {i: (pok, pret) for i, pok, pret in real["steps"][(r, n - 1)]["G"]}
        entry["after"] = []
        for i, a in enumerate(run["after"]):
            pok, pret = got.get(i, (False, "0x"))
            b = cd_bytes(pret)
            entry["after"].append({"entry": a["entry"], "getter": a["getter"], "args": [hexw(x) for x in a["args"]],
                                   "ok": pok, "real": [hexw(int.from_bytes(b[k:k + 32], "big"))
                                                       for k in range(0, len(b), 32)]})
    entry.update(run["extra"])
    entry["passed"] = ok_all
    return entry


# ------------------------------------------------------------------------------------------------ the report
def plan_runs(ctx: Ctx, m: Machine) -> Plan:
    from .paths import upgrade_path
    plan = Plan(m)
    plan.add("upgrade_path", upgrade_path(m))
    res = ctx.root / "results" / ctx.milestone
    from .run import init_entries
    for lid in sorted(init_entries(ctx.milestone, ctx.root)):
        p = res / f"{lid}.json"
        if not p.is_file():
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))
        if rec.get("status") != "REFUTED" or not rec.get("witness"):
            continue
        w = rec["witness"]
        plan.add(lid, w["trace"], extra={"witness_sha256": witness_sha256(w)})
    ip = ctx.root / ctx.out("inflight_results")
    if ip.is_file() and m.path[1:]:
        edges = {e.get("edge"): e for e in json.loads(ip.read_text(encoding="utf-8")).get("edges") or []}
        for a, b in zip(m.path, m.path[1:]):        # I83 (rule IS3): every edge's inhabitant, in the path's order
            edge = f"{a}->{b}"
            x = edges.get(edge)
            if x and x.get("trace"):
                plan.add(f"inflight:{edge}", x["trace"], legacy=x.get("legacy"), after=getters(ctx, m, edge, x))
    return plan


def witness_sha256(w: dict) -> str:
    return hashlib.sha256(json.dumps(w, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def load(ctx: Ctx) -> dict | None:
    """The committed replay report, None when there is none or it is unreadable."""
    p = ctx.root / ctx.out("replay")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def replay_status(ctx: Ctx, rep: dict | None, lid: str, witness: dict | None) -> dict:
    """A REFUTED PAR-init record's replay field, from the report: passed or failed only when the report's one run named
    lid replayed this witness (its trace and its sha256), else not_run."""
    rel = ctx.out("replay")
    if not isinstance(rep, dict):
        return {"status": "not_run", "detail": f"no replay report ({rel})"}
    runs = [r for r in rep.get("runs") or [] if isinstance(r, dict) and r.get("name") == lid]
    if len(runs) != 1:
        return {"status": "not_run", "detail": f"{rel} has {len(runs)} runs named {lid}"}
    r = runs[0]
    if not isinstance(witness, dict) or r.get("witness_sha256") != witness_sha256(witness) \
            or r.get("trace") != witness.get("trace"):
        return {"status": "not_run", "detail": f"{rel}'s run {lid} replayed another witness"}
    ok = r.get("passed") is True
    return {"status": "passed" if ok else "failed",
            "detail": f"run {lid} of {rel}: {len(r.get('steps') or [])} steps, statuses, revert data and words "
                      + ("agree" if ok else "disagree")}


def side(root, milestone: str, lid: str, witness: dict | None) -> dict | None:
    """The replay side (holon.filter's sides format) of a REFUTED PAR-init record from its run in the versions replay
    report, None when the milestone has no versions sidecar or the report has no run of this witness. The run is a
    public schedule on a deployed system: the proxy constructed over the placeholder, each implementation constructed
    from its creation code, every step a call through the proxy by its caller (a migration the admin's). The
    obstruction is observed when the run passed and the real root step succeeded and wrote the words the model's
    did (the commitment of the input bytes the counter-law's claim is false of)."""
    root = Path(root)
    rel = f"spec/{milestone}/lib/versions.json"
    if not (root / rel).is_file():
        return None
    ctx = Ctx(root, rel)
    rep = load(ctx)
    st = replay_status(ctx, rep, lid, witness)
    if st["status"] == "not_run":
        return None
    r = next(x for x in rep["runs"] if x.get("name") == lid)
    last = (r.get("steps") or [{}])[-1]
    words = [x for x in last.get("slots") or [] if num(x.get("real", "0x0")) != 0]
    seen = bool(r.get("passed") is True and last.get("real") == "ok" and words
                and all(num(x["real"]) == num(x["model"]) for x in last.get("slots") or []))
    return {"status": st["status"], "provenance": "public_schedule", "obstruction_observed": seen,
            "run": lid, "report": ctx.out("replay"),
            "basis": f"run {lid} of {ctx.out('replay')}: every step's status, revert data and words agree with the "
                     "model's; the root step succeeded on the real code and wrote the commitment of the input bytes the "
                     "counter-law's claim is false of" if seen else
                     f"run {lid} of {ctx.out('replay')}: the real root step's success and written words are not the "
                     "model's"}


def g6(milestone: str, root) -> tuple[bool, str] | None:
    """G6 over the PAR-init laws of a milestone with a versions sidecar (None without one): every REFUTED PAR-init
    record is bound to a passed run of the replay report (its witness's sha256), and its replay field says so."""
    from .run import init_entries
    root = Path(root)
    rel = f"spec/{milestone}/lib/versions.json"
    if not (root / rel).is_file():
        return None
    ctx = Ctx(root, rel)
    rep = load(ctx)
    bad, n = [], 0
    for lid in sorted(init_entries(milestone, root)):
        p = root / "results" / milestone / f"{lid}.json"
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            bad.append(f"{lid}: no readable result record")
            continue
        if not isinstance(rec, dict) or rec.get("status") != "REFUTED":
            continue
        n += 1
        st = replay_status(ctx, rep, lid, rec.get("witness"))
        if st["status"] != "passed":
            bad.append(f"{lid}: {st['detail']}")
        elif rec.get("replay") != st:
            bad.append(f"{lid}: the record's replay field is not the report's ({(rec.get('replay') or {}).get('status')})")
    return not bad, (f"{n} REFUTED PAR-init records bound to passed runs of {ctx.out('replay')}" if not bad
                     else "; ".join(bad))


def stamp(ctx: Ctx, rep: dict) -> list:
    """Bring the REFUTED PAR-init records' replay field up to the report (replay_status); the ids changed."""
    from .run import init_entries
    changed = []
    for lid in sorted(init_entries(ctx.milestone, ctx.root)):
        p = ctx.root / "results" / ctx.milestone / f"{lid}.json"
        if not p.is_file():
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))
        if rec.get("status") != "REFUTED":
            continue
        new = replay_status(ctx, rep, lid, rec.get("witness"))
        if new != rec.get("replay"):
            rec["replay"] = new
            p.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            changed.append(lid)
    return changed


def getters(ctx: Ctx, m: Machine, edge: str, x: dict) -> list:
    """Each retyped or reinterpreted entry's public getter (named by the entry's label) at the edge's new version, with
    the trace's key for a mapping: [{"entry", "getter", "args", "calldata"}]."""
    a, b = edge.split("->")
    out, abi = [], None
    for t in m.vd.get("in_flight_types") or []:
        if t["edge"] != edge:
            continue
        label = t["entry"].split(".", 1)[1]
        lay = [e for e in ctx.version(b)["layout"] if f"{e['contract']}.{e['label']}" == t["entry"]]
        fn = m.function(b, label)
        if fn is None:      # I83: a public variable's getter is no action of the document; the compiler's ABI has it
            if abi is None:
                abi = build_implementation(ctx, b, matched_configs(ctx)[b])["abi"]
            fn = abi_getter(abi, label)
        if fn is None or not lay:
            continue
        args = [num(x["key"])] if lay[0]["type"].get("encoding") == "mapping" else []
        from ..evm_abi import encode_args
        cd = fn["selector"] + encode_args(fn["inputs"], args).hex()
        out.append({"entry": t["entry"], "getter": label, "args": args, "calldata": cd})
    return out


def abi_getter(abi: list, name: str) -> dict | None:
    """{name, inputs, selector} of the compiled ABI's view function `name` (a public variable's getter), or None."""
    from ..evm_abi import selector
    fs = [f for f in abi if f.get("type") == "function" and f.get("name") == name
          and f.get("stateMutability") in ("view", "pure")]
    if len(fs) != 1:
        return None
    return {"name": name, "inputs": fs[0].get("inputs") or [], "selector": selector(name, fs[0].get("inputs") or [])}


def report(ctx: Ctx, log=None) -> dict:
    m = Machine(ctx)
    try:
        plan = plan_runs(ctx, m)
        cfgs = matched_configs(ctx)
        impls, meta = [], {}
        for vid in m.path:
            b = build_implementation(ctx, vid, cfgs[vid])
            impls.append(b["creation"] + constructor_args(m, b["abi"]))
            meta[vid] = {"commit": b["commit"], "config": cfgs[vid]}
        called = {num(c["to"]) for run in plan.runs for o in run["outs"] for c in o.get("calls") or []
                  if c.get("to") is not None}
        data = harness_input(ctx, m, plan, impls, called)
        work = Path(tempfile.mkdtemp(prefix="holon-versions-replay-"))
        try:
            res = run_harness(ctx, data, work)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        out = res["out"]
        for i, vid in enumerate(m.path):
            meta[vid]["code_sha256"] = hashlib.sha256(cd_bytes(out["K"].get(i, "0x"))).hexdigest()
        runs = [compare(ctx, run, r, out) for r, run in enumerate(plan.runs)]
        if log:
            for x in runs:
                log(f"{x['name']}: {'passed' if x['passed'] else 'FAILED'} ({len(x['steps'])} steps)")
        return {"replay_version": REPLAY_VERSION, "toolchain": res["toolchain"], "implementations": meta,
                "runs": runs}
    finally:
        m.close()


def run(ctx: Ctx, check: bool) -> int:
    doc = report(ctx, log=lambda s: print(f"holon versions replay: {s}"))
    target = ctx.root / ctx.out("replay")
    ok = write_or_check(target, render(doc), check)
    if check:
        print(f"holon versions replay: {ctx.out('replay')} {'reproduces' if ok else 'differs from a fresh replay'}")
        return 0 if ok else 1
    print(f"holon versions replay: wrote {ctx.out('replay')} ({sum(1 for r in doc['runs'] if r['passed'])} of "
          f"{len(doc['runs'])} runs passed)")
    for lid in stamp(ctx, doc):
        print(f"holon versions replay: {lid}: record replay field brought up to the report")
    return 0
