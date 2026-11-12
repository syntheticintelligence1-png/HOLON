import Base
import ../../model/env.bend as M

law cl_l_env_fact_da_window:
  exs av: U32 -> Bool
  {M.da_within(0) == True{} : Bool} & {M.serve(av(0), 0) != Some{0} : Maybe<&2, U32>}
