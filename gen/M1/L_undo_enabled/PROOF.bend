import Base
import ../model/rollup_sm.bend as M
import ./LAWS.bend as Laws

def Laws.cl_l_undo_enabled():
  (Nil{}, e => (%e : M.is_true(M.bool_eq(_, Laws.refutes_l_undo_enabled(Nil{})))
  Unit{}))
