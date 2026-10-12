import Base
import ../core_bad/PROOF.bend as CP
import ../core_bad/LAWS.bend as C
import ./LAWS.bend as Laws

def Laws.u_ok():
  C.c_ok(3n)
