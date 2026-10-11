import Base

# @unsafe skips the termination check; a "proof" that relies on it must be rejected.
@unsafe def loop(x: Nat) -> {Nat.add(x, 1n) == x : Nat}:
  loop(x)

law unsafe_claim:
  for x: Nat
  {Nat.add(x, 1n) == x : Nat}

def unsafe_claim(x):
  loop(x)
