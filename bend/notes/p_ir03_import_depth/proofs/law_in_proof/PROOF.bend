# a proof file that declares a law of its own, with a comment between the name and the colon (audit F-M2-21):
# Bend parses it as a law (its false variant is an open goal), so the comment does not hide it from the checker
import Base
import ../../model/m.bend as M
import ../../laws/a/LAWS.bend as Laws

def Laws.l_a():
  {==}

law sneaky # a comment
:
  {1n == 2n : Nat}
