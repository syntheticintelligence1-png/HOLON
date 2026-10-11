import Base
import ../model/rollup_sm.bend as M
import ./LAWS.bend as Laws

def Laws.cl_l_nat_delay_frontier():
  (Con{Laws.TraceStep{5n, 0n, 0n}, Con{Laws.TraceStep{2n, 1n, 1n}, Con{Laws.TraceStep{10n, 2n, 0n}, Con{Laws.TraceStep{10n, 2n, 0n}, Nil{}}}}}, e => (%e : M.is_true(M.bool_eq(_, Laws.refutes_l_nat_delay_frontier(Con{Laws.TraceStep{5n, 0n, 0n}, Con{Laws.TraceStep{2n, 1n, 1n}, Con{Laws.TraceStep{10n, 2n, 0n}, Con{Laws.TraceStep{10n, 2n, 0n}, Nil{}}}}})))
  Unit{}))
