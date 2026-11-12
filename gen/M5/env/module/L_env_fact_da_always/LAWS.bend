import Base
import ../../model/env.bend as M

law cl_l_env_fact_da_always:
  exs age: U32
  {M.da_deliver(age, 0) != Some{0} : Maybe<&2, U32>}
