# p_ir03_import_depth: the law, two directories below the probe root, importing the model by ../../
import Base
import ../../model/m.bend as M

law l_a:
  {M.g(1n) == 3n : Nat}
