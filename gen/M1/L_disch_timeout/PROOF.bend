import Base
import ../model/rollup_sm.bend as M
import ./LAWS.bend as Laws

def Laws.cl_l_disch_timeout():
  (Con{Laws.TraceStep{2n, 0n, 1n}, Con{Laws.TraceStep{1n, 1n, 0n}, Con{Laws.TraceStep{10n, 1n, 0n}, Con{Laws.TraceStep{10n, 2n, 0n}, Nil{}}}}}, e => (%e : M.is_true(M.bool_eq(_, Laws.refutes_l_disch_timeout(Con{Laws.TraceStep{2n, 0n, 1n}, Con{Laws.TraceStep{1n, 1n, 0n}, Con{Laws.TraceStep{10n, 1n, 0n}, Con{Laws.TraceStep{10n, 2n, 0n}, Nil{}}}}})))
  Unit{}))
