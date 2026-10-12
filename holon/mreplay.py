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

`holon replay --milestone M2` (I15, main_replay_m2): every REFUTED per-entry witness of a SORT-site law (prefix ++
[action]) through the same harness, compared step by step with the M2 model (its oracle parameters answered by their
sidecar instances), and its last step replayed alone by replay/M2/solidity/HolonLastStep.t.sol under the Foundry
debugger, where locate_panic finds the Panic's source line (panic_site); and the refinement corpus, the M1 rule with
its seed and size, on the M2 model.
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
WIDTH = 13       # cells per step row: replay/M1/solidity/HolonTraceReplay.t.sol reads this many per step
LIST_CELLS = 2   # a List<Nat> input is its length, then its first LIST_CELLS elements (the harness's blob slots)
CHUNK = 25
LINE = re.compile(r"HOLON (\d+) (\d+) (ok|rev) ?(.*)")
HDR = re.compile(r"HOLON-HDR (\d+) (g|\d+) (\d+) (0x[0-9a-fA-F]*) (0x[0-9a-fA-F]{64}) (0x[0-9a-fA-F]{64})")
MISMATCH = re.compile(r"HOLON harness-mismatch (\d+) (\d+)")


# ---------------------------------------------------------------- traces
def op_table(facts: dict) -> dict[str, int]:
    """The harness op codes, generated from the facts (audit M2/1 F-M2-16; was a hand table): action i, in facts
    order, is op i + 1; the deployment-history pseudo-step, every migration in facts order applied in that order
    (`@legacy_eta2` for the Rollup), is the next one. The harness decodes the same numbering."""
    ops = {a["name"]: i + 1 for i, a in enumerate(facts["actions"])}
    migs = list(facts.get("migrations", {}))
    if migs:
        ops[history_op(facts)] = len(ops) + 1
    return ops


def history_op(facts: dict) -> str:
    """The pseudo-step that applies every migration of the facts, in facts order."""
    return "@" + "_".join(facts.get("migrations", {}))


def _cells(ty: str, v) -> list[int]:
    if ty == "Nat":
        return [int(v)]
    if ty == "Bool":
        return [1 if v else 0]
    if ty == "List<Nat>":
        xs = [int(x) for x in v]
        return [len(xs)] + [xs[i] if i < len(xs) else 0 for i in range(LIST_CELLS)]
    raise ValueError(f"no harness encoding for an input of type {ty}")


def encode_step(a: dict, facts: dict) -> list[int]:
    """One harness row, generated from the facts: the op code, then the step's inputs in facts order (Nat as is, Bool
    as 1/0, List<Nat> as its length and first LIST_CELLS elements), zero-padded to WIDTH. A pseudo-step's inputs are
    its migrations' inputs, in facts order."""
    ops = op_table(facts)
    if a["op"].startswith("@"):
        if a["op"] != history_op(facts):
            raise ValueError(f"unknown pseudo-step {a['op']}")
        ins = [x for mg in facts.get("migrations", {}).values() for x in mg.get("inputs", [])]
    else:
        ins = next(x for x in facts["actions"] if x["name"] == a["op"])["inputs"]
    row = [ops[a["op"]]]
    for n, ty in ins:
        row += _cells(ty, a[n])
    if len(row) > WIDTH:
        raise ValueError(f"{a['op']}: {len(row)} cells exceed the harness row width {WIDTH}")
    return row + [0] * (WIDTH - len(row))


def model_logs(cm: CompiledMachine, traces: list[list[dict]]) -> list[list]:
    """Per trace, the model observation of each step (None for pseudo-steps such as migrations)."""
    calls = []
    for tr in traces:
        expr = {"fn": "s0", "args": []}
        for a in tr:
            if a["op"].startswith("@"):   # the deployment history: every migration, in facts order (history_op)
                for name, mg in cm.facts.get("migrations", {}).items():
                    expr = {"fn": "mig_" + name, "args": [expr] + [{"val": a[n]} for n, _ in mg.get("inputs", [])]}
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
    key = json.dumps([str(cm.artifact), tr], sort_keys=True)
    if key not in _POLICY_CACHE:
        req = {"module": str(cm.artifact), "facts": cm.facts, "hints": cm.hints(), "trace": tr}
        orc = cm.oracle_runtime()
        if orc is not None:   # an M2+ model: its oracle parameters are their sidecar instances (I15)
            req["oracles"] = orc
        p = subprocess.run(["node", str(ROOT / "holon" / "js" / "policy.mjs")], input=json.dumps(req),
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
            data += encode_step(a, facts)
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
    from .ir import LAW_GLOB, record_files   # every law-id pattern ir.load_laws_any reads (audit F-M2-02)
    laws = {p.stem: json.loads(p.read_text()) for p in (ROOT / "laws" / milestone).glob(LAW_GLOB)}
    records = {p.stem: json.loads(p.read_text()) for p in record_files(results)}
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


# ---------------------------------------------------------------- M2: SORT-site witnesses (I15)
SITE_HARNESS = ROOT / "replay" / "M2" / "solidity" / "HolonLastStep.t.sol"
FOUNDRY_DIR = "contracts"   # the morph directory a scratch Foundry project mirrors (its foundry.toml and contracts/)
PANIC_SELECTOR = bytes.fromhex("4e487b71")
OP_REVERT = 0xFD
CORPUS_SEED = 20261011      # the M1 corpus rule (main_replay_m1), run on the M2 model


def locate_panic(dump: dict) -> dict | None:
    """Where the dumped step raised Panic(uint256) (a `forge test --debug --dump` of HolonLastStep's test_last).

    The raising frame is the first debug-arena node, in execution order, whose last step is a REVERT returning exactly
    the 36 bytes of Panic(uint256). Its code is the artifact of the contract the dump identifies at the node's address
    (for a DELEGATECALL frame the address is the implementation's). The site is the source position of that frame's
    last instruction before the REVERT that solc's runtime source map (pc -> instruction index -> entry) attributes to
    a source file: Yul utility code has no file and is skipped. Returns {"code", "contract", "kind", "path" (in the
    scratch project), "line", "text"}, or None when no frame raised a Panic; ValueError when the frame's artifacts
    name different positions."""
    names = {k.lower(): v for k, v in dump["contracts"]["identified_contracts"].items()}
    sources = dump["contracts"]["sources"]
    for node in dump["debug_arena"]:
        steps = node.get("steps") or []
        if not steps or steps[-1].get("op") != OP_REVERT:
            continue
        rv = steps[-1]
        stack = rv.get("stack") or []
        if len(stack) < 2:
            continue
        off, size = int(stack[-1], 16), int(stack[-2], 16)
        mem = bytes.fromhex(rv["memory"][2:]) if rv.get("memory") else b""
        data = mem[off:off + size]
        if size != 36 or data[:4] != PANIC_SELECTOR:
            continue
        contract = names.get(str(node.get("address", "")).lower())
        sites = set()
        for art in sources["artifacts_by_name"].get(contract) or []:
            files = sources["sources_by_id"].get(str(art["build_id"]), {})
            smap, pcs = art["source_map_runtime"], art["pc_ic_map_runtime"]
            pos = None
            for st in steps[:-1]:
                ic = pcs.get(str(st["pc"]))
                if ic is None or ic >= len(smap):
                    continue
                ent = smap[ic]
                f = files.get(str(ent.get("index"))) if ent.get("index") is not None else None
                if f is None:
                    continue
                src = f["source"]
                pos = (f["path"], src[:ent["offset"]].count("\n") + 1, src[ent["offset"]:ent["offset"] + ent["length"]])
            if pos is not None:
                sites.add(pos)
        lines = {(p, ln) for p, ln, _ in sites}
        if len(lines) != 1:
            raise ValueError(f"the Panic frame of {contract} maps to {sorted(lines)} in its artifacts")
        path, line, text = sorted(sites)[0]
        return {"code": int.from_bytes(data[4:], "big"), "contract": contract, "kind": node.get("kind"),
                "path": path, "line": line, "text": text}
    return None


def site_project(morph: Path, proj: Path) -> Path:
    """A scratch Foundry project: morph's contracts/ tree at the pinned commit, the pinned dependencies, the M1 trace
    harness and HolonLastStep (both copied unchanged)."""
    proj.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(proj / "contracts", ignore_errors=True)
    shutil.copytree(morph / FOUNDRY_DIR / "contracts", proj / "contracts")
    for d in ("mock", "test"):
        shutil.rmtree(proj / "contracts" / d, ignore_errors=True)
    for f in ("foundry.toml", "remappings.txt"):
        shutil.copy(morph / FOUNDRY_DIR / f, proj / f)
    _sol_deps(proj)
    shutil.rmtree(proj / "test", ignore_errors=True)
    (proj / "test").mkdir()
    shutil.copy(ROOT / "replay" / "M1" / "solidity" / "HolonTraceReplay.t.sol", proj / "test")
    shutil.copy(SITE_HARNESS, proj / "test")
    return proj


def last_step(proj: Path, trace: list[dict], facts: dict, forge: str, solc: str | None, k: int) -> tuple[dict, dict | None, str]:
    """Replay one trace with its last step alone in test_last: ({step: outcome}, the located Panic or None, command)."""
    init = facts["initial"]
    data = [init["F"], init["W"], init["D"], init["t"], init["fsr"][0], len(trace)]
    for a in trace:
        data += encode_step(a, facts)
    tf = proj / f"holon_last_trace_{k}.json"
    tf.write_text(json.dumps({"data": data}))
    base = [forge, "test", "--match-contract", "HolonLastStepTest", "--match-test", "test_last", "--offline"] \
        + (["--use", solc] if solc else [])
    code, out = _run(base + ["-vv"], proj, {"HOLON_LAST_TRACE": tf.name})
    got = {int(m.group(2)): ("ok" if m.group(3) == "ok" else "rev " + m.group(4).strip()) for m in LINE.finditer(out)}
    if code != 0 or not got:
        raise SystemExit(f"HolonLastStep failed on trace {k} (exit {code}): {out[-1500:]}")
    dump = proj / f"holon_last_dump_{k}.json"
    code, out = _run(base + ["--debug", "--dump", dump.name], proj, {"HOLON_LAST_TRACE": tf.name})
    if code != 0 or not dump.exists():
        raise SystemExit(f"HolonLastStep debugger dump failed on trace {k} (exit {code}): {out[-1500:]}")
    panic = locate_panic(json.loads(dump.read_text()))
    dump.unlink()
    shown = " ".join("forge" if c == forge else "<solc 0.8.24>" if c == solc else c for c in base)
    return got, panic, f"HOLON_LAST_TRACE=<trace> {shown} -vv; then --debug --dump <file> (holon.mreplay.locate_panic)"


def in_span(span: str, site: str | None) -> bool:
    """Whether a located panic site "<path>:<line>" lies in a facts span "<path>:<lo>[-<hi>]"."""
    import re as _re
    m = _re.match(r"^(\S+?):(\d+)(?:-(\d+))?$", span or "")
    if not m or not site or ":" not in site:
        return False
    path, line = site.rsplit(":", 1)
    return path == m.group(1) and int(m.group(2)) <= int(line) <= int(m.group(3) or m.group(2))


def main_replay_m2(args) -> int:
    """`holon replay --milestone M2` (I15): every REFUTED per-entry witness of a SORT-site law (prefix ++ [action]) on
    the real code through the M1 trace harness, its last step's Panic located by HolonLastStep and a debugger dump;
    and the refinement corpus (the M1 corpus rule, seed and size) on the M2 model, its oracle parameters their sidecar
    instances. Writes replay/<M>/report.json and the records' replay fields."""
    from .ir import LAW_GLOB, record_files
    from .mpipeline import run_model, site_law, derivation_of
    from .replay import PIN_KEYS, morph_path, toolchain
    from .evidence import expected_provenance
    from .sorts.sites import load_sidecar
    milestone = args.milestone
    morph = morph_path(args)
    # the harness replays the M1 rollup machine: its document (laws/M1/REGISTRY.json) gives the op table and initial state
    hrel = json.loads((ROOT / "laws" / "M1" / "REGISTRY.json").read_text())["facts"]
    facts = F.load(ROOT / hrel)
    sha = check_checkout(morph, facts["target"]["commit"])
    tc = toolchain(args)
    work = Path(args.work or ROOT / "build" / f"replay_{milestone.lower()}").resolve()
    results = ROOT / "results" / milestone
    laws = {p.stem: json.loads(p.read_text()) for p in (ROOT / "laws" / milestone).glob(LAW_GLOB)}
    records = {p.stem: json.loads(p.read_text()) for p in record_files(results)}
    der = {e["law_id"]: e for e in (derivation_of(milestone) or {}).get("laws", [])}
    _, _, real_reasons = load_sidecar(milestone, ROOT)
    cm = run_model(milestone, ROOT / hrel)
    plan = []   # (law, entry, trace, witness)
    for lid in sorted(records):
        r = records[lid]
        if r.get("status") != "REFUTED" or site_law(laws.get(lid, {})) is None:
            continue
        if laws[lid].get("facts") != hrel:
            raise SystemExit(f"{lid}: its document {laws[lid].get('facts')} is not the harness's {hrel}")
        for e in sorted(r.get("witnesses") or {}):
            w = r["witnesses"][e]
            if w.get("status") == "REFUTED" and w.get("witness"):
                plan.append((lid, e, list(w["witness"]["s"]["run"]) + [dict(w["witness"]["a"])], w["witness"]))
    corpus = random_corpus(cm, args.corpus, seed=CORPUS_SEED)
    traces = [t for _, _, t, _ in plan] + corpus
    models = model_logs(cm, traces)
    real, command, _ = run_forge(morph, work, traces, facts, tc["forge"], tc["solc"])
    proj = site_project(morph, work / "solidity_site")
    report = {"morph_commit": sha, "command": command, "harness_mismatch": bool(real.pop("harness_mismatch", False)),
              "laws": {}, "witness_sha256": {}, "entry_witness_sha256": {},
              "toolchain": {**{k: tc[k] for k in PIN_KEYS}, "go_version": tc["go_version"]}}
    for tid, (lid, e, tr, w) in enumerate(plan):
        ag, dis = compare(facts, models[tid], real, tid, tr)
        outs = [("ok" if real.get((tid, i), ("?",))[0] == "ok" else "rev " + real.get((tid, i), ("", "?"))[1])
                for i in range(len(tr))]
        ls, panic, lcmd = last_step(proj, tr, facts, tc["forge"], tc["solc"], tid)
        site = f"{FOUNDRY_DIR}/{panic['path']}:{panic['line']}" if panic else None
        span = der.get(lid, {}).get("basis", {}).get("span")
        passed = not dis and len(ag) == len(tr) and ls.get(len(tr) - 1) == outs[-1]
        observed = (passed and any(outs[-1] == f"rev {x}" for x in sorted(real_reasons)) and in_span(span, site))
        ent = {"trace": tr, "model": [obs_str(facts, o) for o in models[tid]], "real": outs, "status": "passed" if passed else "failed",
               "disagree": dis, "panic_site": site, "panic": panic, "obstruction_observed": bool(observed),
               "last_step_command": lcmd}
        L = report["laws"].setdefault(lid, {"entries": {}})
        L["entries"][e] = ent
        report["entry_witness_sha256"].setdefault(lid, {})[e] = witness_sha256(w)
    for lid, L in report["laws"].items():
        ents = L["entries"]
        status = "passed" if ents and all(x["status"] == "passed" for x in ents.values()) else "failed"
        observed = bool(ents) and all(x["obstruction_observed"] for x in ents.values())
        summary = "; ".join(f"{e}: {x['real'][-1]} at {x['panic_site'] or 'no located panic'}" for e, x in sorted(ents.items()))
        L.update({"status": status, "obstruction_reproduced": observed, "observed": summary,
                  "sides": {"solidity": {"status": status, "provenance": expected_provenance(laws[lid], "solidity"),
                                         "observed": summary, "command": command, "obstruction_observed": observed}}})
        report["witness_sha256"][lid] = witness_sha256(records[lid].get("witness"))
    per_op: dict = {}
    disagreements = []
    for k, tr in enumerate(corpus):
        tid = len(plan) + k
        ag, dis = compare(facts, models[tid], real, tid, tr)
        for x in ag:
            per_op.setdefault(x["op"], {"agree": 0, "disagree": 0})["agree"] += 1
        for x in dis:
            per_op.setdefault(x["op"], {"agree": 0, "disagree": 0})["disagree"] += 1
            disagreements.append({"trace": tid, **x, "prefix": tr[: x["step"] + 1]})
    orc = cm.oracle_runtime()
    report["refinement"] = {"traces": len(corpus), "steps": sum(len(t) for t in corpus), "per_action": per_op,
                            "disagreements": disagreements[:50], "n_disagreements": len(disagreements), "seed": CORPUS_SEED,
                            "rule": "holon.mreplay.random_corpus (the M1 corpus rule)",
                            "model": f"the {milestone} model of {hrel}"
                                     + (f"; oracle parameters answered by their sidecar instances "
                                        f"({', '.join(sorted({i['param'] + ' = the instance of entry ' + i['id'] for i in orc['instances']}))})"
                                        if orc else "")}
    out = ROOT / "replay" / milestone / "report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    stamp_site_records(milestone, results, report)
    for lid, L in sorted(report["laws"].items()):
        print(f"{lid}: {L['status']}, obstruction reproduced: {L['obstruction_reproduced']}")
        for e, x in sorted(L["entries"].items()):
            print(f"    {e:22s} {x['status']:7s} last step {x['real'][-1]} at {x['panic_site']}  observed={x['obstruction_observed']}")
    rf = report["refinement"]
    print(f"refinement corpus: {rf['traces']} traces, {rf['steps']} steps, {rf['n_disagreements']} disagreements")
    bad = [lid for lid, L in report["laws"].items() if L["status"] != "passed" or not L["obstruction_reproduced"]]
    if bad or rf["n_disagreements"] or report["harness_mismatch"]:
        print(f"MODEL DEFECT or NOT REPRODUCED: {bad}; refinement disagreements: {rf['n_disagreements']}; "
              f"harness mismatch: {report['harness_mismatch']}")
        return 1
    return 0


def stamp_site_records(milestone: str, results: Path, report: dict) -> list[str]:
    """The records' replay fields from the report: the law's (holon.replay.replay_status) and each REFUTED entry
    point's (holon.mpipeline.entry_replay)."""
    from .mpipeline import entry_replay
    from .replay import replay_status
    changed = []
    for p in sorted(results.glob("L*.json")):
        rec = json.loads(p.read_text())
        if rec.get("status") != "REFUTED" or not isinstance(rec.get("witnesses"), dict):
            continue
        lid = rec["law_id"]
        new = dict(rec)
        new["replay"] = replay_status(report, lid, rec.get("witness"))
        new["witnesses"] = {e: {**w, "replay": entry_replay(report, lid, e, w.get("witness"))} if w.get("status") == "REFUTED"
                            else w for e, w in rec["witnesses"].items()}
        if new != rec:
            p.write_text(json.dumps(new, indent=2, sort_keys=True) + "\n")
            changed.append(lid)
    return changed
