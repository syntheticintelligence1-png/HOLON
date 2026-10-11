import Base
import ../model/rollup_sm.bend as M

def check_all(xs: List<&2, M.State>) -> Bool:
  match xs:
    case Nil{}:
      True{}
    case Con{+h, +t}:
      Bool.and(True{}, check_all(t))

def check_reach(k: Nat, +frontier: List<&2, M.State>) -> Bool:
  match k:
    case 0n:
      check_all(frontier)
    case 1n+p:
      Bool.and(check_all(frontier),
        check_reach(p, M.expand_all(frontier)))

law fused3:
  {check_reach(3n, [M.init_state()]) == True{} : Bool}

def fused3():
  {==}
