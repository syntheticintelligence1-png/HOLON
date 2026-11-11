import Base
import ../model/C8031a4.bend as M

law l_intent_a485355f19d5905c_inhabit:
  exs s: M.St
  exs x: M.X_pause
  {U32.is_eq(M.chk_pause(s, x), 0) == True{} : Bool}
