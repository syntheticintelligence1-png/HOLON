import Base
import ../../model/eval_ctrl_machine.bend as M
import ./LAWS.bend as Laws

def efq(-P: Type, x: Empty) -> P:
  match x:

def core_false_ne_true(e: {False{} == True{} : Bool}) -> Empty:
  (%Equal.sym(Bool, False{}, True{}, e) : M.is_true(_)
  Unit{})

def sub_diag_zero(a: Nat, b: Nat, eq: {Nat.is_eq(a, b) == True{} : Bool}) -> {Nat.is_eq(Nat.sub(Nat.add(a, 1n), Nat.add(b, 1n)), 0n) == True{} : Bool}:
  match a b eq:
    case 0n 0n eq:
      {==}
    case 0n 1n+bp eq:
      efq({Nat.is_eq(Nat.sub(Nat.add(0n, 1n), Nat.add(1n+bp, 1n)), 0n) == True{} : Bool}, core_false_ne_true(eq))
    case 1n+ap 0n eq:
      efq({Nat.is_eq(Nat.sub(Nat.add(1n+ap, 1n), Nat.add(0n, 1n)), 0n) == True{} : Bool}, core_false_ne_true(eq))
    case 1n+ap 1n+bp eq:
      sub_diag_zero(ap, bp, eq)

def Laws.l_ctrl_07(s, r_s, h0):
  match s h0:
    case M.HSt{stage, seq, mirror, acc, tier, locked, halted, alert, overflow, breach, diff_zero, parity, log} h0:
      sub_diag_zero(seq, mirror, h0)
