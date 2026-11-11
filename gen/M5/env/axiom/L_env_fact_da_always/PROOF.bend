import Base
import ./LAWS.bend as Laws
import ../../model/env.bend as M

def Laws.cl_l_env_fact_da_always():
  (x => False{}, e => (%e : M.is_none(_)
  Unit{}))
