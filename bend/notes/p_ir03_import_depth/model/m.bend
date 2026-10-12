# p_ir03_import_depth: a two-definition model, imported by the law and the proofs below.
import Base

def f(x: Nat) -> Nat:
  Nat.add(x, 1n)

def g(x: Nat) -> Nat:
  f(f(x))
