import Base
import ../../model/env.bend as M

law l_env_fact_da_window:
  for age: U32
  for x: U32
  for h: {M.da_within(age) == True{} : Bool}
  {M.da_deliver(age, x) == Some{x} : Maybe<&2, U32>}
