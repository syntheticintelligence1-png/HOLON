import Base
import ../core/LAWS.bend as C
import ./LAWS.bend as Laws

# uses the core's unproved law c_open as a lemma, importing core/LAWS.bend alone
def Laws.u_open():
  C.c_open(3n)
