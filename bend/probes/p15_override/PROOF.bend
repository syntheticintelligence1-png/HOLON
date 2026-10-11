import Base
import ./LAWS.bend as Laws

# A proof file may not redefine the model it is proving things about.
def Laws.double(n: Nat) -> Nat:
  n

def Laws.double_two():
  {==}
