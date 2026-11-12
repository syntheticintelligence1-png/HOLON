import Base
import ../../model/env.bend as M

law cl_l_env_undo_reorg:
  exs k: Nat
  {M.removed(k, M.consumed_depth(0n)) != False{} : Bool}
