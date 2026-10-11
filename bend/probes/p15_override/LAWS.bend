import Base

# Claims live in LAWS.bend; proofs in PROOF.bend fill them as `def Laws.<name>`.
def double(n: Nat) -> Nat:
  match n:
    case 0n:
      0n
    case 1n+p:
      2n+double(p)

law double_two:
  {double(2n) == 4n : Nat}
