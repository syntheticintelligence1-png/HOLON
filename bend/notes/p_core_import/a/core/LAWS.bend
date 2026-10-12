# I8 probe (a), hand-written: a core LAWS module with one proved law (c_ok) and one open law (c_open).
import Base

law c_ok:
  for +n: Nat
  {Nat.add(0n, n) == n : Nat}

# false in general, and proved nowhere
law c_open:
  for +n: Nat
  {Nat.add(n, 1n) == n : Nat}
