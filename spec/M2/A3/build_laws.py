"""A3 scenario laws (lead-authored), written from Rollup.sol @3e44e79 BEFORE any A3 run.
Same shape and helpers as A2 (spec/M2/A2/build_laws.py); laws name reverts by message.
Targets boundaries A2 never probed: commitState, version bound, the challengeState bump of
lfi+1, finalize below LFI / twice, multi-count revert, revert of an uncommitted index."""
import importlib.util, json, sys
from pathlib import Path

_A2 = Path(__file__).resolve().parents[1] / "A2" / "build_laws.py"
_spec = importlib.util.spec_from_file_location("a2_build_laws", _A2)
a2 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(a2)
act, msg, wait, cb, ch, fin, rv, run_of, law = a2.act, a2.msg, a2.wait, a2.cb, a2.ch, a2.fin, a2.rv, a2.run_of, a2.law
C1, C2 = a2.C1, a2.C2

def cs(parent, prev, post, blob=0, who=2, n=1, ver=1):
    return act("commitState", who=who, ver=ver, parent=parent, n=n, lbn=parent + 1, prev=prev, post=post, blobs=[blob])

R = C2 + [rv(2)]          # batch 2 reverted at t=10; batchBlobVersionedHashes[2] = 8 stays stored
F1 = C1 + [wait(40), fin(1)]  # batch 1 finalized at t=50; batchDataStore[0] deleted

SCEN = [  # (law_id, setup, probe, kind, why); rev kinds carry the revert MESSAGE
  ("cb_v3_invalid", [msg], cb(0, 100, 101, 7, ver=3), ("rev", "invalid version"), ":293 version <= 2"),
  ("cb_v2_ok", [msg], cb(0, 100, 101, 7, ver=2), ("ok",), ":293 boundary version = 2, one blob"),
  ("cs_ok", R + [msg], cs(1, 101, 102), ("ok",), ":273-286 recommit from the stored blob hash"),
  ("cs_lci", R + [msg], cs(1, 101, 102), ("lci", 2), "commitState commits batch parent+1"),
  ("cs_carry_blob", R + [msg], cs(1, 101, 102, blob=8), ("rev", "commitState must not carry blob"), ":276 blobhash(0) == 0"),
  ("cs_no_stored", C1 + [msg], cs(1, 101, 102), ("rev", "no stored blob hash for this batch"), ":279 stored hash at parent+1"),
  ("cs_delay_ok", R + [wait(20)], cs(1, 101, 102, n=0), ("ok",), ":281 enqueue + delay < t false at t = 30"),
  ("cs_delay_hit", R + [wait(21)], cs(1, 101, 102, n=0), ("rev", "l1msg delay"), ":281-283 delay exceeded at t = 31, n = 0"),
  ("cs_not_active", R + [msg], cs(1, 101, 102, who=4), ("rev", "only active submitter allowed"), "onlyActiveStaker"),
  ("rv_bad_hash", C2, rv(3), ("rev", "incorrect batch hash"), ":436 committedBatches[3] is empty"),
  ("rv_two", C2, rv(1, count=2), ("lci", 0), ":443 lastCommittedBatchIndex = batchIndex - 1"),
  ("rv_two_clears", C2 + [rv(1, count=2)], ch(2), ("rev", "incorrect batch hash"), ":444-462 loop clears committedBatches[2]"),
  ("ch_bumps_first", C2 + [ch(2), wait(40)], fin(1), ("rev", "batch in challenge window"), ":489-491 bump starts at lfi+1: batch 1 at 60"),
  ("ch_bumps_first_over", C2 + [ch(2), wait(50)], fin(1), ("ok",), "batch 1 finalizable at t = 60"),
  ("fin_twice", F1, fin(1), ("rev", "batch already verified"), ":640 finalizedStateRoots[1] != 0"),
  ("fin_below_lfi", F1, fin(0), ("rev", "batch not exist"), ":630/:704 batchDataStore[0] deleted by finalize(1)"),
]

def claim(setup, probe, kind):
    if kind[0] == "rev":
        return {"eq": [{"fn": "no_code", "args": [{"obs": {"trace": [probe]}, "from": run_of(setup)}, {"reason": kind[1]}]}, {"bool": False}]}
    return a2.claim(setup, probe, kind)

def build(out: Path, milestone="A3"):
    out.mkdir(parents=True, exist_ok=True)
    setups = {}
    for lid, setup, probe, kind, why in SCEN:
        json.dump(law(f"L_a3_{lid}", milestone, claim(setup, probe, kind), why), open(out / f"L_a3_{lid}.json", "w"), indent=2, sort_keys=True)
        setups.setdefault(json.dumps(setup, sort_keys=True), lid)
    for key, lid in setups.items():
        st = {"eq": [{"fn": "runs_ok", "args": [{"trace": json.loads(key)}, {"s0": {}}]}, {"bool": True}]}
        json.dump(law(f"L_a3_setup_{lid}", milestone, st, "setup trace of " + lid + " runs ok (guards against vacuous probes)", subform="setup"),
                  open(out / f"L_a3_setup_{lid}.json", "w"), indent=2, sort_keys=True)

if __name__ == "__main__":
    build(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "A3")
