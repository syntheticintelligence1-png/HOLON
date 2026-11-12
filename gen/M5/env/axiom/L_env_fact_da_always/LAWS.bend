import Base
import ../../model/env.bend as M

law cl_l_env_fact_da_always:
  exs av: U32 -> Bool
  {M.serve(av(0), 0) != Some{0} : Maybe<&2, U32>}
