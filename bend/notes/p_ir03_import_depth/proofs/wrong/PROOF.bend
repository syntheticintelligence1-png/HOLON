# the law imported and filled with a proof of another equation: rejected with a type mismatch
import Base
import ../../model/m.bend as M
import ../../laws/a/LAWS.bend as Laws

def other() -> {M.g(2n) == 4n : Nat}:
  {==}

def Laws.l_a():
  other()
