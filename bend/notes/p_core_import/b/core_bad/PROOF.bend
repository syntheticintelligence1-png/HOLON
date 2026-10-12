import Base
import ./LAWS.bend as Laws

def Laws.c_ok(n):
  {==}

# a wrong helper in the imported proof file: claims 1 == 0
def bad_helper() -> {1n == 0n : Nat}:
  {==}
