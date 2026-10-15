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

def add_comm(+x: Nat, +y: Nat) -> {Nat.add(x, y) == Nat.add(y, x) : Nat}:
  match x:
    case 0n:
      Equal.sym(Nat, Nat.add(y, 0n), y, add_zero_right(y))
    case 1n+p:
      Equal.trans(Nat, 1n+Nat.add(p, y), 1n+Nat.add(y, p), Nat.add(y, 1n+p),
        (%add_comm(p, y) : {1n+Nat.add(p, y) == 1n+_ : Nat}; {==}),
        Equal.sym(Nat, Nat.add(y, 1n+p), 1n+Nat.add(y, p), add_succ_right(y, p)))

def add_right_comm(a: Nat, +x: Nat, +y: Nat) -> {Nat.add(Nat.add(a, x), y) == Nat.add(Nat.add(a, y), x) : Nat}:
  match a:
    case 0n:
      add_comm(x, y)
    case 1n+p:
      (%add_right_comm(p, x, y) : {1n+Nat.add(Nat.add(p, x), y) == 1n+_ : Nat}
      {==})

def Laws.l_ctrl_12(s, r_s, x, y):
  match s:
    case M.HSt{stage, seq, mirror, acc, tier, locked, halted, alert, overflow, breach, diff_zero, parity, log}:
      add_right_comm(acc, x, y)
