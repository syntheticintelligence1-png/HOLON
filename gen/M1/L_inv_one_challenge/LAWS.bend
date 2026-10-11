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

def check_l_inv_one_challenge_assignment(+s: M.State, index: Nat) -> Bool:
  match index:
    case 0n:
      Bool.and(M.bool_eq(Nat.is_eq(M.get_inChallenge(s), 1n), Bool.and(Nat.is_ne(M.nth(M.get_chal_challenger(s), M.get_batchChallenged(s)), 0n), Nat.is_eq(M.nth(M.get_chal_finished(s), M.get_batchChallenged(s)), 0n))), Bool.and(Bool.or(Bool.not(Nat.is_ne(0n, M.get_batchChallenged(s))), Bool.not(Bool.and(Nat.is_ne(M.nth(M.get_chal_challenger(s), 0n), 0n), Nat.is_eq(M.nth(M.get_chal_finished(s), 0n), 0n)))), Bool.and(Bool.or(Bool.not(Nat.is_ne(1n, M.get_batchChallenged(s))), Bool.not(Bool.and(Nat.is_ne(M.nth(M.get_chal_challenger(s), 1n), 0n), Nat.is_eq(M.nth(M.get_chal_finished(s), 1n), 0n)))), Bool.and(Bool.or(Bool.not(Nat.is_ne(2n, M.get_batchChallenged(s))), Bool.not(Bool.and(Nat.is_ne(M.nth(M.get_chal_challenger(s), 2n), 0n), Nat.is_eq(M.nth(M.get_chal_finished(s), 2n), 0n)))), Bool.or(Bool.not(Nat.is_ne(3n, M.get_batchChallenged(s))), Bool.not(Bool.and(Nat.is_ne(M.nth(M.get_chal_challenger(s), 3n), 0n), Nat.is_eq(M.nth(M.get_chal_finished(s), 3n), 0n))))))))
    case 1n+p:
      False{}

def check_l_inv_one_challenge(+s: M.State) -> Bool:
  check_l_inv_one_challenge_assignment(s, 0n)

def all_states_l_inv_one_challenge(states: List<&2, M.State>) -> Bool:
  match states:
    case Nil{}:
      True{}
    case Con{state, rest}:
      Bool.and(check_l_inv_one_challenge(state), all_states_l_inv_one_challenge(rest))

law l_inv_one_challenge:
  {all_states_l_inv_one_challenge(M.reach_k(3n)) == True{} : Bool}
