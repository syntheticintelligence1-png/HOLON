"""python -m holon eval baselines <command> (I52; spec/M4/lib/I52_baselines.json)

  budget  --measurement FILE          write results/eval/holon_budget.json (holon_budget.morph's rule) from the M3 gate's
                                      measurement (argv, exit, wall_s, cpu_s) and the base's recorded M0-M2 timings
  run     --system S [--baseline B ...] [--target T ...] [--jobs N] [--force]
                                      run the tool baselines (not agent_review) at the system's budget, one core each
  agent   --system S --model NAME     the one fresh reviewer of the system
  adjudicate --system S --model NAME  the blinded match adjudicator over every located group not yet adjudicated
  assemble --system S [--check]       results/eval/<system>/<baseline>.json and .timing.json from the raw records
  heldout                             the held-out run, one command once I50 lands (refused until then)

Raw records live under ~/.holon/eval/baselines/ (outside the repository); assemble is deterministic over them.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import common
from . import agent, core, gofuzz, mining, sol

RUNNERS = {**sol.RUNNERS, **gofuzz.RUNNERS, **mining.RUNNERS}
ADJ = core.HOME / "adjudications"


def _tool_info(b: str) -> dict:
    cfg = core.config().get("baselines", {}).get("tools", {})
    t = cfg.get(b if b not in ("two_cycle",) else "go_fuzz", {})
    name = {"go_fuzz": "go test -fuzz", "two_cycle": "holon 2-cycle generator + go test -fuzz",
            "spec_mining": "holon belief miner (gotool + slither API)", "agent_review": "claude -p"}.get(b, b)
    pins = {k: v for k, v in (t.get("pins") or {}).items()}
    installed = not t.get("missing", False)
    return {"name": name, "version": t.get("version", "unknown"), "pins": pins, "installed": installed,
            "missing_reason": t.get("missing_reason"), "same_family": True if b == "agent_review" else None,
            "model_tag": "A" if b == "agent_review" else None}


# ------------------------------------------------------------------------------------------------- budget
def cmd_budget(a) -> int:
    m = core.load(a.measurement)
    if m.get("exit") != 0:
        raise common.Refused("the M3 gate measurement did not pass (exit != 0); HOLON's budget is not measured")
    base = {}
    for i in range(3):
        p = subprocess.run(["git", "-C", str(core.ROOT), "show", f"4fd64a52:results/M{i}/metrics_timing.json"],
                           capture_output=True, text=True, check=True)
        base[f"m{i}_s"] = json.loads(p.stdout)["from_scratch_gate_s"]
    h = base["m0_s"] + base["m1_s"] + base["m2_s"] + m["wall_s"]
    proto = core.protocol()
    (s,) = [s for s in core.systems() if core.pinned(s) and "wall_s_rule" in proto["budget"].get(s, {})]
    doc = {"doc": f"I52: HOLON's own budget on {s} (spec/M4/lib/I52_baselines.json holon_budget.{s}): M0-M2 as "
                  "recorded at the base 4fd64a52, M3 measured by a full `holon gate --milestone M3` on a scratch copy "
                  f"(this machine, before any baseline result). {s}_wall_s = 60 * ceil(sum_s / 60) is every baseline's "
                  f"{s} wall clock. The M3 run used several threads and checker processes (m3_cpu_s); a baseline gets "
                  "one core.",
           **base, "m3_s": m["wall_s"], "m3_cpu_s": m["cpu_s"], "sum_s": round(h, 3),
           f"{s}_wall_s": core.rule_wall_s(h),
           "m3_measurement": {"argv": ["python", "-m", "holon", "gate", "--milestone", "M3", "--root", "<scratch copy>"],
                              "exit": m["exit"], "wall_s": m["wall_s"], "cpu_s": m["cpu_s"]}}
    p = core.holon_budget_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(common.dumps(doc))
    print(f"holon budget: sum {h:.1f} s -> {s} wall_s {doc[f'{s}_wall_s']}")
    return 0


# ------------------------------------------------------------------------------------------------- run
def _one(system, b, t, force):
    if core.raw(system, b, t) and not force:
        return f"{b}/{t}: kept"
    if not core.applicable(b, system, t):
        rec = {"status": "not_applicable", "reason": f"the target's scope holds no {'Solidity' if b in core.SOLIDITY else 'Go'} file",
               "findings": [], "units": [], "commands": [], "seeds": {}, "budget_exhausted": None}
        core.write_raw(system, b, t, rec)
        return f"{b}/{t}: not_applicable"
    info = _tool_info(b)
    if not info["installed"]:
        rec = {"status": "missing", "reason": info["missing_reason"], "findings": [], "units": [], "commands": [],
               "seeds": {}, "budget_exhausted": None}
        core.write_raw(system, b, t, rec)
        return f"{b}/{t}: missing"
    wall = core.budget(system)["wall_s"]
    with core.Core() as cpu:
        try:
            rec = RUNNERS[b](system, t, wall, cpu)
        except Exception as ex:  # noqa: BLE001
            rec = {"status": "error", "reason": f"{type(ex).__name__}: {ex}"[:1500], "findings": [], "units": [],
                   "commands": [], "seeds": {}, "budget_exhausted": None, "traceback": traceback.format_exc()[-3000:]}
    core.write_raw(system, b, t, rec)
    return f"{b}/{t}: {rec['status']} {len(rec['findings'])} findings {rec.get('reason') or ''}"[:300]


def cmd_run(a) -> int:
    bs = a.baseline or [b for b in core.BASELINES if b != "agent_review"]
    ts = a.target or core.targets(a.system)
    jobs = [(b, t) for t in ts for b in bs]
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for line in ex.map(lambda j: _one(a.system, j[0], j[1], a.force), jobs):
            print(line, flush=True)
    return 0


def cmd_agent(a) -> int:
    rec = agent.run_reviewer(a.system, a.model)
    for t in core.targets(a.system):
        st = "run" if (rec["parsed"] or rec["timed_out"]) else "error"
        core.write_raw(a.system, "agent_review", t, {
            "status": st, "reason": None if rec["parsed"] else ("the reviewer was stopped at the budget without an answer"
                                                              if rec["timed_out"] else "the reviewer's answer did not parse"),
            "findings": rec["findings"].get(t, []), "units": [], "commands": ["claude -p (I52_baselines.json agent_review invocation)"],
            "seeds": {}, "budget_exhausted": rec["timed_out"],
            "scope_extra": {"packet_files": rec["per_target"].get(t, []), "prompt_sha256": rec["prompt_sha256"]}})
    print(f"agent {a.system}: {rec['wall_s']} s of {rec['budget_s']} s, parsed {rec['parsed']}, "
          f"{sum(len(v) for v in rec['findings'].values())} findings")
    return 0


# ------------------------------------------------------------------------------------------------- assemble
def _record(system, b, t):
    r = core.raw(system, b, t)
    if r is None:
        return None
    src = None
    scope_files = []
    if r["status"] == "run" or r["status"] == "error":
        try:
            src = core.checkout(system, t)
            scope_files = core.scope_files(src, system, t)
        except Exception:  # noqa: BLE001
            scope_files = []
    allowed = set(scope_files) | (set(core.labelled_files(system, t)) if b == "agent_review" else set())
    fs = core.normalise(r["findings"], allowed) if r["status"] == "run" else []
    matches = []
    for f in fs:
        for lab in core.located(system, t, f):
            matches.append({"finding": f["id"], "label": lab, "how": "location"})
    located = sorted({m["label"] for m in matches}, key=core.label_key)
    adj = []
    store = ADJ / system / b / f"{t}.json"
    have = core.load(store) if store.is_file() else {}
    for lab in located:
        ids = sorted(m["finding"] for m in matches if m["label"] == lab)
        prompt_sha = core.sha256_text(agent.match_prompt(system, lab, [f for f in fs if f["id"] in ids]))
        a = have.get(lab)
        if a and a["prompt_sha256"] == prompt_sha:
            adj.append(a)
    detected = sorted({a["label"] for a in adj if a["confirmed"]}, key=core.label_key)
    scope = {"dirs": core.scope_dirs(system, t), "labelled_files": core.labelled_files(system, t),
             "files": scope_files}
    for k in ("submodules", "packages", "setup_errors", "harness"):
        if r.get(k):
            scope[k] = r[k]
    scope.update(r.get("scope_extra") or {})
    rec = {"status": r["status"], "reason": r.get("reason"), "budget_exhausted": r.get("budget_exhausted"),
           "commit": core.commit_of(system, t), "scope": scope, "commands": r.get("commands", []),
           "seeds": r.get("seeds", {}), "units": [{k: u[k] for k in ("name", "exit", "timed_out") if k in u}
                                                   for u in r.get("units", [])],
           "findings": fs, "matches": matches, "adjudications": adj, "located": located, "detected": detected}
    timing = {"cpus": 1, "setup_s": r.get("setup_s", 0.0), "units": [{"name": u["name"], "wall_s": u["wall_s"],
                                                                     "cpu_s": u.get("cpu_s")} for u in r.get("units", [])],
              "cpu_s": round(sum(u.get("cpu_s") or 0 for u in r.get("units", [])), 3)}
    return rec, timing


def pending_groups(system):
    out = []
    for b in core.BASELINES:
        for t in core.targets(system):
            got = _record(system, b, t)
            if not got:
                continue
            rec, _ = got
            have = {a["label"] for a in rec["adjudications"]}
            for lab in rec["located"]:
                if lab not in have:
                    ids = sorted(m["finding"] for m in rec["matches"] if m["label"] == lab)
                    out.append((b, t, lab, [f for f in rec["findings"] if f["id"] in ids]))
    return out


def cmd_adjudicate(a) -> int:
    groups = pending_groups(a.system)
    print(f"{len(groups)} groups to adjudicate", flush=True)

    def go(g):
        b, t, lab, fs = g
        res = agent.adjudicate(a.system, lab, fs, a.model)
        store = ADJ / a.system / b / f"{t}.json"
        store.parent.mkdir(parents=True, exist_ok=True)
        return b, t, lab, res, store
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for b, t, lab, res, store in ex.map(go, groups):
            have = core.load(store) if store.is_file() else {}
            have[lab] = res
            store.write_text(json.dumps(have, indent=1, sort_keys=True))
            print(f"{b}/{t}/{lab}: confirmed {res['confirmed']}", flush=True)
    return 0


def cmd_assemble(a) -> int:
    out_dir = core.RESULTS / a.system
    ok = True
    for b in core.BASELINES:
        targets, timing = {}, {}
        for t in core.targets(a.system):
            got = _record(a.system, b, t)
            if got is None:
                print(f"{b}/{t}: no raw record", file=sys.stderr)
                ok = False
                continue
            targets[t], timing[t] = got
        doc = {"schema": core.SCHEMA, "baseline": b, "system": a.system, "protocol_sha256": core.protocol_sha256(),
               "tool": _tool_info(b), "budget": core.budget(a.system), "targets": targets}
        tm = {"system": a.system, "baseline": b, "note": "timings only (wall clock and CPU of each unit, setup "
              "outside the budget); never compared for determinism", "targets": timing}
        if b == "agent_review":
            rp = core.HOME / "agent" / f"{a.system}.json"
            if rp.is_file():
                rr = core.load(rp)
                tm["reviewers"] = [{"wall_s": rr["wall_s"], "budget_s": rr["budget_s"], "cpu_s": None,
                                    "cpu_reason": "the model provider's compute; not measured", "tokens": rr["tokens"],
                                    "timed_out": rr["timed_out"]}]
        if a.check:
            ok &= common.write_or_check(out_dir / f"{b}.json", common.dumps(doc), True)
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{b}.json").write_text(common.dumps(doc))
            (out_dir / f"{b}.timing.json").write_text(common.dumps(tm))
    print("assemble:", "OK" if ok else "INCOMPLETE")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="holon eval baselines")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("budget"); p.add_argument("--measurement", required=True)
    p = sp.add_parser("run"); p.add_argument("--system", required=True); p.add_argument("--baseline", nargs="*")
    p.add_argument("--target", nargs="*"); p.add_argument("--jobs", type=int, default=3); p.add_argument("--force", action="store_true")
    p = sp.add_parser("agent"); p.add_argument("--system", required=True); p.add_argument("--model", required=True)
    p = sp.add_parser("adjudicate"); p.add_argument("--system", required=True); p.add_argument("--model", required=True)
    p.add_argument("--jobs", type=int, default=4)
    p = sp.add_parser("assemble"); p.add_argument("--system", required=True); p.add_argument("--check", action="store_true")
    sp.add_parser("heldout")
    a = ap.parse_args(argv)
    if getattr(a, "system", None) == "heldout" or a.cmd == "heldout":
        raise common.Refused("the held-out system is pending: it waits for I49/I50 and this command never reads "
                             "spec/heldout/ until I50's labels and scope exist (then: run, agent, adjudicate, assemble "
                             "with --system heldout)")
    return {"budget": cmd_budget, "run": cmd_run, "agent": cmd_agent, "adjudicate": cmd_adjudicate,
            "assemble": cmd_assemble}[a.cmd](a)


def cli_baselines(argv: list[str]) -> int:
    return main(argv)
