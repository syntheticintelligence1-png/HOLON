import Base
import ../model/Ce5e18e.bend as M

law l_intent_b91c19550edb31c4_inhabit:
  exs s: M.St
  exs x: M.X_pause
  {U32.is_eq(M.chk_pause(s, x), 0) == True{} : Bool}
