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

def check_l_inv_prefix_assignment(+s: M.State, index: Nat) -> Bool:
  match index:
    case 0n:
      Bool.and(Nat.is_le(M.get_lastFinalized(s), M.get_lastCommitted(s)), Bool.and(Bool.and(M.bool_eq(Nat.is_ne(M.nth(M.get_committed(s), 0n), 0n), Nat.is_le(0n, M.get_lastCommitted(s))), Bool.and(M.bool_eq(Nat.is_ne(M.nth(M.get_committed(s), 1n), 0n), Nat.is_le(1n, M.get_lastCommitted(s))), Bool.and(M.bool_eq(Nat.is_ne(M.nth(M.get_committed(s), 2n), 0n), Nat.is_le(2n, M.get_lastCommitted(s))), M.bool_eq(Nat.is_ne(M.nth(M.get_committed(s), 3n), 0n), Nat.is_le(3n, M.get_lastCommitted(s)))))), Bool.and(Bool.or(Bool.not(Nat.is_le(0n, M.get_lastFinalized(s))), Nat.is_ne(M.nth(M.get_finalized_root(s), 0n), 0n)), Bool.and(Bool.or(Bool.not(Nat.is_le(1n, M.get_lastFinalized(s))), Nat.is_ne(M.nth(M.get_finalized_root(s), 1n), 0n)), Bool.and(Bool.or(Bool.not(Nat.is_le(2n, M.get_lastFinalized(s))), Nat.is_ne(M.nth(M.get_finalized_root(s), 2n), 0n)), Bool.or(Bool.not(Nat.is_le(3n, M.get_lastFinalized(s))), Nat.is_ne(M.nth(M.get_finalized_root(s), 3n), 0n)))))))
    case 1n+p:
      False{}

def check_l_inv_prefix(+s: M.State) -> Bool:
  check_l_inv_prefix_assignment(s, 0n)

def all_states_l_inv_prefix(states: List<&2, M.State>) -> Bool:
  match states:
    case Nil{}:
      True{}
    case Con{state, rest}:
      Bool.and(check_l_inv_prefix(state), all_states_l_inv_prefix(rest))

law l_inv_prefix:
  {all_states_l_inv_prefix(M.reach_k(3n)) == True{} : Bool}
