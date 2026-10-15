import Base
import ../../model/eval_ctrl_machine.bend as M
import ./LAWS.bend as Laws

def add_zero_right(k: Nat) -> {Nat.add(k, 0n) == k : Nat}:
  match k:
    case 0n:
      {==}
    case 1n+p:
      (%add_zero_right(p) : {1n+Nat.add(p, 0n) == 1n+_ : Nat}
      {==})

def add_succ_right(a: Nat, +b: Nat) -> {Nat.add(a, 1n+b) == 1n+Nat.add(a, b) : Nat}:
  match a:
    case 0n:
      {==}
    case 1n+p:
      (%add_succ_right(p, b) : {1n+Nat.add(p, 1n+b) == 1n+_ : Nat}
      {==})

def add_comm(+a: Nat, +b: Nat) -> {Nat.add(a, b) == Nat.add(b, a) : Nat}:
  match a:
    case 0n:
      Equal.sym(Nat, Nat.add(b, 0n), b, add_zero_right(b))
    case 1n+p:
      Equal.trans(Nat, 1n+Nat.add(p, b), 1n+Nat.add(b, p), Nat.add(b, 1n+p),
        (%add_comm(p, b) : {1n+Nat.add(p, b) == 1n+_ : Nat}; {==}),
        Equal.sym(Nat, Nat.add(b, 1n+p), 1n+Nat.add(b, p), add_succ_right(b, p)))

def Laws.l_ctrl_11(s, r_s, x):
  match s:
    case M.HSt{stage, seq, mirror, acc, tier, locked, halted, alert, overflow, breach, diff_zero, parity, log}:
      add_comm(seq, x)
