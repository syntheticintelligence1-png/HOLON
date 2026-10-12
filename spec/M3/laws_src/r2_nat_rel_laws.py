"""AUDIT_R2 follow-up: O13/O14 as quantified naturality laws (lead-authored, preregistered before any run).
The e2c laws stated the cutover edges as closed scenarios predicted PROVED; AUDIT_R2 F1/F2 showed that
bypasses G6 and that L_nat_slash_legacy_misses is insensitive to the slash. Here each edge is a law over
the committer w that holds natively (no cutover) and is predicted REFUTED across initialize4, so the
witness w goes through G6. Both rest on the spec-bound effect initialize4: active := nact
(coverage spec_bound); the bond/reward side of O14 is evidenced only by replay/M3/nat_report.json.
    python3 spec/M3/laws_src/r2_nat_rel_laws.py   ->  laws/M3_nat/L_natr_*.json
"""
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FACTS = "spec/M3/extracted/morph_rollup.json"
MS = "M3_nat"

def v(x):
    if isinstance(x, dict): return x
    return {"nats": x} if isinstance(x, list) else {"bool": x} if isinstance(x, bool) else {"nat": x}
def act(_nm, **a): return {"act": _nm, "args": {k: v(x) for k, x in a.items()}}
def run_of(tr): return {"run": {"trace": tr}, "from": {"s0": {}}}
W = {"var": "w"}
msg = act("sendMessage", who=5)
def cw(): return [msg, act("commitBatch", who=W, ver=1, parent=0, n=1, lbn=1, prev=100, post=101, blobs=[7])]
def ch(): return act("challengeState", who=4, idx=1, value=1)
def pr(who): return act("proveState", who=who, idx=1, proof=1)
I4 = act("initialize4", who=6, sub=9, exp=1, nact=[7])
def last_ok(tr, step): return {"fn": "last_ok", "args": [{"step": step, "from": run_of(tr)}]}
def is_true(t): return {"eq": [t, {"bool": True}]}
def active_w(tr): return {"obsv": "active_has", "of": run_of(tr), "args": [W]}

# premise: w committed batch 1 and can defend it natively (so w was an active submitter)
PREM = [is_true(last_ok(cw() + [ch()], pr(W)))]
LAWS = [
  ("L_natr_defend", is_true(last_ok(cw() + [I4, ch()], pr(W))), "REFUTED",
   "O13 (F10) naturality, defend edge: the committer of in-flight batch 1 can still prove it when the challenge comes after initialize4."),
  ("L_natr_slash_at_stake", is_true(active_w(cw() + [I4, ch(), act("wait", dt=10)])), "REFUTED",
   "O14 (F10) naturality, slash edge: when the proof window of a post-cutover challenge on batch 1 has elapsed, its committer is still a member of the registry the challenger win will slash."),
  ("L_natr_slash_at_stake_native", is_true(active_w(cw() + [ch(), act("wait", dt=10)])), "PROVED",
   "control for L_natr_slash_at_stake without initialize4: natively the committer is at stake in the slashed registry."),
]

def law(lid, claim, pred, notes):
    return {"ir_version": "holon-ir/0.2", "law_id": lid, "milestone": MS, "rule": "NAT", "subform": "naturality_scenario",
            "facts": FACTS, "facts_sha256": hashlib.sha256((ROOT / FACTS).read_bytes()).hexdigest(),
            "statement": {"binders": [{"q": "forall", "name": "w", "type": "Nat"}], "assume": PREM, "claim": claim},
            "notes": notes + " Depends on spec-bound initialize4 effect active := nact.", "maps_to": "O13/O14 (F10)",
            "predicted": pred}

def build():
    facts = json.loads((ROOT / FACTS).read_text())
    names = {a["name"] for a in facts["actions"]}
    for lid, c, p, n in LAWS:
        def chk(x):
            if isinstance(x, dict) and "act" in x: assert x["act"] in names, (lid, x["act"])
            if isinstance(x, dict): [chk(y) for y in x.values()]
            if isinstance(x, list): [chk(y) for y in x]
        chk(c)
        out = ROOT / "laws" / MS / f"{lid}.json"
        out.write_text(json.dumps(law(lid, c, p, n), indent=2, sort_keys=True) + "\n")
        print(out.relative_to(ROOT))

if __name__ == "__main__":
    build()
