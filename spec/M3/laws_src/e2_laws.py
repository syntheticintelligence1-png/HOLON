"""M3 E2 scenario laws (lead-authored, preregistered before any run) on the E2 facts.
Messenger: O34/F8 replay budget (DISCH blocked invariant), O29/F8 payer/bearer (SORT).
Router: O3/F14 verifier routing. Every law is predicted PROVED; for the O29 and O34 laws a
PROVED result IS the finding (the mismatch holds on the extracted model).
    python3 spec/M3/laws_src/e2_laws.py   ->  laws/M3_msg/, laws/M3_router/
"""
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FACTS = {"M3_msg": "spec/M3/extracted/l1messenger.json", "M3_router": "spec/M3/extracted/mvrv.json"}

def act(_nm, **a):
    v = lambda x: {"bool": x} if isinstance(x, bool) else {"nat": x}
    return {"act": _nm, "args": {k: v(x) for k, x in a.items()}}
def run_of(setup): return {"run": {"trace": setup}, "from": {"s0": {}}}

# messenger: 5 = original sender, 6 = third-party replayer, 1 = owner; maxReplayTimes = 3 initially
def send(xh=11, who=5, value=4, amt=4): return act("sendMessage", who=who, to=9, val=0, gl=1, xh=xh, value=value, mn=0, amt=amt)
def rep(who=6, xh=11, value=4, frm=5, amt=4, qi=1): return act("replayMessage", who=who, xh=xh, value=value, qi=qi, **{"from": frm}, mn=0, amt=amt)
def wl(sub, b=True): return act("setWhitelist", who=0, sub=sub, b=b)
W = act("wait", dt=1)
S = [W, send()]
EX = S + [rep(qi=1), rep(qi=2), rep(qi=3)]
# router: owner 1; updateVerifier(v, st, a, lfi)
def upd(v, st, a, lfi, who=1): return act("updateVerifier", who=who, v=v, st=st, a=a, lfi=lfi)
U1 = [upd(0, 10, 3, 5)]
U2 = U1 + [upd(0, 20, 4, 15)]

def ok(setup, probe): return {"eq": [{"fn": "last_ok", "args": [{"step": probe, "from": run_of(setup)}]}, {"bool": True}]}
def rev(setup, probe, m): return {"eq": [{"fn": "no_code", "args": [{"obs": {"trace": [probe]}, "from": run_of(setup)}, {"reason": m}]}, {"bool": False}]}
def obs(setup, name, args, val): return {"eq": [{"obsv": name, "of": run_of(setup), "args": [{"nat": x} for x in args]}, {"nat": val}]}

SCEN = {
  "M3_msg": [
    ("msg_replay_ok", "GUARD", S, ok(S, rep()), "third party replays a sent message, paying the fee"),
    ("msg_no_replay_unsent", "GUARD", S, rev(S, rep(xh=12), "Provided message has not been enqueued"), ":193"),
    ("msg_budget_exhausts", "DISCH", EX, rev(EX, rep(qi=4), "Exceed maximum replay times"), "O34: :226 after maxReplayTimes = 3 replays"),
    ("msg_budget_blocks_sender", "DISCH", EX, rev(EX, rep(who=5, qi=4), "Exceed maximum replay times"),
     "O34/F8: the original sender has no exit once a third party burned the budget (no writer of __isL1MessageDropped)"),
    ("msg_budget_owner_lifts", "DISCH", EX + [act("updateMaxReplayTimes", who=1, val=4)],
     ok(EX + [act("updateMaxReplayTimes", who=1, val=4)], rep(qi=4)), "O34: the only exit is the owner raising maxReplayTimes"),
    ("msg_waiver_follows_origin", "SORT", [W, wl(5), send(value=0)], ok([W, wl(5), send(value=0)], rep(value=0)),
     "O29/F8: waiver keyed on _from = 5; non-whitelisted caller 6 replays paying 0"),
    ("msg_waiver_not_caller", "SORT", [W, wl(6), send()], rev([W, wl(6), send()], rep(value=0), "Insufficient msg.value for fee"),
     "O29: a whitelisted caller replaying a non-whitelisted origin's message still pays"),
  ],
  "M3_router": [
    ("rt_unregistered_zero", "PAR", [], obs([], "verifier_of", [1, 100], 0), "O3/F14: unregistered version routes to address(0)"),
    ("rt_latest", "PAR", U1, obs(U1, "verifier_of", [0, 10], 3), ":100 latest verifier from its start index"),
    ("rt_before_start", "PAR", U1, obs(U1, "verifier_of", [0, 9], 0), ":117 not found (source reverts; model 0 = debt)"),
    ("rt_legacy", "PAR", U2, obs(U2, "verifier_of", [0, 15], 3), ":108-113 legacy verifier below the new start"),
    ("rt_latest2", "PAR", U2, obs(U2, "verifier_of", [0, 25], 4), "latest after a second update"),
    ("rt_finalized_start", "GUARD", [], rev([], upd(0, 5, 3, 5), "ErrorStartBatchIndexFinalized"), ":149 start <= lastFinalizedBatchIndex"),
    ("rt_same_start_replaces", "PAR", U1 + [upd(0, 10, 4, 5)], obs(U1 + [upd(0, 10, 4, 5)], "verifier_of", [0, 10], 4), ":157-163 same start replaces in place"),
  ],
}

def law(lid, ms, rule, st, notes, subform="scenario"):
    f = FACTS[ms]
    return {"ir_version": "holon-ir/0.2", "law_id": lid, "milestone": ms, "rule": rule, "subform": subform, "facts": f,
            "facts_sha256": hashlib.sha256((ROOT / f).read_bytes()).hexdigest(),
            "statement": {"binders": [], "assume": [], "claim": st}, "notes": notes, "predicted": "PROVED"}

def build():
    for ms, rows in SCEN.items():
        names = {a["name"] for a in json.loads((ROOT / FACTS[ms]).read_text())["actions"]} | {"wait"}
        out = ROOT / "laws" / ms; out.mkdir(parents=True, exist_ok=True)
        setups = {}
        for lid, rule, setup, st, why in rows:
            for a in setup:
                assert a["act"] in names, (ms, lid, a["act"])
            json.dump(law(f"L_{lid}", ms, rule, st, why), open(out / f"L_{lid}.json", "w"), indent=2, sort_keys=True)
            if setup:
                setups.setdefault(json.dumps(setup, sort_keys=True), lid)
        for key, lid in setups.items():
            st = {"eq": [{"fn": "runs_ok", "args": [{"trace": json.loads(key)}, {"s0": {}}]}, {"bool": True}]}
            json.dump(law(f"L_setup_{lid}", ms, "GUARD", st, "setup trace of " + lid + " runs ok", "setup"),
                      open(out / f"L_setup_{lid}.json", "w"), indent=2, sort_keys=True)

if __name__ == "__main__":
    build()
