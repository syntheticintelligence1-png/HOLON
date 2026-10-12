"""M3 NAT cutover scenario laws (lead-authored, preregistered before any run) on the E2c Rollup facts.
initialize4 (Rollup.sol:209-219) swaps submitterContract; the model carries it as active := nact.
L_nat_defend_legacy_blocked (O13 defend edge) and L_nat_slash_legacy_misses (O14 slash edge) are
predicted PROVED, and for those two PROVED is the finding: eta4 is not natural.
Seam: the model's ISubmitter.slash oracle has no guard. Whether the real new Submitter.slash(legacy)
reverts (liveness) or no-ops (bond not at risk) is a replay question, not decided by these laws.
    python3 spec/M3/laws_src/e2c_nat_laws.py   ->  laws/M3_nat/
"""
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FACTS = "spec/M3/extracted/morph_rollup.json"
MS = "M3_nat"

def act(_nm, **a):
    v = lambda x: {"nats": x} if isinstance(x, list) else {"bool": x} if isinstance(x, bool) else {"nat": x}
    return {"act": _nm, "args": {k: v(x) for k, x in a.items()}}
def run_of(setup): return {"run": {"trace": setup}, "from": {"s0": {}}}
msg = act("sendMessage", who=5)
def wait(dt): return act("wait", dt=dt)
def cb(parent, prev, post, blob, who=2, n=1, ver=1):
    return act("commitBatch", who=who, ver=ver, parent=parent, n=n, lbn=parent + 1, prev=prev, post=post, blobs=[blob])
def ch(idx, who=4, value=1): return act("challengeState", who=who, idx=idx, value=value)
def pr(idx, who, proof=1): return act("proveState", who=who, idx=idx, proof=proof)
def i4(who=6, sub=9, exp=1, nact=(7,)): return act("initialize4", who=who, sub=sub, exp=exp, nact=list(nact))

# s0: t=10, W=10, active [2,3], challenger 4, PADMIN 6. Batch 1 is committed by legacy submitter 2.
C1 = [msg, cb(0, 100, 101, 7)]
X = C1 + [i4()]                                   # cutover at lci = 1; new registry {7}
XC = X + [ch(1)]                                  # legacy batch 1 challenged after cutover
XCW = XC + [wait(10)]                             # proof window elapsed (ch.s + W <= t)
N2 = X + [msg, cb(1, 101, 102, 8, who=7)]         # batch 2 committed natively by new member 7
N2CW = N2 + [ch(2), wait(10)]

def ok(setup, probe): return {"eq": [{"fn": "last_ok", "args": [{"step": probe, "from": run_of(setup)}]}, {"bool": True}]}
def rev(setup, probe, m): return {"eq": [{"fn": "no_code", "args": [{"obs": {"trace": [probe]}, "from": run_of(setup)}, {"reason": m}]}, {"bool": False}]}
def obs(setup, name, args, val):
    v = {"bool": val} if isinstance(val, bool) else {"nat": val}
    return {"eq": [{"obsv": name, "of": run_of(setup), "args": [{"nat": x} for x in args]}, v]}

SCEN = [
  ("nat_defend_legacy_blocked", XC, rev(XC, pr(1, who=2), "only active submitter allowed"),
   "O13 defend edge: after the cutover the legacy committer of in-flight batch 1 cannot prove it (FINDING if PROVED)"),
  ("nat_defend_new_member", XC, ok(XC, pr(1, who=7)), "a new-registry member can defend the legacy batch"),
  ("nat_slash_legacy_misses", XCW + [pr(1, who=7)], obs(XCW + [pr(1, who=7)], "active_has", [7], True),
   "O14 slash edge: challenger wins on legacy batch 1; slash(bds=2) hits a registry without 2, no member loses status (FINDING if PROVED)"),
  ("nat_slash_native_hits", N2CW + [pr(2, who=7)], obs(N2CW + [pr(2, who=7)], "active_has", [7], False),
   "native control: challenger wins on batch 2 committed by 7 post-cutover; 7 is slashed"),
  ("nat_cutover_admin_only", C1, rev(C1, i4(who=1), "only proxy admin"), ":210"),
  ("nat_cutover_mismatch", C1, rev(C1, i4(exp=0), "cutover batch mismatch"), ":212"),
  ("nat_cutover_in_challenge", C1 + [ch(1)], rev(C1 + [ch(1)], i4(), "challenge in progress"), ":213"),
  ("nat_lcb", X, obs(X, "lcb_of", [], 1), ":216 legacyCutoverBatchIndex := expected index"),
]

def law(lid, st, notes, rule="NAT", subform="scenario"):
    return {"ir_version": "holon-ir/0.2", "law_id": lid, "milestone": MS, "rule": rule, "subform": subform, "facts": FACTS,
            "facts_sha256": hashlib.sha256((ROOT / FACTS).read_bytes()).hexdigest(),
            "statement": {"binders": [], "assume": [], "claim": st}, "notes": notes, "predicted": "PROVED"}

def walk(x, f):
    f(x)
    if isinstance(x, dict): [walk(v, f) for v in x.values()]
    if isinstance(x, list): [walk(v, f) for v in x]

def build():
    facts = json.loads((ROOT / FACTS).read_text())
    names = {a["name"] for a in facts["actions"]}
    msgs = set(map(str, facts["reasons"].values())) | set(facts["reasons"].keys())
    out = ROOT / "laws" / MS; out.mkdir(parents=True, exist_ok=True)
    setups = {}
    for lid, setup, st, why in SCEN:
        def chk(x):
            if isinstance(x, dict) and "act" in x: assert x["act"] in names, (lid, x["act"])
            if isinstance(x, dict) and "reason" in x: assert x["reason"] in msgs, (lid, x["reason"])
            if isinstance(x, dict) and "obsv" in x: assert x["obsv"] in facts["observers"], (lid, x["obsv"])
        walk(st, chk)
        json.dump(law(f"L_{lid}", st, why), open(out / f"L_{lid}.json", "w"), indent=2, sort_keys=True)
        setups.setdefault(json.dumps(setup, sort_keys=True), lid)
    for key, lid in setups.items():
        st = {"eq": [{"fn": "runs_ok", "args": [{"trace": json.loads(key)}, {"s0": {}}]}, {"bool": True}]}
        json.dump(law(f"L_setup_{lid}", st, "setup trace of " + lid + " runs ok", "GUARD", "setup"),
                  open(out / f"L_setup_{lid}.json", "w"), indent=2, sort_keys=True)

if __name__ == "__main__":
    build()
