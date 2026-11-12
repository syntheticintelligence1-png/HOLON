import Base
import ../model/Ce5e18e.bend as M

law l_intent_b91c19550edb31c4:
  for s: M.St
  for x: M.X_pause
  {Bool.or(Bool.not(U32.is_eq(M.chk_pause(s, x), 0)), M.w_eq(M.x_pause_caller(x), M.st_owner(s))) == True{} : Bool}
