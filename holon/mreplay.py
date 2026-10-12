"""`holon replay --milestone M1`: replay state-machine witnesses on the real Rollup (whitepaper §8.7, §9.6, §10.9).

Two corpora run through one generic Foundry harness (replay/M1/solidity/HolonTraceReplay.t.sol),
which deploys the real Rollup and L1MessageQueue at the pinned commit for every trace:

  witnesses   every REFUTED law's witness, linearised into the concrete traces its claim compares
              (e.g. an undo law gives  p ++ [do, undo] ++ q  and  p ++ q);
  refinement  a seeded random corpus of traces (successful and failing actions mixed).

For every step the model's observation (ok / revert reason) is compared with the real outcome.
Each law entry has sides (I4): the on-chain trace replay ("solidity"), a Go side for laws over the
Go BatchData machine ("go"), and a Go consumer side ("go_consumer", holon.consumers) for subforms
whose obstruction shows only where an off-chain reader consumes what the chain committed. A side
"passed" iff the real code agreed with the model on every step it ran; obstruction_observed is set
separately from the real code's output (two-sided claims: the continuations' outcomes differ;
one-sided: the symptom appears; ghost tag: the committed v2 header carries the v1 writer's blob
hash; same commitment: equal committedBatches). The law-level verdict (status, obstruction_reproduced)
is the conjunction of its sides. Disagreements are model defects and are reported loudly.

The same harness also replays the M0 codec witnesses on the commit path (m0_commit_sides).
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
import subprocess
from pathlib import Path

from . import facts as F
from .mpipeline import CompiledMachine, _act_val
from .evidence import MODEL_ONLY, OBSERVED, own_go
from .replay import _holon_lines, _run, _sol_deps, check_checkout, witness_sha256  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
OPS = {"commitBatch": 1, "commitState": 2, "commitBatchWithProof": 3, "revertBatch": 4, "challengeState": 5,
       "proveState": 6, "finalizeBatch": 7, "setPause": 8, "sendMessage": 9, "wait": 10, "@legacy_eta2": 11}
WIDTH = 13
CHUNK = 25
LINE = re.compile(r"HOLON (\d+) (\d+) (ok|rev) ?(.*)")
HDR = re.compile(r"HOLON-HDR (\d+) (g|\d+) (\d+) (0x[0-9a-fA-F]*) (0x[0-9a-fA-F]{64}) (0x[0-9a-fA-F]{64})")
MISMATCH = re.compile(r"HOLON harness-mismatch (\d+) (\d+)")


# ---------------------------------------------------------------- traces
def encode_step(a: dict) -> list[int]:
    op = OPS[a["op"]]
    w = [0] * WIDTH
    w[0] = op
    if a["op"] in ("commitBatch", "commitState", "commitBatchWithProof"):
        bl = a["blobs"]
        w[1:12] = [a["who"], a["ver"], a["parent"], a["n"], a["lbn"], a["prev"], a["post"], len(bl),
                   bl[0] if bl else 0, bl[1] if len(bl) > 1 else 0, a.get("proof", 0)]
    elif a["op"] == "revertBatch":
        w[1:4] = [a["who"], a["idx"], a["count"]]
    elif a["op"] == "challengeState":
        w[1:4] = [a["who"], a["idx"], a["value"]]
    elif a["op"] == "proveState":
        w[1:4] = [a["who"], a["idx"], a["proof"]]
    elif a["op"] == "finalizeBatch":
        w[1:3] = [a["who"], a["idx"]]
    elif a["op"] == "setPause":
        w[1:3] = [a["who"], 1 if a["status"] else 0]
    elif a["op"] == "sendMessage":
        w[1] = a["who"]
    elif a["op"] == "wait":
        w[1] = a["dt"]
    elif a["op"] == "@legacy_eta2":
        w[1] = a["root"]
    return w


def model_logs(cm: CompiledMachine, traces: list[list[dict]]) -> list[list]:
    """Per trace, the model observation of each step (None for pseudo-steps such as migrations)."""
    calls = []
    for tr in traces:
        expr = {"fn": "s0", "args": []}
        for a in tr:
            if a["op"] == "@legacy_eta2":
                expr = {"fn": "mig_eta2", "args": [{"fn": "mig_legacy", "args": [expr]}, {"val": a["root"]}]}
            else:
                expr = {"fn": "step", "args": [{"val": _act_val(cm.m, a)}, expr]}
        calls.append({"fn": "log_of", "args": [expr]})
    out = []
    for tr, log in zip(traces, cm.calls(calls)):
        log = list(reversed(log))
        it = iter(log)
        out.append([None if a["op"].startswith("@") else next(it) for a in tr])
    return out


def linearise(law: dict, w: dict) -> list[dict]:
    """The concrete traces a REFUTED law's claim compares, built from its witness."""
    st = law["statement"]

    def trace_of(t) -> list[dict]:
        if "var" in t:
            return list(w[t["var"]])
        if "trace" in t:
            return [act_of(a) for a in t["trace"]]
        if "cat" in t:
            return trace_of(t["cat"][0]) + trace_of(t["cat"][1])
        raise ValueError(t)

    def act_of(t) -> dict:
        if "var" in t:
            return dict(w[t["var"]])
        out = {"op": t["act"]}
        for k, x in t["args"].items():
            out[k] = val(x)
        return out

    def val(x):
        if "nat" in x:
            return x["nat"]
        if "bool" in x:
            return x["bool"]
        if "nats" in x:
            return x["nats"]
        if "var" in x:
            return w[x["var"]]
        if "plus" in x:
            raise ValueError("plus")  # resolved through the witness binder instead
        raise ValueError(x)

    def state_of(t) -> list[dict]:
        if "s0" in t:
            return []
        if "run" in t:
            return state_of(t["from"]) + trace_of(t["run"])
        if "step" in t:
            return state_of(t["from"]) + [act_of(t["step"])]
        if "mig" in t:
            if t["mig"] == "eta2":
                inner = t["of"]
                assert inner.get("mig") == "legacy"
                pre = state_of(inner["of"])
                return pre + [{"op": "@legacy_eta2", "root": None}]
        raise ValueError(t)

    def side(t) -> dict:
        if "obs" in t:
            return {"trace": state_of(t["from"]) + trace_of(t["obs"]), "split": len(state_of(t["from"]))}
        if "fn" in t and t["fn"] == "no_code":
            return {"trace": trace_of(t["args"][0]["obs"]), "split": 0, "symptom": ("code", t["args"][1]["nat"])}
        if "obsv" in t:
            return {"trace": state_of(t["of"]), "split": 0, "symptom": ("observer", t["obsv"])}
        if "fn" in t and t["fn"].endswith("_of"):
            return None
        raise ValueError(t)

    c = st["claim"]["eq"]
    out = []
    if all("obs" in x for x in c):
        out = [{"label": "lhs", **side(c[0])}, {"label": "rhs", **side(c[1])}]
        out[0]["kind"] = "differ"
    elif "fn" in c[0] and c[0]["fn"] == "no_code":
        out = [{"label": "trace", **side(c[0]), "kind": "symptom"}]
    elif "obsv" in c[0]:
        out = [{"label": "trace", **side(c[0]), "kind": "accepted"}]
    elif "fn" in c[0] and c[0]["fn"] == "blobs_of":
        # FACT: the two commits from the same prefix; the commitment (committedBatches) must coincide
        prem = [p["eq"][0] for p in st["assume"] if "obsv" in p["eq"][0] and p["eq"][0]["obsv"] == "new_hdr"]
        s1 = state_of(prem[0]["of"])
        p_assume = [p for p in st["assume"] if "obsv" in p["eq"][0] and p["eq"][0]["obsv"] == "new_hdr"][0]
        s2 = state_of(p_assume["eq"][1]["of"])
        out = [{"label": "c1", "trace": s1, "split": len(s1) - 1, "kind": "same_commitment"},
               {"label": "c2", "trace": s2, "split": len(s2) - 1}]
    else:
        raise ValueError("cannot linearise claim")
    return out


def fill_eta2_root(cm: CompiledMachine, runs: list[dict]) -> None:
    """The eta2 input is the native csr at LCI: evaluate it on the model for the prefix."""
    for r in runs:
        for i, a in enumerate(r["trace"]):
            if a["op"] == "@legacy_eta2" and a["root"] is None:
                pre = r["trace"][:i]
                expr = {"fn": "s0", "args": []}
                for b in pre:
                    expr = {"fn": "step", "args": [{"val": _act_val(cm.m, b)}, expr]}
                a["root"] = cm.calls([{"fn": "csr_last", "args": [expr]}])[0]


def random_corpus(cm: CompiledMachine, n: int, seed: int, length: tuple = (4, 12)) -> list[list[dict]]:
    """Seeded random walks over the explorer's policy, with perturbed indices and principals."""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        tr: list[dict] = []
        L = rng.randint(*length)
        for _ in range(L):
            cands = policy_at(cm, tr)
            a = dict(rng.choice(cands))
            r = rng.random()
            if r < 0.1 and "who" in a:
                a["who"] = rng.choice([1, 2, 3, 4, 5])
            elif r < 0.2 and "idx" in a:
                a["idx"] = max(0, a["idx"] + rng.choice([-1, 1, 2]))
            elif r < 0.25 and "parent" in a:
                a["parent"] = max(0, a["parent"] + rng.choice([-1, 1]))
            tr.append(a)
        out.append(tr)
    return out


_POLICY_CACHE: dict = {}


def policy_at(cm: CompiledMachine, tr: list[dict]) -> list[dict]:
    key = json.dumps(tr, sort_keys=True)
    if key not in _POLICY_CACHE:
        p = subprocess.run(["node", str(ROOT / "holon" / "js" / "policy.mjs")],
                           input=json.dumps({"module": str(cm.artifact), "facts": cm.facts, "hints": cm.hints(), "trace": tr}),
                           capture_output=True, text=True, timeout=120)
        if p.returncode != 0:
            raise RuntimeError(p.stderr[-1500:])
        _POLICY_CACHE[key] = json.loads(p.stdout)
    return _POLICY_CACHE[key]


# ---------------------------------------------------------------- harness
def run_forge(morph: Path, work: Path, traces: list[list[dict]], facts: dict, forge: str, solc: str | None,
              hdrs: dict | None = None) -> tuple[dict, str, int]:
    """Run the traces; return the per-step outcomes. When `hdrs` is a dict, it is filled with the
    headers the harness logged: (trace, step or "g") -> {index, header, committed, bvh, mismatch}."""
    proj = work / "solidity"
    proj.mkdir(parents=True, exist_ok=True)
    # always a fresh copy of the pinned checkout: a stale scratch copy must never be compiled
    shutil.rmtree(proj / "contracts", ignore_errors=True)
    shutil.copytree(morph / "contracts" / "contracts", proj / "contracts")
    for d in ("mock", "test"):
        shutil.rmtree(proj / "contracts" / d, ignore_errors=True)
    for f in ("foundry.toml", "remappings.txt"):
        shutil.copy(morph / "contracts" / f, proj / f)
    _sol_deps(proj)
    (proj / "test").mkdir(exist_ok=True)
    shutil.copy(ROOT / "replay" / "M1" / "solidity" / "HolonTraceReplay.t.sol", proj / "test")
    init = facts["initial"]
    data = [init["F"], init["W"], init["D"], init["t"], init["fsr"][0], len(traces)]
    for tr in traces:
        data.append(len(tr))
        for a in tr:
            data += encode_step(a)
    (proj / "holon_traces.json").write_text(json.dumps({"data": data}))
    cmd = [forge, "test", "--match-contract", "HolonTraceReplay", "-vv", "--offline"] + (["--use", solc] if solc else [])
    res: dict = {}
    out_all, code = "", 0
    for lo in range(0, len(traces), CHUNK):
        c, out = _run(cmd, proj, {"HOLON_TRACES": "holon_traces.json", "HOLON_LO": str(lo), "HOLON_HI": str(lo + CHUNK)},
                      timeout=7200)
        code = code or c
        out_all += out
        for m in LINE.finditer(out):
            res[(int(m.group(1)), int(m.group(2)))] = (m.group(3), m.group(4).strip())
    out = out_all
    if hdrs is not None:
        bad = {(int(m.group(1)), m.group(2)) for m in MISMATCH.finditer(out)}
        for m in HDR.finditer(out):
            key = (int(m.group(1)), m.group(2))
            hdrs[key] = {"index": int(m.group(3)), "header": m.group(4).lower(), "committed": m.group(5).lower(),
                         "bvh": m.group(6).lower(), "mismatch": key in bad}
    if not res:
        raise SystemExit(f"forge produced no HOLON lines (exit {code}):\n" + "\n".join(out.splitlines()[-40:]))
    if "harness-mismatch" in out:
        res["harness_mismatch"] = True
    shown = " ".join("forge" if c == forge else "<solc 0.8.24>" if c == solc else c for c in cmd)
    return res, f"HOLON_TRACES=holon_traces.json HOLON_LO=k HOLON_HI=k+{CHUNK} {shown}  # per chunk of {CHUNK} traces", code


def obs_str(facts: dict, o) -> str:
    if o is None:
        return "ok"
    if o["$"] == "O_Ok":
        return "ok"
    return "rev " + facts["reasons"][str(o["code"])]


def compare(facts: dict, model: list, real: dict, tid: int, trace: list[dict]) -> tuple[list, list]:
    agree, dis = [], []
    for i, (a, mo) in enumerate(zip(trace, model)):
        got = real.get((tid, i))
        want = obs_str(facts, mo)
        if got is None:
            dis.append({"step": i, "op": a["op"], "model": want, "real": "missing"})
            continue
        real_s = "ok" if got[0] == "ok" else "rev " + got[1]
        (agree if real_s == want else dis).append({"step": i, "op": a["op"], "model": want, "real": real_s,
                                                   **({"hash": got[1]} if got[0] == "ok" else {})})
    return agree, dis


def replay_own_go(morph: Path, work: Path, results: Path) -> tuple[dict, str]:
    """OWN laws over Go facts: run the witness on the real common/batch.BatchData."""
    ws = work / "go"
    shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True)
    for d in ("bindings", "common"):
        shutil.copytree(morph / d, ws / d, symlinks=True)
    (ws / "go.work").write_text("go 1.24.0\n\nuse (\n\t./bindings\n\t./common\n)\n")
    shutil.copy(ROOT / "replay" / "M1" / "go" / "holon_own_test.go", ws / "common" / "batch")
    shutil.copytree(results, ws / "holon_results")
    gv = subprocess.run(["go", "version"], capture_output=True, text=True).stdout.strip()
    cmd = ["go", "test", "./batch", "-run", "TestHolonOwn", "-v", "-count=1"]
    code, out = _run(cmd, ws / "common", {"HOLON_RESULTS": str(ws / "holon_results"), "HOLON_GOVERSION": gv})
    lines = _holon_lines(out)
    m = re.search(r"HOLON realistic (\w+) (.*)", out)
    if m:
        lines["realistic"] = ("passed" if m.group(1) == "true" else "failed", m.group(2))
    return lines, f"(cd common && {' '.join(cmd)})  # exit {code}; {gv}"


# ---------------------------------------------------------------- M0 on the commit path
def m0_commit_sides(morph: Path, work: Path, records: dict, laws: dict, hfacts: dict, tc: dict) -> dict[str, dict]:
    """Solidity sides of the M0 codec witnesses whose claim compares enc_sol with a Go encoder.

    The cells to observe come from the law, not from its id (holon.evidence.m0_expected_cells): the
    positions where the model's enc_sol and the claim's Go encoder give different bytes on the
    witness, each holding what enc_sol writes there under the law's pins. The M1 harness deploys the
    real Rollup, runs the witness's version as a commit from s0 and logs the header it rebuilt;
    keccak256 of that header must equal committedBatches(index), read on chain. A committed header
    that contradicts the model's cells is a model defect (status failed), not an unobserved obstruction."""
    from .evidence import CONTRADICTION, OBSERVED, m0_commit, m0_commit_trace, m0_expected_cells, ranges
    from .replay import COMMIT_PATH, solidity_kind
    targets = [lid for lid in sorted(records)
               if records[lid].get("status") == "REFUTED" and solidity_kind(laws[lid]) == COMMIT_PATH]
    if not targets:
        return {}
    reg = json.loads((ROOT / "laws" / "M1" / "REGISTRY.json").read_text())
    facts_path = ROOT / reg["facts"]
    rfacts = F.load(facts_path)
    cm = CompiledMachine.build(facts_path)
    plans = []
    for lid in targets:
        expect, go_fn, version = m0_expected_cells(laws[lid], records[lid]["witness"], hfacts)
        plans.append((lid, m0_commit_trace(rfacts, version), expect, version, go_fn))
    traces = [tr for _, tr, _, _, _ in plans]
    models = model_logs(cm, traces)
    hdrs: dict = {}
    real, command, _ = run_forge(morph, work, traces, rfacts, tc["forge"], tc["solc"], hdrs)
    out = {}
    for tid, (lid, tr, expect, version, go_fn) in enumerate(plans):
        _, dis = compare(rfacts, models[tid], real, tid, tr)
        h = hdrs.get((tid, "0"))
        step = real.get((tid, 0))
        agree = not dis and bool(step) and step[0] == "ok"
        side = {"provenance": "public_schedule", "command": command, "trace": tr}
        if h is not None:
            side.update(header=h["header"], batch_index=h["index"], committed_hash=h["committed"],
                        checked_cells=ranges(sorted(expect)))
        verdict, why = m0_commit(side, laws[lid], records[lid]["witness"], hfacts, rfacts)
        side["status"] = "passed" if agree and verdict != CONTRADICTION else "failed"
        side["obstruction_observed"] = side["status"] == "passed" and verdict == OBSERVED
        hb = _hexb(h["header"]) if h else b""
        shown = "0x" + bytes(hb[i] for i in sorted(expect) if i < len(hb)).hex() if h else "none"
        side["observed"] = (f"commitBatch(version {version}, 1 blob) from s0 on the deployed Rollup: "
                            f"{step[0] if step else 'missing'}; committed header bytes {ranges(sorted(expect))} = "
                            f"{shown}. {why}")
        out[lid] = side
    return out


# ---------------------------------------------------------------- M1
def _hexb(h: str) -> bytes:
    return bytes.fromhex(h[2:] if h.startswith("0x") else h)


def _bytes32(n: int) -> str:
    return "0x" + int(n).to_bytes(32, "big").hex()


def _header_before(hdrs: dict, tid: int, last_step: int, index: int) -> dict | None:
    """The header logged in trace `tid` for batch `index` before step `last_step` (the latest one),
    or the genesis header when index 0 has no later log."""
    logs = sorted((int(si), v) for (t, si), v in hdrs.items() if t == tid and si != "g" and int(si) < last_step
                  and v["index"] == index)
    if logs:
        return logs[-1][1]
    g = hdrs.get((tid, "g"))
    return g if g and index == 0 else None


def _solidity_side(law: dict, outs: list, real: dict, facts: dict, hdrs: dict, runs: list, command: str) -> dict:
    """The on-chain side of one M1 witness. status: the real code agreed with the model on every step
    and the logged evidence contradicts no value the witness predicts; obstruction_observed: what
    holon.evidence reads from the logged evidence (the rule G6 re-applies)."""
    from . import evidence as E
    kind = E.claim_kind(law)
    all_agree = all(not d for _, _, d, _, _ in outs) and all(real.get((t, i)) is not None
                                                            for r, _, _, _, t in outs for i in range(len(r["trace"])))
    side = {"command": command, "provenance": E.expected_provenance(law, "solidity")}
    if kind == "accepted":
        # ghost tag: the last commit's header, and the header whose commit stored its blob hash
        (r0, _, _, _, t0), = outs
        logs = sorted(((int(si), v) for (tid, si), v in hdrs.items() if tid == t0 and si != "g"), key=lambda x: x[0])
        last = logs[-1][1] if logs else None
        first = next((v for _, v in logs if last and v["index"] == last["index"] and v is not last), None)
        if last:
            side.update(header=last["header"], committed_hash=last["committed"], stored_vh=last["bvh"],
                        batch_index=last["index"])
        if first:
            side.update(v1_header=first["header"], v1_committed_hash=first["committed"])
    elif kind == "same_commitment":
        (r1, _, _, _, t1), (r2, _, _, _, t2) = outs
        h1, h2 = real.get((t1, len(r1["trace"]) - 1)), real.get((t2, len(r2["trace"]) - 1))
        side["committed_hash"] = {"c1": h1[1] if h1 and h1[0] == "ok" else None,
                                  "c2": h2[1] if h2 and h2[0] == "ok" else None}
        pidx = r1["trace"][-1]["parent"]
        p1 = _header_before(hdrs, t1, len(r1["trace"]) - 1, pidx)
        p2 = _header_before(hdrs, t2, len(r2["trace"]) - 1, r2["trace"][-1]["parent"])
        same_parent = bool(p1 and p2) and p1["header"] == p2["header"]
        side.update(parent_index=pidx, parent_header=p1["header"] if same_parent else None,
                    parent_committed_hash=p1["committed"] if same_parent else None)
    verdict, why = E.verdict(law, "solidity", side, {"traces": [
        {"label": r["label"], "split": r["split"],
         "real": [("ok" if real.get((t, i), ("?",))[0] == "ok" else "rev " + real.get((t, i), ("", "?"))[1])
                  for i in range(len(r["trace"]))]} for r, _, _, _, t in outs]}, None, None, facts)
    side["status"] = "passed" if all_agree and verdict != E.CONTRADICTION else "failed"
    side["obstruction_observed"] = side["status"] == "passed" and verdict == E.OBSERVED
    side["observed"] = why if all_agree else f"{why}; the real code disagrees with the model on some step"
    return side


def _model_only(why: str) -> dict:
    return {"status": "not_applicable", "provenance": "library_api", "obstruction_observed": False, "command": "",
            "observed": f"model-only pending replay: {why}"}


def _consumer_side(law: dict, runs: list, sol: dict, morph: Path, work: Path) -> dict:
    """The Go consumer side of a law whose claim needs one (holon.evidence.CONSUMER_KINDS). A consumer
    that cannot run is labelled model-only pending replay, never relabelled as replayed."""
    from . import consumers
    from .evidence import claim_kind
    kind = claim_kind(law)
    if kind == "accepted":
        if not (sol.get("header") and sol.get("v1_header")):
            return _model_only("the chain replay logged no ghost-tagged header pair to feed the consumer")
        side = consumers.tag_bvh_side(morph, work, sol["header"], sol["stored_vh"], sol["v1_header"])
    elif kind == "same_commitment":
        commits = {}
        for r in runs:
            a = r["trace"][-1]
            if any(b != 1 for b in a["blobs"]):  # blob id 1 is the all-zero blob (versioned hash Z)
                return _model_only(f"{r['label']}: blob ids {a['blobs']} are not the all-zero blob")
            commits[r["label"]] = {"version": a["ver"], "last_block_number": a["lbn"], "num_l1_messages": a["n"],
                                   "prev_state_root": _bytes32(a["prev"]), "post_state_root": _bytes32(a["post"]),
                                   "withdraw_root": _bytes32(0), "blobs": len(a["blobs"])}
        if not sol.get("parent_header"):
            return _model_only("no common parent header from the chain replay to feed the consumer")
        side = consumers.fact_z_side(morph, work, sol["parent_header"], commits, sol.get("parent_index"))
    else:
        raise ValueError(f"{law['law_id']}: no consumer for claim kind {kind}")
    if side["status"] == "not_run":
        return _model_only(side["observed"])
    return side


def _law_status(sides: dict) -> str:
    """passed iff every side passed or is labelled model-only pending replay, and one side passed."""
    vals = list(sides.values())
    ok = all(s["status"] == "passed" or (s["status"] == "not_applicable" and s["observed"].startswith(MODEL_ONLY))
             for s in vals)
    return "passed" if ok and any(s["status"] == "passed" for s in vals) else "failed"


def main_replay_m1(args) -> int:
    from .filter import claimed_sides
    from .replay import PIN_KEYS, morph_path, toolchain
    morph = morph_path(args)
    milestone = args.milestone
    reg = json.loads((ROOT / "laws" / milestone / "REGISTRY.json").read_text())
    facts_path = ROOT / reg["facts"]
    facts = F.load(facts_path)
    sha = check_checkout(morph, facts["target"]["commit"])
    tc = toolchain(args)
    work = Path(args.work or ROOT / "build" / "replay_m1").resolve()
    shutil.rmtree(work / "go", ignore_errors=True)
    results = ROOT / "results" / milestone
    cm = CompiledMachine.build(facts_path)
    laws = {p.stem: json.loads(p.read_text()) for p in (ROOT / "laws" / milestone).glob("L_*.json")}
    records = {p.stem: json.loads(p.read_text()) for p in results.glob("L_*.json")}
    # witness corpus
    plan = []
    go_laws = []
    for lid in sorted(records):
        r = records[lid]
        if r["status"] != "REFUTED":
            continue
        if claimed_sides(laws[lid], reg["facts_sha256"]) == {"go"}:
            go_laws.append(lid)  # Go-side machine (OWN): replayed through go test below
            continue
        runs = linearise(laws[lid], r["witness"])
        fill_eta2_root(cm, runs)
        plan.append((lid, runs))
    corpus = random_corpus(cm, args.corpus, seed=20261011)
    traces = [run["trace"] for _, runs in plan for run in runs] + corpus
    models = model_logs(cm, traces)
    hdrs: dict = {}
    real, command, code = run_forge(morph, work, traces, facts, tc["forge"], tc["solc"], hdrs)
    gv = subprocess.run(["go", "version"], capture_output=True, text=True).stdout.strip()
    report = {"morph_commit": sha, "command": command, "harness_mismatch": bool(real.pop("harness_mismatch", False)),
              "laws": {}, "witness_sha256": {},
              "toolchain": {**{k: tc[k] for k in PIN_KEYS}, "go_version": gv}}
    tid = 0
    for lid, runs in plan:
        entry = {"traces": []}
        outs = []
        for run in runs:
            ag, dis = compare(facts, models[tid], real, tid, run["trace"])
            outs.append((run, ag, dis, models[tid], tid))
            entry["traces"].append({"label": run["label"], "trace": run["trace"], "split": run["split"],
                                    "agree": len(ag), "disagree": dis,
                                    "real": [("ok" if real.get((tid, i), ("?",))[0] == "ok" else "rev " + real.get((tid, i), ("", "?"))[1])
                                             for i in range(len(run["trace"]))]})
            tid += 1
        sides = {"solidity": _solidity_side(laws[lid], outs, real, facts, hdrs, runs, command)}
        if "go_consumer" in claimed_sides(laws[lid], reg["facts_sha256"]):
            sides["go_consumer"] = _consumer_side(laws[lid], runs, sides["solidity"], morph, work / "consumers")
        entry["sides"] = sides
        entry["status"] = _law_status(sides)
        entry["obstruction_reproduced"] = all(s["obstruction_observed"] for s in sides.values())
        entry["observed"] = "; ".join(f"{k}: {s['observed']}" for k, s in sorted(sides.items())) if len(sides) > 1 \
            else sides["solidity"]["observed"]
        report["laws"][lid] = entry
        report["witness_sha256"][lid] = witness_sha256(records[lid]["witness"])
    for lid in go_laws:
        lines, gcmd = replay_own_go(morph, work, results)
        st, obs = lines.get(lid, ("failed", "no result from go test"))
        realistic = lines.get("realistic")
        obs = obs + (f"; realistic 60-byte contexts: {realistic[0]} ({realistic[1]})" if realistic else "")
        # the Go harness prints changed=true when the held view's bytes changed across Append
        side = {"status": st, "provenance": "library_api", "command": gcmd, "observed": obs}
        side["obstruction_observed"] = st == "passed" and own_go(side)[0] == OBSERVED
        report["laws"][lid] = {"status": st, "obstruction_reproduced": side["obstruction_observed"], "command": gcmd,
                               "observed": obs, "traces": [], "sides": {"go": side}}
        report["witness_sha256"][lid] = witness_sha256(records[lid]["witness"])
    # refinement corpus
    per_op: dict = {}
    disagreements = []
    for tr in corpus:
        ag, dis = compare(facts, models[tid], real, tid, tr)
        for x in ag:
            per_op.setdefault(x["op"], {"agree": 0, "disagree": 0})["agree"] += 1
        for x in dis:
            per_op.setdefault(x["op"], {"agree": 0, "disagree": 0})["disagree"] += 1
            disagreements.append({"trace": tid, **x, "prefix": tr[: x["step"] + 1]})
        tid += 1
    report["refinement"] = {"traces": len(corpus), "steps": sum(len(t) for t in corpus), "per_action": per_op,
                            "disagreements": disagreements[:50], "n_disagreements": len(disagreements), "seed": 20261011}
    out = ROOT / "replay" / milestone / "report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    from .replay import stamp_records
    stamp_records(milestone, results, report)
    for lid, e in report["laws"].items():
        print(f"{lid:20s} {e['status']:7s} reproduced={e['obstruction_reproduced']}  "
              + "  ".join(f"{k}={s['status']}/{s['provenance']}/observed={s['obstruction_observed']}"
                          for k, s in sorted(e["sides"].items())))
    rf = report["refinement"]
    print(f"refinement corpus: {rf['traces']} traces, {rf['steps']} steps, {rf['n_disagreements']} disagreements")
    defects = [l for l, e in report["laws"].items() if e["status"] != "passed"]
    unseen = [l for l, e in report["laws"].items() if e["status"] == "passed" and not e["obstruction_reproduced"]]
    bad = defects + unseen
    model_only = [f"{l}/{k}" for l, e in report["laws"].items() for k, s in e["sides"].items()
                  if s["status"] == "not_applicable"]
    if model_only:
        print(f"model-only pending replay: {model_only}")
    if defects or rf["n_disagreements"] or report["harness_mismatch"]:
        print(f"MODEL DEFECT: {defects}; refinement disagreements: {rf['n_disagreements']}; "
              f"harness mismatch: {report['harness_mismatch']}")
    if unseen:
        print(f"NOT REPRODUCED (replay agrees with the model, but the obstruction did not show on every side): {unseen}")
    if bad or rf["n_disagreements"] or report["harness_mismatch"]:
        return 1
    return 0
