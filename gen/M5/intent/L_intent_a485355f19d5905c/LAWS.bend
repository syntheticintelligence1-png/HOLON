import Base
import ../model/C8031a4.bend as M

law l_intent_a485355f19d5905c:
  for s: M.St
  for x: M.X_pause
  {Bool.or(Bool.not(U32.is_eq(M.chk_pause(s, x), 0)), M.w_eq(M.x_pause_caller(x), M.st_owner(s))) == True{} : Bool}
