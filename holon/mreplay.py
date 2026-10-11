"""`holon replay --milestone M1`: replay state-machine witnesses on the real Rollup (whitepaper §8.7, §9.6, §10.9).

Two corpora run through one generic Foundry harness (replay/M1/solidity/HolonTraceReplay.t.sol),
which deploys the real Rollup and L1MessageQueue at the pinned commit for every trace:

  witnesses   every REFUTED law's witness, linearised into the concrete traces its claim compares
              (e.g. an undo law gives  p ++ [do, undo] ++ q  and  p ++ q);
  refinement  a seeded random corpus of traces (successful and failing actions mixed).

For every step the model's observation (ok / revert reason) is compared with the real outcome.
A witness replays ("passed") iff every step of its traces agrees AND the obstruction itself shows
on the real code (two-sided claims: the continuations' outcomes differ; one-sided: the symptom
appears). Disagreements are model defects and are reported loudly.
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
from . import ir
from .mpipeline import CompiledMachine, _act_val
from .replay import _holon_lines, _run, _sol_deps, check_checkout, witness_sha256  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
OPS = {"commitBatch": 1, "commitState": 2, "commitBatchWithProof": 3, "revertBatch": 4, "challengeState": 5,
       "proveState": 6, "finalizeBatch": 7, "setPause": 8, "sendMessage": 9, "wait": 10, "@legacy_eta2": 11}
WIDTH = 13
CHUNK = 25
LINE = re.compile(r"HOLON (\d+) (\d+) (ok|rev) ?(.*)")


# ---------------------------------------------------------------- traces
class NoHarness(ValueError):
    """The witness starts from a state the Foundry harness cannot build: model-only pending replay."""


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
            raise NoHarness(f"migration {t['mig']} (pre-upgrade storage) has no Foundry harness step")
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
            cands = [c for c in policy_at(cm, tr) if c["op"] in OPS]   # only steps the harness can encode
            if not cands:
                break
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
                           input=json.dumps({"module": str(cm.artifact), "facts": cm.facts, "trace": tr}),
                           capture_output=True, text=True, timeout=120)
        if p.returncode != 0:
            raise RuntimeError(p.stderr[-1500:])
        _POLICY_CACHE[key] = json.loads(p.stdout)
    return _POLICY_CACHE[key]


# ---------------------------------------------------------------- harness
def run_forge(morph: Path, work: Path, traces: list[list[dict]], facts: dict, forge: str, solc: str | None) -> tuple[dict, str, int]:
    proj = work / "solidity"
    proj.mkdir(parents=True, exist_ok=True)
    if not (proj / "contracts").exists():
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


def main_replay_m1(args) -> int:
    morph = Path(args.morph).resolve()
    milestone = args.milestone
    reg = json.loads((ir.laws_dir(milestone, ROOT) / "REGISTRY.json").read_text())
    facts_path = ROOT / reg["facts"]
    facts = F.load(facts_path)
    sha = check_checkout(morph, facts["target"]["commit"][:7])
    shutil.rmtree(Path(args.work or ROOT / "build" / "replay_m1").resolve() / "go", ignore_errors=True)
    results = ROOT / "results" / milestone
    cm = CompiledMachine.build(facts_path)
    work = Path(args.work or ROOT / "build" / "replay_m1").resolve()
    laws = {p.stem: json.loads(p.read_text()) for p in ir.laws_dir(milestone, ROOT).glob("L_*.json")}
    records = {p.stem: json.loads(p.read_text()) for p in results.glob("L_*.json")}
    # witness corpus
    plan = []
    go_laws = []
    pending: dict[str, str] = {}   # model-only pending replay: why no harness step exists for the witness
    ext_path = ir.laws_dir(milestone, ROOT).parent / "replay" / "evidence.json"
    external = json.loads(ext_path.read_text()) if ext_path.exists() else {}
    for lid in sorted(records):
        r = records[lid]
        if r["status"] != "REFUTED":
            continue
        if lid in external:
            continue             # replayed by a harness recorded next to the law specs (checked against the witness below)
        if laws[lid]["facts"] != reg["facts"]:
            if F.load(ROOT / laws[lid]["facts"]).get("policy") == "batchdata":
                go_laws.append(lid)  # Go-side machine (OWN): replayed through go test below
            else:
                pending[lid] = f"no replay harness for {laws[lid]['facts']}"
            continue
        try:
            runs = linearise(laws[lid], r["witness"])
        except NoHarness as e:
            pending[lid] = str(e)
            continue
        unknown = sorted({a["op"] for run in runs for a in run["trace"] if a["op"] not in OPS})
        if unknown:
            pending[lid] = f"no Foundry harness step for {unknown} (the witness needs a caller/role the harness cannot impersonate)"
            continue
        fill_eta2_root(cm, runs)
        plan.append((lid, runs))
    corpus = random_corpus(cm, args.corpus, seed=20261011)
    traces = [run["trace"] for _, runs in plan for run in runs] + corpus
    models = model_logs(cm, traces)
    forge = args.forge or shutil.which("forge")
    real, command, code = run_forge(morph, work, traces, facts, forge, args.solc)
    report = {"morph_commit": sha, "command": command, "harness_mismatch": bool(real.pop("harness_mismatch", False)),
              "laws": {}, "witness_sha256": {}}
    tid = 0
    for lid, runs in plan:
        entry = {"traces": []}
        outs = []
        for run in runs:
            ag, dis = compare(facts, models[tid], real, tid, run["trace"])
            outs.append((run, ag, dis, models[tid], tid))
            entry["traces"].append({"label": run["label"], "trace": run["trace"], "agree": len(ag), "disagree": dis,
                                    "real": [("ok" if real.get((tid, i), ("?",))[0] == "ok" else "rev " + real.get((tid, i), ("", "?"))[1])
                                             for i in range(len(run["trace"]))]})
            tid += 1
        kind = runs[0]["kind"]
        reproduced, why = False, ""
        if kind == "differ":
            (ra, _, _, _, ta), (rb, _, _, _, tb) = outs
            qa = [real.get((ta, i)) for i in range(ra["split"], len(ra["trace"]))]
            qb = [real.get((tb, i)) for i in range(rb["split"], len(rb["trace"]))]
            sa = [x[0] + (" " + x[1] if x and x[0] == "rev" else "") for x in qa if x]
            sb = [x[0] + (" " + x[1] if x and x[0] == "rev" else "") for x in qb if x]
            reproduced = sa != sb
            why = f"continuation outcomes on the real code: {sa} vs {sb}"
        elif kind == "symptom":
            (r0, _, _, _, t0), = outs
            last = real.get((t0, len(r0["trace"]) - 1))
            want = facts["reasons"][str(r0["symptom"][1])]
            reproduced = bool(last) and last[0] == "rev" and last[1] == want
            why = f"last step on the real code: {last}"
        elif kind == "accepted":
            (r0, ag, dis, _, t0), = outs
            reproduced = not dis and all(real.get((t0, i), ("rev",))[0] == "ok" for i in range(len(r0["trace"])))
            why = "the real contract accepts the whole trace (the ghost-tag violation is invisible on chain by design)"
        elif kind == "same_commitment":
            (r1, _, _, _, t1), (r2, _, _, _, t2) = outs
            h1, h2 = real.get((t1, len(r1["trace"]) - 1)), real.get((t2, len(r2["trace"]) - 1))
            reproduced = bool(h1 and h2) and h1[0] == h2[0] == "ok" and h1[1] == h2[1]
            why = f"committedBatches after c1 / c2: {h1} / {h2} (different blob sidecars)"
        all_agree = all(not d for _, _, d, _, _ in outs)
        entry["status"] = "passed" if (all_agree and reproduced) else "failed"
        entry["obstruction_reproduced"] = reproduced
        entry["observed"] = why
        report["laws"][lid] = entry
        report["witness_sha256"][lid] = witness_sha256(records[lid]["witness"])
    for lid, why in sorted(pending.items()):
        report["laws"][lid] = {"status": "not_run", "obstruction_reproduced": False, "observed": "model-only pending replay: " + why, "traces": []}
        report["witness_sha256"][lid] = witness_sha256(records[lid]["witness"])
    for lid, ev in sorted(external.items()):
        if lid not in records or records[lid]["status"] != "REFUTED":
            continue
        same = ev.get("witness") == records[lid]["witness"]
        report["laws"][lid] = {"status": ev["status"] if same else "failed", "obstruction_reproduced": same and ev["status"] == "passed",
                               "command": ev.get("command", ""), "observed": ev.get("observed", "") if same else "external evidence is for a different witness",
                               "evidence": ev.get("files", []), "traces": []}
        report["witness_sha256"][lid] = witness_sha256(records[lid]["witness"])
    for lid in go_laws:
        lines, gcmd = replay_own_go(morph, work, results)
        st, obs = lines.get(lid, ("failed", "no result from go test"))
        realistic = lines.get("realistic")
        report["laws"][lid] = {"status": st, "obstruction_reproduced": st == "passed", "command": gcmd,
                               "observed": obs + (f"; realistic 60-byte contexts: {realistic[0]} ({realistic[1]})" if realistic else ""),
                               "traces": []}
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
        print(f"{lid:20s} {e['status']:7s} reproduced={e['obstruction_reproduced']}  {e['observed'][:110]}")
    rf = report["refinement"]
    print(f"refinement corpus: {rf['traces']} traces, {rf['steps']} steps, {rf['n_disagreements']} disagreements")
    bad = [l for l, e in report["laws"].items() if e["status"] != "passed"]
    if bad or rf["n_disagreements"] or report["harness_mismatch"]:
        print(f"MODEL DEFECT / NOT REPRODUCED: {bad}; refinement disagreements: {rf['n_disagreements']}")
        return 1
    return 0
