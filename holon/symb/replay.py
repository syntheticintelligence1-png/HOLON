"""K7: the real-code replays of the SYM member laws' witnesses (holon symb replay).

  python -m holon symb replay [--milestone M3] [--check]

Each witness holon.symb.lawrun's search finds is run on the real bundle through the bundle harness (holon.bundle.harness)
extended by replay/<M>/symb/HolonSymb.t.sol (generated here): its trace's steps from a fresh deployment, each at an
absolute block time (step kind 4) and, for a versioned witness, the member's proxy pointed at the legacy
implementation (compiled from the legacy version's sources with the pinned solc, its constructor's arguments the
deployment's immutables) and back (step kind 5).

  tau        two worlds: "original" (the prefix's steps at the trace's times, the clock of each step the walk set to 0
             at 0; x at its time) and "translated" (every time plus d). agree: the real member state before x equals
             the witness's state in the first world and its tau_d image in the second (read from the steps' storage
             writes), and x's outcomes differ as the counter-law states (their success, their return or revert data,
             a Time-sorted return word translated).
  invariant  two worlds: "versioned" (the legacy implementation for the prefix's legacy steps, the upgrade, the head
             steps) and "head" (the same steps on the head implementation). agree: the versioned world's real member
             state equals the witness's state and violates the invariant (the member's section evaluates it on that
             state), and the head world's does not.

replay/<M>/symb/<law>.json: {"replay_version", "law", "witness_sha256", "worlds": [{"name", "outcome"}], "agree",
"detail"}. --check re-runs the harness and compares. Nothing here names a target.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

REPLAY_VERSION = "holon-symb-replay/0.1"
CONTRACT = "HolonSymbTest"
HARNESS = "HolonSymb.t.sol"

SOL = """// SPDX-License-Identifier: MIT
// HOLON I92 replay harness (holon/symb/replay.py; rule K7 of tests_m3/test_sym_bundle.py). GENERATED; do not edit.
// The bundle harness (HolonBundleTest) with two more step kinds:
//   kind 4  the block time, absolute: payload = abi.encode(uint256 t)
//   kind 5  a member's implementation: payload = abi.encode(uint256 member index, bytes code): code (creation code
//           with its constructor's arguments) is deployed and the member's proxy upgraded to it by the proxy admin;
//           empty code upgrades it back to the deployment's implementation
// Each prints an env record (S ... env), so that every step has one record.
pragma solidity =0.8.24;

import {HolonBundleTest} from "./HolonBundle.t.sol";
import {ITransparentUpgradeableProxy} from
    "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";

contract HolonSymbTest is HolonBundleTest {
    address[] internal holonImpl0;

    function holonSymbStep(uint256 tid, uint256 id, bytes memory raw) internal {
        (uint8 kind, bytes memory payload) = abi.decode(raw, (uint8, bytes));
        if (kind == 4) {
            BV.warp(abi.decode(payload, (uint256)));
            BV.startStateDiffRecording();
            envRecord(tid, id, BV.stopAndReturnStateDiff());
        } else if (kind == 5) {
            (uint256 mi, bytes memory code) = abi.decode(payload, (uint256, bytes));
            address impl = holonImpl0[mi];
            if (code.length > 0) {
                assembly {
                    impl := create(0, add(code, 32), mload(code))
                }
                require(impl != address(0), "HolonSymb: the implementation's creation failed");
            }
            BV.startStateDiffRecording();
            BV.prank(PROXY_ADMIN);
            ITransparentUpgradeableProxy(payable(members[mi])).upgradeTo(impl);
            envRecord(tid, id, BV.stopAndReturnStateDiff());
        } else {
            holonStep(tid, id, raw);
        }
    }

    function test_symb() public {
        BV.pauseGasMetering();
        string memory js = BV.readFile(BV.envString("HOLON_STEPS_IN"));
        holonOut = BV.envString("HOLON_STEPS_OUT");
        uint256[] memory lens = BV.parseJsonUintArray(js, ".lens");
        bytes[] memory steps = BV.parseJsonBytesArray(js, ".steps");
        uint256[] memory init = BV.parseJsonUintArray(js, ".init");
        address[] memory w = BV.parseJsonAddressArray(js, ".watch");
        for (uint256 i = 0; i < w.length; i++) watched.push(w[i]);
        uint256 p = 0;
        for (uint256 tid = 0; tid < lens.length; tid++) {
            uint256 snap0 = BV.snapshotState();
            holonBegin(tid, init);
            delete holonImpl0;
            for (uint256 i = 0; i < members.length; i++) {
                holonImpl0.push(address(uint160(uint256(BV.load(members[i], EIP1967_IMPLEMENTATION)))));
            }
            for (uint256 si = 0; si < lens[tid]; si++) holonSymbStep(tid, si, steps[p + si]);
            p += lens[tid];
            holonLine(string.concat("E ", dec(tid), " ", dec(lens[tid])));
            BV.revertToState(snap0);
            BV.deleteStateSnapshot(snap0);
        }
        holonLine(string.concat("DONE 0 ", dec(lens.length)));
    }
}
"""


def _enc(values: list, types: list) -> bytes:
    from ..bundle.harness import _enc as e
    return e(values, types)


def clock_step(t: int) -> bytes:
    return _enc([4, _enc([t], ["uint256"])], ["uint8", "bytes"])


def impl_step(mi: int, code: bytes) -> bytes:
    return _enc([5, _enc([mi, code], ["uint256", "bytes"])], ["uint8", "bytes"])


# ------------------------------------------------------------------------------------------------ the legacy build
def legacy_creation(sctx, drec: dict) -> bytes:
    """The legacy implementation's creation code (the legacy sidecar's sources, the pinned solc and the sidecar's
    settings) followed by its constructor's arguments: each constructor parameter the constructor assigns to an
    immutable, valued as the deployment's immutable of that name."""
    from ..bundle import extract as BX
    from ..frontends.solidity import compile as comp
    from ..extracted_eval import abi_encode, parse_types
    lg = sctx.side["legacy"]
    member = lg["member"]
    side = json.loads((sctx.root / sctx.out("legacy", "sidecars", f"{member}.json")).read_text(encoding="utf-8"))
    cfg = sctx.bundle.cfg
    solc, _sha, _v = comp.check_solc(cfg, side["compiler"]["version"])
    src = Path(os.path.abspath(BX.source_for(sctx.bundle, lg["commit"])))
    settings = dict(side["compiler"].get("settings") or {})
    settings["outputSelection"] = {"*": {"*": ["evm.bytecode.object", "abi"], "": ["ast"]}}
    sources = {u: {"content": (src / u).read_text(encoding="utf-8")} for u in side["sources"]}
    cmd = [solc, "--standard-json", "--base-path", "."]
    deps = (cfg.get("replay") or {}).get("sol_deps")
    if deps and (Path(deps) / "node_modules").is_dir():
        cmd += ["--include-path", str(Path(deps) / "node_modules")]
    p = subprocess.run(cmd, input=json.dumps({"language": "Solidity", "sources": sources, "settings": settings},
                                             sort_keys=True), capture_output=True, text=True, timeout=1800, cwd=str(src))
    out = json.loads(p.stdout)
    errs = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    if errs:
        raise ValueError("the legacy build failed: " + "; ".join(e.get("message", "") for e in errs)[:1500])
    contract = sctx.side["members"][member]["contract"]
    unit = next(u for u in side["sources"] if contract in (out["contracts"].get(u) or {}))
    c = out["contracts"][unit][contract]
    code = bytes.fromhex(c["evm"]["bytecode"]["object"])
    ctor = next((x for x in c["abi"] if x.get("type") == "constructor"), {"inputs": []})
    assigns = {}

    def walk(n, in_ctor=False):
        if isinstance(n, dict):
            if n.get("nodeType") == "FunctionDefinition":
                in_ctor = n.get("kind") == "constructor"
            if in_ctor and n.get("nodeType") == "Assignment":
                lhs, rhs = n.get("leftHandSide") or {}, n.get("rightHandSide") or {}
                if lhs.get("nodeType") == "Identifier" and rhs.get("nodeType") == "Identifier":
                    assigns[rhs["name"]] = lhs["name"]
            for v in n.values():
                walk(v, in_ctor)
        elif isinstance(n, list):
            for v in n:
                walk(v, in_ctor)
    walk(out["sources"][unit]["ast"])
    imm = drec["members"][member].get("immutables") or {}
    args = []
    for inp in ctor["inputs"]:
        name = assigns.get(inp["name"])
        if name not in imm:
            raise ValueError(f"the legacy constructor's {inp['name']} assigns no deployment immutable")
        args.append(int(imm[name], 16))
    return code + abi_encode(args, parse_types(",".join(i["type"] for i in ctor["inputs"])))


# ------------------------------------------------------------------------------------------------ the runs
def _project(sctx, work: Path, tc: dict) -> Path:
    from ..bundle import harness as H
    from ..replay_fragments import forge_build, harness_project
    rel = f"replay/{sctx.milestone}/symb/{HARNESS}"
    p = sctx.root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.is_file() or p.read_text(encoding="utf-8") != SOL:
        p.write_text(SOL, encoding="utf-8")
    binding = {"project": {"kind": "checkout", "foundry_dir": "contracts", "drop": ["mock", "test"]},
               "harness": {"files": H.harness_files(sctx.bundle) + [rel]}}
    proj = harness_project(binding, work, sctx.root, Path(sctx.bundle.source_repo()), tc)
    forge_build(proj, tc)
    return proj


def run_worlds(proj: Path, tc: dict, init: list, watch: list, worlds: list) -> list:
    """Run each world (a list of raw steps) from a fresh deployment; the parsed traces."""
    from ..bundle.harness import parse
    fin, fout = proj / "holon_symb.json", proj / "holon_symb.out"
    fin.write_text(json.dumps({"lens": [len(w) for w in worlds], "steps": ["0x" + s.hex() for w in worlds for s in w],
                               "init": init, "watch": watch}))
    fout.unlink(missing_ok=True)
    cmd = [tc["forge"], "test", "--match-contract", f"^{CONTRACT}$", "--match-test", "^test_symb\\(\\)$", "--offline",
           "--use", tc["solc"]]
    env = {**os.environ, "HOLON_STEPS_IN": fin.name, "HOLON_STEPS_OUT": fout.name}
    p = subprocess.run(cmd, cwd=proj, env=env, capture_output=True, text=True, timeout=3600)
    text = fout.read_text() if fout.exists() else ""
    if p.returncode != 0 or not text.rstrip().endswith(f"DONE 0 {len(worlds)}"):
        raise RuntimeError(f"the replay harness failed (exit {p.returncode}): {(p.stdout + p.stderr)[-3000:]}")
    return parse(text)


def _member_state(tr, mi: int) -> dict:
    st: dict = {}
    for r in ([tr.deploy] if tr.deploy else []) + tr.steps:
        for m, slot, val, reverted in r.writes:
            if m == mi and not reverted:
                st[slot] = val
    return st


def _upto(tr, n: int, mi: int) -> dict:
    st: dict = {}
    for r in ([tr.deploy] if tr.deploy else []) + tr.steps[:n]:
        for m, slot, val, reverted in r.writes:
            if m == mi and not reverted:
                st[slot] = val
    return st


def _model_state(v) -> dict:
    """{slot: word} of a model state value (the evaluator's HSt)."""
    out = {}
    for kw in (v.get("f") or {}).get("sl") or []:
        f = kw["f"]
        out[int(f["k"], 16)] = int(f["v"], 16)
    return out


def _same(a: dict, b: dict) -> bool:
    return all(a.get(k, 0) == b.get(k, 0) for k in set(a) | set(b))


def _hst(st: dict) -> dict:
    from ..bundle.lawrun import h32
    return {"$r": "HSt", "f": {"sl": [{"$r": "KW", "f": {"k": {"$w": h32(k)}, "v": {"$w": h32(v)}}}
                                      for k, v in sorted(st.items())]}}


def build(sctx, log=print) -> dict:
    """{path: bytes}: the harness and each witness's replay document."""
    from ..bundle import harness as H
    from ..bundle import render
    from ..bundle.lawrun import corpus_run, h32
    from .lawrun import D, Decider
    root = sctx.root
    d = Decider(root, sctx.milestone, root / "results" / sctx.milestone, root / "gen" / sctx.milestone, log=log)
    files = {f"replay/{sctx.milestone}/symb/{HARNESS}": SOL.encode("utf-8")}
    try:
        b = sctx.bundle
        drec, trs = corpus_run(b, 4, log)
        corpus = b.load(b.out("corpus"))
        by_id = {t["id"]: (t, r) for t, r in zip(corpus["traces"], trs)}
        names = [m["name"] for m in b.members()]
        todo = [(lid, d.witness(lid)[0]) for lid in sorted(d.entries) if d.index[lid]["kind"] in ("tau", "versioned")]
        todo = [(lid, w) for lid, w in todo if w is not None]
        if not todo:
            return files
        tc = H.toolchain(b)
        with tempfile.TemporaryDirectory(prefix="holon-symb-replay-") as td:
            proj = _project(sctx, Path(td), tc)
            dep = H.deployment(proj, tc, b, log)
            enc = H.Encoder(b, dep)
            watch = sorted(set(H.watch_list(b)) | {dep.named["verifier"], dep.named["harness"]})
            legacy = None
            for lid, w in todo:
                e = d.index[lid]
                mi = names.index(e["member"])
                tr, rec = by_id[w.trace["id"]]
                ts = [s.timestamp for s in rec.steps]

                def raw(k, st):
                    if "call" in st:
                        return enc.call(st["call"], 0)
                    return enc.step(st)
                if e["kind"] == "tau":
                    xk = w.frame["k"]
                    worlds = []
                    for shift in (0, D):
                        steps = []
                        for k, st in enumerate(tr["steps"][:xk]):
                            steps += [clock_step((0 if k in w.zeroed else ts[k]) + shift), raw(k, st)]
                        steps.append(clock_step(ts[xk] + shift))
                        if w.frame["top"]:
                            steps.append(raw(xk, tr["steps"][xk]))
                        else:   # a view's frame inside its step: a direct call at the step's time
                            c = {"caller": w.frame["caller"], "value": 0, "to": e["member"], "fn": "", "args": []}
                            payload = _enc([c["caller"], 0, 0, enc.member_addr[e["member"]],
                                            bytes.fromhex(w.frame["data"][2:])],
                                           ["address", "uint256", "uint256", "address", "bytes"])
                            steps.append(_enc([2, payload], ["uint8", "bytes"]))
                        worlds.append(steps)
                    out = run_worlds(proj, tc, H.init_values(b), watch, worlds)
                    doc = judge_tau(d, lid, e, w, out, mi, h32)
                else:
                    if legacy is None:
                        legacy = legacy_creation(sctx, drec)
                    last_l = max(f["k"] for f, _a, _s in w.chain)
                    last = max([last_l] + [f["k"] for f, _a, _s in w.head])
                    worlds = []
                    for versioned in (True, False):
                        steps = [impl_step(mi, legacy)] if versioned else []
                        for k, st in enumerate(tr["steps"][:last + 1]):
                            steps += [clock_step(ts[k]), raw(k, st)]
                            if versioned and k == last_l:
                                steps.append(impl_step(mi, b""))
                        if not versioned:
                            pass
                        worlds.append(steps)
                    out = run_worlds(proj, tc, H.init_values(b), watch, worlds)
                    doc = judge_inv(d, lid, e, w, out, mi)
                doc.update({"replay_version": REPLAY_VERSION, "law": lid, "witness_sha256": w.sha256(),
                            "trace": w.trace["id"]})
                files[f"replay/{sctx.milestone}/symb/{lid}.json"] = render(doc)
                log(f"{lid}: agree {doc['agree']}")
    finally:
        d.close()
    return files


def _outcome(r) -> dict:
    return {"ok": r.ok, "ret": r.ret, "timestamp": r.timestamp, "logs": len(r.logs)}


def judge_tau(d, lid: str, e: dict, w, out: list, mi: int, h32) -> dict:
    lm = d.machine(e["member"])
    ref = d._replay_chain(lm, w)
    kh = dict(w.kh)
    want_a = _model_state(lm.fn("C_sy_tst", lambda t: [t, {"$ref": ref}, {"$w": h32(0)}], kh))
    want_b = _model_state(lm.fn("C_sy_tst", lambda t: [t, {"$ref": ref}, {"$w": h32(1)}], kh))
    a, b = out
    n = len(a.steps) - 1
    sa, sb = _upto(a, n, mi), _upto(b, n, mi)
    xa, xb = a.steps[-1], b.steps[-1]
    pre_ok = _same(sa, want_a) and _same(sb, want_b)
    tr_ret = e.get("time_return")
    if xa.ok != xb.ok:
        differ, how = True, f"x succeeds in one world only (original {xa.ok}, translated {xb.ok})"
    elif tr_ret and xa.ok and len(xa.ret) == 66 and len(xb.ret) == 66:
        # K5: a Time-sorted return word is compared translated: the original's plus d against the translated's
        want = (int(xa.ret, 16) + 1) % (1 << 256)
        differ = int(xb.ret, 16) != want
        how = (f"x's Time-sorted return word: the original's ({int(xa.ret, 16)}) plus d is {want}, the translated "
               f"run's is {int(xb.ret, 16)}")
    elif xa.ret != xb.ret:
        differ, how = True, (f"x's {'return' if xa.ok else 'revert'} data differ: original {xa.ret[:74]}, "
                             f"translated {xb.ret[:74]}")
    elif len(xa.logs) != len(xb.logs) or any(x[2] != y[2] for x, y in zip(xa.logs, xb.logs)):
        differ, how = True, "x's logs differ"
    else:
        differ, how = False, "x's outcomes agree up to the translation"
    detail = (f"{how}; the real member state before x is the witness's (original) and its tau_d image (translated)"
              if pre_ok else f"{how}; but the real member state before x is not the witness's: the real prefix "
                             "reached another state, so the run does not replay the witness")
    return {"worlds": [{"name": "original", "outcome": _outcome(xa)}, {"name": "translated", "outcome": _outcome(xb)}],
            "agree": bool(differ and pre_ok), "detail": detail, "d": 1}


def judge_inv(d, lid: str, e: dict, w, out: list, mi: int) -> dict:
    from .lawrun import as_input
    hm = d.machine(e["member"])
    kh = dict(w.kh)
    if w.head:
        want = _model_state(w.head[-1][2])
    else:
        want = _model_state(w.chain[-1][2])
    v, h = out
    sv, sh = _member_state(v, mi), _member_state(h, mi)

    def ev(fn, st):
        return bool(hm.fn(f"C_{fn}", lambda t: [as_input(_hst(st)), t], kh))
    iv, ih = ev(e["ok"], sv), ev(e["ok"], sh)
    gv, rv = ev(e["g"], sv), ev(e["rne"], sv)
    same = _same(sv, want)
    agree = bool(same and not iv and ih)
    detail = (f"versioned world: the real member state {'is' if same else 'is not'} the witness's; there the view's "
              f"other conjunct {'holds' if gv else 'fails'} and the register {'differs from' if rv else 'equals'} its "
              f"constant (invariant {'holds' if iv else 'fails'}); head world: the invariant "
              f"{'holds' if ih else 'fails'}")
    return {"worlds": [{"name": "versioned", "outcome": {"invariant": iv, "conjunct": gv, "register_differs": rv,
                                                         "steps_ok": [s.ok for s in v.steps]}},
                       {"name": "head", "outcome": {"invariant": ih, "steps_ok": [s.ok for s in h.steps]}}],
            "agree": agree, "detail": detail}


def main(sctx, check: bool, log) -> int:
    from ..bundle import write_or_check
    return write_or_check(sctx.bundle, build(sctx, log), check, owned=[f"replay/{sctx.milestone}/symb"], log=log)
