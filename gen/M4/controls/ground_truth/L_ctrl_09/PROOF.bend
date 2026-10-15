import Base
import ../../model/eval_ctrl_machine.bend as M
import ./LAWS.bend as Laws

def lock_idemp_full(stage: Nat, seq: Nat, mirror: Nat, acc: Nat, tier: Nat, b: Bool, halted: Bool, alert: Bool, overflow: Bool, breach: Bool, diff_zero: Bool, parity: Bool, log: List<&2, M.HObs>) -> {M.obsv_locked(M.step_lock_restore(M.HSt{stage, seq, mirror, acc, tier, b, halted, alert, overflow, breach, diff_zero, parity, log})) == b : Bool}:
  match b:
    case False{}:
      {==}
    case True{}:
      {==}

def Laws.l_ctrl_09(s, r_s):
  match s:
    case M.HSt{stage, seq, mirror, acc, tier, locked, halted, alert, overflow, breach, diff_zero, parity, log}:
      lock_idemp_full(stage, seq, mirror, acc, tier, locked, halted, alert, overflow, breach, diff_zero, parity, log)
