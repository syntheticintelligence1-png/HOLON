import Base

# A law with no proof def is an open claim: SOME PROOFS FAIL.
law open_claim:
  for x: Nat
  {Nat.add(x, 0n) == x : Nat}
