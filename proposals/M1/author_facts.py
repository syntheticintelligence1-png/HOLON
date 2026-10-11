#!/usr/bin/env python3
"""Hand-authored M1 facts for Rollup.sol's batch state machine.

The semantics below are written by hand from the source. This script only
resolves each guard/effect's `code` snippet to its exact line in the Morph
checkout, so citations are not typed by hand, and writes canonical JSON.

    python3 proposals/M1/author_facts.py /path/to/morph   # -> proposals/M1/facts/rollup_sm.json
"""
import copy
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "facts" / "rollup_sm.json"
COMMIT = "3e44e795586af3e11285b603ab642c67823add51"
ROLLUP = "contracts/contracts/l1/rollup/Rollup.sol"
QUEUE = "contracts/contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol"
SUBMITTER = "contracts/contracts/l1/rollup/Submitter.sol"

# ---- tiny constructors for the DSL (documented in "dsl" below) ----
def c(n): return {"c": n}
def s(x): return {"s": x}
def a(x, i): return {"a": x, "i": i}
def p(x): return {"p": x}
def k(x): return {"k": x}
def add(x, y): return {"add": [x, y]}
def subc(x, y, tag): return {"subc": [x, y], "tag": tag}
def eq(x, y): return {"eq": [x, y]}
def ne(x, y): return {"ne": [x, y]}
def lt(x, y): return {"lt": [x, y]}
def le(x, y): return {"le": [x, y]}
def gt(x, y): return {"gt": [x, y]}
def AND(*xs): return {"and": list(xs)}
def OR(*xs): return {"or": list(xs)}
def NOT(x): return {"not": x}
def req(prop, tag, code, file=ROLLUP): return {"req": prop, "tag": tag, "code": code, "file": file}
def setv(lv, t, code, file=ROLLUP): return {"set": lv, "to": t, "code": code, "file": file}
def IF(prop, then, els=None, code=None, file=ROLLUP):
    d = {"if": prop, "then": then, "else": els or []}
    if code: d["code"], d["file"] = code, file
    return d
def FOR(var, frm, to_incl, body, while_=None, code=None):
    d = {"for": var, "from": frm, "to_incl": to_incl, "body": body}
    if while_ is not None: d["while"] = while_
    if code: d["code"], d["file"] = code, ROLLUP
    return d

# ---- shared sub-expressions ----
true = c(1)
def in_chal(i):  # Rollup.sol batchInChallenge
    return AND(ne(a("chal_challenger", i), c(0)), eq(a("chal_finished", i), c(0)))
def exists(i):   # batchExist
    return AND(gt(a("origin", i), c(0)), ne(a("committed", i), c(0)))
first_unfinalized = {"ite": [AND(lt(s("q_pending"), s("q_len")), ne(a("q_enq", s("q_pending")), c(0))),
                             a("q_enq", s("q_pending")), s("now")],
                     "code": "if (pendingQueueIndex < messageQueue.length && messageEnqueueTime[pendingQueueIndex] != 0)",
                     "file": QUEUE}
l1_delayed = lt(add(first_unfinalized, k("D")), s("now"))
modifier_nonreq = req(eq(s("revertReqIndex"), c(0)), "pending revert request", 'require(revertReqIndex == 0, "pending revert request");')
modifier_unpaused = req(eq(s("paused"), c(0)), "Pausable: paused", "whenNotPaused")
modifier_submitter = req(eq(s("submitter_active"), c(1)), "only active submitter allowed",
                         'require(ISubmitter(submitterContract).isActive(_msgSender()), "only active submitter allowed");')

PARENT = s("lastCommitted")   # abstraction A2
NEXT = add(PARENT, c(1))

def scoped(stmts, scope, file=ROLLUP):
    for st in stmts:
        st["scope"], st["scope_file"] = scope, file
        st.setdefault("file", file)
    return stmts

def commit_core(submitter_val, blob_term):
    """_commitBatchWithBatchData; the caller supplies an honest parent header (A1, A2)."""
    return scoped([
        req(le(c(1), c(2)), "invalid version", 'require(batchDataInput.version <= 2, "invalid version");'),
        req(ne(a("state_root", PARENT), c(0)), "previous state root is zero",
            'require(batchDataInput.prevStateRoot != bytes32(0), "previous state root is zero");'),
        req(ne(p("post"), c(0)), "new state root is zero",
            'require(batchDataInput.postStateRoot != bytes32(0), "new state root is zero");'),
        req(eq(a("committed", NEXT), c(0)), "batch already committed",
            'require(committedBatches[_batchIndex + 1] == bytes32(0), "batch already committed");'),
        req(le(add(a("hdr_total", PARENT), p("numL1")), s("q_len")), "message index out of range",
            'require(_queueIndex < messageQueue.length, "message index out of range");', QUEUE),
        {"bound": NEXT, "code": "_batchIndex := add(_batchIndex, 1) // increase batch index", "file": ROLLUP},
        setv(a("committed", NEXT), c(1), "committedBatches[_batchIndex] = BatchHeaderCodecV0.computeBatchHash(_batchPtr, _headerLength);"),
        setv(a("state_root", NEXT), p("post"), "committedStateRoots[_batchIndex] = batchDataInput.postStateRoot;"),
        setv(a("hdr_prev", NEXT), a("state_root", PARENT), "BatchHeaderCodecV0.storePrevStateHash(_batchPtr, batchDataInput.prevStateRoot);"),
        setv(a("hdr_num", NEXT), p("numL1"), "BatchHeaderCodecV0.storeL1MessagePopped(_batchPtr, batchDataInput.numL1Messages);"),
        setv(a("hdr_total", NEXT), add(a("hdr_total", PARENT), p("numL1")),
             "BatchHeaderCodecV0.storeTotalL1MessagePopped(_batchPtr, _totalL1MessagesPoppedOverall);"),
        setv(a("blob", NEXT), blob_term, "batchBlobVersionedHashes[_batchIndex] = blobVersionedHash;"),
        {"let": "prove_remaining",
         "be": {"ite": [eq(s("inChallenge"), c(1)),
                        subc(add(k("P"), a("chal_start", s("batchChallenged"))), s("now"), "panic: arithmetic underflow"),
                        c(0)]},
         "code": "proveRemainingTime = proofWindow + challenges[batchChallenged].startTime - block.timestamp;", "file": ROLLUP},
        setv(a("origin", NEXT), s("now"), "batchDataStore[_batchIndex] = BatchData("),
        setv(a("fin_ts", NEXT), add(add(s("now"), k("F")), {"var": "prove_remaining"}),
             "block.timestamp + finalizationPeriodSeconds + proveRemainingTime,"),
        setv(a("submitter", NEXT), submitter_val, "batchDataStore[_batchIndex] = BatchData("),
        setv(s("lastCommitted"), NEXT, "lastCommittedBatchIndex = _batchIndex;"),
    ], "function _commitBatchWithBatchData(")

def delay_guard():
    return IF(l1_delayed, [req(gt(p("numL1"), c(0)), "l1msg delay", 'require(batchDataInput.numL1Messages > 0, "l1msg delay");')],
              code="IL1MessageQueue(messageQueue).getFirstUnfinalizedMessageEnqueueTime() + rollupDelayPeriod < block.timestamp")

def delete_challenge(i, code):
    return [setv(a(f, i), c(0), code) for f in ("chal_challenger", "chal_finished", "chal_success", "chal_start")]

COMMIT_PARAMS = {"numL1": [0, 1], "post": [1, 2]}

actions = {
  "commitBatch": {"role": "submitter", "fn_line_code": "function commitBatch(", "params": COMMIT_PARAMS, "body": [
      modifier_submitter, modifier_nonreq, modifier_unpaused,
      req(eq(a("blob", NEXT), c(0)), "commitBatch requires no stored blob hash",
          'require(batchBlobVersionedHashes[_nextBatchIndex] == bytes32(0), "commitBatch requires no stored blob hash");'),
      delay_guard(),
  ] + commit_core(c(1), c(1))},
  "commitState": {"role": "submitter", "fn_line_code": "function commitState(", "params": COMMIT_PARAMS, "body": [
      modifier_submitter, modifier_nonreq, modifier_unpaused,
      req(true_eq := eq(c(0), c(0)), "commitState must not carry blob", 'require(blobhash(0) == bytes32(0), "commitState must not carry blob");'),
      req(ne(a("blob", NEXT), c(0)), "no stored blob hash for this batch",
          'require(batchBlobVersionedHashes[_nextBatchIndex] != bytes32(0), "no stored blob hash for this batch");'),
      delay_guard(),
  ] + commit_core(c(1), a("blob", NEXT))},
  "commitBatchWithProof": {"role": "anyone", "fn_line_code": "function commitBatchWithProof(", "params": COMMIT_PARAMS, "body": [
      modifier_nonreq, modifier_unpaused,
      {"let": "rollup_delay", "be": lt(add(a("origin", s("lastCommitted")), k("D")), s("now")),
       "code": "bool rollupDelay = batchDataStore[lastCommittedBatchIndex].originTimestamp + rollupDelayPeriod <", "file": ROLLUP},
      {"let": "l1_delayed", "be": l1_delayed,
       "code": "bool l1MsgQueueDelayed = IL1MessageQueue(messageQueue).getFirstUnfinalizedMessageEnqueueTime() +", "file": ROLLUP},
      IF(AND(NOT({"var": "rollup_delay"}), {"var": "l1_delayed"}),
         [req(gt(p("numL1"), c(0)), "l1msg delay", 'require(batchDataInput.numL1Messages > 0, "l1msg delay");')],
         code="if (!rollupDelay && l1MsgQueueDelayed) {"),
      req(OR({"var": "rollup_delay"}, {"var": "l1_delayed"}), "invalid timing", 'require(rollupDelay || l1MsgQueueDelayed, "invalid timing");'),
  ] + commit_core(c(0), {"ite": [ne(a("blob", NEXT), c(0)), a("blob", NEXT), c(1)]}) + [
      setv(a("fin_ts", s("lastCommitted")), s("now"), "batchDataStore[_batchIndex].finalizeTimestamp = block.timestamp;"),
  ]},
  "revertBatch": {"role": "owner", "fn_line_code": "function revertBatch(", "params": {"idx": "1..N", "count": "1..N"}, "body": [
      req(gt(p("count"), c(0)), "count must be nonzero", 'require(_count > 0, "count must be nonzero");'),
      req(ne(a("committed", p("idx")), c(0)), "incorrect batch hash", 'require(committedBatches[_batchIndex] == _batchHash, "incorrect batch hash");'),
      req(eq(a("committed", add(p("idx"), p("count"))), c(0)), "reverting must start from the ending",
          'require(committedBatches[_batchIndex + _count] == bytes32(0), "reverting must start from the ending");'),
      req(gt(p("idx"), s("lastFinalized")), "can only revert unFinalized batch",
          'require(_batchIndex > lastFinalizedBatchIndex, "can only revert unFinalized batch");'),
      setv(s("lastCommitted"), subc(p("idx"), c(1), "panic: arithmetic underflow"), "lastCommittedBatchIndex = _batchIndex - 1;"),
      FOR("j", p("idx"), add(p("idx"), subc(p("count"), c(1), "panic: arithmetic underflow")), while_=ne(a("committed", {"var": "j"}), c(0)),
          code="while (_count > 0) {", body=[
          setv(a("committed", {"var": "j"}), c(0), "committedBatches[_batchIndex] = bytes32(0);"),
          IF(in_chal({"var": "j"}), [setv(s("inChallenge"), c(0), "inChallenge = false;")], code="if (batchInChallenge(_batchIndex)) {"),
      ] + delete_challenge({"var": "j"}, "delete challenges[_batchIndex];") + [
          IF(AND(gt(s("revertReqIndex"), c(0)), eq({"var": "j"}, s("revertReqIndex"))),
             [setv(s("revertReqIndex"), c(0), "revertReqIndex = 0;")], code="if (revertReqIndex > 0 && _batchIndex == revertReqIndex) {"),
      ]),
  ]},
  "challengeState": {"role": "challenger", "fn_line_code": "function challengeState(", "params": {"i": "1..N"}, "body": [
      modifier_nonreq, modifier_unpaused,
      req(eq(s("inChallenge"), c(0)), "already in challenge", 'require(!inChallenge, "already in challenge");'),
      req(lt(s("lastFinalized"), p("i")), "batch already finalized", 'require(lastFinalizedBatchIndex < batchIndex, "batch already finalized");'),
      req(ne(a("committed", p("i")), c(0)), "incorrect batch hash", 'require(committedBatches[batchIndex] == _batchHash, "incorrect batch hash");'),
      req(exists(p("i")), "batch not exist", 'require(batchExist(batchIndex), "batch not exist");'),
      req(eq(a("chal_challenger", p("i")), c(0)), "batch already challenged", 'require(challenges[batchIndex].challenger == address(0), "batch already challenged");'),
      req(gt(a("fin_ts", p("i")), s("now")), "cannot challenge batch outside the challenge window",
          'require(batchInsideChallengeWindow(batchIndex), "cannot challenge batch outside the challenge window");'),
      setv(s("batchChallenged"), p("i"), "batchChallenged = batchIndex;"),
      setv(a("chal_challenger", p("i")), c(1), "challenges[batchIndex] = BatchChallenge(batchIndex, _msgSender(), msg.value, block.timestamp, false, false);"),
      setv(a("chal_start", p("i")), s("now"), "challenges[batchIndex] = BatchChallenge(batchIndex, _msgSender(), msg.value, block.timestamp, false, false);"),
      setv(a("chal_finished", p("i")), c(0), "challenges[batchIndex] = BatchChallenge(batchIndex, _msgSender(), msg.value, block.timestamp, false, false);"),
      setv(a("chal_success", p("i")), c(0), "challenges[batchIndex] = BatchChallenge(batchIndex, _msgSender(), msg.value, block.timestamp, false, false);"),
      FOR("j", add(s("lastFinalized"), c(1)), s("lastCommitted"), code="for (uint256 i = lastFinalizedBatchIndex + 1; i <= lastCommittedBatchIndex; i++) {", body=[
          IF(ne({"var": "j"}, p("i")), [setv(a("fin_ts", {"var": "j"}), add(a("fin_ts", {"var": "j"}), k("P")),
                                             "batchDataStore[i].finalizeTimestamp += proofWindow;")], code="if (i != batchIndex) {"),
      ]),
      setv(s("inChallenge"), c(1), "inChallenge = true;"),
  ]},
  "proveState": {"role": "submitter", "fn_line_code": "function proveState(", "params": {"i": "1..N"}, "body": [
      modifier_nonreq, modifier_unpaused, modifier_submitter,
      req(ne(a("committed", p("i")), c(0)), "incorrect batch hash", 'require(committedBatches[_batchIndex] == _batchHash, "incorrect batch hash");'),
      req(in_chal(p("i")), "batch in challenge", 'require(batchInChallenge(_batchIndex), "batch in challenge");'),
      setv(a("chal_finished", p("i")), c(1), "challenges[_batchIndex].finished = true;"),
      setv(s("inChallenge"), c(0), "inChallenge = false;"),
      IF(le(add(a("chal_start", p("i")), k("P")), s("now")), [
          setv(a("chal_success", p("i")), c(1), "challenges[_batchIndex].challengeSuccess = true;"),
          setv(s("revertReqIndex"), p("i"), "revertReqIndex = batchIndex;"),
          IF(eq(a("submitter", p("i")), c(1)), scoped([setv(s("submitter_active"), c(0), "registered[submitter] = false;", SUBMITTER)], "function slash(", SUBMITTER),
             code="if (submitter == address(0)) return 0;", file=SUBMITTER),
      ], [], code="if (challenges[_batchIndex].startTime + proofWindow <= block.timestamp) {"),
  ]},
  "finalizeBatch": {"role": "anyone", "fn_line_code": "function finalizeBatch(", "params": {}, "body": [
      {"let": "i", "be": add(s("lastFinalized"), c(1)), "code": 'require(lastFinalizedBatchIndex + 1 == _batchIndex, "incorrect batch index");', "file": ROLLUP},
      modifier_nonreq, modifier_unpaused,
      req(ne(a("committed", {"var": "i"}), c(0)), "incorrect batch hash", 'require(committedBatches[_batchIndex] == _batchHash, "incorrect batch hash");'),
      req(exists({"var": "i"}), "batch not exist", 'require(batchExist(_batchIndex), "batch not exist");'),
      req(NOT(in_chal({"var": "i"})), "batch in challenge", 'require(!batchInChallenge(_batchIndex), "batch in challenge");'),
      req(eq(a("chal_success", {"var": "i"}), c(0)), "batch should be revert", 'require(!batchChallengedSuccess(_batchIndex), "batch should be revert");'),
      req(NOT(gt(a("fin_ts", {"var": "i"}), s("now"))), "batch in challenge window", 'require(!batchInsideChallengeWindow(_batchIndex), "batch in challenge window");'),
      req(eq(a("finalized_root", subc({"var": "i"}, c(1), "panic: arithmetic underflow")), a("hdr_prev", {"var": "i"})), "incorrect previous state root",
          '"incorrect previous state root"'),
      req(eq(a("finalized_root", {"var": "i"}), c(0)), "batch already verified", 'require(finalizedStateRoots[_batchIndex] == bytes32(0), "batch already verified");'),
      setv(s("lastFinalized"), {"var": "i"}, "lastFinalizedBatchIndex = _batchIndex;"),
      setv(a("finalized_root", {"var": "i"}), a("state_root", {"var": "i"}), "finalizedStateRoots[_batchIndex] = BatchHeaderCodecV0.getPostStateHash(memPtr);"),
      IF(gt(a("hdr_num", {"var": "i"}), c(0)), [
          req(eq(s("q_pending"), subc(a("hdr_total", {"var": "i"}), a("hdr_num", {"var": "i"}), "panic: arithmetic underflow")),
              "start index mismatch", 'require(pendingQueueIndex == _startIndex, "start index mismatch");', QUEUE),
          setv(s("q_pending"), a("hdr_total", {"var": "i"}), "pendingQueueIndex = _startIndex + _count;", QUEUE),
      ], code="if (l1MessagePopped == 0) return;"),
  ] + [setv(a(f, subc({"var": "i"}, c(1), "panic: arithmetic underflow")), c(0), code) for f, code in [
          ("origin", "delete batchDataStore[_batchIndex - 1];"), ("fin_ts", "delete batchDataStore[_batchIndex - 1];"),
          ("submitter", "delete batchDataStore[_batchIndex - 1];"), ("state_root", "delete committedStateRoots[_batchIndex - 1];"),
          ("blob", "delete batchBlobVersionedHashes[_batchIndex - 1];")]]
    + delete_challenge(subc({"var": "i"}, c(1), "panic: arithmetic underflow"), "delete challenges[_batchIndex - 1];")},
  "setPause": {"role": "owner", "fn_line_code": "function setPause(", "params": {"b": [0, 1]}, "body": [
      IF(eq(p("b"), c(1)), [
          req(eq(s("paused"), c(0)), "Pausable: paused", "_pause();"),
          setv(s("paused"), c(1), "_pause();"),
          IF(eq(s("inChallenge"), c(1)), delete_challenge(s("batchChallenged"), "delete challenges[batchChallenged];")
             + [setv(s("inChallenge"), c(0), "inChallenge = false;")], code="if (inChallenge) {"),
      ], [
          req(eq(s("paused"), c(1)), "Pausable: not paused", "_unpause();"),
          setv(s("paused"), c(0), "_unpause();"),
      ], code="if (_status) {"),
  ]},
  "addSubmitter": {"role": "owner", "fn_line_code": "function addSubmitter(", "file": SUBMITTER, "params": {}, "body": [
      req(eq(s("submitter_active"), c(0)), "invalid submitter", '"invalid submitter"', SUBMITTER),
      setv(s("submitter_active"), c(1), "registered[submitter] = true;", SUBMITTER),
  ]},
  "enqueue": {"role": "env", "fn_line_code": "function _queueTransaction(", "file": QUEUE, "params": {}, "body": [
      {"bound_q": s("q_len"), "code": "uint256 _queueIndex = messageQueue.length;", "file": QUEUE},
      setv(a("q_enq", s("q_len")), s("now"), "messageEnqueueTime[_queueIndex] = block.timestamp;", QUEUE),
      setv(s("q_len"), add(s("q_len"), c(1)), "messageQueue.push(_hash);", QUEUE),
  ]},
  "tick": {"role": "env", "params": {"d": [1, 2]}, "body": [
      {"bound_t": add(s("now"), p("d"))},
      setv(s("now"), add(s("now"), p("d")), "block.timestamp advances"),
  ]},
}

facts = {
  "facts_version": "holon-facts/0.2-sm",
  "target": {"repo": "morph-l2/morph", "commit": COMMIT},
  "extraction": "hand-written (M1); line numbers resolved from `code` by proposals/M1/author_facts.py",
  "dsl": {
    "terms": "c:const | s:scalar | a:array[i] (reads beyond the bound give 0) | p:param | k:config | var:let/loop var | add | subc (checked; underflow -> Revert(tag)) | ite:[prop,t,e]",
    "props": "eq ne lt le gt and or not | var (a let bound to a prop)",
    "stmts": "req (false -> Revert(tag), state unchanged) | set | let | if | for var from..to_incl [while] (to_incl clipped to N) | bound/bound_q/bound_t (index beyond N / Q / T -> Bound, the trace is outside the model)",
    "outcome": "Ok{State} | Revert{tag} | Bound",
  },
  "config": {"N": 3, "Q": 2, "T": 12, "F": 2, "P": 2, "D": 3},
  "state": {
    "scalars": ["lastCommitted", "lastFinalized", "inChallenge", "batchChallenged", "revertReqIndex", "paused",
                "submitter_active", "q_len", "q_pending", "now"],
    "arrays_N": ["committed", "state_root", "hdr_prev", "hdr_num", "hdr_total", "blob", "origin", "fin_ts", "submitter",
                 "chal_challenger", "chal_finished", "chal_success", "chal_start", "finalized_root"],
    "arrays_Q": ["q_enq"],
  },
  "init": {"code": "importGenesisBatch at now=1 (Rollup.sol)", "now": 1, "submitter_active": 1,
           "arrays": {"committed": {"0": 1}, "origin": {"0": 1}, "fin_ts": {"0": 1}, "blob": {"0": 1},
                      "state_root": {"0": 1}, "finalized_root": {"0": 1}}},
  "roles": {"owner": "onlyOwner", "submitter": "onlyActiveSubmitter (single submitter S)",
            "challenger": "onlyChallenger (single challenger C)", "anyone": "permissionless", "env": "time and L1 message enqueue"},
  "actions": actions,
  "assumptions": [
    {"id": "A1", "text": "Honest headers: every header-hash check `committedBatches[i] == hash` is modelled as committed[i] != 0. A caller passing a wrong header always reverts, so such calls add no states."},
    {"id": "A2", "text": "commit* parent = lastCommitted. Any other parent reverts at `_batchIndex == lastCommittedBatchIndex` or earlier."},
    {"id": "A3", "text": "finalizeBatch index = lastFinalized + 1. Other indices revert at `lastFinalizedBatchIndex + 1 == _batchIndex` or earlier."},
    {"id": "A4", "text": "Proofs submitted to proveState / commitBatchWithProof are valid (mock verifier). Invalid proofs revert."},
    {"id": "A5", "text": "Deposits, rewards, stakes and slash amounts are omitted. slash is modelled only as deactivating the submitter of record (submitter==1). addSubmitter abstracts re-registration plus re-staking."},
    {"id": "A6", "text": "commitBatch always attaches one blob at version 1, so blob hash token = 1. commitState carries no blob. Versions and the v2 blob aggregation are covered by the PAR laws."},
    {"id": "A7", "text": "Hashes and roots are tokens: committed in {0,1}, post state root in {1,2}, and 0 means bytes32(0)."},
    {"id": "A8", "text": "block.timestamp starts at 1 (genesis) and only tick advances it. enqueue uses the current timestamp."},
  ],
}

def resolve(root: Path):
    cache = {}
    def lines(f):
        if f not in cache:
            cache[f] = (root / f).read_text().splitlines()
        return cache[f]
    def fn_start(f, code):
        hits = [n for n, l in enumerate(lines(f), 1) if code in l]
        if not hits: raise SystemExit(f"function not found: {code} in {f}")
        return hits[0]
    def walk(node, f, start):
        if isinstance(node, dict):
            if "scope" in node:
                f, start = node["scope_file"], fn_start(node["scope_file"], node["scope"])
            if "code" in node and "file" in node and node["file"] in (ROLLUP, QUEUE, SUBMITTER):
                nf = node["file"]
                st = start if nf == f else 1
                hits = [n for n, l in enumerate(lines(nf), 1) if n >= st and node["code"] in l]
                if not hits:  # shared modifiers and helpers are defined before the function
                    hits = [n for n, l in enumerate(lines(nf), 1) if node["code"] in l]
                if not hits:
                    raise SystemExit(f"code not found in {nf}: {node['code']}")
                node["line"] = hits[0]
            for v in node.values(): walk(v, f, start)
        elif isinstance(node, list):
            for v in node: walk(v, f, start)
    for name in list(actions):
        actions[name] = act = copy.deepcopy(actions[name])  # shared snippets get per-action lines
        f = act.get("file", ROLLUP)
        if "fn_line_code" in act:
            act["file"] = f
            act["line"] = fn_start(f, act["fn_line_code"])
            walk(act["body"], f, act["line"])

if __name__ == "__main__":
    root = Path(sys.argv[1])
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != COMMIT: raise SystemExit(f"morph checkout at {head}, expected {COMMIT}")
    resolve(root)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
    print(OUT)
