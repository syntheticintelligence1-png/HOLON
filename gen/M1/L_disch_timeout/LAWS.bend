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

def goal_l_disch_timeout(+s: M.State) -> Bool:
  Nat.is_eq(M.get_inChallenge(s), 0n)

def role_succs_l_disch_timeout(+s: M.State) -> List<&2, M.State>:
  M.keep(M.act_challengeState(s, 1n), M.keep(M.act_challengeState(s, 2n), M.keep(M.act_challengeState(s, 3n), M.keep(M.act_commitBatchWithProof(s, 0n, 1n), M.keep(M.act_commitBatchWithProof(s, 0n, 2n), M.keep(M.act_commitBatchWithProof(s, 1n, 1n), M.keep(M.act_commitBatchWithProof(s, 1n, 2n), M.keep(M.act_enqueue(s), M.keep(M.act_finalizeBatch(s), M.keep(M.act_tick(s, 1n), M.keep(M.act_tick(s, 2n), Nil{})))))))))))

def exp_l_disch_timeout(+xs: List<&2, M.State>) -> List<&2, M.State>:
  match xs:
    case Nil{}:
      Nil{}
    case Con{+h, +t}:
      List.append(&2, M.State, role_succs_l_disch_timeout(h), exp_l_disch_timeout(t))

def any_goal_l_disch_timeout(+xs: List<&2, M.State>) -> Bool:
  match xs:
    case Nil{}:
      False{}
    case Con{+h, +t}:
      Bool.or(goal_l_disch_timeout(h), any_goal_l_disch_timeout(t))

def reachw_l_disch_timeout(+p: Nat, +frontier: List<&2, M.State>) -> Bool:
  match p:
    case 0n:
      any_goal_l_disch_timeout(frontier)
    case 1n+q:
      Bool.or(any_goal_l_disch_timeout(frontier), reachw_l_disch_timeout(q, exp_l_disch_timeout(frontier)))

def search_l_disch_timeout(+s: M.State, depth: Nat) -> Bool:
  reachw_l_disch_timeout(depth, [s])

def check_l_disch_timeout_assignment(+s: M.State, index: Nat) -> Bool:
  match index:
    case 0n:
      Bool.or(Bool.not(Bool.and(Nat.is_eq(M.get_inChallenge(s), 1n), Nat.is_lt(Nat.add(M.nth(M.get_chal_start(s), M.get_batchChallenged(s)), 2n), M.get_now(s)))), search_l_disch_timeout(s, 3n))
    case 1n+p:
      False{}

def check_l_disch_timeout(+s: M.State) -> Bool:
  check_l_disch_timeout_assignment(s, 0n)

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

def run_trace_l_disch_timeout(trace: List<&2, TraceStep>, o: M.Outcome) -> M.Outcome:
  match trace:
    case Nil{}:
      o
    case Con{+step, +rest}:
      match o:
        case M.Ok{+s}:
          run_trace_l_disch_timeout(rest, apply_step(s, step))
        case M.Revert{tag}:
          M.Revert{tag}
        case M.Bound{}:
          M.Bound{}

def rf_l_disch_timeout(o: M.Outcome) -> Bool:
  match o:
    case M.Ok{+s}:
      Bool.not(check_l_disch_timeout(s))
    case M.Revert{tag}:
      False{}
    case M.Bound{}:
      False{}

def refutes_l_disch_timeout(trace: List<&2, TraceStep>) -> Bool:
  rf_l_disch_timeout(run_trace_l_disch_timeout(trace, M.Ok{M.init_state()}))

law cl_l_disch_timeout:
  exs trace: List<&2, TraceStep>
  {refutes_l_disch_timeout(trace) != False{} : Bool}
