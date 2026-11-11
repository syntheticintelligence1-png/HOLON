import Base
import ../../model/env.bend as M

law l_env_fact_fetch:
  for x: U32
  {M.fetch_deliver(True{}, x) == Some{x} : Maybe<&2, U32>}
