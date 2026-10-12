# I8 probe (b): the same core with a wrong proof of c_ok.
import Base

law c_ok:
  for +n: Nat
  {Nat.add(0n, n) == n : Nat}
