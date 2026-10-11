#!/usr/bin/env python3
"""Hand-authored M1 law statements (holon-ir/0.2) and preregistered predictions.

    python3 proposals/M1/author_laws.py
writes proposals/M1/laws/L_*.json, proposals/M1/laws/REGISTRY.json, proposals/M1/predictions/M1.json.
Statement hashes use holon.ir.statement_hash, the same as M0.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from holon.ir import statement_hash  # noqa: E402

SM = "proposals/M1/facts/rollup_sm.json"
HDR = "proposals/M1/facts/morph_header_m1.json"

def sha(rel): return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()

# ---- statement DSL (holon-ir/0.2, kind "sm") ----
def c(n): return {"c": n}
def v(x): return {"var": x}
def st(state, f): return {"st": [state, f]}
def arr(state, f, i): return {"arr": [state, f, i]}
def add(x, y): return {"add": [x, y]}
def eq(x, y): return {"eq": [x, y]}
def ne(x, y): return {"ne": [x, y]}
def le(x, y): return {"le": [x, y]}
def lt(x, y): return {"lt": [x, y]}
def AND(*xs): return {"and": list(xs)}
def NOT(x): return {"not": x}
def IFF(x, y): return {"iff": [x, y]}
def IMPL(x, y): return {"implies": [x, y]}
def ALL_IDX(j, body): return {"forall_idx": j, "range": "0..N", "body": body}
def in_chal(state, i):
    return AND(ne(arr(state, "chal_challenger", i), c(0)), eq(arr(state, "chal_finished", i), c(0)))
def step(bind, frm, act, **params): return {"bind": bind, "from": frm, "act": act, "params": params}
def enabled(frm, act): return {"enabled": {"from": frm, "act": act}}
def tag(frm, act, **params): return {"outcome_tag": {"from": frm, "act": act, "params": params}}
def reach_within(frm, J, roles, goal): return {"reach_within": {"from": frm, "J": J, "roles": roles, "goal_state": "t", "goal": goal}}

NON_OWNER = ["submitter", "challenger", "anyone", "env"]
NON_OWNER_NON_SUBMITTER = ["challenger", "anyone", "env"]

def sm(law_id, rule, subform, K, statement, notes, evidence=("E1",)):
    stmt = {"kind": "sm", "bound": {"N": "facts.config.N", "K": K}, "forall_reach": "s"}
    stmt.update(statement)
    return {"ir_version": "holon-ir/0.2", "law_id": law_id, "milestone": "M1", "rule": rule, "subform": subform,
            "evidence": list(evidence), "facts": SM, "facts_sha256": sha(SM), "statement": stmt, "notes": notes}

LAWS = [
  sm("L_undo_commit_revert", "UNDO", "inverse_pair", 5, {
      "forall_params": [{"name": "act", "domain": ["commitBatch", "commitState", "commitBatchWithProof"]},
                        {"name": "n", "domain": [0, 1]}, {"name": "r", "domain": [1, 2]}],
      "steps": [step("s1", "s", "$act", numL1=v("n"), post=v("r")),
                step("s2", "s1", "revertBatch", idx=st("s1", "lastCommitted"), count=c(1))],
      "claim": {"state_eq": ["s", "s2"], "except": []}},
     "revertBatch undoes a successful commit exactly (all modelled storage)."),
  sm("L_undo_enabled", "UNDO", "inverse_pair_observational", 5, {
      "forall_params": [{"name": "n", "domain": [0, 1]}, {"name": "r", "domain": [1, 2]}],
      "steps": [step("s1", "s", "commitBatch", numL1=v("n"), post=v("r")),
                step("s2", "s1", "revertBatch", idx=st("s1", "lastCommitted"), count=c(1))],
      "claim": IFF(enabled("s", "commitBatch"), enabled("s2", "commitBatch"))},
     "After commitBatch then revertBatch, commitBatch (with a fresh blob) is enabled iff it was enabled before."),
  sm("L_undo_pause", "UNDO", "emergency_cancel", 5, {
      "forall_params": [{"name": "i", "domain": "1..N"}],
      "steps": [step("s1", "s", "challengeState", i=v("i")),
                step("s2", "s1", "setPause", b=c(1)),
                step("s3", "s2", "setPause", b=c(0))],
      "claim": AND({"arr_eq": ["s", "s3", "fin_ts"]}, {"arr_eq": ["s", "s3", "chal_challenger"]},
                   {"arr_eq": ["s", "s3", "chal_start"]}, eq(st("s", "inChallenge"), st("s3", "inChallenge")))},
     "A challenge cancelled by setPause(true) followed by setPause(false) leaves no residue on finalize timestamps or challenge state."),
  sm("L_disch_nonowner", "DISCH", "obligation_discharge", 5, {
      "assume": [ne(st("s", "revertReqIndex"), c(0))],
      "claim": reach_within("s", 3, NON_OWNER, eq(st("t", "revertReqIndex"), c(0)))},
     "A pending revert request (set by a successful challenge) can be discharged by non-owner actions within J steps."),
  sm("L_disch_timeout", "DISCH", "obligation_discharge", 5, {
      "assume": [eq(st("s", "inChallenge"), c(1)),
                 lt(add(arr("s", "chal_start", st("s", "batchChallenged")), {"k": "P"}), st("s", "now"))],
      "claim": reach_within("s", 3, NON_OWNER_NON_SUBMITTER, eq(st("t", "inChallenge"), c(0)))},
     "Once a challenge's proof window has passed, parties other than the submitter and the owner can close it within J steps."),
  sm("L_nat_delay_frontier", "NAT", "frontier_commutation", 5, {
      "assume": [lt(c(0), st("s", "q_len")),
                 eq(arr("s", "hdr_total", st("s", "lastCommitted")), st("s", "q_len"))],
      "claim": ne(tag("s", "commitBatch", numL1=c(0), post=c(1)), {"tag": "l1msg delay"})},
     "If every enqueued L1 message is already included in a committed batch, the delay guard does not force numL1Messages > 0."),
  sm("L_inv_prefix", "FACT", "invariant", 3, {
      "claim": AND(le(st("s", "lastFinalized"), st("s", "lastCommitted")),
                   ALL_IDX("j", IFF(ne(arr("s", "committed", v("j")), c(0)), le(v("j"), st("s", "lastCommitted")))),
                   ALL_IDX("j", IMPL(le(v("j"), st("s", "lastFinalized")), ne(arr("s", "finalized_root", v("j")), c(0)))))},
     "Committed batches form a gap-free prefix that contains the finalized prefix; finalized roots are nonzero."),
  sm("L_inv_one_challenge", "FACT", "invariant", 3, {
      "claim": AND(IFF(eq(st("s", "inChallenge"), c(1)), in_chal("s", st("s", "batchChallenged"))),
                   ALL_IDX("j", IMPL(ne(v("j"), st("s", "batchChallenged")), NOT(in_chal("s", v("j"))))))},
     "inChallenge holds exactly when batchChallenged is in challenge, and no other batch is."),
]

ZERO32 = "0x" + "00" * 32
PAR_V2 = {"ir_version": "holon-ir/0.2", "law_id": "L_par_hdr_v2_composed", "milestone": "M1", "rule": "PAR",
          "subform": "cross_component_codec_composed", "evidence": ["E1", "E6"], "facts": HDR, "facts_sha256": sha(HDR),
          "statement": {"forall": [{"name": "h", "type": "Header"}],
                        "assume": [{"eq": [{"field": "version", "of": {"var": "h"}}, {"bytes": "0x02"}]},
                                   {"eq": [{"field": "sequencerSetVerifyHash", "of": {"var": "h"}}, {"bytes": ZERO32}]}],
                        "claim": {"eq": [{"call": "enc_sol", "args": [{"var": "h"}]},
                                         {"call": "enc_go_v2_producer", "args": [{"var": "h"}]}]}},
          "notes": "M0's L_par_hdr_v2 obstruction composed with the real v2 producer (batch_cache.go: V1.Bytes() then h[0] = 2). blobVersionedHash is a shared input: both sides aggregate keccak(concat blob hashes) (Rollup.sol _computeBlobVersionedHash, batch_cache.go aggregateBlobHashes)."}

PREDICTIONS = {"milestone": "M1", "preregistered": "before any mechanized M1 run (commit order is the evidence)",
  "statuses": ["PROVED", "REFUTED", "UNKNOWN"], "laws": [
  {"law_id": "L_undo_commit_revert", "status": "REFUTED", "triage": "intent_question",
   "witness_example": {"trace": "init", "act": "commitBatch", "residue": ["blob[1]", "origin[1]", "fin_ts[1]", "state_root[1]", "hdr_*[1]", "submitter[1]"]},
   "explanation": "revertBatch zeroes committedBatches and challenges only; batchBlobVersionedHashes, batchDataStore and committedStateRoots stay."},
  {"law_id": "L_undo_enabled", "status": "REFUTED", "triage": "intent_question",
   "explanation": "The residual blob hash makes commitBatch revert with 'commitBatch requires no stored blob hash'; commitState is the designed recommit path."},
  {"law_id": "L_undo_pause", "status": "REFUTED", "triage": "finding_candidate",
   "explanation": "setPause(true) deletes the challenge but keeps the +proofWindow added to every other unfinalized batch's finalizeTimestamp; the batch can then be re-challenged and the extension repeats."},
  {"law_id": "L_disch_nonowner", "status": "REFUTED", "triage": "intent_question",
   "explanation": "_challengerWin sets revertReqIndex; nonReqRevert blocks every non-owner state transition; only revertBatch (onlyOwner) clears it."},
  {"law_id": "L_disch_timeout", "status": "REFUTED", "triage": "finding_candidate",
   "explanation": "proveState is onlyActiveSubmitter; commits revert on proveRemainingTime underflow; challengeState is blocked by inChallenge. Only the submitter (self-slashing) or the owner can close a timed-out challenge."},
  {"law_id": "L_nat_delay_frontier", "status": "REFUTED", "triage": "intent_question",
   "explanation": "getFirstUnfinalizedMessageEnqueueTime reads pendingQueueIndex, advanced only by finalizeBatch. A delay until permissionless finalization, not a freeze."},
  {"law_id": "L_inv_prefix", "status": "PROVED", "bound_note": "PROVED relative to N and K only"},
  {"law_id": "L_inv_one_challenge", "status": "PROVED", "bound_note": "PROVED relative to N and K only"},
  {"law_id": "L_par_hdr_v2_composed", "status": "PROVED"},
]}

def main():
    out = HERE / "laws"; out.mkdir(parents=True, exist_ok=True)
    reg = {"milestone": "M1", "facts": {SM: sha(SM), HDR: sha(HDR)}, "laws": {}}
    for law in LAWS + [PAR_V2]:
        (out / f"{law['law_id']}.json").write_text(json.dumps(law, indent=2, sort_keys=True) + "\n")
        reg["laws"][law["law_id"]] = statement_hash(law)
    (out / "REGISTRY.json").write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n")
    pdir = HERE / "predictions"; pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "M1.json").write_text(json.dumps(PREDICTIONS, indent=2, sort_keys=True) + "\n")
    print("wrote", len(reg["laws"]), "laws")

if __name__ == "__main__":
    main()
