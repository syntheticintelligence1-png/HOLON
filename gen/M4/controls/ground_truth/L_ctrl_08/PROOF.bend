import Base
import ../../model/eval_ctrl_machine.bend as M
import ./LAWS.bend as Laws

def bool_not_not(b: Bool) -> {Bool.not(Bool.not(b)) == b : Bool}:
  match b:
    case False{}:
      {==}
    case True{}:
      {==}

def Laws.l_ctrl_08(s, r_s):
  match s:
    case M.HSt{stage, seq, mirror, acc, tier, locked, halted, alert, overflow, breach, diff_zero, parity, log}:
      bool_not_not(parity)
