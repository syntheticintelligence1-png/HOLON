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

def check_l_nat_delay_frontier_assignment(+s: M.State, index: Nat) -> Bool:
  match index:
    case 0n:
      Bool.or(Bool.not(Bool.and(Nat.is_lt(0n, M.get_q_len(s)), Nat.is_eq(M.nth(M.get_hdr_total(s), M.get_lastCommitted(s)), M.get_q_len(s)))), Nat.is_ne(out_tag(M.act_commitBatch(s, 0n, 1n)), 21n))
    case 1n+p:
      False{}

def check_l_nat_delay_frontier(+s: M.State) -> Bool:
  check_l_nat_delay_frontier_assignment(s, 0n)

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

def run_trace_l_nat_delay_frontier(trace: List<&2, TraceStep>, o: M.Outcome) -> M.Outcome:
  match trace:
    case Nil{}:
      o
    case Con{+step, +rest}:
      match o:
        case M.Ok{+s}:
          run_trace_l_nat_delay_frontier(rest, apply_step(s, step))
        case M.Revert{tag}:
          M.Revert{tag}
        case M.Bound{}:
          M.Bound{}

def rf_l_nat_delay_frontier(o: M.Outcome) -> Bool:
  match o:
    case M.Ok{+s}:
      Bool.not(check_l_nat_delay_frontier(s))
    case M.Revert{tag}:
      False{}
    case M.Bound{}:
      False{}

def refutes_l_nat_delay_frontier(trace: List<&2, TraceStep>) -> Bool:
  rf_l_nat_delay_frontier(run_trace_l_nat_delay_frontier(trace, M.Ok{M.init_state()}))

law cl_l_nat_delay_frontier:
  exs trace: List<&2, TraceStep>
  {refutes_l_nat_delay_frontier(trace) != False{} : Bool}
