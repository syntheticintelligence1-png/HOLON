import Base
import ../model/rollup_sm.bend as M
import ./LAWS.bend as Laws

def Laws.cl_l_undo_pause():
  (Con{Laws.TraceStep{2n, 0n, 1n}, Con{Laws.TraceStep{2n, 0n, 1n}, Nil{}}}, e => (%e : M.is_true(M.bool_eq(_, Laws.refutes_l_undo_pause(Con{Laws.TraceStep{2n, 0n, 1n}, Con{Laws.TraceStep{2n, 0n, 1n}, Nil{}}})))
  Unit{}))
