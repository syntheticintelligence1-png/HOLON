import Base
import ../model/rollup_sm.bend as M

def llen(xs: List<&2, M.State>) -> Nat:
  match xs:
    case Nil{}:
      0n
    case Con{head, rest}:
      Nat.add(1n, llen(rest))

law len3:
  {Nat.is_ne(llen(M.reach_k(3n)), 0n) == True{} : Bool}

def len3():
  {==}
