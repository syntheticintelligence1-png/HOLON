# a './' segment inside a relative import path
import Base
import ../../model/m.bend as M
import ../.././laws/a/LAWS.bend as Laws

def Laws.l_a():
  {==}
