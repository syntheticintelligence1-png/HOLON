import Base
import ../../model/eval_ctrl_machine.bend as M
import ./LAWS.bend as Laws

def sub_zero_right(a: Nat) -> {Nat.sub(a, 0n) == a : Nat}:
  match a:
    case 0n:
      {==}
    case 1n+ap:
      {==}

def add_succ_right(a: Nat, +b: Nat) -> {Nat.add(a, 1n+b) == 1n+Nat.add(a, b) : Nat}:
  match a:
    case 0n:
      {==}
    case 1n+p:
      (%add_succ_right(p, b) : {1n+Nat.add(p, 1n+b) == 1n+_ : Nat}
      {==})

def add_zero_right(k: Nat) -> {Nat.add(k, 0n) == k : Nat}:
  match k:
    case 0n:
      {==}
    case 1n+p:
      (%add_zero_right(p) : {1n+Nat.add(p, 0n) == 1n+_ : Nat}
      {==})

def add_sub_id(+a: Nat, +x: Nat) -> {Nat.sub(Nat.add(a, x), x) == a : Nat}:
  match x:
    case 0n:
      Equal.trans(Nat, Nat.sub(Nat.add(a, 0n), 0n), Nat.sub(a, 0n), a,
        (%add_zero_right(a) : {Nat.sub(Nat.add(a, 0n), 0n) == Nat.sub(_, 0n) : Nat}; {==}),
        sub_zero_right(a))
    case 1n+xp:
      Equal.trans(Nat, Nat.sub(Nat.add(a, 1n+xp), 1n+xp), Nat.sub(1n+Nat.add(a, xp), 1n+xp), a,
        (%add_succ_right(a, xp) : {Nat.sub(Nat.add(a, 1n+xp), 1n+xp) == Nat.sub(_, 1n+xp) : Nat}; {==}),
        add_sub_id(a, xp))

def Laws.l_ctrl_10(s, r_s, x):
  match s:
    case M.HSt{stage, seq, mirror, acc, tier, locked, halted, alert, overflow, breach, diff_zero, parity, log}:
      add_sub_id(acc, x)
