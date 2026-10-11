"""Independent abstraction oracle transcribed from the Morph rollup contracts.

This test-only implementation follows the Rollup, L1 message queue, and
Submitter transitions at Morph commit 3e44e795586af3e11285b603ab642c67823add51.
It intentionally does not load or inspect the staged state-machine facts.
"""
from __future__ import annotations

from copy import deepcopy

N = 3
Q = 2
D = 3
F = 2
P = 2
T = 12

SCALARS = (
    "lastCommitted", "lastFinalized", "inChallenge", "batchChallenged",
    "revertReqIndex", "paused", "submitter_active", "q_len", "q_pending", "now",
)
ARRAYS_N = (
    "committed", "state_root", "hdr_prev", "hdr_num", "hdr_total", "blob",
    "origin", "fin_ts", "submitter", "chal_challenger", "chal_finished",
    "chal_success", "chal_start", "finalized_root",
)
ARRAYS_Q = ("q_enq",)


def initial_state():
    state = {name: 0 for name in SCALARS}
    state.update({name: [0] * (N + 1) for name in ARRAYS_N})
    state.update({name: [0] * Q for name in ARRAYS_Q})
    state.update({"now": 1, "submitter_active": 1})
    for name in ("committed", "state_root", "blob", "origin", "fin_ts", "finalized_root"):
        state[name][0] = 1
    return state


def _read(state, array, index):
    if index < 0 or index >= len(state[array]):
        return 0
    return state[array][index]


def _write(state, array, index, value):
    if index < 0 or index >= len(state[array]):
        return False
    state[array][index] = value
    return True


def _failure(state, tag):
    return "Revert", deepcopy(state), tag


def _bound(state):
    return "Bound", deepcopy(state), None


def _ok(state):
    return "Ok", state, None


def _first_unfinalized_time(state):
    index = state["q_pending"]
    if index < state["q_len"] and _read(state, "q_enq", index) != 0:
        return _read(state, "q_enq", index)
    return state["now"]


def _commit_body(state, num_l1, post, blob_token, submitter):
    """The shared _commitBatchWithBatchData transition (Rollup.sol:288-374)."""
    original = state
    next_index = state["lastCommitted"] + 1
    if _read(state, "state_root", state["lastCommitted"]) == 0:
        return _failure(original, "previous state root is zero")
    if post == 0:
        return _failure(original, "new state root is zero")
    if _read(state, "committed", next_index) != 0:
        return _failure(original, "batch already committed")
    if _read(state, "hdr_total", state["lastCommitted"]) + num_l1 > state["q_len"]:
        return _failure(original, "message index out of range")
    if next_index > N:
        return _bound(original)

    prove_remaining = 0
    if state["inChallenge"] == 1:
        prove_remaining = P + _read(state, "chal_start", state["batchChallenged"]) - state["now"]
        if prove_remaining < 0:
            return _failure(original, "panic: arithmetic underflow")

    updated = deepcopy(state)
    previous = updated["lastCommitted"]
    updated["committed"][next_index] = 1
    updated["state_root"][next_index] = post
    updated["hdr_prev"][next_index] = _read(state, "state_root", previous)
    updated["hdr_num"][next_index] = num_l1
    updated["hdr_total"][next_index] = _read(state, "hdr_total", previous) + num_l1
    updated["blob"][next_index] = blob_token
    updated["origin"][next_index] = state["now"]
    updated["fin_ts"][next_index] = state["now"] + F + prove_remaining
    updated["submitter"][next_index] = submitter
    updated["lastCommitted"] = next_index
    return _ok(updated)


def step(action, state, params=None):
    """Apply one abstract transaction and return (tag, full_state, revert_tag)."""
    params = params or {}
    original = deepcopy(state)

    if action == "addSubmitter":
        if state["submitter_active"] != 0:
            return _failure(original, "invalid submitter")
        updated = deepcopy(state)
        updated["submitter_active"] = 1
        return _ok(updated)

    if action == "challengeState":
        i = params["i"]
        if state["revertReqIndex"] != 0:
            return _failure(original, "pending revert request")
        if state["paused"] != 0:
            return _failure(original, "Pausable: paused")
        if state["inChallenge"] != 0:
            return _failure(original, "already in challenge")
        if state["lastFinalized"] >= i:
            return _failure(original, "batch already finalized")
        if _read(state, "committed", i) == 0:
            return _failure(original, "incorrect batch hash")
        if _read(state, "origin", i) == 0 or _read(state, "committed", i) == 0:
            return _failure(original, "batch not exist")
        if _read(state, "chal_challenger", i) != 0:
            return _failure(original, "batch already challenged")
        if _read(state, "fin_ts", i) <= state["now"]:
            return _failure(original, "cannot challenge batch outside the challenge window")
        updated = deepcopy(state)
        updated["batchChallenged"] = i
        updated["chal_challenger"][i] = 1
        updated["chal_start"][i] = state["now"]
        updated["chal_finished"][i] = 0
        updated["chal_success"][i] = 0
        for j in range(state["lastFinalized"] + 1, state["lastCommitted"] + 1):
            if j != i:
                updated["fin_ts"][j] += P
        updated["inChallenge"] = 1
        return _ok(updated)

    if action == "commitBatch":
        num_l1, post = params["numL1"], params["post"]
        if state["submitter_active"] != 1:
            return _failure(original, "only active submitter allowed")
        if state["revertReqIndex"] != 0:
            return _failure(original, "pending revert request")
        if state["paused"] != 0:
            return _failure(original, "Pausable: paused")
        next_index = state["lastCommitted"] + 1
        if _read(state, "blob", next_index) != 0:
            return _failure(original, "commitBatch requires no stored blob hash")
        if _first_unfinalized_time(state) + D < state["now"] and num_l1 <= 0:
            return _failure(original, "l1msg delay")
        return _commit_body(state, num_l1, post, 1, 1)

    if action == "commitState":
        num_l1, post = params["numL1"], params["post"]
        if state["submitter_active"] != 1:
            return _failure(original, "only active submitter allowed")
        if state["revertReqIndex"] != 0:
            return _failure(original, "pending revert request")
        if state["paused"] != 0:
            return _failure(original, "Pausable: paused")
        next_index = state["lastCommitted"] + 1
        blob_token = _read(state, "blob", next_index)
        if blob_token == 0:
            return _failure(original, "no stored blob hash for this batch")
        if _first_unfinalized_time(state) + D < state["now"] and num_l1 <= 0:
            return _failure(original, "l1msg delay")
        return _commit_body(state, num_l1, post, blob_token, 1)

    if action == "commitBatchWithProof":
        num_l1, post = params["numL1"], params["post"]
        if state["revertReqIndex"] != 0:
            return _failure(original, "pending revert request")
        if state["paused"] != 0:
            return _failure(original, "Pausable: paused")
        rollup_delayed = _read(state, "origin", state["lastCommitted"]) + D < state["now"]
        messages_delayed = _first_unfinalized_time(state) + D < state["now"]
        if not rollup_delayed and messages_delayed and num_l1 <= 0:
            return _failure(original, "l1msg delay")
        if not rollup_delayed and not messages_delayed:
            return _failure(original, "invalid timing")
        next_index = state["lastCommitted"] + 1
        blob_token = _read(state, "blob", next_index) or 1
        result = _commit_body(state, num_l1, post, blob_token, 0)
        if result[0] != "Ok":
            return result
        updated = result[1]
        updated["fin_ts"][updated["lastCommitted"]] = updated["now"]
        return _ok(updated)

    if action == "enqueue":
        if state["q_len"] >= Q:
            return _bound(original)
        updated = deepcopy(state)
        updated["q_enq"][updated["q_len"]] = updated["now"]
        updated["q_len"] += 1
        return _ok(updated)

    if action == "finalizeBatch":
        i = state["lastFinalized"] + 1
        if state["revertReqIndex"] != 0:
            return _failure(original, "pending revert request")
        if state["paused"] != 0:
            return _failure(original, "Pausable: paused")
        if _read(state, "committed", i) == 0:
            return _failure(original, "incorrect batch hash")
        if _read(state, "origin", i) == 0 or _read(state, "committed", i) == 0:
            return _failure(original, "batch not exist")
        if _read(state, "chal_challenger", i) != 0 and _read(state, "chal_finished", i) == 0:
            return _failure(original, "batch in challenge")
        if _read(state, "chal_success", i) != 0:
            return _failure(original, "batch should be revert")
        if _read(state, "fin_ts", i) > state["now"]:
            return _failure(original, "batch in challenge window")
        previous_index = i - 1
        if previous_index < 0:
            return _failure(original, "panic: arithmetic underflow")
        if _read(state, "finalized_root", previous_index) != _read(state, "hdr_prev", i):
            return _failure(original, "incorrect previous state root")
        if _read(state, "finalized_root", i) != 0:
            return _failure(original, "batch already verified")
        updated = deepcopy(state)
        updated["lastFinalized"] = i
        updated["finalized_root"][i] = _read(state, "state_root", i)
        if _read(state, "hdr_num", i) > 0:
            start = _read(state, "hdr_total", i) - _read(state, "hdr_num", i)
            if start < 0:
                return _failure(original, "panic: arithmetic underflow")
            if state["q_pending"] != start:
                return _failure(original, "start index mismatch")
            updated["q_pending"] = _read(state, "hdr_total", i)
        for name in ("origin", "fin_ts", "submitter", "state_root", "blob",
                     "chal_challenger", "chal_finished", "chal_success", "chal_start"):
            updated[name][previous_index] = 0
        return _ok(updated)

    if action == "proveState":
        i = params["i"]
        if state["revertReqIndex"] != 0:
            return _failure(original, "pending revert request")
        if state["paused"] != 0:
            return _failure(original, "Pausable: paused")
        if state["submitter_active"] != 1:
            return _failure(original, "only active submitter allowed")
        if _read(state, "committed", i) == 0:
            return _failure(original, "incorrect batch hash")
        if _read(state, "chal_challenger", i) == 0 or _read(state, "chal_finished", i) != 0:
            return _failure(original, "batch in challenge")
        updated = deepcopy(state)
        updated["chal_finished"][i] = 1
        updated["inChallenge"] = 0
        if _read(state, "chal_start", i) + P <= state["now"]:
            updated["chal_success"][i] = 1
            updated["revertReqIndex"] = i
            if _read(state, "submitter", i) == 1:
                updated["submitter_active"] = 0
        return _ok(updated)

    if action == "revertBatch":
        count, index = params["count"], params["idx"]
        if count <= 0:
            return _failure(original, "count must be nonzero")
        if _read(state, "committed", index) == 0:
            return _failure(original, "incorrect batch hash")
        if _read(state, "committed", index + count) != 0:
            return _failure(original, "reverting must start from the ending")
        if index <= state["lastFinalized"]:
            return _failure(original, "can only revert unFinalized batch")
        updated = deepcopy(state)
        updated["lastCommitted"] = index - 1
        end = min(index + count - 1, N)
        for j in range(index, end + 1):
            if _read(updated, "committed", j) == 0:
                break
            updated["committed"][j] = 0
            if _read(updated, "chal_challenger", j) != 0 and _read(updated, "chal_finished", j) == 0:
                updated["inChallenge"] = 0
            for name in ("chal_challenger", "chal_finished", "chal_success", "chal_start"):
                updated[name][j] = 0
            if updated["revertReqIndex"] > 0 and j == updated["revertReqIndex"]:
                updated["revertReqIndex"] = 0
        return _ok(updated)

    if action == "setPause":
        b = params["b"]
        if b == 1:
            if state["paused"] != 0:
                return _failure(original, "Pausable: paused")
            updated = deepcopy(state)
            updated["paused"] = 1
            if state["inChallenge"] == 1:
                i = state["batchChallenged"]
                for name in ("chal_challenger", "chal_finished", "chal_success", "chal_start"):
                    updated[name][i] = 0
                updated["inChallenge"] = 0
            return _ok(updated)
        if state["paused"] != 1:
            return _failure(original, "Pausable: not paused")
        updated = deepcopy(state)
        updated["paused"] = 0
        return _ok(updated)

    if action == "tick":
        d = params["d"]
        if state["now"] + d > T:
            return _bound(original)
        updated = deepcopy(state)
        updated["now"] += d
        return _ok(updated)

    raise KeyError(f"unknown action {action!r}")
