"""python -m holon eval baselines <command> (I52; spec/M4/lib/I52_baselines.json)

  budget  --measurement FILE          write results/eval/holon_budget.json (holon_budget.morph's rule) from the M3 gate's
                                      measurement (argv, exit, wall_s, cpu_s) and the base's recorded M0-M2 timings;
          [--report R --failed-checks G1,..]  a failed run is accepted only when its failing checks are exactly these
  run     --system S [--baseline B ...] [--target T ...] [--jobs N] [--force]
                                      run the tool baselines (not agent_review) at the system's budget, one core each
  agent   --system S --model NAME     the one fresh reviewer of the system
  adjudicate --system S --model NAME  the blinded match adjudicator over every located group not yet adjudicated
  assemble --system S [--check]       results/eval/<system>/<baseline>.json and .timing.json from the raw records
  budget-heldout                      I52b: write results/eval/heldout/holon_budget.json, the primary budget's rule over
                                      I50's route measured on a scratch copy (spec/M4/lib/I52b_heldout.json budget.primary)
  --tier primary|secondary            I52b: the held-out system's budget tier (run, agent, adjudicate, assemble); the
                                      secondary tier's records and results are kept apart (results/eval/heldout/secondary/)

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
    failed, details = [], {}
    if m.get("exit") != 0:
        if not a.report or not a.failed_checks:
            raise common.Refused("the M3 gate measurement did not pass (exit != 0); name its report and the checks "
                                 "allowed to fail (--report, --failed-checks)")
        rep = core.load(a.report)
        failed = sorted(k for k, v in rep["checks"].items() if not v["passed"])
        if failed != sorted(a.failed_checks.split(",")):
            raise common.Refused(f"the gate's failing checks are {failed}, not {a.failed_checks}")
        details = {k: rep["checks"][k]["detail"] for k in failed}
    if a.report:
        rep = core.load(a.report)
        checks = {k: bool(v["passed"]) for k, v in sorted(rep["checks"].items())}
        not_applicable = sorted(rep.get("not_applicable") or {})
    else:
        checks, not_applicable = None, None
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
                              "exit": m["exit"], "wall_s": m["wall_s"], "cpu_s": m["cpu_s"],
                              "failed_checks": failed, "failed_details": details, "checks": checks,
                              "not_applicable": not_applicable}}
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
    store = ADJ / core.tiered(system) / b / f"{t}.json"
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
    if a.system == core.HELDOUT:
        return _adjudicate_heldout(a, groups)

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


def _adjudicate_heldout(a, groups) -> int:
    """I52b: an action's five labels share their located findings, so one process answers for all five (per rule)."""
    labs = core.heldout_labels()
    by = {}
    for b, t, lab, fs in groups:
        k = (b, t, labs[lab]["action"], tuple(f["id"] for f in fs))
        by.setdefault(k, (fs, {}))[1][labs[lab]["rule"]] = lab

    def go(item):
        (b, t, action, _), (fs, rules) = item
        return b, t, action, agent.adjudicate_heldout(action, rules, fs, a.model)
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for b, t, action, res in ex.map(go, sorted(by.items())):
            store = ADJ / core.tiered(a.system) / b / f"{t}.json"
            store.parent.mkdir(parents=True, exist_ok=True)
            have = core.load(store) if store.is_file() else {}
            have.update(res)
            store.write_text(json.dumps(have, indent=1, sort_keys=True))
            print(f"{b}/{t}/{action}: confirmed " + ", ".join(f"{k} {v['confirmed']}" for k, v in sorted(res.items())),
                  flush=True)
    return 0


def cmd_budget_heldout(a) -> int:
    """I52b: H = the wall clock of I50's route (holon target derive, then holon target run) on a scratch copy of the
    repository, from the committed held-out document; written before any held-out baseline result."""
    import os
    import shutil
    import tempfile
    import time
    if core.heldout_budget_path().is_file() and not a.force:
        raise common.Refused(f"{core.heldout_budget_path()} exists (--force to re-measure before any baseline result)")
    t = core.targets(core.HELDOUT)[0]
    scratch = Path(tempfile.mkdtemp(prefix="i52b-budget-")) / "repo"
    shutil.copytree(core.ROOT, scratch, ignore=shutil.ignore_patterns(".git", "__pycache__"), symlinks=True)
    steps = []
    try:
        for c in ("derive", "run"):
            argv = [sys.executable, "-m", "holon", "target", c, "--target", t, "--root", str(scratch)]
            t0 = time.monotonic()
            r0 = os.times()
            p = subprocess.run(argv, cwd=str(scratch), capture_output=True, text=True,
                               env={**os.environ, "BEND_NO_TELEMETRY": "1"})
            wall = time.monotonic() - t0
            r1 = os.times()
            steps.append({"argv": ["python", "-m", "holon", "target", c, "--target", t, "--root", "<scratch copy>"],
                          "exit": p.returncode, "wall_s": round(wall, 3),
                          "cpu_s": round((r1.children_user - r0.children_user) + (r1.children_system - r0.children_system), 3),
                          "stdout_tail": (p.stdout or "")[-600:], "stderr_tail": (p.stderr or "")[-600:]})
            print(f"{c}: exit {p.returncode}, {wall:.3f} s", flush=True)
    finally:
        shutil.rmtree(scratch.parent, ignore_errors=True)
    h = round(sum(s["wall_s"] for s in steps), 3)
    doc = {"doc": "I52b: HOLON's own budget on the held-out system (spec/M4/lib/I52_baselines.json holon_budget.heldout, "
                  "'I50's recorded wall clock'; spec/M4/lib/I52b_heldout.json budget.primary). I50 recorded no wall "
                  "clock, so its route was measured on this machine on a scratch copy of the repository, from the "
                  "committed held-out document, before any baseline result of the system: holon target derive, then "
                  "holon target run. heldout_wall_s = 60 * ceil(sum_s / 60) is every baseline's primary wall clock.",
           "steps": steps, "sum_s": h, "heldout_wall_s": core.rule_wall_s(h),
           "cpu_s": round(sum(s["cpu_s"] for s in steps), 3)}
    p = core.heldout_budget_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(common.dumps(doc))
    print(f"holon budget (held-out): sum {h:.3f} s -> wall_s {doc['heldout_wall_s']}")
    return 0


def cmd_assemble(a) -> int:
    out_dir = core.results_dir(a.system)
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
            rp = agent.reviewer_path(a.system)
            if rp.is_file():
                rr = core.load(rp)
                tm["reviewers"] = [{"wall_s": rr["wall_s"], "budget_s": rr["budget_s"], "cpu_s": None,
                                    "cpu_reason": "the model provider's compute; not measured", "tokens": rr["tokens"],
                                    "timed_out": rr["timed_out"]}]
        if a.check:
            ok &= not common.write_or_check(out_dir / f"{b}.json", common.dumps(doc), True)  # I52b: True means it differs
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
    p.add_argument("--report"); p.add_argument("--failed-checks")
    p = sp.add_parser("budget-heldout"); p.add_argument("--force", action="store_true")
    p = sp.add_parser("run"); p.add_argument("--system", required=True); p.add_argument("--baseline", nargs="*")
    p.add_argument("--target", nargs="*"); p.add_argument("--jobs", type=int, default=3); p.add_argument("--force", action="store_true")
    p = sp.add_parser("agent"); p.add_argument("--system", required=True); p.add_argument("--model", required=True)
    p = sp.add_parser("adjudicate"); p.add_argument("--system", required=True); p.add_argument("--model", required=True)
    p.add_argument("--jobs", type=int, default=4)
    p = sp.add_parser("assemble"); p.add_argument("--system", required=True); p.add_argument("--check", action="store_true")
    sp.add_parser("heldout")
    for name in ("run", "agent", "adjudicate", "assemble"):
        sp.choices[name].add_argument("--tier", choices=core.TIERS, default="primary")
    a = ap.parse_args(argv)
    if a.cmd == "heldout":
        raise common.Refused("the held-out run is: budget-heldout, then run, agent, adjudicate and assemble with "
                             "--system heldout [--tier secondary]")
    if getattr(a, "system", None) == core.HELDOUT or a.cmd == "budget-heldout":
        core.heldout()  # refuses until I52b's instrument exists
    if getattr(a, "tier", "primary") != "primary" and a.system != core.HELDOUT:
        raise common.Refused("--tier applies to the held-out system only")
    core.set_tier(getattr(a, "tier", "primary"))
    return {"budget": cmd_budget, "run": cmd_run, "agent": cmd_agent, "adjudicate": cmd_adjudicate,
            "assemble": cmd_assemble, "budget-heldout": cmd_budget_heldout}[a.cmd](a)


def cli_baselines(argv: list[str]) -> int:
    return main(argv)
