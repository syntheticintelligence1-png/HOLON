import Base

# A false law: the checker must reject it and print expected/observed terms.
law bad:
  for x: Nat
  {Nat.add(x, 1n) == x : Nat}

def bad(x):
  {==}
