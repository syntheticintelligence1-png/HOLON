import Base

type State is Data:
  State{lastCommitted: Nat, lastFinalized: Nat, inChallenge: Nat, batchChallenged: Nat, revertReqIndex: Nat, paused: Nat, submitter_active: Nat, q_len: Nat, q_pending: Nat, now: Nat, committed: List<&2, Nat>, state_root: List<&2, Nat>, hdr_prev: List<&2, Nat>, hdr_num: List<&2, Nat>, hdr_total: List<&2, Nat>, blob: List<&2, Nat>, origin: List<&2, Nat>, fin_ts: List<&2, Nat>, submitter: List<&2, Nat>, chal_challenger: List<&2, Nat>, chal_finished: List<&2, Nat>, chal_success: List<&2, Nat>, chal_start: List<&2, Nat>, finalized_root: List<&2, Nat>, q_enq: List<&2, Nat>}

type Outcome is Data:
  Ok{state: State}
  Revert{tag: Nat}
  Bound{}

# Revert tag IDs: {"Pausable: not paused": 0, "Pausable: paused": 1, "already in challenge": 2, "batch already challenged": 3, "batch already committed": 4, "batch already finalized": 5, "batch already verified": 6, "batch in challenge": 7, "batch in challenge window": 8, "batch not exist": 9, "batch should be revert": 10, "can only revert unFinalized batch": 11, "cannot challenge batch outside the challenge window": 12, "commitBatch requires no stored blob hash": 13, "commitState must not carry blob": 14, "count must be nonzero": 15, "incorrect batch hash": 16, "incorrect previous state root": 17, "invalid submitter": 18, "invalid timing": 19, "invalid version": 20, "l1msg delay": 21, "message index out of range": 22, "new state root is zero": 23, "no stored blob hash for this batch": 24, "only active submitter allowed": 25, "panic: arithmetic underflow": 26, "pending revert request": 27, "previous state root is zero": 28, "reverting must start from the ending": 29, "start index mismatch": 30}

def nth(+xs: List<&2, Nat>, i: Nat) -> Nat:
  match xs i:
    case Nil{} _:
      0n
    case Con{+h, +t} 0n:
      h
    case Con{+h, +t} 1n+p:
      nth(t, p)

def put_nth(+xs: List<&2, Nat>, i: Nat, +x: Nat) -> List<&2, Nat>:
  match xs i:
    case Nil{} _:
      Nil{}
    case Con{h, +t} 0n:
      Con{x, t}
    case Con{h, +t} 1n+p:
      Con{h, put_nth(t, p, x)}

def get_lastCommitted(+s: State) -> Nat:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: lastCommitted

def set_lastCommitted(s: State, x: Nat) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{x, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_lastFinalized(+s: State) -> Nat:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: lastFinalized

def set_lastFinalized(s: State, x: Nat) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, x, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_inChallenge(+s: State) -> Nat:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: inChallenge

def set_inChallenge(s: State, x: Nat) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, x, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_batchChallenged(+s: State) -> Nat:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: batchChallenged

def set_batchChallenged(s: State, x: Nat) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, x, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_revertReqIndex(+s: State) -> Nat:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: revertReqIndex

def set_revertReqIndex(s: State, x: Nat) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, x, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_paused(+s: State) -> Nat:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: paused

def set_paused(s: State, x: Nat) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, x, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_submitter_active(+s: State) -> Nat:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: submitter_active

def set_submitter_active(s: State, x: Nat) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, x, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_q_len(+s: State) -> Nat:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: q_len

def set_q_len(s: State, x: Nat) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, x, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_q_pending(+s: State) -> Nat:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: q_pending

def set_q_pending(s: State, x: Nat) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, x, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_now(+s: State) -> Nat:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: now

def set_now(s: State, x: Nat) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, x, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_committed(+s: State) -> List<&2, Nat>:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: committed

def set_committed(s: State, x: List<&2, Nat>) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, x, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_state_root(+s: State) -> List<&2, Nat>:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: state_root

def set_state_root(s: State, x: List<&2, Nat>) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, x, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_hdr_prev(+s: State) -> List<&2, Nat>:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: hdr_prev

def set_hdr_prev(s: State, x: List<&2, Nat>) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, x, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_hdr_num(+s: State) -> List<&2, Nat>:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: hdr_num

def set_hdr_num(s: State, x: List<&2, Nat>) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, x, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_hdr_total(+s: State) -> List<&2, Nat>:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: hdr_total

def set_hdr_total(s: State, x: List<&2, Nat>) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, x, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_blob(+s: State) -> List<&2, Nat>:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: blob

def set_blob(s: State, x: List<&2, Nat>) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, x, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_origin(+s: State) -> List<&2, Nat>:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: origin

def set_origin(s: State, x: List<&2, Nat>) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, x, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_fin_ts(+s: State) -> List<&2, Nat>:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: fin_ts

def set_fin_ts(s: State, x: List<&2, Nat>) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, x, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_submitter(+s: State) -> List<&2, Nat>:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: submitter

def set_submitter(s: State, x: List<&2, Nat>) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, x, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_chal_challenger(+s: State) -> List<&2, Nat>:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: chal_challenger

def set_chal_challenger(s: State, x: List<&2, Nat>) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, x, chal_finished, chal_success, chal_start, finalized_root, q_enq}

def get_chal_finished(+s: State) -> List<&2, Nat>:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: chal_finished

def set_chal_finished(s: State, x: List<&2, Nat>) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, x, chal_success, chal_start, finalized_root, q_enq}

def get_chal_success(+s: State) -> List<&2, Nat>:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: chal_success

def set_chal_success(s: State, x: List<&2, Nat>) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, x, chal_start, finalized_root, q_enq}

def get_chal_start(+s: State) -> List<&2, Nat>:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: chal_start

def set_chal_start(s: State, x: List<&2, Nat>) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, x, finalized_root, q_enq}

def get_finalized_root(+s: State) -> List<&2, Nat>:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: finalized_root

def set_finalized_root(s: State, x: List<&2, Nat>) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, x, q_enq}

def get_q_enq(+s: State) -> List<&2, Nat>:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}: q_enq

def set_q_enq(s: State, x: List<&2, Nat>) -> State:
  match s:
    case State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, q_enq}:
      State{lastCommitted, lastFinalized, inChallenge, batchChallenged, revertReqIndex, paused, submitter_active, q_len, q_pending, now, committed, state_root, hdr_prev, hdr_num, hdr_total, blob, origin, fin_ts, submitter, chal_challenger, chal_finished, chal_success, chal_start, finalized_root, x}

def bool_eq(a: Bool, b: Bool) -> Bool:
  match a b:
    case True{} True{}:
      True{}
    case True{} False{}:
      False{}
    case False{} True{}:
      False{}
    case False{} False{}:
      True{}

def is_true(b: Bool) -> Type:
  match b:
    case True{}:
      Unit
    case False{}:
      Empty

def nat_list_eq(xs: List<&2, Nat>, ys: List<&2, Nat>) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      True{}
    case Nil{} Con{h, t}:
      False{}
    case Con{h, t} Nil{}:
      False{}
    case Con{x, xt} Con{y, yt}:
      Bool.and(Nat.is_eq(x, y), nat_list_eq(xt, yt))

def state_eq(+a: State, +b: State) -> Bool:
  Bool.and(Nat.is_eq(get_lastCommitted(a), get_lastCommitted(b)), Bool.and(Nat.is_eq(get_lastFinalized(a), get_lastFinalized(b)), Bool.and(Nat.is_eq(get_inChallenge(a), get_inChallenge(b)), Bool.and(Nat.is_eq(get_batchChallenged(a), get_batchChallenged(b)), Bool.and(Nat.is_eq(get_revertReqIndex(a), get_revertReqIndex(b)), Bool.and(Nat.is_eq(get_paused(a), get_paused(b)), Bool.and(Nat.is_eq(get_submitter_active(a), get_submitter_active(b)), Bool.and(Nat.is_eq(get_q_len(a), get_q_len(b)), Bool.and(Nat.is_eq(get_q_pending(a), get_q_pending(b)), Bool.and(Nat.is_eq(get_now(a), get_now(b)), Bool.and(nat_list_eq(get_committed(a), get_committed(b)), Bool.and(nat_list_eq(get_state_root(a), get_state_root(b)), Bool.and(nat_list_eq(get_hdr_prev(a), get_hdr_prev(b)), Bool.and(nat_list_eq(get_hdr_num(a), get_hdr_num(b)), Bool.and(nat_list_eq(get_hdr_total(a), get_hdr_total(b)), Bool.and(nat_list_eq(get_blob(a), get_blob(b)), Bool.and(nat_list_eq(get_origin(a), get_origin(b)), Bool.and(nat_list_eq(get_fin_ts(a), get_fin_ts(b)), Bool.and(nat_list_eq(get_submitter(a), get_submitter(b)), Bool.and(nat_list_eq(get_chal_challenger(a), get_chal_challenger(b)), Bool.and(nat_list_eq(get_chal_finished(a), get_chal_finished(b)), Bool.and(nat_list_eq(get_chal_success(a), get_chal_success(b)), Bool.and(nat_list_eq(get_chal_start(a), get_chal_start(b)), Bool.and(nat_list_eq(get_finalized_root(a), get_finalized_root(b)), nat_list_eq(get_q_enq(a), get_q_enq(b))))))))))))))))))))))))))

def _addSubmitter_done_1(+s: State) -> Outcome:
  Ok{s}
def _addSubmitter_cond_2(c: Bool, +s: State) -> Outcome:
  match c:
    case True{}:
      _addSubmitter_done_1(set_submitter_active(s, 1n))
    case False{}:
      Revert{26n}
def _addSubmitter_set_3(+s: State) -> Outcome:
  _addSubmitter_cond_2(Bool.and(True{}, True{}), s)
def _addSubmitter_cond_4(c: Bool, +s: State) -> Outcome:
  match c:
    case True{}:
      _addSubmitter_set_3(s)
    case False{}:
      Revert{18n}
def _addSubmitter_cond_5(c: Bool, +s: State) -> Outcome:
  match c:
    case True{}:
      _addSubmitter_cond_4(Nat.is_eq(get_submitter_active(s), 0n), s)
    case False{}:
      Revert{18n}
def _addSubmitter_req_6(+s: State) -> Outcome:
  _addSubmitter_cond_5(Bool.and(True{}, True{}), s)

def act_addSubmitter(+s: State) -> Outcome:
  _addSubmitter_req_6(s)

def _challengeState_done_1(+s: State, +i: Nat) -> Outcome:
  Ok{s}
def _challengeState_cond_2(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_done_1(set_inChallenge(s, 1n), i)
    case False{}:
      Revert{26n}
def _challengeState_set_3(+s: State, +i: Nat) -> Outcome:
  _challengeState_cond_2(Bool.and(True{}, True{}), s, i)
def _challengeState_loop_body_done_4(+s: State, +i: Nat, +j: Nat) -> Outcome:
  Ok{s}
def _challengeState_cond_5(c: Bool, +s: State, +i: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_loop_body_done_4(set_fin_ts(s, put_nth(get_fin_ts(s), j, Nat.add(nth(get_fin_ts(s), j), 2n))), i, j)
    case False{}:
      Bound{}
def _challengeState_cond_6(c: Bool, +s: State, +i: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_cond_5(Nat.is_lt(j, 4n), s, i, j)
    case False{}:
      Revert{26n}
def _challengeState_set_7(+s: State, +i: Nat, +j: Nat) -> Outcome:
  _challengeState_cond_6(Bool.and(Bool.and(True{}, True{}), Bool.and(True{}, True{})), s, i, j)
def _challengeState_cond_8(c: Bool, +s: State, +i: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_set_7(s, i, j)
    case False{}:
      _challengeState_loop_body_done_4(s, i, j)
def _challengeState_cond_9(c: Bool, +s: State, +i: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_cond_8(Nat.is_ne(j, i), s, i, j)
    case False{}:
      Revert{26n}
def _challengeState_if_10(+s: State, +i: Nat, +j: Nat) -> Outcome:
  _challengeState_cond_9(Bool.and(True{}, True{}), s, i, j)
def _challengeState_cond_11(c: Bool, +s: State, +i: Nat, +j: Nat, +end: Nat) -> Outcome:
  match c:
    case True{}:
      Ok{s}
    case False{}:
      _challengeState_if_10(s, i, j)
def _challengeState_body_guard_12(+s: State, +i: Nat, +j: Nat, +end: Nat) -> Outcome:
  _challengeState_cond_11(Nat.is_gt(j, end), s, i, j, end)
def _challengeState_loop_13(fuel: Nat, o: Outcome, +s: State, +i: Nat, +j: Nat, +end: Nat) -> Outcome:
  match fuel:
    case 0n:
      match o:
      case Ok{+s2}:
        _challengeState_set_3(s2, i)
      case Revert{tag}:
        Revert{tag}
      case Bound{}:
        Bound{}
    case 1n+p:
      match o:
      case Ok{+s2}:
        _challengeState_loop_13(p, _challengeState_body_guard_12(s2, i, Nat.add(j, 1n), end), s2, i, Nat.add(j, 1n), end)
      case Revert{tag}:
        Revert{tag}
      case Bound{}:
        Bound{}
def _challengeState_cond_14(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_loop_13(Nat.add(Nat.min(get_lastCommitted(s), 3n), 1n), _challengeState_body_guard_12(s, i, Nat.add(get_lastFinalized(s), 1n), Nat.min(get_lastCommitted(s), 3n)), s, i, Nat.add(get_lastFinalized(s), 1n), Nat.min(get_lastCommitted(s), 3n))
    case False{}:
      Revert{26n}
def _challengeState_cond_15(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_cond_14(True{}, s, i)
    case False{}:
      Revert{26n}
def _challengeState_for_16(+s: State, +i: Nat) -> Outcome:
  _challengeState_cond_15(Bool.and(True{}, True{}), s, i)
def _challengeState_cond_17(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_for_16(set_chal_success(s, put_nth(get_chal_success(s), i, 0n)), i)
    case False{}:
      Bound{}
def _challengeState_cond_18(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_cond_17(Nat.is_lt(i, 4n), s, i)
    case False{}:
      Revert{26n}
def _challengeState_set_19(+s: State, +i: Nat) -> Outcome:
  _challengeState_cond_18(Bool.and(Bool.and(True{}, True{}), True{}), s, i)
def _challengeState_cond_20(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_set_19(set_chal_finished(s, put_nth(get_chal_finished(s), i, 0n)), i)
    case False{}:
      Bound{}
def _challengeState_cond_21(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_cond_20(Nat.is_lt(i, 4n), s, i)
    case False{}:
      Revert{26n}
def _challengeState_set_22(+s: State, +i: Nat) -> Outcome:
  _challengeState_cond_21(Bool.and(Bool.and(True{}, True{}), True{}), s, i)
def _challengeState_cond_23(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_set_22(set_chal_start(s, put_nth(get_chal_start(s), i, get_now(s))), i)
    case False{}:
      Bound{}
def _challengeState_cond_24(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_cond_23(Nat.is_lt(i, 4n), s, i)
    case False{}:
      Revert{26n}
def _challengeState_set_25(+s: State, +i: Nat) -> Outcome:
  _challengeState_cond_24(Bool.and(Bool.and(True{}, True{}), True{}), s, i)
def _challengeState_cond_26(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_set_25(set_chal_challenger(s, put_nth(get_chal_challenger(s), i, 1n)), i)
    case False{}:
      Bound{}
def _challengeState_cond_27(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_cond_26(Nat.is_lt(i, 4n), s, i)
    case False{}:
      Revert{26n}
def _challengeState_set_28(+s: State, +i: Nat) -> Outcome:
  _challengeState_cond_27(Bool.and(Bool.and(True{}, True{}), True{}), s, i)
def _challengeState_cond_29(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_set_28(set_batchChallenged(s, i), i)
    case False{}:
      Revert{26n}
def _challengeState_set_30(+s: State, +i: Nat) -> Outcome:
  _challengeState_cond_29(Bool.and(True{}, True{}), s, i)
def _challengeState_cond_31(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_set_30(s, i)
    case False{}:
      Revert{12n}
def _challengeState_cond_32(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_cond_31(Nat.is_gt(nth(get_fin_ts(s), i), get_now(s)), s, i)
    case False{}:
      Revert{12n}
def _challengeState_req_33(+s: State, +i: Nat) -> Outcome:
  _challengeState_cond_32(Bool.and(True{}, True{}), s, i)
def _challengeState_cond_34(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_req_33(s, i)
    case False{}:
      Revert{3n}
def _challengeState_cond_35(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_cond_34(Nat.is_eq(nth(get_chal_challenger(s), i), 0n), s, i)
    case False{}:
      Revert{3n}
def _challengeState_req_36(+s: State, +i: Nat) -> Outcome:
  _challengeState_cond_35(Bool.and(True{}, True{}), s, i)
def _challengeState_cond_37(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_req_36(s, i)
    case False{}:
      Revert{9n}
def _challengeState_cond_38(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_cond_37(Bool.and(Nat.is_gt(nth(get_origin(s), i), 0n), Nat.is_ne(nth(get_committed(s), i), 0n)), s, i)
    case False{}:
      Revert{9n}
def _challengeState_req_39(+s: State, +i: Nat) -> Outcome:
  _challengeState_cond_38(Bool.and(Bool.and(True{}, True{}), Bool.and(True{}, True{})), s, i)
def _challengeState_cond_40(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_req_39(s, i)
    case False{}:
      Revert{16n}
def _challengeState_cond_41(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_cond_40(Nat.is_ne(nth(get_committed(s), i), 0n), s, i)
    case False{}:
      Revert{16n}
def _challengeState_req_42(+s: State, +i: Nat) -> Outcome:
  _challengeState_cond_41(Bool.and(True{}, True{}), s, i)
def _challengeState_cond_43(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_req_42(s, i)
    case False{}:
      Revert{5n}
def _challengeState_cond_44(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_cond_43(Nat.is_lt(get_lastFinalized(s), i), s, i)
    case False{}:
      Revert{5n}
def _challengeState_req_45(+s: State, +i: Nat) -> Outcome:
  _challengeState_cond_44(Bool.and(True{}, True{}), s, i)
def _challengeState_cond_46(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_req_45(s, i)
    case False{}:
      Revert{2n}
def _challengeState_cond_47(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_cond_46(Nat.is_eq(get_inChallenge(s), 0n), s, i)
    case False{}:
      Revert{2n}
def _challengeState_req_48(+s: State, +i: Nat) -> Outcome:
  _challengeState_cond_47(Bool.and(True{}, True{}), s, i)
def _challengeState_cond_49(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_req_48(s, i)
    case False{}:
      Revert{1n}
def _challengeState_cond_50(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_cond_49(Nat.is_eq(get_paused(s), 0n), s, i)
    case False{}:
      Revert{1n}
def _challengeState_req_51(+s: State, +i: Nat) -> Outcome:
  _challengeState_cond_50(Bool.and(True{}, True{}), s, i)
def _challengeState_cond_52(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_req_51(s, i)
    case False{}:
      Revert{27n}
def _challengeState_cond_53(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _challengeState_cond_52(Nat.is_eq(get_revertReqIndex(s), 0n), s, i)
    case False{}:
      Revert{27n}
def _challengeState_req_54(+s: State, +i: Nat) -> Outcome:
  _challengeState_cond_53(Bool.and(True{}, True{}), s, i)

def act_challengeState(+s: State, i: Nat) -> Outcome:
  _challengeState_req_54(s, i)

def _commitBatch_done_1(+s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  Ok{s}
def _commitBatch_cond_2(c: Bool, +s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_done_1(set_lastCommitted(s, Nat.add(get_lastCommitted(s), 1n)), numL1, post, prove_remaining)
    case False{}:
      Revert{26n}
def _commitBatch_set_3(+s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  _commitBatch_cond_2(Bool.and(True{}, Bool.and(True{}, True{})), s, numL1, post, prove_remaining)
def _commitBatch_cond_4(c: Bool, +s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_set_3(set_submitter(s, put_nth(get_submitter(s), Nat.add(get_lastCommitted(s), 1n), 1n)), numL1, post, prove_remaining)
    case False{}:
      Bound{}
def _commitBatch_cond_5(c: Bool, +s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_4(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post, prove_remaining)
    case False{}:
      Revert{26n}
def _commitBatch_set_6(+s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  _commitBatch_cond_5(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post, prove_remaining)
def _commitBatch_cond_7(c: Bool, +s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_set_6(set_fin_ts(s, put_nth(get_fin_ts(s), Nat.add(get_lastCommitted(s), 1n), Nat.add(Nat.add(get_now(s), 2n), prove_remaining))), numL1, post, prove_remaining)
    case False{}:
      Bound{}
def _commitBatch_cond_8(c: Bool, +s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_7(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post, prove_remaining)
    case False{}:
      Revert{26n}
def _commitBatch_set_9(+s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  _commitBatch_cond_8(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), Bool.and(Bool.and(True{}, True{}), True{})), s, numL1, post, prove_remaining)
def _commitBatch_cond_10(c: Bool, +s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_set_9(set_origin(s, put_nth(get_origin(s), Nat.add(get_lastCommitted(s), 1n), get_now(s))), numL1, post, prove_remaining)
    case False{}:
      Bound{}
def _commitBatch_cond_11(c: Bool, +s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_10(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post, prove_remaining)
    case False{}:
      Revert{26n}
def _commitBatch_set_12(+s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  _commitBatch_cond_11(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post, prove_remaining)
def _commitBatch_cond_13(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_set_12(s, numL1, post, Bool.pick(Nat, Nat.is_eq(get_inChallenge(s), 1n), Nat.sub(Nat.add(2n, nth(get_chal_start(s), get_batchChallenged(s))), get_now(s)), 0n))
    case False{}:
      Revert{26n}
def _commitBatch_let_14(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_13(Bool.and(Bool.and(True{}, True{}), Bool.pick(Bool, Nat.is_eq(get_inChallenge(s), 1n), Bool.and(Bool.and(True{}, True{}), Bool.and(True{}, Nat.is_ge(Nat.add(2n, nth(get_chal_start(s), get_batchChallenged(s))), get_now(s))) ), True{})), s, numL1, post)
def _commitBatch_cond_15(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_let_14(set_blob(s, put_nth(get_blob(s), Nat.add(get_lastCommitted(s), 1n), 1n)), numL1, post)
    case False{}:
      Bound{}
def _commitBatch_cond_16(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_15(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post)
    case False{}:
      Revert{26n}
def _commitBatch_set_17(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_16(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post)
def _commitBatch_cond_18(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_set_17(set_hdr_total(s, put_nth(get_hdr_total(s), Nat.add(get_lastCommitted(s), 1n), Nat.add(nth(get_hdr_total(s), get_lastCommitted(s)), numL1))), numL1, post)
    case False{}:
      Bound{}
def _commitBatch_cond_19(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_18(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post)
    case False{}:
      Revert{26n}
def _commitBatch_set_20(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_19(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), Bool.and(True{}, True{})), s, numL1, post)
def _commitBatch_cond_21(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_set_20(set_hdr_num(s, put_nth(get_hdr_num(s), Nat.add(get_lastCommitted(s), 1n), numL1)), numL1, post)
    case False{}:
      Bound{}
def _commitBatch_cond_22(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_21(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post)
    case False{}:
      Revert{26n}
def _commitBatch_set_23(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_22(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post)
def _commitBatch_cond_24(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_set_23(set_hdr_prev(s, put_nth(get_hdr_prev(s), Nat.add(get_lastCommitted(s), 1n), nth(get_state_root(s), get_lastCommitted(s)))), numL1, post)
    case False{}:
      Bound{}
def _commitBatch_cond_25(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_24(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post)
    case False{}:
      Revert{26n}
def _commitBatch_set_26(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_25(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post)
def _commitBatch_cond_27(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_set_26(set_state_root(s, put_nth(get_state_root(s), Nat.add(get_lastCommitted(s), 1n), post)), numL1, post)
    case False{}:
      Bound{}
def _commitBatch_cond_28(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_27(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post)
    case False{}:
      Revert{26n}
def _commitBatch_set_29(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_28(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post)
def _commitBatch_cond_30(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_set_29(set_committed(s, put_nth(get_committed(s), Nat.add(get_lastCommitted(s), 1n), 1n)), numL1, post)
    case False{}:
      Bound{}
def _commitBatch_cond_31(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_30(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post)
    case False{}:
      Revert{26n}
def _commitBatch_set_32(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_31(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post)
def _commitBatch_cond_33(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      Bound{}
    case False{}:
      _commitBatch_set_32(s, numL1, post)
def _commitBatch_cond_34(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_33(Nat.is_gt(Nat.add(get_lastCommitted(s), 1n), 3n), s, numL1, post)
    case False{}:
      Revert{26n}
def _commitBatch_bound_35(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_34(Bool.and(True{}, True{}), s, numL1, post)
def _commitBatch_cond_36(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_bound_35(s, numL1, post)
    case False{}:
      Revert{22n}
def _commitBatch_cond_37(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_36(Nat.is_le(Nat.add(nth(get_hdr_total(s), get_lastCommitted(s)), numL1), get_q_len(s)), s, numL1, post)
    case False{}:
      Revert{22n}
def _commitBatch_req_38(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_37(Bool.and(Bool.and(True{}, True{}), True{}), s, numL1, post)
def _commitBatch_cond_39(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_req_38(s, numL1, post)
    case False{}:
      Revert{4n}
def _commitBatch_cond_40(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_39(Nat.is_eq(nth(get_committed(s), Nat.add(get_lastCommitted(s), 1n)), 0n), s, numL1, post)
    case False{}:
      Revert{4n}
def _commitBatch_req_41(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_40(Bool.and(Bool.and(True{}, True{}), True{}), s, numL1, post)
def _commitBatch_cond_42(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_req_41(s, numL1, post)
    case False{}:
      Revert{23n}
def _commitBatch_cond_43(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_42(Nat.is_ne(post, 0n), s, numL1, post)
    case False{}:
      Revert{23n}
def _commitBatch_req_44(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_43(Bool.and(True{}, True{}), s, numL1, post)
def _commitBatch_cond_45(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_req_44(s, numL1, post)
    case False{}:
      Revert{28n}
def _commitBatch_cond_46(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_45(Nat.is_ne(nth(get_state_root(s), get_lastCommitted(s)), 0n), s, numL1, post)
    case False{}:
      Revert{28n}
def _commitBatch_req_47(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_46(Bool.and(True{}, True{}), s, numL1, post)
def _commitBatch_cond_48(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_req_47(s, numL1, post)
    case False{}:
      Revert{20n}
def _commitBatch_cond_49(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_48(Nat.is_le(1n, 2n), s, numL1, post)
    case False{}:
      Revert{20n}
def _commitBatch_req_50(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_49(Bool.and(True{}, True{}), s, numL1, post)
def _commitBatch_cond_51(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_req_50(s, numL1, post)
    case False{}:
      Revert{21n}
def _commitBatch_cond_52(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_51(Nat.is_gt(numL1, 0n), s, numL1, post)
    case False{}:
      Revert{21n}
def _commitBatch_req_53(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_52(Bool.and(True{}, True{}), s, numL1, post)
def _commitBatch_cond_54(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_req_53(s, numL1, post)
    case False{}:
      _commitBatch_req_50(s, numL1, post)
def _commitBatch_cond_55(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_54(Nat.is_lt(Nat.add(Bool.pick(Nat, Bool.and(Nat.is_lt(get_q_pending(s), get_q_len(s)), Nat.is_ne(nth(get_q_enq(s), get_q_pending(s)), 0n)), nth(get_q_enq(s), get_q_pending(s)), get_now(s)), 3n), get_now(s)), s, numL1, post)
    case False{}:
      Revert{26n}
def _commitBatch_if_56(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_55(Bool.and(Bool.and(Bool.and(Bool.and(Bool.and(True{}, True{}), Bool.and(True{}, True{})), Bool.pick(Bool, Bool.and(Nat.is_lt(get_q_pending(s), get_q_len(s)), Nat.is_ne(nth(get_q_enq(s), get_q_pending(s)), 0n)), True{}, True{})), True{}), True{}), s, numL1, post)
def _commitBatch_cond_57(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_if_56(s, numL1, post)
    case False{}:
      Revert{13n}
def _commitBatch_cond_58(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_57(Nat.is_eq(nth(get_blob(s), Nat.add(get_lastCommitted(s), 1n)), 0n), s, numL1, post)
    case False{}:
      Revert{13n}
def _commitBatch_req_59(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_58(Bool.and(Bool.and(True{}, True{}), True{}), s, numL1, post)
def _commitBatch_cond_60(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_req_59(s, numL1, post)
    case False{}:
      Revert{1n}
def _commitBatch_cond_61(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_60(Nat.is_eq(get_paused(s), 0n), s, numL1, post)
    case False{}:
      Revert{1n}
def _commitBatch_req_62(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_61(Bool.and(True{}, True{}), s, numL1, post)
def _commitBatch_cond_63(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_req_62(s, numL1, post)
    case False{}:
      Revert{27n}
def _commitBatch_cond_64(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_63(Nat.is_eq(get_revertReqIndex(s), 0n), s, numL1, post)
    case False{}:
      Revert{27n}
def _commitBatch_req_65(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_64(Bool.and(True{}, True{}), s, numL1, post)
def _commitBatch_cond_66(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_req_65(s, numL1, post)
    case False{}:
      Revert{25n}
def _commitBatch_cond_67(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatch_cond_66(Nat.is_eq(get_submitter_active(s), 1n), s, numL1, post)
    case False{}:
      Revert{25n}
def _commitBatch_req_68(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatch_cond_67(Bool.and(True{}, True{}), s, numL1, post)

def act_commitBatch(+s: State, numL1: Nat, post: Nat) -> Outcome:
  _commitBatch_req_68(s, numL1, post)

def _commitBatchWithProof_done_1(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool, +prove_remaining: Nat) -> Outcome:
  Ok{s}
def _commitBatchWithProof_cond_2(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_done_1(set_fin_ts(s, put_nth(get_fin_ts(s), get_lastCommitted(s), get_now(s))), numL1, post, rollup_delay, l1_delayed, prove_remaining)
    case False{}:
      Bound{}
def _commitBatchWithProof_cond_3(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_2(Nat.is_lt(get_lastCommitted(s), 4n), s, numL1, post, rollup_delay, l1_delayed, prove_remaining)
    case False{}:
      Revert{26n}
def _commitBatchWithProof_set_4(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool, +prove_remaining: Nat) -> Outcome:
  _commitBatchWithProof_cond_3(Bool.and(Bool.and(True{}, True{}), True{}), s, numL1, post, rollup_delay, l1_delayed, prove_remaining)
def _commitBatchWithProof_cond_5(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_set_4(set_lastCommitted(s, Nat.add(get_lastCommitted(s), 1n)), numL1, post, rollup_delay, l1_delayed, prove_remaining)
    case False{}:
      Revert{26n}
def _commitBatchWithProof_set_6(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool, +prove_remaining: Nat) -> Outcome:
  _commitBatchWithProof_cond_5(Bool.and(True{}, Bool.and(True{}, True{})), s, numL1, post, rollup_delay, l1_delayed, prove_remaining)
def _commitBatchWithProof_cond_7(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_set_6(set_submitter(s, put_nth(get_submitter(s), Nat.add(get_lastCommitted(s), 1n), 0n)), numL1, post, rollup_delay, l1_delayed, prove_remaining)
    case False{}:
      Bound{}
def _commitBatchWithProof_cond_8(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_7(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post, rollup_delay, l1_delayed, prove_remaining)
    case False{}:
      Revert{26n}
def _commitBatchWithProof_set_9(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool, +prove_remaining: Nat) -> Outcome:
  _commitBatchWithProof_cond_8(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post, rollup_delay, l1_delayed, prove_remaining)
def _commitBatchWithProof_cond_10(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_set_9(set_fin_ts(s, put_nth(get_fin_ts(s), Nat.add(get_lastCommitted(s), 1n), Nat.add(Nat.add(get_now(s), 2n), prove_remaining))), numL1, post, rollup_delay, l1_delayed, prove_remaining)
    case False{}:
      Bound{}
def _commitBatchWithProof_cond_11(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_10(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post, rollup_delay, l1_delayed, prove_remaining)
    case False{}:
      Revert{26n}
def _commitBatchWithProof_set_12(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool, +prove_remaining: Nat) -> Outcome:
  _commitBatchWithProof_cond_11(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), Bool.and(Bool.and(True{}, True{}), True{})), s, numL1, post, rollup_delay, l1_delayed, prove_remaining)
def _commitBatchWithProof_cond_13(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_set_12(set_origin(s, put_nth(get_origin(s), Nat.add(get_lastCommitted(s), 1n), get_now(s))), numL1, post, rollup_delay, l1_delayed, prove_remaining)
    case False{}:
      Bound{}
def _commitBatchWithProof_cond_14(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_13(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post, rollup_delay, l1_delayed, prove_remaining)
    case False{}:
      Revert{26n}
def _commitBatchWithProof_set_15(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool, +prove_remaining: Nat) -> Outcome:
  _commitBatchWithProof_cond_14(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post, rollup_delay, l1_delayed, prove_remaining)
def _commitBatchWithProof_cond_16(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_set_15(s, numL1, post, rollup_delay, l1_delayed, Bool.pick(Nat, Nat.is_eq(get_inChallenge(s), 1n), Nat.sub(Nat.add(2n, nth(get_chal_start(s), get_batchChallenged(s))), get_now(s)), 0n))
    case False{}:
      Revert{26n}
def _commitBatchWithProof_let_17(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  _commitBatchWithProof_cond_16(Bool.and(Bool.and(True{}, True{}), Bool.pick(Bool, Nat.is_eq(get_inChallenge(s), 1n), Bool.and(Bool.and(True{}, True{}), Bool.and(True{}, Nat.is_ge(Nat.add(2n, nth(get_chal_start(s), get_batchChallenged(s))), get_now(s))) ), True{})), s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_18(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_let_17(set_blob(s, put_nth(get_blob(s), Nat.add(get_lastCommitted(s), 1n), Bool.pick(Nat, Nat.is_ne(nth(get_blob(s), Nat.add(get_lastCommitted(s), 1n)), 0n), nth(get_blob(s), Nat.add(get_lastCommitted(s), 1n)), 1n))), numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Bound{}
def _commitBatchWithProof_cond_19(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_18(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{26n}
def _commitBatchWithProof_set_20(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  _commitBatchWithProof_cond_19(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), Bool.and(Bool.and(Bool.and(True{}, True{}), True{}), Bool.pick(Bool, Nat.is_ne(nth(get_blob(s), Nat.add(get_lastCommitted(s), 1n)), 0n), Bool.and(True{}, True{}), True{}))), s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_21(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_set_20(set_hdr_total(s, put_nth(get_hdr_total(s), Nat.add(get_lastCommitted(s), 1n), Nat.add(nth(get_hdr_total(s), get_lastCommitted(s)), numL1))), numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Bound{}
def _commitBatchWithProof_cond_22(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_21(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{26n}
def _commitBatchWithProof_set_23(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  _commitBatchWithProof_cond_22(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), Bool.and(True{}, True{})), s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_24(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_set_23(set_hdr_num(s, put_nth(get_hdr_num(s), Nat.add(get_lastCommitted(s), 1n), numL1)), numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Bound{}
def _commitBatchWithProof_cond_25(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_24(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{26n}
def _commitBatchWithProof_set_26(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  _commitBatchWithProof_cond_25(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_27(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_set_26(set_hdr_prev(s, put_nth(get_hdr_prev(s), Nat.add(get_lastCommitted(s), 1n), nth(get_state_root(s), get_lastCommitted(s)))), numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Bound{}
def _commitBatchWithProof_cond_28(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_27(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{26n}
def _commitBatchWithProof_set_29(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  _commitBatchWithProof_cond_28(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_30(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_set_29(set_state_root(s, put_nth(get_state_root(s), Nat.add(get_lastCommitted(s), 1n), post)), numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Bound{}
def _commitBatchWithProof_cond_31(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_30(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{26n}
def _commitBatchWithProof_set_32(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  _commitBatchWithProof_cond_31(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_33(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_set_32(set_committed(s, put_nth(get_committed(s), Nat.add(get_lastCommitted(s), 1n), 1n)), numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Bound{}
def _commitBatchWithProof_cond_34(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_33(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{26n}
def _commitBatchWithProof_set_35(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  _commitBatchWithProof_cond_34(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_36(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      Bound{}
    case False{}:
      _commitBatchWithProof_set_35(s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_37(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_36(Nat.is_gt(Nat.add(get_lastCommitted(s), 1n), 3n), s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{26n}
def _commitBatchWithProof_bound_38(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  _commitBatchWithProof_cond_37(Bool.and(True{}, True{}), s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_39(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_bound_38(s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{22n}
def _commitBatchWithProof_cond_40(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_39(Nat.is_le(Nat.add(nth(get_hdr_total(s), get_lastCommitted(s)), numL1), get_q_len(s)), s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{22n}
def _commitBatchWithProof_req_41(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  _commitBatchWithProof_cond_40(Bool.and(Bool.and(True{}, True{}), True{}), s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_42(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_req_41(s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{4n}
def _commitBatchWithProof_cond_43(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_42(Nat.is_eq(nth(get_committed(s), Nat.add(get_lastCommitted(s), 1n)), 0n), s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{4n}
def _commitBatchWithProof_req_44(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  _commitBatchWithProof_cond_43(Bool.and(Bool.and(True{}, True{}), True{}), s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_45(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_req_44(s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{23n}
def _commitBatchWithProof_cond_46(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_45(Nat.is_ne(post, 0n), s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{23n}
def _commitBatchWithProof_req_47(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  _commitBatchWithProof_cond_46(Bool.and(True{}, True{}), s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_48(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_req_47(s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{28n}
def _commitBatchWithProof_cond_49(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_48(Nat.is_ne(nth(get_state_root(s), get_lastCommitted(s)), 0n), s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{28n}
def _commitBatchWithProof_req_50(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  _commitBatchWithProof_cond_49(Bool.and(True{}, True{}), s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_51(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_req_50(s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{20n}
def _commitBatchWithProof_cond_52(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_51(Nat.is_le(1n, 2n), s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{20n}
def _commitBatchWithProof_req_53(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  _commitBatchWithProof_cond_52(Bool.and(True{}, True{}), s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_54(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_req_53(s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{19n}
def _commitBatchWithProof_cond_55(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_54(Bool.or(rollup_delay, l1_delayed), s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{19n}
def _commitBatchWithProof_req_56(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  _commitBatchWithProof_cond_55(Bool.and(True{}, True{}), s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_57(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_req_56(s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{21n}
def _commitBatchWithProof_cond_58(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_57(Nat.is_gt(numL1, 0n), s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{21n}
def _commitBatchWithProof_req_59(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  _commitBatchWithProof_cond_58(Bool.and(True{}, True{}), s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_60(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_req_59(s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      _commitBatchWithProof_req_56(s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_61(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_60(Bool.and(Bool.not(rollup_delay), l1_delayed), s, numL1, post, rollup_delay, l1_delayed)
    case False{}:
      Revert{26n}
def _commitBatchWithProof_if_62(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool, +l1_delayed: Bool) -> Outcome:
  _commitBatchWithProof_cond_61(Bool.and(True{}, True{}), s, numL1, post, rollup_delay, l1_delayed)
def _commitBatchWithProof_cond_63(c: Bool, +s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_if_62(s, numL1, post, rollup_delay, Nat.is_lt(Nat.add(Bool.pick(Nat, Bool.and(Nat.is_lt(get_q_pending(s), get_q_len(s)), Nat.is_ne(nth(get_q_enq(s), get_q_pending(s)), 0n)), nth(get_q_enq(s), get_q_pending(s)), get_now(s)), 3n), get_now(s)))
    case False{}:
      Revert{26n}
def _commitBatchWithProof_let_64(+s: State, +numL1: Nat, +post: Nat, +rollup_delay: Bool) -> Outcome:
  _commitBatchWithProof_cond_63(Bool.and(Bool.and(Bool.and(Bool.and(Bool.and(True{}, True{}), Bool.and(True{}, True{})), Bool.pick(Bool, Bool.and(Nat.is_lt(get_q_pending(s), get_q_len(s)), Nat.is_ne(nth(get_q_enq(s), get_q_pending(s)), 0n)), True{}, True{})), True{}), True{}), s, numL1, post, rollup_delay)
def _commitBatchWithProof_cond_65(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_let_64(s, numL1, post, Nat.is_lt(Nat.add(nth(get_origin(s), get_lastCommitted(s)), 3n), get_now(s)))
    case False{}:
      Revert{26n}
def _commitBatchWithProof_let_66(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatchWithProof_cond_65(Bool.and(Bool.and(True{}, True{}), True{}), s, numL1, post)
def _commitBatchWithProof_cond_67(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_let_66(s, numL1, post)
    case False{}:
      Revert{1n}
def _commitBatchWithProof_cond_68(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_67(Nat.is_eq(get_paused(s), 0n), s, numL1, post)
    case False{}:
      Revert{1n}
def _commitBatchWithProof_req_69(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatchWithProof_cond_68(Bool.and(True{}, True{}), s, numL1, post)
def _commitBatchWithProof_cond_70(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_req_69(s, numL1, post)
    case False{}:
      Revert{27n}
def _commitBatchWithProof_cond_71(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitBatchWithProof_cond_70(Nat.is_eq(get_revertReqIndex(s), 0n), s, numL1, post)
    case False{}:
      Revert{27n}
def _commitBatchWithProof_req_72(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitBatchWithProof_cond_71(Bool.and(True{}, True{}), s, numL1, post)

def act_commitBatchWithProof(+s: State, numL1: Nat, post: Nat) -> Outcome:
  _commitBatchWithProof_req_72(s, numL1, post)

def _commitState_done_1(+s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  Ok{s}
def _commitState_cond_2(c: Bool, +s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_done_1(set_lastCommitted(s, Nat.add(get_lastCommitted(s), 1n)), numL1, post, prove_remaining)
    case False{}:
      Revert{26n}
def _commitState_set_3(+s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  _commitState_cond_2(Bool.and(True{}, Bool.and(True{}, True{})), s, numL1, post, prove_remaining)
def _commitState_cond_4(c: Bool, +s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_set_3(set_submitter(s, put_nth(get_submitter(s), Nat.add(get_lastCommitted(s), 1n), 1n)), numL1, post, prove_remaining)
    case False{}:
      Bound{}
def _commitState_cond_5(c: Bool, +s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_4(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post, prove_remaining)
    case False{}:
      Revert{26n}
def _commitState_set_6(+s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  _commitState_cond_5(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post, prove_remaining)
def _commitState_cond_7(c: Bool, +s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_set_6(set_fin_ts(s, put_nth(get_fin_ts(s), Nat.add(get_lastCommitted(s), 1n), Nat.add(Nat.add(get_now(s), 2n), prove_remaining))), numL1, post, prove_remaining)
    case False{}:
      Bound{}
def _commitState_cond_8(c: Bool, +s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_7(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post, prove_remaining)
    case False{}:
      Revert{26n}
def _commitState_set_9(+s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  _commitState_cond_8(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), Bool.and(Bool.and(True{}, True{}), True{})), s, numL1, post, prove_remaining)
def _commitState_cond_10(c: Bool, +s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_set_9(set_origin(s, put_nth(get_origin(s), Nat.add(get_lastCommitted(s), 1n), get_now(s))), numL1, post, prove_remaining)
    case False{}:
      Bound{}
def _commitState_cond_11(c: Bool, +s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_10(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post, prove_remaining)
    case False{}:
      Revert{26n}
def _commitState_set_12(+s: State, +numL1: Nat, +post: Nat, +prove_remaining: Nat) -> Outcome:
  _commitState_cond_11(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post, prove_remaining)
def _commitState_cond_13(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_set_12(s, numL1, post, Bool.pick(Nat, Nat.is_eq(get_inChallenge(s), 1n), Nat.sub(Nat.add(2n, nth(get_chal_start(s), get_batchChallenged(s))), get_now(s)), 0n))
    case False{}:
      Revert{26n}
def _commitState_let_14(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_13(Bool.and(Bool.and(True{}, True{}), Bool.pick(Bool, Nat.is_eq(get_inChallenge(s), 1n), Bool.and(Bool.and(True{}, True{}), Bool.and(True{}, Nat.is_ge(Nat.add(2n, nth(get_chal_start(s), get_batchChallenged(s))), get_now(s))) ), True{})), s, numL1, post)
def _commitState_cond_15(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_let_14(set_blob(s, put_nth(get_blob(s), Nat.add(get_lastCommitted(s), 1n), nth(get_blob(s), Nat.add(get_lastCommitted(s), 1n)))), numL1, post)
    case False{}:
      Bound{}
def _commitState_cond_16(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_15(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post)
    case False{}:
      Revert{26n}
def _commitState_set_17(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_16(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), Bool.and(True{}, True{})), s, numL1, post)
def _commitState_cond_18(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_set_17(set_hdr_total(s, put_nth(get_hdr_total(s), Nat.add(get_lastCommitted(s), 1n), Nat.add(nth(get_hdr_total(s), get_lastCommitted(s)), numL1))), numL1, post)
    case False{}:
      Bound{}
def _commitState_cond_19(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_18(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post)
    case False{}:
      Revert{26n}
def _commitState_set_20(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_19(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), Bool.and(True{}, True{})), s, numL1, post)
def _commitState_cond_21(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_set_20(set_hdr_num(s, put_nth(get_hdr_num(s), Nat.add(get_lastCommitted(s), 1n), numL1)), numL1, post)
    case False{}:
      Bound{}
def _commitState_cond_22(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_21(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post)
    case False{}:
      Revert{26n}
def _commitState_set_23(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_22(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post)
def _commitState_cond_24(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_set_23(set_hdr_prev(s, put_nth(get_hdr_prev(s), Nat.add(get_lastCommitted(s), 1n), nth(get_state_root(s), get_lastCommitted(s)))), numL1, post)
    case False{}:
      Bound{}
def _commitState_cond_25(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_24(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post)
    case False{}:
      Revert{26n}
def _commitState_set_26(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_25(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post)
def _commitState_cond_27(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_set_26(set_state_root(s, put_nth(get_state_root(s), Nat.add(get_lastCommitted(s), 1n), post)), numL1, post)
    case False{}:
      Bound{}
def _commitState_cond_28(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_27(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post)
    case False{}:
      Revert{26n}
def _commitState_set_29(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_28(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post)
def _commitState_cond_30(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_set_29(set_committed(s, put_nth(get_committed(s), Nat.add(get_lastCommitted(s), 1n), 1n)), numL1, post)
    case False{}:
      Bound{}
def _commitState_cond_31(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_30(Nat.is_lt(Nat.add(get_lastCommitted(s), 1n), 4n), s, numL1, post)
    case False{}:
      Revert{26n}
def _commitState_set_32(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_31(Bool.and(Bool.and(True{}, Bool.and(True{}, True{})), True{}), s, numL1, post)
def _commitState_cond_33(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      Bound{}
    case False{}:
      _commitState_set_32(s, numL1, post)
def _commitState_cond_34(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_33(Nat.is_gt(Nat.add(get_lastCommitted(s), 1n), 3n), s, numL1, post)
    case False{}:
      Revert{26n}
def _commitState_bound_35(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_34(Bool.and(True{}, True{}), s, numL1, post)
def _commitState_cond_36(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_bound_35(s, numL1, post)
    case False{}:
      Revert{22n}
def _commitState_cond_37(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_36(Nat.is_le(Nat.add(nth(get_hdr_total(s), get_lastCommitted(s)), numL1), get_q_len(s)), s, numL1, post)
    case False{}:
      Revert{22n}
def _commitState_req_38(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_37(Bool.and(Bool.and(True{}, True{}), True{}), s, numL1, post)
def _commitState_cond_39(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_req_38(s, numL1, post)
    case False{}:
      Revert{4n}
def _commitState_cond_40(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_39(Nat.is_eq(nth(get_committed(s), Nat.add(get_lastCommitted(s), 1n)), 0n), s, numL1, post)
    case False{}:
      Revert{4n}
def _commitState_req_41(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_40(Bool.and(Bool.and(True{}, True{}), True{}), s, numL1, post)
def _commitState_cond_42(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_req_41(s, numL1, post)
    case False{}:
      Revert{23n}
def _commitState_cond_43(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_42(Nat.is_ne(post, 0n), s, numL1, post)
    case False{}:
      Revert{23n}
def _commitState_req_44(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_43(Bool.and(True{}, True{}), s, numL1, post)
def _commitState_cond_45(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_req_44(s, numL1, post)
    case False{}:
      Revert{28n}
def _commitState_cond_46(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_45(Nat.is_ne(nth(get_state_root(s), get_lastCommitted(s)), 0n), s, numL1, post)
    case False{}:
      Revert{28n}
def _commitState_req_47(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_46(Bool.and(True{}, True{}), s, numL1, post)
def _commitState_cond_48(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_req_47(s, numL1, post)
    case False{}:
      Revert{20n}
def _commitState_cond_49(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_48(Nat.is_le(1n, 2n), s, numL1, post)
    case False{}:
      Revert{20n}
def _commitState_req_50(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_49(Bool.and(True{}, True{}), s, numL1, post)
def _commitState_cond_51(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_req_50(s, numL1, post)
    case False{}:
      Revert{21n}
def _commitState_cond_52(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_51(Nat.is_gt(numL1, 0n), s, numL1, post)
    case False{}:
      Revert{21n}
def _commitState_req_53(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_52(Bool.and(True{}, True{}), s, numL1, post)
def _commitState_cond_54(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_req_53(s, numL1, post)
    case False{}:
      _commitState_req_50(s, numL1, post)
def _commitState_cond_55(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_54(Nat.is_lt(Nat.add(Bool.pick(Nat, Bool.and(Nat.is_lt(get_q_pending(s), get_q_len(s)), Nat.is_ne(nth(get_q_enq(s), get_q_pending(s)), 0n)), nth(get_q_enq(s), get_q_pending(s)), get_now(s)), 3n), get_now(s)), s, numL1, post)
    case False{}:
      Revert{26n}
def _commitState_if_56(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_55(Bool.and(Bool.and(Bool.and(Bool.and(Bool.and(True{}, True{}), Bool.and(True{}, True{})), Bool.pick(Bool, Bool.and(Nat.is_lt(get_q_pending(s), get_q_len(s)), Nat.is_ne(nth(get_q_enq(s), get_q_pending(s)), 0n)), True{}, True{})), True{}), True{}), s, numL1, post)
def _commitState_cond_57(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_if_56(s, numL1, post)
    case False{}:
      Revert{24n}
def _commitState_cond_58(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_57(Nat.is_ne(nth(get_blob(s), Nat.add(get_lastCommitted(s), 1n)), 0n), s, numL1, post)
    case False{}:
      Revert{24n}
def _commitState_req_59(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_58(Bool.and(Bool.and(True{}, True{}), True{}), s, numL1, post)
def _commitState_cond_60(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_req_59(s, numL1, post)
    case False{}:
      Revert{14n}
def _commitState_cond_61(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_60(Nat.is_eq(0n, 0n), s, numL1, post)
    case False{}:
      Revert{14n}
def _commitState_req_62(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_61(Bool.and(True{}, True{}), s, numL1, post)
def _commitState_cond_63(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_req_62(s, numL1, post)
    case False{}:
      Revert{1n}
def _commitState_cond_64(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_63(Nat.is_eq(get_paused(s), 0n), s, numL1, post)
    case False{}:
      Revert{1n}
def _commitState_req_65(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_64(Bool.and(True{}, True{}), s, numL1, post)
def _commitState_cond_66(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_req_65(s, numL1, post)
    case False{}:
      Revert{27n}
def _commitState_cond_67(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_66(Nat.is_eq(get_revertReqIndex(s), 0n), s, numL1, post)
    case False{}:
      Revert{27n}
def _commitState_req_68(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_67(Bool.and(True{}, True{}), s, numL1, post)
def _commitState_cond_69(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_req_68(s, numL1, post)
    case False{}:
      Revert{25n}
def _commitState_cond_70(c: Bool, +s: State, +numL1: Nat, +post: Nat) -> Outcome:
  match c:
    case True{}:
      _commitState_cond_69(Nat.is_eq(get_submitter_active(s), 1n), s, numL1, post)
    case False{}:
      Revert{25n}
def _commitState_req_71(+s: State, +numL1: Nat, +post: Nat) -> Outcome:
  _commitState_cond_70(Bool.and(True{}, True{}), s, numL1, post)

def act_commitState(+s: State, numL1: Nat, post: Nat) -> Outcome:
  _commitState_req_71(s, numL1, post)

def _enqueue_done_1(+s: State) -> Outcome:
  Ok{s}
def _enqueue_cond_2(c: Bool, +s: State) -> Outcome:
  match c:
    case True{}:
      _enqueue_done_1(set_q_len(s, Nat.add(get_q_len(s), 1n)))
    case False{}:
      Revert{26n}
def _enqueue_set_3(+s: State) -> Outcome:
  _enqueue_cond_2(Bool.and(True{}, Bool.and(True{}, True{})), s)
def _enqueue_cond_4(c: Bool, +s: State) -> Outcome:
  match c:
    case True{}:
      _enqueue_set_3(set_q_enq(s, put_nth(get_q_enq(s), get_q_len(s), get_now(s))))
    case False{}:
      Bound{}
def _enqueue_cond_5(c: Bool, +s: State) -> Outcome:
  match c:
    case True{}:
      _enqueue_cond_4(Nat.is_lt(get_q_len(s), 2n), s)
    case False{}:
      Revert{26n}
def _enqueue_set_6(+s: State) -> Outcome:
  _enqueue_cond_5(Bool.and(Bool.and(True{}, True{}), True{}), s)
def _enqueue_cond_7(c: Bool, +s: State) -> Outcome:
  match c:
    case True{}:
      Bound{}
    case False{}:
      _enqueue_set_6(s)
def _enqueue_cond_8(c: Bool, +s: State) -> Outcome:
  match c:
    case True{}:
      _enqueue_cond_7(Nat.is_ge(get_q_len(s), 2n), s)
    case False{}:
      Revert{26n}
def _enqueue_bound_9(+s: State) -> Outcome:
  _enqueue_cond_8(True{}, s)

def act_enqueue(+s: State) -> Outcome:
  _enqueue_bound_9(s)

def _finalizeBatch_done_1(+s: State, +i: Nat) -> Outcome:
  Ok{s}
def _finalizeBatch_cond_2(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_done_1(set_chal_start(s, put_nth(get_chal_start(s), Nat.sub(i, 1n), 0n)), i)
    case False{}:
      Bound{}
def _finalizeBatch_cond_3(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_2(Nat.is_lt(Nat.sub(i, 1n), 4n), s, i)
    case False{}:
      Revert{26n}
def _finalizeBatch_set_4(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_3(Bool.and(Bool.and(True{}, Bool.and(True{}, Bool.and(True{}, Nat.is_ge(i, 1n)) )), True{}), s, i)
def _finalizeBatch_cond_5(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_set_4(set_chal_success(s, put_nth(get_chal_success(s), Nat.sub(i, 1n), 0n)), i)
    case False{}:
      Bound{}
def _finalizeBatch_cond_6(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_5(Nat.is_lt(Nat.sub(i, 1n), 4n), s, i)
    case False{}:
      Revert{26n}
def _finalizeBatch_set_7(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_6(Bool.and(Bool.and(True{}, Bool.and(True{}, Bool.and(True{}, Nat.is_ge(i, 1n)) )), True{}), s, i)
def _finalizeBatch_cond_8(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_set_7(set_chal_finished(s, put_nth(get_chal_finished(s), Nat.sub(i, 1n), 0n)), i)
    case False{}:
      Bound{}
def _finalizeBatch_cond_9(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_8(Nat.is_lt(Nat.sub(i, 1n), 4n), s, i)
    case False{}:
      Revert{26n}
def _finalizeBatch_set_10(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_9(Bool.and(Bool.and(True{}, Bool.and(True{}, Bool.and(True{}, Nat.is_ge(i, 1n)) )), True{}), s, i)
def _finalizeBatch_cond_11(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_set_10(set_chal_challenger(s, put_nth(get_chal_challenger(s), Nat.sub(i, 1n), 0n)), i)
    case False{}:
      Bound{}
def _finalizeBatch_cond_12(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_11(Nat.is_lt(Nat.sub(i, 1n), 4n), s, i)
    case False{}:
      Revert{26n}
def _finalizeBatch_set_13(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_12(Bool.and(Bool.and(True{}, Bool.and(True{}, Bool.and(True{}, Nat.is_ge(i, 1n)) )), True{}), s, i)
def _finalizeBatch_cond_14(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_set_13(set_blob(s, put_nth(get_blob(s), Nat.sub(i, 1n), 0n)), i)
    case False{}:
      Bound{}
def _finalizeBatch_cond_15(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_14(Nat.is_lt(Nat.sub(i, 1n), 4n), s, i)
    case False{}:
      Revert{26n}
def _finalizeBatch_set_16(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_15(Bool.and(Bool.and(True{}, Bool.and(True{}, Bool.and(True{}, Nat.is_ge(i, 1n)) )), True{}), s, i)
def _finalizeBatch_cond_17(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_set_16(set_state_root(s, put_nth(get_state_root(s), Nat.sub(i, 1n), 0n)), i)
    case False{}:
      Bound{}
def _finalizeBatch_cond_18(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_17(Nat.is_lt(Nat.sub(i, 1n), 4n), s, i)
    case False{}:
      Revert{26n}
def _finalizeBatch_set_19(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_18(Bool.and(Bool.and(True{}, Bool.and(True{}, Bool.and(True{}, Nat.is_ge(i, 1n)) )), True{}), s, i)
def _finalizeBatch_cond_20(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_set_19(set_submitter(s, put_nth(get_submitter(s), Nat.sub(i, 1n), 0n)), i)
    case False{}:
      Bound{}
def _finalizeBatch_cond_21(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_20(Nat.is_lt(Nat.sub(i, 1n), 4n), s, i)
    case False{}:
      Revert{26n}
def _finalizeBatch_set_22(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_21(Bool.and(Bool.and(True{}, Bool.and(True{}, Bool.and(True{}, Nat.is_ge(i, 1n)) )), True{}), s, i)
def _finalizeBatch_cond_23(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_set_22(set_fin_ts(s, put_nth(get_fin_ts(s), Nat.sub(i, 1n), 0n)), i)
    case False{}:
      Bound{}
def _finalizeBatch_cond_24(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_23(Nat.is_lt(Nat.sub(i, 1n), 4n), s, i)
    case False{}:
      Revert{26n}
def _finalizeBatch_set_25(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_24(Bool.and(Bool.and(True{}, Bool.and(True{}, Bool.and(True{}, Nat.is_ge(i, 1n)) )), True{}), s, i)
def _finalizeBatch_cond_26(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_set_25(set_origin(s, put_nth(get_origin(s), Nat.sub(i, 1n), 0n)), i)
    case False{}:
      Bound{}
def _finalizeBatch_cond_27(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_26(Nat.is_lt(Nat.sub(i, 1n), 4n), s, i)
    case False{}:
      Revert{26n}
def _finalizeBatch_set_28(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_27(Bool.and(Bool.and(True{}, Bool.and(True{}, Bool.and(True{}, Nat.is_ge(i, 1n)) )), True{}), s, i)
def _finalizeBatch_cond_29(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_set_28(set_q_pending(s, nth(get_hdr_total(s), i)), i)
    case False{}:
      Revert{26n}
def _finalizeBatch_set_30(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_29(Bool.and(True{}, True{}), s, i)
def _finalizeBatch_cond_31(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_set_30(s, i)
    case False{}:
      Revert{26n}
def _finalizeBatch_cond_32(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_31(Nat.is_eq(get_q_pending(s), Nat.sub(nth(get_hdr_total(s), i), nth(get_hdr_num(s), i))), s, i)
    case False{}:
      Revert{26n}
def _finalizeBatch_req_33(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_32(Bool.and(True{}, Bool.and(True{}, Bool.and(True{}, Nat.is_ge(nth(get_hdr_total(s), i), nth(get_hdr_num(s), i))) )), s, i)
def _finalizeBatch_cond_34(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_req_33(s, i)
    case False{}:
      _finalizeBatch_set_28(s, i)
def _finalizeBatch_cond_35(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_34(Nat.is_gt(nth(get_hdr_num(s), i), 0n), s, i)
    case False{}:
      Revert{26n}
def _finalizeBatch_if_36(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_35(Bool.and(True{}, True{}), s, i)
def _finalizeBatch_cond_37(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_if_36(set_finalized_root(s, put_nth(get_finalized_root(s), i, nth(get_state_root(s), i))), i)
    case False{}:
      Bound{}
def _finalizeBatch_cond_38(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_37(Nat.is_lt(i, 4n), s, i)
    case False{}:
      Revert{26n}
def _finalizeBatch_set_39(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_38(Bool.and(Bool.and(True{}, True{}), True{}), s, i)
def _finalizeBatch_cond_40(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_set_39(set_lastFinalized(s, i), i)
    case False{}:
      Revert{26n}
def _finalizeBatch_set_41(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_40(Bool.and(True{}, True{}), s, i)
def _finalizeBatch_cond_42(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_set_41(s, i)
    case False{}:
      Revert{6n}
def _finalizeBatch_cond_43(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_42(Nat.is_eq(nth(get_finalized_root(s), i), 0n), s, i)
    case False{}:
      Revert{6n}
def _finalizeBatch_req_44(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_43(Bool.and(True{}, True{}), s, i)
def _finalizeBatch_cond_45(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_req_44(s, i)
    case False{}:
      Revert{26n}
def _finalizeBatch_cond_46(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_45(Nat.is_eq(nth(get_finalized_root(s), Nat.sub(i, 1n)), nth(get_hdr_prev(s), i)), s, i)
    case False{}:
      Revert{26n}
def _finalizeBatch_req_47(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_46(Bool.and(Bool.and(True{}, Bool.and(True{}, Nat.is_ge(i, 1n)) ), True{}), s, i)
def _finalizeBatch_cond_48(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_req_47(s, i)
    case False{}:
      Revert{8n}
def _finalizeBatch_cond_49(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_48(Bool.not(Nat.is_gt(nth(get_fin_ts(s), i), get_now(s))), s, i)
    case False{}:
      Revert{8n}
def _finalizeBatch_req_50(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_49(Bool.and(True{}, True{}), s, i)
def _finalizeBatch_cond_51(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_req_50(s, i)
    case False{}:
      Revert{10n}
def _finalizeBatch_cond_52(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_51(Nat.is_eq(nth(get_chal_success(s), i), 0n), s, i)
    case False{}:
      Revert{10n}
def _finalizeBatch_req_53(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_52(Bool.and(True{}, True{}), s, i)
def _finalizeBatch_cond_54(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_req_53(s, i)
    case False{}:
      Revert{7n}
def _finalizeBatch_cond_55(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_54(Bool.not(Bool.and(Nat.is_ne(nth(get_chal_challenger(s), i), 0n), Nat.is_eq(nth(get_chal_finished(s), i), 0n))), s, i)
    case False{}:
      Revert{7n}
def _finalizeBatch_req_56(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_55(Bool.and(Bool.and(True{}, True{}), Bool.and(True{}, True{})), s, i)
def _finalizeBatch_cond_57(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_req_56(s, i)
    case False{}:
      Revert{9n}
def _finalizeBatch_cond_58(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_57(Bool.and(Nat.is_gt(nth(get_origin(s), i), 0n), Nat.is_ne(nth(get_committed(s), i), 0n)), s, i)
    case False{}:
      Revert{9n}
def _finalizeBatch_req_59(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_58(Bool.and(Bool.and(True{}, True{}), Bool.and(True{}, True{})), s, i)
def _finalizeBatch_cond_60(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_req_59(s, i)
    case False{}:
      Revert{16n}
def _finalizeBatch_cond_61(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_60(Nat.is_ne(nth(get_committed(s), i), 0n), s, i)
    case False{}:
      Revert{16n}
def _finalizeBatch_req_62(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_61(Bool.and(True{}, True{}), s, i)
def _finalizeBatch_cond_63(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_req_62(s, i)
    case False{}:
      Revert{1n}
def _finalizeBatch_cond_64(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_63(Nat.is_eq(get_paused(s), 0n), s, i)
    case False{}:
      Revert{1n}
def _finalizeBatch_req_65(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_64(Bool.and(True{}, True{}), s, i)
def _finalizeBatch_cond_66(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_req_65(s, i)
    case False{}:
      Revert{27n}
def _finalizeBatch_cond_67(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_cond_66(Nat.is_eq(get_revertReqIndex(s), 0n), s, i)
    case False{}:
      Revert{27n}
def _finalizeBatch_req_68(+s: State, +i: Nat) -> Outcome:
  _finalizeBatch_cond_67(Bool.and(True{}, True{}), s, i)
def _finalizeBatch_cond_69(c: Bool, +s: State) -> Outcome:
  match c:
    case True{}:
      _finalizeBatch_req_68(s, Nat.add(get_lastFinalized(s), 1n))
    case False{}:
      Revert{26n}
def _finalizeBatch_let_70(+s: State) -> Outcome:
  _finalizeBatch_cond_69(Bool.and(True{}, True{}), s)

def act_finalizeBatch(+s: State) -> Outcome:
  _finalizeBatch_let_70(s)

def _proveState_done_1(+s: State, +i: Nat) -> Outcome:
  Ok{s}
def _proveState_cond_2(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_done_1(set_submitter_active(s, 0n), i)
    case False{}:
      Revert{26n}
def _proveState_set_3(+s: State, +i: Nat) -> Outcome:
  _proveState_cond_2(Bool.and(True{}, True{}), s, i)
def _proveState_cond_4(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_set_3(s, i)
    case False{}:
      _proveState_done_1(s, i)
def _proveState_cond_5(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_cond_4(Nat.is_eq(nth(get_submitter(s), i), 1n), s, i)
    case False{}:
      Revert{26n}
def _proveState_if_6(+s: State, +i: Nat) -> Outcome:
  _proveState_cond_5(Bool.and(True{}, True{}), s, i)
def _proveState_cond_7(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_if_6(set_revertReqIndex(s, i), i)
    case False{}:
      Revert{26n}
def _proveState_set_8(+s: State, +i: Nat) -> Outcome:
  _proveState_cond_7(Bool.and(True{}, True{}), s, i)
def _proveState_cond_9(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_set_8(set_chal_success(s, put_nth(get_chal_success(s), i, 1n)), i)
    case False{}:
      Bound{}
def _proveState_cond_10(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_cond_9(Nat.is_lt(i, 4n), s, i)
    case False{}:
      Revert{26n}
def _proveState_set_11(+s: State, +i: Nat) -> Outcome:
  _proveState_cond_10(Bool.and(Bool.and(True{}, True{}), True{}), s, i)
def _proveState_cond_12(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_set_11(s, i)
    case False{}:
      _proveState_done_1(s, i)
def _proveState_cond_13(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_cond_12(Nat.is_le(Nat.add(nth(get_chal_start(s), i), 2n), get_now(s)), s, i)
    case False{}:
      Revert{26n}
def _proveState_if_14(+s: State, +i: Nat) -> Outcome:
  _proveState_cond_13(Bool.and(Bool.and(True{}, True{}), True{}), s, i)
def _proveState_cond_15(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_if_14(set_inChallenge(s, 0n), i)
    case False{}:
      Revert{26n}
def _proveState_set_16(+s: State, +i: Nat) -> Outcome:
  _proveState_cond_15(Bool.and(True{}, True{}), s, i)
def _proveState_cond_17(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_set_16(set_chal_finished(s, put_nth(get_chal_finished(s), i, 1n)), i)
    case False{}:
      Bound{}
def _proveState_cond_18(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_cond_17(Nat.is_lt(i, 4n), s, i)
    case False{}:
      Revert{26n}
def _proveState_set_19(+s: State, +i: Nat) -> Outcome:
  _proveState_cond_18(Bool.and(Bool.and(True{}, True{}), True{}), s, i)
def _proveState_cond_20(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_set_19(s, i)
    case False{}:
      Revert{7n}
def _proveState_cond_21(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_cond_20(Bool.and(Nat.is_ne(nth(get_chal_challenger(s), i), 0n), Nat.is_eq(nth(get_chal_finished(s), i), 0n)), s, i)
    case False{}:
      Revert{7n}
def _proveState_req_22(+s: State, +i: Nat) -> Outcome:
  _proveState_cond_21(Bool.and(Bool.and(True{}, True{}), Bool.and(True{}, True{})), s, i)
def _proveState_cond_23(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_req_22(s, i)
    case False{}:
      Revert{16n}
def _proveState_cond_24(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_cond_23(Nat.is_ne(nth(get_committed(s), i), 0n), s, i)
    case False{}:
      Revert{16n}
def _proveState_req_25(+s: State, +i: Nat) -> Outcome:
  _proveState_cond_24(Bool.and(True{}, True{}), s, i)
def _proveState_cond_26(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_req_25(s, i)
    case False{}:
      Revert{25n}
def _proveState_cond_27(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_cond_26(Nat.is_eq(get_submitter_active(s), 1n), s, i)
    case False{}:
      Revert{25n}
def _proveState_req_28(+s: State, +i: Nat) -> Outcome:
  _proveState_cond_27(Bool.and(True{}, True{}), s, i)
def _proveState_cond_29(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_req_28(s, i)
    case False{}:
      Revert{1n}
def _proveState_cond_30(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_cond_29(Nat.is_eq(get_paused(s), 0n), s, i)
    case False{}:
      Revert{1n}
def _proveState_req_31(+s: State, +i: Nat) -> Outcome:
  _proveState_cond_30(Bool.and(True{}, True{}), s, i)
def _proveState_cond_32(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_req_31(s, i)
    case False{}:
      Revert{27n}
def _proveState_cond_33(c: Bool, +s: State, +i: Nat) -> Outcome:
  match c:
    case True{}:
      _proveState_cond_32(Nat.is_eq(get_revertReqIndex(s), 0n), s, i)
    case False{}:
      Revert{27n}
def _proveState_req_34(+s: State, +i: Nat) -> Outcome:
  _proveState_cond_33(Bool.and(True{}, True{}), s, i)

def act_proveState(+s: State, i: Nat) -> Outcome:
  _proveState_req_34(s, i)

def _revertBatch_done_1(+s: State, +count: Nat, +idx: Nat) -> Outcome:
  Ok{s}
def _revertBatch_loop_body_done_2(+s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  Ok{s}
def _revertBatch_cond_3(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_loop_body_done_2(set_revertReqIndex(s, 0n), count, idx, j)
    case False{}:
      Revert{26n}
def _revertBatch_set_4(+s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  _revertBatch_cond_3(Bool.and(True{}, True{}), s, count, idx, j)
def _revertBatch_cond_5(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_set_4(s, count, idx, j)
    case False{}:
      _revertBatch_loop_body_done_2(s, count, idx, j)
def _revertBatch_cond_6(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_cond_5(Bool.and(Nat.is_gt(get_revertReqIndex(s), 0n), Nat.is_eq(j, get_revertReqIndex(s))), s, count, idx, j)
    case False{}:
      Revert{26n}
def _revertBatch_if_7(+s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  _revertBatch_cond_6(Bool.and(Bool.and(True{}, True{}), Bool.and(True{}, True{})), s, count, idx, j)
def _revertBatch_cond_8(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_if_7(set_chal_start(s, put_nth(get_chal_start(s), j, 0n)), count, idx, j)
    case False{}:
      Bound{}
def _revertBatch_cond_9(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_cond_8(Nat.is_lt(j, 4n), s, count, idx, j)
    case False{}:
      Revert{26n}
def _revertBatch_set_10(+s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  _revertBatch_cond_9(Bool.and(Bool.and(True{}, True{}), True{}), s, count, idx, j)
def _revertBatch_cond_11(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_set_10(set_chal_success(s, put_nth(get_chal_success(s), j, 0n)), count, idx, j)
    case False{}:
      Bound{}
def _revertBatch_cond_12(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_cond_11(Nat.is_lt(j, 4n), s, count, idx, j)
    case False{}:
      Revert{26n}
def _revertBatch_set_13(+s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  _revertBatch_cond_12(Bool.and(Bool.and(True{}, True{}), True{}), s, count, idx, j)
def _revertBatch_cond_14(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_set_13(set_chal_finished(s, put_nth(get_chal_finished(s), j, 0n)), count, idx, j)
    case False{}:
      Bound{}
def _revertBatch_cond_15(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_cond_14(Nat.is_lt(j, 4n), s, count, idx, j)
    case False{}:
      Revert{26n}
def _revertBatch_set_16(+s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  _revertBatch_cond_15(Bool.and(Bool.and(True{}, True{}), True{}), s, count, idx, j)
def _revertBatch_cond_17(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_set_16(set_chal_challenger(s, put_nth(get_chal_challenger(s), j, 0n)), count, idx, j)
    case False{}:
      Bound{}
def _revertBatch_cond_18(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_cond_17(Nat.is_lt(j, 4n), s, count, idx, j)
    case False{}:
      Revert{26n}
def _revertBatch_set_19(+s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  _revertBatch_cond_18(Bool.and(Bool.and(True{}, True{}), True{}), s, count, idx, j)
def _revertBatch_cond_20(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_set_19(set_inChallenge(s, 0n), count, idx, j)
    case False{}:
      Revert{26n}
def _revertBatch_set_21(+s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  _revertBatch_cond_20(Bool.and(True{}, True{}), s, count, idx, j)
def _revertBatch_cond_22(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_set_21(s, count, idx, j)
    case False{}:
      _revertBatch_set_19(s, count, idx, j)
def _revertBatch_cond_23(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_cond_22(Bool.and(Nat.is_ne(nth(get_chal_challenger(s), j), 0n), Nat.is_eq(nth(get_chal_finished(s), j), 0n)), s, count, idx, j)
    case False{}:
      Revert{26n}
def _revertBatch_if_24(+s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  _revertBatch_cond_23(Bool.and(Bool.and(True{}, True{}), Bool.and(True{}, True{})), s, count, idx, j)
def _revertBatch_cond_25(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_if_24(set_committed(s, put_nth(get_committed(s), j, 0n)), count, idx, j)
    case False{}:
      Bound{}
def _revertBatch_cond_26(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_cond_25(Nat.is_lt(j, 4n), s, count, idx, j)
    case False{}:
      Revert{26n}
def _revertBatch_set_27(+s: State, +count: Nat, +idx: Nat, +j: Nat) -> Outcome:
  _revertBatch_cond_26(Bool.and(Bool.and(True{}, True{}), True{}), s, count, idx, j)
def _revertBatch_cond_28(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat, +end: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_set_27(s, count, idx, j)
    case False{}:
      Ok{s}
def _revertBatch_cond_29(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat, +end: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_cond_28(Nat.is_ne(nth(get_committed(s), j), 0n), s, count, idx, j, end)
    case False{}:
      Revert{26n}
def _revertBatch_cond_30(c: Bool, +s: State, +count: Nat, +idx: Nat, +j: Nat, +end: Nat) -> Outcome:
  match c:
    case True{}:
      Ok{s}
    case False{}:
      _revertBatch_cond_29(Bool.and(True{}, True{}), s, count, idx, j, end)
def _revertBatch_body_guard_31(+s: State, +count: Nat, +idx: Nat, +j: Nat, +end: Nat) -> Outcome:
  _revertBatch_cond_30(Nat.is_gt(j, end), s, count, idx, j, end)
def _revertBatch_loop_32(fuel: Nat, o: Outcome, +s: State, +count: Nat, +idx: Nat, +j: Nat, +end: Nat) -> Outcome:
  match fuel:
    case 0n:
      match o:
      case Ok{+s2}:
        _revertBatch_done_1(s2, count, idx)
      case Revert{tag}:
        Revert{tag}
      case Bound{}:
        Bound{}
    case 1n+p:
      match o:
      case Ok{+s2}:
        _revertBatch_loop_32(p, _revertBatch_body_guard_31(s2, count, idx, Nat.add(j, 1n), end), s2, count, idx, Nat.add(j, 1n), end)
      case Revert{tag}:
        Revert{tag}
      case Bound{}:
        Bound{}
def _revertBatch_cond_33(c: Bool, +s: State, +count: Nat, +idx: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_loop_32(Nat.add(Nat.min(Nat.add(idx, Nat.sub(count, 1n)), 3n), 1n), _revertBatch_body_guard_31(s, count, idx, idx, Nat.min(Nat.add(idx, Nat.sub(count, 1n)), 3n)), s, count, idx, idx, Nat.min(Nat.add(idx, Nat.sub(count, 1n)), 3n))
    case False{}:
      Revert{26n}
def _revertBatch_cond_34(c: Bool, +s: State, +count: Nat, +idx: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_cond_33(Bool.and(True{}, Bool.and(True{}, Bool.and(True{}, Nat.is_ge(count, 1n)) )), s, count, idx)
    case False{}:
      Revert{26n}
def _revertBatch_for_35(+s: State, +count: Nat, +idx: Nat) -> Outcome:
  _revertBatch_cond_34(True{}, s, count, idx)
def _revertBatch_cond_36(c: Bool, +s: State, +count: Nat, +idx: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_for_35(set_lastCommitted(s, Nat.sub(idx, 1n)), count, idx)
    case False{}:
      Revert{26n}
def _revertBatch_set_37(+s: State, +count: Nat, +idx: Nat) -> Outcome:
  _revertBatch_cond_36(Bool.and(True{}, Bool.and(True{}, Bool.and(True{}, Nat.is_ge(idx, 1n)) )), s, count, idx)
def _revertBatch_cond_38(c: Bool, +s: State, +count: Nat, +idx: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_set_37(s, count, idx)
    case False{}:
      Revert{11n}
def _revertBatch_cond_39(c: Bool, +s: State, +count: Nat, +idx: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_cond_38(Nat.is_gt(idx, get_lastFinalized(s)), s, count, idx)
    case False{}:
      Revert{11n}
def _revertBatch_req_40(+s: State, +count: Nat, +idx: Nat) -> Outcome:
  _revertBatch_cond_39(Bool.and(True{}, True{}), s, count, idx)
def _revertBatch_cond_41(c: Bool, +s: State, +count: Nat, +idx: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_req_40(s, count, idx)
    case False{}:
      Revert{29n}
def _revertBatch_cond_42(c: Bool, +s: State, +count: Nat, +idx: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_cond_41(Nat.is_eq(nth(get_committed(s), Nat.add(idx, count)), 0n), s, count, idx)
    case False{}:
      Revert{29n}
def _revertBatch_req_43(+s: State, +count: Nat, +idx: Nat) -> Outcome:
  _revertBatch_cond_42(Bool.and(Bool.and(True{}, True{}), True{}), s, count, idx)
def _revertBatch_cond_44(c: Bool, +s: State, +count: Nat, +idx: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_req_43(s, count, idx)
    case False{}:
      Revert{16n}
def _revertBatch_cond_45(c: Bool, +s: State, +count: Nat, +idx: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_cond_44(Nat.is_ne(nth(get_committed(s), idx), 0n), s, count, idx)
    case False{}:
      Revert{16n}
def _revertBatch_req_46(+s: State, +count: Nat, +idx: Nat) -> Outcome:
  _revertBatch_cond_45(Bool.and(True{}, True{}), s, count, idx)
def _revertBatch_cond_47(c: Bool, +s: State, +count: Nat, +idx: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_req_46(s, count, idx)
    case False{}:
      Revert{15n}
def _revertBatch_cond_48(c: Bool, +s: State, +count: Nat, +idx: Nat) -> Outcome:
  match c:
    case True{}:
      _revertBatch_cond_47(Nat.is_gt(count, 0n), s, count, idx)
    case False{}:
      Revert{15n}
def _revertBatch_req_49(+s: State, +count: Nat, +idx: Nat) -> Outcome:
  _revertBatch_cond_48(Bool.and(True{}, True{}), s, count, idx)

def act_revertBatch(+s: State, count: Nat, idx: Nat) -> Outcome:
  _revertBatch_req_49(s, count, idx)

def _setPause_done_1(+s: State, +b: Nat) -> Outcome:
  Ok{s}
def _setPause_cond_2(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_done_1(set_inChallenge(s, 0n), b)
    case False{}:
      Revert{26n}
def _setPause_set_3(+s: State, +b: Nat) -> Outcome:
  _setPause_cond_2(Bool.and(True{}, True{}), s, b)
def _setPause_cond_4(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_set_3(set_chal_start(s, put_nth(get_chal_start(s), get_batchChallenged(s), 0n)), b)
    case False{}:
      Bound{}
def _setPause_cond_5(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_cond_4(Nat.is_lt(get_batchChallenged(s), 4n), s, b)
    case False{}:
      Revert{26n}
def _setPause_set_6(+s: State, +b: Nat) -> Outcome:
  _setPause_cond_5(Bool.and(Bool.and(True{}, True{}), True{}), s, b)
def _setPause_cond_7(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_set_6(set_chal_success(s, put_nth(get_chal_success(s), get_batchChallenged(s), 0n)), b)
    case False{}:
      Bound{}
def _setPause_cond_8(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_cond_7(Nat.is_lt(get_batchChallenged(s), 4n), s, b)
    case False{}:
      Revert{26n}
def _setPause_set_9(+s: State, +b: Nat) -> Outcome:
  _setPause_cond_8(Bool.and(Bool.and(True{}, True{}), True{}), s, b)
def _setPause_cond_10(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_set_9(set_chal_finished(s, put_nth(get_chal_finished(s), get_batchChallenged(s), 0n)), b)
    case False{}:
      Bound{}
def _setPause_cond_11(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_cond_10(Nat.is_lt(get_batchChallenged(s), 4n), s, b)
    case False{}:
      Revert{26n}
def _setPause_set_12(+s: State, +b: Nat) -> Outcome:
  _setPause_cond_11(Bool.and(Bool.and(True{}, True{}), True{}), s, b)
def _setPause_cond_13(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_set_12(set_chal_challenger(s, put_nth(get_chal_challenger(s), get_batchChallenged(s), 0n)), b)
    case False{}:
      Bound{}
def _setPause_cond_14(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_cond_13(Nat.is_lt(get_batchChallenged(s), 4n), s, b)
    case False{}:
      Revert{26n}
def _setPause_set_15(+s: State, +b: Nat) -> Outcome:
  _setPause_cond_14(Bool.and(Bool.and(True{}, True{}), True{}), s, b)
def _setPause_cond_16(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_set_15(s, b)
    case False{}:
      _setPause_done_1(s, b)
def _setPause_cond_17(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_cond_16(Nat.is_eq(get_inChallenge(s), 1n), s, b)
    case False{}:
      Revert{26n}
def _setPause_if_18(+s: State, +b: Nat) -> Outcome:
  _setPause_cond_17(Bool.and(True{}, True{}), s, b)
def _setPause_cond_19(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_if_18(set_paused(s, 1n), b)
    case False{}:
      Revert{26n}
def _setPause_set_20(+s: State, +b: Nat) -> Outcome:
  _setPause_cond_19(Bool.and(True{}, True{}), s, b)
def _setPause_cond_21(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_set_20(s, b)
    case False{}:
      Revert{1n}
def _setPause_cond_22(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_cond_21(Nat.is_eq(get_paused(s), 0n), s, b)
    case False{}:
      Revert{1n}
def _setPause_req_23(+s: State, +b: Nat) -> Outcome:
  _setPause_cond_22(Bool.and(True{}, True{}), s, b)
def _setPause_cond_24(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_done_1(set_paused(s, 0n), b)
    case False{}:
      Revert{26n}
def _setPause_set_25(+s: State, +b: Nat) -> Outcome:
  _setPause_cond_24(Bool.and(True{}, True{}), s, b)
def _setPause_cond_26(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_set_25(s, b)
    case False{}:
      Revert{0n}
def _setPause_cond_27(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_cond_26(Nat.is_eq(get_paused(s), 1n), s, b)
    case False{}:
      Revert{0n}
def _setPause_req_28(+s: State, +b: Nat) -> Outcome:
  _setPause_cond_27(Bool.and(True{}, True{}), s, b)
def _setPause_cond_29(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_req_23(s, b)
    case False{}:
      _setPause_req_28(s, b)
def _setPause_cond_30(c: Bool, +s: State, +b: Nat) -> Outcome:
  match c:
    case True{}:
      _setPause_cond_29(Nat.is_eq(b, 1n), s, b)
    case False{}:
      Revert{26n}
def _setPause_if_31(+s: State, +b: Nat) -> Outcome:
  _setPause_cond_30(Bool.and(True{}, True{}), s, b)

def act_setPause(+s: State, b: Nat) -> Outcome:
  _setPause_if_31(s, b)

def _tick_done_1(+s: State, +d: Nat) -> Outcome:
  Ok{s}
def _tick_cond_2(c: Bool, +s: State, +d: Nat) -> Outcome:
  match c:
    case True{}:
      _tick_done_1(set_now(s, Nat.add(get_now(s), d)), d)
    case False{}:
      Revert{26n}
def _tick_set_3(+s: State, +d: Nat) -> Outcome:
  _tick_cond_2(Bool.and(True{}, Bool.and(True{}, True{})), s, d)
def _tick_cond_4(c: Bool, +s: State, +d: Nat) -> Outcome:
  match c:
    case True{}:
      Bound{}
    case False{}:
      _tick_set_3(s, d)
def _tick_cond_5(c: Bool, +s: State, +d: Nat) -> Outcome:
  match c:
    case True{}:
      _tick_cond_4(Nat.is_gt(Nat.add(get_now(s), d), 12n), s, d)
    case False{}:
      Revert{26n}
def _tick_bound_6(+s: State, +d: Nat) -> Outcome:
  _tick_cond_5(Bool.and(True{}, True{}), s, d)

def act_tick(+s: State, d: Nat) -> Outcome:
  _tick_bound_6(s, d)

def init_state() -> State:
  State{0n, 0n, 0n, 0n, 0n, 0n, 1n, 0n, 0n, 1n, [1n, 0n, 0n, 0n], [1n, 0n, 0n, 0n], [0n, 0n, 0n, 0n], [0n, 0n, 0n, 0n], [0n, 0n, 0n, 0n], [1n, 0n, 0n, 0n], [1n, 0n, 0n, 0n], [1n, 0n, 0n, 0n], [0n, 0n, 0n, 0n], [0n, 0n, 0n, 0n], [0n, 0n, 0n, 0n], [0n, 0n, 0n, 0n], [0n, 0n, 0n, 0n], [1n, 0n, 0n, 0n], [0n, 0n]}

def keep(o: Outcome, acc: List<&2, State>) -> List<&2, State>:
  match o:
    case Ok{+state}:
      Con{state, acc}
    case Revert{tag}:
      acc
    case Bound{}:
      acc

def succs(+s: State) -> List<&2, State>:
  keep(act_addSubmitter(s), keep(act_challengeState(s, 1n), keep(act_challengeState(s, 2n), keep(act_challengeState(s, 3n), keep(act_commitBatch(s, 0n, 1n), keep(act_commitBatch(s, 0n, 2n), keep(act_commitBatch(s, 1n, 1n), keep(act_commitBatch(s, 1n, 2n), keep(act_commitBatchWithProof(s, 0n, 1n), keep(act_commitBatchWithProof(s, 0n, 2n), keep(act_commitBatchWithProof(s, 1n, 1n), keep(act_commitBatchWithProof(s, 1n, 2n), keep(act_commitState(s, 0n, 1n), keep(act_commitState(s, 0n, 2n), keep(act_commitState(s, 1n, 1n), keep(act_commitState(s, 1n, 2n), keep(act_enqueue(s), keep(act_finalizeBatch(s), keep(act_proveState(s, 1n), keep(act_proveState(s, 2n), keep(act_proveState(s, 3n), keep(act_revertBatch(s, 1n, 1n), keep(act_revertBatch(s, 1n, 2n), keep(act_revertBatch(s, 1n, 3n), keep(act_revertBatch(s, 2n, 1n), keep(act_revertBatch(s, 2n, 2n), keep(act_revertBatch(s, 2n, 3n), keep(act_revertBatch(s, 3n, 1n), keep(act_revertBatch(s, 3n, 2n), keep(act_revertBatch(s, 3n, 3n), keep(act_setPause(s, 0n), keep(act_setPause(s, 1n), keep(act_tick(s, 1n), keep(act_tick(s, 2n), Nil{}))))))))))))))))))))))))))))))))))

def contains_state(xs: List<&2, State>, +s: State) -> Bool:
  match xs:
    case Nil{}:
      False{}
    case Con{h, t}:
      Bool.or(state_eq(h, s), contains_state(t, s))

def add_fresh(+xs: List<&2, State>, +seen: List<&2, State>) -> List<&2, State>:
  match xs:
    case Nil{}:
      Nil{}
    case Con{+h, +t}:
      List.append(&2, State,
        Bool.pick(List<&2, State>, contains_state(seen, h), Nil{}, [h]),
        add_fresh(t, Bool.pick(List<&2, State>, contains_state(seen, h), seen, Con{h, seen})))

def expand_all(xs: List<&2, State>) -> List<&2, State>:
  match xs:
    case Nil{}:
      Nil{}
    case Con{h, t}:
      List.append(&2, State, succs(h), expand_all(t))

def reach_n(k: Nat, frontier: List<&2, State>, +seen: List<&2, State>) -> List<&2, State>:
  match k:
    case 0n:
      seen
    case 1n+p:
      +fresh = add_fresh(expand_all(frontier), seen)
      reach_n(p, fresh, List.append(&2, State, seen, fresh))

def reach_k(k: Nat) -> List<&2, State>:
  reach_n(k, [init_state()], [init_state()])

