"""A2 scenario laws (lead-authored). Closed single-equation laws over the Rollup machine,
written from Rollup.sol @3e44e79 BEFORE any A2 run. Each probe's observations are taken
from the state its setup reaches (obs clears the log), so a law speaks only of the probe.
Kinds: rev(k) = the probe reverts with reason code k; ok = the probe succeeds;
lci(n) = lci_of after the probe equals n; setup = the setup trace runs ok."""
import hashlib, json, sys
from pathlib import Path

FACTS = "spec/M1/facts/morph_rollup.json"
def act(_nm, **a):
    v = lambda x: {"nats": x} if isinstance(x, list) else {"bool": x} if isinstance(x, bool) else {"nat": x}
    return {"act": _nm, "args": {k: v(x) for k, x in a.items()}}
msg = act("sendMessage", who=5)
def wait(dt): return act("wait", dt=dt)
def cb(parent, prev, post, blob, who=2, n=1, ver=1):
    return act("commitBatch", who=who, ver=ver, parent=parent, n=n, lbn=parent + 1, prev=prev, post=post, blobs=[blob])
def ch(idx, who=4, value=1): return act("challengeState", who=who, idx=idx, value=value)
def pr(idx, proof=1, who=2): return act("proveState", who=who, idx=idx, proof=proof)
def fin(idx, who=5): return act("finalizeBatch", who=who, idx=idx)
def rv(idx, count=1, who=1): return act("revertBatch", who=who, idx=idx, count=count)
def pause(st, who=1): return act("setPause", who=who, status=st)

# s0: t=10, lfi=0, W=10, F=40, D=20, DEP=1, owner 1, submitters 2,3, challenger 4.
C1 = [msg, cb(0, 100, 101, 7)]                 # batch 1 at t=10, finalizeTimestamp 50
C2 = C1 + [msg, cb(1, 101, 102, 8)]            # batch 2 at t=10, finalizeTimestamp 50

SCEN = [  # (law_id, setup, probe, kind, why)
  ("ch_not_challenger", C1, ch(1, who=5), ("rev", 28), "Rollup.sol:126 onlyChallenger"),
  ("ch_paused", C1 + [pause(True)], ch(1), ("rev", 3), "whenNotPaused"),
  ("ch_in_challenge", C2 + [ch(1)], ch(2), ("rev", 29), ":475 require(!inChallenge)"),
  ("ch_finalized", C1, ch(0), ("rev", 30), ":476 lastFinalizedBatchIndex < batchIndex"),
  ("ch_next_unfinalized_ok", C1, ch(1), ("ok",), ":476 boundary idx = lfi+1"),
  ("ch_beyond_lci", C1, ch(2), ("rev", 25), ":477 batch hash of an uncommitted index"),
  ("ch_rechallenge", C1 + [ch(1), pr(1)], ch(1), ("rev", 32), ":479 challenger == 0"),
  ("ch_window_closed", C1 + [wait(40)], ch(1), ("rev", 33), ":481 finalizeTimestamp > t, at t = 50"),
  ("ch_window_last_second", C1 + [wait(39)], ch(1), ("ok",), ":481 boundary t = 49"),
  ("ch_no_deposit", C1, ch(1, value=0), ("rev", 34), ":483 msg.value >= minDeposit"),
  ("pr_not_active", C1 + [ch(1)], pr(1, who=4), ("rev", 1), "onlyActiveStaker"),
  ("pr_no_challenge", C1, pr(1), ("rev", 35), ":606 batchInChallenge"),
  ("pr_bad_proof", C1 + [ch(1)], pr(1, proof=2), ("rev", 22), "verifier rejects"),
  ("pr_zero_proof_in_window", C1 + [ch(1), wait(9)], pr(1, proof=0), ("rev", 21), "no timeout at t = start+W-1"),
  ("pr_timeout_ok", C1 + [ch(1), wait(10)], pr(1, proof=0), ("ok",), "timeout at t = start+W: proof unchecked"),
  ("pr_timeout_blocks_commit", C1 + [ch(1), wait(10), pr(1, proof=0), msg], cb(1, 101, 102, 8), ("rev", 2), "timeout sets revertReqIndex"),
  ("pr_clears_challenge", C2 + [ch(1), pr(1)], ch(2), ("ok",), "proveState sets inChallenge = false"),
  ("fin_in_window", C1 + [wait(39)], fin(1), ("rev", 37), ":633 batchInsideChallengeWindow at t = 49"),
  ("fin_window_over_ok", C1 + [wait(40)], fin(1), ("ok",), ":633 boundary t = 50"),
  ("fin_then_unchallengeable", C1 + [wait(40), fin(1)], ch(1), ("rev", 30), "finalize advances lastFinalizedBatchIndex"),
  ("fin_in_challenge", C1 + [ch(1), wait(100)], fin(1), ("rev", 35), ":631 batchInChallenge"),
  ("fin_after_proof_ok", C1 + [ch(1), pr(1), wait(100)], fin(1), ("ok",), "proved challenge no longer blocks"),
  ("fin_out_of_order", C2 + [wait(100)], fin(2), ("rev", 14), ":635 finalizedStateRoots[i-1] == prevStateRoot"),
  ("fin_bump_others", C2 + [ch(1), pr(1), wait(40)], fin(2), ("rev", 37), ":490-491 other batches get +proofWindow: batch 2 at 60"),
  ("fin_bump_others_over", C2 + [ch(1), pr(1), wait(40), fin(1), wait(10)], fin(2), ("ok",), "batch 2 finalizable at t = 60"),
  ("rv_not_owner", C2, rv(2, who=2), ("rev", 23), "onlyOwner"),
  ("rv_zero_count", C2, rv(2, count=0), ("rev", 24), ":431 count > 0"),
  ("rv_not_from_end", C2, rv(1), ("rev", 26), ":439 reverting must start from the ending"),
  ("rv_finalized", C1 + [wait(40), fin(1)], rv(1), ("rev", 27), ":441 batchIndex > lastFinalizedBatchIndex"),
  ("rv_lci", C2, rv(2), ("lci", 1), ":443 lastCommittedBatchIndex = batchIndex - 1"),
  ("rv_clears_challenge", C2 + [ch(2), rv(2)], ch(1), ("ok",), ":451 revert of the challenged batch clears inChallenge"),
  ("cb_not_active", [msg], cb(0, 100, 101, 7, who=4), ("rev", 1), "onlyActiveStaker"),
  ("cb_recommit", C1 + [msg], cb(0, 100, 101, 9), ("rev", 4), ":261 batchBlobVersionedHashes[next] == 0"),
  ("cb_wrong_parent", C1 + [msg], cb(5, 101, 102, 8), ("rev", 12), ":312 parent index == lastCommittedBatchIndex"),
  ("cb_wrong_prev", C1 + [msg], cb(1, 99, 102, 8), ("rev", 14), ":314 prevStateRoot"),
  ("cb_zero_post", [msg], cb(0, 100, 0, 7), ("rev", 10), ":295 postStateRoot != 0"),
  ("cb_queue_overrun", [msg], cb(0, 100, 101, 7, n=2), ("rev", 15), "L1MessageQueue:108 index < length"),
  ("cb_delay_ok", [msg, wait(20)], cb(0, 100, 101, 7, n=0), ("ok",), ":262-266 enqueue + delay >= t at t = 30"),
  ("cb_delay_hit", [msg, wait(21)], cb(0, 100, 101, 7, n=0), ("rev", 5), ":262-266 l1msg delay at t = 31"),
  ("cb_challenge_expired", C1 + [ch(1), wait(11), msg], cb(1, 101, 102, 8), ("rev", 16), ":363 checked underflow (Panic 0x11)"),
  ("cb_challenge_last_second", C1 + [ch(1), wait(10), msg], cb(1, 101, 102, 8), ("ok",), ":363 boundary t = start+W"),
  ("cb_remaining_time", C1 + [ch(1), wait(5), msg, cb(1, 101, 102, 8), pr(1), wait(44)], ch(2), ("ok",), ":368 batch 2 finalizeTimestamp = 15+40+5 = 60 > 59"),
  ("sp_not_owner", C1, pause(True, who=2), ("rev", 23), "onlyOwner"),
  ("sp_cancel_then_rechallenge", C1 + [ch(1), pause(True), pause(False)], ch(1), ("ok",), "setPause(true) deletes the challenge"),
  ("sp_unpause_unpaused", C1, pause(False), ("rev", 39), "Pausable: not paused"),
]

def run_of(setup): return {"run": {"trace": setup}, "from": {"s0": {}}}
# Reason codes are per-facts-file numbering (the S1 extraction numbers them differently), so a
# law names a revert by its message; the emitter resolves {"reason": msg} against the facts file
# it is built on. The preregistered codes (eb4a3d0) are mapped through the hand facts' table.
REASONS = json.loads((Path(__file__).resolve().parents[3] / FACTS).read_text())["reasons"]
def claim(setup, probe, kind):
    if kind[0] == "rev":
        return {"eq": [{"fn": "no_code", "args": [{"obs": {"trace": [probe]}, "from": run_of(setup)}, {"reason": REASONS[str(kind[1])]}]}, {"bool": False}]}
    if kind[0] == "ok":
        return {"eq": [{"fn": "last_ok", "args": [{"step": probe, "from": run_of(setup)}]}, {"bool": True}]}
    if kind[0] == "lci":
        return {"eq": [{"obsv": "lci_of", "of": {"step": probe, "from": run_of(setup)}}, {"nat": kind[1]}]}
    raise ValueError(kind)

def law(lid, milestone, st, notes, rule="GUARD", subform="scenario"):
    return {"ir_version": "holon-ir/0.2", "law_id": lid, "milestone": milestone, "rule": rule, "subform": subform,
            "facts": FACTS, "facts_sha256": hashlib.sha256((Path(__file__).resolve().parents[3] / FACTS).read_bytes()).hexdigest(),
            "statement": {"binders": [], "assume": [], "claim": st}, "notes": notes, "predicted": "PROVED"}

def build(out: Path, milestone="A2"):
    out.mkdir(parents=True, exist_ok=True)
    setups = {}
    for lid, setup, probe, kind, why in SCEN:
        json.dump(law(f"L_a2_{lid}", milestone, claim(setup, probe, kind), why), open(out / f"L_a2_{lid}.json", "w"), indent=2, sort_keys=True)
        setups.setdefault(json.dumps(setup, sort_keys=True), lid)
    for key, lid in setups.items():
        st = {"eq": [{"fn": "runs_ok", "args": [{"trace": json.loads(key)}, {"s0": {}}]}, {"bool": True}]}
        json.dump(law(f"L_a2_setup_{lid}", milestone, st, "setup trace of " + lid + " runs ok (guards against vacuous probes)", subform="setup"),
                  open(out / f"L_a2_setup_{lid}.json", "w"), indent=2, sort_keys=True)

if __name__ == "__main__":
    build(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "A2")
