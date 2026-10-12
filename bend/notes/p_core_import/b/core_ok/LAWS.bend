# I8 probe (b): a fully proved core.
import Base

law c_ok:
  for +n: Nat
  {Nat.add(0n, n) == n : Nat}
