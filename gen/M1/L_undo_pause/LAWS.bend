import Base
import ../model/rollup_sm.bend as M

def is_ok(o: M.Outcome) -> Bool:
  match o:
    case M.Ok{state}:
      True{}
    case M.Revert{tag}:
      False{}
    case M.Bound{}:
      False{}

def out_tag(o: M.Outcome) -> Nat:
  match o:
    case M.Ok{state}:
      31n
    case M.Revert{tag}:
      tag
    case M.Bound{}:
      32n

def i_l_undo_pause_0_2(o: M.Outcome, +s: M.State, +s1: M.State, +s2: M.State) -> Bool:
  match o:
    case M.Ok{+s3}:
      Bool.and(M.nat_list_eq(M.get_fin_ts(s), M.get_fin_ts(s3)), Bool.and(M.nat_list_eq(M.get_chal_challenger(s), M.get_chal_challenger(s3)), Bool.and(M.nat_list_eq(M.get_chal_start(s), M.get_chal_start(s3)), Nat.is_eq(M.get_inChallenge(s), M.get_inChallenge(s3)))))
    case M.Revert{tag}:
      True{}
    case M.Bound{}:
      True{}

def i_l_undo_pause_0_1(o: M.Outcome, +s: M.State, +s1: M.State) -> Bool:
  match o:
    case M.Ok{+s2}:
      i_l_undo_pause_0_2(M.act_setPause(s2, 0n), s, s1, s2)
    case M.Revert{tag}:
      True{}
    case M.Bound{}:
      True{}

def i_l_undo_pause_0_0(o: M.Outcome, +s: M.State) -> Bool:
  match o:
    case M.Ok{+s1}:
      i_l_undo_pause_0_1(M.act_setPause(s1, 1n), s, s1)
    case M.Revert{tag}:
      True{}
    case M.Bound{}:
      True{}

def i_l_undo_pause_1_2(o: M.Outcome, +s: M.State, +s1: M.State, +s2: M.State) -> Bool:
  match o:
    case M.Ok{+s3}:
      Bool.and(M.nat_list_eq(M.get_fin_ts(s), M.get_fin_ts(s3)), Bool.and(M.nat_list_eq(M.get_chal_challenger(s), M.get_chal_challenger(s3)), Bool.and(M.nat_list_eq(M.get_chal_start(s), M.get_chal_start(s3)), Nat.is_eq(M.get_inChallenge(s), M.get_inChallenge(s3)))))
    case M.Revert{tag}:
      True{}
    case M.Bound{}:
      True{}

def i_l_undo_pause_1_1(o: M.Outcome, +s: M.State, +s1: M.State) -> Bool:
  match o:
    case M.Ok{+s2}:
      i_l_undo_pause_1_2(M.act_setPause(s2, 0n), s, s1, s2)
    case M.Revert{tag}:
      True{}
    case M.Bound{}:
      True{}

def i_l_undo_pause_1_0(o: M.Outcome, +s: M.State) -> Bool:
  match o:
    case M.Ok{+s1}:
      i_l_undo_pause_1_1(M.act_setPause(s1, 1n), s, s1)
    case M.Revert{tag}:
      True{}
    case M.Bound{}:
      True{}

def i_l_undo_pause_2_2(o: M.Outcome, +s: M.State, +s1: M.State, +s2: M.State) -> Bool:
  match o:
    case M.Ok{+s3}:
      Bool.and(M.nat_list_eq(M.get_fin_ts(s), M.get_fin_ts(s3)), Bool.and(M.nat_list_eq(M.get_chal_challenger(s), M.get_chal_challenger(s3)), Bool.and(M.nat_list_eq(M.get_chal_start(s), M.get_chal_start(s3)), Nat.is_eq(M.get_inChallenge(s), M.get_inChallenge(s3)))))
    case M.Revert{tag}:
      True{}
    case M.Bound{}:
      True{}

def i_l_undo_pause_2_1(o: M.Outcome, +s: M.State, +s1: M.State) -> Bool:
  match o:
    case M.Ok{+s2}:
      i_l_undo_pause_2_2(M.act_setPause(s2, 0n), s, s1, s2)
    case M.Revert{tag}:
      True{}
    case M.Bound{}:
      True{}

def i_l_undo_pause_2_0(o: M.Outcome, +s: M.State) -> Bool:
  match o:
    case M.Ok{+s1}:
      i_l_undo_pause_2_1(M.act_setPause(s1, 1n), s, s1)
    case M.Revert{tag}:
      True{}
    case M.Bound{}:
      True{}

def check_l_undo_pause_assignment(+s: M.State, index: Nat) -> Bool:
  match index:
    case 0n:
      i_l_undo_pause_0_0(M.act_challengeState(s, 1n), s)
    case 1n:
      i_l_undo_pause_1_0(M.act_challengeState(s, 2n), s)
    case 2n:
      i_l_undo_pause_2_0(M.act_challengeState(s, 3n), s)
    case 3n+p:
      False{}

def check_l_undo_pause(+s: M.State) -> Bool:
  Bool.and(check_l_undo_pause_assignment(s, 0n), Bool.and(check_l_undo_pause_assignment(s, 1n), check_l_undo_pause_assignment(s, 2n)))

type TraceStep is Data:
  TraceStep{action: Nat, p0: Nat, p1: Nat}

def apply_step(+s: M.State, step: TraceStep) -> M.Outcome:
  match step:
    case TraceStep{action, p0, p1}:
      match action:
        case 0n:
          M.act_addSubmitter(s)
        case 1n:
          M.act_challengeState(s, p0)
        case 2n:
          M.act_commitBatch(s, p0, p1)
        case 3n:
          M.act_commitBatchWithProof(s, p0, p1)
        case 4n:
          M.act_commitState(s, p0, p1)
        case 5n:
          M.act_enqueue(s)
        case 6n:
          M.act_finalizeBatch(s)
        case 7n:
          M.act_proveState(s, p0)
        case 8n:
          M.act_revertBatch(s, p0, p1)
        case 9n:
          M.act_setPause(s, p0)
        case 10n:
          M.act_tick(s, p0)
        case 11n+p:
          M.Bound{}

def run_trace_l_undo_pause(trace: List<&2, TraceStep>, o: M.Outcome) -> M.Outcome:
  match trace:
    case Nil{}:
      o
    case Con{+step, +rest}:
      match o:
        case M.Ok{+s}:
          run_trace_l_undo_pause(rest, apply_step(s, step))
        case M.Revert{tag}:
          M.Revert{tag}
        case M.Bound{}:
          M.Bound{}

def rf_l_undo_pause(o: M.Outcome) -> Bool:
  match o:
    case M.Ok{+s}:
      Bool.not(check_l_undo_pause(s))
    case M.Revert{tag}:
      False{}
    case M.Bound{}:
      False{}

def refutes_l_undo_pause(trace: List<&2, TraceStep>) -> Bool:
  rf_l_undo_pause(run_trace_l_undo_pause(trace, M.Ok{M.init_state()}))

law cl_l_undo_pause:
  exs trace: List<&2, TraceStep>
  {refutes_l_undo_pause(trace) != False{} : Bool}
