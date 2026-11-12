import Base
import ../../model/env.bend as M

law l_env_undo_reorg:
  for k: Nat
  for e: Nat
  for h: {M.le(k, M.D()) == True{} : Bool}
  {M.removed(k, M.consumed_depth(e)) == False{} : Bool}
