import Base
import ../../model/env.bend as M

law cl_l_env_fact_fetch:
  exs fa: Bool -> Bool
  {M.serve(fa(True{}), 0) != Some{0} : Maybe<&2, U32>}
