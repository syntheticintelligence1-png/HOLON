import Base
import ../model/C741f84.bend as M

law cl_l_intent_ce4c4710f619fb00:
  exs s: M.St
  exs x: M.X_pause
  {Bool.or(Bool.not(U32.is_eq(M.chk_pause(s, x), 0)), M.w_eq(M.x_pause_caller(x), M.st_owner(s))) != True{} : Bool}
