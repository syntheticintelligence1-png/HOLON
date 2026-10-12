#!/usr/bin/env python3
"""Compute model_outcome for every REFUTED M3 law and stamp the M3 replay reports.

For each REFUTED record in results/<milestone>/<lid>.json, the law's probe is
evaluated on the compiled Bend model at the record's own witness:

  - claim fn "last_ok": run the context trace + the claimed step through
    mreplay.model_logs; the probe outcome is the last action's observation
    (O_Ok -> "ok", O_Rev{code} -> "rev <facts.reasons[code]>").
  - claim fn "no_code": same, but the probe is the observation trace's last step.
  - claim "obsv": the observer is called on the post-trace state; the outcome
    is its boolean value rendered lowercase.

Each replay/M3/<harness>_report.json laws entry gets:
    model_outcome, chain_outcome (from its forge evidence lines),
    verdict = "agree" iff model_outcome == chain_outcome,
    status   = "passed"/"failed" to match.

Usage: python3 tools/m3_model_outcome.py [--check]   # --check: verify, don't write
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from holon.mpipeline import CompiledMachine, _act_val  # noqa: E402
from holon.mreplay import model_logs  # noqa: E402

MILESTONES = {"M3_msg": "msg_report.json", "M3_nat": "nat_report.json"}

# forge HOLON evidence line -> chain outcome, keyed by (milestone, law_id)
CHAIN_OUTCOME = {
    "L_msgr_payer_bears_fee": "ok",
    "L_msgr_sender_can_replay": "rev Exceed maximum replay times",
    "L_natr_defend": "rev only active submitter allowed",
    "L_natr_slash_at_stake": "false",
}


def _wsub(o, w):
    if isinstance(o, dict):
        if "var" in o:
            return {"nat": w[o["var"]]}
        return {k: _wsub(v, w) for k, v in o.items()}
    if isinstance(o, list):
        return [_wsub(v, w) for v in o]
    return o


def _act(t):
    o = {"op": t["act"]}
    for k, x in t["args"].items():
        o[k] = x.get("nat", x.get("bool", x.get("nats")))
    return o


def _obs_str(last, reasons):
    if isinstance(last, dict):
        if last.get("$") == "O_Ok":
            return "ok"
        if last.get("$") == "O_Rev":
            return f"rev {reasons.get(str(last.get('code')), last.get('code'))}"
    return repr(last)


def model_outcome(law: dict, witness: dict | None, cm: CompiledMachine):
    """The law's probe evaluated on the compiled model at the witness."""
    w = witness or {}
    lhs = _wsub(law["statement"]["claim"]["eq"][0], w)
    reasons = cm.facts.get("reasons", {})
    if lhs.get("fn") == "last_ok":
        a = lhs["args"][0]
        tr = [_act(x) for x in a["from"]["run"]["trace"]] + [_act(a["step"])]
        last = [l for l in model_logs(cm, [tr])[0] if l is not None][-1]
        return _obs_str(last, reasons)
    if lhs.get("fn") == "no_code":
        a = lhs["args"][0]
        tr = [_act(x) for x in a["from"]["run"]["trace"]] + [_act(x) for x in a["obs"]["trace"]]
        last = [l for l in model_logs(cm, [tr])[0] if l is not None][-1]
        return _obs_str(last, reasons)
    if "obsv" in lhs:
        tr = [_act(x) for x in lhs["of"]["run"]["trace"]]
        expr = {"fn": "s0", "args": []}
        for a_ in tr:
            expr = {"fn": "step", "args": [{"val": _act_val(cm.m, a_)}, expr]}
        res = cm.calls([{"fn": lhs["obsv"],
                         "args": [expr] + [{"val": v["nat"]} for v in lhs.get("args", [])]}])
        return str(res[0]).lower() if isinstance(res[0], bool) else res[0]
    raise ValueError(f"no probe form for claim {json.dumps(lhs)[:120]}")


def main(check: bool) -> int:
    machines: dict = {}
    changed = []
    for m, fname in MILESTONES.items():
        rpath = ROOT / "replay" / "M3" / fname
        rep = json.loads(rpath.read_text())
        for lid, e in rep.get("laws", {}).items():
            recp = ROOT / "results" / m / f"{lid}.json"
            lawp = ROOT / "laws" / m / f"{lid}.json"
            if not recp.exists() or not lawp.exists():
                continue
            rec = json.loads(recp.read_text())
            if rec.get("status") != "REFUTED":
                continue
            law = json.loads(lawp.read_text())
            cm = machines.setdefault(law["facts"], CompiledMachine.build(ROOT / law["facts"]))
            mo = model_outcome(law, rec.get("witness"), cm)
            co = CHAIN_OUTCOME[lid]
            want = {"model_outcome": mo, "chain_outcome": co,
                    "verdict": "agree" if mo == co else "disagree",
                    "status": "passed" if mo == co else "failed"}
            if any(e.get(k) != v for k, v in want.items()):
                changed.append(f"{lid}: {e.get('model_outcome')}/{e.get('verdict')} -> {mo}/{want['verdict']}")
                e.update(want)
        if not check:
            rpath.write_text(json.dumps(rep, indent=1) + "\n")
    if check:
        # re-read to diff against disk
        for m, fname in MILESTONES.items():
            rep = json.loads((ROOT / "replay" / "M3" / fname).read_text())
            for lid, e in rep.get("laws", {}).items():
                if "model_outcome" in e and e["verdict"] != ("agree" if e["model_outcome"] == e["chain_outcome"] else "disagree"):
                    changed.append(f"{lid}: verdict inconsistent with outcomes")
    for c in changed:
        print("DIFF", c)
    if check and changed:
        return 1
    print("model_outcome stamped" if not check else "all report entries consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
