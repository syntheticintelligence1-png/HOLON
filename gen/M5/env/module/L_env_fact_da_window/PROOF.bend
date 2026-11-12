import Base
import ./LAWS.bend as Laws
import ../../model/env.bend as M

def Laws.l_env_fact_da_window(age, x, h):
  %Equal.sym(Bool, M.da_within(age), True{}, h) : {M.serve(_, x) == Some{x} : Maybe<&2, U32>}
  {==}
